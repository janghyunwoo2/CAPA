# EKS 인프라 (Kubernetes)

AWS EKS (Elastic Kubernetes Service)를 Terraform으로 관리합니다.

## 구조

```
infra/terraform/
├── main.tf          # 모든 모듈 호출
├── variables.tf     # 전역 변수
└── modules/
    └── eks/         # EKS 클러스터
        ├── main.tf          # 클러스터, Node Group, IAM
        ├── variables.tf     # 모듈 변수
        └── outputs.tf       # 출력값
```

## 아키텍처

### 클러스터 구성
- **EKS 클러스터**: Kubernetes 1.28
- **Node Group**: Auto Scaling Group (t3.medium ~ t3.large)
- **IAM 역할**: 클러스터 + Node
- **보안**: 보안 그룹, RBAC

### 환경별 사양

#### 개발 환경
- Node 개수: 2-5개
- 인스턴스 타입: t3.medium
- EBS: 50GB

#### 프로덕션 환경
- Node 개수: 3-10개
- 인스턴스 타입: t3.large
- EBS: 100GB (권장)

## 권한 관리

### EKS 클러스터 IAM
- AmazonEKSClusterPolicy
- AmazonEKSVPCResourceController

### Node IAM
- AmazonEKSWorkerNodePolicy
- AmazonEKS_CNI_Policy
- AmazonEC2ContainerRegistryReadOnly
- **커스텀**: S3, Kinesis, CloudWatch Logs 접근

## 배포

### 1단계: Terraform 초기화
```bash
cd infra/terraform
terraform init
```

### 2단계: 개발 환경 배포
```bash
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### 3단계: kubeconfig 설정
```bash
aws eks update-kubeconfig \
  --name capa-dev \
  --region ap-northeast-2
```

## 클러스터 접근

### kubectl 설정
```bash
# 클러스터 정보 확인
kubectl cluster-info

# Node 확인
kubectl get nodes

# 네임스페이스 확인
kubectl get namespace
```

### AWS IAM 기반 접근 제어
EKS는 AWS IAM을 Kubernetes RBAC과 통합합니다.

```bash
# aws-iam-authenticator 자동 설정됨
kubectl auth can-i get pods
```

## 자동 스케일링

### Cluster Autoscaler 설치 (권장)
```bash
helm repo add autoscaling https://kubernetes.github.io/autoscaler
helm install cluster-autoscaler autoscaling/cluster-autoscaler \
  --set autoDiscovery.clusterName=capa-dev
```

### Metrics Server 설치
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# 확인
kubectl get deployment metrics-server -n kube-system
```

## 모니터링

### CloudWatch Container Insights
```bash
# IAM 역할 생성
aws iam create-role --role-name EKSCloudWatchMetricsRole \
  --assume-role-policy-document file://trust-policy.json

# 추가 정보:
# https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-EKS.html
```

## 비용 최적화

### Spot Instances 사용 (개발)
```hcl
instance_types = ["t3.medium", "t2.medium"]  # Spot 대상
capacity_type  = "SPOT"
```

### Pod Disruption Budgets
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: airflow-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      component: webserver
```

## 참고

- [AWS EKS 문서](https://docs.aws.amazon.com/eks/)
- [EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)
