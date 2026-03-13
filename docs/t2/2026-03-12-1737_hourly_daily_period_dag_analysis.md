# HoulyETL Period DAG(05) 성공 vs DailyETL Period DAG(06) 실패 분석

## 개요
- **날짜**: 2026-03-12 17:37
- **상황**: 05_ad_hourly_summary_period.py는 성공했지만, 06_ad_daily_summary_period.py는 실패함
- **분석 목적**: 두 DAG의 차이점을 분석하여 06 DAG 실패 원인 파악

## 05_ad_hourly_summary_period.py (성공) 분석

### 주요 특징
- **ETL 클래스**: `HourlyETL` 사용
- **데이터 처리**: impressions + clicks → ad_combined_log 테이블 생성
- **파라미터**:
  - start_date: 시작일
  - end_date: 종료일
  - hours: 시간 범위 (기본값: 0-23)
- **실행 시간 제한**: 30분 (execution_timeout)
- **재시도 설정**: 2회, 5분 간격

### 성공 요인
1. 시간별 데이터 처리로 작은 단위 처리
2. 단순한 impressions + clicks 조인 작업
3. 적절한 실행 시간 제한 (30분)

## 06_ad_daily_summary_period.py (실패) 분석

### 주요 특징
- **ETL 클래스**: `DailyETL` 사용
- **데이터 처리**: hourly_summary 24개 집계 + conversion 원천 로그 조인
- **파라미터**:
  - start_date: 시작일
  - end_date: 종료일
  - skip_missing_hours: 일부 시간대 누락 허용 (기본값: True)
- **실행 시간 제한**: 60분 (execution_timeout)
- **재시도 설정**: 2회, 10분 간격
- **추가 태스크**: trigger_reports_batch (리포트 생성 트리거)

### 주요 차이점
1. **복잡도 증가**:
   - 24개의 hourly 데이터 집계 필요
   - conversion 데이터 추가 조인
   - 더 많은 데이터 처리량

2. **추가 태스크**:
   - trigger_reports 태스크가 DAG 마지막에 추가됨
   - 외부 서비스 호출 (report-generator)

3. **실행 환경 차이**:
   - KPO 사용 시 다른 이미지 사용 (python:3.14-slim vs apache/airflow:3.1.7)

## 예상 실패 원인

### 1. DailyETL 자체 문제
```python
# skip_missing_hours 속성 확인
if hasattr(etl, 'skip_missing_hours'):
    etl.skip_missing_hours = SKIP_MISSING
```
- DailyETL 클래스가 skip_missing_hours 속성을 지원하지 않을 가능성

### 2. 데이터 누락 문제
- 24개 시간 중 일부가 누락된 경우
- conversion 데이터가 없는 경우
- skip_missing_hours=True여도 최소 데이터 요구사항 미충족

### 3. 파티션 관련 문제
- ad_combined_log_summary 테이블의 파티션 구조 문제
- MSCK REPAIR TABLE 실행 시 오류

### 4. trigger_reports 네트워크 문제
```python
url = os.getenv("REPORT_URL", "http://report-generator.report.svc.cluster.local:8000/generate")
```
- report-generator 서비스 접근 불가
- 네트워크 타임아웃

## 권장 조치사항

### 즉시 확인 사항
1. Airflow 로그에서 정확한 에러 메시지 확인
2. DailyETL 클래스의 skip_missing_hours 속성 지원 여부 확인
3. 해당 날짜의 hourly 데이터 24개 존재 여부 확인
4. conversion 데이터 존재 여부 확인

### 디버깅 단계
1. **데이터 확인**:
   ```sql
   -- hourly 데이터 확인
   SELECT COUNT(*) FROM ad_combined_log 
   WHERE year=2026 AND month=03 AND day=12;
   
   -- conversion 데이터 확인
   SELECT COUNT(*) FROM conversions
   WHERE year=2026 AND month=03 AND day=12;
   ```

2. **로컬 테스트**:
   ```powershell
   # DailyETL 직접 실행
   cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2
   $env:PYTHONPATH=".\etl_summary_t2"
   python -m etl_summary_t2.run_etl daily --target-date 2026-03-11
   ```

3. **trigger_reports 격리**:
   - 임시로 trigger_reports 태스크 제거하고 테스트
   - 또는 trigger_reports의 trigger_rule을 'all_done'으로 변경

### 코드 수정 제안
1. **에러 핸들링 강화**:
   ```python
   # _run_daily_etl_period 함수 내부
   try:
       etl = DailyETL(target_date=current_date)
       # 더 상세한 로깅 추가
       logger.info(f"DailyETL initialized for {current_date}")
       
       if hasattr(etl, 'skip_missing_hours'):
           etl.skip_missing_hours = skip_missing
           logger.info(f"skip_missing_hours set to {skip_missing}")
       else:
           logger.warning("DailyETL does not support skip_missing_hours attribute")
   ```

2. **데이터 검증 추가**:
   - ETL 실행 전 필수 데이터 존재 여부 확인
   - 최소 데이터 요구사항 체크

## 결론
06 DAG의 실패는 다음 중 하나 이상의 원인일 가능성이 높습니다:
1. DailyETL 클래스의 skip_missing_hours 미지원
2. 필수 데이터(hourly 24개 또는 conversion) 누락
3. trigger_reports 태스크의 외부 서비스 접근 실패

정확한 원인 파악을 위해 Airflow 로그의 상세 에러 메시지 확인이 필요합니다.