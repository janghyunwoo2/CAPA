# 애플리케이션 소스 코드 (src/)

CAPA 프로젝트의 핵심 애플리케이션 코드입니다.

## 구조

```
src/
├── log-generator/       # 광고 로그 생성기
├── airflow/             # 배치 처리 DAG
└── analytics/           # 분석 쿼리 & AI
    ├── athena/          # SQL 쿼리
    └── text-to-sql/     # Vanna, Pydantic AI
```

## 각 컴포넌트

### log-generator/
광고 로그 시뮬레이터
- **역할**: impression, click, conversion 이벤트 생성
- **출력**: AWS Kinesis, 로컬 JSON (디버깅용)
- **주요 클래스**: `AdLogGenerator`

```bash
cd src/log-generator
python main.py  # 로그 생성 시작
```

### airflow/
배치 데이터 처리
- **dags/**: DAG 정의 (Python)
- **logs/**: 실행 로그
- **plugins/**: 커스텀 오퍼레이터, 훅
- **config/**: Airflow 설정

### analytics/
#### athena/
S3 데이터 분석용 SQL 쿼리
```
queries/
├── daily_stats.sql        # 일일 통계
├── ctr_analysis.sql       # CTR 분석
└── funnel_analysis.sql    # 전환 분석
```

#### text-to-sql/
AI 기반 자연어 → SQL 변환
- Vanna: SQL 생성 AI
- Pydantic AI: 데이터 검증

## 로컬 개발

### Docker Compose로 환경 구성
```bash
docker-compose up -d
```

서비스:
- **Airflow Webserver**: http://localhost:8080
- **PostgreSQL**: localhost:5432

### 로그 생성기 실행
```bash
cd src/log-generator
pip install -r requirements.txt
python main.py
```

환경 변수:
```bash
export KINESIS_STREAM_NAME=capa-ad-logs-dev
export AWS_PROFILE=default
```

## 의존성

각 컴포넌트의 `requirements.txt` 또는 `pyproject.toml`을 참고하세요.

## 배포

### log-generator
- Docker 이미지로 배포 (ECR)
- ECS Fargate 또는 EC2에서 실행

### airflow
- MWAA (Managed Workflows for Airflow) 권장
- 또는 EC2에서 자체 호스팅

### analytics
- Athena: SQL 쿼리 직접 실행
- Redash: 대시보드 시각화

## 참고

- [Airflow 문서](https://airflow.apache.org/docs/)
- [Vanna AI](https://www.vanna.ai/)
- [Pydantic AI](https://ai.pydantic.dev/)
