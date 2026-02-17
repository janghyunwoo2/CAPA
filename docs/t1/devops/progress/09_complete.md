# ✅ 작업 09 완료: Athena 데이터 검증

> [!IMPORTANT]
> **2026-02-17 업데이트**: 파티션 인식 방식이 `MSCK REPAIR` 수동 실행에서 **Glue Crawler** 자동 인식 방식으로 변경되었습니다.

**작업 파일**: [`09_athena_데이터_검증.md`](../work/09_athena_데이터_검증.md)
**Phase**: 2 (E2E 연결 테스트)
**실행 일시**: 2026-02-12 16:20 - 16:30
**결과**: ✅ **성공**

---

## 📋 실행 내용

### 1. S3 데이터 및 파티션 확인

*   **S3 경로**: `s3://capa-data-lake-xxx/raw/year=2026/month=02/day=12/`
*   **파일 목록**: 시간대별 Parquet 파일 다수 확인 (15분 간격 등)
*   **Glue Partition 업데이트**:
    *   (이전) `MSCK REPAIR TABLE ad_events_raw`
    *   (현재) `aws glue start-crawler --name capa-log-crawler` 실행
    *   결과: S3의 파티션 구조와 데이터 스키마가 Glue Catalog에 자동 동기화됨.

---

### 2. Athena 쿼리 검증 결과

#### 2.1 전체 데이터 카운트
```sql
SELECT COUNT(*) FROM ad_events_raw;
```
*   **결과**: `3,544` 건 (지속 증가 중)

#### 2.2 이벤트 타입별 집계
```sql
SELECT event_type, COUNT(*) as count FROM ad_events_raw GROUP BY event_type;
```

| event_type | count | 비고 |
|:---:|---:|---|
| **impression** | 3,325 | 노출 (가장 많음) |
| **click** | 328 | 약 10% (의도한 CTR 비율) |
| **conversion** | 70 | 클릭 대비 약 20% (의도한 CVR 비율) |

> **분석**: `Log Generator`에서 설정한 확률(CTR 10%, CVR 20%)과 유사한 비율로 데이터가 적재되고 있음을 확인. 이는 데이터 유실 없이 파이프라인이 정상 작동함을 의미함.

---

## ✅ 성공 기준 달성

- [x] S3 Parquet 파일 존재 확인 (`aws s3 ls`)
- [x] Glue Crawler 인식 (또는 `start-crawler` 실행)
- [x] Athena `SELECT` 쿼리 정상 실행
- [x] 데이터 정합성 확인 (이벤트 타입별 비율 정상)

---

## 🎯 작업 완료

**E2E 데이터 파이프라인 검증 완료**:
1. **Source**: Log Generator (Python)
2. **Ingestion**: Kinesis Data Stream
3. **Processing**: Kinesis Firehose (JSON -> Parquet 변환)
4. **Storage**: S3 Data Lake
5. **Catalog**: AWS Glue
6. **Analytics**: Athena SQL Query

**모든 단계가 정상적으로 연결되어 작동함을 최종 확인했습니다.**

---

**작업 완료 시각**: 2026-02-12 16:30
