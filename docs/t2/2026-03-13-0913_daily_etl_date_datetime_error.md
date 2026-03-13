# Daily ETL date/datetime 타입 오류 분석

## 오류 정보
- **발생 시간**: 2026-03-13 09:11:52 (KST)
- **DAG**: 06_ad_daily_summary_period
- **오류 메시지**: `TypeError: replace() takes at most 3 keyword arguments (4 given)`
- **발생 위치**: `/opt/airflow/etl_summary_t2/daily_etl.py`, line 37

## 문제 분석

### AS-IS (현재 상황)
1. **DAG에서 date 객체 생성**
   ```python
   # 06_ad_daily_summary_period.py의 _run_daily_etl_period 함수
   start_date = datetime.strptime(params.get('start_date'), '%Y-%m-%d').date()
   end_date = datetime.strptime(params.get('end_date'), '%Y-%m-%d').date()
   
   # date 객체를 DailyETL에 전달
   etl = DailyETL(target_date=current_date)  # current_date는 date 객체
   ```

2. **DailyETL에서 datetime 메서드 호출**
   ```python
   # daily_etl.py의 __init__ 메서드 (line 37)
   if target_date:
       self.target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
   ```

3. **오류 발생 원인**
   - Python의 `date` 객체는 `replace()` 메서드를 가지고 있지만, `hour`, `minute`, `second`, `microsecond` 인수를 받지 않음
   - `date` 객체는 `year`, `month`, `day`만 가능
   - `datetime` 객체만 시간 관련 인수를 받을 수 있음

### TO-BE (해결 방안)
1. **DAG 수정**: date 객체 대신 datetime 객체 전달
   ```python
   # .date() 제거하여 datetime 객체 유지
   start_date = datetime.strptime(params.get('start_date'), '%Y-%m-%d')
   end_date = datetime.strptime(params.get('end_date'), '%Y-%m-%d')
   ```

2. **또는 DailyETL 수정**: date와 datetime 둘 다 처리 가능하도록
   ```python
   if target_date:
       if isinstance(target_date, date) and not isinstance(target_date, datetime):
           # date 객체를 datetime으로 변환
           self.target_date = datetime.combine(target_date, datetime.min.time())
       else:
           # datetime 객체 처리
           self.target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
   ```

## 추천 해결 방법

### 방법 1: DAG 수정 (추천)
- 06_ad_daily_summary_period.py의 `_run_daily_etl_period` 함수에서 `.date()` 제거
- 더 간단하고 직관적인 해결책
- DailyETL이 datetime을 기대하므로 DAG에서 맞춰주는 것이 적절

### 방법 2: DailyETL 수정
- daily_etl.py의 `__init__` 메서드에서 타입 체크 추가
- 더 견고한 해결책 (다양한 입력 처리 가능)
- 하지만 코드가 복잡해짐

## 영향 범위
- **06_ad_daily_summary_period.py**: Period DAG
- **02_ad_daily_summary.py**: 일반 Daily DAG (확인 필요)
- 다른 DailyETL을 사용하는 코드들

## 테스트 방법
```python
# 수정 후 로컬에서 테스트
from datetime import datetime, date
from etl_summary_t2.daily_etl import DailyETL

# date 객체로 테스트
test_date = date(2026, 3, 12)
etl = DailyETL(target_date=test_date)  # 오류 발생 여부 확인

# datetime 객체로 테스트
test_datetime = datetime(2026, 3, 12)
etl = DailyETL(target_date=test_datetime)  # 정상 작동 확인
```

## 해결 내용 (2026-03-13 09:15)

### 선택한 해결 방법: 방법 1 (DAG 수정)
06_ad_daily_summary_period.py 파일에서 `.date()` 호출을 제거하여 datetime 객체를 유지하도록 수정

### 수정된 코드
1. **_run_daily_etl_period 함수**:
   - `datetime.strptime(...).date()` → `datetime.strptime(...)`
   - 날짜 비교 시 `.date()` 메서드 추가하여 출력 일관성 유지

2. **ETL_RUNNER_SCRIPT 내부**:
   - 동일하게 `.date()` 제거
   - 로그 출력 시에만 `.date()` 사용하여 날짜만 표시

### 결과
- DailyETL에 datetime 객체가 전달되어 `replace(hour=0, minute=0, second=0, microsecond=0)` 정상 작동
- 기존 로직과 호환성 유지
- 02_ad_daily_summary.py는 이미 datetime을 사용하므로 수정 불필요