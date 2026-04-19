# Infrastructure 디렉토리

## 목적
CAPA 프로젝트의 **Infrastructure as Code (IaC)** 및 Kubernetes 배포 설정을 관리합니다.

## 구조

```
infrastructure/
├── helm-values/              # Helm Chart Values (K8s 앱 설정)
│   ├── airflow.yaml          # Apache Airflow 설정
│   └── vanna.yaml            # Vanna AI 설정
│
└── terraform/
    ├── modules/              # 재사용 가능한 Terraform 모듈
    │   ├── kinesis/          # Kinesis Stream + Firehose
    │   ├── s3/               # S3 Bucket + Lifecycle
    │   ├── glue/             # Glue Catalog + Tables
    │   ├── eks/              # EKS Cluster
    │   └── iam/              # IAM Roles (IRSA)
    │
    └── environments/dev/
        ├── base/             # [Layer 1] AWS 인프라
        │   ├── main.tf       # VPC, EKS, Kinesis, S3, Glue
        │   ├── outputs.tf    # cluster_endpoint, cluster_name 등
        │   └── providers.tf  # AWS Provider만 사용
        │
        └── apps/             # [Layer 2] K8s 애플리케이션
            ├── main.tf       # Helm Release (Airflow, Vanna)
            ├── data.tf       # base의 EKS 정보 참조
            └── providers.tf  # Helm/K8s Provider 설정
```

## 계층 분리 개념 (Layered Approach)

### 왜 Base와 Apps를 분리하는가?

**문제**: EKS 클러스터가 생성되기 전에는 Helm Provider가 클러스터 정보를 가져올 수 없습니다.

**해결**: 클러스터 생성(`base`)과 애플리케이션 배포(`apps`)를 분리하여 순차적으로 실행합니다.

### Layer 1: Base (AWS 인프라)
- **목적**: EKS, Kinesis, S3, Glue 등 AWS 리소스만 생성
- **Provider**: AWS Provider만 사용
- **State**: `base` 전용 State 파일
- **배포 시간**: ~20분 (EKS 생성: ~12분)

### Layer 2: Apps (K8s 애플리케이션)
- **목적**: Layer 1에서 생성된 EKS에 Helm Chart 배포
- **Provider**: Helm/Kubernetes Provider 사용
- **State**: `apps` 전용 State 파일
- **배포 시간**: ~5분

## 배포 순서

```bash
# 1. Base 인프라 배포
cd infrastructure/terraform/environments/dev/base
terraform init
terraform apply

# 2. Apps 배포
cd ../apps
terraform init
terraform apply
```

## 참고 문서
- [DevOps Implementation Guide](../docs/t1/devops/devops_implementation_guide.md)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
