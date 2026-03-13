# Airflow DAG에서 hourly_etl 모듈 import 오류 분석 및 해결

## 오류 정보
- **발생 시간**: 2026-03-12 15:44:40
- **파일**: `/opt/airflow/dags/01_ad_hourly_summary.py`
- **오류 메시지**: `ModuleNotFoundError: No module named 'hourly_etl'`

## AS-IS (현재 상태)
### 현재 코드 구조
```python
# 01_ad_hourly_summary.py (line 22-27)
ETL_PATH = str(Path(__file__).parent.parent / "etl_summary_t2")
if ETL_PATH not in sys.path:
    sys.path.insert(0, ETL_PATH)

from hourly_etl import HourlyETL
```

### 현재 디렉토리 구조
```
services/data_pipeline_t2/
├── dags/                    # DAG 파일들
│   └── 01_ad_hourly_summary.py
├── etl_summary_t2/          # ETL 모듈
│   ├── __init__.py
│   ├── hourly_etl.py
│   └── ...
└── ...
```

### 문제 분석
1. **경로 계산 오류**: `Path(__file__).parent.parent`는 Airflow 컨테이너 내부에서 예상과 다른 경로를 가리킴
   - 로컬: `services/data_pipeline_t2/dags/../.. = services/`
   - Airflow 컨테이너: `/opt/airflow/dags/../.. = /opt/`
   
2. **모듈 누락**: Airflow 컨테이너 내부에 `etl_summary_t2` 모듈이 없음
   - DAG 파일만 `/opt/airflow/dags/`에 복사됨
   - ETL 모듈은 컨테이너에 마운트되지 않음

## TO-BE (해결 방법)

### 방법 1: etl_summary_t2를 Docker 볼륨으로 마운트
**docker-compose.yaml 수정**

현재 설정:
```yaml
x-airflow-common:
  &airflow-common
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
    - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
    - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
    - ${AIRFLOW_PROJ_DIR:-.}/data:/opt/airflow/data
```

수정 필요:
```yaml
x-airflow-common:
  &airflow-common
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
    - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
    - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
    - ${AIRFLOW_PROJ_DIR:-.}/data:/opt/airflow/data
    - ${AIRFLOW_PROJ_DIR:-.}/etl_summary_t2:/opt/airflow/etl_summary_t2  # 추가
```

**DAG 파일 수정**
```python
# 01_ad_hourly_summary.py
import sys
from pathlib import Path

# Airflow 환경에서 절대 경로 사용
ETL_PATH = "/opt/airflow/etl_summary_t2"
if ETL_PATH not in sys.path:
    sys.path.insert(0, ETL_PATH)

from hourly_etl import HourlyETL
```

### 방법 2: etl_summary_t2를 패키지로 설치
**Dockerfile 또는 requirements 수정**
```dockerfile
# Dockerfile
COPY ./etl_summary_t2 /opt/airflow/etl_summary_t2
RUN pip install -e /opt/airflow/etl_summary_t2
```

**DAG 파일 수정**
```python
# 패키지로 설치했다면 직접 import 가능
from etl_summary_t2.hourly_etl import HourlyETL
```

### 방법 3: DAG 파일에 ETL 코드 포함 (임시 방안)
**script 폴더 활용**
```python
# dags/script/ 폴더에 필요한 모듈 복사
# 01_ad_hourly_summary.py
from script.hourly_etl import HourlyETL
```

## 권장 해결책
**방법 1 (Docker 볼륨 마운트)** 을 권장합니다.
- 구현이 간단하고 즉시 적용 가능
- 개발 중 코드 변경사항이 실시간 반영
- 추가 패키지 설치 불필요

### 구현 단계
1. **docker-compose.yaml 수정**
   ```yaml
   volumes:
     - ./dags:/opt/airflow/dags
     - ./etl_summary_t2:/opt/airflow/etl_summary_t2
   ```

2. **DAG 파일들 수정** (01_ad_hourly_summary.py, 02_ad_daily_summary.py 등)
   ```python
   ETL_PATH = "/opt/airflow/etl_summary_t2"
   ```

3. **Airflow 재시작**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## 검증 방법
```bash
# Airflow 컨테이너 접속
docker exec -it airflow_webserver bash

# 모듈 경로 확인
ls -la /opt/airflow/etl_summary_t2/

# Python import 테스트
python -c "import sys; sys.path.append('/opt/airflow/etl_summary_t2'); from hourly_etl import HourlyETL; print('Success')"
```

## 추가 고려사항
- **환경 변수 활용**: ETL_PATH를 환경 변수로 관리하여 유연성 향상
- **로깅 추가**: sys.path와 import 성공 여부를 로그로 남기기
- **CI/CD 파이프라인**: 프로덕션 환경에서는 Docker 이미지에 모듈 포함 고려

## 즉시 적용 가능한 명령어
```bash
# 1. docker-compose.yaml 수정 후 Airflow 재시작
cd services/data_pipeline_t2
docker-compose down
docker-compose up -d

# 2. DAG 리로드 확인
docker exec -it data_pipeline_t2-airflow-webserver-1 airflow dags list

# 3. import 오류 해결 확인
docker exec -it data_pipeline_t2-airflow-webserver-1 bash -c "cd /opt/airflow/dags && python 01_ad_hourly_summary.py"
```

## 대안: 임시 해결책 (권장하지 않음)
etl_summary_t2 모듈을 dags/script 폴더에 복사하는 방법:
```powershell
# Windows PowerShell
Copy-Item -Path ".\etl_summary_t2\*.py" -Destination ".\dags\script\" -Force

# DAG 파일 수정
# from hourly_etl import HourlyETL
from script.hourly_etl import HourlyETL
```
단, 이 방법은 코드 중복과 유지보수 문제가 있으므로 권장하지 않습니다.