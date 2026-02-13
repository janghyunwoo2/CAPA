# 작업 09: Helm Values 준비

> **Phase**: 3 (EKS Apps Layer)  
> **담당**: DevOps Engineer  
> **예상 소요**: 15분  
> **선행 작업**: 09_athena_데이터_검증.md

---

## 1. 목표

Airflow와 Slack Bot을 EKS에 배포하기 위한 Helm Values 파일을 준비합니다.

---

## 2. 생성할 파일

- `infrastructure/helm-values/airflow.yaml`
- `infrastructure/helm-values/redash.yaml` (신규)
- `infrastructure/helm-values/vanna.yaml` (신규)
- `infrastructure/helm-values/report-generator.yaml` (신규)
- `infrastructure/helm-values/chromadb.yaml` (신규)
- `infrastructure/helm-values/slack-bot.yaml`

---

## 3. 실행 단계

### 3.1 Airflow Helm Values

`infrastructure/helm-values/airflow.yaml`:

```yaml
# Airflow 공식 Helm Chart Values
# Repository: https://github.com/apache/airflow/tree/main/chart

# Executor 설정 (LocalExecutor - MVP 단순화)
executor: "LocalExecutor"

# PostgreSQL (내장 DB)
postgresql:
  enabled: true
  auth:
    enablePostgresUser: true
    postgresPassword: "airflow123"

# Redis (비활성화 - LocalExecutor 사용)
redis:
  enabled: false

# Webserver
webserver:
  replicas: 1
  service:
    type: LoadBalancer  # 외부 접근용
  defaultUser:
    enabled: true
    username: admin
    password: admin
    email: admin@example.com

# Scheduler
scheduler:
  replicas: 1

# DAG 저장소 (Git Sync 비활성화, ConfigMap 사용)
dags:
  persistence:
    enabled: true
    size: 1Gi

# 환경 변수
env:
  - name: AIRFLOW__CORE__LOAD_EXAMPLES
    value: "False"

# IRSA (EKS OIDC 설정 후 활성화)
serviceAccount:
  create: true
  name: airflow-sa
  # annotations:
  #   eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/capa-airflow-role

# 리소스 제한
resources:
  limits:
    cpu: 500m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 512Mi
```

### 3.2 Slack Bot Helm Values

`infrastructure/helm-values/slack-bot.yaml` (**generic-service 차트 사용**):

```yaml
# Slack Bot Echo 버전 (MVP)
replicaCount: 1

image:
  repository: <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/capa-slack-bot
  tag: "latest"
  pullPolicy: Always

service:
  type: ClusterIP
  port: 3000

# 환경 변수 (Slack Token은 Secret으로 관리)
env:
  - name: SLACK_BOT_TOKEN
    valueFrom:
      secretKeyRef:
        name: slack-bot-secret
        key: bot-token
  - name: SLACK_APP_TOKEN
    valueFrom:
      secretKeyRef:
        name: slack-bot-secret
        key: app-token

# IRSA
serviceAccount:
  create: true
  name: slack-bot-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<ACCOUNT_ID>:role/capa-bot-role

# 리소스
resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### 3.3 Redash Helm Values

`infrastructure/helm-values/redash.yaml`:

```yaml
serviceAccount:
  create: true
  name: redash-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<ACCOUNT_ID>:role/capa-redash-role

postgresql:
  enabled: true

env:
  REDASH_COOKIE_SECRET: "random-secret"
  REDASH_SECRET_KEY: "random-secret"
```

### 3.4 Report Generator Helm Values

`infrastructure/helm-values/report-generator.yaml` (**generic-service 차트 사용**):

```yaml
replicaCount: 1
image:
  repository: <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator
  tag: "latest"

service:
  type: ClusterIP
  port: 8000

serviceAccount:
  create: true
  name: report-generator-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<ACCOUNT_ID>:role/capa-report-role
```

### 3.5 Vanna AI & ChromaDB Values

`infrastructure/helm-values/chromadb.yaml`:
```yaml
persistence:
  enabled: true
  size: 10Gi
```

`infrastructure/helm-values/vanna.yaml` (**generic-service 차트 사용**):
```yaml
serviceAccount:
  create: true
  name: vanna-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<ACCOUNT_ID>:role/capa-vanna-role

env:
  - name: CHROMADB_HOST
    value: "chromadb"
  - name: CHROMADB_PORT
    value: "8000"
```

### 3.6 Slack Bot Secret 생성

```powershell
# Slack Token을 Kubernetes Secret으로 저장 (1회성)
kubectl create secret generic slack-bot-secret `
    -n default `
    --from-literal=bot-token='xoxb-YOUR-BOT-TOKEN' `
    --from-literal=app-token='xapp-YOUR-APP-TOKEN'

# 확인
kubectl get secret slack-bot-secret -n default
```

---

## 4. 검증 방법

### 4.1 Values 파일 문법 확인

```powershell
# Helm lint (문법 검증)
cd infrastructure\helm-values

# Airflow
helm show values apache-airflow/airflow | Out-File -FilePath airflow-default.yaml
# 기본 값과 비교

# Slack Bot (자체 Chart라면)
cat slack-bot.yaml
```

### 4.2 파일 존재 확인

```powershell
ls infrastructure\helm-values\

# 예상 출력:
# airflow.yaml
# redash.yaml
# report-generator.yaml
# vanna.yaml
# chromadb.yaml
# slack-bot.yaml
```

### 4.3 성공 기준

- [ ] `airflow.yaml` 생성됨
- [ ] `redash.yaml` 생성됨
- [ ] `report-generator.yaml` 생성됨
- [ ] `vanna.yaml` 생성됨
- [ ] `chromadb.yaml` 생성됨
- [ ] `slack-bot.yaml` 생성됨
- [ ] Slack Secret 생성됨
- [ ] YAML 문법 오류 없음

---

## 5. 다음 단계

✅ **Helm Values 준비 완료** → `11_airflow_배포.md`로 이동

---

## 6. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**생성된 파일**:
- [ ] airflow.yaml
- [ ] redash.yaml
- [ ] report-generator.yaml
- [ ] vanna.yaml
- [ ] chromadb.yaml
- [ ] slack-bot.yaml

**Slack Secret**:
- [ ] slack-bot-secret 생성됨

**메모**:
```
(발생한 이슈 기록)
```
