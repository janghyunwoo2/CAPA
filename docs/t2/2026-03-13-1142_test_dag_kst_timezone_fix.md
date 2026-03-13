# Test DAG KST 시간대 수정

## 문제 상황
- `03_ad_hourly_summary_test.py` DAG 실행 시 02시로 돌아가는 문제 발생
- 현재 시간(KST 11:42)에서 실행해도 잘못된 시간으로 처리됨

## AS-IS
```python
def run_hourly_etl(**context):
    # 수동 실행 시 현재 KST 시간 사용
    dt = context.get("data_interval_start", pendulum.now('Asia/Seoul'))
    print(f"[INFO] Running HourlyETL for {dt}")
    etl = HourlyETL(target_hour=dt)
    etl.run()
```

### 문제점
- `data_interval_start`가 있을 경우 UTC 시간을 그대로 사용
- pendulum timezone 변환이 제대로 되지 않음
- 테스트 DAG임에도 스케줄러 시간을 따라감

## TO-BE
```python
def run_hourly_etl(**context):
    # 항상 현재 KST 시간 사용 (수동 테스트 전용)
    dt_kst = pendulum.now('Asia/Seoul')
    
    # 디버깅을 위한 상세 로그
    print(f"[DEBUG] Current KST time: {dt_kst}")
    print(f"[DEBUG] Hour: {dt_kst.hour}, Date: {dt_kst.date()}")
    
    # context에서 data_interval_start가 있으면 UTC->KST 변환
    if "data_interval_start" in context and context["data_interval_start"]:
        dt_utc = context["data_interval_start"]
        print(f"[DEBUG] data_interval_start (UTC): {dt_utc}")
        # 만약 data_interval_start가 있더라도 수동 테스트에서는 현재 시간 사용
        print(f"[DEBUG] Using current KST time instead for manual test")
    
    print(f"[INFO] Running HourlyETL for {dt_kst}")
    etl = HourlyETL(target_hour=dt_kst)
    etl.run()
    print(f"[SUCCESS] HourlyETL completed successfully for hour={dt_kst.hour}")
```

### 개선사항
1. **항상 현재 KST 시간 사용**: 테스트 DAG는 수동 실행 전용이므로 항상 현재 시간 기준
2. **명확한 변수명**: `dt_kst`로 KST 시간임을 명확히 표시
3. **디버깅 로그 추가**: 시간 처리 과정을 상세히 로깅
4. **data_interval_start 무시**: 있어도 현재 시간 사용함을 명시

## 적용 결과
- 수동 실행 시 항상 현재 KST 시간 기준으로 ETL 실행
- 02시로 돌아가는 문제 해결
- 디버깅이 용이한 상세 로그 제공

## 참고사항
- 프로덕션 DAG(`01_ad_hourly_summary`)는 스케줄러에 의해 실행되므로 다른 로직 사용
- 테스트 DAG는 수동 실행만 지원하므로 현재 시간 사용이 적절함