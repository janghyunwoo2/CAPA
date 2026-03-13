# ETL 테이블 컬럼 설명서

**작성일**: 2026-03-12  
**버전**: 1.0

---

## 목차

1. [Raw Data 테이블](#raw-data-테이블)
   - [impressions](#impressions)
   - [clicks](#clicks)
   - [conversions](#conversions)

2. [Hourly Summary 테이블](#hourly-summary-테이블)
   - [ad_combined_log](#ad_combined_log)

3. [Daily Summary 테이블](#daily-summary-테이블)
   - [ad_combined_log_summary](#ad_combined_log_summary)

4. [파티션 스키마](#파티션-스키마)

---

## Raw Data 테이블

### impressions

**설명**: AWS Kinesis Data Firehose를 통해 실시간으로 수집되는 광고 노출(impression) 데이터

**S3 경로**: `s3://{bucket}/raw/impressions/`

**저장 형식**: Parquet (zstd 압축)

**파티션**: `year=/month=/day=/hour=/`

**생성 주기**: 실시간 (10분 단위로 파티셔닝)

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| impression_id | STRING | 광고 노출 고유 ID (PK) |
| user_id | STRING | 사용자 고유 ID |
| ad_id | STRING | 광고 고유 ID |
| campaign_id | STRING | 캠페인 고유 ID |
| advertiser_id | STRING | 광고주 고유 ID |
| platform | STRING | 플랫폼 (web, app 등) |
| device_type | STRING | 기기 타입 (mobile, desktop 등) |
| os | STRING | 운영체제 (iOS, Android, Windows 등) |
| delivery_region | STRING | 배송/서비스 지역 |
| user_lat | DOUBLE | 사용자 위도 |
| user_long | DOUBLE | 사용자 경도 |
| store_id | STRING | 가게/매장 ID |
| food_category | STRING | 음식 카테고리 (피자, 치킨 등) |
| ad_position | STRING | 광고 위치 (상단, 하단, 피드 등) |
| ad_format | STRING | 광고 포맷 (배너, 동영상, 캐러셀 등) |
| user_agent | STRING | 사용자 브라우저/앱 정보 |
| ip_address | STRING | 사용자 IP 주소 |
| session_id | STRING | 세션 고유 ID |
| keyword | STRING | 사용자 검색 키워드 (선택) |
| cost_per_impression | DOUBLE | 노출당 비용 (CPM) |
| timestamp | BIGINT | 노출 발생 시각 (Unix timestamp, ms) |
| year | STRING | 년도 (파티션 컬럼) |
| month | STRING | 월 (파티션 컬럼) |
| day | STRING | 일 (파티션 컬럼) |
| hour | STRING | 시간 (파티션 컬럼) |

**주요 특징**:
- 사용자의 광고 노출(view) 이벤트 기록
- 모든 광고 성과 측정의 기본이 되는 테이블
- 매일 정산/분석의 기준점

---

### clicks

**설명**: AWS Kinesis Data Firehose를 통해 실시간으로 수집되는 광고 클릭 데이터

**S3 경로**: `s3://{bucket}/raw/clicks/`

**저장 형식**: Parquet (zstd 압축)

**파티션**: `year=/month=/day=/hour=/`

**생성 주기**: 실시간 (10분 단위로 파티셔닝)

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| click_id | STRING | 클릭 고유 ID (PK) |
| impression_id | STRING | 해당 노출의 ID (FK to impressions) |
| click_position_x | INT | 클릭 X 좌표 (픽셀) |
| click_position_y | INT | 클릭 Y 좌표 (픽셀) |
| landing_page_url | STRING | 클릭 후 이동한 랜딩 페이지 URL |
| cost_per_click | DOUBLE | 클릭당 비용 (CPC) |
| timestamp | BIGINT | 클릭 발생 시각 (Unix timestamp, ms) |
| year | STRING | 년도 (파티션 컬럼) |
| month | STRING | 월 (파티션 컬럼) |
| day | STRING | 일 (파티션 컬럼) |
| hour | STRING | 시간 (파티션 컬럼) |

**주요 특징**:
- impressions 테이블과 LEFT JOIN으로 연결
- 같은 impression_id를 가진 click 레코드는 0개 또는 1개(impression_id는 고유)
- 클릭이 없는 노출도 impressions에만 존재

---

### conversions

**설명**: 고객이 광고 클릭 후 실제로 구매 또는 회원가입 등의 행동을 한 전환 데이터

**S3 경로**: `s3://{bucket}/raw/conversions/`

**저장 형식**: Parquet (zstd 압축)

**파티션**: `year=/month=/day=/`

**생성 주기**: 실시간 → 일단위 파티셔닝

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| conversion_id | STRING | 전환 고유 ID (PK) |
| impression_id | STRING | 해당 노출의 ID (FK to impressions) |
| conversion_type | STRING | 전환 타입 (purchase, signup, cart_add 등) |
| conversion_value | DOUBLE | 전환 가치 (매출액, 상품값 등) |
| product_id | STRING | 구매한 상품 ID |
| quantity | INT | 구매 수량 |
| attribution_window | STRING | 속성 기간 (며칠 내의 구매를 카운트할지) |
| timestamp | BIGINT | 전환 발생 시각 (Unix timestamp, ms) |
| year | STRING | 년도 (파티션 컬럼) |
| month | STRING | 월 (파티션 컬럼) |
| day | STRING | 일 (파티션 컬럼) |

**주요 특징**:
- 광고 ROI(Return On Investment) 측정의 핵심 테이블
- ad_combined_log_summary와 LEFT JOIN으로 연결
- attribution_window를 통해 노출 이후의 대기 기간 설정 가능

---

## Hourly Summary 테이블

### ad_combined_log

**설명**: `impressions` + `clicks`를 시간 단위로 LEFT JOIN하여 생성하는 조합 테이블  
매시간 해당 시간의 모든 노출과 그에 따른 클릭 정보를 통합

**생성 방식**: 
- 매시간 실행 (Airflow DAG)
- hourly_etl.py에서 생성
- 직전 시간의 데이터 처리
- 정각 15분 이후에 실행

**S3 경로**: `s3://{bucket}/summary/ad_combined_log/`

**저장 형식**: Parquet (snappy 압축)

**파티션**: `year=/month=/day=/hour=/`

**필드 개수**: 27개 (impression 20 + click 6 + flag 1)

| 섹션 | 컬럼명 | 타입 | 설명 |
|------|--------|------|------|
| **Impression** | impression_id | STRING | 광고 노출 고유 ID |
| | user_id | STRING | 사용자 ID |
| | ad_id | STRING | 광고 ID |
| | campaign_id | STRING | 캠페인 ID |
| | advertiser_id | STRING | 광고주 ID |
| | platform | STRING | 플랫폼 |
| | device_type | STRING | 기기 타입 |
| | os | STRING | 운영체제 |
| | delivery_region | STRING | 배송 지역 |
| | user_lat | DOUBLE | 사용자 위도 |
| | user_long | DOUBLE | 사용자 경도 |
| | store_id | STRING | 가게 ID |
| | food_category | STRING | 음식 카테고리 |
| | ad_position | STRING | 광고 위치 |
| | ad_format | STRING | 광고 포맷 |
| | user_agent | STRING | 사용자 에이전트 |
| | ip_address | STRING | IP 주소 |
| | session_id | STRING | 세션 ID |
| | keyword | STRING | 검색 키워드 |
| | cost_per_impression | DOUBLE | 노출당 비용 |
| | impression_timestamp | BIGINT | 노출 시각 |
| **Click** | click_id | STRING | 클릭 ID (NULL이 클릭이 없음을 의미) |
| | click_position_x | INT | 클릭 X 좌표 |
| | click_position_y | INT | 클릭 Y 좌표 |
| | landing_page_url | STRING | 랜딩 페이지 URL |
| | cost_per_click | DOUBLE | 클릭당 비용 |
| | click_timestamp | BIGINT | 클릭 시각 |
| **Flag** | is_click | BOOLEAN | 클릭 여부 (true/false) |
| **Partition** | year | STRING | 년도 |
| | month | STRING | 월 |
| | day | STRING | 일 |
| | hour | STRING | 시간 |

**조인 로직**:
```sql
impressions LEFT JOIN clicks
  ON impressions.impression_id = clicks.impression_id
  AND clicks.year = {year}
  AND clicks.month = {month}
  AND clicks.day = {day}
  AND clicks.hour = {hour}
```

**주요 특징**:
- `is_click = true`: 클릭된 노출 (click_id 포함)
- `is_click = false`: 클릭되지 않은 노출 (click_id = NULL)
- CTR(Click-Through Rate) 계산 기반 데이터
- daily_etl에 의존 (hourly 데이터 24개를 daily에서 집계)

---

## Daily Summary 테이블

### ad_combined_log_summary

**설명**: 24시간(전날)의 `ad_combined_log` (hourly 24건) + `conversions`를 LEFT JOIN하여 생성하는 최종 일일 집계 테이블  
노출, 클릭, 전환을 통합하여 일일 광고 성과를 종합 분석

**생성 방식**:
- 매일 실행 (Airflow DAG) 
- daily_etl.py에서 생성
- 전날 데이터 처리
- 매일 02:00에 실행 완료

**S3 경로**: `s3://{bucket}/summary/ad_combined_log_summary/`

**저장 형식**: Parquet (snappy 압축)

**파티션**: `year=/month=/day=/`

**필드 개수**: 35개 (impression 20 + click 6 + is_click 1 + conversion 7 + is_conversion 1)

| 섹션 | 컬럼명 | 타입 | 설명 |
|------|--------|------|------|
| **Impression** | impression_id | STRING | 광고 노출 고유 ID |
| | user_id | STRING | 사용자 ID |
| | ad_id | STRING | 광고 ID |
| | campaign_id | STRING | 캠페인 ID |
| | advertiser_id | STRING | 광고주 ID |
| | platform | STRING | 플랫폼 |
| | device_type | STRING | 기기 타입 |
| | os | STRING | 운영체제 |
| | delivery_region | STRING | 배송 지역 |
| | user_lat | DOUBLE | 사용자 위도 |
| | user_long | DOUBLE | 사용자 경도 |
| | store_id | STRING | 가게 ID |
| | food_category | STRING | 음식 카테고리 |
| | ad_position | STRING | 광고 위치 |
| | ad_format | STRING | 광고 포맷 |
| | user_agent | STRING | 사용자 에이전트 |
| | ip_address | STRING | IP 주소 |
| | session_id | STRING | 세션 ID |
| | keyword | STRING | 검색 키워드 |
| | cost_per_impression | DOUBLE | 노출당 비용 |
| | impression_timestamp | BIGINT | 노출 시각 |
| **Click** | click_id | STRING | 클릭 ID (NULL이 클릭이 없음을 의미) |
| | click_position_x | INT | 클릭 X 좌표 |
| | click_position_y | INT | 클릭 Y 좌표 |
| | landing_page_url | STRING | 랜딩 페이지 URL |
| | cost_per_click | DOUBLE | 클릭당 비용 |
| | click_timestamp | BIGINT | 클릭 시각 |
| **Click Flag** | is_click | BOOLEAN | 클릭 여부 (true/false) |
| **Conversion** | conversion_id | STRING | 전환 ID (NULL이 전환이 없음을 의미) |
| | conversion_type | STRING | 전환 타입 (purchase, signup 등) |
| | conversion_value | DOUBLE | 전환 가치(매출액) |
| | product_id | STRING | 구매 상품 ID |
| | quantity | INT | 구매 수량 |
| | attribution_window | STRING | 속성 기간 |
| | conversion_timestamp | BIGINT | 전환 시각 |
| **Conversion Flag** | is_conversion | BOOLEAN | 전환 여부 (true/false) |
| **Partition** | year | STRING | 년도 |
| | month | STRING | 월 |
| | day | STRING | 일 |

**조인 로직**:
```sql
ad_combined_log (24시간) LEFT JOIN conversions (같은 날짜)
  ON ad_combined_log.impression_id = conversions.impression_id
  AND conversions.year = {year}
  AND conversions.month = {month}
  AND conversions.day = {day}
```

**주요 특징**:
- `is_click = true`: 클릭된 노출 (클릭 비용 기반 광고)
- `is_click = false`: 클릭되지 않은 노출 (노출 비용 기반 광고)
- `is_conversion = true`: 전환이 발생한 노출 (ROI 측정 가능)
- `is_conversion = false`: 전환이 없는 노출
- ROI(Return On Investment) 계산 기반 데이터
- 광고주별, 캠페인별, 상품별 성과 분석에 사용

**성과 지표 계산**:
```
Impressions (노출): COUNT(DISTINCT impression_id)
Clicks (클릭): SUM(CASE WHEN is_click THEN 1 ELSE 0 END)
CTR (클릭률): Clicks / Impressions * 100
Conversions (전환): SUM(CASE WHEN is_conversion THEN 1 ELSE 0 END)
CVR (전환율): Conversions / Impressions * 100
Total Revenue (총 매출): SUM(conversion_value)
Total Cost (총 비용): SUM(cost_per_impression) + SUM(cost_per_click)
ROI: (Total Revenue - Total Cost) / Total Cost * 100
```

---

## 파티션 스키마

### Raw Data 파티션

**impressions, clicks**: `year=/month=/day=/hour=/`
- 시간 단위 파티션으로 미세한 시간대별 분석 가능
- 10분 단위로 데이터 누적

**conversions**: `year=/month=/day=/`
- 일 단위 파티션
- 특정 날의 전복 데이터 일괄 처리

### Summary 파티션

**ad_combined_log (hourly)**: `year=/month=/day=/hour=/`
- 시간 단위 집계 테이블
- 같은 형식의 raw data와 동일하게 파티셔닝

**ad_combined_log_summary (daily)**: `year=/month=/day=/`
- 일 단위 집계 테이블
- 가장 상위 수준의 집계

### 파티션 예시

```
s3://bucket/summary/ad_combined_log/
  ├── year=2026/month=03/day=10/hour=00/ad_combined_log.parquet
  ├── year=2026/month=03/day=10/hour=01/ad_combined_log.parquet
  ├── ...
  └── year=2026/month=03/day=10/hour=23/ad_combined_log.parquet

s3://bucket/summary/ad_combined_log_summary/
  ├── year=2026/month=03/day=10/ad_combined_log_summary.parquet
  ├── year=2026/month=03/day=11/ad_combined_log_summary.parquet
  └── ...
```

---

## 데이터 ETL 플로우

```
Raw Data (Kinesis Firehose) 
│
├─→ S3/raw/impressions/ ────────────┐
│                                    │
├─→ S3/raw/clicks/ ──────────────────┼─→ [Hourly ETL] ─→ S3/summary/ad_combined_log/
│                                    │
└─→ S3/raw/conversions/ ────────────┼──────────────────────┐
                                     │                      │
                    [매시간 실행]    │                      │
                    04분/시간마다    │                      │
                                     │      [Daily ETL]     │
                                     └──→ (매일 02:00) ─→ S3/summary/ad_combined_log_summary/
```

---

## 데이터 타입 정리

| 타입 | 용도 | 예시 |
|------|------|------|
| STRING | ID, 텍스트, 주소 | user_id, session_id, platform |
| INT | 작은 정수, 좌표 | click_position_x, quantity |
| BIGINT | 큰 정수, 타임스탬프 | timestamp (1ms = 1000000 ns) |
| DOUBLE | 부동소수점, 금액 | cost_per_impression, conversion_value |
| BOOLEAN | 참/거짓 | is_click, is_conversion |

---

## 참고사항

1. **타임스탬프**: Unix timestamp (milliseconds) 형식으로 저장
2. **파티션 컬럼**: 쿼리 성능 향상을 위해 WHERE 절에 반드시 포함 권장
3. **NULL 값**: LEFT JOIN 시 클릭/전환이 없으면 해당 컬럼이 NULL
4. **압축**: 저장 공간 절감 및 쿼리 성능 향상을 위해 Parquet 사용
5. **향후 확장**: weekly, monthly 집계 테이블 추가 계획 중

---

**작성자**: Data Pipeline Team  
**최종 수정**: 2026-03-12  
**상태**: Active
