# Base Layer (AWS 인프라)

## 역할
AWS 리소스만 생성합니다. Helm이나 Kubernetes Provider는 사용하지 않습니다.

## 생성되는 리소스

### 1. VPC 및 네트워크
- VPC (기본 VPC 또는 신규 생성)
- Public/Private Subnet
- Security Groups

### 2. EKS Cluster
- EKS Control Plane
- Node Group (t3.medium × 2~4)
- OIDC Provider (IRSA 전제조건)
- EBS CSI Driver Addon

### 3. Data Pipeline
- Kinesis Stream (`capa-logs-stream`)
- Kinesis Firehose (`capa-logs-firehose`)
- S3 Bucket (`capa-data-lake`)
- Glue Database (`capa-glue-catalog`)
- Athena Workgroup (`capa-athena-workgroup`)

### 4. IAM Roles (IRSA)
- Airflow Role
- Slack Bot Role
- Firehose Role
- Cluster Autoscaler Role

### 5. ECR (Container Registry)
- Docker 이미지 저장소

## 중요 Outputs

`outputs.tf`에서 다음 정보를 출력하여 `apps` 계층에서 사용:

```hcl
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}
```

## 배포 방법

```bash
cd infrastructure/terraform/environments/dev/base
terraform init
terraform plan
terraform apply
```

**예상 소요 시간**: ~20분 (EKS 생성: ~12분)

## 검증

```bash
# EKS 클러스터 상태 확인
aws eks describe-cluster --name capa-eks-dev --query "cluster.status"

# kubectl 연결 설정
aws eks update-kubeconfig --name capa-eks-dev --region ap-northeast-2

# 노드 확인
kubectl get nodes
```

## 주의 사항
⚠️ **OIDC Provider는 모든 IRSA의 전제조건입니다.** 이것이 없으면 IAM Role이 작동하지 않습니다.

⚠️ **EBS CSI Driver**는 PersistentVolumeClaim을 사용하는 모든 워크로드(Airflow, Vanna)에 필수입니다.
