# CAPA 광고 데이터 파이프라인 — 아키텍처 일지 (발표용)

> **프로젝트**: CAPA (Cloud-native AI Pipeline for Ad-logs)  
> **담당**: T2 — 데이터 파이프라인 (수집 → 적재 → ETL → 분석 → 시각화)  
> **작성일**: 2026-03-24  
> **목적**: PPT 발표 기초 자료

---

## 목차

1. [전체 아키텍처 개요](#1-전체-아키텍처-개요)
2. [STEP 1 — 로그 생성기 (Log Generator)](#2-step-1--로그-생성기-log-generator)
3. [STEP 2 — Kinesis Data Streams](#3-step-2--kinesis-data-streams)
4. [STEP 3 — Kinesis Data Firehose](#4-step-3--kinesis-data-firehose)
5. [STEP 4 — S3 Raw 적재](#5-step-4--s3-raw-적재)
6. [STEP 5 — Airflow ETL](#6-step-5--airflow-etl)
7. [STEP 6 — S3 Summary 적재](#7-step-6--s3-summary-적재)
8. [STEP 7 — Glue Crawler & 카탈로그](#8-step-7--glue-crawler--카탈로그)
9. [STEP 8 — Athena 쿼리 엔진](#9-step-8--athena-쿼리-엔진)
10. [STEP 9 — Redash 대시보드](#10-step-9--redash-대시보드)
11. [핵심 이슈 및 트러블슈팅 기록](#11-핵심-이슈-및-트러블슈팅-기록)
12. [AS-IS → TO-BE 변경 이력](#12-as-is--to-be-변경-이력)
13. [향후 확장 계획](#13-향후-확장-계획)
14. [프로젝트 한계점 및 개선 과제](#14-프로젝트-한계점-및-개선-과제)

---

## 1. 전체 아키텍처 개요

### 1-1. 데이터 흐름도 (End-to-End)

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  로그 생성기  │ ──▶ │ Kinesis Streams   │ ──▶ │ Kinesis Firehose  │ ──▶ │  S3 (Raw)    │
│  (Python)    │     │ (3개 스트림)       │     │ (3개 Firehose)    │     │  Parquet/ZSTD│
└──────────────┘     └──────────────────┘     └──────────────────┘     └──────┬───────┘
                                                                              │
                                                                              ▼
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Redash     │ ◀── │    Athena        │ ◀── │  Glue Crawler    │ ◀── │ Airflow ETL  │
│  대시보드     │     │  쿼리 엔진       │     │  카탈로그 갱신    │     │ (Hourly/Daily)│
└──────────────┘     └──────────────────┘     └──────────────────┘     └──────┬───────┘
                                                                              │
                                                                              ▼
                                                                       ┌──────────────┐
                                                                       │ S3 (Summary)  │
                                                                       │ Parquet/ZSTD  │
                                                                       └──────────────┘
```

### 1-2. 기술 스택 요약

| 레이어 | 기술 | 역할 |
|--------|------|------|
| 수집 | Python + Faker | 광고 로그 시뮬레이션 |
| 스트리밍 | Kinesis Data Streams × 3 | 이벤트 타입별 실시간 수집 |
| 적재 | Kinesis Firehose × 3 | Parquet 변환 + S3 적재 |
| 저장 (Raw) | Amazon S3 | Parquet/ZSTD, 시간 파티셔닝 |
| 워크플로우 | Apache Airflow 2.7+ | ETL 스케줄링 및 오케스트레이션 |
| 저장 (Summary) | Amazon S3 | 집계 데이터 Parquet 저장 |
| 메타데이터 | AWS Glue | 스키마 관리 및 파티션 등록 |
| 쿼리 | Amazon Athena | Serverless SQL 분석 |
| 시각화 | Redash | 대시보드 및 시각화 |
| IaC | Terraform | 전체 인프라 코드 관리 |
| 컨테이너 | Docker / EKS | 로그 생성기 배포 |

### 1-3. AWS 리소스 명명 규칙

```
프로젝트: capa
리전: ap-northeast-2 (서울)
버킷: capa-data-lake-827913617635
Kinesis Streams: capa-knss-imp-00, capa-knss-clk-00, capa-knss-cvs-00
Firehose: capa-fh-imp-00, capa-fh-clk-00, capa-fh-cvs-00
Athena DB: capa_ad_logs
Workgroup: capa-workgroup
```

---

## 2. STEP 1 — 로그 생성기 (Log Generator)

### 2-1. 개요

광고 로그 3가지 유형을 시뮬레이션하여 Kinesis로 전송하는 Python 애플리케이션.

| 항목 | 내용 |
|------|------|
| 위치 | `services/data_pipeline_t2/gen_adlog_t2/` |
| 실시간 | `realtime/main.py` — Kinesis Streams로 실시간 전송 |
| 백필 | `local/ad_log_generator.py` — S3에 직접 Parquet 파일 업로드 |
| 배포 | Docker 컨테이너 → EKS Pod |

### 2-2. 이벤트 유형 (3종)

| 이벤트 | 설명 | 주요 필드 | 비율 |
|--------|------|-----------|------|
| **impression** | 광고 노출 | impression_id, user_id, ad_id, campaign_id, ad_format, delivery_region, cost_per_impression | 기준(100%) |
| **click** | 광고 클릭 | click_id, impression_id, click_position_x/y, landing_page_url, cost_per_click | CTR 1~5% |
| **conversion** | 전환(구매 등) | conversion_id, click_id, conversion_type, conversion_value, product_id, quantity | CVR 1~10% |

### 2-3. 트래픽 패턴 모델

시간대/요일별로 실제 광고 트래픽을 반영한 **동적 생성** 구현.

| 시간대 | 트래픽 배수 | 설명 |
|--------|------------|------|
| 00~07시 | 0.1 ~ 0.2배 | 새벽 (최소 트래픽) |
| 07~09시 | 0.4 ~ 0.6배 | 아침 출근 시간 |
| 09~11시 | 0.3 ~ 0.5배 | 오전 |
| 11~14시 | 1.5 ~ 2.0배 | 점심 피크 |
| 14~17시 | 0.6 ~ 0.8배 | 오후 |
| 17~21시 | **2.0 ~ 3.0배** | **저녁 피크 (최대)** |
| 21~24시 | 1.0 ~ 1.5배 | 밤 |

**요일 가중치**: 월~목(0.8~1.0), 금(1.2~1.5), 토(**1.5~2.0**), 일(1.3~1.7)

### 2-4. CTR/CVR 현실적 설정

```python
# 광고 포맷별 CTR (Click-Through Rate)
CTR_RATES = {
    "display":         (0.01, 0.03),  # 1~3%
    "native":          (0.02, 0.04),  # 2~4%
    "video":           (0.03, 0.05),  # 3~5%
    "discount_coupon": (0.025, 0.045) # 2.5~4.5%
}

# 전환 유형별 CVR (Conversion Rate)
CVR_RATES = {
    "view_content": (0.05, 0.10),  # 5~10%
    "add_to_cart":  (0.03, 0.07),  # 3~7%
    "signup":       (0.02, 0.05),  # 2~5%
    "download":     (0.02, 0.05),  # 2~5%
    "purchase":     (0.01, 0.03)   # 1~3% (가장 낮음)
}
```

### 2-5. 예상 생성량

| 시간대 | 예상 생성량 (시간당) |
|--------|---------------------|
| 새벽 (00~07) | ~800 ~ 2,000개 |
| 일반 (09~17) | ~5,000 ~ 15,000개 |
| 피크 (17~21) | ~30,000 ~ 60,000개 |
| **일일 합계** | **약 28만 ~ 30만개** |

### 2-6. 데이터 구조 (도메인 모델)

```
광고주(advertiser, 30명)
  └─ 캠페인(campaign, 5개)
       └─ 광고(ad, 1,000개)
            └─ 키워드(keyword, 500개)
                 └─ 매장(store, 5,000개)

사용자(user, 100,000명)
  └─ 세션(session)
       └─ Impression → Click → Conversion (사용자 여정)
```

**광고주별 매장 매핑**:
- advertiser_01 ~ 10: 각 50개 매장
- advertiser_11 ~ 25: 각 100개 매장
- advertiser_26 ~ 30: 각 200개 매장

### 2-7. Docker 배포

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- **배포 환경**: EKS 클러스터 내 Pod
- **환경 변수**: `.env` 또는 Kubernetes ConfigMap/Secret으로 주입

---

## 3. STEP 2 — Kinesis Data Streams

### 3-1. 구성

이벤트 타입별로 **3개의 독립 스트림**으로 분리하여 운영.

| 스트림 이름 | 이벤트 타입 | 샤드 수 | 보관 기간 |
|------------|-----------|---------|----------|
| `capa-knss-imp-00` | impression | 1 | 24시간 |
| `capa-knss-clk-00` | click | 1 | 24시간 |
| `capa-knss-cvs-00` | conversion | 1 | 24시간 |

### 3-2. 파티션 키 전략

```python
# 분산 + 세션 일관성 균형
# 우선순위: session_id → user_id → impression_id → event_id
key = log.get("session_id") or log.get("user_id") or log.get("impression_id") or log.get("event_id")
partition_key = hashlib.md5(str(key).encode("utf-8")).hexdigest()
```

- **목적**: 샤드 간 균등 분배 + 같은 세션의 이벤트를 동일 샤드에 유지
- **해시**: MD5 해싱으로 키 길이 제한 및 엔트로피 확보

### 3-3. 전송 코드 핵심

```python
class KinesisStreamSender:
    def send(self, log: Dict) -> bool:
        event_type = self._detect_event_type(log)  # impression/click/conversion 자동 분류
        stream_name = self.stream_names[event_type]
        
        payload = dict(log)
        payload.pop("_internal", None)  # 내부 계산 필드 제거
        
        self.client.put_record(
            StreamName=stream_name,
            Data=json.dumps(payload).encode("utf-8"),
            PartitionKey=self._partition_key(payload),
        )
```

### 3-4. 모니터링 지표 (CloudWatch)

- `IncomingRecords` / `IncomingBytes`: 초당 유입량
- `PutRecord.Success` / `PutRecord.Latency`: 전송 성공률 / 지연
- `ReadProvisionedThroughputExceeded`: 소비자 처리량 초과 여부

---

## 4. STEP 3 — Kinesis Data Firehose

### 4-1. 구성

각 Kinesis Stream을 **소스(KinesisStreamAsSource)**로 하는 3개 Firehose.

| Firehose 이름 | 소스 Stream | 대상 S3 경로 |
|--------------|------------|-------------|
| `capa-fh-imp-00` | `capa-knss-imp-00` | `s3://버킷/raw/impressions/` |
| `capa-fh-clk-00` | `capa-knss-clk-00` | `s3://버킷/raw/clicks/` |
| `capa-fh-cvs-00` | `capa-knss-cvs-00` | `s3://버킷/raw/conversions/` |

### 4-2. Firehose 설정

| 설정 항목 | 값 | 설명 |
|----------|-----|------|
| 버퍼 크기 | 64 MB | Parquet 변환 시 최소 64MB 필수 |
| 버퍼 시간 | 60초 | 최대 60초 대기 후 S3 기록 |
| 출력 형식 | **Parquet** | JSON → Parquet 자동 변환 |
| 압축 | **ZSTD** | 높은 압축률 + 빠른 조회 |
| 파티셔닝 | Dynamic Partitioning | 시간 기반 자동 파티셔닝 |

### 4-3. S3 Prefix (Dynamic Partitioning)

```
# 정상 데이터
raw/{event_type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/

# 에러 데이터
errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/
```

### 4-4. 스키마 변환 (Glue 연동)

- Firehose는 Glue Catalog의 테이블 스키마를 참조하여 JSON → Parquet 변환 수행
- `data_format_conversion_configuration`에서 `open_x_json_ser_de` → `parquet_ser_de` 변환

### 4-5. 주의사항

> ⚠️ **Firehose가 Kinesis를 소스로 사용할 때는 `firehose.put_record()` 직접 호출이 거부됩니다.**  
> Generator는 반드시 `kinesis.put_record()`만 호출해야 합니다.

---

## 5. STEP 4 — S3 Raw 적재

### 5-1. 디렉토리 구조

```
s3://capa-data-lake-827913617635/
├── raw/                              ← 원시 로그
│   ├── impressions/
│   │   └── year=2026/month=03/day=24/hour=14/
│   │       └── firehose-*.parquet
│   ├── clicks/
│   │   └── year=2026/month=03/day=24/hour=14/
│   │       └── firehose-*.parquet
│   └── conversions/
│       └── year=2026/month=03/day=24/hour=14/
│           └── firehose-*.parquet
├── summary/                          ← ETL 집계 데이터
│   ├── ad_combined_log/              ← Hourly (impression+click 조인)
│   │   └── year=2026/month=03/day=24/hour=14/
│   └── ad_combined_log_summary/      ← Daily (hourly+conversion 집계)
│       └── year=2026/month=03/day=24/
├── .athena-temp/                     ← Athena 쿼리 결과 (격리)
└── errors/                           ← Firehose 에러 로그
```

### 5-2. 파일 형식

| 항목 | 스펙 |
|------|------|
| 포맷 | Apache Parquet |
| 압축 | ZSTD (Zstandard) |
| 파티셔닝 | Hive-style (`year=YYYY/month=MM/day=DD/hour=HH`) |
| 버킷 | `capa-data-lake-827913617635` |
| 리전 | `ap-northeast-2` (서울) |

### 5-3. S3 라이프사이클 정책

| 정책 | 대상 경로 | 설정 |
|------|----------|------|
| 데이터 만료 | `raw/`, `summary/` | 90일 후 삭제 |
| 쿼리 결과 정리 | `.athena-temp/` | 7일 후 자동 삭제 |
| 버저닝 | 전체 버킷 | Enabled (데이터 보호) |

---

## 6. STEP 5 — Airflow ETL

### 6-1. DAG 구성

ETL은 **2개 DAG**으로 분리 운영 (Airflow 표준 패턴: 파일당 1 DAG).

| DAG ID | 스케줄 | 역할 | 처리 대상 |
|--------|--------|------|----------|
| `01_ad_hourly_summary` | 매시간 10분 (`10 * * * *`) | impression + click 조인 | 이전 1시간 데이터 |
| `02_ad_daily_summary` | 매일 02시 (`0 2 * * *`) | hourly 24건 + conversion 집계 | 전일 데이터 |

### 6-2. Hourly ETL (impression + click → ad_combined_log)

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ impressions  │     │                  │     │ ad_combined_log  │
│ (해당 시간)   │ ──▶ │  LEFT JOIN       │ ──▶ │ (27개 필드)      │
│              │     │  ON impression_id│     │                  │
│ clicks       │     │  + 시간 파티션    │     │ year/month/      │
│ (해당 시간)   │ ──▶ │                  │     │ day/hour 파티션   │
└──────────────┘     └──────────────────┘     └──────────────────┘
```

**출력 필드 (27개)**:
- Impression 필드 20개: impression_id, user_id, ad_id, campaign_id, advertiser_id, platform, device_type, os, delivery_region, user_lat, user_long, store_id, food_category, ad_position, ad_format, user_agent, ip_address, session_id, keyword, cost_per_impression, impression_timestamp
- Click 필드 6개: click_id, click_position_x, click_position_y, landing_page_url, cost_per_click, click_timestamp
- 조인 플래그 1개: is_click (boolean)

### 6-3. Daily ETL (hourly + conversion → ad_combined_log_summary)

```
┌────────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ ad_combined_log    │     │                  │     │ ad_combined_log_summary │
│ (24시간분 × 27필드) │ ──▶ │  LEFT JOIN       │ ──▶ │ (35개 필드)              │
│                    │     │  ON impression_id│     │                         │
│ conversions        │     │  + 날짜 파티션    │     │ year/month/day 파티션    │
│ (하루치)            │ ──▶ │                  │     │                         │
└────────────────────┘     └──────────────────┘     └─────────────────────────┘
```

**추가 필드 (8개 → 총 35개)**:
- Conversion 필드 7개: conversion_id, conversion_type, conversion_value, product_id, quantity, attribution_window, conversion_timestamp
- 전환 플래그 1개: is_conversion (boolean)

### 6-4. ETL 처리 방식 (Athena SELECT → Python → S3 업로드)

> ⚠️ **Athena는 INSERT INTO를 지원하지 않음** (Presto 기반)

```python
# 1. Athena SELECT 쿼리로 데이터 조회
df = executor.execute_query_to_dataframe(query)

# 2. Python에서 Parquet 변환 (PyArrow)
df.to_parquet(temp_path, engine='pyarrow', compression='zstd')

# 3. S3에 업로드 (boto3)
s3_client.upload_file(temp_path, bucket, key)

# 4. MSCK REPAIR TABLE로 파티션 메타데이터 갱신
executor.execute_query("MSCK REPAIR TABLE ad_combined_log")
```

### 6-5. 시간대 처리 (UTC ↔ KST)

| 구분 | 기준 | 설명 |
|------|------|------|
| Airflow 스케줄 | UTC | Airflow는 UTC 기반으로 동작 |
| ETL 처리 | **KST** | `pendulum.in_timezone('Asia/Seoul')` 변환 |
| S3 파티션 | **KST** | `year=2026/month=03/day=24/hour=15` |

```python
# DAG 내 UTC → KST 변환
dt_utc = context["data_interval_start"]
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
target_hour_kst = dt_kst.subtract(hours=1)  # 이전 시간 데이터 처리
```

### 6-6. 설계 결정 사항

#### DAG 2개 분리 근거

| 기준 | 1개 파일 | 2개 파일 (채택) |
|------|----------|----------------|
| schedule 관리 | 다른 주기 혼재 → 복잡 | 파일당 1 DAG, 주기 명확 |
| 배포/수정 | hourly 수정 시 daily에도 영향 | 독립적 배포 가능 |
| 모니터링 | 구분 어려움 | 개별 DAG 상태 확인 용이 |

#### Daily ETL에서 Conversion을 별도 Hourly 집계하지 않는 이유

- CVR(전환율)은 시간 단위 집계에서 비즈니스 의미 없음
- 전환 로그는 노출/클릭 대비 늦게 발생 → hourly로 자르면 데이터 누락 위험
- conversion 로그는 양이 매우 적음 (click의 1~10%)
- DAG 3개는 운영 복잡도만 증가

### 6-7. Kubernetes 배포 (KubernetesExecutor)

```yaml
# Airflow 설정
AIRFLOW__CORE__EXECUTOR: KubernetesExecutor
```

- 각 Task가 독립 Pod로 실행 → 리소스 효율적
- Task 완료 후 Pod 자동 종료
- KubernetesPodOperator로 커스텀 컨테이너 실행 가능

---

## 7. STEP 6 — S3 Summary 적재

### 7-1. 테이블 구조 비교

| 항목 | ad_combined_log (Hourly) | ad_combined_log_summary (Daily) |
|------|-------------------------|--------------------------------|
| 파티션 | year/month/day/**hour** | year/month/day |
| 필드 수 | 27개 | 35개 |
| 포함 데이터 | impression + click | impression + click + **conversion** |
| 갱신 주기 | 매시간 | 매일 02시 |
| 용도 | 시간대별 분석, 실시간 모니터링 | 일별 ROAS, 전환율 분석 |

### 7-2. 주요 스키마

#### ad_combined_log (Hourly)

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| impression_id | string | 노출 이벤트 고유 ID |
| user_id | string | 사용자 ID |
| ad_id | string | 광고 ID |
| campaign_id | string | 캠페인 ID |
| advertiser_id | string | 광고주 ID |
| platform | string | 플랫폼 (web/app_ios/...) |
| device_type | string | 디바이스 유형 |
| is_click | boolean | 클릭 여부 |
| cost_per_impression | double | 노출당 비용 |
| cost_per_click | double | 클릭당 비용 |
| year, month, day, hour | string | **파티션 키** |

#### ad_combined_log_summary (Daily) — 추가 필드

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| conversion_id | string | 전환 이벤트 ID |
| conversion_type | string | 전환 유형 (purchase/signup/...) |
| conversion_value | double | 전환 금액 |
| is_conversion | boolean | 전환 여부 |
| year, month, day | string | **파티션 키** (hour 없음) |

---

## 8. STEP 7 — Glue Crawler & 카탈로그

### 8-1. Glue Database

```
Database: capa_ad_logs
```

### 8-2. Glue 관리 테이블

| 테이블명 | 소스 S3 경로 | 파티션 키 | 설명 |
|----------|-------------|----------|------|
| impressions | `raw/impressions/` | year/month/day/hour | 원시 노출 로그 |
| clicks | `raw/clicks/` | year/month/day/hour | 원시 클릭 로그 |
| conversions | `raw/conversions/` | year/month/day/hour | 원시 전환 로그 |
| ad_combined_log | `summary/ad_combined_log/` | year/month/day/hour | 시간별 집계 |
| ad_combined_log_summary | `summary/ad_combined_log_summary/` | year/month/day | 일별 집계 |

### 8-3. 파티션 등록

- ETL 완료 후 `MSCK REPAIR TABLE` 실행으로 신규 파티션 자동 등록
- Glue Crawler가 S3 경로를 스캔하여 스키마 자동 갱신

> ⚠️ **주의**: Athena는 한 번에 하나의 SQL 문만 실행 가능.  
> `MSCK REPAIR TABLE table1; MSCK REPAIR TABLE table2;` → 불가  
> 각각 별도 실행 필요.

---

## 9. STEP 8 — Athena 쿼리 엔진

### 9-1. 설정

| 항목 | 설정값 |
|------|--------|
| Database | `capa_ad_logs` |
| Workgroup | `capa-workgroup` |
| 결과 저장 | `s3://버킷/.athena-temp/` (격리) |
| 암호화 | SSE-S3 |
| 타임아웃 | 300초 (5분) |
| 재시도 | 최대 3회, 30초 간격 |

### 9-2. 주요 분석 쿼리 유형

| 분석 유형 | 테이블 | 설명 |
|----------|--------|------|
| 시간대별 CTR | ad_combined_log | 시간별 클릭률 추이 |
| 플랫폼별 성과 | ad_combined_log | 디바이스/플랫폼 비교 |
| 실시간 모니터링 | ad_combined_log | 5분 단위 트래픽 |
| 캠페인 성과 | ad_combined_log_summary | 일별 캠페인 KPI |
| ROAS 분석 | ad_combined_log_summary | 광고 수익률 |
| 광고주별 ROI | ad_combined_log_summary | 광고주 효율 비교 |

### 9-3. ETL에서의 Athena 활용

```python
class AthenaQueryExecutor:
    def execute_query(self, query: str, database: str) -> str:
        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH},
            WorkGroup='primary'
        )
        # 쿼리 완료 대기 (폴링)
        self._wait_for_query_completion(query_id)
```

---

## 10. STEP 9 — Redash 대시보드

### 10-1. 연동 구성

```
Redash → Athena Data Source 설정
  - AWS Access Key / Secret Key
  - Region: ap-northeast-2
  - S3 Staging Path: s3://버킷/.athena-temp/
  - Database: capa_ad_logs
```

### 10-2. 대시보드 구성 (4종)

| 대시보드 | 목적 | 주요 지표 |
|----------|------|----------|
| **Executive** | 경영진 핵심 KPI | 일/주/월별 노출, 클릭, 전환, ROAS |
| **Campaign Performance** | 캠페인별 성과 분석 | 캠페인별 CTR, CVR, CPA, Top 10 |
| **Real-time Monitoring** | 실시간 운영 모니터링 | 시간대별 이벤트, CTR 게이지, 이상 탐지 |
| **Advertiser Analysis** | 광고주별 비교 분석 | 광고주별 매출, ROI, 순위 |

### 10-3. 대시보드 파라미터

| 파라미터 | 타입 | 기본값 | 용도 |
|----------|------|--------|------|
| `current_date` | Date | today | 일간 분석 기준일 |
| `start_date` | Date | - | 기간 분석 시작일 |
| `end_date` | Date | - | 기간 분석 종료일 |
| `month` | Text | YYYY-MM | 월간 분석 기준월 |

### 10-4. 주요 쿼리 패턴

```sql
-- 일간 시간대별 성과 (ad_combined_log 활용)
SELECT 
    CAST(hour AS INTEGER) as "시간대",
    COUNT(*) as "노출수",
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as "클릭수",
    ROUND(CAST(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) AS DOUBLE) 
          / COUNT(*) * 100, 2) as "CTR%"
FROM ad_combined_log
WHERE date_parse(concat(year, '-', month, '-', day), '%Y-%m-%d') = DATE '{{current_date}}'
GROUP BY CAST(hour AS INTEGER)
ORDER BY 1;

-- 기간별 종합 성과 (ad_combined_log_summary 활용)
SELECT 
    SUM(CASE WHEN is_conversion THEN conversion_value ELSE 0 END) as "총매출",
    SUM(cost_per_impression) + SUM(CASE WHEN is_click THEN cost_per_click ELSE 0 END) as "총광고비",
    ROUND(SUM(CASE WHEN is_conversion THEN conversion_value ELSE 0 END) 
          / NULLIF(SUM(cost_per_impression) + SUM(CASE WHEN is_click THEN cost_per_click ELSE 0 END), 0), 2) as "ROAS"
FROM ad_combined_log_summary
WHERE date_parse(concat(year, '-', month, '-', day), '%Y-%m-%d') 
      BETWEEN DATE '{{start_date}}' AND DATE '{{end_date}}';
```

---

## 11. 핵심 이슈 및 트러블슈팅 기록

### 이슈 #1: Firehose → Kinesis Streams 마이그레이션

| 구분 | AS-IS | TO-BE |
|------|-------|-------|
| 전송 대상 | Firehose Direct PUT 3개 | **Kinesis Streams 3개** |
| 코드 | `FirehoseSender` → `firehose.put_record()` | `KinesisStreamSender` → `kinesis.put_record()` |
| Firehose | Direct PUT 모드 | **KinesisStreamAsSource (Pull 모드)** |
| 파티션 키 | 미사용 | **MD5 해시 기반 분산** |
| IAM | `firehose:PutRecord` | `kinesis:PutRecord` |
| 이점 | 구현 단순 | 다중 소비자(EFO), 이벤트별 독립 스케일링 |

### 이슈 #2: Athena INSERT INTO 미지원

- **문제**: Athena는 Presto 기반으로 `INSERT INTO ... PARTITION` 미지원
- **해결**: Athena SELECT → Python DataFrame → Parquet 변환 → S3 업로드 → MSCK REPAIR TABLE

### 이슈 #3: Glue 카탈로그에 임시 테이블 자동 생성

- **문제**: Athena 쿼리 결과 CSV가 `athena-results/`에 저장 → Glue가 자동으로 테이블 인식
- **원인**: `ad_combined_log_a936396ed6a1823426395f9b5994868e` 같은 해시 테이블 생성
- **해결**: 쿼리 결과 저장 경로를 `.athena-temp/`로 격리 (Crawler가 감시하지 않는 경로)

### 이슈 #4: Athena Workgroup 설정 충돌

- **문제**: 코드에서 `.athena-temp/`로 설정해도 CSV가 `athena-results/`에 생성됨
- **원인**: Terraform Athena Workgroup에서 `enforce_workgroup_configuration = true` 설정
- **해결**: 워크그룹 설정에서 결과 저장 경로를 `.athena-temp/`로 변경 또는 다중 워크그룹 전략

### 이슈 #5: 실시간 vs 백필 생성량 차이

| 구분 | 실시간 (main.py) | 백필 (ad_log_generator.py) |
|------|-----------------|--------------------------|
| 생성 방식 | 동적 sleep (0.1초/트래픽배수) | 10,000개 × 트래픽 멀티플라이어 |
| 시간당 | 800 ~ 60,000개 | 800 ~ 60,000개 |
| 일일 합계 | ~28만개 | ~35만개 |
| 트래픽 패턴 | ✅ 적용 | ✅ 적용 |

### 이슈 #6: ad_combined_log vs ad_combined_log_summary 혼동

| 항목 | ad_combined_log | ad_combined_log_summary |
|------|----------------|------------------------|
| 파티션 | year/month/day/**hour** | year/month/day |
| Conversion 데이터 | ❌ 없음 | ✅ 있음 |
| 용도 | 시간대별 분석 | 일별 ROAS/전환율 |

> **결론**: conversion 데이터가 필요하면 반드시 `ad_combined_log_summary` 사용

### 이슈 #7: Airflow UTC ↔ KST 시간대

- Airflow는 UTC 기준, S3 파티션은 KST 기준
- `pendulum.in_timezone('Asia/Seoul')` 변환 필수
- 검증 예시: UTC 06:00 → KST 15:00 → 파티션 `hour=15`

### 이슈 #8: DAG 스케줄 조정

| DAG | 변경 전 | 변경 후 | 사유 |
|-----|--------|---------|------|
| 01_ad_hourly_summary | `0 * * * *` (매 정각) | `10 * * * *` (매시 10분) | 데이터 적재 시간 확보 |
| 02_ad_daily_summary | `0 1 * * *` (매일 01시) | `0 2 * * *` (매일 02시) | 충분한 데이터 수집 대기 |

### 이슈 #9: Redash 쿼리 컬럼 오류

- **문제**: `COLUMN_NOT_FOUND: Column 'is_conversion' cannot be resolved`
- **원인**: `ad_combined_log` 테이블에서 conversion 관련 컬럼 사용 시도
- **해결**: conversion 관련 쿼리는 `ad_combined_log_summary` 테이블로 변경

### 이슈 #10: Athena 복수 SQL 실행 불가

- **문제**: `Only one sql statement is allowed`
- **원인**: Athena는 한 번에 하나의 SQL 문만 실행 가능
- **해결**: `MSCK REPAIR TABLE` 등은 테이블별로 별도 실행

---

## 12. AS-IS → TO-BE 변경 이력

### 12-1. 로그 전송 방식 변경

```
AS-IS: Generator → Firehose Direct PUT → S3
TO-BE: Generator → Kinesis Streams → Firehose (Pull) → S3
```

- 다중 소비자 확장(EFO) 가능
- 이벤트별 독립 스케일링/모니터링

### 12-2. 로그 저장 구조 변경

```
AS-IS: s3://버킷/raw/year=.../   (단일 폴더, event_type 필드로 구분)
TO-BE: s3://버킷/raw/impressions/year=.../
       s3://버킷/raw/clicks/year=.../
       s3://버킷/raw/conversions/year=.../
```

- 이벤트 타입별 독립 테이블
- Athena 쿼리 시 불필요한 스캔 제거

### 12-3. 실시간 생성기 개선

```
AS-IS: 0.3초 고정 sleep → 시간당 12,000개 균일
TO-BE: 동적 sleep (0.1초/트래픽배수) → 시간당 800~60,000개 (시간대별 변동)
```

- CTR: 10% 고정 → 1~5% (포맷별 차등)
- CVR: 20% 고정 → 1~10% (전환 유형별 차등)

### 12-4. Athena 쿼리 결과 격리

```
AS-IS: s3://버킷/athena-results/   (Glue Crawler가 감시)
TO-BE: s3://버킷/.athena-temp/     (Crawler 감시 제외, 7일 자동 삭제)
```

### 12-5. Redash 파라미터 단순화

```
AS-IS: current_date + monthly_revenue_target + monthly_cost_target + monthly_conversion_target (4개)
TO-BE: month (YYYY-MM 형식) 1개만 사용 — 목표값은 하드코딩
```

---

## 13. 향후 확장 계획

### 단기 (진행 중)

- [ ] Redash 대시보드 고도화 (기간별 분석 통합)
- [ ] Airflow DAG 안정성 개선 (에러 핸들링 강화)
- [ ] CloudWatch 알림 설정 (ETL 실패 시 Slack 알림)

### 중기

- [ ] Weekly / Monthly 집계 DAG 추가
- [ ] Vanna AI (Text-to-SQL) 연동 — 자연어 쿼리 지원
- [ ] 데이터 품질 검증 DAG 추가 (Data Quality Check)
- [ ] Karpenter 기반 EKS 오토스케일링 최적화

### 장기

- [ ] 실시간 이상 탐지 (Anomaly Detection) 파이프라인
- [ ] ML 기반 CTR/CVR 예측 모델 통합
- [ ] A/B 테스트 자동화 파이프라인
- [ ] 멀티 리전 DR(Disaster Recovery) 구성

---

## 14. 프로젝트 한계점 및 개선 과제

> **작성일**: 2026-03-24  
> **목적**: 현재 파이프라인의 구조적·운영적 한계를 객관적으로 분석하여 발표 및 향후 개선 방향 도출

### 14-1. 데이터 수집 레이어 한계

#### ① Kinesis Streams 단일 샤드 구조

| 구분 | 현재 (AS-IS) | 개선 방향 (TO-BE) |
|------|-------------|------------------|
| 샤드 수 | **1개** (스트림당) | 트래픽 기반 동적 샤드 스케일링 |
| 쓰기 한계 | 1 MB/s 또는 1,000 records/s | Auto-scaling 또는 On-Demand 모드 |
| 읽기 한계 | 2 MB/s (기본), 5개 소비자 공유 | Enhanced Fan-Out (EFO) 활성화 |

- **영향**: 피크 시간(17~21시)에 최대 60,000건/시간 생성 → 현재 단일 샤드로 처리 가능하나, **실제 프로덕션 트래픽 증가 시 병목** 발생 가능
- **위험도**: 🟡 중간 (현재 시뮬레이션 규모에서는 문제 없으나, 확장 시 즉시 한계 도달)

#### ② 로그 생성기의 시뮬레이션 데이터 한계

- **현재**: Faker 기반 랜덤 데이터 생성 → 실제 광고 도메인 패턴과 차이 존재
  - 사용자 행동 시퀀스 모델링 없음 (impression → click → conversion이 단순 확률 기반)
  - 세션 내 연속 행동 패턴 미반영 (같은 세션에서 다수 impression 후 click하는 패턴 등)
  - 광고 피로도(Ad Fatigue), 리타게팅 효과 미반영
- **영향**: 분석 결과가 실제 광고 성과와 괴리가 있을 수 있음 (단, MVP 시뮬레이션 목적으로는 충분)

#### ③ 실시간 로그 생성기 단일 인스턴스

- `main.py`가 단일 프로세스로 실행 → 장애 시 로그 생성 중단
- Graceful Shutdown 처리 없음 (KeyboardInterrupt만 처리)
- Health Check 엔드포인트 없음 → Kubernetes liveness/readiness probe 연동 불가

### 14-2. 데이터 적재 레이어 한계

#### ④ Firehose 버퍼 지연 (최소 60초)

| 구분 | 현재 (AS-IS) | 이상적 (TO-BE) |
|------|-------------|---------------|
| 버퍼 시간 | 60초 | 실시간 (< 5초) |
| 버퍼 크기 | 64 MB | 적응형 버퍼링 |

- **영향**: S3에 데이터가 최소 1분 지연 적재 → Hourly ETL에서는 문제 없으나 **실시간 분석/모니터링에 제약**
- **구조적 한계**: Firehose는 최소 60초 버퍼를 강제 (Parquet 변환 시 64MB 최소)

#### ⑤ Terraform Kinesis 리소스와 실제 운영 불일치

- Terraform `03-kinesis.tf`에는 **단일 Kinesis Stream + 단일 Firehose**만 정의
- 실제 운영에는 **3개 스트림(imp/clk/cvs) + 3개 Firehose**를 사용 중
- Firehose prefix에 이벤트 타입별 분리(`raw/impressions/`, `raw/clicks/`, `raw/conversions/`)가 Terraform에 미반영
- **영향**: IaC와 실제 인프라 간 Drift 발생 → 인프라 재현성 저하

### 14-3. ETL 레이어 한계

#### ⑥ Athena INSERT INTO 미지원으로 인한 우회 패턴

```
현재 ETL 방식:
  Athena SELECT → Python DataFrame → Parquet 변환 → S3 업로드 → MSCK REPAIR TABLE
```

| 문제점 | 설명 |
|--------|------|
| 메모리 제약 | 대용량 데이터를 Python 메모리에 로드 → OOM 위험 |
| 네트워크 비용 | Athena → Python → S3 이중 전송 (데이터가 Athena에서 Python으로, 다시 S3로) |
| 원자성 미보장 | Parquet 업로드 → MSCK REPAIR 사이 시간에 불완전 데이터 노출 가능 |
| 비효율 | Athena 내부에서 직접 S3에 쓸 수 있다면 Python 중간 과정 불필요 |

- **대안 검토**: Athena CTAS(CREATE TABLE AS SELECT)로 대체 가능하나, 기존 테이블에 파티션 추가 시 매번 새 테이블 생성 필요

#### ⑦ ETL 멱등성(Idempotency) 미보장

- 동일 시간대에 ETL을 재실행하면 **데이터 중복 적재** 가능
- `_insert_data_overwrite()` 메서드에서 기존 파티션 데이터 삭제 후 재삽입하는 로직 없음
- **영향**: Airflow 재시도(retry) 시 동일 파티션에 중복 Parquet 파일 생성

#### ⑧ 데이터 품질 검증 부재

- ETL 후 `_validate_results()`가 단순 COUNT 확인만 수행
- 스키마 검증, NULL 비율 검사, 값 범위 검증 등 **Data Quality Check 미구현**
- 이상치(Anomaly) 자동 탐지 없음
- **영향**: 잘못된 데이터가 Summary 테이블에 적재되어도 감지 불가

#### ⑨ ETL 코드 이중 관리

| 위치 | 용도 |
|------|------|
| `etl_summary_t2/` | 독립 실행용 ETL 모듈 |
| `dags/etl_modules/` | Airflow DAG 내장 ETL 모듈 |

- 동일 로직이 **2곳에 복사**되어 관리 → 하나를 수정하면 다른 곳도 동기화 필요
- **영향**: 코드 불일치 위험, 유지보수 비용 증가

### 14-4. 쿼리/분석 레이어 한계

#### ⑩ Athena 쿼리 비용 관리 부재

- Athena는 **스캔한 데이터량 기반 과금** ($5/TB)
- 쿼리별 비용 추적/제한 메커니즘 없음
- Workgroup에 `bytes_scanned_cutoff_per_query` 미설정 → 대규모 Full Scan 쿼리 실행 시 비용 폭증 위험
- **영향**: 개발/테스트 중 부주의한 쿼리로 예상 외 비용 발생 가능

#### ⑪ Athena Workgroup 설정 충돌 미해결

- Terraform의 `enforce_workgroup_configuration = true` 설정으로 코드의 `.athena-temp/` 경로가 무시됨
- 현재 `WorkGroup='primary'`로 우회 중 → **capa-workgroup의 설정과 분리된 상태**
- **영향**: 쿼리 결과가 의도하지 않은 경로에 저장될 수 있음

#### ⑫ ad_combined_log와 ad_combined_log_summary 간 분석 갭

| 분석 요구 | ad_combined_log | ad_combined_log_summary |
|----------|----------------|------------------------|
| 시간대별 Conversion | ❌ 불가 | ❌ 불가 (hour 파티션 없음) |
| 일별 ROAS | ❌ 불가 (conversion 없음) | ✅ 가능 |
| 실시간 CTR | ✅ 가능 | ❌ 불가 (일 단위 집계) |

- **시간대별 전환 분석이 불가능**: hourly 테이블에는 conversion 데이터 없고, daily 테이블에는 hour 파티션 없음
- 시간대별 ROAS/CVR 분석 시 impressions + clicks + conversions 원시 테이블을 직접 JOIN 해야 함 (비용 증가)

### 14-5. 시각화/BI 레이어 한계

#### ⑬ Redash 싱글 인스턴스 운영

- Redash가 단일 Pod로 운영 → 장애 시 대시보드 전체 중단
- 쿼리 캐시 전략 미구현 → 동일 쿼리 반복 실행 시 매번 Athena 과금
- 사용자 접근 제어(RBAC) 미설정 → 모든 사용자가 전체 데이터 접근 가능

#### ⑭ 대시보드 파라미터 하드코딩

- 월간 목표값(매출 30억, 비용 15억, 전환 40만건)이 쿼리 내 하드코딩
- 목표값 변경 시 Redash 쿼리를 직접 수정해야 함
- **영향**: 운영 유연성 저하, 비기술 사용자의 목표 변경 불가

### 14-6. 인프라/운영 레이어 한계

#### ⑮ S3 라이프사이클 정책 단일화

- 현재: 전체 버킷에 90일 만료 정책 적용 (`filter {}` = 전체 대상)
- `.athena-temp/`는 7일 정책이 필요하나 **별도 rule 미정의**
- `summary/` 데이터와 `raw/` 데이터의 보관 정책이 동일 → Summary는 더 오래 보관해야 할 수 있음
- **영향**: 비용 최적화 미달, 또는 필요한 데이터 조기 삭제 위험

#### ⑯ 모니터링/알림 체계 불완전

| 항목 | 현재 상태 |
|------|----------|
| Kinesis 알림 | ✅ Low Traffic, High Iterator Age |
| EKS 알림 | ✅ CPU High (단, Container Insights 미활성화) |
| **ETL 실패 알림** | ❌ 미구현 |
| **S3 적재 지연 알림** | ❌ 미구현 |
| **Athena 쿼리 비용 알림** | ❌ 미구현 |
| **데이터 품질 알림** | ❌ 미구현 |

- Airflow DAG 실패 시 Slack/이메일 알림 미연동
- **영향**: ETL 실패를 수동으로 Airflow UI에서 확인해야 함

#### ⑰ 코딩 규칙 미준수 영역

| 규칙 | 위반 위치 | 현황 |
|------|----------|------|
| `print()` 금지, `logging` 필수 | `gen_adlog_t2/realtime/main.py`, `kinesis_stream_sender.py` | `print()` 18회 사용 |
| Docker `latest` 태그 금지 | `gen_adlog_t2/realtime/Dockerfile` | `python:3.9-slim` (버전 명시 ✅, 단 프로젝트 Python 3.11+ 불일치) |
| 단위 테스트 필수 | `gen_adlog_t2/`, `etl_summary_t2/` | **테스트 코드 없음** |

#### ⑱ 단위 테스트 부재

- `gen_adlog_t2/` (로그 생성기): 테스트 코드 없음
- `etl_summary_t2/` (ETL 모듈): 테스트 코드 없음
- Airflow DAG 테스트: `03_*_test.py`, `04_*_test.py` 존재하나 **통합 테스트 수준** (단위 테스트 아님)
- moto 기반 AWS Mock 테스트 미구현
- **영향**: 코드 변경 시 회귀 테스트 불가, 리팩토링 리스크 높음

### 14-7. 보안 한계

#### ⑲ AWS 자격 증명 관리

- `config.py`에서 `os.environ.get('AWS_ACCESS_KEY_ID')` 직접 참조
- `.env` 파일에 Access Key 저장 → **git에 노출 위험** (.gitignore로 보호되나, 실수 가능)
- EKS 환경에서는 **IRSA(IAM Roles for Service Accounts)** 또는 **Pod Identity** 사용이 권장됨

#### ⑳ S3 버킷 암호화 미설정

- `04-s3.tf`에 **S3 기본 암호화(SSE-S3 또는 SSE-KMS) 설정 없음**
- Athena 결과는 SSE-S3 암호화 적용 (08-athena.tf) → S3 원본 데이터와 불일치
- **영향**: 규정 준수(Compliance) 요건 미충족 가능

### 14-8. 한계점 요약 (심각도별)

| 심각도 | 한계점 | 비고 |
|--------|--------|------|
| 🔴 높음 | ⑦ ETL 멱등성 미보장 | 재실행 시 데이터 중복 |
| 🔴 높음 | ⑨ ETL 코드 이중 관리 | 코드 불일치 위험 |
| 🔴 높음 | ⑱ 단위 테스트 부재 | 회귀 테스트 불가 |
| 🔴 높음 | ⑤ Terraform-실제 인프라 Drift | IaC 재현성 저하 |
| 🟡 중간 | ⑥ Athena INSERT 우회 패턴 | OOM 위험, 원자성 미보장 |
| 🟡 중간 | ⑧ 데이터 품질 검증 부재 | 잘못된 데이터 감지 불가 |
| 🟡 중간 | ⑩ Athena 쿼리 비용 관리 부재 | 비용 폭증 위험 |
| 🟡 중간 | ⑯ 모니터링 체계 불완전 | ETL 실패 수동 확인 |
| 🟡 중간 | ⑰ 코딩 규칙 미준수 | print() 사용, 테스트 없음 |
| 🟡 중간 | ⑲ AWS 자격 증명 관리 | .env 기반 관리 |
| 🟢 낮음 | ① 단일 샤드 구조 | 현재 규모에서 문제 없음 |
| 🟢 낮음 | ② 시뮬레이션 데이터 한계 | MVP 목적으로 충분 |
| 🟢 낮음 | ④ Firehose 60초 지연 | 구조적 한계 (변경 불가) |
| 🟢 낮음 | ⑫ 시간대별 Conversion 분석 갭 | 설계 트레이드오프 |
| 🟢 낮음 | ⑭ 하드코딩 목표값 | 운영 편의 문제 |

---

## 부록: 코드 위치 요약

| 구성 요소 | 경로 |
|----------|------|
| 실시간 로그 생성기 | `services/data_pipeline_t2/gen_adlog_t2/realtime/` |
| 백필 로그 생성기 | `services/data_pipeline_t2/gen_adlog_t2/local/` |
| ETL 코어 모듈 | `services/data_pipeline_t2/etl_summary_t2/` |
| Airflow DAG | `services/data_pipeline_t2/dags/` |
| DAG 내장 ETL 모듈 | `services/data_pipeline_t2/dags/etl_modules/` |
| ETL 설정 | `services/data_pipeline_t2/etl_summary_t2/config.py` |
| Terraform (IaC) | `infrastructure/terraform/` |
| Helm Values | `infrastructure/helm-values/` |
| 문서 | `docs/t2/` |

---

> **문서 끝** — 이 문서는 CAPA T2 데이터 파이프라인의 전체 아키텍처와 이슈 이력을 PPT 발표 기초 자료로 활용하기 위해 작성되었습니다.
