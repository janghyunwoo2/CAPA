# Airflow data_interval 시간 처리 문제 분석

## 문제 상황
- **실행 시간**: 2026-03-13 12:55 (KST)
- **찾는 데이터**: 12시 데이터 ❌
- **기대한 데이터**: 11시 데이터 ✅

## 로그 분석
```
UTC time: 2026-03-13 03:10:00+00:00
KST time: 2026-03-13 12:10:00+09:00
Processing hour: 2026-03-13-12  # 잘못됨! 11시여야 함
```

## 문제 원인

### AS-IS (현재 - 잘못된 로직)
```python
# data_interval_start를 그대로 변환
dt_utc = context["data_interval_start"]  # UTC 03:10
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')  # KST 12:10
etl = HourlyETL(target_hour=dt_kst)  # 12시 데이터 처리 ❌
```

### Airflow 스케줄링 개념
- **Schedule**: `"10 * * * *"` (매시간 10분)
- **12:10 실행 시**:
  - data_interval: 11:00 ~ 12:00
  - 처리할 데이터: 11시

### TO-BE (올바른 로직)
```python
# data_interval_start는 처리할 데이터의 "시작" 시점
dt_utc = context["data_interval_start"]  # UTC 02:00 (11:00 KST)
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')  # KST 11:00
etl = HourlyETL(target_hour=dt_kst)  # 11시 데이터 처리 ✅
```

## 해결 방안

### 옵션 1: data_interval_start 올바르게 사용
```python
def run_hourly_etl(**context):
    # data_interval_start는 이미 처리할 시간을 가리킴
    dt_utc = context["data_interval_start"]
    dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    
    print(f"[INFO] Execution time (UTC): {context['logical_date']}")
    print(f"[INFO] Data interval start (UTC): {dt_utc}")
    print(f"[INFO] Processing hour (KST): {dt_kst}")
    
    etl = HourlyETL(target_hour=dt_kst)
    etl.run()
```

### 옵션 2: logical_date에서 1시간 빼기
```python
def run_hourly_etl(**context):
    # 실행 시간에서 1시간 전 데이터 처리
    execution_time = context["logical_date"]
    target_time = execution_time - timedelta(hours=1)
    dt_kst = pendulum.instance(target_time).in_timezone('Asia/Seoul')
    
    etl = HourlyETL(target_hour=dt_kst)
    etl.run()
```

## 추가 문제 발견

### 1. data_interval 시간 문제
로그에서 `data_interval_start`가 `03:10`으로 나타나는 것도 이상합니다:
- 정상: `02:00` (11시 데이터의 시작)
- 실제: `03:10` (실행 시간과 동일)

### 2. start_date 시간대 문제
```python
# AS-IS (문제)
start_date=pendulum.datetime(2026, 2, 13, tz=pendulum.timezone("Asia/Seoul"))

# TO-BE (수정)
start_date=pendulum.datetime(2026, 2, 13, tz="UTC")
```

### 3. 스케줄 타이밍 문제
- 현재: `"10 * * * *"` (매시간 10분)
- data_interval: 11:10 ~ 12:10
- 하지만 hourly 데이터는 보통 11:00 ~ 12:00 단위

## 최종 해결 방안

### 방안 1: ETL에서 시간을 정시로 조정
```python
def run_hourly_etl(**context):
    dt_utc = context["data_interval_start"]
    dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
    
    # 정시로 조정 (예: 11:10 → 11:00)
    target_hour = dt_kst.replace(minute=0, second=0, microsecond=0)
    
    etl = HourlyETL(target_hour=target_hour)
    etl.run()
```

### 방안 2: 스케줄을 정시로 변경
```python
schedule="0 * * * *"  # 매시간 정시
```

## 실행 후 확인사항
1. 디버깅 로그에서 context 값들 확인
2. data_interval_start가 올바른 값인지 검증
3. 처리되는 시간이 이전 시간인지 확인