# Airflow S3 업로드 타임아웃 문제 분석

## 발생 시간
- 2026-03-13 10:15:39

## 오류 내용
```
[2026-03-13 10:15:39] INFO - Saving 1757 rows to s3://capa-data-lake-827913617635/summary/ad_combined_log/year=2026/month=02/day=12/hour=04/...
[2026-03-13 10:15:39] ERROR - Process timed out pid=5998
[2026-03-13 10:15:39] ERROR - Task failed with exception
AirflowTaskTimeout: Timeout, PID: 5998
```

## 문제 발생 경로
1. DAG: `05_ad_hourly_summary_period`
2. 함수: `_run_hourly_etl_period` → `HourlyETL.run()` → `_insert_data_overwrite()`
3. 타임아웃 위치: S3 파일 업로드 (`s3_client.upload_file()`)

## AS-IS (현재 상태)

### 1. Airflow Task 타임아웃 설정
```python
default_args = {
    "execution_timeout": timedelta(minutes=30),  # 30분 타임아웃
}
```

### 2. S3 업로드 과정
```python
# hourly_etl.py 322번째 줄 부근
s3_client.upload_file(
    local_parquet_file,
    bucket_name,
    s3_object_key
)  # 이 부분에서 타임아웃 발생
```

### 3. 문제점
- 1757 rows의 데이터를 S3에 업로드하는 중 30분 타임아웃 도달
- 네트워크 속도나 S3 처리 지연으로 인한 것으로 추정
- 기간별 처리 시 여러 시간대를 연속으로 처리하여 누적 시간이 증가

## TO-BE (해결 방안)

### 1. 즉시 조치 - 타임아웃 증가 ✅ (적용 완료)
```python
# dags/05_ad_hourly_summary_period.py
default_args = {
    "execution_timeout": timedelta(hours=4),  # 30분 → 4시간으로 증가
}

# dags/06_ad_daily_summary_period.py
default_args = {
    "execution_timeout": timedelta(hours=4),  # 60분 → 4시간으로 증가
}
```

### 2. 중기 조치 - S3 업로드 최적화
```python
# hourly_etl.py의 _insert_data_overwrite 메서드 개선

# A. TransferConfig로 멀티파트 업로드 및 재시도 설정
from boto3.s3.transfer import TransferConfig

transfer_config = TransferConfig(
    multipart_threshold=1024 * 25,  # 25MB
    max_concurrency=10,
    multipart_chunksize=1024 * 25,
    use_threads=True,
    max_io_queue=100
)

s3_client.upload_file(
    local_parquet_file,
    bucket_name,
    s3_object_key,
    Config=transfer_config
)

# B. 타임아웃과 함께 재시도 로직 추가
import time
from botocore.exceptions import ClientError

max_retries = 3
for attempt in range(max_retries):
    try:
        s3_client.upload_file(
            local_parquet_file,
            bucket_name,
            s3_object_key,
            Config=transfer_config
        )
        break  # 성공하면 루프 종료
    except ClientError as e:
        if attempt < max_retries - 1:
            logger.warning(f"S3 upload attempt {attempt + 1} failed, retrying...")
            time.sleep(10)  # 10초 대기 후 재시도
        else:
            raise
```

### 3. 장기 조치 - 아키텍처 개선

#### A. 배치 처리 단위 축소
```python
# Period DAG에서 하루 단위로 나누어 처리
# 현재: start_date ~ end_date 전체를 한 번에
# 개선: 일별로 SubDAG 또는 Dynamic Task로 분할
```

#### B. S3 Transfer Acceleration 활성화
```bash
# AWS CLI로 Transfer Acceleration 활성화
aws s3api put-bucket-accelerate-configuration \
    --bucket capa-data-lake-827913617635 \
    --accelerate-configuration Status=Enabled

# boto3에서 가속화 엔드포인트 사용
s3_client = boto3.client(
    's3',
    region_name=AWS_REGION,
    config=Config(s3={'use_accelerate_endpoint': True})
)
```

#### C. 로컬 임시 파일 대신 S3 직접 쓰기
```python
# pyarrow의 S3FileSystem 사용
import pyarrow.fs as pafs

fs = pafs.S3FileSystem(region=AWS_REGION)
with fs.open_output_stream(s3_path) as f:
    pq.write_table(table, f, compression='snappy')
```

## 성능 메트릭
- 업로드할 데이터: 1757 rows
- 예상 파일 크기: ~1-5MB (parquet 압축 후)
- 정상 업로드 시간: 일반적으로 1-10초
- 현재 상황: 30분 이상 소요 → 네트워크 문제 의심

## 권장 사항

1. **즉시**: ✅ DAG의 execution_timeout을 4시간으로 증가 (완료)
2. **단기**: S3 업로드에 멀티파트 업로드와 재시도 로직 추가
3. **중기**: Period DAG를 일별 처리 단위로 분할
4. **장기**: S3 Transfer Acceleration 또는 Direct Write 구현

## 모니터링 추가
```python
# 업로드 전후 시간 측정
import time

start_time = time.time()
logger.info(f"Starting S3 upload: {s3_object_key}")

s3_client.upload_file(...)

upload_time = time.time() - start_time
logger.info(f"S3 upload completed in {upload_time:.2f} seconds")

# CloudWatch 메트릭 전송 (선택사항)
if upload_time > 60:  # 1분 이상 걸리면 경고
    logger.warning(f"Slow S3 upload detected: {upload_time:.2f}s")
```

## 참고사항
- Airflow가 Kubernetes에서 실행 중일 경우, Pod의 네트워크 정책도 확인 필요
- AWS VPC 엔드포인트를 통한 S3 접근 시 대역폭 제한 확인
- 동시에 많은 Task가 S3에 접근하는 경우 throttling 발생 가능