# Data Quality DAG 분석 보고서

이 문서는 `src/data_pipeline_t2/dags/01_data_quality_dag.py` 파일의 분석 결과를 담고 있습니다.

## 1. 개요
해당 DAG는 수집 및 정제된 데이터의 품질을 검증하고, 그 결과를 보고서 형태로 S3에 저장하는 역할을 수행합니다.

## 2. 주요 확인 항목 (Data Quality Metrics)

### 2.1. 컬럼별 검증
- **Null Ratio (결측치 비율):** 주요 컬럼(`user_id`, `email`, `created_at` 등)의 데이터 누락 확인
- **Unique Violations (유일성 위반):** 고유값 중복 여부 확인 (예: 중복 가입, 중복 ID)
- **Data Type Errors (데이터 타입 오류):** 필드 타입 불일치 데이터 탐지
- **Value Range Checks (범위 검사):** 비즈니스 로직상 허용되는 값의 범위 확인 (예: 나이, 가격)

### 2.2. 테이블별 검증
- `users`, `orders` 테이블 대상
- **PK Duplicates:** 기본키 중복 확인
- **FK Violations:** 외래키 관계 무결성 확인
- **Row/Column Counts:** 데이터 스키마 및 볼륨 정합성 확인

## 3. 종합 품질 점수 (Scores)
다음 네 가지 지표를 바탕으로 0~1 사이의 점수를 산출합니다.
- **Completeness (완전성):** 데이터가 빠짐없이 채워졌는가
- **Accuracy (정확성):** 데이터가 실제 값을 정확히 반영하는가
- **Consistency (일관성):** 데이터 모델 간 일치하는가
- **Timeliness (적시성):** 제때 데이터가 생성/수집되었는가

## 4. 리포팅 및 인프라 연동
- **저장 위치:** AWS S3 (`capa-logs-dev-ap-northeast-2`)
- **저장 경로:** `metadata/quality_YYYYMMDD.json`
- **사용 Hook:** `S3Hook` (AWS Connection ID: `athena`)

## 5. 비고
- 현재 코드의 일부 지표값은 테스트를 위한 샘플 데이터(Mock)로 구성되어 있으며, 실제 운영 시 쿼리 결과와 연동되도록 설계되어 있습니다.
