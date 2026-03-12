# summary/ 폴더의 CSV & Metadata 파일 쌓임 분석

**작성일**: 2026-03-10  
**분석 범위**: `services/data_pipeline_t2/etl_summary_t2/` 의 hourly_etl.py, daily_etl.py, athena_utils.py

---

## 문제 정의

S3 `athena-results/temp/` 폴더에 **CSV 파일과 metadata.json 파일이 계속 쌓이고 있다**.

---

## 원인 분석

### 1️⃣ **Athena 쿼리 결과 저장 메커니즘**

```plaintext
[Athena Query 실행]
  ↓
[ResultConfiguration으로 S3 지정]
  ↓
[쿼리별 폴더 생성: {query_id}/]
  ↓
[메타데이터 파일 저장]:
  - {query_id}.csv        (실제 쿼리 결과)
  - {query_id}.metadata   (메타데이터)
```

**관련 코드**:
```python
# athena_utils.py, line 42-46
response = self.client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': database},
    ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
)
```

### 2️⃣ **임시 경로 설정**

[config.py](config.py#L29)에서:
```python
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/athena-results/temp/"
```

**목적**: Athena 메타데이터 오염 방지

**결과**: 모든 쿼리 결과가 `s3://bucket/athena-results/temp/` 아래에 저장됨

### 3️⃣ **반복 실행으로 인한 축적**

| ETL | 실행 주기 | 호출 빈도 | 결과 |
|-----|---------|---------|------|
| hourly_etl | 매시간 | 1회/hour | 24개 파일/일 |
| daily_etl | 매일 | 1회/day | 1개 파일/일 |
| **합계** | - | **25회/일** | **~50개 파일/일** (CSV + metadata) |

**월간 예상**: ~1,500개 파일 축적

### 4️⃣ **파일 구조**

```
s3://bucket/athena-results/temp/
├── {query_id_1}/
│   ├── {query_id_1}.csv
│   └── {query_id_1}.metadata
├── {query_id_2}/
│   ├── {query_id_2}.csv
│   └── {query_id_2}.metadata
└── ...
```

---

## AS-IS vs TO-BE

### ✗ AS-IS (현재 상태)

```
문제점:
├─ ❌ 매 쿼리마다 새로운 메타데이터 파일 생성
├─ ❌ 파일 자동 삭제 정책 없음
├─ ❌ S3 저장소 공간 낭비
├─ ❌ 관리할 파일이 월 1,500+ 개씩 증가
└─ ❌ 쿼리 디버깅 시 파일 찾기 어려움

영향:
├─ S3 비용 증가
├─ 폴더 구조 복잡화
└─ 메타데이터 관리 부담
```

### ✅ TO-BE (개선 방안)

```
개선 방향:
├─ ✅ 단일 임시 경로 재사용 (쿼리 결과 덮어쓰기)
├─ ✅ S3 Life Cycle Policy로 자동 삭제
├─ ✅ 임시 파일 명시적 정리
└─ ✅ 메인 데이터 경로 분리 유지

장점:
├─ 저장소 공간 절약
├─ 자동화된 정리
├─ 폴더 구조 간결화
└─ 운영 비용 감소
```

---

## 상세 분석

### 파일 생성 플로우

#### **hourly_etl.py**

[hourly_etl.py](hourly_etl.py#L226-250)

```
1️⃣ execute_query() 호출
   → Query ID 생성: qid_abc123xyz
   
2️⃣ Athena에서 SELECT 쿼리 실행
   
3️⃣ 메타데이터 저장
   → s3://bucket/athena-results/temp/qid_abc123xyz/
      ├── qid_abc123xyz.csv
      └── qid_abc123xyz.metadata
   
4️⃣ get_query_results()로 결과 읽기
   → CSV에서 데이터 추출
   
5️⃣ PyArrow로 Parquet 변환
   → s3://bucket/summary/ad_combined_log/year=.../hour=.../
      └── ad_combined_log.parquet (여기에 실제 데이터 저장)
   
6️⃣ 임시 메타데이터 파일은 버려짐 ❌
```

#### **daily_etl.py**

[daily_etl.py](daily_etl.py#L256-270)

```
동일한 과정:
1. execute_query() → Query ID 생성
2. SELECT 쿼리 실행
3. 메타데이터 파일 생성 (temp/ 폴더)
4. 결과 읽기 + Parquet 저장
5. 임시 파일 미삭제
```

---

## 개선 방안

### 방안 1️⃣: S3 Life Cycle Policy (권장)

**효과**: 자동 정리, 운영 부담 최소화

```json
{
  "Rules": [
    {
      "ID": "DeleteAthenaTemp",
      "Filter": { "Prefix": "athena-results/temp/" },
      "Expiration": { "Days": 1 }
    }
  ]
}
```

**장점**:
- 자동 정리 (매일)
- 추가 코드 불필요
- AWS 관리

**단점**:
- 파일 생성 후 1일 경과 후 삭제

---

### 방안 2️⃣: 명시적 파일 정리

**효과**: 즉시 정리, 정밀 제어

```python
# athena_utils.py에 추가
def cleanup_temp_results(self, query_id: str):
    """쿼리 메타데이터 파일 정리"""
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    
    # 임시 폴더 내 파일 삭제
    try:
        prefix = f"athena-results/temp/{query_id}/"
        bucket_name = S3_BUCKET
        
        # 해당 query_id 폴더 내 모든 파일 삭제
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                
        logger.info(f"✅ Cleaned up temp files for query {query_id}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to cleanup temp files: {str(e)}")
```

**적용 위치**:
```python
# hourly_etl.py, line 235 (결과 읽기 후)
query_id = self.executor.execute_query(select_query)
results = self.executor.get_query_results(query_id)

# 여기에 추가:
self.executor.cleanup_temp_results(query_id)
```

**장점**:
- 즉시 정리 (메모리 사용 후)
- 파일이 쌓이지 않음
- 명시적 제어

**단점**:
- 추가 API 호출 (약간의 비용)
- 디버깅 시 메타데이터 파일 없음

---

### 방안 3️⃣: 경로 공유 (저비용)

**효과**: 쿼리 결과 덮어쓰기로 파일 최소화

```python
# config.py 수정
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/athena-results/temp-single/"
# 모든 쿼리가 동일 경로 사용 → 파일 덮어쓰기
```

**결과**:
- 항상 최대 2개 파일 (CSV + metadata)
- 저장소 공간 최소
- 자동 덮어쓰기

**단점**:
- 동시 쿼리 실행 시 충돌 가능
- 디버깅 시 데이터 손실

---

## 권장 솔루션

**1차: S3 Life Cycle Policy** (즉시 적용)
```
목표: 임시 파일 자동 정리
비용: 무료
설정: AWS 콘솔에서 1회 설정
```

**2차: 선택적 명시적 정리**
```
목표: 즉시 정리 필요 시
비용: 약소 증가 (list/delete API 호출)
구현: athena_utils.py에 cleanup 메서드 추가
```

---

## 추가 고려사항

### 📊 현재 누적 파일 정보

```
생성 기간: 프로젝트 시작 ~ 2026-03-10
예상 누적: ~1,500 - 2,000 개 파일
저장 공간: ~50 - 100 MB (메타데이터만)
```

### 🔧 기존 파일 정리 스크립트

```python
import boto3

s3 = boto3.client('s3', region_name='ap-northeast-2')

paginator = s3.get_paginator('list_objects_v2')
pages = paginator.paginate(
    Bucket='capa-data-lake-827913617635',
    Prefix='athena-results/temp/'
)

deleted_count = 0
for page in pages:
    if 'Contents' in page:
        for obj in page['Contents']:
            s3.delete_object(Bucket='capa-data-lake-827913617635', Key=obj['Key'])
            deleted_count += 1

print(f"✅ Deleted {deleted_count} temporary files")
```

---

## 결론

| 항목 | 현황 |
|------|------|
| **문제** | Athena 쿼리 메타데이터가 매일 ~50개씩 쌓임 |
| **원인** | `ATHENA_TEMP_RESULTS_PATH` 설정으로 모든 쿼리 결과 저장 |
| **영향** | 월 1,500+ 파일, 관리 부담 증가 |
| **해결** | S3 Life Cycle Policy로 자동 정리 (권장) |
| **비용** | 무료 (S3 저장 공간만 절약) |
| **구현** | AWS 콘솔 1회 설정 (5분 소요) |

