# DailyETL 전일 데이터 처리로 수정

## 수정 시간
- 2026-03-13 13:19 (KST)

## 수정 파일
- `services/data_pipeline_t2/dags/02_ad_daily_summary.py`
- `.airflow_t2/dags/02_ad_daily_summary.py` (복사본 동기화)

## 문제 상황
- DailyETL이 당일 데이터를 처리하려고 시도
- 하루가 끝나지 않은 상태에서 불완전한 데이터로 집계 수행
- 예: 2026-03-13 13:11에 실행 시 2/24시간 데이터만 사용

## AS-IS (수정 전)
```python
def run_daily_etl(**context):
    try:
        # UTC to KST 변환
        dt_utc = context["data_interval_start"]
        dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
        print(f"[INFO] UTC time: {dt_utc}, KST time: {dt_kst}")
        print(f"[INFO] Running DailyETL for {dt_kst}")
        etl = DailyETL(target_date=dt_kst)  # 당일 날짜 그대로 사용
        etl.run()
```

## TO-BE (수정 후)
```python
def run_daily_etl(**context):
    try:
        # UTC to KST 변환
        dt_utc = context["data_interval_start"]
        dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')
        
        # 전일 날짜로 변경 (완전한 24시간 데이터를 처리하기 위함)
        target_date = dt_kst.subtract(days=1)
        print(f"[INFO] UTC time: {dt_utc}, KST time: {dt_kst}")
        print(f"[INFO] Processing previous day: {target_date}")
        print(f"[INFO] Running DailyETL for {target_date}")
        
        etl = DailyETL(target_date=target_date)  # 전일 날짜 사용
        etl.run()
```

## 주요 변경 사항
1. `target_date = dt_kst.subtract(days=1)` 추가
2. 전일 날짜를 사용하여 DailyETL 초기화
3. 로그 메시지에 "Processing previous day" 추가

## 기대 효과
- **데이터 완전성 보장**: 24시간 전체 데이터로 정확한 일일 집계
- **Airflow 패턴 준수**: 일반적인 ETL 패턴 (T+1 처리)
- **안정적인 운영**: 데이터 누락 없이 일관된 결과 제공

## 실행 시나리오
```
2026-03-14 02:00 DAG 실행
→ data_interval_start: 2026-03-14 00:00 (UTC)
→ dt_kst: 2026-03-14 09:00 (KST)
→ target_date: 2026-03-13 (전일)
→ 2026-03-13의 완전한 24시간 데이터 처리
→ ✅ 정확한 일일 집계 완료
```

## 관련 문서
- [2026-03-13-1313_daily_etl_incomplete_data_issue.md](2026-03-13-1313_daily_etl_incomplete_data_issue.md)