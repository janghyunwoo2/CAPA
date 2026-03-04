# Airflow 실행 가이드 (data_pipeline_t2) - uv 환경

이 폴더(`services/data_pipeline_t2/`)에서 **uv**를 사용하여 Airflow DAG를 독립적으로 실행할 수 있습니다.

## 전제 조건

- Python 3.8+
- **uv 설치** (미설치 시: `pip install uv`)
- 프로젝트 루트: c:\Users\Dell5371\Desktop\projects\CAPA

---

## 1. uv 환경 설정 (권장)

이 방식이 가장 빠르고 간단합니다.

PowerShell에서:

```powershell
# 프로젝트 루트로 이동
cd c:\Users\Dell5371\Desktop\projects\CAPA

# data_pipeline_t2 디렉터리에서 uv sync 실행
cd services/data_pipeline_t2
uv sync

# 또는 프로젝트 루트에서
uv sync --project services/data_pipeline_t2
```

이 명령은 `pyproject.toml`을 읽어 자동으로 `.venv` 디렉터리를 생성하고 의존성을 설치합니다.

---

## 2. Airflow 초기화 (uv run 사용)

```powershell
# 프로젝트 루트로 이동 (또는 services/data_pipeline_t2)
cd c:\Users\Dell5371\Desktop\projects\CAPA

# (옵션) AIRFLOW_HOME 설정
$env:AIRFLOW_HOME = "$PWD\.airflow_t2"

# DB 초기화
uv run --project services/data_pipeline_t2 python -m airflow db init

# 관리자 사용자 생성
uv run --project services/data_pipeline_t2 python -m airflow users create --username admin --firstname Admin --lastname User --role Admin --email admin@example.com
```

---

## 3. DAG 배치

Airflow가 DAG를 찾을 수 있도록 구성합니다.

**옵션 A: 파일 복사 (권장)**

```powershell
# 프로젝트 루트에서
mkdir -Force .airflow_t2\dags
Copy-Item services\data_pipeline_t2\airflow_dag.py .airflow_t2\dags\
```

**옵션 B: 심볼릭 링크 (관리자 권한 필요)**

```powershell
New-Item -ItemType SymbolicLink -Path .airflow_t2\dags\airflow_dag.py -Target (Resolve-Path services\data_pipeline_t2\airflow_dag.py)
```

---

## 4. 웹서버 & 스케줄러 실행 (uv run)

**터미널 1: API 서버 (Airflow 3.x)**

```powershell
cd c:\Users\Dell5371\Desktop\projects\CAPA
uv run --project services/data_pipeline_t2 python -m airflow api-server -p 8081
```

**터미널 2: 스케줄러**

```powershell
cd c:\Users\Dell5371\Desktop\projects\CAPA
uv run --project services/data_pipeline_t2 python -m airflow scheduler
```

웹 UI 접속: **http://localhost:8081** (admin 계정)

---

## 5. DAG 실행 (uv run)

### DAG 목록 확인

```powershell
uv run --project services/data_pipeline_t2 python -m airflow dags list
```

### DAG 수동 실행 (즉시 트리거)

```powershell
uv run --project services/data_pipeline_t2 python -m airflow dags trigger capa_t2_pipeline
```

### 웹 UI에서 실행

1. http://localhost:8081 접속
2. `capa_t2_pipeline` DAG 찾기
3. DAG 우측 상단 **트리거** 클릭

### 개별 태스크 테스트 (로컬 디버깅)

```powershell
# Step 1: 샘플 로그 생성
uv run --project services/data_pipeline_t2 python -m airflow tasks test capa_t2_pipeline generate_logs 2026-02-10

# Step 2: 데이터 처리
uv run --project services/data_pipeline_t2 python -m airflow tasks test capa_t2_pipeline process_metrics 2026-02-10

# Step 3: 분석 리포트
uv run --project services/data_pipeline_t2 python -m airflow tasks test capa_t2_pipeline generate_report 2026-02-10

# Step 4: 시각화
uv run --project services/data_pipeline_t2 python -m airflow tasks test capa_t2_pipeline visualize_outputs 2026-02-10
```

### 로그 확인

```powershell
# 웹 UI에서: DAG → 실행 → 태스크 클릭 → 로그 탭

# 또는 CLI에서
uv run --project services/data_pipeline_t2 python -m airflow tasks logs capa_t2_pipeline generate_logs 2026-02-10
```

---

## 6. 단계별 스크립트 수동 실행 (Airflow 없이)

```powershell
cd c:\Users\Dell5371\Desktop\projects\CAPA/services/data_pipeline_t2

# Step 1: 샘플 로그 생성
uv run python generate_sample_logs.py

# Step 2: 데이터 처리
uv run python processor.py

# Step 3: 분석 리포트
uv run python analyzer.py

# Step 4: 시각화
uv run python visualize.py
```

---

## 7. DAG 스케줄 설정 (선택, KST, Airflow 2.4+)

기본 설정은 수동 실행(`schedule=None`)입니다.  
자동 실행하려면 `airflow_dag.py`의 DAG 정의를 수정하세요 (KST 기준):

```python
import pendulum
from airflow import DAG

with DAG(
    dag_id="capa_t2_pipeline",
    schedule="0 2 * * *",  # 매일 02:00 KST
    start_date=pendulum.datetime(2026, 2, 10, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
):
    ...
```

시간별 실행 예(KST):
```python
with DAG(
    dag_id="capa_t2_pipeline_hourly",
    schedule="10 * * * *",  # 매 시 10분(KST), 10분 버퍼
    start_date=pendulum.datetime(2026, 2, 10, tz=pendulum.timezone("Asia/Seoul")),
    catchup=False,
):
    ...
```

저장 후 웹 UI를 새로고침하면 자동으로 업데이트됩니다.

---

## 8. 데이터 출력 위치

`services/data_pipeline_t2/` 디렉터리 내:

```
data/
├── raw/
│   └── logs.parquet              # Step 1 출력: 샘플 로그
├── processed/
│   └── metrics.parquet           # Step 2 출력: 집계 메트릭
├── analysis/
│   └── report_top_ads.csv        # Step 3 출력: 분석 리포트
└── outputs/
    ├── daily_ctr.png             # Step 4 출력: 일별 CTR 그래프
    └── top5_ads_ctr.png          #         상위 광고 CTR 그래프
```

---

## 9. 문제 해결

### DAG가 웹 UI에 보이지 않음

```powershell
# 1. DAG 파일 위치 확인
ls .airflow_t2\dags\

# 2. DAG 문법 검사 (Python 에러 확인)
uv run --project services/data_pipeline_t2 python -m airflow dags list

# 3. API 서버 재시작 (Ctrl+C 후 재실행)
uv run --project services/data_pipeline_t2 python -m airflow api-server -p 8081
```

### 태스크 실패

```powershell
# 웹 UI에서 빨간 태스크 클릭 → 로그 탭 전체 내용 확인

# 또는 CLI
uv run --project services/data_pipeline_t2 python -m airflow tasks logs capa_t2_pipeline <task_name> 2026-02-10 --full
```

### 포트 8081 충돌

```powershell
# 다른 포트로 실행 (예: 8082)
uv run --project services/data_pipeline_t2 python -m airflow api-server -p 8082
```

### Python 모듈 미설치 에러

```powershell
# 의존성 재설치
cd services/data_pipeline_t2
uv sync
```

---

## 10. 유용한 명령어 요약

```powershell
# 의존성 설치
uv sync --project services/data_pipeline_t2

# Airflow 초기화
uv run --project services/data_pipeline_t2 python -m airflow db init

# DAG 목록
uv run --project services/data_pipeline_t2 python -m airflow dags list

# DAG 트리거
uv run --project services/data_pipeline_t2 python -m airflow dags trigger capa_t2_pipeline

# 웹서버
uv run --project services/data_pipeline_t2 python -m airflow api-server -p 8081

# 스케줄러
uv run --project services/data_pipeline_t2 python -m airflow scheduler

# 태스크 테스트
uv run --project services/data_pipeline_t2 python -m airflow tasks test capa_t2_pipeline <task_id> 2026-02-10

# 수동 스크립트 실행
cd services/data_pipeline_t2 && uv run python generate_sample_logs.py
```

---

## 11. 다음 단계

1. ✅ 로컬에서 DAG 실행 및 결과 검증
2. 데이터 경로를 S3으로 변경 (boto3/aws-data-wrangler)
3. BashOperator를 AWS 작업으로 교체 (Glue, Athena, ECS)
4. IAM 역할 및 Airflow 연결 설정
5. 운영 환경(AWS)으로 배포

---

## 참고 파일

- DAG: [airflow_dag.py](airflow_dag.py)
- 의존성: [pyproject.toml](pyproject.toml)
- 스크립트: [generate_sample_logs.py](generate_sample_logs.py), [processor.py](processor.py), [analyzer.py](analyzer.py), [visualize.py](visualize.py)
