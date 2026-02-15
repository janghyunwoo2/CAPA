# 15. Slack Bot Echo 배포 결과 (완료)

**작업 일시**: 2026-02-15  
**작업자**: DevOps Team  
**상태**: ✅ **Success**

---

## 1. 개요
Slack에서 사용자의 멘션을 수신하고 응답할 수 있는 기본 **Echo Bot**을 EKS에 배포하였습니다.  
Vanna AI 및 Report Generator와의 향후 연동을 위해 **Socket Mode**를 사용하였으며, 내부 서비스 통신을 위한 환경 변수 주입이 완료되었습니다.

---

## 2. 배포 내역

### 2.1 애플리케이션 (`services/slack-bot/`)
- [x] **언어/프레임워크**: Python 3.11 / Slack Bold (Socket Mode)
- [x] **주요 기능**:
    - `@앱이름` 멘션 감지 (`app_mention` 이벤트)
    - `echo <메시지>` 명령어 처리
    - `/health` 엔드포인트 제공 (Liveness/Readiness Probe용)
- [x] **Dockerfile**: `python:3.11-slim` 기반, 포트 3000 노출

### 2.2 인프라 (`infrastructure/terraform/11-k8s-apps.tf`)
- [x] **Namespace**: `slack-bot`
- [x] **ECR Repository**: `capa-slack-bot` (Mutable, Scan on push)
- [x] **Secret**: `slack-bot-secrets` (Bot Token, App Token 저장)
- [x] **Service**: ClusterIP (Port 3000)
- [x] **Deployment**:
    - Replicas: 1
    - Resources: CPU 100m~500m, Mem 128Mi~512Mi
    - Env Vars: `VANNA_API_URL`, `REPORT_API_URL` (Internal DNS)

---

## 3. 검증 결과

### 3.1 파드 상태 확인
```bash
$ kubectl get pods -n slack-bot
NAME                         READY   STATUS    RESTA..
slack-bot-7db4b9b564-ddtd7   1/1     Running   0
```

### 3.2 로그 확인 (Socket Mode 연결)
```bash
$ kubectl logs -n slack-bot -l app=slack-bot
INFO:slack_bolt.App:⚡️ Bolt app is running!
INFO:slack_bolt.App:Starting to receive messages from a new connection
```

### 3.3 기능 테스트 (Slack)
사용자가 슬랙 채널에서 봇을 호출하여 응답을 확인했습니다.

> **User**: `@slack-ai-bot echo 안녕`  
> **Bot**: `Echo: 안녕`

---

## 4. 이슈 및 해결
- **초기 계획 변경**: Helm Chart(`generic-service`)를 사용하는 대신, Vanna AI 배포와 일관성을 유지하기 위해 **Terraform Native Resource (`kubernetes_deployment` 등)**를 직접 정의하여 배포하였습니다.
- **권한 설정**: `app_mentions:read`, `chat:write` 스코프가 필요함을 확인하고 적용하였습니다.

---

## 5. 다음 단계
- **[16_E2E_통합_검증.md](../work/16_E2E_통합_검증.md)**
    - Slack Bot에서 Vanna AI API(`POST /generate_sql`) 호출 연동
    - "매출 데이터 보여줘" -> SQL 생성 -> 결과 리턴 흐름 구현
