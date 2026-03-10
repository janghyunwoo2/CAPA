# Glue 임시 테이블 생성으로 인한 Athena 쿼리 실패 문제

**작성일**: 2026-03-09  
**상태**: 완료 (원인 분석 + 해결책 수립)

---

## 📋 문제 요약

### 증상
- S3에는 데이터가 정상적으로 적재되고 있음
- Athena에서 데이터를 조회하려 하면 쿼리가 실행되지 않음 (타임아웃 또는 오류)
- Glue 카탈로그에서 많은 임시 테이블이 계속 생성됨 (`ad_combined_log_temp_YYYY_MM_DD_HH` 등)

### 영향 범위
- **ad_combined_log** 테이블 쿼리 불가
- 매시간 ETL 작업 실패
- Daily 요약 데이터 생성 불가

---

## 🔍 원인 분석

### AS-IS (현재 방식의 문제점)

```
매시간 ETL 프로세스:

1. CTAS 임시 테이블 생성
   ├─ CREATE TABLE ad_combined_log_temp_2026_03_09_10 AS SELECT...
   ├─ Glue 카탈로그에 임시 테이블 메타데이터 추가
   └─ S3에 PARQUET 파일 쓰기 (정상)

2. 파티션 미등록
   ├─ CTAS로 생성된 데이터는 S3에만 존재
   ├─ Glue 카탈로그의 파티션 정보는 미동기화
   └─ 실제 테이블(ad_combined_log)에서 데이터 찾을 수 없음

3. 임시 테이블 삭제 불완전
   ├─ DROP TABLE 명령이 실패하거나 누락
   └─ Glue 카탈로그에 좀비 임시 테이블 축적
```

### 근본 원인 3가지

#### 1️⃣ **파티션 미등록 (Primary Issue)**
- **원인**: CTAS 쿼리로 S3에 데이터를 직접 쓰면, Glue 카탈로그의 파티션 메타데이터가 자동으로 갱신되지 않음
- **결과**: Athena가 쿼리할 파티션을 찾을 수 없음 → 쿼리 실패 또는 0건 반환
- **코드 위치**: `hourly_etl.py`의 CTAS 쿼리 후 파티션 수리 로직 부재

#### 2️⃣ **임시 테이블 카탈로그 오염**
- **원인**: 매시간마다 새로운 임시 테이블(`ad_combined_log_temp_YYYY_MM_DD_HH`)이 생성되고, Glue 카탈로그에 축적
- **결과**: 
  - Glue 카탈로그 검색 시간 증가
  - 테이블 메타데이터 혼란
  - Athena 메타스토어 응답 지연

#### 3️⃣ **테이블 구조 불일치**
- **원인**: 실제 테이블(`ad_combined_log`)과 임시 테이블(`ad_combined_log_temp_*`)의 스키마가 일관성 없음
- **결과**: 데이터 타입 불일치로 인한 쿼리 에러

---

## ✅ 해결책 (TO-BE)

### 전략 요약
```
최소 변경으로 최대 효과:
1. CTAS 후 파티션 수리 추가 (MSCK REPAIR TABLE)
2. 임시 테이블 정리 자동화
3. 파티션 기반 S3 경로 표준화
```

### 변경 사항

#### Step 1: 파티션 자동 등록 추가

**파일**: `etl_summary_t2/hourly_etl.py`

```python
# 변경 전
def run(self):
    try:
        self.create_tables_if_not_exists()
        # CTAS 실행
        self.executor.execute_query(ctas_query)
        # ❌ 여기서 파티션 수리 없음!

# 변경 후
def run(self):
    try:
        self.create_tables_if_not_exists()
        # CTAS 실행
        self.executor.execute_query(ctas_query)
        
        # ✅ 파티션 등록 (신규 추가)
        self._repair_partitions()
        
        # ✅ 임시 테이블 정리 (신규 추가)
        self._cleanup_temp_tables()
```

#### Step 2: 파티션 수리 메서드 추가

```python
def _repair_partitions(self):
    """Glue 카탈로그 파티션 동기화"""
    repair_query = f"MSCK REPAIR TABLE {DATABASE}.ad_combined_log"
    logger.info("Repairing partitions...")
    self.executor.execute_query(repair_query)
    logger.info("Partition repair completed")
```

#### Step 3: 임시 테이블 정리 메서드 추가

```python
def _cleanup_temp_tables(self):
    """7일 이상 된 임시 테이블 삭제"""
    from datetime import datetime, timedelta
    import boto3
    
    athena_client = boto3.client('athena', region_name=AWS_REGION)
    cutoff_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y_%m_%d')
    
    # Glue 카탈로그에서 임시 테이블 목록 조회
    try:
        glue_client = boto3.client('glue', region_name=AWS_REGION)
        response = glue_client.get_tables(DatabaseName=DATABASE)
        
        for table in response['TableList']:
            table_name = table['Name']
            if 'ad_combined_log_temp_' in table_name:
                # 7일 이상 된 테이블 삭제
                table_date = table_name.replace('ad_combined_log_temp_', '')
                if table_date < cutoff_date:
                    drop_query = f"DROP TABLE IF EXISTS {DATABASE}.{table_name}"
                    logger.info(f"Dropping old temp table: {table_name}")
                    self.executor.execute_query(drop_query)
    except Exception as e:
        logger.warning(f"Temp table cleanup failed: {e}")
        # 정리 실패는 비치명적 → 계속 진행
```

#### Step 4: S3 경로 표준화

**파일**: `etl_summary_t2/config.py`

```python
# 변경 전
S3_PATHS = {
    "ad_combined_log": f"s3://{S3_BUCKET}/summary/ad_combined_log/"
}

# 변경 후 (파티션 구조 명시)
S3_PATHS = {
    "ad_combined_log": f"s3://{S3_BUCKET}/summary/ad_combined_log/",
    # 파티션 구조: year={YYYY}/month={MM}/day={DD}/hour={HH}/
    "ad_combined_log_daily": f"s3://{S3_BUCKET}/summary/ad_combined_log_summary/",
    # 파티션 구조: year={YYYY}/month={MM}/day={DD}/
}

# Athena 타임아웃 설정 추가
QUERY_TIMEOUT_SECONDS = 600  # 10분
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10
```

---

## 📊 기대 효과

### 개선 전후 비교

| 항목 | 변경 전 | 변경 후 |
|------|--------|--------|
| **Athena 쿼리 성공률** | 0% (데이터 없음) | 100% |
| **파티션 등록** | 수동/불완전 | 자동 (MSCK) |
| **임시 테이블 축적** | 무제한 (카탈로그 오염) | 7일 후 자동 정리 |
| **쿼리 응답 시간** | N/A | < 30초 (정상) |
| **Glue 카탈로그 크기** | ↑ 매일 증가 | → 안정화 |

---

## 🛠️ 적용 순서

### Phase 1: 긴급 (즉시 적용)
1. `hourly_etl.py` → `_repair_partitions()` 메서드 추가
2. `run()` 메서드에서 CTAS 후 `_repair_partitions()` 호출
3. DAG 재시작 및 테스트

### Phase 2: 향상 (1주일 이내)
4. `_cleanup_temp_tables()` 메서드 추가
5. `config.py`에 타임아웃 설정 추가
6. `daily_etl.py`에도 동일 변경 적용

### Phase 3: 운영 (지속)
7. Glue 카탈로그 모니터링 (CloudWatch)
8. 파티션 등록 실패 시 알림 설정

---

## 🧪 검증 체크리스트

```
[ ] 1. S3에 파케이 파일이 정상 적재되는가?
      → s3://capa-data-lake-827913617635/summary/ad_combined_log/ 확인

[ ] 2. Glue 카탈로그에 파티션이 등록되는가?
      → aws glue get-partitions --database-name capa_ad_logs --table-name ad_combined_log

[ ] 3. Athena에서 ad_combined_log를 조회할 수 있는가?
      → SELECT COUNT(*) FROM capa_ad_logs.ad_combined_log WHERE year='2026' AND month='03'

[ ] 4. 임시 테이블이 정상 삭제되는가?
      → Glue 카탈로그에서 ad_combined_log_temp_* 테이블 개수 감소 확인

[ ] 5. Daily ETL이 정상 작동하는가?
      → ad_combined_log_summary 데이터 생성 확인
```

---

## 📌 주의 사항

### ⚠️ 기존 데이터 처리
```sql
-- 기존의 고아 파티션(orphan partitions) 정리
MSCK REPAIR TABLE capa_ad_logs.ad_combined_log;

-- 확인: 파티션 개수 체크
SHOW PARTITIONS capa_ad_logs.ad_combined_log;
```

### ⚠️ 임시 테이블 수동 정리 (필요시)
```sql
-- Glue 콘솔에서 또는 다음 명령으로 제거
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log_temp_2026_03_08_*;
```

### ⚠️ Athena 쿼리 권한
- IAM 역할에 `athena:*`, `s3:GetObject`, `glue:*` 권한 필수
- S3 경로 권한 확인: `s3:///summary/ad_combined_log/` 읽기 권한

---

## 📚 참고 자료

### AWS 문서
- [Athena 외부 테이블 및 파티션](https://docs.aws.amazon.com/ko_kr/athena/latest/ug/partition-projection.html)
- [Glue 카탈로그 파티션](https://docs.aws.amazon.com/ko_kr/glue/latest/dg/how-partitions-work.html)
- [MSCK REPAIR TABLE](https://docs.aws.amazon.com/ko_kr/athena/latest/ug/alter-table-repair.html)

### 실행 명령
```bash
# Hourly ETL 수동 실행 (테스트용)
python run_etl.py hourly --target-hour 2026-03-09-14

# Daily ETL 수동 실행
python run_etl.py daily --target-date 2026-03-09

# 백필 (과거 데이터 재처리)
python run_etl.py backfill --start-date 2026-03-01 --end-date 2026-03-09 --type hourly
```

---

## ✨ 다음 단계

1. **코드 변경**: 위 `Step 1~4` 적용
2. **테스트**: 검증 체크리스트 실행
3. **모니터링**: CloudWatch에서 Athena 쿼리 성공률 추적
4. **문서화**: 팀에 변경 사항 공유
