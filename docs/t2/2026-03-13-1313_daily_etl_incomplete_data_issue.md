# DailyETL 불완전한 데이터 처리 문제 분석

## 문제 상황

### 발생 시간
- 2026-03-13 13:11:12

### 증상
```
[2026-03-13 13:11:21] WARNING - ⚠️  Only 2/24 hours of data available for 2026-03-13. Proceeding with available data.
```

### 실행 로그 요약
- DailyETL 실행 시간: 2026-03-13 13:10:47+09:00
- 처리하려는 날짜: 2026-03-13 (당일)
- 사용 가능한 데이터: 2/24 시간 (약 8%)
- 처리된 데이터: 10,412 rows

## 문제 분석

### 근본 원인
DailyETL이 **아직 끝나지 않은 당일(2026-03-13)의 데이터를 처리**하려고 시도함

### 상세 분석
1. **현재 시간**: 2026-03-13 13:13 (KST)
2. **처리 대상 날짜**: 2026-03-13 (당일)
3. **문제점**: 
   - 하루가 아직 끝나지 않았음 (13시간/24시간 = 54% 진행)
   - DailyETL은 완전한 24시간 데이터를 기반으로 일일 집계를 수행해야 함
   - 불완전한 데이터로 집계 시 정확한 일일 통계가 불가능

### AS-IS (현재 상황)
```python
# 02_ad_daily_summary.py의 run_daily_etl 함수
dt_utc = context["data_interval_start"]
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
etl = DailyETL(target_date=dt_kst)  # 당일 날짜를 그대로 사용
```

- DAG 스케줄: 매일 02:00 실행
- data_interval_start가 2026-03-13 00:00:00을 가리킴
- DailyETL이 2026-03-13 데이터를 처리하려 함

## 해결 방안

### TO-BE (해결책)

#### 방안 1: DailyETL에서 전일 데이터 처리 (권장)
```python
# run_daily_etl 함수 수정
dt_utc = context["data_interval_start"]
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')

# 전일 날짜로 변경
target_date = dt_kst.subtract(days=1)
print(f"[INFO] Processing previous day: {target_date}")

etl = DailyETL(target_date=target_date)
etl.run()
```

**장점**:
- DAG 스케줄(02:00)에서 전일 완전한 24시간 데이터 처리
- Airflow의 일반적인 패턴과 일치
- 데이터 무결성 보장

#### 방안 2: Airflow 스케줄 조정 (대안)
```python
# DAG 정의에서 schedule 수정
schedule="0 2 * * *",  # 현재: 매일 02:00
# 변경 ↓
schedule="0 0 * * *",  # 매일 00:00 (자정)

# 그리고 data_interval_end 사용
dt_utc = context["data_interval_end"]  # start 대신 end 사용
```

**단점**:
- 자정 실행 시 마지막 시간(23시) 데이터가 아직 적재되지 않을 수 있음
- 데이터 지연 위험

## 실행 흐름 예시

### 수정 후 정상 동작
```
2026-03-14 02:00 DAG 실행
→ data_interval_start: 2026-03-14 00:00
→ target_date: 2026-03-13 (전일)
→ 2026-03-13의 완전한 24시간 데이터 처리
→ ✅ 정확한 일일 집계 완료
```

## 추가 고려사항

### 2. 데이터 검증 강화
```python
# DailyETL 내부에서 추가 검증
if available_hours < 24:
    if not skip_missing_hours:
        raise ValueError(f"Incomplete data: only {available_hours}/24 hours available")
    else:
        logger.warning(f"Processing with incomplete data: {available_hours}/24 hours")
```

### 3. 모니터링 개선
- Slack 알림에 데이터 완전성 정보 추가
- 불완전한 데이터로 처리 시 경고 레벨 상향

## 구현 우선순위

1. **즉시**: `02_ad_daily_summary.py`의 `run_daily_etl` 함수 수정

## 영향 범위

- **영향 받는 파일**:
  - `services/data_pipeline_t2/dags/02_ad_daily_summary.py`
  
- **데이터 영향**:
  - 기존 불완전 데이터는 다음 실행 시 덮어쓰기됨
  - 정확한 일일 통계 제공 가능