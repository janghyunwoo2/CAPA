# 로컬 데이터 파이프라인 실행 가이드

## 로컬 실행 가이드 및 AWS 반영 포인트

- 로컬 테스트용 스크립트: `src/data_pipeline` 아래에 샘플 로그 생성, 처리, 분석, 시각화 스크립트를 추가해 로컬에서 전체 플로우를 검증할 수 있습니다.
    - 샘플 생성기: [src/data_pipeline/generate_sample_logs.py](src/data_pipeline/generate_sample_logs.py)
    - 처리기(집계): [src/data_pipeline/processor.py](src/data_pipeline/processor.py)
    - 분석 리포트: [src/data_pipeline/analyzer.py](src/data_pipeline/analyzer.py)
    - 시각화: [src/data_pipeline/visualize.py](src/data_pipeline/visualize.py)

- AWS로 반영해야 할 부분(로컬 대체 지점):
    - 데이터 수집: 로컬 `generate_sample_logs.py` -> AWS에서는 `Kinesis` 또는 컨테이너 기반 Producer로 대체
    - 스트리밍 → 저장: Kinesis/Firehose를 통해 S3에 Parquet로 적재 (현재 로컬은 `data/raw/*.parquet`)
    - 카탈로그: Glue Catalog에 테이블을 등록해 Athena에서 쿼리 가능하도록 구성
    - 배치/스케줄링: Airflow DAG에서 `processor` 로직(또는 aws-data-wrangler 이용)을 실행해 S3에서 집계
    - 분석/시각화: 현재 로컬 `analyzer`/`visualize`는 pandas+matplotlib 기반; 운영은 Athena(SQL)+Redash 또는 QuickSight로 이전 권장

위 파일들은 로컬에서 바로 실행해 결과물(`data/processed/metrics.parquet`, `data/analysis/*.csv`, `data/outputs/*.png`)을 확인할 수 있습니다. AWS 반영 시에는 주석의 TODO들을 참고해 S3 URI, Glue, Kinesis 설정을 적용하세요.

## 1. 시스템 개요

CAPA 데이터 파이프라인의 로컬 버전은 4개 단계로 구성되어 있습니다:
- **로그 생성**: 샘플 광고 이벤트(impression, click, conversion) 생성
- **데이터 처리**: 원시 로그 집계 및 주요 메트릭 계산
- **분석**: 집계 메트릭에서 리포트 생성
- **시각화**: CTR 및 주요 지표를 그래프로 출력

---

## 2. 작동 과정 (Flow Diagram)

```
[Step 1: generate_sample_logs.py]
    ↓
    생성: data/raw/logs.parquet (20,000개 이벤트)
    - event_type: impression, click, conversion
    - bid_price, cpc_cost, conversion_type 포함
    ↓
    
[Step 2: processor.py]
    ↓
    입력: data/raw/logs.parquet
    처리: 광고(ad_id)와 날짜(date)별 집계
    - impressions: 노출 수
    - clicks: 클릭 수
    - conversions: 전환 수
    - avg_bid_price: 평균 입찍가
    - avg_cpc: 평균 CPC
    - ctr: 클릭률 (clicks/impressions)
    - conversion_rate: 전환율 (conversions/clicks)
    ↓
    생성: data/processed/metrics.parquet
    ↓
    
[Step 3: analyzer.py]
    ↓
    입력: data/processed/metrics.parquet
    분석: 노출이 10회 이상인 광고 중 CTR 상위 20개 추출
    ↓
    생성: data/analysis/report_top_ads.csv
    ↓
    
[Step 4: visualize.py]
    ↓
    입력: data/processed/metrics.parquet
    시각화:
    - daily_ctr.png: 일별 평균 CTR 추이
    - top5_ads_ctr.png: 상위 5개 광고의 CTR 변화
    ↓
    생성: data/outputs/*.png
```

---

## 3. 파일 구조 및 데이터 흐름

### 프로젝트 구조
```
CAPA/
├── requirements.txt              (의존 패키지)
├── data/
│   ├── raw/
│   │   └── logs.parquet         (로그 생성기의 출력물)
│   ├── processed/
│   │   └── metrics.parquet      (처리기의 출력물)
│   ├── analysis/
│   │   └── report_top_ads.csv   (분석기의 출력물)
│   └── outputs/
│       ├── daily_ctr.png        (시각화: 일별 CTR)
│       └── top5_ads_ctr.png     (시각화: 상위 광고)
└── src/data_pipeline/
    ├── __init__.py
    ├── generate_sample_logs.py  (Step 1)
    ├── processor.py             (Step 2)
    ├── analyzer.py              (Step 3)
    └── visualize.py             (Step 4)
```

### 각 스크립트의 역할

| 파일 | 입력 | 처리 | 출력 |
|------|------|------|------|
| `generate_sample_logs.py` | - | UUID 기반 20,000개 이벤트 생성 | Parquet |
| `processor.py` | Parquet | 광고별/날짜별 집계, 지표 계산 | Parquet |
| `analyzer.py` | Parquet | CTR 기준 상위 20개 광고 선별 | CSV |
| `visualize.py` | Parquet | Matplotlib를 이용한 플롯 생성 | PNG |

---

## 4. 작동 방법 (Step by Step)

### 4.1 사전 준비

두 가지 방식 중 하나를 선택하여 환경을 설정할 수 있습니다.

#### 방법 1: venv + pip (기본)

Windows PowerShell에서 실행:

```powershell
# (1) 프로젝트 루트 디렉터리로 이동
cd c:\Users\Dell5371\Desktop\projects\CAPA

# (2) Python 가상환경 생성
python -m venv .venv

# (3) 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# (4) 의존 패키지 설치
pip install -r requirements.txt
```

#### 방법 2: uv (권장 - 빠르고 간단함)

`uv`는 Rust 기반으로 작성된 초고속 Python 패키지 관리자입니다. venv 방식보다 훨씬 빠릅니다.

**uv 설치 (처음 한 번만)**:
```powershell
pip install uv
```

# 가상환경 내 파이썬 버전 설치
uv python install 3.14.2
# 가상환경 내 파이썬 버전 고정
uv python pin 3.14.2

**프로젝트 환경 설정**:
```powershell
# (1) 프로젝트 루트 디렉터리로 이동
cd c:\Users\Dell5371\Desktop\projects\CAPA

# (2) uv로 의존성 설치 (venv 자동 생성)
uv init
```

**가상환경 활성화 (필요 시)**:
```powershell
# uv는 자동으로 .venv에 설치하므로 명시적 활성화 불필요
# 하지만 활성화하려면:
.\.venv\Scripts\Activate.ps1
```

**설치 패키지**:
- `pandas`: 데이터프레임 처리
- `numpy`: 수치 계산
- `pyarrow`: Parquet 파일 읽기/쓰기
- `matplotlib`: 그래프 생성
- `seaborn`: 시각화 스타일

# 가상환경 내 패키지 설치
uv add pandas numpy pyarrow matplotlib seaborn

**uv로 스크립트 실행 (권장)**:
```powershell
# 가상환경에서 자동으로 실행됨 (활성화 불필요)
uv run python src/data_pipeline_t2/generate_sample_logs.py
uv run python src/data_pipeline_t2/processor.py
uv run python src/data_pipeline_t2/analyzer.py
uv run python src/data_pipeline_t2/visualize.py
```

---

**uv 방식의 장점**:
- ⚡ **10배 빠름**: venv + pip 보다 훨씬 빠른 패키지 설치
- 🔄 **버전 관리 단순화**: `uv.lock` 파일로 재현 가능한 환경 보장
- 📦 **의존성 해석 우수**: 복잡한 버전 충돌 자동 해결
- ✨ **개발 경험 개선**: `uv run`으로 활성화 없이 바로 실행 가능


---

**방법 선택 가이드**:
- venv: 기존 Python 환경과 호환성이 최고, 모든 시스템에서 작동
- uv: 개발 속도 and 의존성 관리 우수, Python 3.7+ 필요

### 4.2 단계별 실행

#### Step 1: 샘플 로그 생성 (5-10초)
```powershell
python src/data_pipeline/generate_sample_logs.py
```

**기대 출력**:
```
샘플 로그 생성 완료 -> data/raw/logs.parquet
```

**생성되는 데이터**:
- 파일: `data/raw/logs.parquet`
- 크기: ~500 KB (20,000 이벤트)
- 컬럼: event_id, timestamp, event_type, ad_id, campaign_id, user_id, bid_price, cpc_cost, conversion_type, date

---

#### Step 2: 데이터 처리 (5초)
```powershell
python src/data_pipeline/processor.py
```

**기대 출력**:
```
처리 완료 -> data/processed/metrics.parquet
```

**생성되는 집계 지표**:
- 파일: `data/processed/metrics.parquet`
- 예시 데이터 (행별로 ad_id, date 단위):
  ```
  ad_id    date        impressions  clicks  conversions  avg_bid_price  avg_cpc    ctr        conversion_rate
  ad_1     2026-02-03  45          5       0            2.156          1.234      0.1111     0.0
  ad_1     2026-02-04  52          8       1            1.987          1.456      0.1538     0.125
  ...
  ```

---

#### Step 3: 분석 리포트 생성 (2초)
```powershell
python src/data_pipeline/analyzer.py
```

**기대 출력**:
```
분석 리포트 생성 완료 -> data/analysis/report_top_ads.csv
```

**생성되는 리포트**:
- 파일: `data/analysis/report_top_ads.csv`
- 내용: 노출이 10회 이상인 광고 중 CTR이 높은 상위 20개 광고
- 열: ad_id, date, impressions, clicks, conversions, ctr, conversion_rate 등

---

#### Step 4: 시각화 (3초)
```powershell
python src/data_pipeline/visualize.py
```

**기대 출력**:
```
시각화 결과 저장: data/outputs/daily_ctr.png, data/outputs/top5_ads_ctr.png
```

**생성되는 이미지**:
- `data/outputs/daily_ctr.png`: 일별 평균 CTR 추이 라인 그래프
- `data/outputs/top5_ads_ctr.png`: 상위 5개 광고의 CTR 변화 멀티라인 그래프

---

### 4.3 한 번에 모두 실행하기

#### venv 방식:
```powershell
# 가상환경 활성화 후 순차 실행
.\.venv\Scripts\Activate.ps1
python src/data_pipeline/generate_sample_logs.py; `
python src/data_pipeline/processor.py; `
python src/data_pipeline/analyzer.py; `
python src/data_pipeline/visualize.py
```

#### uv 방식 (권장):
```powershell
# 자동으로 가상환경에서 실행 (활성화 불필요)
uv run python src/data_pipeline/generate_sample_logs.py
uv run python src/data_pipeline/processor.py
uv run python src/data_pipeline/analyzer.py
uv run python src/data_pipeline/visualize.py
```

또는 한 줄로 실행:
```powershell
uv run python src/data_pipeline/generate_sample_logs.py; uv run python src/data_pipeline/processor.py; uv run python src/data_pipeline/analyzer.py; uv run python src/data_pipeline/visualize.py
```

---

#### 배치 파일 (venv 방식):

**run_pipeline.bat** 생성 후:
```batch
@echo off
cd /d %~dp0
call .venv\Scripts\activate.bat
python src/data_pipeline/generate_sample_logs.py
python src/data_pipeline/processor.py
python src/data_pipeline/analyzer.py
python src/data_pipeline/visualize.py
pause
```

#### PowerShell 스크립트 (uv 방식):

**run_pipeline.ps1** 생성 후:
```powershell
# uv로 파이프라인 실행
uv run python src/data_pipeline/generate_sample_logs.py
uv run python src/data_pipeline/processor.py
uv run python src/data_pipeline/analyzer.py
uv run python src/data_pipeline/visualize.py
Write-Host "파이프라인 완료!" -ForegroundColor Green
```

실행:
```powershell
.\run_pipeline.ps1
```

---

## 5. 결과 확인 및 검증

### 파일 확인
```powershell
# 생성된 모든 파일 확인
ls -Recurse data/

# Parquet 파일 내용 확인 (Python)
python -c "import pandas as pd; print(pd.read_parquet('data/processed/metrics.parquet').head(10))"

# CSV 파일 확인
cat data/analysis/report_top_ads.csv | head -5
```

### 이미지 확인
생성된 PNG 파일은 Windows 탐색기에서 `data/outputs/` 폴더를 열어 시각 확인 가능합니다.

---

## 6. 주요 성능 지표 설명

| 항목 | 의미 | 계산식 |
|------|------|--------|
| **Impressions** | 광고 노출 수 | impression 이벤트의 개수 |
| **Clicks** | 광고 클릭 수 | click 이벤트의 개수 |
| **CTR** | 클릭률 | clicks / impressions |
| **Conversions** | 전환 수 | conversion 이벤트의 개수 |
| **Conversion Rate** | 전환율 | conversions / clicks |
| **Avg Bid Price** | 평균 입찰가 | impression의 bid_price 평균 |
| **Avg CPC** | 평균 클릭당 비용 | click의 cpc_cost 평균 |

---

## 7. AWS 반영 포인트

### 각 단계에서 AWS로 전환할 부분

| 로컬 | AWS |
|------|-----|
| `generate_sample_logs.py` (파일 생성) | Kinesis Producer (실시간 스트림) 또는 ECS 컨테이너 |
| `data/raw/*.parquet` (로컬 파일) | S3 (Kinesis Firehose → S3 자동 저장) |
| 파일 읽기/쓰기 | boto3 또는 aws-data-wrangler 라이브러리 |
| `processor.py` (단순 집계) | Airflow DAG에서 Athena SQL 또는 Glue Job 실행 |
| `analyzer.py` (리포트) | Redash 또는 QuickSight에서 저장된 SQL 쿼리 |
| `visualize.py` (Matplotlib) | Redash 또는 QuickSight 대시보드 |
| 메타데이터 관리 | AWS Glue Catalog (테이블, 파티션) |

### AWS 반영 체크리스트

- [ ] S3 버킷 생성 (dev, prod 환경별)
- [ ] Kinesis Data Stream 설정 (Producer 추가)
- [ ] Kinesis Firehose 설정 (Parquet 변환, S3 저장)
- [ ] Glue Crawler 설정 (S3의 Parquet 자동 메타데이터 등록)
- [ ] Airflow DAG 작성 (processor 로직을 SQL로 변환)
- [ ] Redash 설정 (Athena 데이터소스 연결)
- [ ] IAM 정책 설정 (필요 권한)

각 파일의 주석에 **TODO (AWS)** 세션을 참고하세요.

---

## 8. 문제 해결

### venv 방식 트러블슈팅

#### 에러: ModuleNotFoundError
```
ModuleNotFoundError: No module named 'pandas'
```
→ 가상환경이 활성화되지 않았거나 의존성 미설치
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### 에러: 가상환경 활성화 안 됨
```
.venv\Scripts\Activate.ps1 : 이 시스템에서 스크립트를 실행할 수 없으므로... 
```
→ PowerShell 실행 정책 변경
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### uv 방식 트러블슈팅

#### 에러: uv 명령어를 찾을 수 없음
```
uv : 용어 'uv'는 인식되지 않습니다...
```
→ uv 미설치 또는 PATH 업데이트 필요
```powershell
pip install uv
# 또는 scoop을 이용한 설치 (Windows)
scoop install uv
```

#### 에러: uv sync 실패
```
Failed to create virtual environment
```
→ Python 버전 확인 (Python 3.7+ 필요)
```powershell
python --version
# Python 3.7 미만이면 업그레이드 필요
```

---

### 공통 에러

#### 에러: FileNotFoundError: 'data/raw/logs.parquet'
```
FileNotFoundError: No such file or directory: 'data/raw/logs.parquet'
```
→ Step 1 (generate_sample_logs.py)을 먼저 실행하세요

#### PNG 파일이 생성되지 않음
→ `data/outputs/` 디렉터리가 생성되지 않았을 수 있음
```powershell
mkdir -p data/outputs
# venv 방식
python src/data_pipeline/visualize.py
# uv 방식
uv run python src/data_pipeline/visualize.py
```

---

## 9. 커스터마이징

### 샘플 데이터 크기 변경
[generate_sample_logs.py](generate_sample_logs.py) 마지막 줄 수정:
```python
gen.generate(100000)  # 기본 20,000 → 100,000개로 변경
```

### 상위 리포트 개수 변경
[analyzer.py](analyzer.py) 마지막 줄 수정:
```python
a.generate_report(top_n=50)  # 기본 20 → 50개로 변경
```

### 최소 노출 임계값 변경
[analyzer.py](analyzer.py) 내 threshold 값:
```python
threshold = 10  # 노출이 10회 이상인 광고만 분석
```

---

## 10. 추가 팁

### uv + pyproject.toml 사용 (권장)

현재는 `requirements.txt`를 사용하지만, 더 모던한 방식은 `pyproject.toml`입니다:

**pyproject.toml** 생성:
```toml
[project]
name = "capa-pipeline"
version = "0.1.0"
description = "Cloud-native AI Pipeline for Ad-logs - Local Data Pipeline"
requires-python = ">=3.8"
dependencies = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pyarrow>=12.0.0",
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "black>=23.0.0",
]
```

**uv.lock 생성 및 설치**:
```powershell
uv sync
```

### 환경별 설정 (개발/운영)

**uv.lock 파일 커밋**:
```bash
git add uv.lock
git commit -m "Lock Python dependencies"
```

이렇게 하면 팀원이 동일한 환경을 사용할 수 있습니다:
```powershell
uv sync  # 정확한 같은 버전 설치
```

### 성능 튜닝

대용량 데이터 처리 시:
```powershell
# 병렬 처리 활용 (processor.py 내에서)
# groupby 대신 polars 사용 검토 (pandas보다 10배 빠름)
```

### IDE 통합

VS Code에서:
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.formatting.provider": "black"
}
```

### IDE 통합

VS Code에서:
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.formatting.provider": "black"
}
```

PyCharm에서:
1. `Preferences` → `Python Interpreter`
2. `Add` → `Existing Environment`
3. `.venv\Scripts\python.exe` 선택

---

## 참고 사항

- 모든 스크립트는 **이전 스크립트의 출력을 입력**으로 사용합니다. 순서 준수 필수
- Parquet 파일은 바이너리 형식으로 직접 열 수 없으므로 pandas로 확인하세요
- 시각화 이미지는 벡터 형식(SVG)이 아닌 래스터 형식(PNG)으로 저장됩니다
- 로컬 실행 시 데이터는 누적되지 않으며, 매번 새로 생성됩니다 (비파괴)
- **uv 권장**: venv+pip 방식보다 속도와 의존성 관리 면에서 우수합니다