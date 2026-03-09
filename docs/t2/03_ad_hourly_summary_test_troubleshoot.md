# Airflow 테스트 DAG 트러블슈팅 가이드

> `03_ad_hourly_summary_test.py` / `04_ad_daily_summary_test.py` DAG가 Airflow에서 인식은 되지만, 데이터에 접근하지 못하는 문제 분석

---

## 한줄 요약

> **테스트 DAG(`*_test.py`)과 정상 작동하는 ETL 스크립트(`etl_summary_t2/`)는 "데이터베이스 이름", "테이블 이름", "S3 경로", "Jinja 템플릿 렌더링 방식"이 모두 다릅니다.**
> DAG는 인식되지만 실행 시 Athena가 데이터를 찾지 못하는 이유가 여기에 있습니다.

---

## 문제 상황

| 구분 | 상태 |
|------|------|
| `03_ad_hourly_summary_test.py` | Airflow에서 DAG 인식 ✅ → 실행 시 데이터 접근 실패 ❌ |
| `04_ad_daily_summary_test.py` | Airflow에서 DAG 인식 ✅ → 실행 시 데이터 접근 실패 ❌ |
| `etl_summary_t2/hourly_etl.py` | 정상 작동 ✅ |
| `etl_summary_t2/daily_etl.py` | 정상 작동 ✅ |

---

## 발견된 문제점 (총 5가지)

### 문제 1: 데이터베이스 이름 불일치 (가장 핵심)

가장 큰 원인입니다. 두 곳에서 서로 다른 데이터베이스 이름을 사용하고 있습니다.

| 구분 | 데이터베이스 이름 | 파일 위치 |
|------|-------------------|-----------|
| 테스트 DAG | `ad_log` | `dags/03_ad_hourly_summary_test.py` 15행 |
| 정상 ETL | `capa_ad_logs` | `etl_summary_t2/config.py` 35행 |

```python
# ❌ 테스트 DAG (dags/03_ad_hourly_summary_test.py:15)
DATABASE = "ad_log"

# ✅ 정상 작동하는 ETL (etl_summary_t2/config.py:35)
DATABASE = "capa_ad_logs"
```

💡 **왜 문제인가?**
- Athena에서 `ad_log.ad_events_raw` 라는 테이블을 찾으려고 하는데
- 실제 데이터는 `capa_ad_logs` 데이터베이스에 있음
- → "테이블이 없다" 또는 "데이터가 0건" 에러 발생

---

### 문제 2: 테이블 이름 불일치

테스트 DAG와 정상 ETL이 참조하는 원본 테이블 이름이 다릅니다.

| 구분 | 원본 테이블 | 결과 테이블 |
|------|-------------|-------------|
| 테스트 DAG | `ad_events_raw` (하나의 통합 테이블) | `ad_hourly_summary` |
| 정상 ETL | `impressions` + `clicks` (별도 테이블) | `ad_combined_log` |

```python
# ❌ 테스트 DAG - ad_events_raw 하나로 self-join
FROM ad_log.ad_events_raw AS imp
LEFT JOIN ad_log.ad_events_raw AS clk
  ON imp.campaign_id = clk.campaign_id ...
  AND clk.event_type = 'click'
WHERE imp.event_type = 'impression'

# ✅ 정상 ETL - impressions, clicks 별도 테이블로 join
FROM capa_ad_logs.impressions imp
LEFT JOIN capa_ad_logs.clicks clk
  ON imp.impression_id = clk.impression_id
```

💡 **왜 문제인가?**
- `ad_events_raw` 테이블이 Athena/Glue Catalog에 등록되어 있지 않을 수 있음
- 또는 등록되어 있더라도, `ad_log` 데이터베이스가 아닌 `capa_ad_logs`에 있을 수 있음

---

### 문제 3: S3 경로 구조 불일치

데이터의 S3 저장 경로가 다릅니다.

| 구분 | S3 경로 |
|------|---------|
| 테스트 DAG | `s3://capa-data-lake-.../summary/ad_hourly_summary/dt=YYYY-MM-DD-HH/` |
| 정상 ETL | `s3://capa-data-lake-.../summary/ad_combined_log/dt=YYYY-MM-DD-HH/` |

```python
# ❌ 테스트 DAG
HOURLY_SUMMARY_PATH = f"s3://{S3_BUCKET}/summary/ad_hourly_summary"
# 결과 → s3://capa-data-lake-.../summary/ad_hourly_summary/dt=2026-02-13-06/

# ✅ 정상 ETL
S3_PATHS["ad_combined_log"] = f"s3://{S3_BUCKET}/summary/ad_combined_log/"
# 결과 → s3://capa-data-lake-.../summary/ad_combined_log/dt=2026-02-13-06/
```

💡 **왜 문제인가?**
- 정상 ETL이 만든 데이터는 `ad_combined_log/` 경로에 있음
- 테스트 DAG는 `ad_hourly_summary/` 경로를 기대함
- → Athena가 데이터를 찾을 수 없음

---

### 문제 4: Jinja 템플릿이 PythonOperator에서 렌더링되지 않을 수 있음

이것이 **로컬 Docker Compose 환경에서의 실제 실행 실패 원인**입니다.

```python
# 테스트 DAG의 PythonOperator (else 분기)
create_hourly_summary = PythonOperator(
    task_id="create_hourly_summary",
    python_callable=_run_athena_query,
    op_kwargs={
        "query": (
            "CREATE TABLE {{ params.database }}.ad_hourly_summary_tmp ..."
            # ⚠️ op_kwargs의 값은 Jinja 렌더링이 되지만,
            # schedule=None + 수동 트리거 시 data_interval_end 값이 문제
        ),
    },
    params={"database": DATABASE, "summary_path": HOURLY_SUMMARY_PATH},
)
```

💡 **왜 문제인가?**

Airflow의 `PythonOperator`에서 `op_kwargs`는 Jinja 렌더링을 지원합니다.
하지만 `schedule=None`으로 **수동 트리거** 시:
- `data_interval_end`는 **트리거한 시점**으로 설정됨
- 해당 시점에 데이터가 없으면 결과가 **0건**
- 렌더링이 되더라도 `ad_log` 데이터베이스의 `ad_events_raw` 테이블을 참조 (문제 1, 2)

결과적으로 Athena에 보내지는 쿼리:
```sql
-- 렌더링 후에도 이렇게 됨 (잘못된 DB + 테이블)
CREATE TABLE ad_log.ad_hourly_summary_tmp ...
FROM ad_log.ad_events_raw ...
WHERE ... timestamp >= 1739408400000 AND timestamp < 1739412000000
-- → 데이터가 없는 시간 범위 + 잘못된 테이블
```

---

### 문제 5: 04 DAG의 ExternalTaskSensor가 영원히 대기

```python
# 04_ad_daily_summary_test.py
wait_for_hourly = ExternalTaskSensor(
    task_id="wait_for_hourly_summary",
    external_dag_id="ad_hourly_summary",    # ← "01_ad_hourly_summary"가 아님!
    external_task_id="register_partition",
    execution_delta=timedelta(hours=3),
    timeout=3600,
    mode="reschedule",
)
```

💡 **왜 문제인가?**
- `external_dag_id="ad_hourly_summary"` → 이 dag_id를 가진 DAG가 존재하지 않음
- → Sensor가 1시간(timeout=3600) 동안 기다리다 실패

실제 hourly DAG의 `dag_id`는 `"01_ad_hourly_summary"`:
```python
# 01_ad_hourly_summary.py
with DAG(dag_id="01_ad_hourly_summary", ...)
```

---

## 비교 요약표

| 항목 | 테스트 DAG (`*_test.py`) | 정상 ETL (`etl_summary_t2/`) |
|------|--------------------------|-------------------------------|
| **데이터베이스** | `ad_log` ❌ | `capa_ad_logs` ✅ |
| **원본 테이블** | `ad_events_raw` (통합) | `impressions` + `clicks` (분리) |
| **조인 키** | `campaign_id + user_id` | `impression_id` |
| **결과 테이블** | `ad_hourly_summary` | `ad_combined_log` |
| **결과 S3 경로** | `summary/ad_hourly_summary/` | `summary/ad_combined_log/` |
| **Athena 접근** | boto3 직접 호출 | `AthenaQueryExecutor` 클래스 |
| **설정 관리** | DAG 파일 내 하드코딩 | `config.py`에서 중앙 관리 |
| **AWS 인증** | 환경변수/IRSA 의존 | `.env` 파일 + 환경변수 |
| **파티션 형식** | `year/month/day` 컬럼 | `year/month/day/hour` 컬럼 |

---

## 해결 방법

### 방법 A: 빠른 수정 (데이터베이스/테이블만 맞추기)

테스트 DAG에서 데이터베이스 이름과 테이블 이름을 실제 환경에 맞게 수정합니다.

```python
# 03_ad_hourly_summary_test.py 수정
# 변경 전
DATABASE = "ad_log"

# 변경 후
DATABASE = "capa_ad_logs"
```

그리고 쿼리의 테이블 이름도 실제 존재하는 테이블로 변경:
```python
# 변경 전: ad_events_raw (통합 테이블)
FROM ad_log.ad_events_raw AS imp
LEFT JOIN ad_log.ad_events_raw AS clk

# 변경 후: impressions + clicks (분리 테이블, 실제 존재)
FROM capa_ad_logs.impressions AS imp
LEFT JOIN capa_ad_logs.clicks AS clk
  ON imp.impression_id = clk.impression_id
```

### 방법 B: 근본적 해결 (추천)

테스트 DAG가 `etl_summary_t2/config.py`의 설정값을 **공유**하도록 리팩토링합니다.

```python
# dags/03_ad_hourly_summary_test.py
import sys
sys.path.insert(0, '/opt/airflow/etl_summary_t2')  # Docker 볼륨 마운트 경로

from config import DATABASE, S3_PATHS, S3_BUCKET
```

또는 `.env` 파일에 공통 설정을 넣고 양쪽에서 읽기:
```bash
# .env
DATABASE=capa_ad_logs
S3_BUCKET=capa-data-lake-827913617635
```

### 방법 C: 04 DAG의 ExternalTaskSensor 수정

```python
# 변경 전
external_dag_id="ad_hourly_summary",

# 변경 후 (실제 dag_id에 맞게)
external_dag_id="03_ad_hourly_summary_test",
# 또는 테스트용이므로 sensor 자체를 제거
```

테스트 전용이므로 `ExternalTaskSensor` 자체를 제거하고 바로 daily summary를 실행하는 것도 방법입니다.

---

## 수정 전 확인 체크리스트

테스트 DAG를 수정하기 전에 아래 사항을 먼저 확인하세요:

### 1. Athena에서 실제 데이터베이스/테이블 확인
```sql
-- AWS 콘솔 → Athena → 쿼리 에디터에서 실행
SHOW DATABASES;
-- capa_ad_logs가 있는지 확인

SHOW TABLES IN capa_ad_logs;
-- impressions, clicks, conversions 등 테이블이 있는지 확인
```

### 2. S3에 실제 데이터가 있는지 확인
```bash
# AWS CLI로 확인
aws s3 ls s3://capa-data-lake-827913617635/raw/impressions/ --recursive | head -5
aws s3 ls s3://capa-data-lake-827913617635/summary/ad_combined_log/ --recursive | head -5
```

### 3. Airflow 환경에서 AWS 자격증명 확인
```bash
# Docker Compose Airflow worker 컨테이너에 접속
docker exec -it <airflow-worker-container> bash

# AWS 자격증명 확인
python3 -c "import boto3; client = boto3.client('sts'); print(client.get_caller_identity())"
```

---

## 전체 그림 (왜 이렇게 되었나?)

```
etl_summary_t2/        (먼저 개발됨 - 독립 실행형)
├── config.py          → DATABASE = "capa_ad_logs"
├── hourly_etl.py      → impressions + clicks → ad_combined_log
└── daily_etl.py       → ad_combined_log + conversions → ad_combined_log_summary

dags/                  (나중에 개발됨 - Airflow DAG)
├── 01, 02             → 스케줄 기반 프로덕션 DAG
└── 03, 04 (_test)     → 수동 테스트용 DAG
                         → DATABASE = "ad_log" (다른 이름!)
                         → ad_events_raw (다른 테이블!)
```

두 시스템이 **별도로 개발**되면서 설정값이 동기화되지 않은 것이 근본 원인입니다.

---

## 요약

| 문제 | 심각도 | 해결 난이도 |
|------|--------|------------|
| DATABASE 이름 불일치 (`ad_log` vs `capa_ad_logs`) | 🔴 높음 | 🟢 쉬움 (값 변경) |
| 테이블 이름 불일치 (`ad_events_raw` vs `impressions`+`clicks`) | 🔴 높음 | 🟡 보통 (쿼리 수정) |
| S3 경로 불일치 | 🟡 보통 | 🟢 쉬움 (경로 변경) |
| Jinja 렌더링 + 수동 트리거 시 data_interval | 🟡 보통 | 🟡 보통 (로직 수정) |
| ExternalTaskSensor dag_id 불일치 | 🔴 높음 | 🟢 쉬움 (dag_id 수정 또는 제거) |
다음 단계
- 필요 시 버전 C(개선된 문서 구조) 또는 버전 A로 확장 가능
