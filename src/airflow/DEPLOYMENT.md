# EKS Airflow 배포 가이드

## 사전 준비

### 필수 도구
- AWS CLI v2
- kubectl
- Helm 3.x
- Terraform (인프라 배포용)

### AWS 계정 설정
```bash
aws configure
export AWS_REGION=ap-northeast-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

## 1단계: EKS 클러스터 생성 (Terraform)

### 개발 환경
```bash
cd infra/terraform

# 초기화
terraform init

# 계획
terraform plan -var-file="environments/dev/terraform.tfvars"

# 적용
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### 프로덕션 환경
```bash
terraform apply -var-file="environments/prod/terraform.tfvars"
```

클러스터 생성에 10-15분 소요됩니다.

## 2단계: kubectl 설정

```bash
# kubeconfig 업데이트
aws eks update-kubeconfig \
  --name capa-dev \
  --region ap-northeast-2

# 확인
kubectl get nodes
kubectl get pods -A
```

## 3단계: Namespace & Secret 생성

```bash
# Namespace 생성
kubectl apply -f src/airflow/kubernetes/namespace.yaml

# AWS 자격증명 Secret 생성 (개발)
kubectl create secret generic airflow-aws-secret \
  --from-literal=AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id) \
  --from-literal=AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key) \
  -n airflow-dev

# Git 접근 Secret (프라이빗 레포의 경우)
kubectl create secret generic git-secret \
  --from-literal=username=YOUR_GITHUB_USERNAME \
  --from-literal=password=YOUR_GITHUB_TOKEN \
  -n airflow-dev
```

## 4단계: Helm 저장소 추가

```bash
# Apache Airflow Helm 저장소
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# 설치된 차트 확인
helm search repo airflow
```

## 5단계: Airflow 배포 (Helm)

### 개발 환경 배포

```bash
# Helm 드라이런 (시뮬레이션)
helm install airflow apache-airflow/airflow \
  --namespace airflow-dev \
  -f src/airflow/helm/values.yaml \
  -f src/airflow/helm/values-dev.yaml \
  --debug --dry-run

# 실제 배포
helm install airflow apache-airflow/airflow \
  --namespace airflow-dev \
  -f src/airflow/helm/values.yaml \
  -f src/airflow/helm/values-dev.yaml
```

### 프로덕션 환경 배포

```bash
helm install airflow apache-airflow/airflow \
  --namespace airflow-prod \
  -f src/airflow/helm/values.yaml \
  -f src/airflow/helm/values-prod.yaml
```

## 6단계: 배포 확인

```bash
# Pod 상태 확인
kubectl get pods -n airflow-dev

# Webserver 로그 확인
kubectl logs -f deployment/airflow-webserver -n airflow-dev

# Service 확인
kubectl get svc -n airflow-dev

# Port Forwarding (로컬 접속)
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow-dev

# Airflow UI 접속: http://localhost:8080
```

## DAG 관리

### Git 동기화 설정
Helm values에서 DAG 동기화를 활성화하면, Git 저장소의 `src/airflow/dags/` 경로에서 자동으로 DAG를 가져옵니다.

```yaml
dags:
  gitSync:
    enabled: true
    repo: https://github.com/YOUR_ORG/CAPA.git
    branch: main
    subPath: src/airflow/dags
```

### DAG 작성 예시

`src/airflow/dags/example_dag.py`:
```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.athena import AthenaOperator

default_args = {
    'owner': 'data-engineering',
    'start_date': datetime(2024, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'ad_logs_analysis',
    default_args=default_args,
    schedule_interval='@daily',
    description='Daily ad logs analysis',
)

def extract_task():
    # Athena 쿼리 실행
    pass

task = PythonOperator(
    task_id='extract_logs',
    python_callable=extract_task,
    dag=dag,
)
```

## 모니터링 & 로깅

### CloudWatch 로그 확인
```bash
# Airflow Scheduler 로그
aws logs tail /aws/eks/capa-dev/scheduler --follow

# Airflow Webserver 로그
aws logs tail /aws/eks/capa-dev/webserver --follow
```

### Kubernetes 메트릭
```bash
# 리소스 사용량
kubectl top nodes -n airflow-dev
kubectl top pods -n airflow-dev
```

## 업그레이드 & 유지보수

### Airflow 버전 업그레이드
```bash
# 현재 설치된 버전 확인
helm list -n airflow-dev

# 업그레이드
helm upgrade airflow apache-airflow/airflow \
  -n airflow-dev \
  -f src/airflow/helm/values.yaml \
  -f src/airflow/helm/values-dev.yaml
```

### Helm 값 수정
```bash
# values.yaml 수정 후
helm upgrade airflow ./src/airflow/helm \
  -n airflow-dev
```

## 문제 해결

### PostgreSQL 연결 오류
```bash
# PostgreSQL Pod 확인
kubectl get pods -n airflow-dev | grep postgres

# PostgreSQL 로그 확인
kubectl logs <postgres-pod-name> -n airflow-dev

# PostgreSQL에 접속하여 확인
kubectl exec -it <postgres-pod-name> -n airflow-dev -- psql -U airflow -d airflow
```

### DAG가 로드되지 않음
```bash
# Git Sync Pod 로그 확인
kubectl logs <airflow-webserver-pod> -c git-sync -n airflow-dev

# DAG 폴더 확인
kubectl exec <airflow-scheduler-pod> -n airflow-dev -- ls -la /opt/airflow/dags/
```

### Worker가 작동하지 않음 (KubernetesExecutor)
```bash
# Pod의 이벤트 확인
kubectl describe pod <failed-task-pod> -n airflow-dev

# 리소스 제한 확인
kubectl get resourcequota -n airflow-dev
```

## 참고

- [Apache Airflow Helm Chart](https://airflow.apache.org/helm-chart/)
- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes Executor](https://airflow.apache.org/docs/apache-airflow/stable/executor/kubernetes.html)
