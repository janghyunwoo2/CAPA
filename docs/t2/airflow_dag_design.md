# Airflow DAG 설계: Hourly / Daily Summary

## 1. 설계 결정 사항

### Q1. 파일을 2개로 만들 것인가, 1개로 만들 것인가?

**결론: 2개 파일로 분리**

| 기준 | 1개 파일 | 2개 파일 (채택) |
|------|----------|----------------|
| schedule 관리 | 한 파일에 다른 주기 혼재 → 복잡 | 파일당 1 DAG, 주기 명확 |
| 배포/수정 | hourly 수정 시 daily에도 영향 | 독립적 배포 가능 |
| 모니터링 | Airflow UI에서 구분 어려움 | 개별 DAG 상태 확인 용이 |
| 커뮤니티 표준 | - | 파일당 1 DAG이 Airflow 표준 패턴 |

### Q2. 일 단위 summary 생성 전략

**비교 대상:**
- (A) 원천 로그 3개(impression, click, conversion)를 한번에 합침
- (B) hourly summary(impression+click) 재집계 + conversion만 원천에서 조인

**결론: (B) hourly summary 재집계 + conversion 조인**

| 기준 | (A) 원천 3개 한번에 | (B) hourly 재집계 + conversion (채택) |
|------|---------------------|--------------------------------------|
| Athena 스캔량 | 하루치 impression+click+conversion 전체 스캔 | hourly summary(소량) + conversion만 스캔 |
| 비용 | 높음 (대량 원천 데이터 재스캔) | **낮음** (이미 집계된 데이터 활용) |
| 속도 | 느림 | **빠름** (hourly summary는 24개 파티션, 집계 완료 상태) |
| 데이터 일관성 | 원천에서 직접 계산하므로 일관적 | hourly와 daily가 동일 소스 기반으로 일관적 |
| 중복 계산 | impression+click 조인을 다시 수행 | 조인은 hourly에서 이미 완료 |

### Q3. Conversion도 1시간 단위로 미리 summary할 것인가? (DAG 3개 체제)

**결론: 하지 않음 → DAG 2개 유지**

근거 (회의록 기반):
- **"CVR(전환율)은 시간 단위 집계에서는 적용 X"** — 시간 단위 conversion 집계는 비즈니스 의미가 없음
- **"전환 로그의 특성: 노출/클릭 대비 늦게 발생하는 경향"** — hourly로 자르면 데이터 누락 위험
- conversion 로그는 impression/click 대비 양이 매우 적음 (CVR 20% 가정 시 click의 20%)
- DAG 3개는 운영 복잡도만 증가시킴 (모니터링 포인트 증가, 의존성 관리 복잡)

## 2. 최종 아키텍처

### DAG 구성

| DAG ID | 파일 | 주기 | 역할 |
|--------|------|------|------|
| `ad_hourly_summary` | `ad_hourly_summary.py` | `@hourly` | impression + click → hourly summary |
| `ad_daily_summary` | `ad_daily_summary.py` | 매일 02:00 UTC | hourly summary 집계 + conversion 조인 → daily summary |

### 데이터 흐름

```
[실시간 수집]
Kinesis → Firehose → S3 raw/
  ├── event_type = 'impression'
  ├── event_type = 'click'
  └── event_type = 'conversion'

[매시간] ad_hourly_summary DAG
  S3 raw/ (impression + click만)
    → Athena CTAS: impression LEFT JOIN click (campaign_id, user_id 기준)
    → S3 summary/ad_hourly_summary/dt=YYYY-MM-DD-HH/ (Parquet + zstd)
    → Glue 파티션 등록

[매일 02:00] ad_daily_summary DAG
  1. ExternalTaskSensor: hourly DAG 완료 대기
  2. Athena CTAS:
     ├── hourly_summary 24개분 SUM 재집계 (소량, 빠름)
     └── conversion 원천 로그 COUNT (campaign_id 기준 LEFT JOIN)
  → S3 summary/ad_daily_summary/ds=YYYY-MM-DD/ (Parquet + zstd)
  → Glue 파티션 등록
  → report-generator 트리거
```

### S3 경로 구조

```
s3://capa-data-lake-827913617635/
├── raw/                                    ← Kinesis/Firehose 원천 로그
│   └── year=YYYY/month=MM/day=DD/
├── summary/
│   ├── ad_hourly_summary/                  ← hourly DAG 결과
│   │   ├── dt=2026-02-13-00/
│   │   ├── dt=2026-02-13-01/
│   │   └── ...
│   └── ad_daily_summary/                   ← daily DAG 결과
│       ├── ds=2026-02-13/
│       └── ds=2026-02-14/
└── athena-results/                         ← Athena 쿼리 결과 임시 저장
```

## 3. Hourly DAG 상세

### Task 구성

```
check_raw_data → create_hourly_summary → register_partition
```

| Task | 역할 | Operator |
|------|------|----------|
| `check_raw_data` | S3에 해당 시간 raw 데이터 존재 확인 | KubernetesPodOperator (aws-cli) |
| `create_hourly_summary` | Athena CTAS로 impression+click 조인 집계 | KubernetesPodOperator (boto3) |
| `register_partition` | Glue 테이블 파티션 등록 (MSCK REPAIR) | KubernetesPodOperator (boto3) |

### 핵심 SQL 로직

```sql
-- impression과 click을 조인하여 시간 단위 집계
SELECT
    imp.campaign_id,
    imp.device_type,
    '{dt}' AS dt,
    COUNT(DISTINCT imp.event_id)    AS impressions,
    COUNT(DISTINCT clk.event_id)    AS clicks,
    CASE
        WHEN COUNT(DISTINCT imp.event_id) > 0
        THEN CAST(COUNT(DISTINCT clk.event_id) AS DOUBLE)
             / CAST(COUNT(DISTINCT imp.event_id) AS DOUBLE) * 100
        ELSE 0.0
    END AS ctr,
    SUM(imp.bid_price)              AS total_bid_cost,
    AVG(imp.bid_price)              AS avg_bid_price
FROM ad_events_raw AS imp
LEFT JOIN ad_events_raw AS clk
    ON imp.campaign_id = clk.campaign_id
    AND imp.user_id = clk.user_id
    AND clk.event_type = 'click'
WHERE imp.event_type = 'impression'
  AND imp.timestamp >= {start_ms}
  AND imp.timestamp <  {end_ms}
GROUP BY imp.campaign_id, imp.device_type
```

### 결과 테이블 스키마: `ad_hourly_summary`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| campaign_id | STRING | 캠페인 식별자 |
| device_type | STRING | 디바이스 (iOS/Android/Web) |
| dt | STRING | 시간 파티션 키 (YYYY-MM-DD-HH) |
| impressions | BIGINT | 노출 수 |
| clicks | BIGINT | 클릭 수 |
| ctr | DOUBLE | 클릭률 (%) |
| total_bid_cost | DOUBLE | 총 입찰 비용 |
| avg_bid_price | DOUBLE | 평균 입찰 단가 |

## 4. Daily DAG 상세

### Task 구성

```
wait_for_hourly_summary → create_daily_summary → register_partition → trigger_report
```

| Task | 역할 | Operator |
|------|------|----------|
| `wait_for_hourly_summary` | hourly DAG 23시분 완료 대기 | ExternalTaskSensor |
| `create_daily_summary` | hourly 재집계 + conversion 조인 | KubernetesPodOperator (boto3) |
| `register_partition` | Glue 테이블 파티션 등록 | KubernetesPodOperator (boto3) |
| `trigger_report` | report-generator 서비스 호출 | KubernetesPodOperator (curl) |

### 핵심 SQL 로직

```sql
-- hourly summary 재집계 + conversion 원천 조인
WITH hourly_agg AS (
    SELECT
        campaign_id,
        device_type,
        SUM(impressions)    AS impressions,
        SUM(clicks)         AS clicks,
        SUM(total_bid_cost) AS total_bid_cost
    FROM ad_hourly_summary
    WHERE dt >= '{ds}-00' AND dt <= '{ds}-23'
    GROUP BY campaign_id, device_type
),
conversion_agg AS (
    SELECT
        campaign_id,
        device_type,
        COUNT(DISTINCT event_id) AS conversions
    FROM ad_events_raw
    WHERE event_type = 'conversion'
      AND year = '{yyyy}' AND month = '{mm}' AND day = '{dd}'
    GROUP BY campaign_id, device_type
)
SELECT
    h.campaign_id,
    h.device_type,
    '{ds}' AS ds,
    h.impressions,
    h.clicks,
    COALESCE(c.conversions, 0)  AS conversions,
    -- CTR = clicks / impressions * 100
    CASE WHEN h.impressions > 0
        THEN CAST(h.clicks AS DOUBLE) / CAST(h.impressions AS DOUBLE) * 100
        ELSE 0.0 END AS ctr,
    -- CVR = conversions / clicks * 100
    CASE WHEN h.clicks > 0
        THEN CAST(COALESCE(c.conversions, 0) AS DOUBLE) / CAST(h.clicks AS DOUBLE) * 100
        ELSE 0.0 END AS cvr,
    h.total_bid_cost,
    CASE WHEN h.impressions > 0
        THEN h.total_bid_cost / CAST(h.impressions AS DOUBLE)
        ELSE 0.0 END AS avg_bid_price
FROM hourly_agg h
LEFT JOIN conversion_agg c
    ON h.campaign_id = c.campaign_id
    AND h.device_type = c.device_type
```

### 결과 테이블 스키마: `ad_daily_summary`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| campaign_id | STRING | 캠페인 식별자 |
| device_type | STRING | 디바이스 (iOS/Android/Web) |
| ds | STRING | 일 파티션 키 (YYYY-MM-DD) |
| impressions | BIGINT | 노출 수 |
| clicks | BIGINT | 클릭 수 |
| conversions | BIGINT | 전환 수 |
| ctr | DOUBLE | 클릭률 (%) |
| cvr | DOUBLE | 전환률 (%) |
| total_bid_cost | DOUBLE | 총 입찰 비용 |
| avg_bid_price | DOUBLE | 평균 입찰 단가 |

## 5. 비용 효율성 분석

### Athena 비용 비교 (하루 기준 추정)

가정: 원천 impression 로그 1일 = 10GB, click = 1GB, conversion = 0.2GB

| 전략 | 스캔량 | 비용 ($5/TB) |
|------|--------|-------------|
| (A) 원천 3개 한번에 | ~11.2 GB | $0.056 |
| (B) hourly 재집계 + conversion | ~0.05 GB (summary) + 0.2 GB (conversion) = ~0.25 GB | **$0.00125** |

→ **전략 (B)가 약 45배 저렴**

### DAG 개수 비교

| 구성 | DAG 수 | 장점 | 단점 |
|------|--------|------|------|
| 2개 (채택) | hourly(imp+clk) + daily | 운영 단순, 비용 최적 | - |
| 3개 | hourly(imp+clk) + hourly(conv) + daily | conversion hourly 존재 | 운영 복잡, conversion hourly 무의미 |

## 6. 운영 고려사항

### Idempotency (멱등성)
- CTAS + 임시 테이블 패턴: `DROP IF EXISTS → CTAS tmp → DROP tmp`
- S3 파티션 경로에 직접 적재하여 재실행 시 덮어쓰기

### 의존성 관리
- Daily DAG는 `ExternalTaskSensor`로 Hourly DAG 완료를 확인
- `mode="reschedule"`로 워커 슬롯을 점유하지 않고 대기

### 파티셔닝
- Hourly: `dt=YYYY-MM-DD-HH` (회의록의 `dt=2026-02-13T06` 형식 준수)
- Daily: `ds=YYYY-MM-DD`
- Parquet + zstd 압축 (회의록: "높은 압축률로 스토리지 비용 절감")

### 모니터링
- 각 DAG 독립적으로 Airflow UI에서 상태 확인
- 실패 시 2회 자동 재시도 (hourly: 5분 간격, daily: 10분 간격)
- report-generator를 통한 결과 알림

## 7. 관련 파일

| 파일 | 역할 |
|------|------|
| `services/airflow-dags/ad_hourly_summary.py` | Hourly DAG 구현 |
| `services/airflow-dags/ad_daily_summary.py` | Daily DAG 구현 |
| `services/airflow-dags/ad_performance_daily.py` | (DEPRECATED) 기존 DAG |
