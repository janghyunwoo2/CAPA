# Period DAG 비교 분석 (05_ad_hourly vs 06_ad_daily)
- 작성일시: 2026-03-13 09:35
- 분석 대상: 05_ad_hourly_summary_period.py, 06_ad_daily_summary_period.py

## AS-IS
Period DAG들이 작성되었으나 상세한 차이점 분석이 없었음

## TO-BE  
주기 설정 이외의 차이점과 특이사항을 명확히 문서화

## 주요 차이점 분석

### 1. ETL 클래스 사용
- **05_ad_hourly_summary_period.py**: `HourlyETL` 사용
- **06_ad_daily_summary_period.py**: `DailyETL` 사용

### 2. 파라미터 차이
#### 05번 (Hourly)
```python
params={
    "start_date": Param(...),
    "end_date": Param(...),
    "hours": Param(  # 시간 범위 파라미터 추가
        default="0-23",
        type='string',
        description="처리할 시간 범위 (예: 0-23, 9-18, 12)"
    ),
}
```

#### 06번 (Daily)
```python
params={
    "start_date": Param(...),
    "end_date": Param(...),
    "skip_missing_hours": Param(  # 결측 시간 처리 옵션 추가
        default=True,
        type='boolean',
        description="일부 시간대 데이터가 없어도 진행할지 여부"
    ),
}
```

### 3. 시간 처리 로직
#### 05번 (Hourly)
- 각 날짜의 지정된 시간 범위(hours)를 반복 처리
- 미래 시간은 자동으로 스킵 (`if dt_kst <= pendulum.now('Asia/Seoul')`)

#### 06번 (Daily)  
- 날짜 단위로 처리 (시간 미지정)
- 오늘 날짜는 스킵 (`if current_date.date() >= datetime.now().date()`)

### 4. 실패 처리 방식
#### 05번 (Hourly)
- 실패해도 계속 진행 (fail_count만 증가)
- 마지막에 성공/실패 개수만 로그

#### 06번 (Daily)
- `skip_missing_hours=False`일 때 실패 시 중단
- 실패한 날짜 목록 별도 관리

### 5. 추가 Task 차이
#### 05번 (Hourly)
- create_hourly_summary → register_partitions (2개 태스크)

#### 06번 (Daily)
- create_daily_summary → register_partitions → **trigger_reports** (3개 태스크)
- 리포트 생성 트리거 추가됨

### 6. 배치 리포트 스크립트 (06번만 존재)
```python
BATCH_REPORT_SCRIPT = textwrap.dedent("""...""")
def _trigger_reports_batch(**context):
    """기간별 리포트 생성 트리거"""
```

### 7. 테이블 차이
- 05번: `ad_combined_log` 테이블에 파티션 등록
- 06번: `ad_combined_log_summary` 테이블에 파티션 등록

## 특이사항

### 1. Import 경로 처리 중복
두 파일 모두 PythonOperator 내부에서 sys.path 추가를 중복 수행:
```python
# 파일 상단
DATA_PIPELINE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DATA_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, DATA_PIPELINE_PATH)

# 함수 내부에서도 동일 작업
def _run_hourly_etl_period(**context):
    data_pipeline_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if data_pipeline_path not in sys.path:
        sys.path.insert(0, data_pipeline_path)
```
→ Airflow 실행 환경에서 필요하다는 주석이 있지만, 중복 여부 확인 필요

### 2. skip_missing_hours 속성 체크
06번 파일에서만 발견:
```python
if hasattr(etl, 'skip_missing_hours'):
    etl.skip_missing_hours = SKIP_MISSING
```
→ DailyETL 클래스가 이 속성을 지원하는지 불확실하여 hasattr로 체크

### 3. 로거 사용 차이
- 05번: logger를 사용하여 구조화된 로그
- 06번: logger와 print 혼재 사용

### 4. KubernetesPodOperator 볼륨 마운트
두 파일 모두 동일한 볼륨 설정 사용:
```python
volumes=[{
    "name": "etl-code",
    "hostPath": {
        "path": "/opt/airflow/services/data_pipeline_t2",
        "type": "Directory"
    }
}]
```

## 권장사항

1. **로거 통일**: 모든 출력을 logger로 통일하여 일관성 확보
2. **skip_missing_hours 확인**: DailyETL 클래스에서 실제로 지원하는지 확인 필요
3. **Import 경로 처리**: 중복 제거 또는 명확한 주석 추가
4. **에러 핸들링**: 05번도 skip 옵션 추가 고려

## 실행 결과
- 05_ad_hourly_summary_period.py 파일 분석 완료
- 06_ad_daily_summary_period.py 파일과 비교 분석 완료
- 주기 설정 외의 차이점 문서화 완료
- 특이사항 발견하여 문서에 기록함 (수정하지 않음)