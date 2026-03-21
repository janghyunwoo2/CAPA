# 2026-02-27 회의록 정리 및 보완안

## 1) 배경/목표
- 광고 데이터 파이프라인에서 로그(노출/클릭/전환)와 품질/이상탐지 로그를 실시간 수집·처리.
- Kinesis 스트림을 3개로 분리하고, 트래픽 증가 시 샤드를 단계적으로(+50 단위) 확장.
- 서로 다른 로그 특성에 맞춰 다중 소비자(이상탐지, 부정클릭 식별, 적재/요약) 운영.
- 실시간 처리와 장기 저장을 병행하고, Redash에서 현업이 즉시 활용 가능한 지표(CTR/CVR/CPA)를 시각화.

## 2) 요구사항 요약
- 스트림: 3개 (예: `ad-imp`, `ad-click`, `ad-cv`)
- 샤드: 트래픽 증가에 따라 증분 확장(예: +50 샤드 단위), 감소도 고려.
- 소비자 증가: 이상탐지, 부정클릭, 리포팅/요약 등 독립 처리.
- 로그 유형: 부정클릭, 보이드 클릭 등 품질 관련 이벤트 포함. imp → clk → cv 경로 기반 분석.
- 운영 모드: Kinesis On-demand(자동) vs Provisioned(수동) 선택 가능.
- IoT 유사 사례: 전봇대별 전력 사용량 요약처럼 캠페인/디바이스 단위 요약 병행.
- Redash: 도메인/세일즈가 쓰는 성과지표(CTR/CVR/CPA)를 시간 축(일/주/월)으로 시각화.
- 예시 질문: “2월 한달 간 캠페인 A의 일별 CTR, CVR, CPA 변화”

## 3) 제안 아키텍처(고수준)
- Producer
  - 앱/SDK(Log Generator)가 `ad-imp`/`ad-click`/`ad-cv`에 이벤트 송신
  - 파티션 키: 세션/디바이스/캠페인 해시 전략으로 고르게 분포
- Kinesis Streams (3개)
  - `ad-imp`: 노출
  - `ad-click`: 클릭(부정/보이드 플래그 포함)
  - `ad-cv`: 전환(구매/가입 등)
- Consumers (Enhanced Fan-Out 권장)
  - Fraud Detector: 부정/보이드 클릭 식별(특징 엔지니어링/룰·ML)
  - Anomaly Detector: 트래픽/지표 이상 탐지(예: Kinesis Data Analytics for Apache Flink/SQL)
  - Archiver: Firehose → S3(원천 로그 영속화, Athena/Glue 카탈로그)
  - Aggregator: 실시간/근실시간 요약 테이블 적재(Athena 외부 테이블 또는 DWH)
- Storage/Query
  - S3(Data Lake) + Athena(Ad-hoc/리포트), 필요 시 Redshift로 Mart 구성
  - Redash: Athena/Redshift 연결로 대시보드 구성

## 4) 샤드 스케일링 정책(예시)
- On-demand 권장: 버스티한 트래픽 시 운영 단순화. 비용/예측 가능성이 낮으면 적합.
- Provisioned 선택 시
  - 지표 모니터링: `WriteProvisionedThroughputExceeded`, `ReadProvisionedThroughputExceeded`, `IteratorAgeMilliseconds`
  - 목표: 샤드 당 평균 사용률 70% 전후 유지
  - 확장 규칙: 경보 연속 N분 초과 시 `UpdateShardCount(UNIFORM_SCALING)`으로 +50 샤드 증설
  - 축소 규칙: 낮은 부하가 충분 기간 지속 시 점진적 축소(스플릿/머지 계획 수립)
- 소비자 분리: EFO로 소비자 간 처리량 간섭 최소화

## 5) 데이터 모델: 요약 테이블 스펙(안)
- 테이블: `analytics.ad_campaign_daily_summary` (Athena/Glue 카탈로그)
- 파티션/키
  - 파티션: `event_date`(DATE) 파티셔닝
  - 키(개념상): `(event_date, campaign_id)`
- 컬럼
  - `event_date` DATE: 통계 기준 일자
  - `campaign_id` STRING: 캠페인 식별자
  - `campaign_name` STRING: 캠페인명(조인으로 채움 가능)
  - `channel` STRING NULLABLE: 매체/채널(google, meta, naver 등)
  - `impressions` BIGINT: 노출 수
  - `unique_impressions` BIGINT NULLABLE: 순노출 수(선택)
  - `clicks` BIGINT: 클릭 수(필터링 후 유효 클릭 기준 권장)
  - `unique_clicks` BIGINT NULLABLE: 순클릭 수(선택)
  - `conversions` BIGINT: 전환 수
  - `invalid_clicks` BIGINT NULLABLE: 부정 클릭 수
  - `void_clicks` BIGINT NULLABLE: 보이드 처리된 클릭 수
  - `cost` DOUBLE NULLABLE: 광고비(원/달러 등 통화 별도 관리)
  - `revenue` DOUBLE NULLABLE: 매출(선택)
  - `updated_at` TIMESTAMP: 적재/갱신 시간
- 파생 지표 정의(표현식)
  - $CTR = \frac{clicks}{impressions}$
  - $CVR = \frac{conversions}{clicks}$
  - $CPA = \frac{cost}{conversions}$
  - 분모 0 회피: `NULLIF` 또는 `CASE WHEN … THEN … END`

## 6) Redash 대시보드(예시)
- 차트 1: “캠페인 일별 CTR/CVR/CPA” (x: 날짜, y: CTR/CVR/CPA 다축 또는 멀티시리즈)
- 차트 2: “일별 노출/클릭/전환 추이” (막대/선 혼합)
- 필터: 캠페인, 날짜 범위, 채널, (필요 시) 디바이스/지역

## 7) SQL 예시: 2월 한달 간 캠페인 A의 일별 CTR/CVR/CPA

### A. Redash 파라미터 버전(Athena/Presto)
- Parameters: `start_date`(Date), `end_date`(Date), `campaign_name`(Text)
```sql
WITH base AS (
  SELECT
    event_date,
    campaign_id,
    campaign_name,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(conversions) AS conversions,
    SUM(cost) AS cost
  FROM analytics.ad_campaign_daily_summary
  WHERE event_date >= DATE '{{ start_date }}'
    AND event_date <  DATE '{{ end_date }}'
    AND campaign_name = '{{ campaign_name }}'
  GROUP BY 1,2,3
)
SELECT
  event_date,
  impressions,
  clicks,
  conversions,
  cost,
  CAST(clicks AS DOUBLE) / NULLIF(CAST(impressions AS DOUBLE), 0) AS ctr,
  CAST(conversions AS DOUBLE) / NULLIF(CAST(clicks AS DOUBLE), 0) AS cvr,
  CAST(cost AS DOUBLE) / NULLIF(CAST(conversions AS DOUBLE), 0) AS cpa
FROM base
ORDER BY event_date;
```
- 예시 파라미터: `start_date=2026-02-01`, `end_date=2026-03-01`, `campaign_name=캠페인 A`

### B. 고정 기간 예시(Athena/Presto)
```sql
WITH base AS (
  SELECT
    event_date,
    campaign_id,
    campaign_name,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(conversions) AS conversions,
    SUM(cost) AS cost
  FROM analytics.ad_campaign_daily_summary
  WHERE event_date >= DATE '2026-02-01'
    AND event_date <  DATE '2026-03-01'
    AND campaign_name = '캠페인 A'
  GROUP BY 1,2,3
)
SELECT
  event_date,
  impressions,
  clicks,
  conversions,
  cost,
  CAST(clicks AS DOUBLE) / NULLIF(CAST(impressions AS DOUBLE), 0) AS ctr,
  CAST(conversions AS DOUBLE) / NULLIF(CAST(clicks AS DOUBLE), 0) AS cvr,
  CAST(cost AS DOUBLE) / NULLIF(CAST(conversions AS DOUBLE), 0) AS cpa
FROM base
ORDER BY event_date;
```
- 퍼센트 표기 필요 시: `ctr*100 AS ctr_pct` 처럼 변환하여 사용.

## 8) 보완 포인트 / 오픈 쿼스천
- `invalid_clicks`/`void_clicks`의 정의 경계와 처리 시점(스트림 단계 vs 집계 단계)
- 지표 기준(유효 클릭 기준 CTR/CVR인지, 원천 클릭 포함인지) 통일
- 비용/통화 관리(원/달러, 환율 시점), 캠페인 단가/예산 테이블 필요 여부
- 캠페인 메타데이터 조인 방식(`dim_campaign` 관리 주체/동기화 주기)
- 샤드 증설 단위(+50)의 상한/하한, 자동화 람다 스로틀링·재시도 정책

## 9) 다음 액션(제안)
- (데이터) `ad_campaign_daily_summary` 스키마 확정 및 Glue 카탈로그/DDL 생성
- (파이프라인) Aggregator 소비자 구현(근실시간 집계) + S3 적재 파티셔닝 전략 확정
- (모니터링) Kinesis 지표 알람과 자동 증설 람다 배포(On-demand 전환 여부 평가)
- (리포팅) Redash 대시보드 1차 시안(CTR/CVR/CPA, 노출/클릭/전환) 작성 및 피드백
