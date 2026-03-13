# DAG에서 ETL 모듈 Import 경로 문제 분석 및 해결

## 문제 상황
- `run_etl.py`에서는 ETL 모듈 import가 정상 작동
- `06_ad_daily_summary_period.py` DAG에서는 import 실패
- 오류: `ModuleNotFoundError: No module named 'etl_summary_t2'`

## 원인 분석

### AS-IS (현재 상태)
```python
# 06_ad_daily_summary_period.py의 잘못된 sys.path 설정
ETL_PACKAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'etl_summary_t2')
if ETL_PACKAGE_PATH not in sys.path:
    sys.path.insert(0, os.path.dirname(ETL_PACKAGE_PATH))
```

#### 경로 분석:
- `__file__`: `/dags/06_ad_daily_summary_period.py`
- `os.path.dirname(__file__)`: `/dags`
- `os.path.dirname(os.path.dirname(__file__))`: `/data_pipeline_t2`
- `ETL_PACKAGE_PATH`: `/data_pipeline_t2/etl_summary_t2`
- 실제로 추가되는 경로: `/data_pipeline_t2` (올바름)
- **하지만 조건문이 잘못됨**: `ETL_PACKAGE_PATH not in sys.path`는 `/data_pipeline_t2/etl_summary_t2`를 검사

### run_etl.py가 작동하는 이유
- `run_etl.py`는 `etl_summary_t2` 패키지 내부에 위치
- 상대 import 사용: `from .hourly_etl import HourlyETL`
- 패키지 내부에서 실행되므로 경로 문제 없음

### 06_ad_daily_summary_period.py가 작동하지 않는 이유
1. **잘못된 조건문**: 올바른 경로를 추가하지만, 조건 검사가 잘못됨
2. **PythonOperator 문제**: `_run_daily_etl_period` 함수 실행 시 sys.path가 초기화될 수 있음
3. **Airflow 실행 환경**: DAG 로드 시점과 태스크 실행 시점의 Python 환경이 다를 수 있음

## TO-BE (해결 방안)

### 1. sys.path 설정 수정
```python
# 올바른 경로 설정
DATA_PIPELINE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DATA_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, DATA_PIPELINE_PATH)
```

### 2. PythonOperator 함수 내부에서도 경로 설정
```python
def _run_daily_etl_period(**context):
    """지정된 기간의 DailyETL 실행"""
    import sys
    import os
    
    # 함수 내부에서도 경로 추가
    data_pipeline_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if data_pipeline_path not in sys.path:
        sys.path.insert(0, data_pipeline_path)
    
    from etl_summary_t2.daily_etl import DailyETL
    # ... 나머지 코드
```

### 3. import 위치 조정
- 모듈 최상단의 import는 경로 설정 이후로 이동
- 또는 함수 내부에서만 import 수행

## 구현 계획
1. 06_ad_daily_summary_period.py의 sys.path 설정 수정
2. _run_daily_etl_period 함수 내부에 경로 설정 추가
3. 05_ad_hourly_summary_period.py도 동일하게 수정 (일관성 유지)
4. 테스트 후 다른 DAG 파일들도 확인 및 수정