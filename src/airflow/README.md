# CAPA Airflow - EKS Helm 배포 구조

EKS (Elastic Kubernetes Service)에 Helm을 통해 Apache Airflow를 배포합니다.

## 구조

```
src/airflow/
├── dags/                   # DAG 정의 (DAG sync로 자동 실행)
├── logs/                   # (EKS: PersistentVolume)
├── plugins/                # 커스텀 플러그인
├── config/                 # 추가 설정
├── helm/                   # Helm 차트 설정
│   ├── Chart.yaml          # Helm 차트 정의
│   ├── values.yaml         # 기본 values
│   ├── values-dev.yaml     # 개발 환경
│   ├── values-prod.yaml    # 프로덕션 환경
│   └── templates/          # (선택) 커스텀 Kubernetes manifests
└── kubernetes/             # EKS 관련 설정
    ├── namespace.yaml      # Kubernetes namespace
    ├── secrets.yaml        # (템플릿) AWS 자격증명
    └── ingress.yaml        # (선택) ALB Ingress

infra/terraform/
└── modules/
    └── eks/                # EKS 클러스터
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## 배포 방식

### Option 1: 공식 Helm 차트 사용 (권장)
```bash
# Airflow 공식 Helm 저장소 추가
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# 개발 환경에 배포
helm install airflow apache-airflow/airflow \
  -f src/airflow/helm/values.yaml \
  -f src/airflow/helm/values-dev.yaml \
  -n airflow-dev --create-namespace

# 프로덕션 환경에 배포
helm install airflow apache-airflow/airflow \
  -f src/airflow/helm/values.yaml \
  -f src/airflow/helm/values-prod.yaml \
  -n airflow-prod --create-namespace
```

### Option 2: 커스텀 Helm 차트 (고도로 커스터마이징 필요할 때)
```bash
helm install airflow ./src/airflow/helm \
  -f src/airflow/helm/values-dev.yaml
```

## 주요 설정

- **Executor**: KubernetesExecutor (EKS 기반 동적 리소스)
- **PostgreSQL**: RDS 또는 EKS 내부 Postgres
- **DAG Sync**: Git 저장소에서 자동 동기화
- **Logging**: CloudWatch 또는 S3
- **RBAC**: Kubernetes RBAC 활성화

## 다음 단계

1. EKS 클러스터 생성 (Terraform)
2. Helm values 설정
3. 배포 및 DAG 테스트
