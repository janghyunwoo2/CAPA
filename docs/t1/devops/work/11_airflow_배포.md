# 작업 10: Airflow 배포

> **Phase**: 3 (EKS Apps Layer)  
> **담당**: DevOps Engineer  
> **예상 소요**: 15분  
>- **이전 단계**: [10_helm_values_준비.md](./10_helm_values_준비.md)
>- **다음 단계**: [12_redash_배포.md](./12_redash_배포.md)

---

## 1. 목표

Apache Airflow를 Helm Chart로 EKS에 배포하고, Webserver에 접속하여 정상 작동을 확인합니다.

---

## 2. 실행 단계

### 2.1 Helm Repository 추가

```powershell
# Apache Airflow Helm Chart 저장소 추가
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# 확인
helm search repo airflow

# 예상 출력:
# NAME                 CHART VERSION  APP VERSION
# apache-airflow/airflow  1.12.0       2.8.1
```

### 2.2 Namespace 생성

```powershell
kubectl create namespace airflow

# 확인
kubectl get namespaces | Select-String "airflow"
```

### 2.3 Airflow 배포

```powershell
# Helm install
helm install airflow apache-airflow/airflow `
    -n airflow `
    -f infrastructure\helm-values\airflow.yaml

# 예상 출력:
# NAME: airflow
# NAMESPACE: airflow
# STATUS: deployed
# ... (설치 메시지)
```

### 2.4 Pod 상태 확인

```powershell
# Pod 확인 (모든 Pod이 Running될 때까지 대기, 3~5분)
kubectl get pods -n airflow -w

# 예상 출력:
# NAME                                 READY   STATUS
# airflow-postgresql-0                 1/1     Running
# airflow-scheduler-0                  2/2     Running
# airflow-webserver-xxxxx              1/1     Running
```

### 2.5 Webserver 외부 IP 확인

```powershell
# LoadBalancer Service 확인
kubectl get svc -n airflow | Select-String "webserver"

# 예상 출력:
# airflow-webserver  LoadBalancer  10.100.x.x  a123...elb.amazonaws.com  8080:30123/TCP
```

---

## 3. 검증 방법

### 3.1 Webserver 접속

```powershell
# LoadBalancer URL 가져오기
$WebserverURL = (kubectl get svc airflow-webserver -n airflow -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
Write-Host "Airflow URL: http://$WebserverURL:8080"

# 브라우저에서 접속
# ID: admin
# PW: admin
```

### 3.2 Scheduler 로그 확인

```powershell
kubectl logs -n airflow deployment/airflow-scheduler --tail=50

# 예상 출력:
# [2026-02-11 21:45:00] {scheduler_job.py:XXX} INFO - Scheduler started
```

### 3.3 Database 연결 테스트

```powershell
# Airflow CLI 테스트
kubectl exec -n airflow deployment/airflow-scheduler -- airflow version

# 예상 출력: 2.8.1
```

### 3.4 성공 기준

- [ ] 모든 Pod Running 상태
- [ ] Webserver LoadBalancer 외부 IP 할당됨
- [ ] 브라우저에서 Airflow UI 접속 가능
- [ ] admin/admin 로그인 성공

---

## 4. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `Pod pending (PVC)` | EBS CSI Driver 미설치 | 06_eks_cluster.md 확인 |
| `ImagePullBackOff` | ECR 권한 부족 | Node IAM Role 확인 |
| `LoadBalancer pending` | Node 리소스 부족 or Quota | Node 추가 or Quota 증가 |
| `CrashLoopBackOff` | 설정 오류 | `kubectl logs` 확인 |

---

## 5. 추가 설정 (선택)

### 5.1 DAG 추가 (테스트용)

```powershell
# ConfigMap으로 간단한 DAG 추가
kubectl create configmap test-dag -n airflow --from-literal=test.py='
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG("test_dag", start_date=datetime(2026, 1, 1), schedule="@daily") as dag:
    task = BashOperator(task_id="hello", bash_command="echo Hello CAPA")
'

# Airflow Webserver에서 DAG 확인
```

---

## 6. 다음 단계

✅ **Airflow 배포 및 접속 확인 완료** → `11_slack_bot_echo.md`로 이동

---

## 7. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**Airflow Webserver URL**: http://_______________:8080  
**로그인 정보**: admin / admin

**Pod 상태**:
```
(kubectl get pods -n airflow 출력)
```

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```
