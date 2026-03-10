# Airflow 작동 안 함 - 문제 진단 및 해결 (2026-03-09)

## 문제 상황

Airflow를 실행해도 아무 DAG도 로드되지 않음

## 원인 분석

### 1. **DAG 폴더 누락** (주요 원인)
```
❌ .airflow_t2/dags/  → 폴더 없음 (존재하지 않음)
✓ services/data_pipeline_t2/dags/  → DAG 파일 존재 (4개)
```

| DAG 파일 | 위치 | 상태 |
|---------|------|------|
| 01_ad_hourly_summary.py | services/data_pipeline_t2/dags/ | ✓ 존재 |
| 02_ad_daily_summary.py | services/data_pipeline_t2/dags/ | ✓ 존재 |
| 03_ad_hourly_summary_test.py | services/data_pipeline_t2/dags/ | ✓ 존재 |
| 04_ad_daily_summary_test.py | services/data_pipeline_t2/dags/ | ✓ 존재 |

### 2. Airflow 홈 디렉토리 현황
```
.airflow_t2/
  ├── logs/           ✓ 존재
  ├── airflow.cfg     ✓ 존재
  ├── airflow.db      ✓ 존재
  └── dags/           ❌ 없음! ← 이것이 문제
```

## 해결 방법

### AS-IS (현재 상태)
- Airflow가 `.airflow_t2/dags/` 폴더를 찾음
- 해당 폴더가 존재하지 않으므로 DAG 로드 실패
- Airflow 웹 UI에 DAG가 표시되지 않음

### TO-BE (수정 후)
- `.airflow_t2/dags/` 폴더 생성
- `services/data_pipeline_t2/dags/` 의 모든 DAG 파일을 복사
- Airflow 재시작 시 DAG가 정상 로드됨

## 수정 작업

### 실행 완료 ✓

**1. `.airflow_t2/dags/` 폴더 생성** ✓
```powershell
mkdir -Force .airflow_t2\dags
```

**2. DAG 파일 복사** ✓
```powershell
Copy-Item -Path "services\data_pipeline_t2\dags\*.py" -Destination ".airflow_t2\dags\" -Force
```

**3. 결과 확인** ✓
```
.airflow_t2/dags/
├── 01_ad_hourly_summary.py
├── 02_ad_daily_summary.py
├── 03_ad_hourly_summary_test.py
├── 04_ad_daily_summary_test.py
└── __init__.py
```

### 다음 단계

Airflow를 재시작하면 DAG가 정상 로드됩니다:

```powershell
# PowerShell에서 실행
cd c:\Users\Dell5371\Desktop\projects\CAPA
$env:AIRFLOW_HOME = "$PWD\.airflow_t2"

# 스케줄러 시작 (터미널 1)
uv run --project services/data_pipeline_t2 python -m airflow scheduler

# API 서버 시작 (터미널 2)
uv run --project services/data_pipeline_t2 python -m airflow api-server -p 8081
```

웹 UI: **http://localhost:8081** (admin / admin)

---

## 추가 문제: 03_ad_hourly_summary_test.py DAG 실행 오류 (2026-03-09)

### 🔴 발견된 문제들

#### 1. **Jinja 템플릿이 env_vars에서 렌더링되지 않음**
```python
# ❌ 문제 코드
env_vars={
    "QUERY": (
        "CREATE TABLE {{ params.database }}.ad_combined_log_tmp ..."
    )
}
```
**원인**: KubernetesPodOperator의 `env_vars`는 문자열로 직접 전달되므로, 
Jinja 템플릿(`{{ }}`)이 Python 문자열 리터럴로 그대로 처리됨

**영향**: Athena 쿼리에 실제 값(예: `capa_ad_logs`) 대신 `{{ params.database }}` 문자열이 들어감 → 쿼리 실패

#### 2. **Docker 이미지 버전 불일치**
```python
# ❌ 문제 코드
image="apache/airflow:2.9.3-python3.14.2"
```
**실제 실행 중인 이미지**: `apache/airflow:3.1.7` (docker-compose.yaml)

**해결**: `3.1.7`로 통일

#### 3. **PythonOperator의 query에서 params 사용 오류**
```python
# ❌ 문제 코드
"query": (
    "CREATE TABLE {{ params.database }}.ad_combined_log_tmp ..."
),
```
**원인**: PythonOperator의 `op_kwargs`는 기본적으로 Jinja 템플릿을 렌더링하지 않음
(`template_fields` 미설정)

### ✅ 해결 방법

#### 수정 내용
1. Jinja 템플릿을 **Python 함수 내에서 동적 생성**으로 변경
2. Docker 이미지를 **`3.1.7`로 업그레이드**
3. `context` 객체를 활용하여 **data_interval_end 등의 값 동적 추출**
4. SQL 쿼리를 **문자열 보간(f-string) 또는 .format()으로 생성**

#### 수정 전 (AS-IS)
- Jinja 템플릿을 op_kwargs에 하드코딩
- Airflow 2.9.3 이미지 사용
- context에서 값을 받지 않음

#### 수정 후 (TO-BE)
- SQL 쿼리를 함수 내에서 **data_interval_end와 함께 동적 생성**
- Airflow 3.1.7 이미지 사용 (docker-compose와 일치)
- context 활용으로 **정확한 타임스탐프** 반영
