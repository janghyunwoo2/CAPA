# Plan: EKS 프로덕션 배포 — vanna-api & slack-bot 현시점 기능 이식

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | eks-production-deployment |
| 시작일 | 2026-03-27 |
| 예상 기간 | 반나절 |
| 대상 서비스 | vanna-api (namespace: vanna), slack-bot (namespace: slack-bot) |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | 로컬에서 동작하는 멀티턴·자동교정·DynamoDB·비동기폴링이 EKS에서 ENV 누락·값 불일치로 전부 비활성화 |
| **Solution** | 코드 `os.getenv` 전수 조사 후 — 누락 ENV 10개 추가 + 로컬 true인데 EKS false인 tfvars 4개 수정 |
| **Function / UX Effect** | Slack에서 멀티턴·자동교정·비동기폴링·DynamoDB 이력 저장이 로컬과 동일하게 동작 |
| **Core Value** | 코드 기준으로 검증된 최소 변경으로 현시점 로컬 기능을 EKS에 완전 이식 |

---

## 1. 변경 내용

### 1.1 `terraform.tfvars` — 기존 값 수정 (4개)

로컬 docker-compose에서 `true`로 동작 중이나 EKS tfvars에서 막혀 있는 항목.

| 변수 | 현재 | 변경 | 이유 |
|------|------|------|------|
| `dynamodb_enabled` | false | **true** | 로컬 동작값. `false`면 DynamoDB 접근 자체 비활성화 |
| `async_query_enabled` | false | **true** | 로컬 동작값. `false`면 AsyncQueryManager 미초기화 |
| `phase2_feedback_enabled` | false | **true** | 로컬 동작값. `false`면 👍 피드백이 vanna.train() 즉시 호출로 분기 |
| `phase2_rag_enabled` | false | **true** | 로컬 동작값. 코드 확인 결과 `true`여도 Reranker는 영구 비활성화(`_reranker = None` 하드코딩) — `retrieve_v2()` (Dynamic DDL Injection)만 활성화됨 |

### 1.2 `variables.tf` + `terraform.tfvars` + `11-k8s-apps.tf` — 신규 추가 (10개)

코드에서 `os.getenv`로 읽으나 EKS 배포 설정에 없는 항목.

**vanna-api (8개):**

| ENV | tfvars 값 | 이유 |
|-----|----------|------|
| `MULTI_TURN_ENABLED` | `true` | 멀티턴 대화 활성화 (로컬 동작값) |
| `SELF_CORRECTION_ENABLED` | `true` | SQL 자동교정 활성화 (로컬 동작값) |
| `MAX_CORRECTION_ATTEMPTS` | `3` | 최대 재시도 횟수 (로컬 동작값) |
| `RERANKER_ENABLED` | `false` | Reranker 코드 자체가 주석처리되어 이 값은 실제 무효. 명시적 관리 목적 |
| `LLM_TIMEOUT_SECONDS` | `60` | LLM 호출 타임아웃 (코드 기본값과 동일, 명시적 관리) |
| `DEBUG` | `false` | EKS는 프로덕션 — 로컬 true와 다르게 설정 |
| `HISTORY_TABLE_NAME` | `capa-dev-query-history` | `MULTI_TURN_ENABLED=true` 시 `conversation_history_retriever.py`가 읽는 ENV. `DYNAMODB_HISTORY_TABLE`과 별개 변수 |
| `internal_api_token` (tfvars만) | `(실제 토큰값)` | variables.tf 기본값이 `""` — 현재 EKS secret이 빈 문자열로 배포 중. 실제 토큰 설정 필요 |

**slack-bot (2개):**

| ENV | tfvars 값 | 이유 |
|-----|----------|------|
| `VANNA_API_TIMEOUT` | `310` | vanna-api 호출 타임아웃 (코드 기본값과 동일, 명시적 관리) |
| `SLACK_THREAD_ENABLED` | `true` | 스레드 답글 모드 (코드 기본값과 동일, 명시적 관리) |

---

## 2. 구현 순서

```
[Step 1] terraform.tfvars — 기존 3개 값 수정
    ↓
[Step 2] variables.tf — 8개 신규 변수 선언
    ↓
[Step 3] terraform.tfvars — 8개 신규 값 추가
    ↓
[Step 4] 11-k8s-apps.tf — vanna-api 6개 + slack-bot 2개 ENV 블록 추가
    ↓
[Step 5] Docker 이미지 빌드 & ECR 푸시 (vanna-api, slack-bot)
    ↓
[Step 6] terraform plan → 검토 후 apply
    ↓
[Step 7] kubectl rollout restart + status 확인
    ↓
[Step 8] Slack E2E 검증
```

---

## 3. 검증 기준

| 체크포인트 | 성공 조건 |
|-----------|---------|
| 파드 상태 | 모두 `Running 1/1` |
| Slack 멘션 | SQL + 결과 정상 반환 |
| 멀티턴 | 후속 질문에서 이전 컨텍스트 유지 |
| 비동기 폴링 | "⏳ 처리 중..." 후 결과 수신 |
| DynamoDB 이력 | `capa-dev-query-history` 레코드 적재 확인 |

---

## 4. 리스크

| 리스크 | 대응 |
|--------|------|
| terraform plan 예상 외 변경 | apply 전 반드시 확인 — ENV 추가 + deployment 변경 외 있으면 중단 |
| DynamoDB IAM 권한 (async-tasks ARN 누락) | terraform apply 후 실제 쿼리로 AccessDenied 여부 확인 |

---

## 5. 변경 파일

| 파일 | 변경 |
|------|------|
| `infrastructure/terraform/terraform.tfvars` | 기존 4개 값 수정 + 신규 9개 추가 (`internal_api_token` 포함) |
| `infrastructure/terraform/variables.tf` | 신규 변수 9개 추가 (`HISTORY_TABLE_NAME` 포함, `internal_api_token`은 이미 존재) |
| `infrastructure/terraform/11-k8s-apps.tf` | vanna-api ENV 7개 + slack-bot ENV 2개 추가 |
| `services/vanna-api/Dockerfile` | Reranker 모델 다운로드 주석처리 (`RERANKER_ENABLED=false`) |
| `services/vanna-api/` | 이미지 재빌드 |
| `services/slack-bot/` | 이미지 재빌드 |

> **ChromaDB 시딩 방법 (EKS):**
> `seed_chromadb.py`는 실행 시 기존 컬렉션을 먼저 삭제(`reset_collections()`) 후 재시딩하므로 중복 없음.
> ```bash
> kubectl exec -n vanna deployment/vanna-api -- python scripts/seed_chromadb.py
> ```
