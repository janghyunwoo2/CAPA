# Summary 폴더의 CSV 및 Metadata 파일 쌓임 문제 분석 및 해결방안

**작성일**: 2026-03-14  
**문제**: S3 summary 폴더에 CSV와 metadata 파일이 지속적으로 쌓이는 문제

---

## 📋 문제 상황

### 현상
- S3의 `summary` 폴더에 CSV와 metadata 파일이 계속 쌓임
- AWS 콘솔에서 Athena 쿼리 결과를 `s3://capa-data-lake-827913617635/athena-results/`에 저장하도록 설정했으나 문제 지속
- ETL 프로세스를 통해 raw 데이터를 summary 폴더에 적재하는 과정에서 발생

### 파일 구조 예시
```
s3://capa-data-lake-827913617635/summary/
├── ad_combined_log/            # 시간별 요약 데이터 (정상)
│   └── year=2026/month=03/day=14/hour=10/
│       └── ad_combined_log.parquet
├── {query_id}.csv              # ❌ 문제: 쌓이는 CSV 파일
└── {query_id}.csv.metadata     # ❌ 문제: 쌓이는 메타데이터
```

---

## 🔍 원인 분석

### 1. ETL 프로세스의 Athena 쿼리 실행 흐름

ETL 프로세스(`hourly_etl.py`, `daily_etl.py`)에서 다음과 같은 흐름으로 작동:

```python
# 1. Athena SELECT 쿼리 실행
query_id = self.executor.execute_query(select_query)

# 2. Athena는 자동으로 쿼리 결과를 CSV로 저장
#    → s3://bucket/{output_location}/{query_id}.csv
#    → s3://bucket/{output_location}/{query_id}.csv.metadata

# 3. Python에서 쿼리 결과를 읽어서 Parquet로 변환
results = self.executor.get_query_results(query_id)
df = pd.DataFrame(results)

# 4. Parquet 파일을 summary 폴더에 저장
df.to_parquet(local_file)
s3_client.upload_file(local_file, bucket, s3_key)
```

### 2. 문제의 핵심: OutputLocation 설정

현재 코드에서 확인된 설정:
```python
# config.py
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"
```

하지만 사용자가 AWS 콘솔에서 `athena-results/`로 설정했다면, 다음 두 가지 가능성:
1. AWS 콘솔 설정이 코드의 `OutputLocation`을 덮어쓰지 않음
2. 실제로는 summary 폴더로 잘못 설정되어 있을 수 있음

### 3. Athena 쿼리 결과 저장 메커니즘

Athena는 **모든 SELECT 쿼리의 결과를 자동으로 S3에 저장**:
- 쿼리마다 고유한 `query_id` 생성
- 지정된 `OutputLocation`에 CSV와 metadata 파일 생성
- 이 파일들은 쿼리 결과를 읽은 후에도 자동 삭제되지 않음

### 4. 누적되는 파일 수 예측

| ETL 유형 | 실행 주기 | 일일 실행 횟수 | 생성 파일 수 |
|---------|----------|----------------|--------------|
| hourly_etl | 매시간 | 24회 | 48개 (CSV + metadata) |
| daily_etl | 매일 | 1회 | 2개 (CSV + metadata) |
| **합계** | - | **25회/일** | **50개/일** |

월간 약 1,500개의 파일이 누적될 수 있음

---

## ✅ 해결 방안

### 방안 1: OutputLocation 경로 확인 및 수정 (즉시 대응)

1. **현재 설정 확인**:
   ```python
   # athena_utils.py에서 실제 사용되는 경로 확인
   ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
   ```

2. **summary 폴더가 아닌 별도 임시 경로 사용**:
   ```python
   # config.py 수정
   # ❌ 문제가 될 수 있는 설정
   ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/summary/"
   
   # ✅ 권장 설정 (격리된 임시 경로)
   ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"
   ```

3. **AWS 콘솔과 코드 설정 일치 확인**:
   - AWS Athena 콘솔 > Settings > Query result location 확인
   - 워크그룹 설정도 확인 (워크그룹 설정이 우선할 수 있음)

### 방안 2: S3 라이프사이클 정책 설정 (장기 해결책)

AWS S3 콘솔에서 라이프사이클 규칙 추가:

```json
{
  "Rules": [{
    "Id": "DeleteAthenaTempFiles",
    "Status": "Enabled",
    "Filter": {
      "Prefix": ".athena-temp/"  // 또는 "athena-results/"
    },
    "Expiration": {
      "Days": 7  // 7일 후 자동 삭제
    }
  }]
}
```

### 방안 3: 쿼리 실행 후 즉시 파일 삭제 (적극적 해결책)

`athena_utils.py`에 cleanup 메서드 추가:

```python
def cleanup_query_results(self, query_id: str):
    """쿼리 결과 파일을 S3에서 삭제"""
    try:
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        bucket = ATHENA_TEMP_RESULTS_PATH.split('/')[2]
        prefix = ATHENA_TEMP_RESULTS_PATH.split(bucket + '/')[-1]
        
        # CSV와 metadata 파일 삭제
        objects_to_delete = [
            {'Key': f"{prefix}{query_id}.csv"},
            {'Key': f"{prefix}{query_id}.csv.metadata"}
        ]
        
        s3_client.delete_objects(
            Bucket=bucket,
            Delete={'Objects': objects_to_delete}
        )
        
        logger.info(f"✅ Cleaned up results for query {query_id}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to cleanup: {str(e)}")
```

ETL 코드에서 사용:
```python
# hourly_etl.py의 _insert_data_overwrite() 메서드
query_id = self.executor.execute_query(select_query)
results = self.executor.get_query_results(query_id)

# 데이터 처리 완료 후 정리
self.executor.cleanup_query_results(query_id)  # 추가
```

### 방안 4: UNLOAD 명령 사용 (대안적 접근)

Athena SELECT 대신 UNLOAD 명령을 사용하여 직접 Parquet로 저장:

```sql
UNLOAD (
    SELECT * FROM impressions 
    WHERE year=2026 AND month=3 AND day=14 AND hour=10
)
TO 's3://bucket/summary/ad_combined_log/year=2026/month=03/day=14/hour=10/'
WITH (format = 'PARQUET', compression = 'SNAPPY')
```

장점: 중간 CSV 파일 생성 없이 직접 Parquet로 저장

---

## 🎯 권장 조치 사항

### 즉시 조치
1. **OutputLocation 경로 확인**: summary 폴더가 아닌 별도 임시 경로 사용 확인
2. **기존 CSV/metadata 파일 정리**: summary 폴더의 불필요한 파일 삭제

### 단기 조치 (1주일 내)
1. **S3 라이프사이클 정책 설정**: 임시 파일 자동 삭제
2. **cleanup 메서드 구현**: 쿼리 실행 후 즉시 정리

### 장기 개선 (1개월 내)
1. **UNLOAD 명령으로 전환 검토**: 중간 CSV 없이 직접 Parquet 저장
2. **모니터링 설정**: S3 폴더별 파일 수 및 용량 모니터링

---

## 📊 영향 및 이점

### 현재 문제점
- S3 저장 공간 낭비 (월 1,500개 파일)
- 폴더 구조 복잡화
- S3 API 호출 비용 증가
- 데이터 거버넌스 문제

### 개선 후 이점
- 저장 공간 90% 이상 절약
- 깔끔한 폴더 구조 유지
- 운영 비용 절감
- 자동화된 파일 관리

---

## 📚 참고 자료

- [AWS Athena 쿼리 결과 위치 설정](https://docs.aws.amazon.com/athena/latest/ug/querying.html#query-results-specify-location)
- [S3 라이프사이클 정책](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [Athena UNLOAD 명령](https://docs.aws.amazon.com/athena/latest/ug/unload.html)