# Design: EKS 프로덕션 배포 — vanna-api & slack-bot 현시점 기능 이식

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | eks-production-deployment |
| 설계일 | 2026-03-27 |
| 참조 Plan | `15_eks-production-deployment/01-plan/features/eks-production-deployment.plan.md` |
| 변경 파일 | `variables.tf`, `terraform.tfvars`, `11-k8s-apps.tf` |

---

## 1. 변경 파일별 상세 설계

### 1.1 `infrastructure/terraform/variables.tf` — 신규 변수 9개 추가

기존 변수 블록 끝(`reranker_top_k` 아래)에 추가한다.

```hcl
# ------------------------------------------------------------------------------
# Phase 2: 신규 Feature Flags (EKS 이식)
# ------------------------------------------------------------------------------
variable "multi_turn_enabled" {
  description = "멀티턴 대화 활성화 (이전 대화 이력 참조)"
  type        = bool
  default     = false
}

variable "self_correction_enabled" {
  description = "SQL 자동교정 활성화 (검증 실패 시 LLM 재생성)"
  type        = bool
  default     = false
}

variable "max_correction_attempts" {
  description = "Self-Correction 최대 재시도 횟수"
  type        = number
  default     = 3
}

variable "reranker_enabled" {
  description = "Reranker 활성화 (현재 코드에서 영구 비활성화 상태 — PHASE2_RAG_ENABLED=true여도 _reranker=None 고정)"
  type        = bool
  default     = false
}

variable "llm_timeout_seconds" {
  description = "LLM API 호출 타임아웃 (초)"
  type        = number
  default     = 60
}

variable "debug" {
  description = "디버그 모드 (EKS 프로덕션은 false)"
  type        = bool
  default     = false
}

variable "history_table_name" {
  description = "멀티턴 대화 이력 조회용 DynamoDB 테이블명 (conversation_history_retriever.py의 HISTORY_TABLE_NAME)"
  type        = string
  default     = "capa-dev-query-history"
}

variable "vanna_api_timeout" {
  description = "slack-bot → vanna-api 호출 타임아웃 (초, Athena 쿼리 대기 포함)"
  type        = number
  default     = 310
}

variable "slack_thread_enabled" {
  description = "Slack 스레드 답글 모드 활성화"
  type        = bool
  default     = true
}
```

---

### 1.2 `infrastructure/terraform/terraform.tfvars` — 기존 4개 수정 + 신규 9개 추가

#### A. 기존 항목 값 수정

```hcl
# 기존: false → 수정 (로컬 동작값 반영)
phase2_rag_enabled      = true   # retrieve_v2() 활성화 (Reranker는 코드에서 영구 비활성화)
phase2_feedback_enabled = true   # 👍 피드백 → DynamoDB 저장 (vanna.train() 즉시 호출 방지)
async_query_enabled     = true   # AsyncQueryManager 초기화 활성화
dynamodb_enabled        = true   # DynamoDB 접근 활성화
```

#### B. 신규 항목 추가

```hcl
# ------------------------------------------------------------------------------
# Phase 2: 신규 Feature Flags (EKS 이식 — 로컬 동작값 반영)
# ------------------------------------------------------------------------------
multi_turn_enabled        = true
self_correction_enabled   = true
max_correction_attempts   = 3
reranker_enabled          = false
llm_timeout_seconds       = 60
debug                     = false   # EKS 프로덕션 — 로컬(true)과 다르게 설정
history_table_name        = "capa-dev-query-history"

# Slack Bot
vanna_api_timeout    = 310
slack_thread_enabled = true

# 내부 서비스 인증 토큰 (variables.tf default="" → 실제 토큰 입력 필요)
internal_api_token = "<실제_토큰_값>"
```

> `internal_api_token`: 로컬 `.env`의 `INTERNAL_API_TOKEN` 값 입력. vanna-api ↔ slack-bot 양방향 인증에 사용.

---

### 1.3 `infrastructure/terraform/11-k8s-apps.tf` — ENV 블록 추가

#### vanna-api Deployment (7개 추가)

`RERANKER_TOP_K` env 블록 직후, `volume_mount` 블록 직전에 삽입.

```hcl
          # Phase 2: 신규 Feature Flags (EKS 이식)
          env {
            name  = "MULTI_TURN_ENABLED"
            value = tostring(var.multi_turn_enabled)
          }
          env {
            name  = "SELF_CORRECTION_ENABLED"
            value = tostring(var.self_correction_enabled)
          }
          env {
            name  = "MAX_CORRECTION_ATTEMPTS"
            value = tostring(var.max_correction_attempts)
          }
          env {
            name  = "RERANKER_ENABLED"
            value = tostring(var.reranker_enabled)
          }
          env {
            name  = "LLM_TIMEOUT_SECONDS"
            value = tostring(var.llm_timeout_seconds)
          }
          env {
            name  = "DEBUG"
            value = tostring(var.debug)
          }
          env {
            name  = "HISTORY_TABLE_NAME"
            value = var.history_table_name
          }
```

#### slack-bot Deployment (2개 추가)

`INTERNAL_API_TOKEN` secret_key_ref 블록 직후, `resources` 블록 직전에 삽입.

```hcl
          # Phase 2: 신규 설정 (EKS 이식)
          env {
            name  = "VANNA_API_TIMEOUT"
            value = tostring(var.vanna_api_timeout)
          }
          env {
            name  = "SLACK_THREAD_ENABLED"
            value = tostring(var.slack_thread_enabled)
          }
```

---

### 1.4 `services/vanna-api/Dockerfile` — 이미 완료

Reranker 모델 다운로드 주석처리 완료 (`RERANKER_ENABLED=false` 운영 중).

---

## 2. 배포 시퀀스

```
1. terraform.tfvars 수정 (기존 4개 값 변경 + 신규 9개 추가)
        ↓
2. variables.tf 변수 9개 추가
        ↓
3. 11-k8s-apps.tf ENV 블록 추가 (vanna-api 7개, slack-bot 2개)
        ↓
4. docker build & ECR push
   ├── vanna-api: cd services/vanna-api
   │   docker build -t <ECR_URL>/capa-vanna-api:latest .
   │   docker push <ECR_URL>/capa-vanna-api:latest
   └── slack-bot: cd services/slack-bot
       docker build -t <ECR_URL>/capa-slack-bot:latest .
       docker push <ECR_URL>/capa-slack-bot:latest
        ↓
5. terraform plan  ← 변경 내용 검토 (ENV 추가 + deployment 변경만 있어야 함)
        ↓
6. terraform apply
        ↓
7. kubectl rollout restart deployment/vanna-api -n vanna
   kubectl rollout restart deployment/slack-bot -n slack-bot
        ↓
8. kubectl rollout status deployment/vanna-api -n vanna
   kubectl rollout status deployment/slack-bot -n slack-bot
        ↓
9. ChromaDB 시딩 (최초 배포 or 데이터 초기화 필요 시)
   kubectl exec -n vanna deployment/vanna-api -- python scripts/seed_chromadb.py
   (seed_chromadb.py 내부에서 reset_collections() → 재시딩 수행)
        ↓
10. E2E 검증 (Slack 멘션 테스트)
```

---

## 3. terraform plan 예상 변경

`terraform plan` 실행 시 아래 리소스만 변경되어야 한다. 그 외 변경이 있으면 apply 중단.

| 리소스 | 변경 유형 | 내용 |
|--------|---------|------|
| `kubernetes_deployment.vanna_api` | update in-place | ENV 7개 추가 + phase2_rag/dynamodb/async/feedback 값 변경 |
| `kubernetes_deployment.slack_bot` | update in-place | ENV 2개 추가 |
| `kubernetes_secret.vanna_secrets` | update in-place | `internal-api-token` 값 설정 |
| `kubernetes_secret.slack_bot_secrets` | update in-place | `internal-api-token` 값 설정 |

---

## 4. 롤백 계획

문제 발생 시:

```bash
# 이전 이미지로 롤백
kubectl rollout undo deployment/vanna-api -n vanna
kubectl rollout undo deployment/slack-bot -n slack-bot

# tfvars 복구 후 재적용
git checkout infrastructure/terraform/terraform.tfvars
terraform apply
```

---

## 5. ECR 빌드 명령어 (참고)

```bash
# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  827913617635.dkr.ecr.ap-northeast-2.amazonaws.com

# vanna-api
cd services/vanna-api
docker build -t 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-vanna-api:latest .
docker push 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-vanna-api:latest

# slack-bot
cd ../slack-bot
docker build -t 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-slack-bot:latest .
docker push 827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-slack-bot:latest
```
