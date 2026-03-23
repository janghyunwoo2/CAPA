# Redash 대시보드 구축 가이드

## 개요
본 가이드는 CAPA 프로젝트의 광고 성과 데이터를 효과적으로 시각화하기 위한 Redash 대시보드 구축 방법을 설명합니다.

## 목차
1. [데이터 구조 이해](#데이터-구조-이해)
2. [핵심 대시보드 구성](#핵심-대시보드-구성)
3. [대시보드 생성 단계별 가이드](#대시보드-생성-단계별-가이드)
4. [권장 시각화 차트](#권장-시각화-차트)
5. [모니터링 및 알림 설정](#모니터링-및-알림-설정)

---

## 데이터 구조 이해

### 주요 테이블
- **ad_combined_log**: 실시간 광고 이벤트 로그 (impression, click)
- **ad_hourly_summary**: 시간별 집계 데이터
- **ad_daily_summary**: 일별 집계 데이터  
- **ad_conversion_log**: 전환 이벤트 로그

### 핵심 지표
- **impressions**: 광고 노출수
- **clicks**: 클릭수
- **conversions**: 전환수
- **CTR (Click-Through Rate)**: 클릭률 = clicks / impressions × 100
- **CPC (Cost Per Click)**: 클릭당 비용
- **CVR (Conversion Rate)**: 전환율 = conversions / clicks × 100
- **CPA (Cost Per Acquisition)**: 전환당 비용

---

## 핵심 대시보드 구성

### 1. Executive Dashboard (경영진 대시보드)
- **목적**: 전체 광고 성과의 핵심 지표를 한눈에 파악
- **주요 구성요소**:
  - KPI 카드: 일별/주별/월별 총 노출수, 클릭수, 전환수
  - 트렌드 차트: 일별 CTR/CVR 추이
  - 비용 효율성: CPC/CPA 트렌드

### 2. Campaign Performance Dashboard (캠페인 성과 대시보드)
- **목적**: 개별 캠페인별 성과 분석
- **주요 구성요소**:
  - 캠페인별 성과 테이블
  - Top 10 캠페인 바 차트
  - 캠페인별 CTR 히트맵

### 3. Real-time Monitoring Dashboard (실시간 모니터링)
- **목적**: 실시간 광고 성과 모니터링
- **주요 구성요소**:
  - 최근 1시간 이벤트 카운트
  - 실시간 CTR 게이지
  - 이상 탐지 알림

### 4. Advertiser Analysis Dashboard (광고주 분석)
- **목적**: 광고주별 성과 분석 및 비교
- **주요 구성요소**:
  - 광고주별 매출 기여도
  - 광고주 성과 순위
  - 광고주별 ROI 분석

---

## 대시보드 생성 단계별 가이드

### Step 1: 데이터 소스 연결
1. Redash 관리자 페이지에서 "Data Sources" 클릭
2. "Add Data Source" → "Amazon Athena" 선택
3. 연결 정보 입력:
   ```
   AWS Access Key: [AWS Access Key ID]
   AWS Secret Key: [AWS Secret Access Key]
   AWS Region: ap-northeast-2
   S3 Staging (Query Results) Bucket: capa-data-lake
   Database: ad_analytics
   ```
4. "Test Connection" 후 저장

### Step 2: 쿼리 생성

#### 2.1 일별 핵심 지표 쿼리
```sql
-- Query Name: Daily Core Metrics
SELECT 
    date_format(date_parse(day, '%Y/%m/%d'), '%Y-%m-%d') as date,
    SUM(total_impressions) as impressions,
    SUM(total_clicks) as clicks,
    SUM(total_conversions) as conversions,
    ROUND(CAST(SUM(total_clicks) AS DOUBLE) / NULLIF(SUM(total_impressions), 0) * 100, 2) as ctr,
    ROUND(CAST(SUM(total_conversions) AS DOUBLE) / NULLIF(SUM(total_clicks), 0) * 100, 2) as cvr,
    ROUND(AVG(avg_cpc), 2) as avg_cpc
FROM ad_daily_summary
WHERE date_parse(day, '%Y/%m/%d') >= current_date - interval '30' day
GROUP BY 1
ORDER BY 1 DESC
```

#### 2.2 캠페인별 성과 쿼리
```sql
-- Query Name: Campaign Performance
SELECT 
    campaign_id,
    campaign_name,
    SUM(total_impressions) as impressions,
    SUM(total_clicks) as clicks,
    SUM(total_conversions) as conversions,
    ROUND(CAST(SUM(total_clicks) AS DOUBLE) / NULLIF(SUM(total_impressions), 0) * 100, 2) as ctr,
    ROUND(CAST(SUM(total_conversions) AS DOUBLE) / NULLIF(SUM(total_clicks), 0) * 100, 2) as cvr,
    ROUND(SUM(total_cost), 2) as total_cost,
    ROUND(SUM(total_cost) / NULLIF(SUM(total_clicks), 0), 2) as cpc,
    ROUND(SUM(total_cost) / NULLIF(SUM(total_conversions), 0), 2) as cpa
FROM ad_daily_summary
WHERE date_parse(day, '%Y/%m/%d') >= current_date - interval '7' day
GROUP BY 1, 2
ORDER BY impressions DESC
LIMIT 20
```

#### 2.3 실시간 모니터링 쿼리
```sql
-- Query Name: Realtime Metrics (Last Hour)
SELECT 
    date_format(from_unixtime(CAST(event_time/1000 AS BIGINT)), '%Y-%m-%d %H:%i') as minute,
    event_type,
    COUNT(*) as event_count
FROM ad_combined_log
WHERE date_format(from_unixtime(CAST(event_time/1000 AS BIGINT)), '%Y-%m-%d %H') = 
      date_format(current_timestamp, '%Y-%m-%d %H')
GROUP BY 1, 2
ORDER BY 1 DESC
```

### Step 3: 시각화 생성

#### 3.1 KPI 카드 생성
1. 쿼리 실행 후 "New Visualization" 클릭
2. "Counter" 선택
3. Value Column: 원하는 지표 선택 (예: impressions)
4. "Counter Label" 설정 (예: "총 노출수")
5. "Format" 탭에서 숫자 포맷 설정 (천 단위 구분)

#### 3.2 트렌드 차트 생성
1. "Line Chart" 선택
2. X축: date
3. Y축: 원하는 지표들 (ctr, cvr 등)
4. "Series" 탭에서 각 지표별 색상 지정
5. "Y Axis" 탭에서 단위 설정 (%, 원 등)

#### 3.3 히트맵 생성
1. "Heatmap" 선택
2. X축: hour 또는 day_of_week
3. Y축: campaign_id
4. Value: ctr 또는 다른 지표
5. Color Scheme 선택

### Step 4: 대시보드 구성

#### 4.1 새 대시보드 생성
1. "Dashboards" → "New Dashboard"
2. 대시보드 이름 입력 (예: "광고 성과 Executive Dashboard")
3. "Add Widget" 클릭

#### 4.2 위젯 배치
1. 생성한 시각화들을 드래그&드롭으로 추가
2. 권장 레이아웃:
   ```
   [KPI 카드들 - 상단 한 줄]
   [트렌드 차트 - 중앙 큰 영역]
   [테이블/히트맵 - 하단]
   ```
3. 위젯 크기 조정 (모서리 드래그)
4. "Done Editing" 클릭

---

## 권장 시각화 차트

### 1. KPI 모니터링
- **Counter**: 핵심 지표 단일 값 표시
- **Gauge**: CTR, CVR 등 비율 지표 표시

### 2. 트렌드 분석
- **Line Chart**: 시계열 데이터 추이
- **Area Chart**: 누적 지표 표시
- **Column Chart**: 기간별 비교

### 3. 비교 분석
- **Bar Chart**: 캠페인/광고주별 비교
- **Pie Chart**: 비중 분석
- **Scatter Plot**: 상관관계 분석

### 4. 상세 분석
- **Table**: 상세 데이터 조회
- **Heatmap**: 패턴 분석
- **Pivot Table**: 다차원 분석

---

## 모니터링 및 알림 설정

### 알림 설정 예시

#### 1. CTR 급감 알림
```sql
-- Alert Query: CTR Drop Detection
WITH hourly_ctr AS (
    SELECT 
        date_format(from_unixtime(CAST(event_time/1000 AS BIGINT)), '%Y-%m-%d %H') as hour,
        ROUND(CAST(SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS DOUBLE) / 
              NULLIF(SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END), 0) * 100, 2) as ctr
    FROM ad_combined_log
    WHERE from_unixtime(CAST(event_time/1000 AS BIGINT)) >= current_timestamp - interval '2' hour
    GROUP BY 1
)
SELECT 
    hour,
    ctr,
    CASE 
        WHEN ctr < 1.0 THEN 'CRITICAL'
        WHEN ctr < 1.5 THEN 'WARNING'
        ELSE 'OK'
    END as status
FROM hourly_ctr
ORDER BY hour DESC
LIMIT 1
```

#### 2. 알림 규칙 설정
1. Query 페이지에서 "Alerts" 탭 클릭
2. "Create Alert" 클릭
3. 조건 설정:
   - Value column: status
   - Condition: equals
   - Threshold: 'CRITICAL'
4. 알림 채널 설정 (이메일, Slack 등)
5. 실행 주기: Every 5 minutes

### 대시보드 자동 새로고침
1. 대시보드 편집 모드에서 "Settings" 클릭
2. "Refresh Rate" 설정:
   - 실시간 대시보드: 1분
   - 일별 대시보드: 1시간
   - 주간/월간 대시보드: 6시간

---

## 모범 사례

### 1. 성능 최적화
- 대용량 테이블은 파티션 활용
- 집계 테이블(summary) 우선 사용
- 쿼리 캐싱 활용 (TTL 설정)

### 2. 사용성 개선
- 명확한 대시보드/쿼리 네이밍
- 쿼리에 주석 추가
- 파라미터 활용으로 동적 대시보드 구성

### 3. 권한 관리
- 팀별 대시보드 폴더 구분
- 민감한 데이터는 권한 제한
- 정기적인 사용자 권한 검토

### 4. 유지보수
- 정기적인 쿼리 성능 모니터링
- 사용하지 않는 쿼리/대시보드 아카이빙
- 변경사항 문서화

---

## 문의사항
대시보드 구축 관련 문의사항은 데이터팀에 연락 바랍니다.
- Email: data-team@company.com
- Slack: #data-support