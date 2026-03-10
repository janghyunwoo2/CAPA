# CAPA 프로젝트 데이터 분석 플랫폼 평가 보고서
## Report Generator vs Redash 아키텍처 검토 및 최종 추천

**작성일**: 2026-03-04
**팀**: T3 (배포/운영)
**참여자**: 데이터 분석가, 기술 아키텍처, 보고서 작성가

---

## Executive Summary

CAPA 배달앱 광고 로그 분석 플랫폼은 현재 두 가지 분석 도구가 구성되어 있습니다:

1. **Report Generator** (운영 중): Slack 봇 기반 자동 PDF 보고서 생성
2. **Redash** (배포 완료, 미사용): Helm/Kubernetes 기반 SQL 대시보드

본 보고서는 이 두 도구의 역할을 평가하고 **통합 운영 전략**을 제시합니다.

### 핵심 결론

| 항목 | 추천사항 |
|---|---|
| **운영 전략** | **둘 다 유지, 역할 분리** |
| **Redash** | 일상적 모니터링/탐색 대시보드로 활용 |
| **Report Generator** | 정기 공식 보고서(주간/월간) 생성 도구 |
| **우선순위** | Redash 활성화 (우선), Report Generator 버그 수정 (차순) |

---

## 1. 데이터 분석가 관점: 광고 지표 분석

### 1.1 광고 성과 측정 체계

배달앱 광고 플랫폼의 광고 성과는 다음 4계층 지표로 측정됩니다:

#### **Layer 1: 코어 효율 지표**

| 지표 | 공식 | 의미 | 현재 상태 |
|---|---|---|---|
| **CTR** (Click-Through Rate) | clicks / impressions × 100 | 광고 노출 후 클릭 비율 | ✅ Report Generator에서 계산 |
| **CVR** (Conversion Rate) | conversions / clicks × 100 | 클릭 후 전환 비율 | ✅ Report Generator에서 계산 |
| **CPC** (Cost Per Click) | SUM(cpc_cost) / clicks | 클릭당 평균 비용 | ✅ Report Generator에서 계산 |
| **ROAS** (Return on Ad Spend) | SUM(total_amount) / SUM(cpc_cost) × 100 | 광고비 대비 수익률 | ❌ **누락됨** |

#### **Layer 2: 카테고리별 성과**

CAPA의 광고 카테고리별 클릭율 벤치마크 (generator.py 기준):

```
분식:   CTR 9.0% (최고)
치킨:   CTR 8.0%
피자:   CTR 7.0%
한식:   CTR 6.0%
중식:   CTR 6.0%
카페:   CTR 5.0% (최저)
```

**분석 포인트**: 카페의 CTR이 현저히 낮음 → 광고 소재 또는 타겟팅 최적화 필요

#### **Layer 3: Shop 성과 분석**

각 음식점별(shop_id) 광고 효율 측정:
- Top performers: 높은 ROAS, 안정적인 CTR
- Problem shops: 낮은 CTR, 높은 비용 대비 저수익

#### **Layer 4: 이벤트 퍼널 분석**

전환 경로 추적:
```
노출(Impression)
    ↓ CTR
클릭(Click)
    ↓ CVR (3가지 유형)
메뉴 조회(view_menu) - 55% 가중치
장바구니(add_to_cart) - 30% 가중치
주문(order) - 15% 가중치
```

### 1.2 현재 Report Generator의 분석 내용

Report Generator의 `athena_client.py`는 다음 4가지 Athena 쿼리를 실행합니다:

1. **daily_summary** → 일별 impression/click/conversion
2. **kpi_summary** → 전체 KPI (CTR, CVR, CPC)
3. **category_performance** → 카테고리별 성과
4. **shop_performance** → Shop별 성과

생성된 PDF 보고서의 섹션:
- Executive Summary (경영진 요약)
- 주요 지표 분석
- 일별 트렌드
- 카테고리별 성과
- Shop별 성과
- 인사이트 및 추천사항 (Claude LLM으로 자동 생성)

### 1.3 발견된 문제점 및 개선안

#### **문제 1: ROAS 지표 누락**

현재 Report Generator의 `query_kpi_summary()`는 ROAS를 계산하지 않습니다.

```python
# 현재 구현 (athena_client.py)
SELECT
    COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
    COUNT(CASE WHEN event_type = 'click' THEN 1 END) AS clicks,
    COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) AS conversions,
    ...
    # ROAS = SUM(total_amount) / SUM(cpc_cost) × 100 누락!

# 개선안
SUM(CASE WHEN event_type = 'conversion' THEN total_amount ELSE 0 END) AS total_revenue,
ROUND(
    SUM(CASE WHEN event_type = 'conversion' THEN total_amount ELSE 0 END)
    / NULLIF(SUM(CASE WHEN event_type = 'click' THEN cpc_cost ELSE 0 END), 0) * 100,
    1
) AS roas_pct
```

**영향도**: 광고 효율 평가의 가장 중요한 지표가 누락되어 있음

#### **문제 2: Shop 성과에서 user_id vs shop_id 혼동**

```python
# 현재 (athena_client.py 라인 ~250)
def query_shop_performance(self, start_date, end_date):
    query = f"""
        SELECT user_id, ...  ← 잘못됨! 광고를 클릭한 사용자 기준
        GROUP BY user_id
    """

# 올바른 구현
def query_shop_performance(self, start_date, end_date):
    query = f"""
        SELECT shop_id, ...  ← 광고를 게재한 음식점 기준
        GROUP BY shop_id
    """
```

**영향도**: Shop 성과 분석이 전혀 다른 의미의 데이터를 표시

### 1.4 Redash 활용 시 추적할 추가 지표

Redash 대시보드를 통해 Report Generator에서 다루지 못하는 지표들을 추적 가능:

#### **Device 타입별 성과**
```sql
SELECT device_type,
       COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
       COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
       ROUND(100.0 * clicks / NULLIF(impressions, 0), 2) AS ctr_pct
FROM ad_events_raw
GROUP BY device_type
```

**가치**: 모바일 vs PC 광고 성과 비교

#### **시간대별 트래픽 패턴**
```sql
SELECT DATE_FORMAT(from_unixtime(timestamp/1000), '%H:00') AS hour,
       COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions
FROM ad_events_raw
WHERE CAST(year AS int) = YEAR(CURRENT_DATE)
  AND CAST(month AS int) = MONTH(CURRENT_DATE)
  AND CAST(day AS int) = DAY(CURRENT_DATE)
GROUP BY hour
ORDER BY hour
```

**가치**: 피크 시간대 파악 → 예산 배치 최적화

#### **전환 퍼널 (5단계)**
```
Impression(100%)
    ↓ (CTR ~7%)
Click(7%)
    ↓ (CVR ~3%)
view_menu(2%)
add_to_cart(1.5%)
order(0.5%)
```

---

## 2. 기술 아키텍처 관점: Report Generator vs Redash 평가

### 2.1 아키텍처 현황

#### **CAPA 데이터 플로우**

```
광고 로그 생성
    ↓ (Kinesis Stream)
S3 Data Lake (Parquet, year/month/day 파티션)
    ↓ (Glue Crawler)
Athena + Glue Catalog (capa_db.ad_events_raw)
    ↓ (Airflow DAG)
ad_hourly_summary (매시간 생성)
ad_daily_summary (매일 02:00 UTC)
    ↓
┌─────────────────────────────────────┐
│ Redash (웹 대시보드)                │
│ Vanna API (Text-to-SQL)             │
│ Report Generator (Slack PDF)        │
└─────────────────────────────────────┘
```

### 2.2 Report Generator 기술 스펙

**배포 환경**: AWS EKS (Kubernetes)

**구성요소**:
```
bot.py (Slack Socket Mode + FastAPI)
    ├── athena_client.py (Athena 쿼리)
    ├── report_writer.py (Claude LLM)
    ├── pdf_exporter.py (PDF 생성)
    └── requirements.txt (Python 의존성)
```

**기술 스택**:
- **Slack 연동**: slack-bolt (Socket Mode)
- **LLM**: Anthropic Claude (claude-sonnet-4-5-20250929)
- **데이터**: AWS Athena + boto3
- **PDF 생성**: ReportLab + matplotlib
- **한글 지원**: NanumGothic 폰트 (Docker 환경)

**특징**:
- 온디맨드 실행 (Slack 멘션 트리거)
- 최근 30일 고정 기간 (코드 수정 필요)
- 자연어 해석 보고서 (Claude API의 이해도 높음)
- PDF로 공유 가능 (Slack, 이메일 등)

**리소스 사용**:
- CPU: ~200m (대기 중)
- Memory: ~512Mi
- 24/7 Socket Mode 유지

### 2.3 Redash 기술 스펙

**배포 상태**: Helm v3.0.0으로 EKS에 배포 완료

**구성요소** (helm-values/redash.yaml 기준):
```
redash-server (웹 UI)
    ├── PostgreSQL (메타데이터, 2Gi PVC)
    ├── Redis (캐시)
    ├── scheduler (쿼리 스케줄)
    ├── adhocWorker (임시 쿼리)
    ├── scheduledWorker (정기 쿼리)
    └── genericWorker (일반 작업)
```

**기술 스택**:
- **언어**: Python 기반 (서버), React 기반 (프론트엔드)
- **DB**: PostgreSQL (설정 저장)
- **캐시**: Redis
- **Athena**: IRSA 권한 완전 구성

**특징**:
- SQL 기반 쿼리 (드릴다운 분석 가능)
- 웹 UI (대시보드 자유 구성)
- 자동 갱신 설정 (분/시간/일 단위)
- 내장 Alert 기능 (이상 탐지)
- 쿼리 결과 공유 가능 (URL)

**리소스 사용** (최대 제한값):
```
server:          CPU 700m,   Memory 768Mi
scheduler:       CPU 200m,   Memory 256Mi
adhocWorker:     CPU 200m,   Memory 256Mi
scheduledWorker: CPU 200m,   Memory 256Mi
genericWorker:   CPU 200m,   Memory 256Mi
PostgreSQL:      CPU 200m,   Memory 512Mi
Redis:           CPU 100m,   Memory 128Mi
───────────────────────────────────────────
합계:            CPU 1.8core Memory 2.3Gi
```

### 2.4 비용 비교 분석

#### **AWS 비용 (Athena 쿼리)**

**Report Generator**:
- 1회 요청 = 4개 쿼리 실행
- 데이터 스캔: 파티션 활용으로 최적화 (year/month/day)
- 약 $0.01-0.02 per request

**Redash**:
- 대시보드 새로고침 = 3-5개 쿼리 자동 실행
- 스케줄 설정 시 지속적 비용 발생
- 월간: $5-15 (사용 패턴에 따라 가변)

#### **EKS 컴퓨팅 비용**

**Report Generator**:
- 상시 메모리: ~512Mi
- Karpenter Spot 노드에 배치 가능 (70% 할인)
- 월간: ~$10-15

**Redash**:
- 상시 메모리: ~1.15Gi + PVC 2Gi
- Core 노드에 배치 필요
- 월간: ~$40-50

### 2.5 기술 특성 비교 매트릭스

| 평가항목 | Report Generator | Redash |
|---|---|---|
| **초기 설정 복잡도** | 낮음 | 중간 |
| **운영 복잡도** | 낮음 | 높음 (5개 컴포넌트) |
| **월간 인프라 비용** | $15-25 | $45-65 |
| **Athena 쿼리 비용** | 낮음 (온디맨드) | 중간 (자동) |
| **탐색적 분석 가능성** | 제한적 (고정 4개 쿼리) | 높음 (SQL 자유) |
| **기간 변경 용이성** | 어려움 (코드 수정) | 쉬움 (파라미터) |
| **인사이트 품질** | 높음 (LLM) | 낮음 (숫자만) |
| **사용자 접근성** | 높음 (Slack) | 낮음 (웹 URL) |
| **알림 기능** | 없음 | 내장 (조건부) |
| **버전 관리** | Git | PostgreSQL (외부 관리 필요) |
| **실시간성** | 저 (요청 시점) | 높음 (자동 갱신) |

---

## 3. 최종 추천사항 및 실행 계획

### 3.1 아키텍처 결정

#### **추천 전략: 이중 구조 (Dual-Layer Architecture)**

```
[운영 레이어 - Redash]
    목적: 일상적 KPI 모니터링
    사용자: 데이터 팀, 마케팅 팀
    주기: 자동 갱신 (5분/1시간/1일)
    접근: 웹 대시보드

[보고 레이어 - Report Generator]
    목적: 공식 주간/월간 보고서
    사용자: 경영진, 이해관계자
    주기: 온디맨드 (Slack 요청)
    접근: Slack 채널
```

**이유**:

1. **인프라 재활용**: Redash는 이미 배포 완료, 철거 비용 불필요
2. **비용 효율**: 월간 ~$10-15 추가 비용만으로 모니터링 기능 확보
3. **기능 보완**: Report Generator의 ROAS 계산, shop 분석 오류 보완 가능
4. **운영 분리**: 모니터링과 보고서 생성 역할 분명화

### 3.2 우선순위별 실행 계획

#### **우선순위 1: Redash 즉시 활성화** (1주일 소요)

이미 배포되어 있으므로 추가 인프라 작업 없음.

**작업 목록**:

1. **Redash 웹 UI 접속**
   ```bash
   kubectl port-forward svc/redash 5000:5000 -n redash
   # http://localhost:5000 접속
   ```

2. **Athena 데이터소스 연결**
   - IRSA 권한 이미 구성 (terraform/02-iam.tf 확인 완료)
   - Connection String: `awsathena://827913617635@us-east-1/?s3_staging_dir=s3://capa-logs-dev-ap-northeast-2/redash-results/`

3. **쿼리 등록** (4개)

   **쿼리 1: 실시간 KPI 요약**
   ```sql
   SELECT
       COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
       COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
       ROUND(100.0 * clicks / NULLIF(impressions, 0), 2) AS ctr_pct,
       SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END) AS revenue
   FROM capa_db.ad_events_raw
   WHERE year || '-' || lpad(month, 2, '0') || '-' || lpad(day, 2, '0') = '{{ date }}'
   ```

   **쿼리 2: 카테고리별 성과 (ROAS 포함)**
   ```sql
   SELECT
       campaign_id,
       COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
       COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
       ROUND(100.0 * clicks / NULLIF(impressions, 0), 2) AS ctr_pct,
       ROUND(SUM(CASE WHEN event_type='conversion' THEN total_amount ELSE 0 END)
           / NULLIF(SUM(CASE WHEN event_type='click' THEN cpc_cost ELSE 0 END), 0) * 100, 1) AS roas_pct
   FROM capa_db.ad_events_raw
   WHERE year || '-' || lpad(month, 2, '0') || '-' || lpad(day, 2, '0')
         BETWEEN '{{ start_date }}' AND '{{ end_date }}'
   GROUP BY campaign_id
   ORDER BY roas_pct DESC NULLS LAST
   ```

   **쿼리 3: 시간대별 볼륨**
   ```sql
   SELECT
       DATE_FORMAT(from_unixtime(timestamp/1000), '%H:00') AS hour,
       COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
       COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks
   FROM capa_db.ad_events_raw
   WHERE year='{{ year }}' AND month='{{ month }}' AND day='{{ day }}'
   GROUP BY hour
   ORDER BY hour
   ```

   **쿼리 4: 전환 퍼널**
   ```sql
   SELECT
       shop_id,
       COUNT(CASE WHEN event_type='impression' THEN 1 END) AS impressions,
       COUNT(CASE WHEN event_type='click' THEN 1 END) AS clicks,
       COUNT(CASE WHEN conversion_type='order' THEN 1 END) AS orders
   FROM capa_db.ad_events_raw
   WHERE year || '-' || lpad(month, 2, '0') || '-' || lpad(day, 2, '0')
         BETWEEN '{{ start_date }}' AND '{{ end_date }}'
   GROUP BY shop_id
   HAVING COUNT(CASE WHEN event_type='impression' THEN 1 END) > 100
   ORDER BY orders DESC
   LIMIT 20
   ```

4. **대시보드 3개 구성**
   - Dashboard 1: "운영 현황" (카드 + 라인 차트)
   - Dashboard 2: "캠페인 분석" (테이블 + 트렌드)
   - Dashboard 3: "Shop 성과" (순위 테이블 + 퍼널)

5. **Alert 3개 설정**
   - Alert 1: impression 급락 (전주 대비 50% 이하)
   - Alert 2: CTR 급락 (카테고리 평균 대비 50% 이하)
   - Alert 3: 비용 급등 (전주 평균 대비 200% 초과)

#### **우선순위 2: Report Generator 버그 수정** (1주일 소요)

**버그 1: Shop 성과 분석 오류 수정**

파일: `services/report-generator/t3_report_generator/athena_client.py`

```python
# 현재 (라인 ~249-259)
def query_shop_performance(self, start_date, end_date):
    query = f"""
        SELECT
            user_id,  # ← 잘못됨
            COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
            ...
        FROM {self.database}.{self.table}
        WHERE {date_condition}
        GROUP BY user_id
    """

# 수정안
def query_shop_performance(self, start_date, end_date):
    query = f"""
        SELECT
            shop_id,  # ← 올바름
            COUNT(CASE WHEN event_type = 'impression' THEN 1 END) AS impressions,
            ...
        FROM {self.database}.{self.table}
        WHERE {date_condition}
        GROUP BY shop_id
    """
```

**버그 2: ROAS 지표 추가**

파일: `services/report-generator/t3_report_generator/athena_client.py`

```python
# query_kpi_summary() 함수의 SELECT에 추가
SELECT
    ...기존 지표들...
    SUM(CASE WHEN event_type = 'conversion' THEN total_amount ELSE 0 END) AS total_revenue,
    ROUND(
        SUM(CASE WHEN event_type = 'conversion' THEN total_amount ELSE 0 END)
        / NULLIF(SUM(CASE WHEN event_type = 'click' THEN cpc_cost ELSE 0 END), 0) * 100,
        1
    ) AS roas_pct
FROM ...
```

**검증**:
```bash
# Athena에서 직접 shop_id 집계 확인
SELECT shop_id, COUNT(*) FROM capa_db.ad_events_raw
WHERE year='2026' AND month='03' AND day='04'
GROUP BY shop_id
LIMIT 10;

# Report Generator 실행
@Bot 리포트
# 생성된 PDF에서 "Shop별 성과" 섹션 확인
```

#### **우선순위 3: Report Generator 기간 파라미터 개선** (2주일 소요)

파일: `services/report-generator/t3_report_generator/bot.py`

현재: `datetime.now() - timedelta(days=30)` (고정값)

개선:
```python
def _parse_date_range(text):
    """Slack 메시지에서 기간 파싱"""
    if "7일" in text:
        days = 7
    elif "14일" in text:
        days = 14
    elif "월간" in text or "1월" in text or "2월" in text:
        # 월별 첫날~마지막날 계산
        pass
    else:
        days = 30  # 기본값

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date
```

### 3.3 운영 가이드라인

#### **Redash 사용 시나리오**

**매일 아침**:
1. Redash "운영 현황" 대시보드 확인
2. CTR/CVR 이상 여부 점검
3. Alert 확인 (이상 탐지)

**주 1회**:
1. "캠페인 분석" 대시보드에서 ROAS 추이 확인
2. 하위 성과 카테고리 드릴다운 분석

**월 1회**:
1. Report Generator로 공식 월간 보고서 생성
2. 경영진 보고

#### **Alert 처리 절차**

| Alert | 원인 | 대응 |
|---|---|---|
| Impression 급락 | 로그 파이프라인 장애 또는 트래픽 급감 | log-generator, Kinesis 상태 확인 |
| CTR 급락 | 광고 소재 품질 저하 또는 타겟팅 오류 | A/B 테스트, 입찰가 조정 검토 |
| 비용 급등 | 입찰가 설정 오류 또는 비정상 트래픽 | bid_price 분포 확인, cap 설정 |

### 3.4 기대 효과

| 측면 | 기대 효과 |
|---|---|
| **모니터링** | 실시간 KPI 대시보드 제공 → 신속한 이슈 대응 |
| **분석 깊이** | ROAS, 전환 퍼널 등 추가 지표 확보 → 의사결정 정보 품질 향상 |
| **운영 효율** | Alert 자동화 → 수동 모니터링 시간 감소 |
| **비용** | Redash 활용 시 월간 ~$10 추가 비용으로 모니터링 기능 확보 |

---

## 4. 구현 로드맵

```
Week 1  │ Redash 활성화 (쿼리 등록, 대시보드 3개, Alert 3개)
────────┼─────────────────────────────────────────────
Week 2  │ Report Generator 버그 수정 (shop_id, ROAS 계산)
────────┼─────────────────────────────────────────────
Week 3  │ 기간 파라미터 개선, 문서화
────────┼─────────────────────────────────────────────
Week 4  │ 팀 교육, 운영 가이드라인 배포
```

---

## 5. 부록: 기술 명세

### 5.1 데이터 스키마

**테이블**: `capa_db.ad_events_raw`

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| event_id | string | 이벤트 UUID |
| event_type | string | impression / click / conversion |
| timestamp | bigint | Unix milliseconds |
| campaign_id | string | 캠페인(카테고리) ID |
| shop_id | string | 음식점 ID |
| user_id | string | 사용자 UUID |
| device_type | string | 모바일 / PC |
| bid_price | double | Impression당 입찰가 |
| cpc_cost | double | Click당 실제 비용 |
| ad_id | string | 광고 ID |
| conversion_type | string | view_menu / add_to_cart / order |
| total_amount | double | 전환 금액 |
| year, month, day | string | 파티션 키 |

### 5.2 환경 변수 (Report Generator)

```ini
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# AWS
AWS_REGION=ap-northeast-2
ATHENA_S3_OUTPUT=s3://capa-logs-dev-ap-northeast-2/athena-results/

# Glue
GLUE_DATABASE=capa_db
GLUE_TABLE=ad_events_raw
```

### 5.3 Kubernetes 배포 확인

```bash
# Report Generator
kubectl get deployment -n default | grep report-generator
kubectl logs deployment/report-generator-bot

# Redash
kubectl get deployment -n redash
kubectl get pvc -n redash
```

---

## 결론

CAPA 배달앱 광고 분석 플랫폼은 Report Generator와 Redash의 이중 구조로 운영하는 것이 최적입니다.

- **Redash**: 일상 모니터링 및 탐색적 분석 담당
- **Report Generator**: 정기 공식 보고서 생성 담당

이를 통해 데이터 팀의 분석 능력을 강화하고, 경영진 보고의 품질을 높일 수 있습니다.

---

**승인자**: _________________
**검토일**: 2026-03-04
**다음 리뷰**: 2026-06-04 (3개월 후)
