# Airflow DAGs for Ad Data Pipeline

본 디렉토리에는 광고 데이터 파이프라인을 위한 Airflow DAG 파일들이 위치합니다.

## DAG 목록

### 정기 실행 DAG
- `01_ad_hourly_summary.py`: 시간별 광고 데이터 집계 (매시간 10분)
- `02_ad_daily_summary.py`: 일별 광고 데이터 집계 (매일 02:00 KST)

### 테스트 DAG (수동 실행)
- `03_ad_hourly_summary_test.py`: 시간별 집계 테스트
- `04_ad_daily_summary_test.py`: 일별 집계 테스트

### 기간 수동 실행 DAG ⭐
- `05_ad_hourly_summary_period.py`: 지정 기간의 시간별 데이터 집계
- `06_ad_daily_summary_period.py`: 지정 기간의 일별 데이터 집계

### 예정된 DAG (Phase 3)
- `report_generation_dag.py`: 정기 리포트 생성
- `vanna_training_dag.py`: Vanna DDL Training 자동화

---

## 기간 수동 실행 DAG 사용 가이드

### 05_ad_hourly_summary_period.py

**목적**: 특정 기간의 시간별 광고 데이터(impressions + clicks)를 일괄 처리

#### 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `start_date` | string | 어제 날짜 | 시작일 (YYYY-MM-DD 형식) |
| `end_date` | string | 오늘 날짜 | 종료일 (YYYY-MM-DD 형식) |
| `hours` | string | "0-23" | 처리할 시간 범위 (예: "0-23", "9-18", "12") |

#### 실행 방법

##### Airflow CLI
```bash
# 기본값으로 실행 (어제~오늘, 전체 시간)
airflow dags trigger 05_ad_hourly_summary_period

# 특정 날짜 범위 지정
airflow dags trigger 05_ad_hourly_summary_period \
  --conf '{"start_date": "2026-03-01", "end_date": "2026-03-05", "hours": "0-23"}'

# 특정 시간대만 처리
airflow dags trigger 05_ad_hourly_summary_period \
  --conf '{"start_date": "2026-03-10", "end_date": "2026-03-10", "hours": "9-18"}'
```

##### Airflow Web UI
1. DAGs 목록에서 `05_ad_hourly_summary_period` 찾기
2. "Trigger DAG w/ Config" 버튼 클릭
3. Configuration JSON 입력:
```json
{
  "start_date": "2026-03-01",
  "end_date": "2026-03-05",
  "hours": "0-23"
}
```

#### 사용 예시

1. **지난 일주일 전체 데이터 재처리**
```bash
airflow dags trigger 05_ad_hourly_summary_period \
  --conf '{"start_date": "2026-03-05", "end_date": "2026-03-11"}'
```

2. **특정 날짜의 업무 시간대만 재처리**
```bash
airflow dags trigger 05_ad_hourly_summary_period \
  --conf '{"start_date": "2026-03-10", "end_date": "2026-03-10", "hours": "9-18"}'
```

3. **특정 시간만 재처리**
```bash
airflow dags trigger 05_ad_hourly_summary_period \
  --conf '{"start_date": "2026-03-10", "end_date": "2026-03-10", "hours": "14"}'
```

---

### 06_ad_daily_summary_period.py

**목적**: 특정 기간의 일별 광고 데이터를 일괄 집계 (hourly 24개 + conversions 조인)

#### 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `start_date` | string | 7일 전 | 시작일 (YYYY-MM-DD 형식) |
| `end_date` | string | 어제 | 종료일 (YYYY-MM-DD 형식, 어제까지만 가능) |
| `skip_missing_hours` | boolean | true | 일부 시간대 데이터가 없어도 진행할지 여부 |

#### 실행 방법

##### Airflow CLI
```bash
# 기본값으로 실행 (지난 7일)
airflow dags trigger 06_ad_daily_summary_period

# 특정 기간 지정
airflow dags trigger 06_ad_daily_summary_period \
  --conf '{"start_date": "2026-03-01", "end_date": "2026-03-10"}'

# 누락된 시간대가 있으면 실패하도록 설정
airflow dags trigger 06_ad_daily_summary_period \
  --conf '{"start_date": "2026-03-01", "end_date": "2026-03-10", "skip_missing_hours": false}'
```

##### Airflow Web UI
1. DAGs 목록에서 `06_ad_daily_summary_period` 찾기
2. "Trigger DAG w/ Config" 버튼 클릭
3. Configuration JSON 입력:
```json
{
  "start_date": "2026-03-01",
  "end_date": "2026-03-10",
  "skip_missing_hours": true
}
```

#### 사용 예시

1. **지난 한 달 데이터 재집계**
```bash
airflow dags trigger 06_ad_daily_summary_period \
  --conf '{"start_date": "2026-02-01", "end_date": "2026-02-28"}'
```

2. **특정 기간 엄격한 검증으로 재집계**
```bash
# 24시간 데이터가 모두 있어야만 성공
airflow dags trigger 06_ad_daily_summary_period \
  --conf '{"start_date": "2026-03-05", "end_date": "2026-03-10", "skip_missing_hours": false}'
```

---

## 주의사항

### 데이터 의존성
1. **Hourly Period DAG (05)**: 
   - S3의 원천 데이터(impressions, clicks)가 있어야 실행 가능
   - 미래 시간은 자동으로 건너뜀

2. **Daily Period DAG (06)**:
   - 해당 날짜의 hourly summary 데이터가 있어야 함
   - 일반적으로 05번 DAG를 먼저 실행 후 06번 실행
   - 오늘 날짜는 처리하지 않음 (완료된 날짜만 집계)

### 권장 워크플로우
```bash
# 1단계: 시간별 데이터 생성
airflow dags trigger 05_ad_hourly_summary_period \
  --conf '{"start_date": "2026-03-01", "end_date": "2026-03-05"}'

# 2단계: 시간별 데이터 완료 확인 후 일별 집계
airflow dags trigger 06_ad_daily_summary_period \
  --conf '{"start_date": "2026-03-01", "end_date": "2026-03-05"}'
```

### 성능 고려사항
- 대량 기간 처리 시 충분한 리소스 확보
- 한 번에 너무 긴 기간 처리 지양 (권장: 1개월 이하)
- 실행 시간: 
  - Hourly: 1일당 약 2-3분 (24시간 처리)
  - Daily: 1일당 약 1-2분

### 모니터링
```bash
# 실행 상태 확인
airflow dags state 05_ad_hourly_summary_period <execution_date>

# 로그 확인
airflow tasks logs 05_ad_hourly_summary_period create_hourly_summary_period <execution_date>
```

### 재시도 및 복구
- 기본 재시도: 2회 (5분 간격)
- 실패 시 해당 날짜/시간만 다시 실행 가능
- `skip_missing_hours=true` 설정으로 부분 실패 허용

---

## 트러블슈팅

### 일반적인 오류

1. **"No data found for hour X"**
   - 원인: 해당 시간의 원천 데이터 없음
   - 해결: 원천 데이터 확인 또는 해당 시간 제외

2. **"Failed to create parquet file"**
   - 원인: S3 권한 문제 또는 디스크 공간 부족
   - 해결: AWS credentials 및 S3 권한 확인

3. **"MSCK REPAIR TABLE failed"**
   - 원인: Athena 메타데이터 동기화 실패
   - 해결: Glue 카탈로그 상태 확인, 수동으로 MSCK REPAIR 실행

### 로그 위치
- Airflow UI: Graph View → Task → Logs
- CLI: `airflow tasks logs <dag_id> <task_id> <execution_date>`
- Kubernetes: Pod 로그 확인 (KPO 사용 시)

---

## 관련 문서
- [ETL Integration Guide](./README_ETL_INTEGRATION.md): ETL 패키지 통합 가이드
- [ETL Summary Process](../../docs/t2/etl_summary_process.md): ETL 프로세스 상세 설명
- [Airflow 배포 가이드](../../docs/t2/etl_summary_airflow_dag.md): Airflow 배포 상세 가이드
