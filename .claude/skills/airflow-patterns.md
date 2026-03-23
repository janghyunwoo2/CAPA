# .claude/skills/airflow-patterns.md

---
name: airflow-patterns
description: CAPA Airflow DAG 작성 전문가
triggers: ["DAG", "airflow", "태스크", "schedule", "task"]
---

## 역할

CAPA 프로젝트에서 Airflow DAG을 작성할 때 이 규칙을 자동으로 적용합니다.

## CAPA DAG 필수 규칙

### 1. default_args 템플릿

```python
from datetime import datetime, timedelta

default_args = {
    "owner": "capa-team",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["capa-team@company.com"],
}
```

### 2. DAG 기본 설정

```python
with DAG(
    dag_id="capa_daily_report",  # snake_case
    default_args=default_args,
    schedule_interval="0 9 * * *",  # 한국 시간 오전 9시 (UTC+9 고려)
    catchup=False,  # 반드시 False
    tags=["capa", "report"],
) as dag:
    pass
```

### 3. Task 명명 규칙

- **snake_case** 필수
- **동사로 시작** (extract, load, transform, validate, send)
- 명확한 목적 표현

✅ 올바른 예:
- `extract_raw_logs`
- `transform_to_parquet`
- `load_to_athena`
- `send_slack_notification`

❌ 잘못된 예:
- `load-to-s3` (하이픈 금지)
- `task1` (동사 없음)
- `DataProcessing` (카멜케이스 금지)

### 4. 에러 핸들링 패턴

```python
from airflow.operators.python import PythonOperator
from airflow.utils.decorators import apply_defaults

def safe_task_func(**context):
    try:
        # 작업 로직
        pass
    except Exception as e:
        logger.error(f"Task 실패: {e}")
        raise
```

### 5. 로깅 규칙

```python
import logging

logger = logging.getLogger(__name__)

# ✅ 올바른 예
logger.info("데이터 추출 시작")
logger.error(f"처리 실패: {e}")

# ❌ 금지
print("데이터 추출 시작")  # print() 금지
```

## 금지 사항

| 항목 | 이유 |
|------|------|
| `catchup=True` | 과거 데이터 중복 처리 위험 |
| `latest` 태그 | 버전 불명확, 재현성 문제 |
| Task ID 한국어 | 로그/모니터링 혼동 |
| 전역 변수 | 병렬 처리 시 경쟁 조건 |
| print() | 로깅 시스템 우회 |

## Schedule Interval 예시

| 패턴 | 의미 | 용도 |
|------|------|------|
| `"0 9 * * *"` | 매일 오전 9시 | 일일 리포트 |
| `"0 */6 * * *"` | 6시간마다 | 주기적 동기화 |
| `"30 1 * * *"` | 매일 새벽 1시 30분 | 야간 배치 |
| `"0 9 * * MON"` | 매주 월요일 오전 9시 | 주간 리포트 |

## 참고 문서

- CAPA CLAUDE.md: 핵심 개발 원칙
- coding-rules.md: Python 타입 힌트, 에러 핸들링 규칙
