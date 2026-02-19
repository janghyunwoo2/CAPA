# CAPA T2 Airflow 파이프라인 가이드

## 📋 개요

**airflow_dag.py**는 데이터 생성 → 처리 → 분석 → 시각화의 전체 파이프라인을 **PythonOperator**로 자동화합니다.

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────┐
│ Airflow DAG: capa_t2_pipeline                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [1] generate_logs                                  │
│      ↓                                              │
│  AdLogGenerator.generate(20K)                       │
│  → data/raw/logs.parquet                            │
│      ↓                                              │
│  [2] process_metrics                                │
│      ↓                                              │
│  AdDataProcessor.process()                          │
│  → data/processed/metrics.parquet                   │
│      ↓                                              │
│  [3] generate_report                                │
│      ↓                                              │
│  AdAnalytics.generate_report()                      │
│  → data/analysis/report_top_ads.csv                 │
│      ↓                                              │
│  [4] visualize_outputs                              │
│      ↓                                              │
│  plot_ctr_over_time()                               │
│  → data/outputs/daily_ctr.png                       │
│  → data/outputs/top5_ads_ctr.png                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 📊 각 단계 설명

### 1️⃣ **generate_logs** (데이터 생성)
- **역할**: 샘플 광고 로그 20,000개 생성
- **출력**: `data/raw/logs.parquet`
- **이벤트 타입**:
  - `impression`: 광고 노출 (80%)
  - `click`: 클릭 이벤트 (15%)
  - `conversion`: 전환 (5%)

### 2️⃣ **process_metrics** (데이터 처리)
- **역할**: 원시 로그를 집계 메트릭으로 변환
- **입력**: `data/raw/logs.parquet`
- **출력**: `data/processed/metrics.parquet`
- **생성 지표**:
  - `impressions`: 노출 수
  - `clicks`: 클릭 수
  - `conversions`: 전환 수
  - `avg_bid_price`: 평균 입찰가
  - `avg_cpc`: 평균 CPC 비용
  - `ctr`: CTR = clicks / impressions
  - `conversion_rate`: 전환율 = conversions / clicks

### 3️⃣ **generate_report** (분석)
- **역할**: 성과 상위 광고 추출
- **입력**: `data/processed/metrics.parquet`
- **출력**: `data/analysis/report_top_ads.csv`
- **조건**: impressions ≥ 10인 광고 중 CTR 상위 20개

### 4️⃣ **visualize_outputs** (시각화)
- **역할**: 시각화 차트 생성
- **입력**: `data/processed/metrics.parquet`
- **출력**:
  - `data/outputs/daily_ctr.png`: 일별 평균 CTR 추이
  - `data/outputs/top5_ads_ctr.png`: 상위 5개 광고 CTR 비교

## 🚀 사용 방법

### 준비 (한 번만)

```bash
# 1. Airflow 설치 및 초기화
pip install apache-airflow==2.5.3

# 2. Airflow 홈 디렉토리 설정
export AIRFLOW_HOME=/path/to/src/data_pipeline_t2

# 3. Airflow DB 초기화
airflow db init

# 4. 기본 사용자 생성
airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com
```

### 실행

#### **방법 1: Airflow 웹 UI (권장)**

```bash
# 1. 스케줄러 시작
airflow scheduler &

# 2. 웹 서버 시작
airflow webui

# 3. 브라우저에서 http://localhost:8080 접속
# 4. DAG 목록에서 "capa_t2_pipeline" 찾기
# 5. "Trigger DAG" 버튼 클릭
```

#### **방법 2: CLI에서 직접 실행**

```bash
# DAG 단일 실행
airflow dags test capa_t2_pipeline 2026-02-10

# 또는 특정 작업만 실행
airflow tasks run capa_t2_pipeline generate_logs 2026-02-10
```

#### **방법 3: Python 스크립트로 직접 실행 (개발/테스트)**

```python
# test_pipeline.py
import sys
from pathlib import Path

pipeline_root = Path(__file__).parent / "src" / "data_pipeline_t2"
sys.path.insert(0, str(pipeline_root))

from generate_sample_logs import AdLogGenerator
from processor import AdDataProcessor
from analyzer import AdAnalytics
from visualize import plot_ctr_over_time

# 순차 실행
AdLogGenerator().generate(20000)
AdDataProcessor().process()
AdAnalytics().generate_report()
plot_ctr_over_time()

print("파이프라인 완료!")
```

```bash
python test_pipeline.py
```

## 📁 출력 파일 구조

```
data/
├── raw/
│   └── logs.parquet              # 원시 로그 (20K 행)
├── processed/
│   └── metrics.parquet           # 집계 메트릭 (광고/날짜별)
├── analysis/
│   └── report_top_ads.csv        # CTR 상위 20개 광고 리포트
└── outputs/
    ├── daily_ctr.png             # 일별 평균 CTR 라인 차트
    └── top5_ads_ctr.png          # 상위 5개 광고 비교 차트
```

## 🔧 DAG 스케줄 설정

### 매일 오전 2시 자동 실행

```python
# airflow_dag.py 내 schedule_interval 수정
schedule_interval="0 2 * * *"  # Cron format (UTC)
```

### 매주 일요일 자동 실행

```python
schedule_interval="0 2 * * 0"  # 매주 일요일 오전 2시
```

### 수동 실행만 (기본값)

```python
schedule_interval=None  # 수동으로 Trigger DAG
```

## 🐛 문제 해결

### 1. 모듈 임포트 에러

```
ModuleNotFoundError: No module named 'generate_sample_logs'
```

**해결**: Airflow Config에서 PYTHONPATH 설정

```bash
export PYTHONPATH="/path/to/src/data_pipeline_t2:$PYTHONPATH"
```

### 2. 데이터 디렉토리 없음

```
FileNotFoundError: [Errno 2] No such file or directory: 'data/raw'
```

**해결**: 디렉토리 수동 생성

```bash
mkdir -p data/{raw,processed,analysis,outputs}
```

### 3. 권한 에러

```
PermissionError: [Errno 13] Permission denied: 'data/outputs/daily_ctr.png'
```

**해결**: 디렉토리 권한 확인

```bash
chmod -R 755 data/
```

## 📈 모니터링

### Airflow 웹 UI에서 확인

- **DAG Graph**: 태스크 간 의존성 시각화
- **Tree View**: 시간별 실행 이력
- **Logs**: 각 태스크의 실행 로그
- **XCom**: 태스크 간 데이터 전달 (필요 시 추가 가능)

## 🚀 AWS 확장 (향후 계획)

현재는 **로컬 파일 시스템** 기반이지만, AWS로 확장할 수 있습니다:

| 로컬 | AWS |
|------|-----|
| `data/raw/logs.parquet` | `s3://bucket/raw/logs.parquet` |
| `AdDataProcessor` | `AWS Glue Job` (PySpark) |
| `AdAnalytics` | `Amazon Athena` (SQL) |
| 시각화 | `Amazon QuickSight` / `Redash` |

**변경 포인트**:
1. PythonOperator → `GlueJobOperator`, `AthenaOperator`
2. 로컬 경로 → S3 URI
3. 디렉토리 생성 → S3 파티셔닝

## 📚 참고 자료

- [Apache Airflow 공식 문서](https://airflow.apache.org/docs/)
- [Airflow Operators](https://airflow.apache.org/docs/apache-airflow/stable/operators.html)
- [CAPA 프로젝트 README](../README.md)

---

**버전**: 0.1.0  
**마지막 수정**: 2026-02-10  
**작성자**: CAPA T2 Pipeline Team
