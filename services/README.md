# Services 디렉토리

## 목적
CAPA 프로젝트의 애플리케이션 소스 코드를 관리합니다.

## 디렉토리 구조

```
services/
├── log-generator/        # 광고 로그 생성기
│   ├── src/              # 로그 생성 코드
│   ├── Dockerfile        # 컨테이너 이미지
│   └── pyproject.toml    # Python 프로젝트 설정
│
├── airflow-dags/         # Apache Airflow DAG 파일
│   ├── dags/             # DAG 정의
│   ├── plugins/          # 커스텀 플러그인
│   └── config/           # Airflow 설정
│
├── slack-bot/            # Slack Bot 애플리케이션
│   ├── src/              # Bot 소스 코드
│   ├── Dockerfile        # 컨테이너 이미지
│   └── requirements.txt  # Python 의존성
│
└── vanna-api/            # Vanna AI (Text-to-SQL)
    ├── src/              # API 서버 코드
    ├── Dockerfile        # 컨테이너 이미지
    └── pyproject.toml    # Python 프로젝트 설정
```

## 각 서비스 설명

### `log-generator/`
**용도**: 광고 로그 시뮬레이터 (테스트 데이터 생성)

**주요 기능**:
- Impression → Click → Conversion 로그 생성
- Kinesis Stream 전송
- 실시간 이벤트 시뮬레이션

**배포 방식**: 독립 실행 또는 EKS CronJob

### `airflow-dags/`
**용도**: 데이터 파이프라인 오케스트레이션

**주요 DAG**:
- 광고 로그 ETL 파이프라인
- Athena 쿼리 스케줄링
- 데이터 검증 및 품질 체크

**배포 방식**: EKS Airflow Pod에 ConfigMap/PVC로 마운트

### `slack-bot/`
**용도**: Slack에서 자연어 질의 → Athena 쿼리 실행

**주요 기능**:
- Slack 이벤트 수신
- Vanna API 호출 (Text-to-SQL)
- Athena 쿼리 실행
- 결과 시각화 및 응답

**배포 방식**: EKS Deployment (Docker 컨테이너)

### `vanna-api/`
**용도**: 자연어를 SQL로 변환하는 AI API

**주요 기능**:
- OpenAI API 연동
- Glue Catalog 스키마 학습
- SQL 생성 및 최적화

**배포 방식**: EKS Deployment (Helm Chart)

## 기존 `src/` 디렉토리와의 관계

**현재 상태**: `src/` 디렉토리 유지 (기존 작업 보존)

**향후 계획**: 작업 명세서 작성 후 점진적 마이그레이션
- `src/airflow/` → `services/airflow-dags/`
- `src/log-generator/` → `services/log-generator/`

## CI/CD 연동

각 서비스는 GitHub Actions를 통해 자동 배포:

```yaml
# .github/workflows/deploy-slack-bot.yaml
- name: Build and Push Docker Image
  run: |
    cd services/slack-bot
    docker build -t $ECR_REPO:$TAG .
    docker push $ECR_REPO:$TAG
```

## 로컬 개발

```bash
# 예시: Slack Bot 로컬 실행
cd services/slack-bot
pip install -r requirements.txt
python src/main.py
```
