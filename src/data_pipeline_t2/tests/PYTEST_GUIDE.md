# Pytest Guide for Airflow DAG Tests

## 디렉토리 구조

```
CAPA/
├── tests/
│   ├── conftest.py                    # Pytest 설정 및 공유 픽스처
│   ├── test_schema_extraction_dag.py  # 스키마 추출 DAG 테스트
│   ├── test_data_quality_dag.py       # 데이터 품질 검사 DAG 테스트
│   ├── test_preagg_dag.py             # Pre-aggregation DAG 테스트
│   └── pytest.ini                     # Pytest 설정
├── dags/
│   ├── schema_extraction_dag.py
│   ├── data_quality_dag.py
│   └── preagg_dag.py
├── requirements.txt
└── ...
```

## 필수 패키지

```bash
pip install pytest pytest-cov pytest-mock boto3 pandas sqlalchemy
```

## 테스트 실행 명령

### 모든 테스트 실행
```bash
pytest tests/ -v
```

### 특정 테스트 파일 실행
```bash
pytest tests/test_schema_extraction_dag.py -v
pytest tests/test_data_quality_dag.py -v
pytest tests/test_preagg_dag.py -v
```

### 특정 테스트 클래스/함수만 실행
```bash
pytest tests/test_schema_extraction_dag.py::TestSchemaExtraction -v
pytest tests/test_data_quality_dag.py::TestDataQualityChecks::test_quality_check_success -v
```

### 커버리지 리포트 생성
```bash
pytest tests/ --cov=dags --cov-report=html
# HTML 리포트: htmlcov/index.html
```

### 마커로 특정 테스트만 실행
```bash
pytest tests/ -m unit -v              # Unit 테스트만
pytest tests/ -m integration -v       # Integration 테스트만
pytest tests/ -m "not slow" -v        # Slow 테스트 제외
```

## 테스트 파일 설명

### 1. test_schema_extraction_dag.py
**목적**: 스키마 추출 DAG 검증

**주요 테스트**:
- `test_extract_schema_success`: DB에서 스키마를 성공적으로 추출하고 S3에 업로드
- `test_extract_schema_empty_db`: 빈 DB(테이블 없음)에서 추출
- `test_extract_schema_db_connection_error`: DB 연결 실패 처리
- `test_extract_schema_s3_upload_error`: S3 업로드 실패 처리
- `test_schema_json_format`: 출력 JSON 형식 검증
- `test_schema_naming_convention`: S3 파일명 규칙 검증

**예제 실행**:
```bash
pytest tests/test_schema_extraction_dag.py::TestSchemaExtraction::test_extract_schema_success -v
```

### 2. test_data_quality_dag.py
**목적**: 데이터 품질 검사 DAG 검증

**주요 테스트**:
- `test_quality_check_success`: 성공적인 품질 검사 및 리포트 생성
- `test_quality_check_too_many_nulls`: 결측치 과다 감지
- `test_quality_report_schema`: 리포트 출력 스키마 검증
- `test_quality_check_data_type_errors`: 데이터 타입 불일치 감지
- `test_quality_metrics_validation`: 개별 메트릭 검증

**예제 실행**:
```bash
pytest tests/test_data_quality_dag.py::TestDataQualityChecks -v
```

### 3. test_preagg_dag.py
**목적**: Pre-aggregation(미리 계산된 뷰) DAG 검증

**주요 테스트**:
- `test_preagg_sql_validity`: SQL 문법 검증
- `test_preagg_output_table_name`: 출력 테이블명 규칙 검증
- `test_preagg_partitioning_strategy`: 파티셔닝 전략 검증
- `test_preagg_aggregation_metrics`: 집계 지표 검증
- `test_preagg_idempotency`: 멱등성(반복 실행 안전성) 검증
- `test_preagg_table_metadata`: 테이블 메타데이터 구조 검증

**예제 실행**:
```bash
pytest tests/test_preagg_dag.py::TestPreAggregation::test_preagg_sql_validity -v
```

## 픽스처(Fixtures) 사용

### conftest.py에 정의된 픽스처
- `airflow_home`: Airflow 홈 디렉토리 설정
- `aws_credentials`: AWS 자격증명 모킹
- `db_credentials`: DB 자격증명 모킹
- `s3_bucket`: S3 버킷명 환경변수 설정

### 테스트에서 픽스처 사용
```python
def test_example(mock_context, mock_env, monkeypatch):
    """테스트에서 픽스처 활용"""
    monkeypatch.setenv('MY_VAR', 'value')
    assert mock_context['ds'] == '2025-01-02'
```

## 모킹(Mocking) 패턴

### boto3 클라이언트 모킹
```python
@patch('boto3.client')
def test_s3_operation(mock_s3_client, mock_context):
    mock_s3 = MagicMock()
    mock_s3_client.return_value = mock_s3
    mock_s3.put_object.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    # 테스트 로직
```

### SQLAlchemy 엔진 모킹
```python
@patch('sqlalchemy.create_engine')
def test_db_operation(mock_engine, mock_context):
    mock_conn = MagicMock()
    mock_engine.return_value = mock_conn
    # 테스트 로직
```

## 운영

### 테스트 실패 디버깅
```bash
# 더 자세한 로그 출력
pytest tests/ -vv -s --tb=long

# 첫 번째 실패 시 중단
pytest tests/ -x

# 이전 실패한 테스트만 다시 실행
pytest tests/ --lf

# 특정 키워드로 테스트 필터링
pytest tests/ -k "success" -v
```

### CI/CD 통합 예시 (GitHub Actions)
```yaml
name: Airflow DAG Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: |
          pytest tests/ --cov=dags --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 주의사항

1. **모킹은 필수**: AWS/DB 연결이 없는 환경에서도 테스트가 동작해야 함
2. **환경변수**: `conftest.py`의 픽스처로 환경변수를 항상 정의
3. **데이터**: 테스트용 샘플 데이터를 하드코딩하거나 fixture로 제공
4. **타이밍**: 비동기/스케줄 관련 테스트는 신중하게 설계(mocking 권장)

## 예제: 전체 실행 및 리포트

```bash
# 모든 테스트 실행 + 커버리지 + 리포트
pytest tests/ -v --cov=dags --cov-report=html --cov-report=term

# 결과 확인
echo "Detailed results in htmlcov/index.html"
```

---
작성: CAPA - Pytest 테스트 가이드
