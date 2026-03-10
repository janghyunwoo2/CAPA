# Redash API 직접 테스트 가이드

## 이 문서는 뭔가요?

나중에 Slack 봇이나 Vanna AI를 통해 자동으로 대시보드를 만드는 기능을 구현할 건데,
그 전에 **"Redash가 API로 명령을 잘 받는지"를 직접 손으로 확인**하는 테스트 절차입니다.

비유하자면:
> 자동 주문 시스템을 만들기 전에, **직접 주방에 가서 "이 메뉴 되나요?" 하고 물어보는 것**과 같습니다.

---

## 전체 흐름 한눈에 보기

이 테스트에서 할 일을 택배 비유로 설명하면:

```
1️⃣ 열쇠 받기       → API Key 발급 (Redash에 명령을 보내려면 신분증이 필요)
2️⃣ 배송지 확인      → Data Source 확인 (Redash가 Athena에 연결되어 있는지 확인)
3️⃣ 주문서 작성      → 쿼리 생성 (SQL을 Redash에 등록)
4️⃣ 주문 실행       → 쿼리 실행 (등록한 SQL을 실제로 돌려서 데이터 받기)
5️⃣ 포장하기        → 시각화 생성 (데이터를 막대그래프/파이차트 등으로 변환)
6️⃣ 진열대에 올리기   → 대시보드 생성 + 위젯 배치 (차트를 한 화면에 모아 보기)
7️⃣ 확인하기        → 브라우저에서 대시보드 URL 열어보기
```

실제 API 호출 순서:

```
[API Key 발급] → [Data Source 확인] → [쿼리 생성] → [쿼리 실행] → [시각화 생성] → [대시보드 생성] → [위젯 추가] → [URL 확인]
```

---

## 0. 시작 전 준비

### Redash란?

Redash는 **"데이터를 예쁜 차트로 그려주는 웹 도구"** 입니다.
보통은 웹 화면에서 마우스로 클릭해서 사용하지만, **API(프로그래밍 명령)로도 똑같은 작업**을 할 수 있습니다.

이 테스트에서는 터미널(명령어 창)에서 API를 직접 호출해봅니다.

### Redash 주소 확인하기

Redash가 우리 쿠버네티스 클러스터에 이미 배포되어 있습니다. 주소를 확인합니다:

```bash
# 이 명령어를 치면 Redash의 외부 주소(ALB)가 나옵니다
kubectl get ingress -n redash
```

출력 예시:
```
NAME             HOSTS   ADDRESS                                                  PORTS
redash-ingress   *       k8s-capa-xxxxx.ap-northeast-2.elb.amazonaws.com          80
```

`ADDRESS` 열에 나온 주소가 Redash의 URL입니다.

### 환경 변수 세팅

앞으로 같은 주소를 반복 입력하기 귀찮으니, 변수로 저장해둡니다:

```bash
# ⚠️ <ALB-주소> 부분을 위에서 확인한 실제 주소로 바꿔주세요
export REDASH_URL="http://k8s-capa-xxxxx.ap-northeast-2.elb.amazonaws.com"
```

### 살아있는지 확인 (헬스 체크)

```bash
curl $REDASH_URL/ping
```

`PONG`이 나오면 Redash가 정상 동작 중입니다. 👍

---

## 1단계: API Key 발급 (열쇠 받기)

### API Key가 뭔가요?

Redash API에 명령을 보내려면 **"나는 이 시스템을 쓸 수 있는 사람이야"를 증명하는 열쇠**(비밀번호 같은 것)가 필요합니다.
이것이 **API Key**입니다.

### 발급 방법

**방법 1: 웹 화면에서 발급 (권장)**

1. 브라우저에서 Redash 주소 접속
2. 로그인
3. 우측 상단 사람 아이콘 클릭 → **Settings**
4. **Account** 탭 → **API Key** 항목의 긴 문자열을 복사

**방법 2: 아직 계정이 없다면 (최초 1회)**

Redash를 처음 띄운 거라면 관리자 계정부터 만들어야 합니다:

```bash
# 웹에서: 브라우저로 아래 주소 접속 → 이름/이메일/비밀번호 입력
# $REDASH_URL/setup
```

또는 터미널에서:

```bash
kubectl exec -it deploy/redash -n redash -- python /app/manage.py users create \
  --admin \
  --password "admin123" \
  "Admin" "admin@capa.local"
```

### 발급받은 Key 저장

```bash
# ⚠️ 아래 값을 실제 발급받은 API Key로 바꿔주세요
export REDASH_API_KEY="여기에_복사한_API_Key_붙여넣기"
```

> 💡 **팁:** 이 Key는 비밀번호와 같으니 다른 사람에게 공유하지 마세요.

---

## 2단계: Data Source 확인 (배송지 확인)

### Data Source가 뭔가요?

Redash 혼자서는 데이터를 가지고 있지 않습니다.
**"어디서 데이터를 가져올지"** 알려줘야 하는데, 이것이 **Data Source(데이터 출처)** 입니다.

우리 프로젝트에서는 **Athena**(S3에 있는 광고 데이터를 SQL로 조회하는 AWS 서비스)를 Data Source로 씁니다.

### 확인 방법

```bash
curl -s \
  -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/data_sources | python3 -m json.tool
```

> 💡 각 부분이 하는 일:
> - `curl -s` → 터미널에서 HTTP 요청을 보내는 명령 (`-s`는 진행 표시줄 숨김)
> - `-H "Authorization: Key ..."` → "나 이 열쇠 가지고 있어" 라고 알려주는 부분
> - `| python3 -m json.tool` → 응답을 보기 좋게 정렬해줌

**정상이면 이렇게 나옵니다:**

```json
[
  {
    "id": 1,          ← 이 번호를 기억해두세요! (data_source_id)
    "name": "Athena",
    "type": "athena"
  }
]
```

### 만약 비어있다면? (Athena 연결이 안 되어 있을 때)

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/data_sources \
  -d '{
    "name": "Athena",
    "type": "athena",
    "options": {
      "region": "ap-northeast-2",
      "s3_staging_dir": "s3://capa-athena-results-827913617635/redash/",
      "schema": "capa_ad_logs",
      "work_group": "primary"
    }
  }' | python3 -m json.tool
```

> 💡 별도 Access Key를 입력하지 않아도 됩니다.
> Redash Pod에 IRSA(자동으로 AWS 권한을 부여하는 설정)가 되어 있기 때문입니다.

### 연결이 잘 되는지 테스트

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/data_sources/1/test | python3 -m json.tool
```

`{"message": "success"}` → 연결 성공! ✅

---

## 3단계: 쿼리 생성 (주문서 작성)

### 이 단계에서 하는 일

SQL 문(데이터를 꺼내달라는 명령)을 Redash에 **등록**합니다.
아직 실행하는 건 아니고, "이런 SQL을 쓸 거야"라고 **저장만** 하는 단계입니다.

### 쿼리 등록

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/queries \
  -d '{
    "name": "[테스트] 캠페인별 CTR 상위 5개",
    "query": "SELECT campaign_id, AVG(ctr) AS avg_ctr, SUM(impressions) AS total_impressions FROM ad_combined_log_summary WHERE date >= date_add('"'"'day'"'"', -7, current_date) GROUP BY campaign_id ORDER BY avg_ctr DESC LIMIT 5",
    "data_source_id": 1
  }' | python3 -m json.tool
```

> 💡 보내는 정보 3가지:
> - `name` → 쿼리 이름 (나중에 찾기 쉽게 붙이는 제목)
> - `query` → 실제 SQL 문 (최근 7일간 CTR 상위 5개 캠페인을 조회)
> - `data_source_id` → 2단계에서 확인한 Athena의 ID (보통 1)

**응답에서 중요한 값:**

```json
{
  "id": 1,        ← ⭐ query_id (다음 단계에서 계속 씀)
  "name": "[테스트] 캠페인별 CTR 상위 5개",
  "visualizations": [
    {
      "id": 1,    ← 기본 TABLE 시각화 (Redash가 자동으로 만들어줌)
      "type": "TABLE"
    }
  ]
}
```

```bash
# 응답에서 나온 id 값을 저장 (이후 단계에서 사용)
export QUERY_ID=1
```

> 💡 **알아두면 좋은 점:** 쿼리를 만들면 Redash가 자동으로 "TABLE" 시각화를 하나 만들어줍니다.
> (기본으로 표 형태를 보여주려고)

---

## 4단계: 쿼리 실행 (주문 실행)

### 이 단계에서 하는 일

3단계에서 등록한 SQL을 **실제로 Athena에 보내서 데이터를 받아옵니다.**
"주문서를 써놨으니 이제 실제로 음식을 만들어주세요" 하는 것과 같습니다.

### 실행

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/query_results \
  -d '{
    "query": "SELECT campaign_id, AVG(ctr) AS avg_ctr, SUM(impressions) AS total_impressions FROM ad_combined_log_summary WHERE date >= date_add('"'"'day'"'"', -7, current_date) GROUP BY campaign_id ORDER BY avg_ctr DESC LIMIT 5",
    "data_source_id": 1,
    "max_age": 0
  }' | python3 -m json.tool
```

> 💡 `"max_age": 0` → "캐시(이전 결과) 쓰지 말고 무조건 새로 실행해줘"라는 뜻

### 응답은 2가지 경우가 있습니다

**경우 A: 바로 결과가 오는 경우 (빠른 쿼리)**

```json
{
  "query_result": {
    "id": 1,
    "data": {
      "columns": [
        {"name": "campaign_id", "type": "string"},
        {"name": "avg_ctr",     "type": "float"},
        {"name": "total_impressions", "type": "integer"}
      ],
      "rows": [
        {"campaign_id": "camp_001", "avg_ctr": 0.085, "total_impressions": 15234},
        {"campaign_id": "camp_007", "avg_ctr": 0.072, "total_impressions": 8921}
      ]
    },
    "runtime": 3.45
  }
}
```

→ `data.rows`에 실제 데이터가 들어있습니다. 이게 나오면 성공! ✅

**경우 B: 아직 실행 중인 경우 (느린 쿼리)**

Athena 쿼리가 오래 걸리면, 바로 결과 대신 **"접수했으니 나중에 확인해"**라는 응답(job)이 옵니다.

```json
{
  "job": {
    "id": "abc-123-def",
    "status": 1
  }
}
```

이 경우 결과를 "폴링(반복 확인)"해야 합니다:

```bash
# job 상태 확인 (몇 초 기다렸다가 실행)
curl -s -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/jobs/abc-123-def | python3 -m json.tool
```

> 💡 **status 값 의미:**
> - `1` → 대기 중 (아직 순서 안 됨)
> - `2` → 실행 중 (Athena가 처리 중)
> - `3` → ✅ 성공! → `query_result_id`로 결과 조회
> - `4` → ❌ 실패

status가 `3`이 되면:

```bash
# 결과 조회 (query_result_id는 job 응답에서 확인)
curl -s -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/query_results/1 | python3 -m json.tool
```

---

## 5단계: 시각화 생성 (차트로 포장하기)

### 이 단계에서 하는 일

4단계에서 받은 숫자 데이터를 **눈에 보이는 차트(그래프)로 변환**합니다.
엑셀에서 데이터를 선택하고 "차트 삽입"을 누르는 것과 같은 동작입니다.

### 차트 종류별 설명

| Redash에서 쓰는 이름 | 우리가 아는 이름 | 언제 쓰나? | 예시 |
|---------------------|---------------|-----------|------|
| `column` | 막대 그래프 | 항목끼리 비교할 때 | "캠페인별 CTR 비교" |
| `line` | 꺾은선 그래프 | 시간 흐름을 볼 때 | "일별 CTR 추이" |
| `pie` | 원형(파이) 차트 | 비율을 볼 때 | "플랫폼별 지출 비율" |
| `COUNTER` | 큰 숫자 1개 | 합계/평균 같은 단일 값 | "오늘 총 광고비" |
| `TABLE` | 표 | 상세 목록을 볼 때 | "캠페인 리스트" |

### 5-1. 막대 그래프 (BAR) 만들기

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/visualizations \
  -d '{
    "query_id": '"$QUERY_ID"',
    "type": "CHART",
    "name": "캠페인별 CTR 막대 차트",
    "options": {
      "globalSeriesType": "column",
      "xAxis": {"type": "-", "labels": {"enabled": true}},
      "yAxis": [{"type": "linear"}],
      "columnMapping": {
        "campaign_id": "x",
        "avg_ctr": "y"
      },
      "legend": {"enabled": true},
      "series": {}
    }
  }' | python3 -m json.tool
```

> 💡 **options 해석:**
> - `globalSeriesType: "column"` → 차트 유형 = 막대 (column = 세로 막대)
> - `columnMapping` → **어떤 데이터를 X축/Y축에 놓을지** 지정
>   - `"campaign_id": "x"` → X축(가로)에 캠페인 이름
>   - `"avg_ctr": "y"` → Y축(세로)에 CTR 값

**응답에서 확인:**

```json
{
  "id": 2,     ← ⭐ visualization_id (대시보드에 넣을 때 씀)
  "type": "CHART",
  "name": "캠페인별 CTR 막대 차트"
}
```

```bash
export VIZ_ID=2
```

### 5-2. 꺾은선 그래프 (LINE) 만들기

먼저 시간 데이터가 있는 쿼리를 하나 더 만듭니다:

```bash
# 일별 CTR 추이 쿼리 생성
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/queries \
  -d '{
    "name": "[테스트] 일별 CTR 추이",
    "query": "SELECT date, AVG(ctr) AS avg_ctr FROM ad_combined_log_summary WHERE date >= date_add('"'"'day'"'"', -14, current_date) GROUP BY date ORDER BY date",
    "data_source_id": 1
  }' | python3 -m json.tool
```

```bash
# 응답에서 나온 query_id 저장
export QUERY_ID_LINE=2
```

```bash
# LINE 시각화 생성
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/visualizations \
  -d '{
    "query_id": '"$QUERY_ID_LINE"',
    "type": "CHART",
    "name": "일별 CTR 추이 라인 차트",
    "options": {
      "globalSeriesType": "line",
      "xAxis": {"type": "-", "labels": {"enabled": true}},
      "yAxis": [{"type": "linear"}],
      "columnMapping": {
        "date": "x",
        "avg_ctr": "y"
      },
      "legend": {"enabled": true}
    }
  }' | python3 -m json.tool
```

> 💡 **BAR와 다른 점은 딱 하나:** `globalSeriesType`이 `"column"` → `"line"`으로 바뀜

### 5-3. 원형 차트 (PIE) 만들기

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/visualizations \
  -d '{
    "query_id": '"$QUERY_ID"',
    "type": "CHART",
    "name": "캠페인별 노출 비율",
    "options": {
      "globalSeriesType": "pie",
      "columnMapping": {
        "campaign_id": "x",
        "total_impressions": "y"
      }
    }
  }' | python3 -m json.tool
```

> 💡 PIE는 설정이 단순합니다. `columnMapping`만 있으면 됩니다.

### 5-4. 큰 숫자 (COUNTER) 만들기

"오늘 총 노출수가 몇인지" 같은 **숫자 하나만 크게** 보여주는 시각화입니다.

```bash
# 먼저 단일 숫자를 뽑는 쿼리 생성
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/queries \
  -d '{
    "name": "[테스트] 오늘 총 노출수",
    "query": "SELECT SUM(impressions) AS total_impressions FROM ad_combined_log_summary WHERE date = current_date",
    "data_source_id": 1
  }' | python3 -m json.tool
```

```bash
export QUERY_ID_COUNTER=3
```

```bash
# COUNTER 시각화 생성
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/visualizations \
  -d '{
    "query_id": '"$QUERY_ID_COUNTER"',
    "type": "COUNTER",
    "name": "총 노출수",
    "options": {
      "counterColName": "total_impressions",
      "rowNumber": 1,
      "targetRowNumber": 1,
      "stringDecimal": 0,
      "stringDecChar": ".",
      "stringThouSep": ","
    }
  }' | python3 -m json.tool
```

> 💡 **options 해석:**
> - `counterColName` → 어떤 컬럼의 값을 보여줄지 (여기선 total_impressions)
> - `stringThouSep: ","` → 천 단위 쉼표 (15,234 처럼 표시)

---

## 6단계: 대시보드 만들기 (진열대에 올리기)

### 이 단계에서 하는 일

5단계에서 만든 차트들을 **한 화면에 모아서 보기 좋게 배치**합니다.
PPT 슬라이드에 차트들을 배치하는 것과 비슷합니다.

**2단계로 나뉩니다:**
1. 빈 대시보드 만들기 (빈 슬라이드 생성)
2. 위젯 추가하기 (슬라이드에 차트 배치)

### 6-1. 빈 대시보드 만들기

```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/dashboards \
  -d '{
    "name": "[테스트] 광고 성과 대시보드"
  }' | python3 -m json.tool
```

**응답:**

```json
{
  "id": 1,
  "slug": "테스트-광고-성과-대시보드",   ← URL에 쓰이는 이름
  "name": "[테스트] 광고 성과 대시보드"
}
```

```bash
export DASHBOARD_ID=1
export DASHBOARD_SLUG="테스트-광고-성과-대시보드"
```

### 6-2. 차트를 대시보드에 배치하기 (위젯 추가)

대시보드는 **6칸 x N줄 격자** 구조입니다:

```
┌───┬───┬───┬───┬───┬───┐
│ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │  ← col (가로 위치, 0~5)
├───┴───┴───┼───┴───┴───┤
│  TABLE    │   BAR     │  ← 각 위젯이 차지하는 영역
│  (3칸)    │   (3칸)   │
│           │           │
└───────────┴───────────┘
```

```bash
# 왼쪽에 TABLE 위젯 배치 (col=0, 가로3칸)
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/widgets \
  -d '{
    "dashboard_id": '"$DASHBOARD_ID"',
    "visualization_id": 1,
    "width": 1,
    "options": {
      "position": {"col": 0, "row": 0, "sizeX": 3, "sizeY": 8}
    }
  }' | python3 -m json.tool
```

> 💡 **position 해석:**
> - `col: 0` → 왼쪽 끝에서 시작
> - `row: 0` → 맨 위에서 시작
> - `sizeX: 3` → 가로 3칸 차지 (전체 6칸 중 절반)
> - `sizeY: 8` → 세로 8칸 차지

```bash
# 오른쪽에 BAR 차트 위젯 배치 (col=3, 가로3칸)
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/widgets \
  -d '{
    "dashboard_id": '"$DASHBOARD_ID"',
    "visualization_id": '"$VIZ_ID"',
    "width": 1,
    "options": {
      "position": {"col": 3, "row": 0, "sizeX": 3, "sizeY": 8}
    }
  }' | python3 -m json.tool
```

### 6-3. 브라우저에서 확인하기 🎉

```bash
echo "대시보드 URL: $REDASH_URL/dashboard/$DASHBOARD_SLUG"
```

출력된 URL을 브라우저에 붙여넣으면 **TABLE + BAR 차트가 나란히 있는 대시보드**가 보입니다!

---

## 7. Python 스크립트로 한 번에 테스트하기

위의 1~6단계를 **하나의 Python 스크립트로 자동 실행**할 수 있습니다.
curl을 하나하나 치기 귀찮을 때 사용하세요.

### 사전 준비

```bash
pip install requests
```

### 실행 방법

```bash
# 환경 변수 3개 설정
export REDASH_URL="http://k8s-capa-xxxxx.ap-northeast-2.elb.amazonaws.com"
export REDASH_API_KEY="여기에_API_Key"
export REDASH_DATA_SOURCE_ID=1

# 스크립트 실행
python test_redash_api.py
```

### 스크립트 전체 코드

```python
"""
Redash API 통합 테스트 스크립트
위의 1~6단계를 자동으로 한 번에 실행합니다.

사용법: python test_redash_api.py
"""
import os
import time
import requests

# ===== 설정 =====
REDASH_URL = os.getenv("REDASH_URL", "http://<ALB-주소>")
API_KEY = os.getenv("REDASH_API_KEY", "<발급받은_API_KEY>")
DATA_SOURCE_ID = int(os.getenv("REDASH_DATA_SOURCE_ID", "1"))

HEADERS = {
    "Authorization": f"Key {API_KEY}",
    "Content-Type": "application/json",
}

# ===== 테스트할 SQL =====
TEST_SQL = """
SELECT campaign_id,
       AVG(ctr) AS avg_ctr,
       SUM(impressions) AS total_impressions
FROM ad_combined_log_summary
WHERE date >= date_add('day', -7, current_date)
GROUP BY campaign_id
ORDER BY avg_ctr DESC
LIMIT 5
"""


def step(name):
    """단계 구분선 출력"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def check_response(resp, step_name):
    """API 응답 확인"""
    if resp.status_code >= 400:
        print(f"  ❌ {step_name} 실패: {resp.status_code}")
        print(f"     {resp.text[:300]}")
        return False
    print(f"  ✅ {step_name} 성공")
    return True


# ---- 1단계: 헬스 체크 ----
step("1단계: 헬스 체크 (Redash 살아있나?)")
resp = requests.get(f"{REDASH_URL}/ping")
print(f"  응답: {resp.text}")

# ---- 2단계: Data Source 확인 ----
step("2단계: Data Source 확인 (Athena 연결 확인)")
resp = requests.get(f"{REDASH_URL}/api/data_sources", headers=HEADERS)
if check_response(resp, "Data Source 조회"):
    for ds in resp.json():
        print(f"  - ID: {ds['id']}, 이름: {ds['name']}, 타입: {ds['type']}")

# ---- 3단계: 쿼리 생성 ----
step("3단계: 쿼리 생성 (SQL을 Redash에 등록)")
resp = requests.post(
    f"{REDASH_URL}/api/queries",
    headers=HEADERS,
    json={
        "name": "[API 테스트] 캠페인별 CTR Top 5",
        "query": TEST_SQL,
        "data_source_id": DATA_SOURCE_ID,
    },
)
if not check_response(resp, "쿼리 생성"):
    exit(1)

query_data = resp.json()
query_id = query_data["id"]
default_viz_id = query_data["visualizations"][0]["id"]
print(f"  query_id: {query_id}")
print(f"  기본 TABLE visualization_id: {default_viz_id}")

# ---- 4단계: 쿼리 실행 ----
step("4단계: 쿼리 실행 (Athena에 SQL 보내기)")
resp = requests.post(
    f"{REDASH_URL}/api/query_results",
    headers=HEADERS,
    json={
        "query": TEST_SQL,
        "data_source_id": DATA_SOURCE_ID,
        "max_age": 0,
    },
)

if resp.status_code == 200:
    result = resp.json()

    # 바로 결과가 온 경우
    if "query_result" in result:
        qr = result["query_result"]
        print(f"  ✅ 쿼리 실행 완료 (걸린 시간: {qr.get('runtime', '?')}초)")
        print(f"  컬럼: {[c['name'] for c in qr['data']['columns']]}")
        print(f"  행 수: {len(qr['data']['rows'])}개")
        for row in qr["data"]["rows"][:3]:
            print(f"    {row}")

    # 비동기(아직 실행 중)인 경우
    elif "job" in result:
        job = result["job"]
        print(f"  ⏳ Athena에서 처리 중... (job_id: {job['id']})")
        for _ in range(60):  # 최대 2분 대기
            time.sleep(2)
            job_resp = requests.get(
                f"{REDASH_URL}/api/jobs/{job['id']}", headers=HEADERS
            )
            job_data = job_resp.json()["job"]
            status = job_data["status"]
            if status == 3:  # 성공
                query_result_id = job_data["query_result_id"]
                print(f"  ✅ 쿼리 완료!")
                qr_resp = requests.get(
                    f"{REDASH_URL}/api/query_results/{query_result_id}",
                    headers=HEADERS,
                )
                qr = qr_resp.json()["query_result"]
                print(f"  컬럼: {[c['name'] for c in qr['data']['columns']]}")
                print(f"  행 수: {len(qr['data']['rows'])}개")
                break
            elif status == 4:  # 실패
                print(f"  ❌ 쿼리 실패: {job_data.get('error', 'unknown')}")
                exit(1)
        else:
            print("  ❌ 타임아웃 (2분 초과)")
            exit(1)
else:
    print(f"  ❌ 실패: {resp.status_code} - {resp.text[:200]}")
    exit(1)

# ---- 5단계: BAR 시각화 생성 ----
step("5단계: BAR 차트 생성 (막대그래프로 변환)")
resp = requests.post(
    f"{REDASH_URL}/api/visualizations",
    headers=HEADERS,
    json={
        "query_id": query_id,
        "type": "CHART",
        "name": "캠페인별 CTR (BAR)",
        "options": {
            "globalSeriesType": "column",
            "xAxis": {"type": "-", "labels": {"enabled": True}},
            "yAxis": [{"type": "linear"}],
            "columnMapping": {"campaign_id": "x", "avg_ctr": "y"},
            "legend": {"enabled": True},
        },
    },
)
if not check_response(resp, "BAR 시각화 생성"):
    exit(1)
bar_viz_id = resp.json()["id"]
print(f"  visualization_id: {bar_viz_id}")

# ---- 6단계: 대시보드 생성 + 위젯 배치 ----
step("6단계: 대시보드 생성 + 차트 배치")
resp = requests.post(
    f"{REDASH_URL}/api/dashboards",
    headers=HEADERS,
    json={"name": "[API 테스트] 광고 성과 대시보드"},
)
if not check_response(resp, "대시보드 생성"):
    exit(1)

dashboard_data = resp.json()
dashboard_id = dashboard_data["id"]
dashboard_slug = dashboard_data["slug"]
print(f"  dashboard_id: {dashboard_id}, slug: {dashboard_slug}")

# TABLE 위젯 (왼쪽 절반)
resp = requests.post(
    f"{REDASH_URL}/api/widgets",
    headers=HEADERS,
    json={
        "dashboard_id": dashboard_id,
        "visualization_id": default_viz_id,
        "width": 1,
        "options": {"position": {"col": 0, "row": 0, "sizeX": 3, "sizeY": 8}},
    },
)
check_response(resp, "TABLE 위젯 추가 (왼쪽)")

# BAR 위젯 (오른쪽 절반)
resp = requests.post(
    f"{REDASH_URL}/api/widgets",
    headers=HEADERS,
    json={
        "dashboard_id": dashboard_id,
        "visualization_id": bar_viz_id,
        "width": 1,
        "options": {"position": {"col": 3, "row": 0, "sizeX": 3, "sizeY": 8}},
    },
)
check_response(resp, "BAR 위젯 추가 (오른쪽)")

# ---- 완료 ----
step("🎉 완료!")
dashboard_url = f"{REDASH_URL}/dashboard/{dashboard_slug}"
print(f"  대시보드 URL: {dashboard_url}")
print(f"  → 브라우저에서 위 URL을 열어 확인하세요!")
```

### 기대 출력

```
============================================================
  1단계: 헬스 체크 (Redash 살아있나?)
============================================================
  응답: PONG

============================================================
  2단계: Data Source 확인 (Athena 연결 확인)
============================================================
  ✅ Data Source 조회 성공
  - ID: 1, 이름: Athena, 타입: athena

============================================================
  3단계: 쿼리 생성 (SQL을 Redash에 등록)
============================================================
  ✅ 쿼리 생성 성공
  query_id: 1
  기본 TABLE visualization_id: 1

============================================================
  4단계: 쿼리 실행 (Athena에 SQL 보내기)
============================================================
  ✅ 쿼리 실행 완료 (걸린 시간: 3.45초)
  컬럼: ['campaign_id', 'avg_ctr', 'total_impressions']
  행 수: 5개
    {'campaign_id': 'camp_001', 'avg_ctr': 0.085, 'total_impressions': 15234}
    ...

============================================================
  5단계: BAR 차트 생성 (막대그래프로 변환)
============================================================
  ✅ BAR 시각화 생성 성공
  visualization_id: 2

============================================================
  6단계: 대시보드 생성 + 차트 배치
============================================================
  ✅ 대시보드 생성 성공
  ✅ TABLE 위젯 추가 (왼쪽) 성공
  ✅ BAR 위젯 추가 (오른쪽) 성공

============================================================
  🎉 완료!
============================================================
  대시보드 URL: http://<ALB-주소>/dashboard/api-test-광고-성과-대시보드
  → 브라우저에서 위 URL을 열어 확인하세요!
```

---

## 8. 테스트 후 정리 (삭제)

테스트가 끝나면 만들었던 것들을 지울 수 있습니다:

```bash
# 대시보드 삭제
curl -s -X DELETE \
  -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/dashboards/$DASHBOARD_SLUG

# 쿼리 삭제 (쿼리를 지우면 그 안의 시각화도 같이 삭제됩니다)
curl -s -X DELETE \
  -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/queries/$QUERY_ID

# 잘 삭제됐는지 확인
curl -s -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/queries | python3 -m json.tool
```

---

## 9. 자주 만나는 문제와 해결법

### "PONG이 안 나와요" (헬스 체크 실패)

```
원인: Redash가 아직 안 떴거나, URL이 잘못됨
확인: kubectl get pods -n redash  →  모든 Pod가 Running인지 확인
     kubectl get ingress -n redash  →  ALB 주소 다시 확인
```

### "401 Unauthorized" 에러

```
원인: API Key가 틀리거나 빠졌음
확인: echo $REDASH_API_KEY  →  값이 제대로 들어있는지 확인
해결: Redash 웹 → Settings → Account에서 API Key 다시 복사
```

### "403 Forbidden" 에러

```
원인: 일반 사용자 키로 관리자 전용 API를 호출함
해결: admin 계정의 API Key를 사용하세요
```

### "table not found" 에러

```
원인: Athena에서 테이블을 못 찾음 (Data Source의 database 설정이 안 맞음)
확인: Redash 웹 → Data Sources → Athena → Schema 필드가 "capa_ad_logs"인지 확인
해결: Schema 값을 "capa_ad_logs"로 수정
```

### Data Source 연결 실패

```
원인: Redash Pod에 Athena 접근 권한이 없음
확인: kubectl describe sa redash-sa -n redash
     → annotations에 IAM Role ARN이 있는지 확인
해결: Terraform 02-iam.tf의 redash IRSA 설정 확인
```

### 차트에 "No data"가 표시됨

```
원인: 쿼리를 등록만 하고 실행(4단계)을 안 했음
해결: POST /api/query_results 를 먼저 호출해서 데이터를 만든 후 차트를 확인하세요
```

### PowerShell에서 curl이 안 될 때

Windows PowerShell에서는 `curl`이 `Invoke-WebRequest`의 별칭이라 다르게 동작합니다:

```powershell
# PowerShell 전용 환경 변수 설정
$env:REDASH_URL = "http://<ALB-주소>"
$env:REDASH_API_KEY = "<API_KEY>"

# 헬스 체크
Invoke-RestMethod -Uri "$env:REDASH_URL/ping"

# Data Source 조회
Invoke-RestMethod -Uri "$env:REDASH_URL/api/data_sources" `
  -Headers @{"Authorization" = "Key $env:REDASH_API_KEY"}
```

> 💡 **팁:** PowerShell이 불편하면 Git Bash나 WSL을 쓰면 Linux curl을 그대로 사용할 수 있습니다.
