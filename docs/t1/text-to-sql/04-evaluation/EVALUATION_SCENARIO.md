# Spider EM/Exec 평가 시나리오 — CAPA 프로젝트 실제 연동

**작성일**: 2026-03-22
**범위**: Vanna API의 SQL 생성 정확도를 CAPA 실제 데이터로 검증하는 엔드-투-엔드 시나리오

---

## 목차

1. [현재 CAPA 아키텍처](#현재-capa-아키텍처)
2. [Spider 평가의 위치](#spider-평가의-위치)
3. [구체적인 평가 시나리오](#구체적인-평가-시나리오-전체-흐름)
4. [테스트 케이스 예시 → 실행 결과](#테스트-케이스-예시--실행-결과)
5. [평가 결과 해석](#평가-결과-해석)

---

## 현재 CAPA 아키텍처

### 데이터 파이프라인

```
[온라인 광고 로그]
    ↓
[AWS Kinesis Stream] (실시간 수집)
    ↓
[AWS S3] (파티션 저장)
    year=2026/month=03/day=22/
    ├── impression.parquet (광고 노출)
    ├── click.parquet (클릭)
    └── conversion.parquet (전환)
    ↓
[AWS Athena] (SQL 쿼리 엔진)
    ↓
[Redash] (BI 대시보드)
    ↓
[Vanna API] ← 사용자 자연어 질문
    ↓
[생성된 SQL]
    ↓
[Athena 실행]
    ↓
[결과] → Slack 봇, Redash 시각화
```

### 현재 데이터 상태 (2026-03-22)

**S3 파티션 구조**:
```
s3://capa-dev-raw-logs/
├── year=2026/
│   ├── month=01/ (2026-02-01부터 생성)
│   ├── month=02/ (✅ 완전)
│   ├── month=03/ (✅ 2026-03-01 ~ 현재)
│   └── ...
```

**Athena 테이블**:
```sql
CREATE EXTERNAL TABLE campaigns (
    campaign_id STRING,
    campaign_name STRING,
    advertiser_id STRING,
    year STRING,
    month STRING,
    day STRING,
    clicks BIGINT,
    impressions BIGINT,
    conversions BIGINT,
    cost DECIMAL(15,2),
    revenue DECIMAL(15,2),
    ctr DOUBLE,        -- clicks / impressions
    cvr DOUBLE,        -- conversions / clicks
    roas DOUBLE        -- revenue / cost
)
PARTITIONED BY (year STRING, month STRING, day STRING)
LOCATION 's3://capa-dev-raw-logs/'
```

**Redash 데이터 소스**:
- Athena 연동 완료
- 임시 쿼리 실행 가능
- 캐싱: 5분

---

## Spider 평가의 위치

### CAPA 품질 평가 3단계

```
┌─────────────────────────────────────────────────────────────┐
│ 1️⃣ Design 검증 (Gap Analysis)                               │
├─────────────────────────────────────────────────────────────┤
│ 대상: 설계 문서 vs 구현 코드                                  │
│ 방식: 설계서 섹션 ↔ Python 파일 매핑 (수동)                  │
│ 결과: 96% Match Rate ✅                                      │
│ 목적: 구현이 설계를 따랐는가?                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2️⃣ SQL 생성 정확도 (Spider EM/Exec) ← 본 평가               │
├─────────────────────────────────────────────────────────────┤
│ 대상: Vanna API 생성 SQL vs 정답 SQL                         │
│ 방식: 100개 테스트 케이스 자동 실행                          │
│ 결과: EM % / Exec % (목표: 85% / 90%)                       │
│ 목적: Vanna API가 정확한 SQL을 생성하는가?                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3️⃣ 사용자 만족도 (Phase 3 예정)                              │
├─────────────────────────────────────────────────────────────┤
│ 대상: 실제 사용자 질문 → Vanna 응답 → Slack 봇 출력         │
│ 방식: 실제 비즈니스 사용 로그 분석                           │
│ 결과: NPS, 오류율, 응답시간 등                              │
│ 목적: 사용자가 Vanna를 잘 사용하는가?                       │
└─────────────────────────────────────────────────────────────┘
```

### Spider 평가가 중요한 이유

```
설계 ✅ (96% Match)
  ↓
구현 ✅ (코드 완성)
  ↓
SQL 정확도 ❓ ← Spider 평가로 검증
  ↓
실제 사용 ❓
```

**Spider 결과에 따른 다음 단계**:
- EM >= 85%, Exec >= 90% → Phase 3 (프롬프트 최적화) 진행
- EM < 85% 또는 Exec < 90% → 프롬프트 개선 후 재평가
- 심각한 오류 발견 → 설계 문서 재검토

---

## 구체적인 평가 시나리오 (전체 흐름)

### 타임라인: 2026-03-22 (오늘)

---

### [09:00] Step 1: 평가 스크립트 시작

```bash
# 로컬에서 평가 시작
$ bash run_spider_evaluation.sh local

# 또는 Docker에서
$ docker-compose -f docker-compose.local-e2e.yml up spider-evaluator

[INFO] Spider EM/Exec 평가 시작
[INFO] 테스트 케이스 로드: test_cases.json (100개)
[INFO] Vanna API 연결: http://localhost:8000 ✅
[INFO] Redash 연결: http://redash-server:5000 ✅
[INFO] 평가 시작: 2026-03-22 09:00:00
```

---

### [09:00 ~ 09:30] Step 2: 배치 평가 (100개 테스트 케이스)

#### 테스트 케이스 #1 실행 예시

**입력**:
```json
{
  "id": "T001",
  "question": "지난주 CTR이 가장 높은 캠페인 5개",
  "ground_truth_sql": "SELECT campaign_name, AVG(ctr) as avg_ctr FROM campaigns WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21' GROUP BY campaign_name ORDER BY avg_ctr DESC LIMIT 5"
}
```

#### Step 2-1: 정답 SQL 실행 (Redash/Athena)

```bash
[09:00:01] [T001] 정답 SQL 실행 중...

SELECT campaign_name, AVG(ctr) as avg_ctr
FROM campaigns
WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21'
GROUP BY campaign_name
ORDER BY avg_ctr DESC
LIMIT 5
```

**정답 결과** (Athena 실행 시간: 0.23초):
```
┌───────────────────┬──────────┐
│  campaign_name    │ avg_ctr  │
├───────────────────┼──────────┤
│ Campaign_A        │  0.0850  │
│ Campaign_B        │  0.0720  │
│ Campaign_C        │  0.0685  │
│ Campaign_D        │  0.0620  │
│ Campaign_E        │  0.0580  │
└───────────────────┴──────────┘
Row Count: 5
Execution Time: 0.23s
```

#### Step 2-2: Vanna API로 SQL 생성

```bash
[09:00:02] [T001] Vanna로 SQL 생성 중...

입력 프롬프트:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[날짜 컨텍스트]
오늘=2026-03-22(year='2026',month='03',day='22'),
어제=2026-03-21(...),
이번달=2026-03(...),
지난달=2026-02(...)
파티션 형식: year/month/day는 STRING 2자리

[이전 대화 SQL] (없음 - 첫 턴)

지난주 CTR이 가장 높은 캠페인 5개
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Vanna 내부 처리:
1. ChromaDB에서 유사 SQL 템플릿 검색
   → "GROUP BY" 템플릿 (상위도 높음)
   → "PARTITION" 템플릿

2. Claude로 SQL 생성
   → Prompt: [시스템 지시] + [검색된 템플릿] + [사용자 질문]
```

**생성된 SQL** (Vanna 응답 시간: 1.2초):
```sql
SELECT campaign_name, AVG(ctr) as avg_ctr
FROM campaigns
WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21'
GROUP BY campaign_name
ORDER BY avg_ctr DESC
LIMIT 5
```

#### Step 2-3: 생성 SQL 실행 (Redash/Athena)

```bash
[09:00:03] [T001] 생성 SQL 실행 중...
```

**생성 결과** (Athena 실행 시간: 0.24초):
```
┌───────────────────┬──────────┐
│  campaign_name    │ avg_ctr  │
├───────────────────┼──────────┤
│ Campaign_A        │  0.0850  │
│ Campaign_B        │  0.0720  │
│ Campaign_C        │  0.0685  │
│ Campaign_D        │  0.0620  │
│ Campaign_E        │  0.0580  │
└───────────────────┴──────────┘
Row Count: 5
Execution Time: 0.24s
```

#### Step 2-4: EM/Exec 계산

```bash
[09:00:04] [T001] 평가 계산 중...

═══════════════════════════════════════

📊 T001 평가 결과

[EM] Exact Match (SQL 정확도)
─────────────────────────────────
정답 SQL:
  SELECT campaign_name, AVG(ctr) as avg_ctr FROM campaigns
  WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21'
  GROUP BY campaign_name ORDER BY avg_ctr DESC LIMIT 5

생성 SQL:
  SELECT campaign_name, AVG(ctr) as avg_ctr FROM campaigns
  WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21'
  GROUP BY campaign_name ORDER BY avg_ctr DESC LIMIT 5

정규화:
  SELECT CAMPAIGN_NAME, AVG(CTR) AS AVG_CTR FROM CAMPAIGNS WHERE
  YEAR = '2026' AND MONTH = '03' AND DAY >= '15' AND DAY <= '21'
  GROUP BY CAMPAIGN_NAME ORDER BY AVG_CTR DESC LIMIT 5

  =

  SELECT CAMPAIGN_NAME, AVG(CTR) AS AVG_CTR FROM CAMPAIGNS WHERE
  YEAR = '2026' AND MONTH = '03' AND DAY >= '15' AND DAY <= '21'
  GROUP BY CAMPAIGN_NAME ORDER BY AVG_CTR DESC LIMIT 5

✅ EM = 1.0 (100%)  [정확히 일치]

[Exec] Execution Accuracy (결과 일치도)
─────────────────────────────────
정답 결과 (5행):
  {campaign_name: Campaign_A, avg_ctr: 0.0850}
  {campaign_name: Campaign_B, avg_ctr: 0.0720}
  {campaign_name: Campaign_C, avg_ctr: 0.0685}
  {campaign_name: Campaign_D, avg_ctr: 0.0620}
  {campaign_name: Campaign_E, avg_ctr: 0.0580}

생성 결과 (5행):
  {campaign_name: Campaign_A, avg_ctr: 0.0850}
  {campaign_name: Campaign_B, avg_ctr: 0.0720}
  {campaign_name: Campaign_C, avg_ctr: 0.0685}
  {campaign_name: Campaign_D, avg_ctr: 0.0620}
  {campaign_name: Campaign_E, avg_ctr: 0.0580}

✅ Exec = 1.0 (100%)  [결과 일치]

═══════════════════════════════════════
```

---

#### 또 다른 예시: 테스트 케이스 #32 (실패)

**입력**:
```json
{
  "id": "T032",
  "question": "캠페인별 이번달 총 광고비는?",
  "ground_truth_sql": "SELECT campaign_name, SUM(cost) as total_cost FROM campaigns WHERE year='2026' AND month='03' GROUP BY campaign_name ORDER BY total_cost DESC"
}
```

#### Step 2-1: 정답 SQL 실행

```sql
SELECT campaign_name, SUM(cost) as total_cost
FROM campaigns
WHERE year='2026' AND month='03'
GROUP BY campaign_name
ORDER BY total_cost DESC
```

**정답 결과**:
```
┌───────────────────┬──────────────┐
│  campaign_name    │ total_cost   │
├───────────────────┼──────────────┤
│ Campaign_A        │ 5,000,000.00 │
│ Campaign_B        │ 3,500,000.00 │
│ Campaign_C        │ 2,800,000.00 │
└───────────────────┴──────────────┘
Row Count: 3
```

#### Step 2-2: Vanna로 SQL 생성

```
입력: "캠페인별 이번달 총 광고비는?"

Vanna 생성 SQL:
  SELECT campaign_name, cost
  FROM campaigns
  WHERE year='2026' AND month='03'

❌ 문제: GROUP BY 누락!
```

#### Step 2-3: 생성 SQL 실행

**생성 결과**:
```
┌───────────────────┬──────────────┐
│  campaign_name    │ cost         │
├───────────────────┼──────────────┤
│ Campaign_A        │ 100,000.00   │  ← 개별 행
│ Campaign_A        │ 150,000.00   │  ← 개별 행
│ Campaign_A        │ 120,000.00   │  ← 개별 행
│ Campaign_B        │ 80,000.00    │
│ ...               │ ...          │  총 342행 반환 (GROUP BY 없음)
└───────────────────┴──────────────┘
Row Count: 342  ← 정답은 3행!
```

#### Step 2-4: EM/Exec 계산

```
[EM] Exact Match
────────────────
정답: SELECT campaign_name, SUM(cost) as total_cost FROM campaigns ...
생성: SELECT campaign_name, cost FROM campaigns WHERE ...

❌ EM = 0.0 (0%)  [완전히 다름]

[Exec] Execution Accuracy
─────────────────────────
정답 결과: 3행 (각 캠페인별 합계)
생성 결과: 342행 (개별 레코드)

데이터 비교:
  정답[0] = {campaign_name: Campaign_A, total_cost: 5000000}
  생성[0] = {campaign_name: Campaign_A, cost: 100000}

  행 수 다름 (3 vs 342) → 일치 불가능

❌ Exec = 0.0 (0%)  [결과 불일치]

최종: EM=0%, Exec=0%
근원: GROUP BY 누락 (프롬프트 개선 필요)
```

---

### [09:30] Step 3: 100개 테스트 완료 후 리포트 생성

```bash
[09:30:00] 평가 완료!

╔════════════════════════════════════════════════════════════╗
║       📊 Spider EM/Exec 평가 결과 (2026-03-22)             ║
╚════════════════════════════════════════════════════════════╝

전체 테스트: 100건
소요 시간: 30분

┌──────────────────────────────────────────────────────────┐
│ ✅ EM (Exact Match) 정확도                                │
├──────────────────────────────────────────────────────────┤
│ 통과: 82 / 100                                           │
│ 정확도: 82.0%                                            │
│ 목표: >= 85%                                             │
│ 상태: ⚠️  목표 미달 (3% 부족)                              │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ ✅ Exec (Execution Accuracy) 정확도                        │
├──────────────────────────────────────────────────────────┤
│ 통과: 91 / 100                                           │
│ 정확도: 91.0%                                            │
│ 목표: >= 90%                                             │
│ 상태: ✅ 목표 달성!                                       │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ 📈 카테고리별 성과 분석                                   │
├──────────────────────────────────────────────────────────┤
│ 1. 단순 조회 (SELECT 1개 테이블): 95% / 98%             │
│    → 가장 성공적
│                                                          │
│ 2. 집계 함수 (GROUP BY): 78% / 88%                      │
│    → EM 낮음 (GROUP BY 누락 케이스 多)
│                                                          │
│ 3. 조인/서브쿼리: 72% / 85%                             │
│    → 복잡도 높을수록 성능 저하
│                                                          │
│ 4. 날짜 필터링: 88% / 96%                               │
│    → 날짜 컨텍스트 프롬프트 효과 있음
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ ❌ 실패 케이스 (상위 5개 문제)                             │
├──────────────────────────────────────────────────────────┤
│ 1. GROUP BY 누락 (12건)                                 │
│    예: "월별 매출" → SUM(revenue) 빼먹음                 │
│    근원: 프롬프트에서 "총", "합계" 키워드 인식 부족      │
│                                                          │
│ 2. HAVING 절 생성 못함 (8건)                            │
│    예: "CTR > 5% 캠페인" → WHERE로 생성                 │
│    근원: HAVING 사용 예시 부족                           │
│                                                          │
│ 3. WHERE vs JOIN 혼동 (5건)                             │
│    예: "채널별 매출" → JOIN 필요한데 WHERE로 생성         │
│                                                          │
│ 4. 파티션 형식 오류 (3건)                                │
│    예: WHERE day=22 대신 day='022' (2자리 패딩 누락)    │
│                                                          │
│ 5. 컬럼명 오타 (2건)                                    │
│    예: CTR vs ctr_rate 구분 불명확                      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ 🎯 권장 개선 방향                                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ 우선순위 1 (즉시): 프롬프트 개선                         │
│  • "총", "합계", "평균" 키워드 → SUM/AVG 명시            │
│  • "~인 것만" 키워드 → HAVING 사용 가이드                │
│                                                          │
│ 우선순위 2 (2주): Few-shot 증대                          │
│  • GROUP BY 예시 3개 추가                               │
│  • HAVING 예시 2개 추가                                 │
│  • JOIN 예시 3개 추가                                   │
│                                                          │
│ 우선순위 3 (1개월): 설계서 검토                          │
│  • sql_generator.py 프롬프트 재설계                     │
│  • Vanna 설정 최적화 (temperature, top_k)               │
│                                                          │
└──────────────────────────────────────────────────────────┘

[✅] 상세 결과 저장됨:
  - results/2026-03-22-result.json (JSON)
  - results/evaluation-report-2026-03-22.md (Markdown)
```

---

### [09:30 이후] Step 4: 프롬프트 개선 → 재평가

만약 EM < 85%라면:

```bash
# 1. sql_generator.py의 프롬프트 개선
# 파일: services/vanna-api/src/pipeline/sql_generator.py (라인 42-63)

date_context = (
    f"[날짜 컨텍스트] ... "
    f"[집계 함수 사용 규칙] "
    f"- '총', '합계', '평균', '최대', '최소' 키워드 있으면 SUM/AVG/MAX/MIN 반드시 사용 "
    f"- 같은 컬럼 여러 개 행 있으면 GROUP BY 필수 "
    f"- GROUP BY 사용하면 WHERE가 아니라 HAVING으로 필터링할 것"
)

# 2. Few-shot 추가
# 파일: Vanna의 유사 SQL 템플릿 (ChromaDB)에 새로운 예시 추가

# 3. 재평가
bash run_spider_evaluation.sh local

# 결과: EM 82% → 87% (목표 달성!)
```

---

## 테스트 케이스 예시 → 실행 결과

### CAPA 실제 데이터로 작성한 테스트 케이스

**파일**: `test_cases.json` (일부)

```json
[
  {
    "id": "T001",
    "category": "basic_single_metric",
    "question": "지난주 CTR이 가장 높은 캠페인 5개",
    "ground_truth_sql": "SELECT campaign_name, AVG(ctr) as avg_ctr FROM campaigns WHERE year='2026' AND month='03' AND day >= '15' AND day <= '21' GROUP BY campaign_name ORDER BY avg_ctr DESC LIMIT 5",
    "difficulty": "easy"
  },
  {
    "id": "T032",
    "category": "aggregation",
    "question": "캠페인별 이번달 총 광고비는?",
    "ground_truth_sql": "SELECT campaign_name, SUM(cost) as total_cost FROM campaigns WHERE year='2026' AND month='03' GROUP BY campaign_name ORDER BY total_cost DESC",
    "difficulty": "medium"
  },
  {
    "id": "T065",
    "category": "complex_filtering",
    "question": "지난달 매출이 1M 이상이고 ROI가 3배 이상인 캠페인들은?",
    "ground_truth_sql": "SELECT campaign_name, revenue, cost, roas FROM campaigns WHERE year='2026' AND month='02' AND revenue >= 1000000 AND roas >= 3.0 ORDER BY roas DESC",
    "difficulty": "hard"
  },
  {
    "id": "T078",
    "category": "time_series",
    "question": "최근 7일간 일별 CTR 추이를 보여줘",
    "ground_truth_sql": "SELECT year, month, day, AVG(ctr) as daily_ctr FROM campaigns WHERE year='2026' AND month='03' AND day >= '16' AND day <= '22' GROUP BY year, month, day ORDER BY year, month, day",
    "difficulty": "medium"
  },
  {
    "id": "T095",
    "category": "multi_condition",
    "question": "클릭 1000 이상이면서 CVR 1% 이상인 캠페인의 ROAS 상위 5개",
    "ground_truth_sql": "SELECT campaign_name, clicks, cvr, roas FROM campaigns WHERE clicks >= 1000 AND cvr >= 0.01 ORDER BY roas DESC LIMIT 5",
    "difficulty": "hard"
  }
]
```

### 평가 흐름 다이어그램

```
테스트 케이스 100개 (T001 ~ T100)
    ↓
┌─────────────────────────────────────────────┐
│ for each test_case in test_cases:           │
├─────────────────────────────────────────────┤
│ 1. Redash에서 정답 SQL 실행                 │
│    → ground_truth_result = {...}            │
│                                             │
│ 2. Vanna API로 SQL 생성                     │
│    질문 → [프롬프트] → LLM → generated_sql │
│                                             │
│ 3. Redash에서 생성 SQL 실행                 │
│    → generated_result = {...}               │
│                                             │
│ 4. EM 계산                                  │
│    normalize(generated_sql) ==              │
│    normalize(ground_truth_sql)?             │
│    → em_score = 0 or 1                      │
│                                             │
│ 5. Exec 계산                                │
│    generated_result ==                      │
│    ground_truth_result?                     │
│    → exec_score = 0 or 1                    │
│                                             │
│ 6. 결과 저장                                │
│    {                                        │
│      "test_id": "T001",                     │
│      "em": 1.0,                             │
│      "exec": 1.0,                           │
│      "avg": 1.0                             │
│    }                                        │
└─────────────────────────────────────────────┘
    ↓
100개 모두 평가 완료
    ↓
┌─────────────────────────────────────────────┐
│ 리포트 생성                                  │
├─────────────────────────────────────────────┤
│ - EM 정확도: 82%                            │
│ - Exec 정확도: 91%                          │
│ - 카테고리별 분석                           │
│ - 실패 케이스 분석                          │
│ - 개선 권장사항                             │
└─────────────────────────────────────────────┘
    ↓
JSON + Markdown 저장
```

---

## 평가 결과 해석

### Exec 91% vs EM 82% — 왜 차이나?

**예시**:
```
질문: "캠페인별 이번달 총 광고비"

정답 SQL:
  SELECT campaign_name, SUM(cost) as total_cost
  FROM campaigns
  WHERE year='2026' AND month='03'
  GROUP BY campaign_name
  ORDER BY total_cost DESC

생성 SQL (틀렸지만 우연히 결과가 같은 경우):
  SELECT campaign_name, SUM(cost) as total_cost
  FROM campaigns
  WHERE year='2026' AND month='03'
  GROUP BY campaign_name
  ORDER BY total_cost DESC, campaign_name

→ SQL은 다름 (EM = 0) 하지만 ORDER BY 추가 정렬도 결과 순서만 다를 수 있음
  또는 ORDER BY 없어도 내부적으로 같은 결과

따라서:
  EM = 0% (정확도 낮음)
  Exec = 1% (우연히 맞음)
```

### 결과별 다음 액션

**Case 1: EM >= 85%, Exec >= 90%** ✅
```
→ Phase 3로 진행 (프롬프트 최적화 X)
→ BIRD VES 평가 추가 (쿼리 효율성)
→ 월간 모니터링만 유지
```

**Case 2: EM < 85%, Exec >= 90%** ⚠️
```
→ SQL은 다르지만 결과는 맞는 경우 많음
→ 프롬프트 개선 (not urgent)
→ Few-shot 예시 추가로 해결
```

**Case 3: EM >= 85%, Exec < 90%** 🔴
```
→ SQL 구문은 맞지만 의미 오류 있음
→ 즉시 프롬프트 개선 필요
→ 설계서 검토
```

**Case 4: EM < 85%, Exec < 90%** 🚨
```
→ 심각한 오류 (GROUP BY 누락 등)
→ 대수술 필요 (프롬프트 대폭 개선)
→ 설계 재검토
```

---

## 월간 모니터링 계획

### 매월 22일 자동 평가

```bash
# Cron 설정
0 9 22 * * bash /path/to/run_spider_evaluation.sh docker

# 결과:
results/
├── 2026-03-22-result.json (초기 평가)
├── 2026-04-22-result.json (1개월 후)
├── 2026-05-22-result.json (2개월 후)
└── metrics-history.json (추이)
```

**추이 추적**:
```json
{
  "2026-03": {
    "em": 0.82,
    "exec": 0.91,
    "avg": 0.865,
    "changes": "초기 평가"
  },
  "2026-04": {
    "em": 0.87,
    "exec": 0.92,
    "avg": 0.895,
    "changes": "프롬프트 v1.1 개선"
  },
  "2026-05": {
    "em": 0.91,
    "exec": 0.94,
    "avg": 0.925,
    "changes": "Few-shot 확대 + 설계 최적화"
  }
}
```

### 대시보드 예시 (Redash)

```
┌─────────────────────────────────────────┐
│    Spider EM/Exec 월간 성능 추이         │
├─────────────────────────────────────────┤
│                                         │
│  Exec (실행 정확도)                     │
│  100% ┤         ▲                       │
│       │       ▲ │                       │
│       │     ▲   │ 94%                   │
│   90% ┼───▲─────┼───────                │
│       │ 91%     │ 92%                   │
│   80% ┤         │                       │
│       ├─────┴─────┴───────              │
│       │   3월  4월  5월                  │
│                                         │
│  EM (정확도)                           │
│  100% ┤         ▲                       │
│       │       ▲ │                       │
│       │     ▲   │ 91%                   │
│   90% ┼───────────┼───────               │
│       │ 82%   87% │                     │
│   80% ┤         │                       │
│       │         │                       │
│       ├─────┴─────┴───────              │
│       │   3월  4월  5월                  │
│                                         │
└─────────────────────────────────────────┘
```

---

## 결론

**Spider 평가 = CAPA의 SQL 생성 엔진 건강도 체크**

```
┌────────────────────────────────────────┐
│  Vanna API의 SQL 생성 정확도            │
│  (실제 CAPA 데이터 기반)                │
├────────────────────────────────────────┤
│                                        │
│ 입력: 자연어 질문                      │
│  → "지난주 CTR이 높은 캠페인 5개"       │
│                                        │
│ 처리: Vanna 파이프라인                 │
│  → ChromaDB (RAG)                      │
│  → Claude (SQL 생성)                   │
│  → sql_generator.py (프롬프트)         │
│                                        │
│ 출력: SQL                              │
│  → Athena 실행                         │
│  → Redash 시각화                       │
│  → Slack 봇 통지                       │
│                                        │
│ 평가 기준:                             │
│  ✅ EM >= 85% (SQL 정확도)             │
│  ✅ Exec >= 90% (결과 정확도)          │
│                                        │
│ 목표: 사용자가 신뢰할 수 있는           │
│      SQL 생성 엔진                      │
│                                        │
└────────────────────────────────────────┘
```

