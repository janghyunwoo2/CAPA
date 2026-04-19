# [Plan] Prompt Engineering Enhancement (FR-PE)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | prompt-engineering-enhancement |
| **FR ID** | FR-PE |
| **작성일** | 2026-03-23 |
| **담당** | t1 |
| **참고 문서** | `docs/t1/text-to-sql/00_mvp_develop/00-기타/prompt-engineering.md` (현행 프롬프트 분석) |

### Value Delivered (4관점)

| 관점 | 내용 |
|------|------|
| **Problem** | SQLGenerator가 날짜 관련 질문에서 파티션 값을 잘못 생성하거나 예시 SQL을 그대로 복사하는 환각이 발생하며, conversation_history가 파라미터로 전달되지만 프롬프트에 주입되지 않아 멀티턴 SQL 일관성이 깨짐 |
| **Solution** | CoT(Chain-of-Thought) 단계를 SQLGenerator에 추가하고, 테이블 스키마와 날짜 파티션 규칙을 구조화된 형태로 주입하며, Few-shot 예시를 날짜 중심으로 5개로 확대하고, 프롬프트를 YAML 파일로 외부화 |
| **Function UX Effect** | 사용자가 "지난주", "이번달", "2월 실적" 같은 자연어 날짜 표현을 입력하면 파티션 조건이 정확히 생성된 SQL이 반환되며, 멀티턴 후속 질문에서도 이전 SQL과 일관된 쿼리가 나옴 |
| **Core Value** | 코드 재배포 없이 YAML 프롬프트 파일만 수정하면 즉시 반영되는 구조를 구현, SQL 정확도 향상으로 데이터 신뢰도 제고 |

---

## 1. 배경 및 목적

### 1.1 문제 정의 (현행 AS-IS)

#### 문제 1: conversation_history 미주입 버그 (Critical)

```python
# sql_generator.py:35 — history 파라미터를 받지만
def generate(self, question: str, rag_context=None, conversation_history=None) -> str:
    ...
    prompt = f"{date_context}{question}"  # ← history가 프롬프트에 포함되지 않음!
```

**증상**: 멀티턴 대화에서 Turn 2 질문("그 중에 비용이 적은 건?")이 Turn 1 SQL을 참조하지 못해 잘못된 SQL 생성

#### 문제 2: 날짜 환각 (High)

```
사용자: "지난주 월요일부터 금요일까지 실적"
현행 프롬프트: "지난주=2026-03-09~2026-03-15" (월요일이 09일인지 확인 안 됨)
문제: 날짜 범위 계산을 LLM이 추론 → 틀릴 수 있음
```

- 날짜 컨텍스트는 단순 텍스트 나열 → LLM이 파티션 형식(year/month/day)을 무시하고 DATE 함수로 SQL 작성하는 사례
- 예시 SQL의 날짜 값 복사 금지 경고가 있지만 구조적 강제 없음

#### 문제 3: CoT(Chain-of-Thought) 부재 (Medium)

- SQLGenerator가 질문을 받자마자 바로 SQL 생성 시도
- 복잡한 집계(CTR, ROAS), 조인, 서브쿼리 필요 시 추론 단계 없이 생성 → 오류 빈도 증가

#### 문제 4: Few-shot 예시 부족 (Medium)

| 단계 | 현행 예시 수 | 날짜 관련 예시 |
|------|------------|--------------|
| QuestionRefiner | 1개 | 없음 |
| SQLGenerator (Vanna ChromaDB) | 가변 (벡터 검색) | 일부 |

#### 문제 5: 프롬프트 하드코딩 (Low)

- `intent_classifier.py`, `question_refiner.py`, `ai_analyzer.py`에 프롬프트가 소스코드에 직접 삽입
- 프롬프트 수정 = 코드 수정 + Docker 이미지 재빌드 + EKS 재배포 (30분+)

### 1.2 목표 (TO-BE)

```
[목표] 사용자 자연어 날짜 표현 → 정확한 Athena 파티션 SQL 반환

[핵심 지표]
- 날짜 관련 쿼리 SQL 정확도: 현행 미측정 → Spider EM 기준 85% 이상
- conversation_history 주입: 0% → 100% (버그 수정)
- 프롬프트 수정 배포 시간: 30분+ → 0분 (YAML 핫 리로드)
```

---

## 2. 기능 요구사항

### 2.1 FR-PE 세부 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| FR-PE-01 | conversation_history를 SQLGenerator 프롬프트에 실제로 주입 (버그 수정) | Must |
| FR-PE-02 | SQLGenerator에 CoT 단계 추가: 테이블 선택 → 날짜 변환 → 집계 로직 → SQL 작성 | Must |
| FR-PE-03 | 날짜 파티션 규칙을 구조화된 XML 블록으로 분리하여 주입 | Must |
| FR-PE-04 | 프롬프트를 `prompts/` YAML 파일로 외부화, 런타임 로드 | Should |
| FR-PE-05 | AIAnalyzer 스키마 정보를 instructions 블록에 추가 (차트 타입 결정 정확도 향상) | Could |

### 2.2 제외 범위 (Out of Scope)

- ChromaDB Few-shot 시드 추가 (RAG 고도화 세션에서 별도 진행)
- QuestionRefiner Few-shot 예시 확대 (RAG 담당 범위)
- 다국어(영어, 일본어) 지원 확장 (별도 Phase)
- 사용자 피드백 루프 구축 (별도 Feature)
- Vanna 학습 데이터 자동 갱신
- 프롬프트 A/B 테스트 프레임워크

---

## 3. 아키텍처

### 3.1 핵심 설계: CoT + 구조화 날짜 컨텍스트

```
[현행 SQLGenerator 프롬프트 구조]
┌─────────────────────────────────────────────┐
│ [날짜 컨텍스트] 오늘=2026-03-23... (단순 텍스트)   │
│ {question}                                   │
└─────────────────────────────────────────────┘

[개선 후 SQLGenerator 프롬프트 구조]
┌─────────────────────────────────────────────┐
│ <schema>                                    │
│   테이블: ad_logs (impression/click/conv)   │
│   파티션: year STRING, month STRING (2자리) │
│   day STRING (2자리)                        │
│   주요 컬럼: campaign, ctr, cost, roas...   │
│ </schema>                                   │
│                                             │
│ <date_rules>                                │
│   오늘=2026-03-23 → year='2026',month='03' │
│   어제=2026-03-22 → year='2026',month='03' │
│   지난달=2026-02 → year='2026',month='02'  │
│   규칙: DATE 함수 절대 금지, 파티션 문자열만 │
│ </date_rules>                               │
│                                             │
│ <history>                                   │
│   Turn 1 SQL: SELECT ... (conversation)     │
│ </history>                                  │
│                                             │
│ <thinking>                                  │
│   Step 1: 어떤 테이블이 필요한가?           │
│   Step 2: 날짜 조건을 파티션으로 변환하면? │
│   Step 3: 집계/필터 로직은?                 │
│   Step 4: 최종 SQL 작성                     │
│ </thinking>                                 │
│                                             │
│ 질문: {question}                            │
└─────────────────────────────────────────────┘
```

### 3.2 프롬프트 외부화 구조

```
services/vanna-api/
├── prompts/                          ← 신규 (YAML 파일들)
│   ├── intent_classifier.yaml        ← IntentClassifier 프롬프트
│   ├── question_refiner.yaml         ← QuestionRefiner 프롬프트 + few-shot
│   ├── sql_generator.yaml            ← CoT 템플릿, 날짜 규칙, 스키마
│   └── ai_analyzer.yaml             ← AIAnalyzer instructions
└── src/
    └── prompt_loader.py              ← 신규: YAML 로드 + 캐시 (핫 리로드)
```

**YAML 구조 예시** (`prompts/sql_generator.yaml`):
```yaml
system: |
  당신은 AWS Athena SQL 전문가입니다.

schema: |
  <schema>
    테이블: ad_logs (S3 파티션 테이블)
    파티션 컬럼: year (STRING, 4자리), month (STRING, 2자리), day (STRING, 2자리)
    집계 컬럼: impressions, clicks, conversions, cost, revenue
    파생 지표: CTR=clicks/impressions, CVR=conversions/clicks, ROAS=revenue/cost
  </schema>

date_rules: |
  <date_rules>
    ⚠️ 반드시 파티션 문자열로 표현. DATE() 함수, BETWEEN, CAST 금지.
    오늘={today} → year='{year}', month='{month}', day='{day}'
    ...
  </date_rules>

cot_template: |
  <thinking>
    Step 1: 질문에서 필요한 테이블/컬럼 식별
    Step 2: 날짜/기간 표현을 파티션 조건으로 변환
    Step 3: 필터, 집계, 정렬 로직 결정
    Step 4: SQL 작성
  </thinking>

few_shot:
  - question: "지난달 캠페인별 CTR"
    sql: |
      SELECT campaign,
             SUM(clicks) * 1.0 / NULLIF(SUM(impressions), 0) AS ctr
      FROM ad_logs
      WHERE year='2026' AND month='02'
      GROUP BY campaign
      ORDER BY ctr DESC
```

### 3.3 날짜 처리 구조화 (핵심)

```
[현행] 단순 텍스트 경고
"[경고: 예시 SQL의 year/month/day 값을 절대 그대로 복사하지 말 것...]"
→ LLM이 경고를 무시할 수 있음

[개선] XML 블록 + 규칙 목록 + 예시 매핑
<date_rules>
  금지: DATE(), TO_DATE(), CAST(), BETWEEN, date_format()
  허용: year='YYYY', month='MM', day='DD' (문자열 등호만)

  변환 표:
  "오늘"      → WHERE year='{Y}' AND month='{M}' AND day='{D}'
  "어제"      → WHERE year='{Y}' AND month='{M}' AND day='{D-1}'
  "이번달"    → WHERE year='{Y}' AND month='{M}'
  "지난달"    → WHERE year='{Y}' AND month='{M-1}'
  "지난주"    → WHERE year='{Y}' AND month='{M}' AND day IN ('{D-7}','{D-6}',...,'{D-1}')
  "N월"       → WHERE year='{Y}' AND month='{NN}'
  "N월 N일"   → WHERE year='{Y}' AND month='{NN}' AND day='{DD}'
</date_rules>
```

---

## 4. 구현 파일 목록

| 파일 | 변경 종류 | 설명 |
|------|---------|------|
| `services/vanna-api/prompts/sql_generator.yaml` | **신규** | CoT 템플릿, 스키마, 날짜 규칙 |
| `services/vanna-api/prompts/intent_classifier.yaml` | **신규** | IntentClassifier 시스템 프롬프트 |
| `services/vanna-api/prompts/question_refiner.yaml` | **신규** | QuestionRefiner 시스템 프롬프트 (Few-shot은 RAG 담당) |
| `services/vanna-api/prompts/ai_analyzer.yaml` | **신규** | AIAnalyzer instructions + 스키마 정보 |
| `services/vanna-api/src/prompt_loader.py` | **신규** | YAML 로드 + Jinja2 렌더링 + 파일 변경 감지 캐시 |
| `services/vanna-api/src/pipeline/sql_generator.py` | 수정 | CoT 주입, conversation_history 주입 버그 수정, YAML 로드 |
| `services/vanna-api/src/pipeline/question_refiner.py` | 수정 | YAML 기반 프롬프트 로드 |
| `services/vanna-api/src/pipeline/intent_classifier.py` | 수정 | YAML 기반 프롬프트 로드 |
| `services/vanna-api/src/pipeline/ai_analyzer.py` | 수정 | YAML 기반 프롬프트 로드 |
| `services/vanna-api/requirements.txt` | 수정 | `jinja2`, `pyyaml` 의존성 추가 |

---

## 5. 성공 기준

| 항목 | 기준 |
|------|------|
| 날짜 파티션 쿼리 정확도 | 날짜 관련 10개 테스트 케이스 중 8개 이상 EM(Exact Match) |
| DATE 함수 사용 금지 | 생성 SQL에 `DATE()`, `CAST()`, `BETWEEN` 미사용 |
| 멀티턴 SQL 일관성 | Turn 2 SQL이 Turn 1 테이블/파티션 조건과 동일하게 생성 |
| CoT 포함 여부 | 생성 응답에 `<thinking>` 블록 포함 (Vanna 내부 추출) |
| 프롬프트 핫 리로드 | YAML 수정 후 서버 재시작 없이 다음 요청부터 반영 |

---

## 6. 구현 순서

```
1. [FR-PE-01] sql_generator.py — conversation_history 프롬프트 주입 버그 수정
   (가장 빠른 임팩트, 코드 3줄 수정)

2. [FR-PE-04] prompt_loader.py 신규 구현
   - YAML 파일 로드, Jinja2 날짜 변수 렌더링
   - 파일 mtime 감지 캐시 (핫 리로드)

3. [FR-PE-02, FR-PE-03] sql_generator.yaml 작성
   - 스키마 블록, 날짜 규칙 변환 표, CoT 템플릿
   - sql_generator.py에서 YAML 기반 프롬프트 로드

4. [FR-PE-04] question_refiner.yaml + intent_classifier.yaml 작성
   - 기존 프롬프트 YAML로 이관 (기능 변경 없음)
   - 각 파이프라인 Step에서 YAML 로드 적용

5. [FR-PE-05] ai_analyzer.yaml 작성
   - 스키마 정보 추가, instructions 블록 강화

6. 단위 테스트 및 결과 문서 업데이트
```

---

## 7. 리스크 및 대응

| 리스크 | 가능성 | 대응 |
|--------|--------|------|
| Vanna `generate_sql()` 내부가 CoT `<thinking>` 블록을 SQL로 오해 | 중 | SQL 후처리: `<thinking>` 블록 제거 정규식 추가 |
| YAML 파일 누락 시 서비스 장애 | 저 | PromptLoader: YAML 없으면 코드 내 기본값 fallback |
| Jinja2 렌더링 오류 | 저 | try-except + 원본 템플릿 반환 fallback |
```
