# Airflow DAG에 etl_summary_t2 패키지 통합 (2026-03-12)

## 요청 사항
- Airflow DAG에서 etl_summary_t2 패키지를 직접 사용하도록 수정
- 현재 DAG는 인식되지만 ETL이 작동하지 않는 문제 해결

## AS-IS (문제 상황)
### 문제점
1. **Athena 쿼리 직접 실행**: DAG에서 SQL 쿼리를 직접 정의하고 실행
2. **코드 중복**: etl_summary_t2 패키지의 로직을 DAG에서 다시 구현
3. **유지보수 어려움**: ETL 로직이 두 곳에 분산되어 있음

### 기존 코드 구조
```python
# DAG에서 직접 Athena 쿼리 정의
def _run_athena_query(database: str, output: str, region: str, **context):
    query = f"""
        CREATE TABLE {database}.{tmp_table} WITH (...) AS
        SELECT ... FROM impressions LEFT JOIN clicks ...
    """
    # Athena 쿼리 직접 실행
```

## TO-BE (해결 방안)
### 개선 사항
1. **etl_summary_t2 패키지 직접 사용**: HourlyETL, DailyETL 클래스 활용
2. **코드 통합**: ETL 로직은 패키지에서만 관리
3. **유지보수 용이**: 한 곳에서 ETL 로직 관리

### 변경된 코드 구조

#### 1. 03_ad_hourly_summary_test.py
```python
# 패키지 경로 추가
import sys
ETL_PACKAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'etl_summary_t2')
if ETL_PACKAGE_PATH not in sys.path:
    sys.path.insert(0, os.path.dirname(ETL_PACKAGE_PATH))

# HourlyETL 실행 함수
def _run_hourly_etl(**context):
    """etl_summary_t2의 HourlyETL 실행"""
    from etl_summary_t2.hourly_etl import HourlyETL
    
    # UTC → KST 변환
    dt_utc = context.get('data_interval_end')
    dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    
    # HourlyETL 실행
    etl = HourlyETL(target_hour=dt_kst)
    etl.run()

# PythonOperator 사용
create_hourly_summary = PythonOperator(
    task_id="create_hourly_summary",
    python_callable=_run_hourly_etl,
    provide_context=True,
)
```

#### 2. 04_ad_daily_summary_test.py
```python
# DailyETL 실행 함수
def _run_daily_etl(**context):
    """etl_summary_t2의 DailyETL 실행"""
    from etl_summary_t2.daily_etl import DailyETL
    
    # UTC → KST 변환 후 전날 날짜 계산
    dt_utc = context.get('data_interval_end')
    dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    target_date = dt_kst.subtract(days=1).date()
    
    # DailyETL 실행
    etl = DailyETL(target_date=target_date)
    etl.run()

# PythonOperator 사용
create_daily_summary = PythonOperator(
    task_id="create_daily_summary",
    python_callable=_run_daily_etl,
    provide_context=True,
)
```

## 주요 변경 사항
1. **sys.path 추가**: etl_summary_t2 패키지를 import할 수 있도록 경로 추가
2. **_run_hourly_etl, _run_daily_etl 함수**: 패키지의 ETL 클래스 직접 실행
3. **시간대 처리**: Airflow의 UTC 시간을 KST로 변환하여 처리
4. **provide_context=True**: Airflow context를 함수에 전달

## 필수 환경 설정
### AWS Credentials
etl_summary_t2 패키지는 AWS 자격증명이 필요합니다:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Airflow에서 설정 방법:
1. **환경변수**: Airflow 실행 환경에 설정
2. **Airflow Connection**: aws_default connection 사용
3. **K8s Secret**: KubernetesPodOperator 사용 시

## 장점
1. **단일 소스**: ETL 로직이 etl_summary_t2 패키지에만 존재
2. **재사용성**: 동일한 ETL 코드를 Airflow, 로컬, 다른 환경에서 사용 가능
3. **테스트 용이**: ETL 로직을 독립적으로 테스트 가능
4. **유지보수**: 한 곳에서만 코드 수정

## 주의사항
1. **패키지 설치**: Airflow 환경에 etl_summary_t2의 의존성 패키지 설치 필요
   ```bash
   pip install pyathena pandas pyarrow boto3 python-dotenv
   ```
2. **경로 설정**: DAG 파일이 etl_summary_t2 패키지를 찾을 수 있도록 경로 설정
3. **AWS 권한**: Athena, S3 접근 권한 필요