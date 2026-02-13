# CAPA Implementation Guide

> **참조 문서**: [technical_specification_v3.2.md](./project_concept_v3.2.md)  
> **목적**: 페르소나별 개발을 위한 실무 가이드

---

## 1. Component Ownership Matrix

각 컴포넌트의 책임자, 의존성, 우선순위를 정의합니다.

| Component | Owner | Tech Stack | Dependencies | Priority |
|-----------|-------|------------|--------------|----------|
| **Log Generator** | Backend Dev | Python, boto3 | - | P0 |
| **Kinesis Pipeline** | Data Engineer | Kinesis Stream, Firehose | Log Generator | P0 |
| **Glue Catalog** | Data Engineer | AWS Glue | S3 Parquet | P0 |
| **Athena Setup** | Data Engineer | Athena, SQL | Glue Catalog | P0 |
| **Redash Dashboard** | Data Engineer | Redash | Athena | P1 |
| **Slack Bot (Basic)** | Backend Dev | Python, Slack Bolt | - | P1 |
| **Vanna AI Integration** | ML Engineer | Vanna AI, ChromaDB, OpenAI API | Athena, Slack Bot | P1 |
| **CloudWatch Alerts** | Data Engineer | CloudWatch, SNS | Kinesis | P1 |
| **Report Generator** | Backend Dev + ML | Python, Jinja2, Claude API | Athena, Airflow | P2 |
| **Prophet Model** | ML Engineer | Prophet, Python | Athena | P3 |
| **Airflow Orchestration** | Data Engineer | Airflow, EKS | Athena | P3 |
| **Terraform IaC** | DevOps | Terraform | AWS | All Phases |

**Priority 정의:**
- **P0**: 파이프라인 기본 동작을 위한 필수 컴포넌트
- **P1**: 핵심 기능 (Ask, Alert 기본)
- **P2**: 생산성 향상 기능 (Report, Dashboard)
- **P3**: 고도화 기능 (Prophet, Airflow)

---

## 2. 시스템 아키텍처 (System Architecture)

전체 시스템의 구성 요소와 연결 관계를 보여줍니다.

```mermaid
flowchart TB
    subgraph DataGen["Data Generation"]
        LogGen[Log Generator]
    end

    subgraph AWS["AWS Cloud"]
        subgraph Ingestion["Data Ingestion"]
            KDS[Kinesis Data Stream]
            KDF[Kinesis Firehose]
        end

        subgraph Storage["Data Storage"]
            S3_Raw[(S3 Raw Data)]
            S3_Processed[(S3 Parquet)]
            Glue[AWS Glue Catalog]
        end

        subgraph Analysis["Data Analysis"]
            Athena[Amazon Athena]
        end

        subgraph AI_App["AI Application Layer"]
            EKS[Amazon EKS]
            subgraph Pods["K8s Pods"]
                Vanna[Vanna AI Service]
                Chroma[ChromaDB]
                Airflow[Apache Airflow]
                Redash[Redash Dashboard]
                SlackBot[Slack Bot App]
            end
        end
        
        subgraph Monitoring["Monitoring"]
            CW[CloudWatch]
            SNS[SNS Topic]
            Prophet["Prophet (Future)"]
        end
    end

    subgraph Client["Client"]
        SlackUI[Slack Service]
        User[User]
    end

    LogGen -->|"JSON Stream"| KDS
    KDS -->|"Buffering"| KDF
    KDF -->|"Parquet Conversion"| S3_Processed
    Glue -.->|"Schema Metadata"| Athena
    Athena -->|"Query (S3 Scan)"| S3_Processed
    
    User -->|"Message"| SlackUI
    SlackUI <-->|"Socket Mode"| SlackBot
    SlackBot <-->|"API Call"| Vanna
    Vanna <-->|"Vector Search"| Chroma
    Vanna -->|"SQL Query"| Athena
    Athena -->|"Result Set"| Vanna
    
    Airflow -->|"ETL Job"| Athena
    
    KDS -->|"Metric"| CW
    CW -->|"Alarm"| SNS
    SNS -->|"Webhook"| SlackUI
    
    Athena -->|"KPI Visualization"| Redash
    User -->|"View Dashboard"| Redash
```

---

## 3. 데이터 흐름도 (Data Flow with Formats)

각 서비스를 거치면서 데이터가 어떻게 변환되는지 상세하게 표현합니다.

```mermaid
flowchart LR
    subgraph Generator["Log Generator"]
        LG[Python Script]
    end
    
    subgraph Kinesis["Kinesis Stream"]
        KDS[Data Stream]
    end
    
    subgraph Firehose["Kinesis Firehose"]
        KDF[Format Converter]
    end
    
    subgraph S3["S3 Data Lake"]
        S3B[(Parquet Files)]
    end
    
    subgraph Glue["AWS Glue"]
        CAT[Glue Catalog]
    end
    
    subgraph Athena["Athena"]
        ATH[Query Engine]
    end
    
    subgraph Applications["EKS App Layer"]
        BOT[Slack Bot Pod]
        VAN[Vanna AI Service]
        LLM[OpenAI/Claude API]
    end
    
    subgraph Slack["External Service"]
        UI[Slack Platform]
    end
    
    LG -->|"JSON"| KDS
    KDS -->|"JSON Stream"| KDF
    KDF -->|"Parquet"| S3B
    S3B -->|"Table Metadata"| CAT
    CAT -->|"Schema"| ATH
    
    UI <-->|"Socket Mode"| BOT
    BOT <-->|"API Call"| VAN
    VAN -->|"Context + Prompt"| LLM
    LLM -->|"SQL Query"| VAN
    VAN -->|"SQL Query"| ATH
    ATH -->|"Query Results"| VAN
    VAN -->|"Formatted Response"| BOT
```

### 2.1 데이터 형식 상세

#### Stage 1: Log Generator → Kinesis Stream
**형식**: JSON (Raw Event)
```json
{
  "impression_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "campaign_id": "campaign_spring_2026",
  "ad_id": "ad_12345",
  "user_id": "user_abc123",
  "timestamp": "2026-02-10T14:23:15Z",
  "bid_price": 0.25,
  "device_type": "mobile",
  "geo_country": "KR"
}
```
**특징**: 
- UTF-8 인코딩
- 1개 이벤트 = 1개 JSON 객체
- Kinesis에 `put_record()` 호출 시 전송

---

#### Stage 2: Kinesis Stream → Firehose
**형식**: JSON Stream (버퍼링)
```json
{"impression_id":"...","campaign_id":"..."}
{"impression_id":"...","campaign_id":"..."}
{"impression_id":"...","campaign_id":"..."}
```
**특징**:
- JSON Lines 형식 (개행 구분)
- Firehose가 최대 128MB 또는 900초마다 배치로 묶음
- 실시간성: 최소 60초 ~ 최대 900초 버퍼링

---

#### Stage 3: Firehose → S3
**형식**: Parquet (컬럼 기반 저장)
```
s3://capa-data-lake/impressions/
  date=2026-02-10/
    part-00000.parquet  (128MB)
    part-00001.parquet
  date=2026-02-11/
    part-00000.parquet
```
**특징**:
- Parquet 포맷으로 변환 (Firehose 자동 변환)
- 파티션 키: `date` (YYYY-MM-DD)
- 압축: Snappy (기본값)
- 스키마는 Glue Catalog에서 참조

**Parquet 내부 구조**:
```
Row Group 1:
  Column: impression_id (Binary)
  Column: campaign_id (Binary)
  Column: timestamp (Timestamp)
  Column: bid_price (Double)
Row Group 2:
  ...
```

---

#### Stage 4: Glue Catalog → Athena
**형식**: Table Metadata (DDL)
```sql
CREATE EXTERNAL TABLE impressions (
  impression_id STRING,
  campaign_id STRING,
  ad_id STRING,
  user_id STRING,
  timestamp TIMESTAMP,
  bid_price DOUBLE,
  device_type STRING,
  geo_country STRING
)
PARTITIONED BY (date STRING)
STORED AS PARQUET
LOCATION 's3://capa-data-lake/impressions/';
```
**특징**:
- Glue Catalog이 메타데이터만 관리 (실제 데이터는 S3)
- Athena는 Catalog를 참조하여 쿼리 실행

---

#### Stage 5: Athena Query Execution
**입력 (SQL)**:
```sql
SELECT campaign_id, COUNT(*) as impressions
FROM impressions
WHERE date = '2026-02-10'
GROUP BY campaign_id
ORDER BY impressions DESC
LIMIT 5;
```

**출력 (CSV → JSON 변환)**:
```json
[
  {"campaign_id": "campaign_A", "impressions": 125430},
  {"campaign_id": "campaign_B", "impressions": 98210},
  {"campaign_id": "campaign_C", "impressions": 87540},
  {"campaign_id": "campaign_D", "impressions": 76320},
  {"campaign_id": "campaign_E", "impressions": 65100}
]
```
**특징**:
- Athena 기본 출력: CSV (S3에 저장)
- API 호출 시: ResultSet을 JSON으로 파싱

---

#### Stage 6: Slack Bot → Vanna AI
**입력 (자연어)**:
```json
{
  "user_id": "U12345",
  "channel_id": "C67890",
  "query": "어제 캠페인별 노출수 top 5"
}
```

**Vanna AI 내부 처리**:
1. **RAG 검색 (ChromaDB)**:
```python
# 유사 컨텍스트 검색
similar_contexts = chromadb.query(
    query_embeddings=[embed("어제 캠페인별 노출수 top 5")],
    n_results=3
)
# Returns:
# - DDL: impressions 테이블 구조
# - Example SQL: 캠페인별 집계 쿼리
# - Documentation: "노출수 = impressions 테이블 COUNT"
```

2. **LLM Prompt 구성**:
```
You are a SQL expert. Generate a SQL query based on:

Context:
- Table: impressions (impression_id, campaign_id, timestamp, date)
- Example: SELECT campaign_id, COUNT(*) FROM impressions GROUP BY campaign_id
- Definition: 노출수 = COUNT of impression_id

User Question: "어제 캠페인별 노출수 top 5"

Generate SQL:
```

3. **LLM Response (SQL)**:
```sql
SELECT campaign_id, COUNT(*) as impressions
FROM impressions
WHERE date = DATE_FORMAT(CURRENT_DATE - INTERVAL '1' DAY, '%Y-%m-%d')
GROUP BY campaign_id
ORDER BY impressions DESC
LIMIT 5;
```

---

#### Stage 7: Vanna AI → Slack Bot
**출력 형식**:
```json
{
  "status": "success",
  "results": [
    {"campaign_id": "campaign_A", "impressions": 125430},
    {"campaign_id": "campaign_B", "impressions": 98210}
  ],
  "generated_sql": "SELECT campaign_id, COUNT(*) as impressions FROM impressions WHERE date = '2026-02-10' GROUP BY campaign_id ORDER BY impressions DESC LIMIT 5;",
  "execution_time_ms": 1234
}
```

**Slack 메시지 렌더링**:
```markdown
📊 **어제 캠페인별 노출수 top 5**

| campaign_id | impressions |
|-------------|------------|
| campaign_A  | 125,430    |
| campaign_B  | 98,210     |
| campaign_C  | 87,540     |
| campaign_D  | 76,320     |
| campaign_E  | 65,100     |

🔍 **생성된 SQL**:
```sql
SELECT campaign_id, COUNT(*) as impressions
FROM impressions
WHERE date = '2026-02-10'
GROUP BY campaign_id
ORDER BY impressions DESC
LIMIT 5;
```

⏱️ 실행 시간: 1.23초
```

---

## 4. 페르소나별 담당 영역

### 4.1 Backend Developer
**담당:**
- Log Generator 구현
- Slack Bot 개발 (메시지 수신/발신)
- Report Generator 서비스
- FastAPI 기반 API 서버 (Vanna AI ↔ Slack 연결)

**주요 작업:**
1. Slack App 생성 및 Bot Token 발급
2. Slack Bolt SDK로 이벤트 리스너 구현
3. Kinesis에 로그 전송 스크립트 작성
4. Report 템플릿 (Jinja2) 작성

---

### 4.2 Data Engineer
**담당:**
- Kinesis Data Stream/Firehose 설정
- S3 버킷 및 Parquet 포맷 구성
- Glue Catalog 테이블 정의
- Athena 쿼리 최적화
- CloudWatch Alarm 설정
- Redash 대시보드 구축
- Airflow DAG 작성

**주요 작업:**
1. Terraform으로 Kinesis → S3 → Glue 파이프라인 구축
2. Glue Crawler 설정 또는 수동 DDL 작성
3. Athena Workgroup 및 Output 버킷 설정
4. CloudWatch Metrics → SNS → Slack Webhook 연결
5. Redash를 Athena 데이터소스로 연결

---

### 4.3 ML Engineer
**담당:**
- Vanna AI Text-to-SQL 엔진 구현
- ChromaDB 벡터 DB 설정 및 학습 데이터 관리
- Prophet 시계열 이상 탐지 모델 개발
- Report Generator의 LLM 인사이트 생성 로직

**주요 작업:**
1. Vanna AI 초기화 및 DDL/SQL/문서 학습
2. ChromaDB 임베딩 저장 및 RAG 검색 최적화
3. Prophet 모델 학습 파이프라인 구축
4. LLM API (Claude/GPT) 호출 모듈 작성

---

### 4.4 DevOps

**역할**: Infrastructure as Code를 관리하고 안정적인 배포 파이프라인을 구축하는 전문가

**담당:**
- Terraform IaC 전체 관리 (계층 분리: Base/Apps)
- EKS 클러스터 구성 및 Helm 차트 배포
- CI/CD 파이프라인 구축 (OIDC 기반 보안)
- IRSA (IAM Roles for Service Accounts) 구성
- 모니터링 및 로깅 인프라

**핵심 원칙:**
1. **Infrastructure as Code**: 수동 설정 금지, 모든 것을 코드로 관리
2. **계층 분리**: AWS 인프라(`base`)와 K8s 앱(`apps`)의 Terraform State 분리
3. **보안 우선**: OIDC 기반 CI/CD, IRSA 적용, Least Privilege 원칙
4. **재현 가능성**: 전체 인프라를 `terraform apply` 한 번으로 구축

**주요 작업:**

#### 1. Terraform 계층 통합 설계
```
infrastructure/terraform/environments/dev/
└── base/              # [Unified] 통합 인프라 및 앱 배포
    ├── main.tf        # AWS Provider 설정
    ├── 05-eks.tf      # EKS Cluster
    └── 10-applications.tf # 모든 Helm Release (Airflow, Vanna, SlackBot 등)
```

**통합 이유**: 관리 복잡성을 줄이고, `terraform apply` 단일 명령어로 전체 스택을 배포하기 위함 (기존 Layer 분리 제거).

#### 2. IRSA (IAM Roles for Service Accounts) 구성
- Airflow, Slack Bot, Firehose 등 서비스별 IAM Role 분리
- Least Privilege 원칙: 각 서비스는 필요한 최소 권한만 보유
- OIDC Provider 생성 (EKS와 IAM 신뢰 관계 구축)

#### 3. CI/CD 파이프라인 (OIDC)
```yaml
# GitHub Actions에서 AWS Access Key 사용 금지
- name: Configure AWS Credentials (OIDC)
  uses: aws-actions/configure-aws-credentials@v2
  with:
    role-to-assume: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole
    aws-region: ap-northeast-2
```

#### 4. EKS 클러스터 및 Helm 배포
- EKS 1.30, Node Group (AL2023, t3.medium × 2~4)
- EBS CSI Driver Addon 설치 (PVC 지원)
- **Local Helm Chart (`generic-service`)** 를 통한 커스텀 앱 배포 표준화

#### 5. 모니터링
- CloudWatch Logs 수집
- CloudWatch Alarms (Kinesis, EKS)
- SNS → Slack Webhook 연동

**배포 순서:**
1. `base` 배포 (~25분): EKS 생성 후 Helm App 자동 배포 완료
2. 검증: `kubectl get pods -A`

**참고 문서:**
- [DevOps Implementation Guide](./devops/devops_implementation_guide.md)
- [MIGRATION_GUIDE.md](../../MIGRATION_GUIDE.md)

---

## 5. API 인터페이스 스펙

### API 버전 관리 전략

모든 API 엔드포인트는 버전을 명시하여 하위 호환성을 유지합니다.

**버전 관리 원칙**:
- URL에 버전 포함: `/api/v1/ask`, `/api/v2/ask`
- 환경 변수로 기본 버전 제어: `API_VERSION=v1`
- 클라이언트는 환경 변수 참조하여 동적 구성

**Python 구현 예시**:
```python
import os
from fastapi import FastAPI

API_VERSION = os.getenv("API_VERSION", "v1")
app = FastAPI()

@app.post(f"/api/{API_VERSION}/ask")
async def ask_endpoint(query: str):
    # Implementation
    pass
```

**클라이언트 (Slack Bot) 구현**:
```python
API_VERSION = os.getenv("API_VERSION", "v1")
VANNA_API_URL = f"http://vanna-service:8000/api/{API_VERSION}/ask"

response = requests.post(VANNA_API_URL, json={"query": user_query})
```

---

### 5.1 Slack Bot ↔ Vanna AI Service

#### `POST /api/v1/ask`
**설명**: 자연어 질의를 받아 SQL을 생성하고 Athena 실행 후 결과 반환.

**Request:**
```json
{
  "user_id": "U12345",
  "channel_id": "C67890",
  "query": "어제 캠페인별 CTR top 5 알려줘"
}
```

**Response:**
```json
{
  "status": "success",
  "results": [
    {"campaign_id": "campaign_A", "ctr": 2.5},
    {"campaign_id": "campaign_B", "ctr": 2.1}
  ],
  "generated_sql": "SELECT campaign_id, ROUND(...) as ctr FROM events WHERE date = '2026-02-10' ORDER BY ctr DESC LIMIT 5",
  "execution_time_ms": 1234
}
```

**Error Response:**
```json
{
  "status": "error",
  "error_code": "INVALID_SQL",
  "message": "생성된 SQL에 문법 오류가 있습니다."
}
```

---

#### `POST /api/v1/report/generate`
**설명**: 주간/월간 리포트 생성 요청.

**Request:**
```json
{
  "report_type": "weekly",
  "start_date": "2026-02-03",
  "end_date": "2026-02-09",
  "channel_id": "C67890"
}
```

**Response:**
```json
{
  "status": "success",
  "report_url": "https://s3.amazonaws.com/capa-reports/weekly_2026-02-09.pdf",
  "slack_message_ts": "1707123456.789012"
}
```

---

### 5.2 Error Code 정의

**전체 에러 코드 목록**:

| Code | Description | User Message | Retry 가능? | HTTP Status |
|------|-------------|--------------|------------|-------------|
| `INVALID_SQL` | SQL 문법 오류 | "질문을 다시 정리해주세요." | Yes | 400 |
| `ATHENA_TIMEOUT` | Athena 실행 시간 초과 (30초+) | "쿼리가 복잡합니다. 기간을 줄여주세요." | Yes | 504 |
| `QUOTA_EXCEEDED` | 일일 API 호출 한도 초과 | "일일 한도를 초과했습니다." | No | 429 |
| `CHROMADB_UNAVAILABLE` | ChromaDB 연결 실패 | "일시적 오류입니다. 잠시 후 다시 시도해주세요." | Yes | 503 |
| `LLM_API_ERROR` | OpenAI/Claude API 오류 | "AI 서비스 오류입니다. 잠시 후 다시 시도해주세요." | Yes | 502 |
| `ATHENA_EXECUTION_ERROR` | Athena 쿼리 실행 중 오류 | "데이터 조회 중 오류가 발생했습니다." | No | 500 |

**Error Response 공통 포맷**:
```json
{
  "status": "error",
  "error_code": "ATHENA_TIMEOUT",
  "message": "쿼리가 복잡합니다. 기간을 줄여주세요.",
  "retry_after": 5,  // Optional: 재시도 가능 시간 (초)
  "request_id": "req_abc123"  // 디버깅용
}
```

---

### 5.3 CloudWatch → SNS → Slack Webhook

#### Slack Webhook Payload
**설명**: CloudWatch Alarm 발생 시 SNS가 Slack으로 전송하는 메시지.

**SNS Message Format:**
```json
{
  "AlarmName": "capa-log-volume-low",
  "NewStateValue": "ALARM",
  "NewStateReason": "Threshold Crossed: 1 datapoint [45.0] was less than the threshold (100.0).",
  "StateChangeTime": "2026-02-11T06:32:15.000+0000",
  "MetricName": "IncomingRecords",
  "Namespace": "AWS/Kinesis"
}
```

**Slack Webhook Transform** (Lambda 또는 SNS 직접):
```json
{
  "text": "🚨 *CAPA Alert*\n로그 유입량이 임계값 이하입니다.\n• 현재: 45건/분\n• 임계값: 100건/분\n• 시각: 2026-02-11 06:32"
}
```

---

## 6. Slack App 설정 가이드

### 6.1 Slack App 생성

1. **Slack API 포털 접속**: https://api.slack.com/apps
2. **"Create New App"** 클릭
3. **"From an app manifest"** 선택 (아래 manifest 사용)

### 6.2 App Manifest (JSON)

```json
{
  "display_information": {
    "name": "CAPA Bot",
    "description": "AI-powered Ad Analytics Assistant",
    "background_color": "#2c3e50"
  },
  "features": {
    "bot_user": {
      "display_name": "CAPA",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "chat:write",
        "files:write",
        "channels:history",
        "groups:history",
        "im:history",
        "mpim:history"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "request_url": "https://your-domain.com/slack/events",
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {
      "is_enabled": true,
      "request_url": "https://your-domain.com/slack/interactions"
    },
    "org_deploy_enabled": false,
    "socket_mode_enabled": true
  }
}
```

### 6.3 필수 Token 발급

**Bot Token 발급**:
1. App 생성 후 **"OAuth & Permissions"** 메뉴
2. **"Install to Workspace"** 클릭
3. `xoxb-`로 시작하는 **Bot User OAuth Token** 복사
   - `.env`에 `SLACK_BOT_TOKEN=xoxb-...` 저장

**App Token 발급** (Socket Mode 사용 시):
1. **"Basic Information"** → **"App-Level Tokens"**
2. **"Generate Token and Scopes"** 클릭
3. Scope: `connections:write` 추가
4. `xapp-`로 시작하는 토큰 복사
   - `.env`에 `SLACK_APP_TOKEN=xapp-...` 저장

**Signing Secret**:
1. **"Basic Information"** → **"App Credentials"**
2. **Signing Secret** 복사
   - `.env`에 `SLACK_SIGNING_SECRET=...` 저장

### 6.4 Scope 설명

| Scope | 용도 | 필수 여부 |
|-------|------|----------|
| `app_mentions:read` | @mention 이벤트 수신 | 필수 |
| `chat:write` | 메시지 전송 | 필수 |
| `files:write` | 리포트 파일 업로드 | 필수 |
| `channels:history` | 채널 메시지 읽기 | Ask 기능용 |
| `im:history` | DM 메시지 읽기 | DM 지원 시 |

### 6.5 환경 변수 확인

```bash
# .env 파일
SLACK_BOT_TOKEN=  
SLACK_APP_TOKEN=  
SLACK_SIGNING_SECRET=  
```

---

## 7. 데이터 스키마 상세

### 7.1 Glue Table: `impressions`
**설명**: 광고 노출 이벤트 데이터.

| Column | Type | Description | Sample Value | Nullable |
|--------|------|-------------|--------------|----------|
| `impression_id` | string | 노출 고유 ID (UUID) | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` | No |
| `campaign_id` | string | 캠페인 식별자 | `"campaign_spring_2026"` | No |
| `ad_id` | string | 광고 소재 ID | `"ad_12345"` | No |
| `user_id` | string | 사용자 ID (익명화) | `"user_abc123"` | Yes |
| `timestamp` | timestamp | 노출 발생 시각 (UTC) | `2026-02-10T14:23:15Z` | No |
| `bid_price` | double | 입찰가 (USD) | `0.25` | No |
| `device_type` | string | 디바이스 유형 | `"mobile"`, `"desktop"` | Yes |
| `geo_country` | string | 국가 코드 (ISO 3166) | `"KR"`, `"US"` | Yes |

**Partition Key**: `date` (string, format: `YYYY-MM-DD`)

**Sample JSON (Kinesis 전송 전):**
```json
{
  "impression_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "campaign_id": "campaign_spring_2026",
  "ad_id": "ad_12345",
  "user_id": "user_abc123",
  "timestamp": "2026-02-10T14:23:15Z",
  "bid_price": 0.25,
  "device_type": "mobile",
  "geo_country": "KR"
}
```

---

### 7.2 Glue Table: `clicks`
**설명**: 광고 클릭 이벤트 데이터.

| Column | Type | Description | Sample Value | Nullable |
|--------|------|-------------|--------------|----------|
| `click_id` | string | 클릭 고유 ID (UUID) | `"b2c3d4e5-f6a7-8901-bcde-f12345678901"` | No |
| `impression_id` | string | 연결된 노출 ID (FK) | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` | No |
| `timestamp` | timestamp | 클릭 발생 시각 (UTC) | `2026-02-10T14:23:45Z` | No |
| `cpc_cost` | double | CPC 비용 (USD) | `0.18` | No |

**Partition Key**: `date` (string, format: `YYYY-MM-DD`)

---

### 7.3 Glue Table: `conversions`
**설명**: 전환 이벤트 데이터.

| Column | Type | Description | Sample Value | Nullable |
|--------|------|-------------|--------------|----------|
| `conversion_id` | string | 전환 고유 ID (UUID) | `"c3d4e5f6-a7b8-9012-cdef-123456789012"` | No |
| `click_id` | string | 연결된 클릭 ID (FK) | `"b2c3d4e5-f6a7-8901-bcde-f12345678901"` | No |
| `timestamp` | timestamp | 전환 발생 시각 (UTC) | `2026-02-10T15:10:23Z` | No |
| `event_type` | string | 전환 유형 | `"signup"`, `"purchase"`, `"add_to_cart"` | No |
| `revenue` | double | 전환 수익 (USD) | `49.99` | Yes |

**Partition Key**: `date` (string, format: `YYYY-MM-DD`)

---

## 8. 로컬 개발 환경 설정

> ⚠️ **중요**: 환경 변수를 먼저 설정한 후 다른 도구를 설치하세요.

### 8.1 환경 변수 설정 (최우선)

**`.env` 파일 생성** (프로젝트 루트):
```bash
# AWS
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-northeast-2

# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your_signing_secret

# OpenAI/Claude
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-claude-key

# API Configuration
API_VERSION=v1
VANNA_API_URL=http://localhost:8000

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# Athena
ATHENA_WORKGROUP=capa-workgroup
ATHENA_OUTPUT_BUCKET=s3://capa-athena-results/
```

**Python에서 로드**:
```python
from dotenv import load_dotenv
import os

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_VERSION = os.getenv("API_VERSION", "v1")  # Default: v1
```

**`.env.example` 파일 생성** (Git에 커밋용):
```bash
# AWS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-northeast-2

# Slack
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
SLACK_SIGNING_SECRET=

# ... (나머지 변수)
```

---

### 8.2 필수 도구 설치

```bash
# Python 3.11+
python --version

# AWS CLI
aws --version
aws configure  # Access Key, Secret Key, Region 설정

# Terraform
terraform --version

# Docker (LocalStack 사용 시)
docker --version
```

---

### 8.3 LocalStack을 활용한 로컬 AWS 시뮬레이션

**설치:**
```bash
pip install localstack awscli-local
```

**시작:**
```bash
# docker-compose.yml
version: '3.8'
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=kinesis,s3,glue,athena,sns
      - DEBUG=1
    volumes:
      - "./localstack_data:/tmp/localstack"

# 실행
docker-compose up -d
```

**Kinesis 테스트:**
```bash
# Stream 생성
awslocal kinesis create-stream --stream-name capa-logs --shard-count 1

# 데이터 전송
awslocal kinesis put-record \
  --stream-name capa-logs \
  --partition-key "test" \
  --data '{"impression_id":"test123","campaign_id":"test_campaign"}'

# 데이터 확인
awslocal kinesis get-shard-iterator \
  --stream-name capa-logs \
  --shard-id shardId-000000000000 \
  --shard-iterator-type TRIM_HORIZON
```

---

### 8.4 Python 가상 환경 설정

**Backend/ML Engineer 공통:**
```bash
# 프로젝트 루트에서
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

**requirements.txt (예시):**
```txt
# Slack Bot
slack-bolt==1.18.0
slack-sdk==3.23.0

# AWS
boto3==1.34.0
awscli==1.32.0

# ML/AI
vanna==0.5.0
chromadb==0.4.22
openai==1.12.0
anthropic==0.18.0
prophet==1.1.5

# Data Processing
pandas==2.2.0
pyarrow==15.0.0

# Web Framework
fastapi==0.109.0
uvicorn==0.27.0
jinja2==3.1.3

# Utilities
python-dotenv==1.0.1
pydantic==2.6.0
```

---

### 8.5 ChromaDB 영속성 설정

**Docker로 ChromaDB 실행** (볼륨 마운트 필수):
```bash
# docker-compose.yml에 추가
services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - ./chromadb_data:/chroma/chroma  # 영속성 확보
    environment:
      - IS_PERSISTENT=TRUE
```

**학습 데이터 백업 전략**:
```python
# 주기적으로 S3에 백업
import boto3
import chromadb

def backup_chromadb_to_s3():
    # ChromaDB collection export
    client = chromadb.Client()
    collection = client.get_collection("vanna_training")
    
    # S3 upload
    s3 = boto3.client('s3')
    s3.upload_file(
        './chromadb_data/chroma.sqlite3',
        'capa-backups',
        f'chromadb/backup_{datetime.now().strftime("%Y%m%d")}.sqlite3'
    )
```

---

## 9. 개발 우선순위 및 마일스톤

### Phase 0: 인프라 기초 (1주)
- [ ] AWS 계정 및 IAM 설정 (`capa-admin`)
- [ ] Terraform 백엔드 설정 (S3 + DynamoDB)
- [ ] GitHub Repository 생성 및 Secrets 설정
- [ ] 로컬 개발 환경 구축 (.env, Terraform, AWS CLI)

**Owner**: DevOps, All Team

---

### Phase 1: Data Pipeline (2주)
- [ ] Log Generator 구현 (Python)
- [ ] Kinesis Stream/Firehose (Terraform)
- [ ] S3 Bucket 및 Lifecycle (Terraform)
- [ ] Glue Catalog 및 Athena Workgroup (Terraform)
- [ ] Athena 쿼리 테스트

**Owner**: Data Engineer, Backend Dev

**검증 기준**: Athena에서 `SELECT * FROM impressions LIMIT 10` 성공

---

### Phase 2: 병렬 작업 (Slack Bot + Vanna AI 기초) (2주)

> ⚠️ **중요**: 아래 2A와 2B는 **병렬로 진행 가능**합니다.

#### Phase 2A: Slack Bot 기본 (1주)
- [ ] Slack App 생성 및 Bot Token 발급 (Manifest 활용)
- [ ] Echo Bot 구현 (Socket Mode)
- [ ] Slack Workspace 배포

**Owner**: Backend Dev

**검증 기준**: `@capa-bot 안녕` → `안녕하세요!` 응답

---

#### Phase 2B: Vanna AI 기초 설정 (1주)
- [ ] ChromaDB Docker 설정 (Local Persistence)
- [ ] Vanna AI 초기화 (DDL 학습)
- [ ] 단독 테스트 스크립트 작성

**Owner**: ML Engineer

**검증 기준**: Python 스크립트로 "어제 노출수" → SQL 생성 성공

---

### Phase 2C: EKS & Airflow (DevOps) (2주)
- [ ] EKS 클러스터 생성 (Terraform `06-eks.tf`)
- [ ] Airflow Helm Release (Terraform `10-helm-releases.tf`)
- [ ] Vanna API 서비스 배포 준비

**Owner**: DevOps

**검증 기준**: `kubectl get pods -n airflow` Running 상태 확인

---

### Phase 3: Ask 기능 통합 (1주)
- [ ] `/api/v1/ask` API 구현 (Vanna AI 호출)
- [ ] Slack Bot ↔ Vanna API 연동
- [ ] 에러 핸들링 (Error Code 구현)
- [ ] End-to-End 테스트

**Owner**: Backend Dev + ML Engineer (협업)

**검증 기준**: 슬랙에서 `@capa-bot 어제 노출수` → Athena 결과 반환

**의존성**: Phase 2A + 2B 완료

---

### Phase 4: Alert (1주)
- [ ] CloudWatch Metrics 설정
- [ ] CloudWatch Alarm → SNS → Slack 연결
- [ ] 테스트 알람 발송

**Owner**: Data Engineer

**검증 기준**: 수동으로 로그 유입 중단 → 슬랙 알림 수신

---

### Phase 5: Dashboard & Report (2주)
- [ ] Redash 설치 및 Athena 연결
- [ ] 기본 대시보드 (일별 트렌드, 캠페인 성과)
- [ ] Report Generator 구현
- [ ] Airflow DAG 작성 (주간 리포트 자동 생성)

**Owner**: Data Engineer, Backend Dev, ML Engineer

**검증 기준**: Redash 대시보드 확인 + 주간 리포트 슬랙 수신

---

### Phase 6: Prophet 이상 탐지 (2주)
- [ ] Prophet 모델 학습 파이프라인
- [ ] Athena 집계 데이터 → Prophet 예측
- [ ] 이상 탐지 시 슬랙 알림

**Owner**: ML Engineer

**검증 기준**: 의도적으로 CTR 하락 데이터 투입 → 이상 알림 수신

---

## 10. 코드 저장소 구조

인프라(Terraform)와 애플리케이션(Source Code)을 분리하여 관리합니다.

```
capa/
├── infrastructure/              # [DevOps] 인프라 영역 (Terraform + Helm)
│   ├── helm-values/             # Helm Chart 설정
│   │   ├── airflow.yaml
│   │   └── vanna.yaml
│   │
│   └── terraform/
│       ├── modules/             # 재사용 가능한 Terraform 모듈
│       │   ├── kinesis/         # Kin esis Stream + Firehose
│       │   ├── s3/              # S3 Bucket + Lifecycle
│       │   ├── glue/            # Glue Catalog + Tables
│       │   ├── eks/             # EKS Cluster
│       │   └── iam/             # IAM Roles (IRSA)
│       │
│       └── environments/dev/    # 환경별 설정 (dev/staging/prod)
│           ├── base/            # [Layer 1] AWS 인프라
│           │   ├── main.tf      # VPC, EKS, Kinesis, S3, Glue
│           │   ├── outputs.tf   # cluster_endpoint, cluster_name 등
│           │   └── providers.tf # AWS Provider만 사용
│           │
│           └── apps/            # [Layer 2] K8s 애플리케이션
│               ├── main.tf      # Helm Release (Airflow, Vanna)
│               ├── data.tf      # base의 EKS 정보 참조
│               └── providers.tf # Helm/K8s Provider 설정
│
├── services/                    # [Developer] 애플리케이션 영역
│   ├── log-generator/           # 로그 생성기
│   │   ├── src/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── airflow-dags/            # Airflow DAGs
│   │   ├── dags/
│   │   ├── plugins/
│   │   └── README.md
│   │
│   ├── slack-bot/               # Slack Bot
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── vanna-api/               # Vanna AI API
│       ├── src/
│       ├── Dockerfile
│       └── pyproject.toml
│
├── .github/workflows/           # [DevOps] CI/CD 파이프라인
│   ├── deploy-base.yaml         # Layer 1 배포 (EKS, Kinesis 등)
│   └── deploy-apps.yaml         # Layer 2 배포 (Helm Charts)
│
├── docs/                        # 프로젝트 문서
└── README.md
```

> **참고**: 계층 분리(Base/Apps) 개념과 배포 순서는 [Dev Ops Implementation Guide](./devops/devops_implementation_guide.md)를 참조하세요.

---

## 11. 팀 커뮤니케이션 규칙

### 11.1 일일 스탠드업
- **시간**: 매일 오전 10시
- **형식**: 어제 완료 / 오늘 계획 / 블로커
- **도구**: Slack #capa-standup

### 11.2 코드 리뷰
- **규칙**: 모든 PR은 최소 1명 이상 리뷰 필수
- **체크리스트**:
  - [ ] 테스트 코드 포함
  - [ ] 환경 변수 `.env.example`에 추가
  - [ ] README 업데이트 (필요 시)

### 11.3 Issue Tracking
- **Labels**:
  - `backend`, `data`, `ml`, `devops`
  - `P0-critical`, `P1-high`, `P2-medium`, `P3-low`
  - `bug`, `feature`, `docs`

---

## 12. 참고 자료

- [Vanna AI 공식 문서](https://vanna.ai/docs)
- [Slack Bolt Python SDK](https://slack.dev/bolt-python/)
- [AWS Kinesis Developer Guide](https://docs.aws.amazon.com/kinesis/)
- [Prophet 시계열 예측](https://facebook.github.io/prophet/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
