# Apps Layer (K8s 애플리케이션)

## 역할
Base 계층에서 생성된 EKS 클러스터에 Helm Chart를 배포합니다.

## 배포되는 애플리케이션

### 1. Apache Airflow
- **Namespace**: `airflow`
- **Chart**: `airflow` (공식 Helm Chart)
- **Values**: `../../helm-values/airflow.yaml`
- **용도**: 데이터 파이프라인 오케스트레이션

### 2. Vanna AI (Text-to-SQL)
- **Namespace**: `vanna`
- **Chart**: Custom Chart
- **Values**: `../../helm-values/vanna.yaml`
- **용도**: 자연어 → SQL 변환 API

### 3. Slack Bot
- **Namespace**: `default`
- **Type**: Kubernetes Deployment
- **용도**: Athena 쿼리 실행 및 Slack 응답

## Base 계층 정보 참조

`data.tf`에서 Base 계층의 EKS 정보를 가져옵니다:

```hcl
data "aws_eks_cluster" "cluster" {
  name = var.cluster_name  # base에서 생성한 클러스터 이름
}

data "aws_eks_cluster_auth" "cluster" {
  name = var.cluster_name
}
```

## Provider 설정

```hcl
provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.cluster.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.cluster.token
  }
}
```

## 배포 방법

**전제조건**: Base 계층이 먼저 배포되어야 합니다.

```bash
cd infrastructure/terraform/environments/dev/apps
terraform init
terraform plan
terraform apply
```

**예상 소요 시간**: ~5분

## 검증

```bash
# Airflow Pod 확인
kubectl get pods -n airflow

# Vanna Pod 확인
kubectl get pods -n vanna

# Slack Bot Pod 확인
kubectl get pods -l app=slack-bot
```

## 트러블슈팅

### 증상: `Error: Kubernetes cluster unreachable`
**원인**: Base 계층이 배포되지 않았거나, 클러스터 정보를 가져오지 못함

**해결**:
1. Base 계층 배포 확인: `cd ../base && terraform output`
2. kubectl 연결 테스트: `kubectl get nodes`
3. `cluster_name` 변수 확인

### 증상: Pod이 `Pending` 상태
**원인**: EBS CSI Driver 미설치

**해결**:
Base 계층에서 EBS CSI Driver Addon 설치 확인:
```bash
aws eks describe-addon --cluster-name capa-eks-dev --addon-name aws-ebs-csi-driver
```
