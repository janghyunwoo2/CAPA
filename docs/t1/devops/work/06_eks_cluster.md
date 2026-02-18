# 작업 06: EKS 클러스터 구축

> **Phase**: 1 (Terraform Base Layer)  
> **담당**: Infra Architect  
> **예상 소요**: 15분 (대부분 대기 시간)  
> **선행 작업**: 05_data_pipeline_기본.md

---

## 1. 목표

Kubernetes 애플리케이션을 배포할 EKS 클러스터를 생성합니다. (Cluster + Node Group + OIDC + EBS CSI)

---

## 2. 생성 리소스

| 리소스 | 생성 내용 | 소요 시간 |
|--------|----------|----------|
| EKS Cluster | Kubernetes 1.30 | ~8분 |
| Node Group | t3.medium × 2~4 (AL2023) | ~4분 |
| OIDC Provider | IRSA 전제조건 | 즉시 |
| EBS CSI Driver | PVC 지원 | ~1분 |

---

## 3. 실행 단계

### 3.1 EKS Terraform 파일 생성

`infrastructure/terraform/environments/dev/base/06-eks.tf`:

```hcl
# ============================================
# 1. 기본 VPC 및 Subnet 조회 (기존 리소스 사용)
# ============================================
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ============================================
# 2. EKS Cluster
# ============================================
resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-eks"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.30"
  
  vpc_config {
    subnet_ids              = data.aws_subnets.default.ids
    endpoint_private_access = true
    endpoint_public_access  = true
  }
  
  enabled_cluster_log_types = ["api", "audit", "authenticator"]
  
  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy
  ]
}

# ============================================
# 3. EKS Node Group
# ============================================
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-node-group"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = data.aws_subnets.default.ids
  
  instance_types = ["t3.medium"]
  capacity_type  = "ON_DEMAND"
  ami_type       = "AL2023_x86_64_STANDARD"

  scaling_config {
    desired_size = 2
    max_size     = 4
    min_size     = 2
  }
  
  update_config {
    max_unavailable = 1
  }
  
  depends_on = [
    aws_eks_cluster.main,
    aws_iam_role_policy_attachment.eks_node_policies
  ]
}

# ============================================
# 4. OIDC Provider (IRSA 전제조건)
# ============================================
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# ============================================
# 5. EBS CSI Driver Addon
# ============================================
resource "aws_eks_addon" "ebs_csi" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "aws-ebs-csi-driver"
  
  depends_on = [aws_eks_node_group.main]
}

# ============================================
# 6. Outputs
# ============================================
output "eks_cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "eks_cluster_oidc_issuer" {
  value = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

output "eks_cluster_name" {
  value = aws_eks_cluster.main.name
}
```

### 3.1 Terraform 실행

**디렉토리**: `infrastructure/terraform/environments/dev/base`
**(통합 배포: AWS 인프라 + Helm Apps)**

```powershell
cd infrastructure\terraform\environments\dev\base

# 초기화
terraform init

# 계획 확인
terraform plan

# 적용 (약 20~25분 소요)
terraform apply
```
# 예상 출력:
# aws_eks_cluster.main: Creating... (약 8분)
# aws_eks_cluster.main: Still creating... [8m0s elapsed]
# aws_eks_cluster.main: Creation complete
# aws_eks_node_group.main: Creating... (약 4분)
# ...
# Apply complete! Resources: 5 added, 0 changed, 0 destroyed.
```

### 3.3 kubectl 설정

```powershell
# kubectl config 업데이트
aws eks update-kubeconfig --name capa-eks --region ap-northeast-2

# 예상 출력:
# Added new context arn:aws:eks:ap-northeast-2:123456789012:cluster/capa-eks
```

---

## 4. 검증 방법

### 4.1 EKS Cluster 상태 확인

```powershell
aws eks describe-cluster --name capa-eks --query "cluster.status"

# 예상 출력: "ACTIVE"
```

### 4.2 Node 확인

```powershell
kubectl get nodes

# 예상 출력:
# NAME                                              STATUS   AGE
# ip-172-31-47-63.ap-northeast-2.compute.internal   Ready    2m
# ip-172-31-62-32.ap-northeast-2.compute.internal   Ready    2m
```

### 4.3 EBS CSI Driver 확인

```powershell
kubectl get pods -n kube-system | Select-String "ebs-csi"

# 예상 출력:
# ebs-csi-controller-xxxxx   6/6     Running
# ebs-csi-node-xxxxx        3/3     Running
```

### 4.4 OIDC Provider 확인

```powershell
aws iam list-open-id-connect-providers

# 예상 출력: EKS OIDC URL 포함
```

### 4.5 성공 기준

- [ ] EKS Cluster ACTIVE
- [ ] Node 2개 Ready 상태
- [ ] `kubectl get nodes` 성공
- [ ] EBS CSI Driver Pod Running
- [ ] OIDC Provider 생성됨

---

## 5. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `Cluster creation timed out` | 네트워크 문제 | 재시도 or VPC 확인 |
| `Node group creation failed` | IAM Role 권한 부족 | 04_iam_roles.md 확인 |
| `Unable to connect to cluster` | kubectl config 미설정 | `aws eks update-kubeconfig` 재실행 |
| `EBS CSI pods pending` | Node 리소스 부족 | Node Group 스케일업 |

---

## 6. 추가 설정 (선택)

### 6.1 EKS Access Entry (팀원 추가)

```hcl
# 06-eks.tf에 추가
resource "aws_eks_access_entry" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = "arn:aws:iam::123456789012:user/your-user"
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_eks_access_entry.admin.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  
  access_scope {
    type = "cluster"
  }
}
```

---

## 7. 다음 단계

✅ **EKS 설정 완료** → `07_alert_system.md`로 이동

> ⚠️ **Note**: Phase 1 (Terraform Base Layer) 완료! 이제 Phase 2 (E2E 테스트) 시작

---

## 8. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**EKS Cluster**:
- 이름: capa-eks
- 버전: 1.30 (2027년 7월까지 지원)
- OS: Amazon Linux 2023 (AL2023_x86_64_STANDARD)
- Node 수: ______
- Endpoint: _______________

**kubectl config**:
```
(kubectl get nodes 출력 결과)
```

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```
