# CAPA T2 데이터 파이프라인 (로컬 개발 & Airflow 통합)

이 폴더(`src/data_pipeline_t2/`)는 로컬 환경에서 CAPA 데이터 파이프라인을 개발하고, Apache Airflow로 스케줄링/조율하기 위한 모든 리소스를 포함합니다.

## 폴더 구조

```
src/data_pipeline_t2/
├── __init__.py                  # 패키지 초기화
├── generate_sample_logs.py      # Step 1: 샘플 광고 로그 생성
├── processor.py                 # Step 2: 로그 집계 & 메트릭 계산
├── analyzer.py                  # Step 3: 분석 리포트 생성
├── visualize.py                 # Step 4: 시각화 (PNG)
├── airflow_dag.py               # Airflow DAG (4단계 자동화)
├── requirements_airflow.txt     # pip 의존성 (airflow 포함)
├── RUN_AIRFLOW.md               # Airflow 실행 가이드 (이 파일)
├── README.md                    # 이 파일
├── data/
│   ├── raw/                     # 생성된 샘플 로그 (Parquet)
│   ├── processed/               # 처리된 메트릭 (Parquet)
│   ├── analysis/                # 분석 리포트 (CSV)
│   └── outputs/                 # 시각화 결과 (PNG)
```

## 빠른 시작

### 1. 수동 실행 (uv + 직접 스크립트)

```powershell
# 프로젝트 루트로 이동
cd c:\Users\Dell5371\Desktop\projects\CAPA

# uv 의존성 설치 (처음 한 번만)
uv sync --project src/data_pipeline_t2

# 각 단계 순차 실행
cd src/data_pipeline_t2
uv run python generate_sample_logs.py
uv run python processor.py
uv run python analyzer.py
uv run python visualize.py
```

### 2. Airflow로 자동화 (권장)

```powershell
# 프로젝트 루트
cd c:\Users\Dell5371\Desktop\projects\CAPA

# uv 환경 설정
uv sync --project src/data_pipeline_t2

# Airflow 초기화
$env:AIRFLOW_HOME = "$PWD\.airflow_t2"
uv run --project src/data_pipeline_t2 airflow db init
uv run --project src/data_pipeline_t2 airflow users create --username admin --firstname Admin --lastname User --role Admin --email admin@example.com

# DAG 배치
mkdir -Force .airflow_t2\dags
Copy-Item src\data_pipeline_t2\airflow_dag.py .airflow_t2\dags\

# 웹서버 & 스케줄러 실행 (각각 다른 터미널)
uv run --project src/data_pipeline_t2 airflow webserver -p 8080
uv run --project src/data_pipeline_t2 airflow scheduler

# 웹 UI에서 capa_t2_pipeline DAG 찾아 실행
# http://localhost:8080
```

**더 자세한 가이드**: [RUN_AIRFLOW.md](RUN_AIRFLOW.md)

## 주요 기능

### 데이터 생성
- 20,000개의 광고 이벤트 시뮬레이션
- 이벤트 타입: impression, click, conversion
- UUID 기반 고유 ID 생성

### 데이터 처리
- 광고(ad_id)와 날짜(date)별 집계
- 클릭률(CTR), 전환율, 평균 CPC 계산

### 분석
- CTR 상위 20개 광고 추출
- CSV 리포트 생성

### 시각화
- 일별 평균 CTR 추이 (라인 그래프)
- 상위 5개 광고의 CTR 변화 (멀티라인 그래프)

## W

## AWS 전환 시 체크리스트

- [ ] S3 버킷 생성 (raw, processed, analysis, outputs)
- [ ] Kinesis Data Stream & Firehose 설정
- [ ] Glue Catalog에 테이블 등록
- [ ] airflow_dag.py의 BashOperator를 AWS 작업(Glue, Athena, ECS)으로 변경
- [ ] Airflow 연결(Connections) 설정 (AWS 자격증명)
- [ ] IAM 역할 및 권한 설정
- [ ] CloudWatch 모니터링 구성

## 의존성

**uv 기반 관리** (권장):

```toml
# pyproject.toml
[project]
dependencies = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pyarrow>=12.0.0",
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
    "apache-airflow==2.5.3",
]
```

**설치**:
```powershell
uv sync
```

**또는 pip 방식** (기존 환경용):

```
pandas
numpy
pyarrow
matplotlib
seaborn
apache-airflow==2.5.3
```

**설치**:
```powershell
pip install -r requirements_airflow.txt
```

## 참고

- **로컬 테스트**: 빠른 프로토타이핑 및 검증
- **Airflow 통합**: 작업 스케줄링, 의존성 관리, 모니터링
- **AWS 전환**: 스크립트는 유지하되, 파일 경로와 작업 실행자만 변경

## 다음 단계

1. `RUN_AIRFLOW.md`를 읽고 Airflow 환경 설정
2. DAG 실행 및 데이터 결과 검증
3. AWS 권한 및 리소스 준비
4. `airflow_dag.py`를 AWS용으로 리팩토링

## 연락처

문제나 개선 사항은 프로젝트 repo의 Issues에서 논의하세요.
