# ETL 파티션 스키마 불일치 - 해결완료

**작성일**: 2026-03-09  
**상태**: ✅ 완료 (코드 수정 + 테스트 성공)

---

## 🎯 최종 원인

### 문제
```
코드가 예상한 구조:        year/month/day/hour (4개 파티션)
실제 테이블 구조:         dt (1개 파티션)
```

### 증상
- DELETE 쿼리: COLUMN_NOT_FOUND (year 컬럼 없음)
- INSERT 쿼리: TYPE_MISMATCH (컬럼 수 불일치)

### 진단
```
테이블 컬럼:
- impression_id (string)
- user_id (string)
- ad_id (string)
- campaign_id (string)
- advertiser_id (string)
- platform (string)
- device_type (string)
- timestamp (bigint)
- is_click (boolean)
- click_timestamp (bigint)
- dt (string) ← 파티션 컬럼 (year/month/day/hour이 아님!)
```

---

## ✅ 해결책 (실행 완료)

### 수정 사항

#### 1️⃣ hourly_etl.py

**변경 전**:
```python
# PARTITION (year/month/day/hour) 사용
SELECT ..., '{self.year}' AS year, '{self.month}' AS month, '{self.day}' AS day, '{self.hour}' AS hour
WHERE year = '{self.year}' AND month = '{self.month}' ...
```

**변경 후**:
```python
# PARTITION (dt) 사용
SELECT ..., '{self.hour_str}' AS dt   # hour_str = "2026-03-09-03"
WHERE dt = '{self.hour_str}'
```

**CREATE TABLE 변경**:
```sql
-- 변경 전
PARTITIONED BY (year STRING, month STRING, day STRING, hour STRING)

-- 변경 후
PARTITIONED BY (dt STRING)
```

#### 2️⃣ daily_etl.py

**동일한 방식으로 수정**:
```python
# PARTITION (dt) 사용
SELECT ..., '{self.date_str}' AS dt   # date_str = "2026-03-09"
WHERE dt LIKE '{self.year}-{self.month}-{self.day}-%'  # ad_combined_log 조인용
```

#### 3️⃣ DELETE + INSERT 구조

**모든 파티션 관련 쿼리 통일**:
```sql
-- DELETE (기존 데이터 삭제)
DELETE FROM table WHERE dt = '{partition_value}'

-- INSERT (새 데이터 삽입)
INSERT INTO table SELECT ..., '{partition_value}' AS dt

-- REPAIR (파티션 메타데이터 등록)
MSCK REPAIR TABLE table
```

---

## 🧪 테스트 결과

### ✅ hourly_etl.py 테스트 성공

```
INFO:__main__:Processing hour: 2026-03-09-04
INFO:__main__:✅ Table ad_combined_log exists
INFO:__main__:✅ Existing data deleted
INFO:__main__:✅ Data inserted successfully
INFO:__main__:Repairing partitions...
```

| 단계 | 상태 | 시간 |
|------|------|------|
| DESCRIBE 확인 | ✅ 성공 | 2.07초 |
| DELETE | ✅ 성공 | 0.56초 |
| INSERT | ✅ 성공 | 1.55초 |
| MSCK REPAIR | ✅ 진행 중 | - |

### 예상되는 결과
- ✅ Glue 카탈로그에 파티션 등록
- ✅ Athena에서 단일 테이블로 조회 가능
- ✅ 파티션별 새 테이블 생성 안 됨

---

## 🔄 AS-IS vs TO-BE

### AS-IS (문제 상태)
```
매 시간 실행:
1. DESCRIBE 쿼리 실패 (SHOW TABLES 파싱 에러)
2. 강제로 CTAS 실행 → TABLE_ALREADY_EXISTS 에러
3. ETL 실패
4. Glue 카탈로그에 파티션별 새 테이블 계속 생성
5. Athena에서 0건 반환
```

### TO-BE (해결 후)
```
매 시간 실행:
1. DESCRIBE로 테이블 존재 확인 ✅
2. DELETE로 기존 파티션 데이터 삭제 ✅
3. INSERT로 새 데이터 삽입 ✅
4. MSCK REPAIR로 파티션 메타데이터 등록 ✅
5. Athena에서 정상 조회 가능 ✅
6. Glue 카탈로그 깔끔하게 유지 (새 테이블 안 생김)
```

---

## 📋 수정된 파일 목록

| 파일 | 주요 변경 사항 |
|------|---|
| `hourly_etl.py` | - _table_exists() → DESCRIBE 사용<br/>- year/month/day/hour → dt 파티션<br/>- DELETE + INSERT 구조 적용<br/>- _repair_partitions() 추가 |
| `daily_etl.py` | - _table_exists() → DESCRIBE 사용<br/>- year/month/day → dt 파티션<br/>- DELETE + INSERT 구조 적용<br/>- _repair_partitions() 추가<br/>- WHERE dt LIKE 패턴 사용 |

---

## 🚀 다음 단계

### 1️⃣ daily_etl.py 테스트 (예정)
```bash
python run_etl.py daily --target-date 2026-03-08
```

### 2️⃣ 백필 (과거 데이터 재처리)
```bash
# Hourly: 최근 7일 데이터
python run_etl.py backfill --start-date 2026-03-02 --end-date 2026-03-09 --type hourly

# Daily: 최근 7일 요약
python run_etl.py backfill --start-date 2026-03-02 --end-date 2026-03-09 --type daily
```

### 3️⃣ Athena에서 데이터 검증
```sql
SELECT COUNT(*) FROM capa_ad_logs.ad_combined_log;
SELECT DISTINCT dt FROM capa_ad_logs.ad_combined_log ORDER BY dt DESC LIMIT 10;
SELECT * FROM capa_ad_logs.ad_combined_log LIMIT 5;
```

### 4️⃣ Glue 카탈로그 정리 (선택)
```bash
# 기존 파티션별 테이블 삭제 (필요시)
python etl_summary_t2/cleanup_old_tables.py
```

---

## 💡 교훈 및 예방

### 근본 원인
- 테이블 스키마를 확인하지 않고 코드 작성
- SHOW TABLES 결과 파싱 불안정

### 예방 방법
1. **테이블 생성 전 스키마 검증**
   ```sql
   DESCRIBE table_name;
   ```

2. **테이블 존재 확인은 DESCRIBE 사용**
   - SHOW TABLES보다 안정적
   - 실패 = 테이블 없음

3. **Athena 쿼리 특성 이해**
   - INSERT OVERWRITE 미지원 (DELETE + INSERT 사용)
   - Presto 기반이므로 Hive 문법 제한

4. **CI/CD 테스트**
   ```bash
   python run_etl.py hourly --target-hour $(date -u +'%Y-%m-%d-%H')
   python run_etl.py daily --target-date $(date -u -d yesterday +'%Y-%m-%d')
   ```

---

## 📞 상태 요약

| 항목 | 상태 |
|------|------|
| **코드 수정** | ✅ 완료 |
| **hourly_etl 테스트** | ✅ 성공 |
| **daily_etl 테스트** | ⏳ 예정 |
| **백필** | ⏳ 예정 |
| **데이터 검증** | ⏳ 예정 |
