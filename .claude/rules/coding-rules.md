# 코딩 규칙 (Coding Rules)

## Python 규칙

### 타입 힌트 필수

```python
# ❌ 금지
def process_log(data):
    pass

# ✅ 올바른 예
from typing import Optional
def process_log(data: dict[str, str]) -> Optional[str]:
    pass
```

### 에러 핸들링 필수

```python
# ❌ 금지
async def send_to_kinesis(record: dict) -> None:
    client.put_record(...)

# ✅ 올바른 예
async def send_to_kinesis(record: dict[str, str]) -> None:
    try:
        await client.put_record(...)
    except ClientError as e:
        logger.error(f"Kinesis 전송 실패: {e}")
        raise
```

### 로깅 규칙

- `print()` 사용 금지. 반드시 `logging` 모듈을 사용한다.
- 로그 메시지는 **한국어**로 작성한다.

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Kinesis 스트림 전송 시작")
logger.error(f"데이터 파싱 실패: {e}")
```

### 데이터 모델

- 딕셔너리 대신 `dataclass` 또는 `pydantic BaseModel`을 사용한다.

```python
from pydantic import BaseModel

class AdLogEvent(BaseModel):
    event_type: str       # impression | click | conversion
    user_id: str
    ad_id: str
    timestamp: float
    device_type: str      # Android | iOS | Web | Tablet
```

---

## Terraform 규칙

### 리소스 명명 규칙

```hcl
# 패턴: capa-<환경>-<리소스명>
resource "aws_s3_bucket" "raw_logs" {
  bucket = "capa-${var.env}-raw-logs"
}
```

### 변수 필수 설명

```hcl
variable "env" {
  type        = string
  description = "배포 환경 (dev | prod)"
}
```

### 태그 필수 부착

```hcl
tags = {
  Project     = "CAPA"
  Environment = var.env
  ManagedBy   = "Terraform"
}
```

---

## Airflow DAG 규칙

### DAG 기본 설정

```python
from datetime import datetime, timedelta
from airflow import DAG

default_args = {
    "owner": "capa-team",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
}

with DAG(
    dag_id="capa_daily_report",
    default_args=default_args,
    schedule_interval="0 9 * * *",  # 한국 시간 오전 9시 (UTC+9 고려)
    catchup=False,
    tags=["capa", "report"],
) as dag:
    ...
```

### Task 명명 규칙

- `snake_case`를 사용한다.
- 동사로 시작하되 목적이 명확하게 드러나게 작성한다.
- 예: `extract_raw_logs`, `transform_to_parquet`, `load_to_athena`

---

## Docker / 컨테이너 규칙

- 베이스 이미지는 공식 `slim` 또는 `alpine` 버전을 사용한다.
- `latest` 태그 사용을 금지한다. 반드시 버전을 명시한다.
- `.dockerignore` 파일을 반드시 포함한다.

```dockerfile
# ❌ 금지
FROM python:latest

# ✅ 올바른 예
FROM python:3.11-slim
```

---

## 테스트 규칙

- 새 기능 추가 시 단위 테스트를 반드시 함께 작성한다.
- AWS 서비스 호출은 `moto` 라이브러리로 Mock 처리한다.
- 테스트 함수 명: `test_<기능>_<조건>_<기대결과>` 패턴 준수.

```python
def test_parse_impression_log_valid_input_returns_event():
    ...
```
