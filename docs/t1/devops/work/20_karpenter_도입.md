# [계획서] Karpenter 도입 - 지능형 노드 자동 프로비저닝

- **날짜**: 2026-02-24
- **작성자**: DevOps (AI 지원)
- **티켓**: None
- **참고**: 기존 `19_온디맨드_스팟_하이브리드_노드_그룹.md` (A안)을 대체하는 B안

---

## 📋 배경 및 목표

### 기존 Cluster Autoscaler의 한계 (현재 구조)
```
[현재]
aws_eks_node_group.main (ON_DEMAND, t3a.large x2)
  └─ cluster-autoscaler (helm_release, kube-system)
     └─ 노드가 부족할 때 ASG에 +1, 넘칠 때 -1만 할 수 있음
     └─ 미리 정해둔 인스턴스 타입만 사용 가능
     └─ 노드 추가에 3~5분 소요
```

### Karpenter 도입 후 구조
```
[도입 후]
aws_eks_node_group.core (ON_DEMAND, t3a.large x1, 고정)
  └─ Karpenter Controller (여기서 실행, 절대 내려가면 안 됨)
  └─ airflow-scheduler, redash-server, 각종 DB (핵심 파드 고정)

Karpenter가 직접 관리하는 노드들 (ASG 없음!)
  └─ NodePool "default": 스팟 우선(t3a.large, t3.large, m5a.large), 재고 없으면 온디맨드 자동 폴백
     └─ 평상시 스팟 1대로 시작 (airflow-triggerer, redash-workers, vanna-api, slack-bot)
  └─ 파드 Pending 감지 → 20~60초 안에 새 노드 자동 주문
  └─ 부하 해소 시 자동으로 노드 반납 (Consolidation)
```

---

## 🗺️ 아키텍처 설계

### NodePool 분리 전략

| NodePool 이름 | Capacity Type | 배치 파드 | 인스턴스 타입 |
| :--- | :--- | :--- | :--- |
| `on-demand` | ON_DEMAND 우선 | airflow-webserver, airflow-scheduler, redash-server, 각종 DB | t3a.large, t3.large |
| `spot-workers` | SPOT 우선 | airflow-triggerer, redash-workers(x3), vanna-api, slack-bot, report-generator | t3a.large, t3.large, m5a.large (다양하게 섞어 회수 리스크 분산) |

### 파드 배치 메커니즘

```yaml
# 온디맨드 파드 예시 (죽으면 짜증나는 것들)
nodeSelector:
  karpenter.sh/nodepool: "on-demand"

# 스팟 파드 예시 (일꾼들)
nodeSelector:
  karpenter.sh/nodepool: "spot-workers"
tolerations:
  - key: "karpenter.sh/disruption"
    operator: "Exists"
```

---

## 📝 작업 단계 (테라폼 기준)

### Step 1. Karpenter IAM 역할 생성 [NEW] `02-iam.tf`

Karpenter Controller가 AWS API를 직접 호출(EC2 생성/삭제)하려면 전용 IAM Role이 필요합니다.

```hcl
# Karpenter Controller IRSA Role
resource "aws_iam_role" "karpenter_controller" {
  name = "${var.project_name}-karpenter-controller-role"
  assume_role_policy = ...  # OIDC 기반 IRSA
}

# Karpenter Node Instance Profile
# Karpenter가 직접 띄우는 노드들이 사용할 IAM Instance Profile
resource "aws_iam_instance_profile" "karpenter_node" { ... }
```

**필요한 EC2 권한 (핵심)**:
- `ec2:RunInstances`, `ec2:TerminateInstances` (노드 생성/삭제)
- `ec2:DescribeInstances`, `ec2:DescribeInstanceTypes` (최저가 타입 조회)
- `ec2:CreateFleet`, `ec2:CreateLaunchTemplate` (Launch Template 생성)
- `iam:PassRole` (노드에 IAM Role 부여)
- `ssm:GetParameter` (EKS 최적화 AMI ID 조회)

---

### Step 2. 기존 노드 그룹을 "코어 그룹"으로 축소 [MODIFY] `06-eks.tf`

Cluster Autoscaler 관련 태그를 제거하고, **온디맨드 1대**만 고정 유지합니다.
이 노드에는 Karpenter 컨트롤러 + 핵심 파드(DB, 웹서버)가 배치됩니다.

```hcl
resource "aws_eks_node_group" "core" {      # 이름 변경: main → core
  ...
  instance_types = ["t3a.large"]
  capacity_type  = "ON_DEMAND"

  scaling_config {
    desired_size = 1   # ← 온디맨드 1대로 고정
    min_size     = 1
    max_size     = 1   # Karpenter가 나머지를 모두 관리
  }

  # Karpenter가 이 노드에 일반 워커 파드를 배치하지 않도록
  taint {
    key    = "CriticalAddonsOnly"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  tags = {
    Name = "${var.project_name}-core-node-group"
    # Cluster Autoscaler 태그 제거
  }
}
```

### Step 2-a. Karpenter 기본 노드 설계 (평상시 스팟 1대)

Karpenter가 관리하는 **기본(default) NodePool**을 평상시 스팟 1대로 설정합니다.

```yaml
# NodePool: 스팟 우선, 온디맨드 폴백
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]   # 스팟 먼저 시도, 없으면 온디맨드 자동 폴백
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3a.large", "t3.large", "m5a.large"]  # 다양한 타입으로 회수 리스크 분산
  limits:
    cpu: "16"       # 최대 8코어 (t3a.large 기준 4노드까지 허용)
    memory: "64Gi"
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 60s
```

**평상시 예상 상태**:
```
[온디맨드 1대 - 코어] ← Karpenter Controller, airflow-scheduler, redash-server, 각종 DB
[스팟 1대 - Karpenter] ← airflow-triggerer, redash-workers, vanna-api, slack-bot
```

---

### Step 3. Karpenter 설치 [NEW] `15-karpenter.tf`

```hcl
# Karpenter 컨트롤러 헬름 설치
resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = "1.3.3"   # EKS 1.29 호환 버전 확인 필요
  namespace  = "kube-system"

  set {
    name  = "settings.clusterName"
    value = aws_eks_cluster.main.name
  }
  set {
    name  = "settings.interruptionQueue"
    value = aws_sqs_queue.karpenter_interruption.name  # 스팟 회수 알림용
  }
  ...
}

# 스팟 인스턴스 회수 알림을 받을 SQS 큐
resource "aws_sqs_queue" "karpenter_interruption" {
  name = "${var.project_name}-karpenter-interruption"
}
```

---

### Step 4. NodePool & EC2NodeClass 정의 [NEW] `11-k8s-apps.tf`

쿠버네티스 Custom Resource(CR)로 "어떤 노드를, 어떤 전략으로 띄울지" 선언합니다.

```hcl
# EC2NodeClass: 노드의 하드웨어/네트워크 설정
resource "kubectl_manifest" "karpenter_node_class" {
  yaml_body = <<YAML
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2   # Amazon Linux 2
  role: "${aws_iam_role.karpenter_node.name}"
  subnetSelectorTerms:
    - id: "${sort(data.aws_subnets.default.ids)[0]}"
  securityGroupSelectorTerms:
    - tags:
        aws:eks:cluster-name: "${aws_eks_cluster.main.name}"
YAML
}

# NodePool: 온디맨드 전용 (핵심 서비스)
resource "kubectl_manifest" "nodepool_on_demand" {
  yaml_body = <<YAML
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: on-demand
spec:
  template:
    spec:
      nodeClassRef:
        name: default
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3a.large", "t3.large"]
  limits:
    cpu: "8"
    memory: "32Gi"
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
YAML
}

# NodePool: 스팟 전용 (워커 파드)
resource "kubectl_manifest" "nodepool_spot" {
  yaml_body = <<YAML
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: spot-workers
spec:
  template:
    spec:
      taints:
        - key: node-type
          value: spot
          effect: NoSchedule
      nodeClassRef:
        name: default
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3a.large", "t3.large", "m5a.large", "m5.large"]
  limits:
    cpu: "16"
    memory: "64Gi"
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 30s
YAML
}
```

---

### Step 5. Cluster Autoscaler 제거 [DELETE]

```hcl
# 12-metrics-server.tf에 있는 helm_release.cluster_autoscaler 블록 삭제
# 02-iam.tf에 있는 aws_iam_role.cluster_autoscaler 및 관련 policy 삭제
```

---

### Step 6. 파드 배치 설정 추가 [MODIFY]

스팟 노드에 배치할 일꾼 파드들에 `nodeSelector` & `toleration` 추가

**수정 파일 목록**:
- `infrastructure/terraform/11-k8s-apps.tf`: Slack Bot, Report Generator, Vanna API
- `infrastructure/helm-values/airflow.yaml`: `triggerer` 섹션에 추가
- `infrastructure/terraform/10-applications.tf`: Redash Workers (adhoc, generic, scheduled)

---

## 🚀 실행 순서 (중요!)

```bash
# 1단계: IAM 및 SQS 먼저 생성 (Karpenter 설치 전 선행 필수)
terraform apply -target="aws_iam_role.karpenter_controller" \
                -target="aws_iam_instance_profile.karpenter_node" \
                -target="aws_sqs_queue.karpenter_interruption"

# 2단계: Karpenter 컨트롤러 설치
terraform apply -target="helm_release.karpenter"

# 3단계: NodePool & EC2NodeClass 생성
terraform apply -target="kubectl_manifest.karpenter_node_class" \
                -target="kubectl_manifest.nodepool_on_demand" \
                -target="kubectl_manifest.nodepool_spot"

# 4단계: 파드 배치 설정 반영 및 CA 제거 (전체 apply)
terraform apply

# 5단계: 검증
kubectl get nodes -L karpenter.sh/nodepool,eks.amazonaws.com/capacityType
kubectl get pods -A -o wide --sort-by='.spec.nodeName'
kubectl top nodes
```

---

## ✅ 체크리스트

- [ ] Step 1: `02-iam.tf` — Karpenter Controller Role, Node Instance Profile, SQS 권한 추가
- [ ] Step 2: `06-eks.tf` — 기존 노드 그룹을 `core`로 전환, CA 태그 제거
- [ ] Step 3: `15-karpenter.tf` 신규 생성 — Karpenter Helm, SQS 큐 정의
- [ ] Step 4: `11-k8s-apps.tf` — NodePool, EC2NodeClass CRD 정의
- [ ] Step 5: `12-metrics-server.tf` — Cluster Autoscaler 헬름 릴리즈 제거
- [ ] Step 6-a: `11-k8s-apps.tf` — Slack Bot, Vanna API, Report Generator 스팟 설정
- [ ] Step 6-b: `airflow.yaml` — Triggerer 스팟 배치 설정
- [ ] Step 6-c: `10-applications.tf` — Redash Workers 스팟 배치 설정
- [ ] 전체 `terraform apply` 실행 및 노드/파드 배치 검증

---

## ⚠️ 리스크 및 사전 확인 사항

| 항목 | 내용 |
| :--- | :--- |
| **EKS 버전 호환성** | 현재 EKS `1.29` 사용 중. Karpenter `v1.x`는 EKS 1.26+ 지원 (호환 OK) |
| **kubectl 프로바이더** | `EC2NodeClass`, `NodePool` CRD를 테라폼으로 배포하려면 `kubectl` provider 추가 필요 (`01-providers.tf`) |
| **AMI 자동 업데이트** | Karpenter는 EKS 최적화 AMI를 SSM을 통해 자동으로 선택함. 별도 AMI 관리 불필요 |
| **롤링 교체 중 서비스 중단** | CA 제거 → Karpenter 도입 시, 기존 CA가 관리하던 노드들에서 잠깐의 파드 재스케줄링 발생 가능 |
| **Consolidation 주의** | Karpenter의 자동 통합(Consolidation) 기능이 공격적으로 동작하면 파드가 예상치 못하게 재시작될 수 있음. DB 파드는 반드시 `on-demand` 노드에 고정 필요 |
