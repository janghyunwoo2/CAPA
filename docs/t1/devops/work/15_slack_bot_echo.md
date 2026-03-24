# 작업 11: Slack Bot Echo 배포

> **Phase**: 3 (EKS Apps Layer)  
> **담당**: Backend Developer + DevOps  
> **예상 소요**: 20분  
> **선행 작업**: 14_vanna_ai_배포.md

---

## 1. 목표

Slack에서 "@capa-bot echo <메시지>"를 입력하면 그대로 응답하는 Echo Bot을 EKS에 배포합니다.

---

## 2. Echo Bot 구조

```
User: "@capa-bot echo Hello"
  ↓ (Slack Event)
Bot: "Echo: Hello"
```

---

## 3. 실행 단계

### 3.1 Echo Bot 코드 작성

`services/slack-bot/app.py`:

```python
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Slack App 초기화
app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.event("app_mention")
def handle_mention(event, say):
    """@capa-bot 멘션 처리"""
    text = event["text"]
    
    # "@capa-bot echo <메시지>" 파싱
    if "echo" in text.lower():
        message = text.split("echo", 1)[-1].strip()
        say(f"Echo: {message}")
    else:
        say("사용법: @capa-bot echo <메시지>")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡️ Slack Bot Echo 시작!")
    handler.start()
```

**requirements.txt**:
```
slack-bolt==1.18.0
```

### 3.2 Dockerfile 작성

`services/slack-bot/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
```

### 3.3 Docker 이미지 빌드 및 ECR 푸시

```powershell
cd services\slack-bot

# AWS Account ID 확인
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$REGION = "ap-northeast-2"
$REPO = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/capa-slack-bot"

# ECR 로그인
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REPO

# ECR Repository 생성 (없는 경우)
aws ecr create-repository --repository-name capa-slack-bot --region $REGION

# 이미지 빌드
docker build -t capa-slack-bot .

# 태그
docker tag capa-slack-bot:latest $REPO:latest

# 푸시
docker push $REPO:latest

Write-Host "✅ 이미지 푸시 완료: $REPO:latest"
```

### 3.4 Kubernetes Deployment 생성

`infrastructure/helm-values/slack-bot-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: slack-bot
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: slack-bot
  template:
    metadata:
      labels:
        app: slack-bot
    spec:
      serviceAccountName: slack-bot-sa
      containers:
      - name: slack-bot
        image: <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/capa-slack-bot:latest
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
        resources:
          limits:
            cpu: 200m
            memory: 256Mi
          requests:
            cpu: 100m
            memory: 128Mi
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: slack-bot-sa
  namespace: default
```

### 3.5 배포

```powershell
# Deployment 적용
kubectl apply -f infrastructure\helm-values\slack-bot-deployment.yaml

# 확인
kubectl get pods -l app=slack-bot

# 예상 출력:
# NAME                         READY   STATUS
# slack-bot-xxxxx              1/1     Running
```

---

## 4. 검증 방법

### 4.1 Pod 로그 확인

```powershell
kubectl logs -l app=slack-bot --tail=50

# 예상 출력:
# ⚡️ Slack Bot Echo 시작!
```

### 4.2 Slack에서 테스트

1. Slack 채널에서 Bot 멘션:
   ```
   @capa-bot echo Hello CAPA!
   ```

2. 예상 응답:
   ```
   Echo: Hello CAPA!
   ```

### 4.3 성공 기준

- [ ] Pod Running 상태
- [ ] 로그에 "Slack Bot Echo 시작!" 출력
- [ ] Slack에서 "@capa-bot echo test" 응답 확인
- [ ] "Echo: test" 메시지 수신

---

## 5. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `ImagePullBackOff` | ECR 권한 or 이미지 없음 | Node IAM Role 확인, 이미지 푸시 재확인 |
| `CrashLoopBackOff` | Token 오류 | Secret 값 확인 |
| Slack 응답 없음 | Event Subscription 미설정 | Slack App 설정 확인 |

---

## 6. 다음 단계

- **이전 단계**: [14_vanna_ai_배포.md](./14_vanna_ai_배포.md)
- **다음 단계**: [16_E2E_통합_검증.md](./16_E2E_통합_검증.md)

---

## 7. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**ECR 이미지**: _______________

**Slack 테스트**:
- 입력: @capa-bot echo _______________
- 응답: _______________

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```
