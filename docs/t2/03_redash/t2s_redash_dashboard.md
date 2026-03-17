# Text-to-SQL → Redash 대시보드 구현 가이드

Slack에서 자연어로 질문하면, Vanna AI가 SQL을 생성하고, Redash API로 대시보드(차트/그래프)를 자동 생성하여 링크를 받아보는 전체 파이프라인을 정리합니다.

---

## 1. 전체 아키텍처

```
사용자 (Slack)
    │
    │ @capa-bot "이번 달 캠페인별 CTR 추이 대시보드 만들어줘"
    ▼
┌──────────┐
│ slack-bot │  (Slack Bolt + Flask)
└────┬─────┘
     │ POST /query-to-dashboard
     ▼
┌───────────┐
│ vanna-api │  (FastAPI + Vanna + Anthropic)
│           │
│ ① 자연어 → SQL 변환 (Vanna + ChromaDB)
│ ② SQL 실행 (Athena)
│ ③ 시각화 유형 판단 (Claude AI)
│ ④ Redash API 호출 (쿼리 등록 + 시각화 + 대시보드 생성)
│ ⑤ 대시보드 URL 반환
└────┬──────┘
     │
     ▼
┌────────┐         ┌─────────┐
│ Redash │ ─────▶ │ Athena  │
│ (대시보드)│      │ (S3 조회) │
└────────┘         └─────────┘
     │
     ▼
사용자 (Slack에서 대시보드 URL 클릭 → Redash 웹 대시보드 확인)
```

---

## 2. 시각화 유형 결정 방법

### 2.1 판단 우선순위

```
사용자가 Slack에서 직접 지정 ("--차트 line")
        ↓ (미지정인 경우)
AI(Claude)가 질문 + SQL + 결과 컬럼을 분석하여 판단
        ↓ (AI 응답 실패 시 fallback)
규칙 기반 휴리스틱으로 자동 결정
```

### 2.2 AI 기반 판단 (추천)

SQL 생성 후, 같은 LLM에게 시각화 유형도 함께 결정하게 합니다.

**프롬프트 예시:**

```
사용자 질문: "{question}"
생성된 SQL: {sql}
결과 컬럼: {column_names}

이 데이터를 시각화할 최적의 차트 유형을 JSON으로 반환하세요:
{
  "chart_type": "line | bar | pie | table | counter | scatter",
  "x_column": "X축에 사용할 컬럼",
  "y_columns": ["Y축에 사용할 컬럼들"],
  "group_by": "그룹핑 컬럼 (있으면)",
  "reason": "선택 이유"
}
```

**판단 기준:**

| 데이터 패턴 | 차트 유형 | 예시 질문 |
|------------|----------|----------|
| 시간축 + 수치 | line (꺾은선) | "이번 달 캠페인별 CTR 추이" |
| 항목별 비교 | bar (막대) | "TOP 10 캠페인 성과" |
| 비율/구성 | pie (원형) | "광고 플랫폼별 지출 비율" |
| 단일 숫자 (합계, 평균) | counter (큰 숫자) | "오늘 총 광고비" |
| 두 수치 간 관계 | scatter (산점도) | "CPC와 CTR의 관계" |
| 상세 목록 | table (표) | "캠페인 상세 목록 보여줘" |

### 2.3 규칙 기반 fallback

AI 호출이 실패했을 때, SQL 결과의 컬럼 타입과 구조로 휴리스틱하게 판단합니다.

```python
def infer_chart_type(columns, row_count):
    """SQL 결과 구조로 시각화 유형 자동 추론"""
    # 단일 숫자 → counter
    if row_count == 1 and len(columns) == 1:
        return {"chart_type": "COUNTER", "x_column": None, "y_columns": [columns[0]]}

    # 날짜 컬럼 존재 → line chart
    date_cols = [c for c in columns if any(k in c.lower() for k in ["date", "time", "day", "hour", "month"])]
    numeric_cols = [c for c in columns if c not in date_cols]
    if date_cols:
        return {"chart_type": "CHART", "x_column": date_cols[0], "y_columns": numeric_cols, "series_type": "line"}

    # 2개 컬럼 (카테고리 + 숫자) → 항목 수에 따라 pie 또는 bar
    if len(columns) == 2:
        if row_count <= 8:
            return {"chart_type": "CHART", "x_column": columns[0], "y_columns": [columns[1]], "series_type": "pie"}
        return {"chart_type": "CHART", "x_column": columns[0], "y_columns": [columns[1]], "series_type": "column"}

    # 기본 → table
    return {"chart_type": "TABLE", "x_column": None, "y_columns": columns}
```

### 2.4 사용자 직접 지정

Slack 메시지에서 `--차트` 옵션으로 명시할 수 있습니다.

```
@capa-bot 대시보드 생성 캠페인별 CTR 추이 --차트 line
@capa-bot 대시보드 생성 플랫폼별 지출 --차트 pie
@capa-bot 대시보드 생성 TOP 10 캠페인         (→ 미지정이면 AI가 판단)
```

---

## 3. Redash API 연동 절차

### 3.1 사전 준비

| 항목 | 설명 |
|------|------|
| Redash API Key | Redash UI → Settings → Account → API Key 복사 |
| Data Source ID | Redash에 등록된 Athena Data Source의 ID (보통 1) |
| Redash 내부 URL | `http://redash.redash.svc.cluster.local` (K8s 클러스터 내부) |
| Redash 외부 URL | Ingress로 노출된 주소 (Slack 링크에 사용) |

### 3.2 Redash API 호출 순서

```
① POST /api/queries          → 쿼리 생성 (Vanna가 만든 SQL 등록)
② POST /api/query_results     → 쿼리 실행 (결과 데이터 생성)
③ POST /api/visualizations    → 시각화 생성 (AI가 결정한 차트 유형)
④ POST /api/dashboards        → 대시보드 생성
⑤ POST /api/widgets           → 대시보드에 시각화 위젯 추가
⑥ 대시보드 URL 반환            → Slack에 링크 전달
```

### 3.3 각 API 상세

#### ① 쿼리 생성

```python
response = requests.post(
    f"{REDASH_URL}/api/queries",
    headers={"Authorization": f"Key {REDASH_API_KEY}"},
    json={
        "name": f"[자동생성] {question[:50]}",
        "query": generated_sql,
        "data_source_id": REDASH_DATA_SOURCE_ID,
    }
)
query_id = response.json()["id"]
```

#### ② 쿼리 실행

```python
response = requests.post(
    f"{REDASH_URL}/api/query_results",
    headers={"Authorization": f"Key {REDASH_API_KEY}"},
    json={
        "query": generated_sql,
        "data_source_id": REDASH_DATA_SOURCE_ID,
        "max_age": 0,  # 캐시 무시, 항상 새로 실행
    }
)
query_result_id = response.json()["query_result"]["id"]
```

#### ③ 시각화 생성

**차트 유형별 options 설정:**

```python
# --- LINE 차트 ---
line_options = {
    "globalSeriesType": "line",
    "xAxis": {"type": "-", "labels": {"enabled": True}},
    "yAxis": [{"type": "linear"}],
    "columnMapping": {
        x_column: "x",
        **{y: "y" for y in y_columns}
    },
    "seriesOptions": {},
    "legend": {"enabled": True},
}

# --- BAR 차트 ---
bar_options = {
    "globalSeriesType": "column",
    "xAxis": {"type": "-", "labels": {"enabled": True}},
    "columnMapping": {
        x_column: "x",
        **{y: "y" for y in y_columns}
    },
}

# --- PIE 차트 ---
pie_options = {
    "globalSeriesType": "pie",
    "columnMapping": {
        x_column: "x",
        y_columns[0]: "y"
    },
}

# --- COUNTER ---
counter_options = {
    "counterColName": y_columns[0],
    "rowNumber": 1,
    "targetRowNumber": 1,
    "stringDecimal": 0,
    "stringDecChar": ".",
    "stringThouSep": ",",
}
```

**시각화 생성 API 호출:**

```python
viz_type = "CHART"  # 또는 "TABLE", "COUNTER"

response = requests.post(
    f"{REDASH_URL}/api/visualizations",
    headers={"Authorization": f"Key {REDASH_API_KEY}"},
    json={
        "query_id": query_id,
        "type": viz_type,
        "name": f"{question[:30]} 차트",
        "options": chart_options,  # 위에서 유형별로 선택
    }
)
visualization_id = response.json()["id"]
```

#### ④ 대시보드 생성

```python
response = requests.post(
    f"{REDASH_URL}/api/dashboards",
    headers={"Authorization": f"Key {REDASH_API_KEY}"},
    json={
        "name": f"[자동생성] {question[:50]} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    }
)
dashboard_id = response.json()["id"]
dashboard_slug = response.json()["slug"]
```

#### ⑤ 위젯 추가

```python
requests.post(
    f"{REDASH_URL}/api/widgets",
    headers={"Authorization": f"Key {REDASH_API_KEY}"},
    json={
        "dashboard_id": dashboard_id,
        "visualization_id": visualization_id,
        "width": 1,
        "options": {
            "position": {"col": 0, "row": 0, "sizeX": 6, "sizeY": 8}
        }
    }
)
```

#### ⑥ 대시보드 URL 반환

```python
dashboard_url = f"{REDASH_EXTERNAL_URL}/dashboard/{dashboard_slug}"
```

---

## 4. 서비스별 코드 변경 사항

### 4.1 vanna-api 변경

**파일: `services/vanna-api/src/main.py`**

추가할 엔드포인트:

```python
class DashboardRequest(BaseModel):
    question: str
    chart_type: Optional[str] = None  # 사용자가 직접 지정 (없으면 AI 판단)

class DashboardResponse(BaseModel):
    sql: str
    chart_type: str
    dashboard_url: str
    message: str

@app.post("/query-to-dashboard", response_model=DashboardResponse)
async def query_to_dashboard(request: DashboardRequest):
    """
    자연어 → SQL → Redash 대시보드 자동 생성

    1. Vanna로 SQL 생성
    2. Athena에서 SQL 실행 (결과 컬럼 확인용)
    3. 시각화 유형 결정 (사용자 지정 > AI 판단 > 규칙 기반)
    4. Redash API로 쿼리 등록 → 시각화 → 대시보드 생성
    5. 대시보드 URL 반환
    """
    ...
```

추가할 환경 변수:

```
REDASH_URL=http://redash.redash.svc.cluster.local
REDASH_EXTERNAL_URL=https://redash.capa.example.com
REDASH_API_KEY=<발급받은 API KEY>
REDASH_DATA_SOURCE_ID=1
```

**파일: `services/vanna-api/requirements.txt`**

```
requests  # Redash API 호출용 (추가)
```

### 4.2 slack-bot 변경

**파일: `services/slack-bot/app.py`**

`handle_mention()` 함수에 "대시보드 생성" 명령어 분기 추가:

```python
# "대시보드 생성" 명령어 확인
if "대시보드" in text and ("생성" in text or "만들어" in text):
    # --차트 옵션 파싱
    chart_type = None
    if "--차트" in text:
        chart_type = text.split("--차트")[-1].strip().split()[0]

    # 질문 텍스트 추출 (봇 멘션 제거)
    question = re.sub(r"<@\w+>", "", text)
    question = re.sub(r"대시보드\s*(생성|만들어줘?)", "", question)
    question = re.sub(r"--차트\s*\w+", "", question).strip()

    say(f"📊 <@{user}>님, 대시보드 생성을 시작합니다. 잠시만 기다려주세요...")

    try:
        payload = {"question": question}
        if chart_type:
            payload["chart_type"] = chart_type

        response = requests.post(
            f"{VANNA_API_URL}/query-to-dashboard",
            json=payload,
            timeout=120,
        )

        if response.status_code == 200:
            result = response.json()
            say(
                f"✅ 대시보드가 생성되었습니다!\n"
                f"📈 차트 유형: {result['chart_type']}\n"
                f"🔗 대시보드 링크: {result['dashboard_url']}\n"
                f"📝 SQL: ```{result['sql']}```"
            )
        else:
            say(f"❌ 대시보드 생성 실패: {response.status_code}")
    except Exception as e:
        logger.error(f"Dashboard creation error: {e}")
        say(f"⚠️ 대시보드 생성 중 오류: {e}")
    return
```

---

## 5. 사용 예시

### 5.1 기본 사용 (AI가 차트 유형 자동 판단)

```
사용자:  @capa-bot 대시보드 생성 이번 달 캠페인별 CTR 추이
봇:      📊 @사용자님, 대시보드 생성을 시작합니다. 잠시만 기다려주세요...
봇:      ✅ 대시보드가 생성되었습니다!
         📈 차트 유형: line
         🔗 대시보드 링크: https://redash.capa.example.com/dashboard/ctr-1709712000
         📝 SQL: SELECT date, campaign_id, AVG(ctr) AS avg_ctr
                 FROM ad_combined_log_summary
                 WHERE date >= date_add('day', -30, current_date)
                 GROUP BY date, campaign_id
                 ORDER BY date
```

### 5.2 차트 유형 직접 지정

```
사용자:  @capa-bot 대시보드 생성 광고 플랫폼별 지출 비율 --차트 pie
봇:      📊 @사용자님, 대시보드 생성을 시작합니다. 잠시만 기다려주세요...
봇:      ✅ 대시보드가 생성되었습니다!
         📈 차트 유형: pie
         🔗 대시보드 링크: https://redash.capa.example.com/dashboard/spend-1709712000
```

### 5.3 단순 숫자 조회 (counter)

```
사용자:  @capa-bot 대시보드 생성 오늘 총 광고비
봇:      ✅ 대시보드가 생성되었습니다!
         📈 차트 유형: counter
         🔗 대시보드 링크: https://redash.capa.example.com/dashboard/total-spend-1709712000
```

---

## 6. 사전 준비 체크리스트

- [ ] Redash에 Athena Data Source 등록 완료
- [ ] Redash API Key 발급 및 환경 변수 설정
- [ ] vanna-api Pod → Redash 서비스 네트워크 접근 확인
- [ ] Redash 외부 URL (Ingress) 설정 (Slack 링크용)
- [ ] Vanna 학습 데이터(DDL, 문서, SQL 예제) 등록 완료
- [ ] slack-bot에 VANNA_API_URL 환경 변수 설정 확인

---

## 7. 트러블슈팅

### Redash API 401 에러

```
원인: API Key가 잘못되었거나 만료됨
해결: Redash UI → Settings → Account → API Key 재발급 후 환경 변수 업데이트
```

### 시각화가 빈 차트로 나올 때

```
원인: columnMapping이 실제 컬럼명과 불일치
해결: Athena 쿼리 결과의 컬럼명을 확인하고 columnMapping 수정
     (대소문자 주의 - Athena는 소문자로 반환)
```

### 대시보드 링크가 접근 불가할 때

```
원인: REDASH_EXTERNAL_URL이 내부 URL로 설정됨
해결: Ingress로 노출된 외부 도메인으로 REDASH_EXTERNAL_URL 변경
```

### Redash 쿼리 실행 시간 초과

```
원인: Athena 쿼리가 너무 오래 걸림
해결: 1) Redash Data Source 설정에서 timeout 값 증가
     2) SQL에 LIMIT 추가 또는 파티션 조건(WHERE date >= ...) 사용
```
