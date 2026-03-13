# Airflow DAG schedule_interval 오류 해결

## 발생 일시
2026-03-12 16:43:58

## 문제 상황
```
TypeError: DAG.__init__() got an unexpected keyword argument 'schedule_interval'
```

## 원인 분석
Airflow 버전 2.4 이상에서는 `schedule_interval` 파라미터가 deprecated되고 `schedule`로 변경되었습니다.

## AS-IS
```python
with DAG(
    dag_id='01_ad_hourly_summary',
    schedule_interval='0 * * * *',  # 매시간 정각
    ...
)
```

## TO-BE
```python
with DAG(
    dag_id='01_ad_hourly_summary',
    schedule='0 * * * *',  # 매시간 정각
    ...
)
```

## 해결 방법
1. 모든 DAG 파일에서 `schedule_interval` → `schedule`로 변경
2. 영향받는 파일:
   - 01_ad_hourly_summary.py
   - 02_ad_daily_summary.py

## 검증 방법
```bash
# Airflow에서 DAG 파싱 오류 확인
airflow dags list
```

## 해결 결과
- ✅ 01_ad_hourly_summary.py: `schedule_interval` → `schedule` 변경 완료
- ✅ 02_ad_daily_summary.py: `schedule_interval` → `schedule` 변경 완료
- 수정 시간: 2026-03-12 16:44