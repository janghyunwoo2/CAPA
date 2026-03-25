# Plan: SQL 정확도 튜닝 (과적합 없는 정답률 향상)

**Feature**: sql-accuracy-tuning
**작성일**: 2026-03-24
**담당자**: t1 (Text-to-SQL)
**예상 기간**: 1주 (6일)
**우선순위**: ⭐⭐⭐ (평가 체계 구축 후 정확도 개선 필수)

---

## Executive Summary

| 항목 | 설명 |
|------|------|
| **Problem** | Spider 평가 체계(04-evaluation)를 구축했으나 테스트 케이스 60개가 전부 실패 중. 현재 프롬프트와 RAG 시딩이 일반화되지 않아 다양한 질문 유형에 대응 불가. |
| **Solution** | 프롬프트 강화(CoT 고도화 + 네거티브 규칙 + system/user 분리) + 패턴 기반 RAG 시딩 재설계(코드값 포함) + Self-Correction Loop(SQL 오류 시 최대 3회 재생성) + Config 튜닝으로 정답률 향상 |
| **Function & UX Effect** | run_evaluation.py 실행 시 EM/Exec 정답률이 측정 가능한 수준으로 상승. SQL 오류 시 자동 재시도로 실패율 감소 |
| **Core Value** | 프롬프트·시딩·Self-Correction 3축으로 과적합 없는 정답률 극대화. 사전조사 1순위 전략(+5~15%p) 포함 |

---

## 1. 목표

### Primary Goal (Exec 정답률 향상)
run_evaluation.py 기준 **Exec >= 60%** 달성 (현재 0% → 첫 측정 가능한 베이스라인 확보 후 점진적 개선).

### Secondary Goal (EM 정답률 향상)
**EM >= 40%** 달성 (SQL 표현 차이로 EM은 Exec보다 낮을 수밖에 없음).

### Stretch Goal
Exec >= 80%, EM >= 60% (프롬프트 + 시딩 + Self-Correction 모두 완료 시).

> **목표 설정 근거**: 현재 평가가 한 번도 성공하지 못한 상태(500 에러)이므로, 먼저 정상 동작하는 베이스라인을 확보하고 반복 개선하는 전략을 취한다. 사전조사에서 프롬프트+시딩으로 +10~20%p, Self-Correction Loop로 추가 +5~15%p 개선 가능하다고 분석됨.

---

## 2. 범위 (Scope)

### 포함 항목 ✅

| 항목 | 설명 |
|------|------|
| **프롬프트 강화** | `sql_generator.yaml` CoT 고도화, 네거티브 규칙 추가, 테이블 선택 기준 명시, system/user 프롬프트 분리 |
| **RAG 시딩 재설계** | `seed_chromadb.py` QA 패턴 기반 재구성, 컬럼 코드값 Documentation 추가, 패러프레이징 |
| **Self-Correction Loop** | SQL 실행 오류 시 에러 메시지를 LLM에 재주입 → 최대 3회 재생성 (사전조사 1순위 전략) |
| **Config 튜닝** | temperature=0 설정, n_results/top_k 최적화 |
| **테스트 케이스 상대 날짜 도입** | 60개 중 30개를 상대 날짜(어제/오늘/이번 달)로 교체, ground_truth_sql에 Jinja2 변수 사용 |
| **run_evaluation.py Jinja2 렌더링** | ground_truth_sql의 `{{ y_year }}` 등을 실행 시점 날짜로 렌더링하는 기능 추가 |
| **베이스라인 측정** | run_evaluation.py로 현재 정답률 최초 측정 |
| **반복 개선** | 측정 → 실패 패턴 분석 → 프롬프트/시딩 수정 → 재측정 사이클 |

### 제외 항목 ❌

| 항목 | 이유 |
|------|------|
| **Self-Consistency (다수결)** | SQL 후보 여러 개 생성은 파이프라인 변경 필요 |
| **Schema Linking 모듈** | 별도 모듈 신규 구현 필요 |
| **LLM 모델 변경** | claude-haiku-4-5 유지 (비용/속도 제약) |
| **Execution Feedback** | Athena 실행 후 재생성은 파이프라인 변경에 해당 |

---

## 3. 현재 상태 분석

### 3.1 파이프라인 구조

```
질문 입력
  → Step 1: IntentClassifier (의도 분류)
  → Step 2: QuestionRefiner (질문 정제)
  → Step 3: KeywordExtractor (키워드 추출)
  → Step 4: RAGRetriever (Phase 2: ChromaDB → Reranker → LLM 선별)
  → Step 5: SQLGenerator (Claude Haiku + CoT 프롬프트)          ← 프롬프트 수정
  → Step 6: SQLValidator (EXPLAIN + sqlglot)
  → Step 6.5: Self-Correction Loop (오류 시 에러 피드백 → 재생성, 최대 3회)  ← 신규 추가
  → Step 7~11: Redash 실행, 분석, 기록
```

### 3.2 현재 RAG 시딩 현황

| 종류 | 수량 | 비고 |
|------|------|------|
| DDL | 2개 | ad_combined_log, ad_combined_log_summary |
| Documentation | 15개+ | 지표 정의, 파티션 규칙, 코드값 등 |
| QA 예제 | 28개 | CTR/CVR/ROAS/시간대/지역/비용 등 |

### 3.3 현재 Config

| 설정 | 현재 값 | 문제점 |
|------|---------|--------|
| temperature | 미설정 (SDK 기본값) | 비결정론적 출력 → 불안정 |
| n_results_sql | Phase 2에서 max(기본값, 20) | 후보 풀 크기 미최적화 |
| Reranker top_k | 7 | 최적값 검증 필요 |
| CoT 프롬프트 | 4-Step 기본형 | 테이블 선택/컬럼 확인 규칙 부재 |

### 3.4 사전조사에서 도출한 핵심 실패 원인

| 원인 | 예시 | 해결 방향 |
|------|------|----------|
| Hallucination | 존재하지 않는 `campaign_name` 컬럼 사용 | 프롬프트에 "DDL에 없는 컬럼 사용 금지" 강화 |
| 잘못된 테이블 선택 | 집계 질문에 원본 로그 테이블 사용 | 테이블 선택 기준 Documentation 추가 |
| 날짜 함수 오용 | `DATE()`, `CAST()` 사용 | 네거티브 규칙 이미 있으나 강화 필요 |
| 패턴 미학습 | 새로운 표현에 대응 불가 | 패턴 기반 QA + 질문 패러프레이징 |

---

## 4. 개선 전략 (3단계)

### Phase A: Quick Win (Day 1~2) — 프롬프트 강화 + Config 튜닝

코드 변경 최소화, 프롬프트 파일과 설정값만 수정.

#### A-1. temperature=0 설정
- **위치**: `sql_generator.py`의 LLM 호출부
- **효과**: SQL 생성 결과 안정화, 재현성 확보

#### A-2. sql_generator.yaml CoT 고도화

현재 CoT (4-Step):
```
Step 1. 어떤 테이블/컬럼이 필요한가?
Step 2. 날짜/기간 표현을 파티션 조건으로 변환하면?
Step 3. 집계·필터·정렬 로직은?
Step 4. 위 분석을 바탕으로 SQL 작성
```

개선 CoT (6-Step):
```
Step 1. DDL에서 실제 존재하는 테이블과 컬럼을 확인한다.
        - 반드시 제공된 DDL에 있는 컬럼만 사용.
        - 없는 컬럼을 추측하거나 만들어내지 않는다.
Step 2. 질문 유형에 맞는 테이블을 선택한다.
        - 시간대별 분석 / hour 파티션 필요 → ad_combined_log
        - 일별 집계 / 전환(conversion) 데이터 필요 → ad_combined_log_summary
        - 두 테이블 모두 필요한 경우만 JOIN
Step 3. 날짜/기간 표현을 파티션 조건으로 변환한다.
        - 반드시 year='YYYY' AND month='MM' AND day='DD' 형식 사용
Step 4. 집계·필터·정렬 로직을 설계한다.
        - CTR = COUNT(CASE WHEN is_click = true) / COUNT(*)
        - CVR = COUNT(CASE WHEN is_conversion = true) / COUNT(*)
Step 5. 위 분석을 바탕으로 SQL을 작성한다.
Step 6. 최종 검증: 사용한 모든 컬럼이 DDL에 존재하는지 재확인한다.
```

#### A-3. 네거티브 규칙 (Negative Constraints) 추가

```yaml
negative_rules: |
  <constraints>
    ❌ 절대 금지 사항:
    1. DDL에 정의되지 않은 컬럼을 사용하지 마라 (예: campaign_name, ad_name 등은 존재하지 않음)
    2. DATE(), TO_DATE(), CAST(... AS DATE), BETWEEN, date_format(), DATE_TRUNC() 사용 금지
    3. 서브쿼리에서 불필요한 중첩 금지 — 단일 쿼리로 해결 가능하면 단일 쿼리 사용
    4. SELECT * 금지 — 필요한 컬럼만 명시적으로 선택
    5. 파티션 컬럼(year, month, day, hour)에 함수 적용 금지
    6. 존재하지 않는 테이블 참조 금지 — ad_combined_log, ad_combined_log_summary 두 개만 존재
  </constraints>
```

#### A-4. system/user 프롬프트 분리

현재 SQL 생성 규칙이 user 메시지에 섞여 있어 LLM의 instruction following 효율이 낮음 (사전조사 지적).

- **위치**: `sql_generator.py`의 `submit_prompt()` 호출부
- **변경 내용**: 고정 규칙(date_rules, constraints, CoT 형식)은 **system 메시지**로, 사용자 질문+RAG 컨텍스트는 **user 메시지**로 분리
- **효과**: LLM이 규칙을 더 엄격하게 따르고 토큰 효율 향상

#### A-5. 베이스라인 측정
- vanna-api 컨테이너 정상 기동 후 run_evaluation.py 실행
- 60개 테스트 케이스 최초 정답률 기록

### Phase A-3: 키워드 추출 품질 개선 (Day 2 포함) — RAG 검색 오염 방지

#### 문제 분석

Step 3 KeywordExtractor가 추출한 키워드는 `search_query = question + " " + keywords` 방식으로
RAG 검색 쿼리에 직접 결합됨. 잘못된 키워드가 추가되면 embedding 벡터 자체가 오염되어
실제 질문과 무관한 QA 예제가 검색되고 SQL 정확도에 직접 영향을 줌.

**Phase 2 Reranker도 동일한 오염된 query로 관련성 재평가** → 문제 전파.

#### A-3-1. KeywordExtractor 프롬프트 제약 강화

```
[수정 전] "광고 분석에 관련된 핵심 명사와 지표를 추출하세요"
[수정 후] "질문에 직접 언급된 단어/표현만 추출하세요 — 질문에 없는 관련 지표 추가 금지"
```

#### A-3-2. 허용 키워드 화이트리스트 필터링

추출된 키워드를 스키마 기반 허용 목록과 교차 검증 후, 목록에 없는 키워드 제거:

| 허용 범주 | 예시 |
|---------|------|
| 실제 컬럼명 | `campaign_id`, `device_type`, `is_click`, `conversion_value` 등 |
| 표준 지표명 | CTR, CVR, ROAS, CPA, CPC, 클릭률, 전환율, 노출수, 클릭수 |
| 도메인 객체 | 캠페인, 광고주, 플랫폼, 지역, 카테고리, 시간대 |
| 컬럼 범주값 | `web`, `mobile`, `purchase`, `display`, `강남구` 등 |
| 시간 표현 | 어제, 오늘, 이번달, 지난달, 지난주 |

**효과**: 없는 컬럼명(`campaign_name`, `channel` 등) 추출 → 자동 제거

#### A-3-3. 수정 파일

- `src/pipeline/keyword_extractor.py`: 프롬프트 제약 추가 + `_ALLOWED_KEYWORDS` 화이트리스트 + `_filter_keywords()` 함수

### Phase B: 시딩 재설계 (Day 3~4) — 패턴 기반 QA + Documentation 보강

#### B-1. QA 예제 패턴 기반 재구성

**원칙**: 특정 날짜/값이 아닌 **SQL 패턴 카테고리**로 시딩

| 패턴 카테고리 | QA 예제 수 | 핵심 패턴 |
|---------------|-----------|----------|
| 기본 집계 (COUNT/SUM) | 3개 | GROUP BY + 단일 지표 |
| CTR/CVR 계산 | 3개 | CASE WHEN + COUNT 비율 |
| 기간 비교 (CTE) | 3개 | WITH 절 + 두 기간 비교 |
| 시간대별 분석 | 2개 | hour 파티션 + GROUP BY hour |
| TOP N 순위 | 2개 | ORDER BY + LIMIT |
| 다중 조건 필터 | 2개 | WHERE 복합 조건 |
| 전환(Conversion) 분석 | 2개 | is_conversion + conversion_value |
| 비용 분석 (ROAS/CPA/CPC) | 2개 | cost 컬럼 집계 |
| 지역별 분석 | 2개 | delivery_region GROUP BY |
| 기기/플랫폼별 분석 | 2개 | device_type/platform GROUP BY |

**총 ~23개** (현재 28개에서 과적합성 높은 것 제거, 패턴 커버리지 중심 재배치)

#### B-2. 질문 패러프레이징

동일한 SQL 패턴에 대해 다양한 자연어 표현을 시딩:

```
패턴: 캠페인별 CTR 집계
  - "캠페인별 클릭률을 보여줘"
  - "각 캠페인의 CTR은?"
  - "캠페인별로 노출 대비 클릭 비율 알려줘"
```

→ 같은 SQL에 3가지 표현을 매핑하여 임베딩 다양성 확보 (과적합 아닌 일반화)

**패러프레이징 소스**: `00_사전조사/05-sample-queries.md`에 정의된 59개 자연어 샘플(일간 25개 + 주간 19개 + 월간 15개)을 1차 재료로 활용. 유사한 의도의 샘플을 묶어 같은 SQL 패턴에 매핑.

**스키마 불일치 필터링** (사용 불가 7개 제외 → 실사용 가능 약 52개):

| 제외 항목 | 이유 |
|----------|------|
| 일간 14번 "신규로 시작된 캠페인" | 캠페인 시작일 컬럼 없음 |
| 일간 22번, 주간 3·9번, 월간 7·14번 "광고채널별(검색, 디스플레이, SNS)" | 채널 구분 컬럼 없음 (ad_format과 다름) |

**주의 필요** (복잡하지만 사용 가능):

| 항목 | 이유 |
|------|------|
| 일간 11번 "전일 대비 변화율", 일간 19번 "클릭수 증가율" | 날짜 2개 비교 필요 → CTE 패턴으로 구현 가능하나 복잡도 높음, 패러프레이징 소스로만 활용 |

#### B-3. Documentation 보강

| 추가 항목 | 내용 |
|----------|------|
| **테이블 선택 가이드** | "시간대별 → ad_combined_log (hour 파티션 있음)", "일별 집계/전환 → ad_combined_log_summary" |
| **존재하지 않는 컬럼 목록** | "campaign_name, ad_name, advertiser_name 등은 없음. campaign_id, ad_id로만 식별" |
| **컬럼 허용 코드값 목록** | `platform`: web/app_ios/app_android/tablet_ios/tablet_android, `device_type`: mobile/tablet/desktop/others, `conversion_type`: purchase/signup/download/view_content/add_to_cart, `campaign_id`: campaign_01~campaign_05, `ad_format`: display/native/video/discount_coupon 등 (`05-sample-queries.md` 기반) |
| **지표 계산 공식 표준화** | CTR, CVR, ROAS, CPA, CPC의 정확한 SQL 표현식 |
| **Athena SQL 방언 규칙** | "LIMIT은 지원하지만 TOP N은 미지원", "문자열 비교 시 = 사용" 등 |

### Phase C: Self-Correction Loop 구현 (Day 5) — SQL 오류 자동 재시도

사전조사 1순위 전략. `sql_validator.py`가 이미 존재하므로, 검증 실패 시 에러를 LLM에 재주입하는 루프만 추가.

#### C-1. 구현 위치

- **파일**: `src/query_pipeline.py` (Step 5~6 사이 루프 추가)
- 또는 `src/pipeline/sql_generator.py` 내부에 재시도 로직 캡슐화

#### C-2. 동작 방식

```
SQL 생성 (Step 5)
  → SQLValidator 검증 (Step 6)
  → 오류 발생 시:
      에러 메시지 + 원래 질문 + 실패한 SQL → LLM 재주입
      "위 SQL에서 다음 오류가 발생했습니다: {error}. 수정해주세요."
  → 재생성 (최대 3회)
  → 3회 후에도 실패 시 원래 SQL 반환 (기존 동작 유지)
```

#### C-3. 제약 조건

- 재시도 횟수: 최대 3회 (과도한 지연 방지)
- 타임아웃: 기존 `LLM_TIMEOUT_SECONDS` 그대로 적용
- 실패 로그: 재시도 횟수와 최종 결과를 로그에 기록

### Phase D: 최적화 + 반복 개선 (Day 6) — 측정-분석-수정 사이클

#### D-1. Config 튜닝 실험

| 파라미터 | 실험 범위 | 측정 방법 |
|---------|----------|----------|
| n_results_sql | 10, 15, 20, 30 | 각 값으로 run_evaluation.py 실행, Exec 비교 |
| Reranker top_k | 5, 7, 10 | 동일 |
| LLM 선별 max_tokens | 256, 512 | 동일 |

#### D-2. 실패 패턴 분석 → 타겟 수정

1. run_evaluation.py 실행 → evaluation_report.json 분석
2. 실패 케이스를 카테고리별로 분류:
   - **Hallucination** (없는 컬럼/테이블) → 프롬프트 네거티브 규칙 보강
   - **잘못된 테이블 선택** → Documentation 테이블 가이드 보강
   - **날짜 조건 오류** → date_rules 예시 추가
   - **집계 로직 오류** → QA 패턴 예제 보강
   - **SQL 문법 오류** → Athena 방언 Documentation 보강
3. 수정 후 재측정 (최대 3회 반복)

#### D-3. 최종 결과 기록

- 최종 Exec/EM 수치 기록
- 개선 전후 비교표 작성
- 잔여 실패 케이스 원인 분석 (다음 단계 입력)

---

## 5. 수정 대상 파일

| 파일 | 수정 내용 | Phase |
|------|----------|-------|
| `prompts/sql_generator.yaml` | CoT 6-Step 고도화, 네거티브 규칙 추가 | A |
| `src/pipeline/sql_generator.py` | temperature=0 설정, system/user 프롬프트 분리 | A |
| `src/pipeline/keyword_extractor.py` | 프롬프트 제약 + `_filter_keywords()` 화이트리스트 필터 | A-3 |
| `scripts/seed_chromadb.py` | QA 패턴 재설계, 컬럼 코드값 Documentation 추가, 패러프레이징 | B |
| `src/query_pipeline.py` | Self-Correction Loop (Step 6.5) 추가 | C |
| `src/pipeline/rag_retriever.py` | n_results / top_k 조정 (실험 결과 기반) | D |

---

## 6. 작업 일정

| Day | 작업 | 산출물 | 측정 |
|-----|------|--------|------|
| **Day 1** | 베이스라인 측정 + temperature=0 + system/user 분리 | evaluation_report.json (베이스라인) | 최초 Exec/EM 수치 |
| **Day 2** | CoT 6-Step 고도화 + 네거티브 규칙 추가 | sql_generator.yaml 수정 | Quick Win 후 Exec/EM |
| **Day 3** | QA 패턴 재설계 + 패러프레이징 (05-sample-queries 활용) | seed_chromadb.py 수정 | 시딩 후 Exec/EM |
| **Day 4** | 컬럼 코드값 Documentation 추가 + Config 튜닝 실험 | Documentation 추가, 실험 기록 | 최적 Config 후 Exec/EM |
| **Day 5** | Self-Correction Loop 구현 | query_pipeline.py 수정 | Self-Correction 적용 후 Exec/EM |
| **Day 6** | 실패 패턴 분석 + 타겟 수정 + 최종 측정 | 최종 결과 기록 | 최종 Exec/EM |

---

## 7. 측정 방법

### 7.1 평가 도구
```bash
# vanna-api 컨테이너 기동 후
cd services/vanna-api
python evaluation/run_evaluation.py
```

### 7.2 평가 지표

| 지표 | 설명 | 목표 |
|------|------|------|
| **Exec Accuracy** | 생성 SQL과 정답 SQL의 실행 결과 일치율 | >= 60% (Stretch: 75%) |
| **EM (Exact Match)** | 정규화된 SQL 문자열 일치율 | >= 40% (Stretch: 55%) |
| **카테고리별 Exec** | basic_ctr, conversion, cost 등 카테고리별 정답률 | 편차 분석 |

### 7.3 측정 사이클

```
수정 → run_evaluation.py 실행 → evaluation_report.json 분석
  → 실패 패턴 분류 → 타겟 수정 → 재측정
  (최대 Day 5까지 반복)
```

---

## 8. 리스크

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| vanna-api 컨테이너 기동 실패로 베이스라인 측정 불가 | 중 | 높음 | docker-compose 설정 점검, 로그 확인 |
| 프롬프트 변경이 기존 잘 되던 케이스를 깨뜨림 (regression) | 중 | 중 | 매 수정 후 전체 60개 재평가로 회귀 검증 |
| temperature=0으로도 LLM 출력이 불안정 | 낮 | 중 | 프롬프트 구조화 강화로 보완 |
| 패턴 기반 시딩으로도 일반화 부족 | 중 | 중 | 패러프레이징 수를 늘려 임베딩 커버리지 확대 |
| 60개 테스트 케이스 전체 평가 시간이 길어 반복 비효율 | 중 | 낮 | 카테고리별 부분 평가 → 전체 평가 순서로 진행 |
| Self-Correction Loop로 인한 응답 지연 (재시도 × LLM 호출) | 중 | 중 | 재시도 횟수 3회 상한, 타임아웃 내 처리 보장 |
| system/user 분리 후 프롬프트 포맷 오류 | 낮 | 중 | 변경 직후 단일 케이스로 수동 검증 후 전체 평가 진행 |

---

## 9. 성공 기준

| 기준 | 조건 |
|------|------|
| **최소 성공** | Exec >= 50% (30/60 케이스 통과) |
| **목표 성공** | Exec >= 60%, EM >= 40% |
| **초과 성공** | Exec >= 80%, EM >= 60% (Self-Correction 포함 시 달성 가능) |
| **과적합 검증** | 카테고리별 Exec 편차 <= 30%p (특정 카테고리만 높고 나머지 낮으면 과적합) |
