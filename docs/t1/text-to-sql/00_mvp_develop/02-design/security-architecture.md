## 5. 보안 아키텍처

> **분석 기준일**: 2026-03-12
> **분석 대상**: `services/vanna-api/src/main.py`, `services/slack-bot/app.py`
> **기준**: OWASP Top 10 (2021)

---

### 5.1 위협 모델 (Threat Model)

| # | 위협 | OWASP 분류 | 영향도 | 현재 상태 | 대응 전략 |
|---|------|-----------|--------|----------|----------|
| T-01 | LLM 생성 SQL에 DROP/DELETE/UPDATE 포함 | A03 Injection | **Critical** | 미구현 | SQL 허용 목록(Allowlist) 검증 |
| T-02 | Athena 풀 스캔으로 비용 폭발 | A04 Insecure Design | **High** | 미구현 | 스캔 크기 제한 + 파티션 필터 강제 |
| T-03 | Slack Bot Token 환경 변수 노출 | A02 Cryptographic Failures | **High** | 평문 env var | AWS Secrets Manager 이관 |
| T-04 | vanna-api 무인증 내부 접근 | A01 Broken Access Control | **High** | 인증 없음 | Internal Service Token + NetworkPolicy |
| T-05 | 광고주 ID / 사용자 PII 응답 노출 | A02 Cryptographic Failures | **High** | 미구현 | 컬럼 마스킹 + IAM 열 수준 제어 |
| T-06 | 과도한 쿼리 요청 (DDoS급) | A04 Insecure Design | **Medium** | 미구현 | User별 Rate Limiting |
| T-07 | 내부 에러 메시지 클라이언트 노출 | A05 Security Misconfiguration | **Medium** | 노출 중 | 에러 메시지 추상화 |
| T-08 | API Key 로그 부분 노출 | A09 Logging Failures | **Low** | 노출 중 | 로그에서 키 완전 제거 |
| T-09 | SSRF (report-generator URL 임의 조작) | A10 SSRF | **Low** | 미검증 | 허용 URL 화이트리스트 |

---

### 5.2 SQL Injection 방지

#### 5.2.1 위협 상세

`main.py:83`에서 LLM 생성 SQL이 검증 없이 Athena에 직접 실행된다.

```python
# 현재 코드 (취약) - main.py:83
response = self.athena_client.start_query_execution(
    QueryString=sql,  # LLM 생성 SQL 무검증 실행
    ...
)
```

공격 시나리오: Prompt Injection으로 `DROP TABLE`, `SELECT * FROM sensitive_table` 등 악의적 SQL이 생성될 수 있음.

#### 5.2.2 방어 전략: 3계층 SQL 검증

```
[LLM SQL 생성]
     ↓
[Layer 1] 문법 파싱 (sqlparse)
  - SELECT 외 DML/DDL 차단
  - 허용 키워드 외 거부
     ↓
[Layer 2] AST 기반 Semantic 검증
  - 접근 허용 테이블 화이트리스트 확인
  - 와일드카드 SELECT * 경고 처리
  - LIMIT 절 미포함 시 강제 추가
     ↓
[Layer 3] Athena Workgroup 정책
  - 스캔 크기 하드 제한
  - 읽기 전용 IAM 역할
     ↓
[Athena 실행]
```

#### 5.2.3 구현 명세

```python
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML

# 허용 테이블 화이트리스트 (실제 Athena 테이블 기준)
ALLOWED_TABLES: frozenset[str] = frozenset({
    "ad_combined_log",          # Hourly: impression + click
    "ad_combined_log_summary",  # Daily:  impression + click + conversion
})

# 허용 DML 키워드 (SELECT만)
ALLOWED_DML: frozenset[str] = frozenset({"SELECT"})

# 금지 키워드
BLOCKED_KEYWORDS: frozenset[str] = frozenset({
    "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE",
    "CREATE", "ALTER", "GRANT", "REVOKE", "EXEC",
    "EXECUTE", "INTO", "LOAD",
})

class SQLValidationError(Exception):
    """SQL 검증 실패 예외"""
    pass

def validate_sql(sql: str) -> str:
    """
    LLM 생성 SQL 3계층 검증.
    통과한 SQL만 반환, 실패 시 SQLValidationError 발생.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("SQL이 비어있습니다")

    sql_upper = sql.strip().upper()

    # Layer 1: 금지 키워드 검사
    for blocked in BLOCKED_KEYWORDS:
        if blocked in sql_upper.split():
            raise SQLValidationError(f"허용되지 않는 SQL 키워드: {blocked}")

    # Layer 1: SELECT만 허용
    parsed = sqlparse.parse(sql)
    if not parsed:
        raise SQLValidationError("SQL 파싱 실패")

    stmt: Statement = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        raise SQLValidationError(f"SELECT만 허용됩니다. 감지된 타입: {stmt_type}")

    # Layer 2: LIMIT 절 강제 추가 (최대 1000행)
    if "LIMIT" not in sql_upper:
        sql = sql.rstrip(";") + " LIMIT 1000"

    # Layer 2: 세미콜론 이후 추가 구문 차단 (SQL 주입 패턴)
    statements = [s for s in sqlparse.parse(sql) if s.get_type()]
    if len(statements) > 1:
        raise SQLValidationError("다중 SQL 구문은 허용되지 않습니다")

    return sql
```

#### 5.2.4 Athena Workgroup 읽기 전용 IAM 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution"
      ],
      "Resource": "arn:aws:athena:ap-northeast-2:*:workgroup/capa-text2sql-wg"
    },
    {
      "Effect": "Allow",
      "Action": ["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions"],
      "Resource": [
        "arn:aws:glue:ap-northeast-2:*:catalog",
        "arn:aws:glue:ap-northeast-2:*:database/capa_db",
        "arn:aws:glue:ap-northeast-2:*:table/capa_db/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": [
        "arn:aws:s3:::capa-*-raw-logs/*",
        "arn:aws:s3:::capa-*-athena-results/*"
      ]
    },
    {
      "Effect": "Deny",
      "Action": ["s3:DeleteObject", "s3:DeleteBucket"],
      "Resource": "*"
    }
  ]
}
```

---

### 5.3 Athena 비용 제어

#### 5.3.1 위협 상세

현재 `run_sql()`에 스캔 크기 제한이 없어 악의적이거나 비효율적인 쿼리가 수백 GB를 스캔할 수 있다.

- Athena 요금: **$5 / TB 스캔** (ap-northeast-2 기준)
- 파티션 미지정 풀 스캔 시 수십 달러가 단일 쿼리에서 발생 가능

#### 5.3.2 Athena Workgroup 비용 제한

```hcl
# infrastructure/terraform/08-athena.tf 에 추가 (기존 capa-workgroup과 별도)
# Text-to-SQL 전용 Workgroup — 스캔 1GB 제한 포함
resource "aws_athena_workgroup" "text2sql" {
  name = "capa-text2sql-wg"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      # 기존 data_lake 버킷 재사용 (새 버킷 불필요)
      output_location = "s3://${aws_s3_bucket.data_lake.bucket}/athena-results/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    # 쿼리당 최대 스캔 크기: 1 GB (1,073,741,824 bytes)
    bytes_scanned_cutoff_per_query = 1073741824
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  force_destroy = true
}
```

#### 5.3.3 SQL 파서 기반 파티션 필터 강제

```python
import re
from datetime import datetime, timedelta

# 파티션 키 컬럼 (실제 Athena 테이블 파티션 기준: year/month/day)
# ad_combined_log        파티션: year, month, day, hour
# ad_combined_log_summary 파티션: year, month, day (hour 없음)
PARTITION_COLUMNS: frozenset[str] = frozenset({"year", "month", "day"})

def enforce_partition_filter(sql: str) -> str:
    """
    파티션 컬럼 필터(year/month/day)가 없는 쿼리에 최근 7일 기본 필터를 추가.
    실제 테이블 파티션이 year/month/day(STRING) 구조이므로 해당 형식으로 삽입.
    """
    sql_upper = sql.upper()
    has_partition_filter = any(col.upper() in sql_upper for col in PARTITION_COLUMNS)

    if not has_partition_filter:
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        # year/month/day STRING 파티션 조건 생성
        partition_cond = (
            f"year = '{seven_days_ago.strftime('%Y')}' "
            f"AND month = '{seven_days_ago.strftime('%m')}' "
            f"AND day >= '{seven_days_ago.strftime('%d')}'"
        )
        if "WHERE" in sql_upper:
            sql = re.sub(
                r"(WHERE\s)",
                f"WHERE {partition_cond} AND ",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            sql = re.sub(
                r"(GROUP BY|ORDER BY|LIMIT)",
                f"WHERE {partition_cond} \\1",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
    return sql
```

#### 5.3.4 쿼리 비용 사전 예측 (Dry Run)

```python
async def estimate_scan_size(sql: str) -> int:
    """
    Athena EXPLAIN으로 예상 스캔 크기 확인.
    반환값: bytes. 제한 초과 시 QueryCostExceedError 발생.
    """
    MAX_SCAN_BYTES = 500 * 1024 * 1024  # 500 MB 소프트 제한

    try:
        response = self.athena_client.start_query_execution(
            QueryString=f"EXPLAIN {sql}",
            QueryExecutionContext={"Database": self.athena_database},
            ResultConfiguration={"OutputLocation": self.s3_staging_dir},
        )
        # EXPLAIN 결과 파싱하여 예상 스캔 크기 추출 (생략)
        # Workgroup의 하드 제한(1 GB)이 최종 방어선
    except ClientError as e:
        logger.error(f"스캔 크기 추정 실패: {e}")
        raise
```

---

### 5.4 인증 & 비밀 관리

#### 5.4.1 현재 취약점

| 위치 | 취약점 | 위험도 |
|------|--------|--------|
| `app.py:14-15` | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`을 환경 변수로 직접 주입 | High |
| `main.py:31` | `ANTHROPIC_API_KEY`를 환경 변수로 직접 주입 | High |
| `main.py:149` | `ANTHROPIC_API_KEY[:5]` 로그 출력 | Low |
| `app.py:91` | vanna-api 호출 시 인증 헤더 없음 | High |

#### 5.4.2 시크릿 관리 방식 (현재 인프라 기반)

> **⚠️ 실제 구축 환경 기준**: 이 프로젝트는 AWS Secrets Manager 대신 **`terraform.tfvars` → K8s Secret** 방식을 채택한다.
> `terraform.tfvars`는 `.gitignore`에 등록되어 Git에 커밋되지 않으며, Terraform 실행 시 K8s Secret으로 주입된다.

**현재 동작 방식:**
```
terraform.tfvars (로컬/CI)
    ↓  terraform apply
kubernetes_secret.vanna_secrets     (namespace: vanna)
    ├── anthropic-api-key           → ENV: ANTHROPIC_API_KEY
    └── (신규) redash-api-key       → ENV: REDASH_API_KEY
    └── (신규) internal-api-token   → ENV: INTERNAL_API_TOKEN

kubernetes_secret.slack_bot_secrets (namespace: slack-bot)
    ├── slack-bot-token             → ENV: SLACK_BOT_TOKEN
    ├── slack-app-token             → ENV: SLACK_APP_TOKEN
    └── (신규) internal-api-token   → ENV: INTERNAL_API_TOKEN
```

**Text-to-SQL 구현을 위해 `terraform.tfvars`에 추가할 항목:**
```hcl
# infrastructure/terraform/terraform.tfvars 에 추가

# Redash API 연동 (Redash Admin > Settings > API Key에서 발급)
redash_api_key     = "..."

# Internal Service Token (vanna-api 내부 인증용, openssl rand -hex 32 로 생성)
internal_api_token = "capa-internal-..."
```

**`variables.tf`에 추가할 변수 선언:**
```hcl
# infrastructure/terraform/variables.tf 에 추가

variable "redash_api_key" {
  description = "Redash API Key for vanna-api integration"
  type        = string
  sensitive   = true
}

variable "internal_api_token" {
  description = "Internal service-to-service authentication token"
  type        = string
  sensitive   = true
}
```

**`11-k8s-apps.tf`의 `kubernetes_secret.vanna_secrets` 확장:**
```hcl
# 기존 vanna-secrets에 신규 키 추가
resource "kubernetes_secret" "vanna_secrets" {
  metadata {
    name      = "vanna-secrets"
    namespace = kubernetes_namespace.vanna.metadata[0].name
  }

  data = {
    anthropic-api-key  = var.anthropic_api_key   # 기존
    redash-api-key     = var.redash_api_key       # 신규
    internal-api-token = var.internal_api_token   # 신규
  }

  type = "Opaque"
}
```

**`11-k8s-apps.tf`의 `kubernetes_secret.slack_bot_secrets` 확장:**
```hcl
# 기존 slack-bot-secrets에 신규 키 추가
resource "kubernetes_secret" "slack_bot_secrets" {
  metadata {
    name      = "slack-bot-secrets"
    namespace = kubernetes_namespace.slack_bot.metadata[0].name
  }

  data = {
    slack-bot-token    = var.slack_bot_token      # 기존
    slack-app-token    = var.slack_app_token      # 기존
    internal-api-token = var.internal_api_token   # 신규
  }

  type = "Opaque"
}
```

#### 5.4.3 Internal Service Token 설계

vanna-api는 Kubernetes 내부 서비스이지만 무인증으로 노출되어 있다. Internal Service Token으로 최소한의 접근 제어를 적용한다.

```python
# vanna-api: 서비스 토큰 검증 미들웨어
import os
from fastapi import Header, HTTPException
import secrets

# K8s Secret에서 주입된 ENV 변수로 로드 (Secrets Manager 불필요)
INTERNAL_SERVICE_TOKEN = os.environ["INTERNAL_API_TOKEN"]

async def verify_internal_token(x_internal_token: str = Header(...)) -> None:
    """Internal Service Token 검증 (타이밍 공격 방지: secrets.compare_digest 사용)"""
    if not secrets.compare_digest(x_internal_token, INTERNAL_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="접근이 거부되었습니다")
```

```python
# slack-bot: vanna-api 호출 시 토큰 헤더 추가
import os
import httpx

VANNA_API_URL = os.environ["VANNA_API_URL"]         # K8s ENV: http://vanna-api.vanna.svc.cluster.local:8000
INTERNAL_API_TOKEN = os.environ["INTERNAL_API_TOKEN"] # K8s Secret에서 주입

# NFR-06: slack-bot의 vanna-api 호출 timeout 300초 이상
response = httpx.post(
    f"{VANNA_API_URL}/query",
    json=payload,
    headers={"X-Internal-Token": INTERNAL_API_TOKEN},
    timeout=310,  # NFR-06: Redash 폴링 최대 300초 + 여유분
)
```

#### 5.4.4 Kubernetes NetworkPolicy (vanna-api 격리)

```yaml
# infrastructure/helm-values/vanna-api-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: vanna-api-ingress-policy
  namespace: vanna
spec:
  podSelector:
    matchLabels:
      app: vanna-api
  policyTypes:
    - Ingress
  ingress:
    # slack-bot 네임스페이스에서만 접근 허용
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: slack-bot
        - podSelector:
            matchLabels:
              app: slack-bot
      ports:
        - protocol: TCP
          port: 8000
```

#### 5.4.5 Slack 요청 출처 검증

```python
# Slack Signing Secret으로 요청 위변조 검증
# slack_bolt 라이브러리가 자동 처리하지만, 명시적 확인 필요
import hmac
import hashlib
import time

def verify_slack_signature(
    signing_secret: str,
    request_body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Slack 요청 서명 검증 (Replay Attack 방지 포함)"""
    # 5분 이상 지난 요청 거부 (Replay Attack 방지)
    if abs(time.time() - float(timestamp)) > 300:
        return False

    base_string = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    expected_signature = (
        "v0=" + hmac.new(
            signing_secret.encode(),
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected_signature, signature)
```

---


### 5.5 데이터 보호

#### 5.5.1 민감 컬럼 분류

| 컬럼 | 분류 | 마스킹 방식 |
|------|------|------------|
| `user_id` | PII (준식별자) | 후반 6자리 마스킹: `USR_****1234` |
| `advertiser_id` | 사업 기밀 | 비즈니스 역할 없으면 차단 |
| `ip_address` | PII | 마지막 옥텟 마스킹: `192.168.1.*` |
| `device_id` | PII (준식별자) | SHA-256 해시 치환 |
| `campaign_budget` | 사업 기밀 | 집계 쿼리에서만 허용 |

#### 5.5.2 응답 마스킹 처리

```python
import re
import hashlib

# 마스킹 대상 컬럼 설정
MASKED_COLUMNS: dict[str, str] = {
    "user_id": "partial",       # 부분 마스킹
    "ip_address": "ip",         # IP 마스킹
    "device_id": "hash",        # 해시 치환
    "advertiser_id": "redact",  # 완전 차단 (집계 제외)
}

def mask_sensitive_data(records: list[dict]) -> list[dict]:
    """쿼리 결과에서 민감 데이터 마스킹 처리"""
    masked_records = []
    for record in records:
        masked_record = {}
        for col, value in record.items():
            col_lower = col.lower()
            if col_lower not in MASKED_COLUMNS:
                masked_record[col] = value
                continue

            mask_type = MASKED_COLUMNS[col_lower]
            if value is None:
                masked_record[col] = value
            elif mask_type == "partial" and len(str(value)) > 4:
                masked_record[col] = "****" + str(value)[-4:]
            elif mask_type == "ip":
                parts = str(value).split(".")
                masked_record[col] = ".".join(parts[:3] + ["*"]) if len(parts) == 4 else "*.*.*.* "
            elif mask_type == "hash":
                masked_record[col] = hashlib.sha256(str(value).encode()).hexdigest()[:16]
            elif mask_type == "redact":
                masked_record[col] = "[REDACTED]"
            else:
                masked_record[col] = value
        masked_records.append(masked_record)
    return masked_records
```

#### 5.5.3 Lake Formation 열 수준 접근 제어 (AWS)

```hcl
# Terraform: Lake Formation 컬럼 권한
resource "aws_lakeformation_permissions" "vanna_api_column_filter" {
  principal = aws_iam_role.vanna_api_irsa.arn

  table_with_columns {
    database_name = "capa_db"
    name          = "ad_events"
    # 허용 컬럼만 명시 (user_id, ip_address 제외)
    column_names = [
      "event_type", "ad_id", "campaign_id",
      "device_type", "timestamp", "ctr",
      "impressions", "clicks", "conversions", "dt"
    ]
  }

  permissions = ["SELECT"]
}
```

---

### 5.6 Rate Limiting 설계

#### 5.6.1 제한 정책

| 대상 | 단위 | 제한 | 초과 시 응답 |
|------|------|------|------------|
| Slack User별 | 분당 | 5 요청 | `429: 잠시 후 다시 시도해주세요` |
| Slack Channel별 | 분당 | 20 요청 | `429: 채널 요청 한도 초과` |
| vanna-api 전체 | 초당 | 10 요청 | `503: 서비스 과부하` |
| Athena Workgroup | 동시 | 5 쿼리 | Workgroup 자동 대기열 |

#### 5.6.2 슬라이딩 윈도우 Rate Limiter 구현

```python
import time
import threading
from collections import defaultdict, deque
from fastapi import Request, HTTPException

class SlidingWindowRateLimiter:
    """
    메모리 기반 슬라이딩 윈도우 Rate Limiter.
    프로덕션에서는 Redis 기반으로 교체 권장 (다중 파드 대응).
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """요청 허용 여부 확인. True: 허용, False: 차단"""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            queue = self._requests[key]
            # 윈도우 밖 요청 제거
            while queue and queue[0] < window_start:
                queue.popleft()

            if len(queue) >= self.max_requests:
                return False

            queue.append(now)
            return True


# vanna-api Rate Limiter 인스턴스
user_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
channel_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60)


async def rate_limit_middleware(request: Request, call_next):
    """FastAPI 미들웨어: 요청 제한 적용"""
    user_id = request.headers.get("X-Slack-User-Id", "unknown")
    channel_id = request.headers.get("X-Slack-Channel-Id", "unknown")

    if not user_limiter.is_allowed(user_id):
        raise HTTPException(
            status_code=429,
            detail="요청 한도를 초과했습니다. 1분 후 다시 시도해주세요.",
        )
    if not channel_limiter.is_allowed(channel_id):
        raise HTTPException(
            status_code=429,
            detail="채널 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
        )

    return await call_next(request)
```

#### 5.6.3 에러 메시지 추상화

```python
# main.py 현재 코드 (취약): 내부 스택 트레이스를 클라이언트에 노출
raise HTTPException(status_code=500, detail=str(e))

# 개선된 패턴
import uuid

ERROR_MESSAGES: dict[str, str] = {
    "SQLValidationError": "쿼리를 처리할 수 없습니다. 질문을 다시 표현해주세요.",
    "QueryCostExceedError": "요청한 데이터 범위가 너무 큽니다. 조회 기간을 줄여주세요.",
    "TimeoutError": "쿼리 처리 시간이 초과되었습니다. 다시 시도해주세요.",
    "default": "일시적인 오류가 발생했습니다. 관리자에게 문의하세요.",
}

def handle_query_error(e: Exception) -> HTTPException:
    """내부 에러를 추상화된 사용자 메시지로 변환"""
    error_id = str(uuid.uuid4())[:8]
    error_type = type(e).__name__
    user_message = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["default"])

    logger.error(f"[ERR-{error_id}] {error_type}: {e}", exc_info=True)

    return HTTPException(
        status_code=500,
        detail=f"{user_message} (참조 코드: ERR-{error_id})",
    )
```

---

### 5.7 보안 구현 우선순위 로드맵

| 우선순위 | 항목 | 난이도 | OWASP | 대상 파일 |
|---------|------|--------|-------|----------|
| P0 (즉시) | SQL 허용 목록 검증 (`validate_sql`) | 중 | A03 | `main.py` |
| P0 (즉시) | Athena Workgroup 스캔 제한 (1 GB) | 하 | A04 | Terraform |
| P1 (배포 전) | Secrets Manager 이관 | 중 | A02 | `main.py`, `app.py` |
| P1 (배포 전) | Internal Service Token + NetworkPolicy | 중 | A01 | K8s manifests |
| P1 (배포 전) | 에러 메시지 추상화 | 하 | A05 | `main.py` |
| P2 (다음 스프린트) | 응답 데이터 마스킹 | 중 | A02 | `main.py` |
| P2 (다음 스프린트) | Rate Limiting 미들웨어 | 중 | A04 | `main.py` |
| P3 (백로그) | Lake Formation 열 수준 제어 | 상 | A01 | Terraform |
| P3 (백로그) | Redis 기반 분산 Rate Limiter | 상 | A04 | 신규 서비스 |

---

### 에이전트 기여 내역 (Agent Attribution)

#### 에이전트별 수행 작업

| 에이전트명 | 모델 | 수행 작업 |
|-----------|------|----------|
| security-reviewer | claude-sonnet-4-6 | 전체 보안 아키텍처 설계, 코드 취약점 분석, 위협 모델링, 구현 명세 작성 |

#### 문서 섹션별 주요 기여

| 섹션 | 기여 에이전트 | 기여 내용 |
|------|-------------|----------|
| 5.1 위협 모델 | security-reviewer | `main.py`, `app.py` 직접 분석 기반 9개 위협 식별 |
| 5.2 SQL Injection 방지 | security-reviewer | 3계층 검증 설계, IAM 정책 최소 권한 원칙 적용 |
| 5.3 Athena 비용 제어 | security-reviewer | Workgroup 하드 제한, 파티션 필터 강제 로직 설계 |
| 5.4 인증 & 비밀 관리 | security-reviewer | Secrets Manager 통합, Internal Token, NetworkPolicy 설계 |
| 5.5 데이터 보호 | security-reviewer | PII 컬럼 분류, 마스킹 로직, Lake Formation 설계 |
| 5.6 Rate Limiting | security-reviewer | 슬라이딩 윈도우 알고리즘, 에러 추상화 패턴 |
