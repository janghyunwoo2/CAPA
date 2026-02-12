# 작업 08: Athena 데이터 검증

> **Phase**: 2 (E2E 연결 테스트)  
> **담당**: Data Engineer  
> **예상 소요**: 10분  
- **이전 단계**: [08_log_generator.md](./08_log_generator.md)
- **다음 단계**: [10_helm_values_준비.md](./10_helm_values_준비.md)

---

## 1. 목표

S3에 저장된 Parquet 데이터가 Athena에서 쿼리 가능한지 확인하여 Kinesis → S3 → Athena 파이프라인을 검증합니다.

---

## 2. 검증 플로우

```
Log Generator → Kinesis → Firehose → S3 (Parquet) → Glue Catalog → Athena SELECT
```

---

## 3. 실행 단계

### 3.1 S3 데이터 확인

```powershell
# S3에 Parquet 파일 존재 확인
aws s3 ls s3://capa-data-lake-<ACCOUNT_ID>/raw/ --recursive

# 예상 출력:
# 2026-02-11 21:35:00  2048 raw/year=2026/month=02/day=11/file1.parquet
# 2026-02-11 21:36:00  2048 raw/year=2026/month=02/day=11/file2.parquet
```

### 3.2 Glue Partition 추가 (필요 시)

```powershell
# partition이 자동 생성되지 않았다면 수동 추가
aws athena start-query-execution `
    --query-string "MSCK REPAIR TABLE ad_events_raw" `
    --query-execution-context Database=capa_db `
    --result-configuration OutputLocation=s3://capa-data-lake-<ACCOUNT_ID>/athena-results/
```

### 3.3 Athena 쿼리 실행 (AWS Console 또는 CLI)

**방법 1: AWS Console**

1. AWS Console → Athena로 이동
2. Database: `capa_db` 선택
3. 쿼리 입력:

```sql
-- 1. 테이블 확인
SELECT * FROM ad_events_raw LIMIT 10;

-- 2. 이벤트 타입별 집계
SELECT event_type, COUNT(*) as count
FROM ad_events_raw
GROUP BY event_type;

-- 3. 캠페인별 집계
SELECT campaign_id, COUNT(*) as events
FROM ad_events_raw
GROUP BY campaign_id
ORDER BY events DESC;
```

**방법 2: AWS CLI**

```powershell
# Athena 쿼리 실행
$QueryString = "SELECT event_type, COUNT(*) as count FROM ad_events_raw GROUP BY event_type"

$QueryId = (aws athena start-query-execution `
    --query-string $QueryString `
    --query-execution-context Database=capa_db `
    --result-configuration OutputLocation=s3://capa-data-lake-<ACCOUNT_ID>/athena-results/ `
    --query 'QueryExecutionId' `
    --output text)

Write-Host "Query ID: $QueryId"

# 결과 조회 (몇 초 대기 후)
Start-Sleep -Seconds 5

aws athena get-query-results --query-execution-id $QueryId

# 예상 출력:
# Rows:
# - Data:
#   - VarCharValue: event_type
#   - VarCharValue: count
# - Data:
#   - VarCharValue: impression
#   - VarCharValue: 45
# - Data:
#   - VarCharValue: click
#   - VarCharValue: 30
# - Data:
#   - VarCharValue: conversion
#   - VarCharValue: 5
```

---

## 4. 검증 방법

### 4.1 데이터 존재 확인

```sql
SELECT COUNT(*) as total_events FROM ad_events_raw;
-- 예상: total_events > 0
```

### 4.2 스키마 확인

```sql
DESCRIBE ad_events_raw;

-- 예상 출력:
-- event_id       string
-- event_type     string
-- timestamp      bigint
-- campaign_id    string
-- user_id        string
-- device_type    string
-- bid_price      double
```

### 4.3 Partition 확인

```sql
SHOW PARTITIONS ad_events_raw;

-- 예상 출력:
-- year=2026/month=02/day=11
```

### 4.4 성공 기준

- [ ] S3에 Parquet 파일 존재
- [ ] Athena `SELECT *` 쿼리 성공
- [ ] 데이터 행 수 > 0
- [ ] event_type별 집계 결과 출력

---

## 5. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `Table not found` | Glue Table 미생성 | 05_data_pipeline_기본.md 확인 |
| `Zero records returned` | S3파일 없음 or Partition 문제 | `MSCK REPAIR TABLE` 실행 |
| `HIVE_PARTITION_SCHEMA_MISMATCH` | 스키마 불일치 | Glue Table DDL 확인 |
| `Access Denied (S3)` | Athena IAM 권한 부족 | S3 읽기 권한 추가 |

---

## 6. 추가 분석 쿼리

### 6.1 시간대별 이벤트 수

```sql
SELECT 
    FROM_UNIXTIME(timestamp) as event_time,
    event_type,
    COUNT(*) as count
FROM ad_events_raw
WHERE year = '2026' AND month = '02' AND day = '11'
GROUP BY 1, 2
ORDER BY 1 DESC
LIMIT 20;
```

### 6.2 캠페인별 평균 입찰가

```sql
SELECT 
    campaign_id,
    COUNT(*) as events,
    AVG(bid_price) as avg_bid,
    MAX(bid_price) as max_bid
FROM ad_events_raw
GROUP BY campaign_id
ORDER BY events DESC;
```

---

## 7. 다음 단계

✅ **Athena 쿼리 성공 = E2E 파이프라인 검증 완료!** → `09_helm_values_준비.md`로 이동

> 🎉 **Phase 2 완료!** Kinesis → S3 → Athena 데이터 흐름이 정상 작동합니다.

---

## 8. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**Athena 쿼리 결과**:
```sql
SELECT event_type, COUNT(*) FROM ad_events_raw GROUP BY event_type;

(결과 복사)
```

**총 레코드 수**: ______

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```
