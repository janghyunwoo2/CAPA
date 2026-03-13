# ETL 스케줄 업데이트 계획 (2026-03-13 09:28)

## 요구사항
- **01_ad_hourly_summary**: 매시간 10분마다 직전 1시간 ETL 실행
- **02_ad_daily_summary**: 매일 02시에 직전 하루 ETL 실행

## AS-IS (현재 상태)

### 01_ad_hourly_summary.py
- **스케줄**: `schedule="0 * * * *"` (매시간 정각)
- **실행 예시**: 
  - 01:00에 실행 → data_interval_start: 00:00
  - 02:00에 실행 → data_interval_start: 01:00

### 02_ad_daily_summary.py
- **스케줄**: `schedule="0 1 * * *"` (매일 01:00)
- **실행 예시**: 
  - 3월 13일 01:00에 실행 → data_interval_start: 3월 12일 00:00

## TO-BE (변경 후)

### 01_ad_hourly_summary.py
- **스케줄**: `schedule="10 * * * *"` (매시간 10분)
- **실행 예시**: 
  - 01:10에 실행 → data_interval_start: 00:00 (00:00-00:59 데이터 처리)
  - 02:10에 실행 → data_interval_start: 01:00 (01:00-01:59 데이터 처리)
- **장점**: 원본 로그가 S3에 충분히 적재된 후 ETL 실행

### 02_ad_daily_summary.py
- **스케줄**: `schedule="0 2 * * *"` (매일 02:00)
- **실행 예시**: 
  - 3월 13일 02:00에 실행 → data_interval_start: 3월 12일 00:00
  - 3월 12일 전체 hourly 데이터(24개) + 3월 12일 conversion 데이터 조인
- **장점**: 
  - 모든 hourly ETL이 완료된 후 실행 (01:10까지 모든 시간 처리 완료)
  - Conversion 데이터도 충분히 적재됨

## Airflow data_interval 동작 원리

Airflow에서 `data_interval_start`는 **처리해야 할 데이터의 시간 범위 시작점**을 의미합니다:

1. **Hourly DAG** (`10 * * * *`):
   - 실행 시각: 01:10
   - data_interval_start: 00:00
   - data_interval_end: 01:00
   - **처리 대상**: 00:00-00:59의 데이터

2. **Daily DAG** (`0 2 * * *`):
   - 실행 시각: 3월 13일 02:00
   - data_interval_start: 3월 12일 00:00
   - data_interval_end: 3월 13일 00:00
   - **처리 대상**: 3월 12일 전체 데이터

## 변경 사항

### 1. 01_ad_hourly_summary.py
```python
# 변경 전
schedule="0 * * * *",  # 매 정각

# 변경 후
schedule="10 * * * *",  # 매 시간 10분
```

### 2. 02_ad_daily_summary.py
```python
# 변경 전
schedule="0 1 * * *",  # 매일 01:00

# 변경 후
schedule="0 2 * * *",  # 매일 02:00
```

## 실행 타임라인 예시 (3월 13일)

| 시간 | DAG | data_interval_start | 처리 데이터 |
|------|-----|-------------------|------------|
| 00:10 | 01_ad_hourly_summary | 3/12 23:00 | 3/12 23:00-23:59 |
| 01:10 | 01_ad_hourly_summary | 3/13 00:00 | 3/13 00:00-00:59 |
| 02:00 | 02_ad_daily_summary | 3/12 00:00 | 3/12 전체 (24시간 + conversion) |
| 02:10 | 01_ad_hourly_summary | 3/13 01:00 | 3/13 01:00-01:59 |
| ... | ... | ... | ... |

## 구현 확인 사항

1. **ETL 클래스 동작 확인**:
   - HourlyETL과 DailyETL이 `data_interval_start`를 올바르게 처리하는지 확인
   - 시간대(timezone) 처리가 올바른지 확인 (Asia/Seoul)

2. **데이터 지연 고려**:
   - Kinesis → S3 적재까지의 지연 시간이 10분 내에 완료되는지 모니터링
   - 필요시 스케줄 조정 (예: 15분, 20분으로 변경)

3. **의존성 확인**:
   - Daily ETL이 Hourly ETL 완료를 기다리지 않아도 되는지 확인
   - 현재 구조상 02:00 실행 시 01:00 hourly는 01:10에 완료되므로 문제없음

## 다음 단계

1. 위 변경사항을 01, 02 파일에 적용
2. Airflow에서 DAG 재로드 및 확인
3. 테스트 실행으로 동작 검증