# CAPA 기술 상세 문서

> **문서 목적**: 기술 구현 상세 및 코드 예시  
> **대상**: 개발팀  
> **참조**: [프로젝트 컨셉 문서](./project_concept_v4.md)

---

## 1. Vanna AI 구현 상세

### Vanna AI란?

오픈소스 Text-to-SQL 프레임워크. Python 라이브러리로 RAG 기반 동작.

### 핵심 구성

```python
from vanna.chromadb import ChromaDB_VectorStore
from vanna.openai import OpenAI_Chat

class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)

vn = MyVanna(config={'api_key': 'sk-...', 'model': 'gpt-4'})

# 1. DDL 학습
vn.train(ddl="""
    CREATE TABLE impressions (
        impression_id STRING,
        campaign_id STRING,
        bid_price DOUBLE
    )
""")

# 2. 예시 SQL 학습
vn.train(
    question="어제 캠페인별 노출수",
    sql="SELECT campaign_id, COUNT(*) FROM impressions WHERE date = current_date - 1 GROUP BY 1"
)

# 3. 도메인 문서 학습
vn.train(documentation="CTR = 클릭수 / 노출수")

# 4. SQL 생성
sql = vn.generate_sql("어제 캠페인별 CTR top 5")
```

### ChromaDB 역할

벡터 DB로 학습 데이터를 임베딩하여 저장. 질문이 들어오면 유사한 컨텍스트를 검색 (RAG).

**저장 데이터**:
- DDL (테이블 구조)
- 예시 SQL 쿼리
- 도메인 문서 (용어 설명)

**RAG 검색 플로우**:
```
User: "어제 캠페인별 CTR"
  ↓
ChromaDB 유사 검색:
  - 유사 DDL: impressions, clicks 테이블
  - 유사 SQL: "캠페인별 CTR 계산" 예시
  - 유사 문서: "CTR = 클릭수 / 노출수"
  ↓
LLM에게 전달 + SQL 생성
```

---

## 2. Report Generator 구현

### 구성 요소

```python
from jinja2 import Template
import boto3
from anthropic import Anthropic

class WeeklyReportGenerator:
    def __init__(self):
        self.athena = boto3.client('athena')
        self.llm = Anthropic()
    
    def fetch_data(self, start_date, end_date):
        """Athena에서 주간 데이터 조회"""
        kpi_query = f"""
        SELECT 
            COUNT(DISTINCT impression_id) as impressions,
            COUNT(DISTINCT click_id) as clicks,
            ROUND(COUNT(DISTINCT click_id) * 100.0 / 
                  COUNT(DISTINCT impression_id), 2) as ctr
        FROM ad_events
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        """
        return self._execute_query(kpi_query)
    
    def generate_insights(self, data):
        """LLM으로 인사이트 생성"""
        prompt = f"""
        광고 성과 데이터를 분석해서 핵심 인사이트 3가지를 작성하세요.
        
        [데이터]
        {data}
        
        [형식]
        - 간결한 bullet point
        - 실행 가능한 제안 포함
        """
        return self.llm.complete(prompt)
    
    def render_report(self, data, insights):
        """Jinja2 템플릿으로 렌더링"""
        template = Template("""
        # 📊 주간 광고 성과 리포트
        
        ## 📈 주요 KPI
        - 노출수: {{ impressions }}
        - 클릭수: {{ clicks }}
        - CTR: {{ ctr }}%
        
        ## 💡 AI 인사이트
        {{ insights }}
        """)
        return template.render(
            impressions=data['impressions'],
            clicks=data['clicks'],
            ctr=data['ctr'],
            insights=insights
        )
```

### Airflow DAG

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

def generate_and_send_report():
    generator = WeeklyReportGenerator()
    report = generator.generate(
        start_date=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
        end_date=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    )
    
    # Slack 전송
    slack = WebClient(token=os.environ['SLACK_TOKEN'])
    slack.chat_postMessage(channel='#marketing-reports', text=report)

with DAG(
    'weekly_ad_report',
    schedule_interval='0 9 * * MON',
    start_date=datetime(2026, 1, 1)
) as dag:
    generate_report = PythonOperator(
        task_id='generate_weekly_report',
        python_callable=generate_and_send_report
    )
```

---

## 3. Prophet 시계열 예측

### 왜 Prophet인가?

광고 데이터는 변동성이 큼:
- 요일별 패턴 (주중 vs 주말)
- 시간대별 변화 (피크 타임 vs 새벽)
- 계절성 (명절, 이벤트)

단순 임계값 기반 CloudWatch는 "월요일 오전이라 트래픽 적은지" vs "진짜 이상인지" 구분 어려움.

### 구현

```python
from prophet import Prophet
import pandas as pd

# 1. 과거 데이터 로드
df = pd.read_sql("""
    SELECT date, ctr 
    FROM mart_campaign_daily 
    WHERE date >= DATE_ADD('day', -30, CURRENT_DATE)
""", athena_conn)

# 2. Prophet 모델 학습
df.columns = ['ds', 'y']
model = Prophet(interval_width=0.95)
model.fit(df)

# 3. 예측
future = model.make_future_dataframe(periods=1)
forecast = model.predict(future)

# 4. 이상 탐지
today_forecast = forecast.iloc[-1]
actual_ctr = get_today_ctr()

if actual_ctr < today_forecast['yhat_lower']:
    send_alert(f"🚨 CTR 급락! 실제: {actual_ctr:.2%}, 예측 하한: {today_forecast['yhat_lower']:.2%}")
```

### 모델 비교

| 모델 | 특징 | 장점 | 단점 |
|------|------|------|------|
| **Prophet** | Meta 오픈소스 | 계절성 자동, 구현 쉬움 | 대규모 데이터 느림 |
| ARIMA | 전통 통계 | 해석 가능 | 계절성 수동 |
| LSTM | 딥러닝 | 복잡 패턴 학습 | 학습 데이터 많이 필요 |

---

## 4. CloudWatch Alarm 설정

### MVP Alert

```yaml
# Terraform
LogVolumeAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: capa-log-volume-low
    MetricName: IncomingRecords
    Namespace: AWS/Kinesis
    Statistic: Sum
    Period: 300  # 5분
    EvaluationPeriods: 1
    Threshold: 100
    ComparisonOperator: LessThanThreshold
    AlarmActions:
      - !Ref SlackAlertTopic
```

### SNS → Slack Webhook

```python
import json
import urllib.request

def lambda_handler(event, context):
    message = event['Records'][0]['Sns']['Message']
    
    slack_message = {
        "text": f"🚨 CloudWatch Alarm",
        "attachments": [{
            "color": "danger",
            "text": message
        }]
    }
    
    req = urllib.request.Request(
        os.environ['SLACK_WEBHOOK_URL'],
        data=json.dumps(slack_message).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)
```

---

## 5. dbt 데이터 모델링

### 왜 dbt가 필요한가?

Text-to-SQL 정확도 향상:

**dbt 없이**:
```sql
-- AI가 복잡한 JOIN + 계산 로직을 생성해야 함 (오류 가능성 높음)
SELECT 
  campaign_id,
  ROUND(COUNT(DISTINCT c.click_id) * 100.0 / 
        NULLIF(COUNT(DISTINCT i.impression_id), 0), 2) as ctr
FROM impressions i
LEFT JOIN clicks c ON i.event_id = c.impression_id
WHERE DATE(i.timestamp) = DATE_ADD('day', -1, CURRENT_DATE)
GROUP BY campaign_id
```

**dbt 있으면**:
```sql
-- AI가 단순 SELECT만 생성 (정확도 높음)
SELECT campaign_id, ctr
FROM mart_campaign_daily
WHERE date = DATE_ADD('day', -1, CURRENT_DATE)
```

### dbt 모델 예시

```sql
-- models/mart/mart_campaign_daily.sql

{{ config(materialized='table') }}

WITH impressions AS (
    SELECT * FROM {{ ref('stg_impressions') }}
),

clicks AS (
    SELECT * FROM {{ ref('stg_clicks') }}
),

conversions AS (
    SELECT * FROM {{ ref('stg_conversions') }}
)

SELECT
    i.campaign_id,
    DATE(i.timestamp) AS date,
    COUNT(DISTINCT i.impression_id) AS impressions,
    COUNT(DISTINCT c.click_id) AS clicks,
    COUNT(DISTINCT cv.conversion_id) AS conversions,
    ROUND(COUNT(DISTINCT c.click_id) * 100.0 / 
          NULLIF(COUNT(DISTINCT i.impression_id), 0), 2) AS ctr,
    ROUND(COUNT(DISTINCT cv.conversion_id) * 100.0 / 
          NULLIF(COUNT(DISTINCT c.click_id), 0), 2) AS cvr
FROM impressions i
LEFT JOIN clicks c ON i.event_id = c.impression_id
LEFT JOIN conversions cv ON c.event_id = cv.click_id
GROUP BY 1, 2
```

### 도입 시점

| 단계 | 시점 | 내용 |
|------|------|------|
| 1단계 | MVP | dbt 없이, 원본 테이블 직접 쿼리 |
| 2단계 | Text-to-SQL 정확도 이슈 발생 시 | dbt 도입, Mart 레이어 추가 |
| 3단계 | 테이블 10개+, 팀 확장 시 | 전체 데이터 모델 dbt 관리 |

---

## 6. 보안: SQL Injection 방지

### 악의적 SQL 실행 방지

```python
def is_safe_sql(sql: str) -> bool:
    """DML/DDL 차단"""
    forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']
    sql_upper = sql.upper()
    
    for keyword in forbidden:
        if keyword in sql_upper:
            return False
    return True

def execute_safe_sql(sql: str):
    if not is_safe_sql(sql):
        raise ValueError("Only SELECT queries allowed")
    
    # READ-ONLY 권한으로 실행
    return athena.execute_query(sql)
```

### Athena READ-ONLY 권한

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::capa-data-lake/*"
      ]
    }
  ]
}
```

---

**문서 끝**
