# HourlyETL Clicks 빈 값 오류 분석

## 발생 시간
- 2026-03-13 12:31:07

## 오류 현상
```
✅ Hourly ETL completed (2026/03/13/12) - Impressions: 0, Clicks: , CTR: 0.00%
```
- Clicks 값이 빈 문자열로 표시됨 (예상: 숫자 0)
- 데이터가 없음에도 정상 완료로 처리됨

## 근본 원인
코드 분석 결과, run() 메서드의 실행 흐름 문제 발견:

```python
def run(self):
    # 1. 테이블 존재 확인
    if not self._table_exists():
        self._create_table_with_ctas()
    else:
        self._insert_data_overwrite()  # 데이터 없으면 early return
    
    # 2. 항상 실행됨 (문제 지점!)
    self._validate_results()
```

1. `_insert_data_overwrite()`에서 데이터가 없으면 return
2. 하지만 `run()` 메서드는 계속 진행하여 `_validate_results()` 실행
3. 빈 파티션에 대한 COUNT 쿼리가 예상치 못한 결과 반환

## 로그 분석

### 1. 시간대 변환 정상
- UTC: 2026-03-13 03:00:00+00:00
- KST: 2026-03-13 12:00:00+09:00 ✅

### 2. 쿼리 실행 정상
- ad_combined_log 테이블 존재 확인 ✅
- INSERT OVERWRITE 실행 ✅
- 파티션 등록 완료 ✅

### 3. 데이터 문제
```
WARNING - ⚠️  No data found for 2026/03/13/12
```
- 해당 시간대에 impressions/clicks 데이터가 없음
- Impressions: 0으로 정상 표시
- **Clicks: 빈 값으로 비정상 표시** ❌

## AS-IS (현재 상태)
- `_insert_data_overwrite()`에서 데이터 없으면 early return
- 그러나 `_validate_results()`는 항상 실행됨
- 빈 파티션에 대한 COUNT 쿼리 결과가 불안정함
- Athena가 COUNT(*)=0일 때 NULL 또는 빈 문자열 반환 가능

## TO-BE (개선안)

### 1. run() 메서드 흐름 개선
```python
def run(self):
    """ETL 실행 (CTAS로 테이블 생성, INSERT OVERWRITE로 데이터 삽입)"""
    try:
        # 플래그 추가
        self.has_data = True
        
        # 1. 테이블 존재 여부 확인
        if not self._table_exists():
            logger.info("📌 Table does not exist, creating with CTAS...")
            self._create_table_with_ctas()
        else:
            logger.info("✅ Table exists, inserting data with INSERT OVERWRITE...")
            self.has_data = self._insert_data_overwrite()  # bool 반환
        
        # 2. 데이터가 있을 때만 검증
        if self.has_data:
            self._validate_results()
        else:
            logger.warning(
                f"⚠️  Hourly ETL completed ({self.year}/{self.month}/{self.day}/{self.hour}) - "
                f"No data (Impressions: 0, Clicks: 0, CTR: 0.00%)"
            )
            
    except Exception as e:
        logger.error(f"❌ Hourly ETL failed: {str(e)}")
        raise
```

### 2. _insert_data_overwrite() 수정
```python
def _insert_data_overwrite(self):
    """테이블이 있을 때 INSERT OVERWRITE로 데이터 삽입"""
    # ... (기존 코드) ...
    
    if not results:
        logger.warning(f"⚠️  No data found for {self.year}/{self.month}/{self.day}/{self.hour}")
        return False  # 데이터 없음을 반환
    
    # ... (데이터 처리) ...
    return True  # 데이터 처리 완료
```

### 3. _validate_results() 개선
```python
def _validate_results(self):
    """처리 결과 확인"""
    # ... (기존 쿼리) ...
    
    if results and len(results) > 0:
        result = results[0]
        # None 값 안전 처리
        impressions = result.get('total_impressions', 0) or 0
        clicks = result.get('total_clicks', 0) or 0
        ctr = float(result.get('ctr', 0) or 0)
        
        logger.info(
            f"✅ Hourly ETL completed ({self.year}/{self.month}/{self.day}/{self.hour}) - "
            f"Impressions: {impressions}, "
            f"Clicks: {clicks}, "
            f"CTR: {ctr:.2f}%"
        )
    else:
        logger.warning(f"⚠️  No validation results for {self.year}/{self.month}/{self.day}/{self.hour}")
```

### 2. 데이터 없음 경고 강화
```python
if not data_exists:
    logger.warning(f"⚠️  No data found for {partition_path}")
    logger.info(f"Creating empty partition with 0 records")
    # 빈 파티션 생성 로직
```

### 3. 로그 메시지 표준화
```python
# 데이터가 있을 때
"✅ Hourly ETL completed (2026/03/13/12) - Impressions: 1234, Clicks: 56, CTR: 4.54%"

# 데이터가 없을 때
"⚠️  Hourly ETL completed (2026/03/13/12) - No data (Impressions: 0, Clicks: 0, CTR: 0.00%)"
```

## 즉시 조치사항

### 1. 코드 수정 (dags/etl_modules/hourly_etl.py)
```python
# Option A: 최소 수정 - _validate_results()의 결과 처리만 개선
if results and len(results) > 0:
    result = results[0]
    # None/빈값 안전 처리
    impressions = result.get('total_impressions', 0) or 0
    clicks = result.get('total_clicks', 0) or 0
    
# Option B: 전체 흐름 개선 - run() 메서드에서 데이터 없음 처리
```

### 2. 임시 해결책 (즉시 적용 가능)
```python
# _validate_results() 메서드의 376번째 줄 수정
logger.info(
    f"✅ Hourly ETL completed ({self.year}/{self.month}/{self.day}/{self.hour}) - "
    f"Impressions: {result.get('total_impressions', 0) or 0}, "
    f"Clicks: {result.get('total_clicks', 0) or 0}, "  # or 0 추가
    f"CTR: {float(result.get('ctr', 0) or 0):.2f}%"
)
```

### 3. 테스트 시나리오
```python
# 테스트 DAG로 빈 데이터 시간대 실행
python -m services.data_pipeline_t2.dags.03_ad_hourly_summary_test

# 예상 결과:
# ⚠️  No data found for 2026/03/13/14
# ⚠️  Hourly ETL completed (2026/03/13/14) - No data (Impressions: 0, Clicks: 0, CTR: 0.00%)
```

## 장기 개선사항

### 1. 데이터 검증 강화
- ETL 시작 전 원본 데이터 존재 여부 확인
- 빈 파티션 생성 정책 수립

### 2. 메트릭 수집
- 빈 파티션 발생 빈도 모니터링
- 데이터 누락 알림 설정

### 3. 에러 핸들링 개선
- None 값 처리 표준화
- 타입 안정성 보장

## 영향 범위
- **DailyETL**: hourly 데이터 집계 시 빈 값으로 인한 타입 오류 가능
- **리포트 생성**: 숫자 연산 시 문자열/None 값으로 인한 예외 발생
- **모니터링**: 메트릭 수집 시 잘못된 데이터 타입으로 실패
- **Airflow**: 작업은 성공으로 표시되지만 실제 데이터는 불완전

## 추가 발견사항

### Athena COUNT 쿼리 동작
```sql
-- 빈 테이블에 대한 COUNT(*) 쿼리
SELECT COUNT(*) as total FROM empty_table
-- 결과: 0이 아니라 NULL 또는 빈 결과셋 반환 가능
```

### 파일 중복 문제
- `etl_summary_t2/hourly_etl.py`와 `dags/etl_modules/hourly_etl.py` 동일 코드 존재
- DAG는 `etl_modules` 버전 사용 중
- 버전 관리 및 동기화 필요

## 권장사항
1. **단기**: _validate_results()의 None 값 처리 개선
2. **중기**: run() 메서드 흐름 개선으로 불필요한 검증 제거
3. **장기**: 빈 파티션 처리 정책 수립 (빈 파일 생성 vs 스킵)