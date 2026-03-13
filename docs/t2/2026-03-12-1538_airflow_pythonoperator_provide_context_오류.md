# Airflow PythonOperator provide_context 오류 분석

## 발생 일시
- 2026-03-12 15:37:17

## 오류 내용
```
TypeError: Invalid arguments were passed to PythonOperator (task_id: create_hourly_summary). Invalid arguments were:
**kwargs: {'provide_context': True}
```

## 발생 파일
- `services/data_pipeline_t2/dags/03_ad_hourly_summary_test.py`
- 318번째 줄

## AS-IS (오류 발생 코드)
```python
create_hourly_summary = PythonOperator(
    task_id="create_hourly_summary",
    python_callable=_run_hourly_etl,
    provide_context=True,  # ❌ Airflow 3.x에서 제거된 파라미터
)
```

## 원인 분석
1. **Airflow 버전 차이**: Airflow 2.0 이상부터 `provide_context` 파라미터가 제거됨
2. **자동 context 전달**: 최신 버전에서는 PythonOperator가 자동으로 context를 callable 함수에 전달
3. **환경 정보**:
   - 현재 사용 중인 Airflow 버전: 3.1.7 (docker-compose 환경)
   - `provide_context`는 Airflow 1.x 버전의 레거시 파라미터

## TO-BE (수정된 코드)
```python
create_hourly_summary = PythonOperator(
    task_id="create_hourly_summary",
    python_callable=_run_hourly_etl,
    # provide_context=True 제거 - 자동으로 context 전달됨
)
```

## 영향 범위
동일한 오류가 발생하는 모든 DAG 파일:
1. `01_ad_hourly_summary.py` (88번째 줄)
2. `02_ad_daily_summary.py` (86번째 줄)
3. `03_ad_hourly_summary_test.py` (325번째 줄) - 현재 오류 발생
4. `04_ad_daily_summary_test.py` (267번째 줄)

**총 4개 파일에서 동일한 `provide_context=True` 제거 필요**

## 수정 방법
### 즉시 수정 (전체 파일 일괄 처리)
```bash
# PowerShell에서 실행 (Windows)
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2\dags

# provide_context 라인 제거
$files = @("01_ad_hourly_summary.py", "02_ad_daily_summary.py", "03_ad_hourly_summary_test.py", "04_ad_daily_summary_test.py")
foreach ($file in $files) {
    (Get-Content $file) -replace '\s*provide_context=True,\s*' | Set-Content $file
}
```

### 수동 수정
1. **단순 제거**: `provide_context=True,` 라인을 삭제
2. **callable 함수 시그니처 확인**:
   ```python
   def _run_hourly_etl(**context):  # context는 자동으로 전달됨
       dt_utc = context.get('data_interval_end')
       # ...
   ```

## 추가 고려사항
### context 접근 방법 변경
- **AS-IS (Airflow 1.x)**:
  ```python
  def my_function(**context):
      ti = context['ti']
      ds = context['ds']
  ```

- **TO-BE (Airflow 2.x/3.x)**:
  ```python
  # 방법 1: **context로 받기 (권장)
  def my_function(**context):
      ti = context['ti']
      ds = context['ds']
  
  # 방법 2: 특정 파라미터만 받기
  def my_function(ti, ds, **context):
      # ti와 ds를 직접 사용
  ```

## 검증 방법
1. DAG 파일 수정 후 Airflow UI에서 DAG 리로드 확인
2. 오류 메시지가 사라지고 DAG가 정상적으로 로드되는지 확인
3. 테스트 실행으로 context가 올바르게 전달되는지 확인

## 참고 문서
- [Airflow 2.0 Migration Guide - PythonOperator](https://airflow.apache.org/docs/apache-airflow/stable/upgrading-from-1-10/index.html#pythonoperator)
- [Airflow 3.x PythonOperator API](https://airflow.apache.org/docs/apache-airflow/stable/howto/operator/python.html)

## 결론
- Airflow 3.1.7에서 `provide_context=True`는 deprecated된 파라미터
- 모든 PythonOperator에서 해당 파라미터를 제거해야 함
- Context는 자동으로 callable 함수에 전달되므로 기능상 영향 없음
- 총 4개의 DAG 파일 수정 필요