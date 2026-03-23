# Airflow DAG ETL Integration Guide

## 개요
이 문서는 Airflow DAG에서 etl_summary_t2 패키지를 사용하는 방법을 설명합니다.

## DAG 구조
- `03_ad_hourly_summary_test.py`: 시간별 ETL (HourlyETL)
- `04_ad_daily_summary_test.py`: 일별 ETL (DailyETL)

## 필수 설정

### 1. 의존성 패키지 설치
Airflow 환경에 다음 패키지들을 설치해야 합니다:
```bash
pip install pyathena pandas pyarrow boto3 python-dotenv pendulum
```

### 2. AWS 자격증명 설정

#### 방법 1: Airflow Variables
Airflow UI에서 다음 변수 설정:
- `aws_access_key_id`
- `aws_secret_access_key`

#### 방법 2: 환경변수
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

#### 방법 3: Kubernetes Secret (K8s 환경)
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aws-credentials
  namespace: airflow
stringData:
  AWS_ACCESS_KEY_ID: your_access_key
  AWS_SECRET_ACCESS_KEY: your_secret_key
```

### 3. 코드 마운트 (KubernetesPodOperator 사용 시)

#### 옵션 1: 커스텀 Docker 이미지
```dockerfile
FROM apache/airflow:3.1.7
COPY services/data_pipeline_t2 /opt/airflow/services/data_pipeline_t2
RUN pip install pyathena pandas pyarrow boto3 python-dotenv
```

#### 옵션 2: Volume Mount
DAG에서 이미 설정되어 있음:
- Host Path: `/opt/airflow/services/data_pipeline_t2`
- Container Path: `/opt/airflow/services/data_pipeline_t2`

## 실행 방법

### 1. 수동 트리거
```bash
# Hourly ETL 실행
airflow dags trigger 03_ad_hourly_summary_test

# Daily ETL 실행
airflow dags trigger 04_ad_daily_summary_test
```

### 2. 특정 날짜 실행
```bash
# 특정 날짜의 Hourly ETL
airflow dags trigger 03_ad_hourly_summary_test \
  --conf '{"data_interval_end": "2026-03-12T15:00:00+00:00"}'

# 특정 날짜의 Daily ETL
airflow dags trigger 04_ad_daily_summary_test \
  --conf '{"data_interval_end": "2026-03-13T00:00:00+00:00"}'
```

## 시간대 처리
- Airflow는 UTC로 동작
- etl_summary_t2는 KST로 동작
- DAG에서 자동 변환 처리

### 변환 프로세스
1. **Airflow 스케줄러**: UTC 기준으로 실행 (`data_interval_end`가 UTC)
2. **DAG 내부 변환**: 
   ```python
   # UTC → KST 변환 (pendulum 사용)
   dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
   ```
3. **ETL 패키지**: KST 시간을 받아 처리
   ```python
   etl = HourlyETL(target_hour=dt_kst)  # KST 시간 전달
   etl.run()
   ```
4. **S3 파티션**: KST 기준으로 생성
   - 경로: `s3://bucket/summary/year=2026/month=03/day=12/hour=15/`

### 예시
- Airflow 스케줄: `2026-03-12T06:00:00+00:00` (UTC)
- DAG 변환 후: `2026-03-12T15:00:00+09:00` (KST)
- S3 파티션: `year=2026/month=03/day=12/hour=15/`
- Athena 쿼리: WHERE hour = '15' (KST 15시 데이터)

### 주의사항
- ETL 패키지는 반드시 KST 시간을 받아야 함
- 파티션 생성 시 KST 기준으로 year/month/day/hour 추출
- 백필 시에도 동일한 시간대 변환 적용

## 디버깅

### 로그 확인
```bash
# Task 로그 확인
airflow tasks logs 03_ad_hourly_summary_test create_hourly_summary 2026-03-12
```

### 일반적인 문제 해결

1. **ModuleNotFoundError: etl_summary_t2**
   - sys.path에 경로가 추가되었는지 확인
   - KPO의 경우 볼륨 마운트 확인

2. **AWS Credentials Error**
   - 환경변수 또는 Airflow Variables 확인
   - IAM 권한 확인 (Athena, S3)

3. **Athena Query Failed**
   - S3 버킷 경로 확인
   - Glue 카탈로그 테이블 존재 여부 확인

## 성능 최적화
- `max_active_runs=1`: 동시 실행 방지
- `catchup=False`: 과거 실행 건너뛰기
- `execution_timeout`: 타임아웃 설정으로 무한 대기 방지