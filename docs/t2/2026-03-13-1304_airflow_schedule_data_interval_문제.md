# Airflow Schedule과 Data Interval 문제 분석 및 해결

## 문제 상황
- **발생 시간**: 2026-03-13 13:04
- **증상**: 1시 10분에 실행되는 DAG가 1시 데이터를 찾음 (정상: 0시 데이터를 찾아야 함)
- **영향 DAG**: `01_ad_hourly_summary.py`

## AS-IS (문제 상황)

### 스케줄 변경 이력
- 기존: `"0 * * * *"` (매시간 정각)
- 변경: `"10 * * * *"` (매시간 10분)

### 문제 동작
```
13:10 실행 시:
- data_interval_start: 13:00 (KST)
- 처리 시도: 13시 데이터 (아직 생성되지 않음)
- 결과: 데이터 없음 오류
```

### 기존 코드
```python
dt_utc = context["data_interval_start"]
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
etl = HourlyETL(target_hour=dt_kst)  # 13시를 그대로 전달
```

## TO-BE (해결 방안)

### 수정 로직
- data_interval_start에서 1시간을 빼서 이전 시간 데이터 처리
- 예: 13:10 실행 → 12시 데이터 처리

### 수정된 코드
```python
dt_utc = context["data_interval_start"]
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')

# 실제 처리할 시간: data_interval_start - 1시간
target_hour_kst = dt_kst.subtract(hours=1)

print(f"  - data_interval_start (KST): {dt_kst.format('YYYY-MM-DD HH:00')}")
print(f"  - Target hour for processing: {target_hour_kst.format('YYYY-MM-DD HH:00')} (previous hour)")

etl = HourlyETL(target_hour=target_hour_kst)  # 12시를 전달
```

## 원인 분석

### Airflow 스케줄링 동작
1. **정각 실행 (`0 * * * *`)**: 
   - 12:00 실행 → data_interval: 11:00~12:00
   - data_interval_start = 11:00 (이전 시간)

2. **10분 실행 (`10 * * * *`)**: 
   - 12:10 실행 → data_interval: 12:00~13:00 
   - data_interval_start = 12:00 (현재 시간)
   - 하지만 12시 데이터는 아직 완성되지 않았을 가능성

### 데이터 파이프라인 타이밍
- 12:00~12:59: 데이터 생성 중
- 13:00: 12시 데이터 완성
- 13:10: DAG 실행 (12시 데이터 처리)

## 검증 계획
1. 수정된 DAG로 수동 실행 테스트
2. 로그에서 target_hour 확인
3. 처리되는 S3 파티션 경로 확인

## 관련 파일
- `/services/data_pipeline_t2/dags/01_ad_hourly_summary.py`
- `/services/data_pipeline_t2/dags/etl_modules/hourly_etl.py`