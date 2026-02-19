# 02_preagg_dag.py 설명서

`02_preagg_dag.py` 파일은 AWS Athena를 활용하여 대용량 원시 로그 데이터를 효율적으로 집계하고 관리하기 위한 Airflow DAG를 정의합니다.

## 1. 개요 (Overview)
- **DAG ID**: `02_preagg_daily`
- **주요 목적**: Athena CTAS (Create Table As Select) 기능을 사용하여 원시 로그(Raw Logs)를 일일 단위로 사전 집계(Pre-aggregation)함으로써 쿼리 성능을 향상시키고 비용을 절감합니다.
- **실행 주기**: `@daily` (매일 1회 실행)

## 2. 주요 태스크 구성 (Workflow)

집계 프로세스는 다음과 같은 순서로 진행됩니다:

1.  **`start`**: DAG 시작을 알리는 더미 태스크입니다.
2.  **`create_daily_aggregation`**: 
    - 이 DAG의 핵심 태스크로, Athena를 사용하여 `analytics.preagg_ads_daily` 테이블을 생성하거나 업데이트합니다.
    - **집계 항목**: 광고주 ID(`advertiser_id`) 및 날짜(`ds`)별로 그룹화하여 다음 지표를 계산합니다.
        - 총 이벤트 수 (`total_events`)
        - 노출 수 (`impressions`)
        - 클릭 수 (`clicks`)
        - 전환 수 (`conversions`)
        - 입찰 금액 관련 통계 (`total_bid_amount`, `avg_bid_amount`, `max_bid_amount`, `min_bid_amount`)
    - **최적화**: 데이터를 **Parquet** 형식으로 저장하고, 날짜(`ds`) 기반으로 **파티셔닝**하여 쿼리 스캔 효율을 극대화합니다.
3.  **`create_hourly_aggregation`**: (현재 샘플 로직) 시간 단위의 세부 집계 테이블 생성을 위한 태스크입니다.
4.  **`validate_aggregation`**: (현재 샘플 로직) 원본 데이터와 집계 데이터의 행 수(Row Count) 등을 비교하여 데이터 정합성을 검증합니다.
5.  **`end`**: 모든 작업이 성공적으로 완료되었음을 나타내는 더미 태스크입니다.

## 3. 기술적 특징

### Athena Operator 대체 로직
코드 내에서 `USE_ATHENA_OPERATOR` 플래그를 통해 실제 `AthenaOperator`를 사용하거나, 환경이 준비되지 않은 경우 `PythonOperator`와 `boto3`를 사용하는 로직으로 자동 전환됩니다. 이는 특히 로컬 테스트 환경이나 자격 증명이 없는 환경에서의 유연성을 제공합니다.

### 쿼리 최적화 (CTAS & Parquet)
Athena의 CTAS 쿼리를 사용하여 다음과 같은 최적화를 수행합니다:
- **Parquet Format**: 컬럼 기반 저장 형식을 사용하여 필요한 데이터만 읽어 성능을 높이고 비용을 줄입니다.
- **Partitioning**: `ds` 컬럼으로 파티셔닝하여 특정 날짜의 데이터만 빠르게 조회할 수 있도록 합니다.

## 4. 관련 환경 변수
- `S3_BUCKET`: 집계 결과 및 쿼리 결과가 저장될 S3 버킷 이름.
- `AWS_REGION`: Athena 및 S3가 위치한 AWS 리전 (기본값: `ap-northeast-2`).

## 5. 비즈니스 가치
- **비용 절감**: 매번 전체 원시 로그를 스캔하는 대신 사전 집계된 테이블을 조회함으로써 Athena 쿼리 비용을 대폭 절감합니다.
- **성능 향상**: 대시보드(예: Redash)나 분석 도구에서 쿼리 응답 속도를 수 초 이내로 단축시킵니다.
