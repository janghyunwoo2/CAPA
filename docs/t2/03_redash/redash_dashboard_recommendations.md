# Redash 대시보드 추천 및 생성 매뉴얼

## 개요
이 문서는 CAPA 프로젝트에서 **Redash를 활용하여 어떤 대시보드를 만들면 좋을지**와, **실제로 Redash에서 대시보드를 만드는 방법**을 단계별로 정리한 매뉴얼입니다.

- **추천 대시보드**: 어떤 목적의 대시보드를 만들지 빠르게 파악
- **구성 요소**: 어떤 쿼리와 시각화가 필요한지
- **생성 방법**: Redash UI/쿼리/위젯을 직접 만드는 순서

---

## 1. 어떤 대시보드를 만들면 좋을까?
### 1.1 Executive Dashboard (경영진 대시보드)
- **목적**: 전체 광고 성과의 핵심 지표를 한눈에 파악
- **주요 지표**
  - 일/주/월별 **노출수(impressions)**, **클릭수(clicks)**, **전환수(conversions)**
  - **CTR/CVR** 트렌드
  - **CPC/CPA** 비용 효율성
- **권장 시각화**
  - KPI 카운터 (Counter) 4~6개
  - 시계열 라인 차트 (Line / Area)
  - 요약 테이블 (Table)

### 1.2 Campaign Performance Dashboard (캠페인 성과)
- **목적**: 캠페인별 성과를 비교/분석
- **주요 지표**
  - 캠페인별 노출/클릭/전환
  - 캠페인별 CTR/CVR
  - 캠페인별 비용 및 CPA
- **권장 시각화**
  - 캠페인별 순위 바 차트 (Bar)
  - 캠페인 성과 테이블 (Table)
  - CTR/CVR 히트맵 (Heatmap)

### 1.3 Real-time Monitoring Dashboard (실시간 모니터링)
- **목적**: 즉시 이상 징후 파악 및 빠른 대처
- **주요 지표**
  - 최근 1시간/1일 이벤트(노출/클릭/전환) 카운트
  - 실시간 CTR
  - 최대/평균 응답 지연 또는 데이터 지연
- **권장 시각화**
  - 실시간 이벤트 카운트 라인 차트
  - 메트릭 게이지(CTR, 처리량)
  - 최근 오류/경고 로그(테이블)

### 1.4 Advertiser/Publisher Analysis Dashboard (광고주/퍼블리셔 성과)
- **목적**: 광고주 및 퍼블리셔별 성과 비교
- **주요 지표**
  - 광고주/퍼블리셔별 노출/클릭/전환
  - 광고주별 ROI/CPA
  - 상위 광고주 및 하위 광고주 추적
- **권장 시각화**
  - 광고주별 매출 기여도 파이 차트
  - 순위형 바 차트
  - 상세 성과 테이블

---

## 2. 대시보드 생성 전 준비
### 2.1 Redash 접속 확인
1. Redash 외부 URL 확인
   ```bash
   kubectl get ingress -n redash
   ```
2. 브라우저에서 Redash URL 접속 후 정상 동작 확인

### 2.2 API 테스트 (Optional)
- Redash API를 직접 호출해보고 싶다면 `redash_api_test.md` 문서를 참고하세요.

### 2.3 (권장) Data Source 연결 확인
- Redash가 **Athena** 또는 다른 데이터 소스를 연결할 수 있어야 합니다.
- Athena의 경우, `data_sources` API 또는 UI에서 `type: athena`가 등록되어 있는지 확인합니다.

---

## 3. 대시보드 생성 순서 (매뉴얼)
### 3.1 1) 쿼리 생성
1. Redash 상단 메뉴에서 **Queries** → **New Query**
2. **Data Source**를 선택 (예: Athena)
3. 쿼리 작성 후 **Execute** 버튼으로 결과 확인
4. 결과가 정상이면 **Save** 후 쿼리 이름 설정

#### 3.1.1 추천 쿼리 예시 (일별 핵심 지표)
```sql
-- Query Name: Daily Core Metrics
SELECT
  date_format(date_parse(day, '%Y/%m/%d'), '%Y-%m-%d') AS date,
  SUM(total_impressions) AS impressions,
  SUM(total_clicks) AS clicks,
  SUM(total_conversions) AS conversions,
  ROUND(CAST(SUM(total_clicks) AS DOUBLE) / NULLIF(SUM(total_impressions), 0) * 100, 2) AS ctr,
  ROUND(CAST(SUM(total_conversions) AS DOUBLE) / NULLIF(SUM(total_clicks), 0) * 100, 2) AS cvr,
  ROUND(AVG(avg_cpc), 2) AS avg_cpc
FROM ad_daily_summary
WHERE date_parse(day, '%Y/%m/%d') >= current_date - interval '30' day
GROUP BY 1
ORDER BY 1 DESC
```

#### 3.1.2 추천 쿼리 예시 (캠페인별 성과)
```sql
-- Query Name: Campaign Performance
SELECT
  campaign_id,
  campaign_name,
  SUM(total_impressions) AS impressions,
  SUM(total_clicks) AS clicks,
  SUM(total_conversions) AS conversions,
  ROUND(CAST(SUM(total_clicks) AS DOUBLE) / NULLIF(SUM(total_impressions), 0) * 100, 2) AS ctr,
  ROUND(CAST(SUM(total_conversions) AS DOUBLE) / NULLIF(SUM(total_clicks), 0) * 100, 2) AS cvr,
  ROUND(SUM(total_cost), 2) AS total_cost,
  ROUND(SUM(total_cost) / NULLIF(SUM(total_clicks), 0), 2) AS cpc,
  ROUND(SUM(total_cost) / NULLIF(SUM(total_conversions), 0), 2) AS cpa
FROM ad_daily_summary
WHERE date_parse(day, '%Y/%m/%d') >= current_date - interval '7' day
GROUP BY 1, 2
ORDER BY impressions DESC
LIMIT 20
```

### 3.2 2) 시각화 생성
1. 쿼리 결과 오른쪽 상단에서 **New Visualization** 클릭
2. 시각화 타입 선택 (Line, Bar, Table, Counter 등)
3. 시각화 옵션 설정
   - X축/값 컬럼 지정
   - 필터, 정렬, 색상 등 설정
4. **Save** 클릭하여 시각화 저장

#### 3.2.1 KPI 카드 (Counter) 만들기
- 쿼리 결과에서 **New Visualization** → **Counter** 선택
- Value Column에 KPI 값(예: impressions) 선택
- Label 설정 (예: "총 노출수")
- 필요 시 포맷 옵션으로 소수점/천 단위 구분 설정

#### 3.2.2 시계열 차트 만들기
- **Line Chart** 또는 **Area Chart** 선택
- X축에 날짜/시간 컬럼 지정 (예: date)
- Y축에 지표 컬럼 지정 (예: ctr, cvr)
- Series를 추가해 여러 지표를 한 차트에 표시 가능

### 3.3 3) 대시보드 생성 및 구성
1. 상단 메뉴에서 **Dashboards** → **New Dashboard** 클릭
2. 대시보드 이름 입력 (예: "광고 성과 대시보드")
3. 대시보드 편집 모드에서 **Add Widget** 클릭
4. 생성한 시각화를 위젯으로 추가
5. 위젯 크기/위치 조정 후 **Done Editing** 클릭

---

## 4. 운영 시 주의점 및 팁
### 4.1 쿼리 성능
- 데이터가 커질수록 쿼리 응답이 느려지므로, **최근 30일 / 7일 등 기간 제한**을 두는 것이 좋습니다.
- 필요한 컬럼만 조회하고 불필요한 JOIN을 줄입니다.

### 4.2 쿼리 재사용
- **Query Snippets** 또는 **Query 복제(Duplicate)** 기능을 활용해 기본 쿼리를 복사한 후 필요한 부분만 수정합니다.

### 4.3 리포트 자동화
- Redash의 **Alerts** 기능을 활용해 특정 조건(예: CTR 급락 시) 발생 시 Slack 등으로 알림을 보낼 수 있습니다.
- **Schedule** 기능을 이용해 대시보드를 정기적으로 이메일로 전송할 수 있습니다.

---

## 5. 참고 문서
- `docs/t2/03_redash/redash_api_test.md` (Redash API 직접 테스트 가이드)
- `docs/t2/03_redash/redash_dashboard_guide.md` (대시보드 구축 가이드)
