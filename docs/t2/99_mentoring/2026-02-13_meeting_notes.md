# 2026-02-13 회의록 정리

## 1. 광고 도메인

### 광고 로그 데이터 필수 정보
- **사용자 정보**: user_id, ip, device
- **광고주 관련**: advertiser_id, campaign_id, creative_id
- **광고 지면 관련**: inventory_id (지면에 이미지가 들어가는 곳)
- **광고 비용**: CPC (Cost Per Click)

### 핵심 지표
- **CTR (Click-Through Rate)**: 클릭수 / 노출수 * 100
- **CVR (Conversion Rate)**: 전환율 (시간 단위 집계에서는 적용 X)
- **노출 ID (imp_event_id)**: 사용자가 광고를 볼 때마다 생성되는 고유 ID

### 이미지 크기와 광고 효과
- Creative 사이즈가 광고 효과에 영향

### (참고) RTB (Real-Time Bidding) 관련
- **경매 시스템**: 몰로코 등 경쟁사 존재
- **AI 활용**: 딥러닝 모델로 경매가 판단 및 예측 모델 개발
- **주요 필드**:
  - `adx_id`: RTB exchange 식별자
  - `bid_logic`: 비딩 요청 시 사용한 로직
  - `bid_cost`: 입찰 비용 (≠ 예산)
  
## 2. DB 테이블 구조

### 원천 로그 테이블
1. **ad_impression**: 광고 노출 로그
2. **ad_click**: 광고 클릭 로그
3. **ad_conversion**: 광고 전환 로그

### Summary 테이블
1. **ad_combined_log**: ad_impression과 ad_click을 조인한 테이블
2. **ad_combined_log_summary**: 시간/일 단위로 집계된 요약 테이블

### 주요 스키마 필드
```sql
adx_id INT COMMENT 'RTB exchange identifier',
ad_account_id STRING COMMENT 'Advertiser identifier',
cre_id STRING COMMENT 'Ad creative identifier',
spa_tag_id STRING COMMENT 'Inventory identifier',
app_bundle STRING COMMENT 'App identifier where ad was displayed',
dynamic_cre_id STRING COMMENT 'Dynamic creative identifier',
campaign_id STRING COMMENT 'Campaign identifier',
audiences ARRAY<STRING> COMMENT 'List of usr_ifa lists',
bid_logic STRING COMMENT 'Bidding logic used',
impressions FLOAT COMMENT 'Number of ad impressions',
clicks FLOAT COMMENT 'Number of ad clicks'
```

### 파티셔닝 및 저장 형식
- **시간 파티셔닝 필수**: `dt=2026-02-13T06` 또는 `dt=2026-02-13-06`
- **파일 형식**: Parquet
- **압축 설정**: zstd (높은 압축률로 스토리지 비용 절감)

### 조인 방법
```sql
SELECT imp_event_id,
   ...,
   IF(imp_event_id IN (SELECT imp_event_id FROM clicked_imp_event_id_set), 1, 0) AS is_click
FROM wheres.wheres_dsp_parquet_prod.impression_logs
WHERE dt >= :start_datetime
  AND dt < :end_datetime
```

## 3. Airflow 역할

### 주요 기능
- **Summary 테이블 생성**: 1시간 단위로 집계 테이블 자동 생성
- **ETL 파이프라인**: 원천 로그에서 combined log 및 summary 생성
- **배치 처리**: 노출-클릭 데이터를 imp_event_id로 조인

### DAG 예시
```python
@dag(default_args=DableArguments().get(),
     description='hourly ETL for ad',
     schedule=HourlyDagSchedule.hourly_ad_etl_dag,
     start_date=pendulum.datetime(2021, 5, 14),
     catchup=False,
     tags=['hourly', '_hourly_ad_action_count',])
def hourly_ad_etl_dag():
    hourly_ad_action_count = PyRangersK8sPodOperator(
        task_id='hourly_ad_action_count',
        cmds=['/root/.pyenv/versions/current/bin/python',
              '/opt/apps/py-rangers/src/dna/ad/ad_action_count/hourly_ad_action_count.py'],
        arguments=['--execution_datetime', '{{ data_interval_start.isoformat() }}'],
        container_resources=K8S_RESOURCES_TRINO
    )
```

### 처리 프로세스
1. ad_impression과 ad_click 조인하여 ad_combined_log 생성
2. ad_combined_log에서 집계하여 ad_combined_log_summary 생성
3. 시간별 CTR 계산 및 저장

## 4. LLM/Text-to-SQL 시스템

### 시스템 구성
- **LLM 프롬프트 구성**:
  - ad_combined_log_summary 스키마
  - ad_conversion 스키마
  - 예시 쿼리들
- **처리 흐름**:
  1. 사용자의 자연어 분석 요청 입력
  2. 컨텍스트 + 자연어로 LLM이 SQL 생성
  3. 생성된 SQL을 Athena로 실행
  4. 실행 결과를 LLM에게 전달하여 최종 분석

### 중요 포인트
- text-to-sql은 Airflow와 별개 시스템
- Glue에서 테이블 관리
- Redash에서 대시보드 생성

## 5. 빅데이터 처리 철학

### 핵심 원칙
- **실시간성 로그는 각자 저장**: 처음부터 합쳐서 저장하려고 하면 복잡도 증가
- **배치에서 주기적으로 병합**: 효율적인 데이터 처리
- **중복 데이터 비용 절감**: Parquet의 높은 압축률과 저렴한 스토리지 활용

### 참고사항
- **전환 로그의 특성**: 노출/클릭 대비 늦게 발생하는 경향
- **데이터 수집 방식**: Kinesis로 각 이벤트 타입별로 수집

### 관련 링크
- https://dabletech.oopy.io/14a5bbc0-e5c2-80a7-93ce-c7237cd218c8

## 6. 주요 쿼리 예시
```sql
SELECT cre_id, 
       SUM(impressions) as impressions,
       SUM(clicks) as clicks, 
       SUM(clicks) / CAST(SUM(impressions) as REAL) * 100 as ctr
FROM wheres_etl.combined_log_summary
WHERE utc_basic_time >= '2026-02-12-00' 
  AND utc_basic_time < '2026-02-13-00'
GROUP BY cre_id
```

```
cre_id    | impressions | clicks  | ctr      
----------+-------------+---------+----------
iPwhLIArNs| 9253.0      | 330.0   | 0.035664108 
9s2WOeOavF| 12421.0     | 5834.0  | 0.46968845 
JiJzEvI2Bl| 21539.0     | 5206.0  | 0.2417011
```