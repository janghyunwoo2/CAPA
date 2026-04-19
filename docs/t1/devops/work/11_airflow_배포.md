# 작업 10: Airflow 배포

> **Phase**: 3 (EKS Apps Layer)  
> **담당**: DevOps Engineer  
> **예상 소요**: 15분  
> **이전 단계**: [10_helm_values_준비.md](./10_helm_values_준비.md)
> **다음 단계**: [12_redash_배포.md](./12_redash_배포.md)

---

## 1. 목표

Apache Airflow를 Helm Chart로 EKS에 배포하고, Webserver에 접속하여 정상 작동을 확인합니다.
본 가이드는 **EKS 1.29 버전**을 기준으로 작성되었으며, 호환성 문제 해결을 위해 커스텀 PostgreSQL 이미지를 사용합니다.

---

## 2. 사전 준비 (Pre-requisites)

### 2.1 ECR 이미지 준비 (필수)
Airflow의 메타데이터 DB(`airflow-postgresql`) 컨테이너 구동을 위해 ECR에 이미지가 존재해야 합니다.

```powershell
# 1. Docker 로그인
aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com

# 2. 이미지 준비 및 푸시 (postgres:11)
docker pull postgres:11
docker tag postgres:11 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa/postgres:11
docker push 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa/postgres:11
```

---

## 3. 실행 단계

### 3.1 Terraform 배포
Airflow는 Terraform의 `helm_release` 리소스로 관리됩니다.

**Terraform 파일**: `infrastructure/terraform/environments/dev/base/10-applications.tf`
**Values 파일**: `infrastructure/helm-values/airflow.yaml`

```powershell
# Base 디렉토리로 이동
cd infrastructure\terraform\environments\dev\base

# Airflow 모듈 타겟 배포 (전체 apply 권장)
terraform apply -target=helm_release.airflow
```

**참고**: `helm_release` 리소스가 `kubernetes_storage_class.gp2` (EBS CSI Driver)에 의존성을 가집니다.

### 3.2 배포 확인

```powershell
# Helm Release 상태 확인
helm list -n airflow

# Pod 확인 (모든 Pod이 Running될 때까지 대기, 3~5분)
kubectl get pods -n airflow -w
```
**예상 출력**:
```text
NAME                                   READY   STATUS     RESTARTS
airflow-postgresql-0                   1/1     Running    0
airflow-scheduler-0                    1/1     Running    0
airflow-webserver-xxxxx                1/1     Running    0
airflow-triggerer-xxxxx                1/1     Running    0
```

### 3.3 Webserver 외부 IP 확인

```powershell
# LoadBalancer Service 확인
kubectl get svc -n airflow airflow-webserver
```

### 3.4 접속 정보 확인 (팀 공유용)

배포 후 팀원들에게 접속 정보를 공유하려면 아래 명령어를 사용하세요.

```powershell
# Airflow 접속 정보 및 계정 출력
terraform output airflow_webserver_url
terraform output airflow_admin_account
```

---

## 4. 검증 방법

### 4.1 Webserver 접속

```powershell
# LoadBalancer URL 가져오기
$WebserverURL = (kubectl get svc airflow-webserver -n airflow -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
Write-Host "Airflow URL: http://$WebserverURL:8080"
```

1.  브라우저에서 위 URL로 접속합니다.
2.  로그인: `admin` / `admin`

### 4.2 성공 기준
- [ ] PostgreSQL Pod가 `Running` 상태이며 로그에 에러 없음.
- [ ] Webserver LoadBalancer URL로 접속 가능.
- [ ] Admin 계정으로 로그인 성공.

---

## 5. 실패 시 대응 (Troubleshooting)

| 증상 | 원인 | 해결 방법 |
|------|------|-----------|
| `ImagePullBackOff` | ECR에 postgres 이미지가 없음 | **2.1 ECR 이미지 준비** 단계를 다시 수행 |
| `PVC Pending` | StorageClass 호환성 문제 | `05-storage-class.tf`의 `ebs.csi.aws.com` 설정 확인 |
| `CrashLoopBackOff` | DB 연결 실패 | `airflow-postgresql` Pod가 정상인지 먼저 확인 |

---

## 6. 다음 단계

✅ **Airflow 배포 및 접속 확인 완료** → [12_redash_배포.md](./12_redash_배포.md)로 이동
