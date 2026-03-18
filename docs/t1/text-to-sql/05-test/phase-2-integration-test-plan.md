# Text-to-SQL 로컬 통합 테스트 계획서 (TDD)

> **작성일**: 2026-03-17
> **담당**: t1
> **목적**: EKS 없이 로컬 Docker Compose 환경에서 E2E 전체 시나리오 완전 검증 — TDD 방식 적용
> **기준 문서**:
> - `docs/t1/text-to-sql/05-test/test-plan.md` — 원본 테스트 계획서 (Phase 2 참조)
> - `docs/t1/text-to-sql/05-test/phase-3-prerequisites-report.md` — Phase 3 미해결 이슈 목록
> - `services/vanna-api/docker-compose.test.yml` — 기존 Phase 2 구성 (확장 대상)

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | text-to-sql 로컬 E2E 검증 |
| **목표 환경** | Docker Compose (vanna-api + ChromaDB + Redash + Athena 직접 연결) |
| **테스트 범위** | 케이스 A/B + EX-1~EX-10 (Phase 3 시나리오 그대로) |
| **전제 조건** | Phase 3 미해결 이슈(BUG-4 등) 수정 완료 |
| **EKS 의존성** | 없음 — 로컬에서 이미지 빌드 → 컨테이너 실행 → curl 테스트 |

### 4-Perspective Value

| 관점 | 내용 |
|------|------|
| **Problem** | EKS 배포 사이클(빌드→ECR 푸시→롤아웃)이 너무 길어 코드 수정 후 즉각 검증 불가 |
| **Solution** | 기존 docker-compose.test.yml에 Redash 스택 추가, Athena 실제 연결로 EKS와 동등한 환경 구성 |
| **Function / UX Effect** | 코드 수정 → `docker compose up --build` 한 명령으로 즉시 재테스트 가능 |
| **Core Value** | EKS 없이도 전체 파이프라인(Step 1~11)을 완전 검증하여 배포 전 품질 보장 |

---

## 1. 테스트 전략

### 1.1 핵심 원칙

#### 환경 원칙

- **EKS 없음**: 모든 의존성(vanna-api, ChromaDB, Redash)을 로컬 Docker Compose로 구동
- **실제 Athena 연결**: Redash가 로컬에서 실제 AWS Athena에 직접 쿼리 (mock 아님)
- **Phase 3 시나리오 동일 적용**: 케이스 A/B + EX-1~EX-10을 `curl.exe`로 직접 호출
- **핫 리로드**: `src/` 볼륨 마운트로 코드 수정 시 컨테이너 재빌드 불필요

#### TDD 원칙 (Red → Green → Refactor)

- **Red**: 수정 전 코드로 테스트를 먼저 실행하여 실패 상태(현재 버그)를 확인한다
- **Green**: BUG-4·RAG 패치 적용 후 동일 테스트를 재실행하여 Pass(기대값 충족)를 확인한다
- **Refactor**: 전체 Pass 후 로그 품질·응답 구조를 검토하여 개선 여지를 파악한다
- **단언 기반 검증**: 모든 케이스의 Pass 기준은 `assert response["field"] == expected` 형태의 단언문으로 명시한다

### 1.2 기존 Phase 2 대비 달라지는 점

| 구분 | 기존 Phase 2 (docker-compose.test.yml) | 로컬 E2E (이번 계획) |
|------|----------------------------------------|----------------------|
| **Redash** | 비활성화 (`REDASH_ENABLED=false`) | 활성화 (Redash 컨테이너 포함) |
| **Athena** | moto mock 사용 | 실제 AWS Athena 직접 연결 |
| **AWS 자격증명** | 더미값 (`AWS_ACCESS_KEY_ID=test`) | 실제 AWS 자격증명 |
| **테스트 방법** | pytest 단위/통합 테스트 | curl 시나리오 테스트 (E2E) |
| **검증 목표** | 코드 인터페이스 및 로직 검증 | 전체 파이프라인 E2E 동작 검증 |

### 1.3 실행 흐름 (TDD 사이클)

```
[Red Phase — 실패 확인]
  사전 작업: BUG-4·RAG 미수정 상태로 케이스 A 먼저 실행 → KeyError 발생 확인
    ↓

[환경 구성]
  docker-compose.local-e2e.yml 작성
  (vanna-api + ChromaDB + Redash + Postgres + Redis)
    ↓

[환경 기동]
  docker compose -f docker-compose.local-e2e.yml up --build -d
    ↓

[초기 설정]
  ChromaDB 시딩 + Redash 초기화 + Athena 데이터소스 등록
    ↓

[Green Phase — 패치 적용 후 통과]
  코드 수정 (BUG-4, RAG-1, RAG-2) 적용 → vanna-api 재빌드
  케이스 A → 케이스 B → EX-1 ~ EX-10 순차 실행
  각 케이스별 assert 단언 항목 Pass 확인
    ↓

[Refactor Phase — 품질 검토]
  로그 품질·응답 구조·SQL 생성 정확도 검토
  결과 기록: local-e2e-test-results.md 작성
```

---

## 2. 사전 코드 수정 항목 (테스트 전 완료 필수)

Phase 3 진행 중 발견된 미해결 이슈 중 테스트에 직접 영향을 주는 항목을 먼저 수정한다.

### 2.1 [BUG-4] Redash 캐시 응답 처리 오류 ← **최우선 수정**

| 항목 | 내용 |
|------|------|
| **파일** | `services/vanna-api/src/clients/redash_client.py` |
| **증상** | `ERROR: Redash 실행 응답 파싱 실패: 'job'` → HTTP 500 |
| **원인** | 동일 SQL 재실행 시 Redash가 `{"query_result": {...}}` 캐시 응답을 즉시 반환, `execute_query()`가 `data["job"]["id"]`만 처리하므로 `KeyError: 'job'` 발생 |
| **수정 방법** | `execute_query()` POST body에 `"max_age": 0` 추가 → Redash가 항상 신규 job 생성 |

```python
# services/vanna-api/src/clients/redash_client.py
# execute_query() 내 POST body 수정
payload = {
    "parameters": {},
    "max_age": 0,  # 캐시 무효화: 항상 신규 job 생성
}
```

### 2.2 [RAG-1] ChromaDB 시딩 예시 SQL LIMIT 값 통일

| 항목 | 내용 |
|------|------|
| **파일** | `services/vanna-api/scripts/seed_chromadb.py` |
| **증상** | Redash 실행 결과가 예시 SQL에 따라 LIMIT 100 또는 LIMIT 50으로 제한됨 |
| **원인** | QA 예제 SQL의 LIMIT 값이 제각각 (100, 50, 1000, 1 등) → LLM이 가장 유사한 예시의 LIMIT을 그대로 복사 |
| **수정 방법** | 모든 QA 예제 SQL에서 LIMIT 제거 (또는 1000으로 통일) → SQLValidator의 `DEFAULT_LIMIT=1000` 자동 적용에 위임 |

### 2.3 [RAG-2] ChromaDB 시딩 예시 SQL 날짜 하드코딩 정리

| 항목 | 내용 |
|------|------|
| **파일** | `services/vanna-api/scripts/seed_chromadb.py` |
| **현황** | `sql_generator.py`에 날짜 컨텍스트 주입으로 임시 해결 중 |
| **수정 방법** | 예시 SQL의 날짜를 `current_date - interval '1' day` 형식의 상대 날짜 표현으로 변경 |
| **우선순위** | 낮음 — BUG-4 수정 후 테스트 진행하면서 병행 수정 가능 |

---

## 3. 로컬 환경 구성

### 3.1 docker-compose.local-e2e.yml 구성 설계

기존 `docker-compose.test.yml`을 기반으로 Redash 스택을 추가한 새 파일을 생성한다.

```
services:
  chromadb          — 벡터 DB (기존과 동일)
  vanna-api         — API 서버 (REDASH_ENABLED=true, 실제 AWS 자격증명)
  redash-server     — Redash 웹서버 (포트 5000)
  redash-worker     — Redash 쿼리 실행 워커
  redash-scheduler  — Redash 스케줄러
  postgres          — Redash 메타데이터 DB
  redis             — Redash 작업 큐
```

#### 주요 서비스 구성 포인트

**vanna-api 환경변수 변경 사항**:

| 변수 | 기존 Phase 2 | 로컬 E2E |
|------|-------------|----------|
| `REDASH_ENABLED` | `false` | `true` |
| `REDASH_URL` | (없음) | `http://redash-server:5000` |
| `REDASH_API_KEY` | (없음) | Redash 초기화 후 발급 |
| `REDASH_DATASOURCE_ID` | (없음) | `1` (Athena 데이터소스) |
| `AWS_ACCESS_KEY_ID` | `test` (더미) | 실제 AWS 자격증명 |
| `AWS_SECRET_ACCESS_KEY` | `test` (더미) | 실제 AWS 자격증명 |
| `S3_STAGING_DIR` | `s3://test-bucket/` | 실제 Athena 결과 버킷 |

**Redash Athena 연결 설정**:
- Redash 내장 Amazon Athena 데이터소스 사용 (v8+에서 기본 지원)
- AWS 자격증명: 컨테이너 환경변수로 주입 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- S3 결과 버킷: `s3://capa-dev-athena-results/` (기존 EKS 설정과 동일)
- 데이터베이스: `capa_db` / 리전: `ap-northeast-2`

### 3.2 환경 변수 파일 (.env.local-e2e)

```bash
# AWS 실제 자격증명
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=<실제값>
AWS_SECRET_ACCESS_KEY=<실제값>

# Athena 설정
ATHENA_DATABASE=capa_db
ATHENA_WORKGROUP=primary
S3_STAGING_DIR=s3://capa-dev-athena-results/

# Anthropic
ANTHROPIC_API_KEY=<실제값>

# vanna-api 인증 (개발 환경 스킵 가능)
INTERNAL_API_TOKEN=test-token

# Redash (초기화 후 업데이트)
REDASH_API_KEY=<Redash 초기화 후 발급>
REDASH_DATASOURCE_ID=1
```

> **보안**: `.env.local-e2e`는 `.gitignore`에 포함 (민감 정보 커밋 금지)

---

## 4. 선행 조건 체크리스트

### 4.1 코드 수정 완료 확인

- [ ] BUG-4 수정: `redash_client.py`에 `max_age: 0` 추가
- [ ] RAG-1 수정: `seed_chromadb.py` QA 예제 LIMIT 제거/통일
- [ ] RAG-2 수정: `seed_chromadb.py` 날짜 표현 상대값으로 변경 (선택)

### 4.2 환경 파일 준비

- [ ] `.env.local-e2e` 파일 작성 (AWS 자격증명, Anthropic API Key)
- [ ] `docker-compose.local-e2e.yml` 파일 작성

### 4.3 Docker 환경

```powershell
# Docker 동작 확인
docker --version        # Docker 20.10+
docker compose version  # Compose v2+

# 포트 충돌 확인 (사용 중이면 기존 프로세스 종료)
# 8000: vanna-api, 8001: chromadb, 5000: redash
```

### 4.4 AWS 접근 확인

```powershell
# Athena 접근 가능 여부 사전 확인
aws athena list-work-groups --region ap-northeast-2
aws s3 ls s3://capa-dev-athena-results/
```

---

## 5. 실행 절차

### Step 1: 컨테이너 기동

```powershell
cd services/vanna-api

# 전체 스택 기동 (백그라운드)
docker compose -f docker-compose.local-e2e.yml --env-file .env.local-e2e up --build -d

# 기동 상태 확인
docker compose -f docker-compose.local-e2e.yml ps
```

기동 예상 시간: 약 3~5분 (이미지 빌드 포함)

### Step 2: Redash 초기화

Redash는 최초 실행 시 DB 마이그레이션이 필요하다.

```powershell
# Redash DB 초기화 (최초 1회만)
docker compose -f docker-compose.local-e2e.yml exec redash-server python manage.py database create_tables

# Redash 관리자 계정 생성 (최초 1회만)
docker compose -f docker-compose.local-e2e.yml exec redash-server python manage.py users create_root \
  --email admin@capa.local \
  --password admin123 \
  --name Admin
```

> 이후 브라우저에서 `http://localhost:5000`으로 접근하여 로그인 가능

### Step 3: Redash Athena 데이터소스 등록

Redash 웹 UI 또는 API로 Athena 데이터소스를 등록한다.

```powershell
# Redash API로 데이터소스 등록
curl.exe -X POST http://localhost:5000/api/data_sources `
  -H "Content-Type: application/json" `
  -u admin@capa.local:admin123 `
  -d '{
    "name": "AWS Athena (capa_db)",
    "type": "athena",
    "options": {
      "region": "ap-northeast-2",
      "s3_staging_dir": "s3://capa-dev-athena-results/",
      "schema": "capa_db",
      "aws_access_key": "<AWS_ACCESS_KEY_ID>",
      "aws_secret_key": "<AWS_SECRET_ACCESS_KEY>"
    }
  }'
```

**응답에서 `id` 값 확인 후 `.env.local-e2e`의 `REDASH_DATASOURCE_ID`에 반영.**

### Step 4: Redash API Key 발급 및 반영

```powershell
# API Key 조회
curl.exe http://localhost:5000/api/users/me `
  -u admin@capa.local:admin123 | python -m json.tool
```

발급된 `api_key`를 `.env.local-e2e`의 `REDASH_API_KEY`에 반영한 뒤 vanna-api 재시작:

```powershell
docker compose -f docker-compose.local-e2e.yml --env-file .env.local-e2e `
  restart vanna-api
```

### Step 5: ChromaDB 시딩

```powershell
docker compose -f docker-compose.local-e2e.yml exec vanna-api `
  python scripts/seed_chromadb.py
```

예상 출력:
```
✓ ChromaDB connected
✓ DDL #1: ad_combined_log 추가됨
✓ DDL #2: ad_combined_log_summary 추가됨
✓ Q&A 예제 10개 추가됨
✓ 문서 4개 추가됨
✓ ChromaDB 시딩 완료!
```

### Step 6: 스모크 테스트

```powershell
# Health Check
curl.exe http://localhost:8000/health

# 기대 응답:
# {
#   "status": "ok",
#   "dependencies": {
#     "chromadb": "connected",
#     "athena": "connected",
#     "redash": "connected",
#     "llm": "ok"
#   }
# }
```

3가지 모두 `connected` 확인 후 시나리오 테스트로 진행.

---

## 6. E2E 시나리오 테스트 (케이스 A/B + EX-1~EX-10)

> **공통 변수**:
> ```powershell
> $API_BASE = "http://localhost:8000"
> $TOKEN = "test-token"
> ```

### 6.1 케이스 A: CTR 질문

**TC-A-01** | 실제 데이터 날짜로 캠페인별 CTR 조회

#### Given
- 로컬 E2E 환경 기동 완료 (vanna-api + ChromaDB + Redash + Athena)
- ChromaDB 시딩 완료 (DDL, 문서, QA 예제)
- Athena `capa_db` 에 `2026-02-01` 파티션 데이터 존재
- BUG-4 패치 적용 완료 (`max_age: 0`)

#### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -H "X-Internal-Token: $TOKEN" `
  -d '{"question": "2026-02-01 캠페인별 CTR 알려줘"}'
```

#### Then (assert 단언)

| TC | Step | assert 단언 | 판정 |
|----|------|------------|------|
| A-01-1 | Step 1 | `assert response["intent"] == "DATA_QUERY"` | ☐ |
| A-01-2 | Step 2 | `assert "CTR" in response["refined_question"]` | ☐ |
| A-01-3 | Step 3 | `assert len(response["keywords"]) >= 2` | ☐ |
| A-01-4 | Step 4 | `assert response["rag_results"]["ddl_count"] >= 1` | ☐ |
| A-01-5 | Step 5 | `assert "year='2026'" in response["generated_sql"]` | ☐ |
| A-01-5 | Step 5 | `assert "ad_combined_log" in response["generated_sql"]` | ☐ |
| A-01-6 | Step 6 | `assert response["sql_validated"] == True` | ☐ |
| A-01-7 | Step 7~8 | `assert response["redash_query_id"] is not None`  *(BUG-4 검증)* | ☐ |
| A-01-8 | Step 9 | `assert response["row_count"] >= 1` | ☐ |
| A-01-9 | Step 10 | `assert len(response["analysis"]) > 0` | ☐ |
| A-01-10 | Step 10.5 | `assert response["chart_image_base64"] is not None`  *(CHART-1 조건부)* | ☐ |
| A-01-11 | Step 11 | `assert response["history_id"] is not None` | ☐ |
| A-01-12 | 전체 | `assert http_status == 200 and response["error"] is None` | ☐ |

**TC-A-01 성공 기준**: 13개 assert 중 11개 이상 Pass (CHART-1은 조건부 허용)

---

### 6.2 케이스 B: ROAS 질문

**TC-B-01** | 최근 7일간 디바이스별 ROAS 순위 조회

#### Given
- TC-A-01 Pass 완료 (환경 정상 기동 확인)
- Athena `capa_db`에 최근 7일 이내 파티션 데이터 존재 (2026-02-01 이후)
- `ad_combined_log_summary` 테이블에 `cost`, `conversion_value`, `device_type` 컬럼 존재

#### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -H "X-Internal-Token: $TOKEN" `
  -d '{"question": "최근 7일간 디바이스별 ROAS 순위 알려줘"}'
```

#### Then (assert 단언)

| TC | assert 단언 | 판정 |
|----|------------|------|
| B-01-1 | `assert response["intent"] == "DATA_QUERY"` | ☐ |
| B-01-2 | `assert "ad_combined_log_summary" in response["generated_sql"]` | ☐ |
| B-01-3 | `assert "SUM(conversion_value)" in response["generated_sql"] or "conversion_value" in response["generated_sql"]` | ☐ |
| B-01-4 | `assert "device_type" in response["generated_sql"]` | ☐ |
| B-01-5 | `assert "GROUP BY" in response["generated_sql"]` | ☐ |
| B-01-6 | `assert response["row_count"] >= 1` | ☐ |
| B-01-7 | `assert len(response["analysis"]) > 0  # 디바이스별 인사이트 포함` | ☐ |
| B-01-8 | `assert http_status == 200 and response["error"] is None` | ☐ |

**TC-B-01 성공 기준**: 8개 assert 중 7개 이상 Pass

---

### 6.3 예외 케이스 EX-1 ~ EX-10

> **공통 Given**: 로컬 E2E 환경 기동 완료, TC-A-01 Pass 확인 후 진행

---

#### TC-EX-01: 도메인 범위 외 질문

##### Given
- 광고 데이터와 무관한 일반 질문 입력

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "파이썬 배우는 방법은?"}'
```

##### Then (assert 단언)
```
assert response["intent"] == "OUT_OF_DOMAIN"
assert http_status == 200
assert response.get("generated_sql") is None
assert response["status"] == "rejected"  # 또는 error 필드 존재
```

---

#### TC-EX-02: 의도 불명확 질문

##### Given
- 날짜·지표가 불특정한 모호한 질문 입력

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "지난 주 데이터 좀"}'
```

##### Then (assert 단언)
```
# 두 가지 경우 중 하나면 Pass
assert (
    response.get("refined_question") is not None  # Step 2에서 정제 시도
    or response["intent"] == "OUT_OF_DOMAIN"       # Step 1에서 분류 거부
)
```

---

#### TC-EX-03: SQL 생성 타임아웃 시뮬레이션

##### Given
- `LLM_TIMEOUT_SECONDS=0.001` 환경변수 오버라이드 후 vanna-api 재시작
- 또는 Anthropic API 네트워크 차단으로 시뮬레이션

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "어제 캠페인별 CTR"}'
```

##### Then (assert 단언)
```
assert response.get("error_code") == "SQL_GENERATION_FAILED"  # 또는 TIMEOUT
assert response.get("message") is not None  # 사용자 친화적 오류 메시지
assert http_status in [200, 504]  # 서비스에 따라 허용
```

---

#### TC-EX-04: Redash 쿼리 타임아웃

##### Given
- `REDASH_QUERY_TIMEOUT_SECONDS=1` 설정 후 vanna-api 재시작
- 복잡한 JOIN 쿼리가 생성될 질문 사용

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "최근 30일간 캠페인별 디바이스별 시간대별 CTR ROAS 전환율 알려줘"}'
```

##### Then (assert 단언)
```
assert response.get("error_code") == "QUERY_TIMEOUT"
assert response.get("message") is not None  # 쿼리 단순화 안내 포함
```

---

#### TC-EX-05: SQL 인젝션 시도

##### Given
- DDL 조작 구문이 포함된 악의적 질문 입력

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "DROP TABLE ad_combined_log; SELECT 1"}'
```

##### Then (assert 단언)
```
# 두 가지 경우 중 하나면 Pass
assert (
    response.get("sql_validated") == False         # SQL 검증 단계에서 차단
    or response["intent"] == "OUT_OF_DOMAIN"        # 의도 분류 단계에서 차단
)
assert response.get("error") is not None or response.get("status") == "rejected"
```

---

#### TC-EX-06: 허용되지 않은 테이블 참조

##### Given
- 허용 테이블(`ad_combined_log`, `ad_combined_log_summary`) 외 테이블 요청

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "users 테이블에서 이메일 목록 줘"}'
```

##### Then (assert 단언)
```
assert response.get("sql_validated") == False or response["intent"] == "OUT_OF_DOMAIN"
assert response.get("message") is not None  # 허용 테이블 안내 포함
```

---

#### TC-EX-07: 빈 질문

##### Given
- 빈 문자열 question 전송

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": ""}'
```

##### Then (assert 단언)
```
assert http_status in [400, 422]  # FastAPI 유효성 검사 거부
```

---

#### TC-EX-08: 데이터 존재 범위 외 날짜 요청

##### Given
- Athena에 데이터 없는 날짜 (DATA_START_DATE: 2026-02-01 이전) 질문

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "2020년 1월 데이터 줘"}'
```

##### Then (assert 단언)
```
# 두 가지 경우 중 하나면 Pass
assert (
    response.get("row_count") == 0             # SQL 생성 성공 + 빈 결과 처리
    or response.get("status") == "rejected"    # 사전 날짜 범위 차단
)
assert response.get("message") is not None
```

---

#### TC-EX-09: 특수문자 포함 질문 (XSS 방어)

##### Given
- HTML/스크립트 태그가 포함된 질문 입력

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "<script>alert(1)</script> CTR 알려줘"}'
```

##### Then (assert 단언)
```
# 스크립트 태그 미실행 확인 (이스케이프 또는 도메인 거부)
assert "<script>" not in response.get("analysis", "")
assert "<script>" not in response.get("message", "")
assert (
    response["intent"] == "OUT_OF_DOMAIN"      # 거부
    or response.get("sql_validated") is not None  # 정상 처리 (이스케이프)
)
```

---

#### TC-EX-10: 데이터 없는 정상 날짜 쿼리 (빈 결과 처리)

##### Given
- 유효한 날짜이나 Athena 파티션 데이터 없음 (2026-03-01 이후 미존재)

##### When
```powershell
curl.exe -X POST $API_BASE/query `
  -H "Content-Type: application/json; charset=utf-8" `
  -d '{"question": "2026-03-01 캠페인별 CTR 알려줘"}'
```

##### Then (assert 단언)
```
assert http_status == 200
assert response["intent"] == "DATA_QUERY"
assert response.get("generated_sql") is not None  # SQL 생성 성공
assert response.get("row_count") == 0              # 빈 결과
assert response.get("message") is not None         # fallback 메시지 (LLM 스킵)
assert response.get("error") is None               # 오류 없이 정상 완료
```

---

## 7. 로그 모니터링

### 7.1 실시간 로그 확인

```powershell
# vanna-api 로그 (Step별 JSON 로그)
docker compose -f docker-compose.local-e2e.yml logs -f vanna-api

# Redash worker 로그 (쿼리 실행 상태)
docker compose -f docker-compose.local-e2e.yml logs -f redash-worker
```

### 7.2 Step별 로그 필터링

```powershell
# 에러만 필터
docker compose -f docker-compose.local-e2e.yml logs vanna-api `
  | Select-String "ERROR|WARNING"

# Step 5 SQL 생성 로그만
docker compose -f docker-compose.local-e2e.yml logs vanna-api `
  | Select-String "step.*5|sql.*gen"
```

---

## 8. 성공 기준 및 결과 기록

### 8.1 전체 성공 기준 (TDD Green Phase)

| 구분 | TC ID | assert 개수 | Green 기준 |
|------|-------|------------|-----------|
| **케이스 A** | TC-A-01 | 13개 | 11/13 이상 Pass |
| **케이스 B** | TC-B-01 | 8개 | 7/8 이상 Pass |
| **예외 EX-01~10** | TC-EX-01~10 | 케이스당 2~6개 | 8/10 케이스 Pass |
| **BUG-4 검증** | TC-A-01-7 | `redash_query_id is not None` | 0건 KeyError 발생 |
| **CHART-1 검증** | TC-A-01-10 | `chart_image_base64 is not None` | 조건부 (실패해도 진행) |
| **피드백 RAG 훈련** | TC-FB-01 | 3개 | trained=true + 학습 건수 +1 |

**Refactor 진입 조건**: TC-A-01 + TC-B-01 + TC-EX 8개 이상 Green 달성 시

---

### 8.3 TC-FB-01: 긍정 피드백 → RAG 자동 훈련 검증

**목적**: 사용자가 👍 피드백 시 해당 질문-SQL 쌍이 ChromaDB에 자동 학습되는지 확인

**사전 조건**: 성공한 쿼리(`history_id` 보유)가 1건 이상 존재

**테스트 절차**:

```bash
# Step 1: 현재 RAG 학습 데이터 건수 확인 (before)
curl http://localhost:8000/training-data | grep count

# Step 2: 쿼리 실행 → history_id 획득
curl -X POST http://localhost:8000/query \
  -H "X-Internal-Token: test-token" \
  -d '{"question": "2월 5일 캠페인별 CTR 알려줘"}'
# → 응답에서 history_id 확인 (또는 /data/query_history.jsonl 직접 조회)

# Step 3: 긍정 피드백 전송
curl -X POST http://localhost:8000/feedback \
  -H "X-Internal-Token: test-token" \
  -d '{"history_id": "<step2에서 획득>", "feedback": "positive", "slack_user_id": "test-user"}'

# Step 4: RAG 학습 건수 재확인 (after)
curl http://localhost:8000/training-data | grep count
```

**assert 단언**:

| TC | assert 단언 | 기대값 | Pass 기준 |
|----|------------|--------|----------|
| FB-01-1 | `/feedback` 응답 HTTP 상태 | 200 | 200 |
| FB-01-2 | 응답 `trained` 필드 | `true` | `true` |
| FB-01-3 | `/training-data` count | before + 1 | before보다 1 증가 |

### 8.2 결과 기록 파일

테스트 완료 후 아래 파일에 결과 기록:

- **결과 파일**: `docs/t1/text-to-sql/05-test/local-e2e-test-results.md`
- **기록 항목**:
  - 각 케이스별 curl 명령 및 실제 응답 JSON
  - Step별 통과/실패 여부
  - 발견된 신규 이슈 및 수정 내용
  - 최종 통과율 및 권장사항

---

## 9. 환경 종료

```powershell
# 전체 컨테이너 중지 (데이터 유지)
docker compose -f docker-compose.local-e2e.yml stop

# 전체 컨테이너 + 볼륨 삭제 (완전 초기화)
docker compose -f docker-compose.local-e2e.yml down -v
```

---

## 10. 작업 순서 요약

| 순서 | 작업 | 예상 시간 | 담당 |
|------|------|----------|------|
| 1 | BUG-4 코드 수정 (`redash_client.py`) | 30분 | t1 |
| 2 | RAG-1 시딩 LIMIT 통일 (`seed_chromadb.py`) | 30분 | t1 |
| 3 | `docker-compose.local-e2e.yml` 작성 | 1시간 | t1 |
| 4 | Redash 초기화 + Athena 데이터소스 등록 | 30분 | t1 |
| 5 | ChromaDB 시딩 + 스모크 테스트 | 15분 | t1 |
| 6 | 케이스 A/B 실행 및 결과 기록 | 1~2시간 | t1 |
| 7 | EX-1~EX-10 실행 및 결과 기록 | 2~3시간 | t1 |
| 8 | `local-e2e-test-results.md` 작성 | 1시간 | t1 |

---

**작성자**: t1
**작성일**: 2026-03-17
**상태**: 계획 완료 — 작업 순서 1번(BUG-4 수정)부터 시작

> 실행 결과는 `phase-2-integration-test-result.md` 참조
