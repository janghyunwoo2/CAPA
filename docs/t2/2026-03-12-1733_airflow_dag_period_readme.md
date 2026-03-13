# Airflow DAG 기간 수동 실행 가이드 작성

## 요청사항
- 05_ad_hourly_summary_period.py와 06_ad_daily_summary_period.py 파일에 대한 사용 방법 README.md 작성

## AS-IS
- `services/data_pipeline_t2/dags/README.md` 파일에 간단한 예정 내용만 존재
- 05, 06 DAG 파일에 대한 사용 방법 문서 없음
- 개발자가 DAG 실행 방법을 코드를 읽어서 파악해야 함

## TO-BE
- 전체 DAG 목록과 설명을 포함한 종합 가이드로 확장
- 05, 06 DAG의 상세 사용 방법 추가:
  - 파라미터 설명 (테이블 형식)
  - 실행 방법 (CLI, Web UI)
  - 실제 사용 예시
  - 주의사항 및 트러블슈팅

## 구현 내용

### 1. DAG 목록 정리
- 정기 실행 DAG (01, 02)
- 테스트 DAG (03, 04)
- 기간 수동 실행 DAG (05, 06) ⭐
- 예정된 DAG (report_generation, vanna_training)

### 2. 05_ad_hourly_summary_period.py 가이드
- **파라미터**:
  - `start_date`: 시작일 (기본: 어제)
  - `end_date`: 종료일 (기본: 오늘)
  - `hours`: 시간 범위 (기본: "0-23")
- **실행 예시**: 특정 기간, 특정 시간대, 단일 시간 처리
- **용도**: 과거 데이터 재처리, 특정 시간대 재생성

### 3. 06_ad_daily_summary_period.py 가이드
- **파라미터**:
  - `start_date`: 시작일 (기본: 7일 전)
  - `end_date`: 종료일 (기본: 어제)
  - `skip_missing_hours`: 누락 시간 허용 여부 (기본: true)
- **실행 예시**: 월간 재집계, 엄격한 검증 모드
- **용도**: 일별 데이터 재생성, 대량 백필

### 4. 운영 가이드
- **데이터 의존성**: 
  - Hourly는 원천 데이터 필요
  - Daily는 Hourly 데이터 필요
- **권장 워크플로우**: Hourly 먼저, Daily 나중에
- **성능 고려사항**: 한 달 이하 권장
- **모니터링 방법**: 상태 확인, 로그 위치

### 5. 트러블슈팅
- 일반적인 오류와 해결 방법
- 로그 확인 위치
- 재시도 정책

## 파일 위치
- 수정된 파일: `services/data_pipeline_t2/dags/README.md`

## 효과
- 개발자와 운영자가 DAG 사용 방법을 쉽게 파악
- 백필 작업 시 참고할 수 있는 구체적인 예시 제공
- 트러블슈팅 시간 단축