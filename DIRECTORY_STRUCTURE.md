# CAPA 프로젝트 디렉토리 구조

```
CAPA/
├── infra/                          # 인프라 코드 (IaC - Terraform)
│   ├── terraform/                  # Terraform 설정
│   │   ├── main.tf                 # 메인 설정
│   │   ├── variables.tf            # 커스터마이징 가능한 변수
│   │   ├── outputs.tf              # 출력값
│   │   └── modules/                # 모듈화된 리소스
│   │       ├── kinesis/            # Kinesis Stream + Firehose
│   │       ├── s3/                 # S3 버킷 + 정책
│   │       ├── glue/               # Glue 카탈로그/테이블
│   │       └── iam/                # IAM 역할/정책
│   ├── environments/
│   │   ├── dev/                    # 개발 환경 변수
│   │   │   └── terraform.tfvars
│   │   └── prod/                   # 프로덕션 환경 변수
│   │       └── terraform.tfvars
│   └── scripts/                    # 배포 스크립트
│       └── deploy.sh
│
├── src/                            # 애플리케이션 소스 코드
│   ├── log-generator/              # 광고 로그 생성기
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   ├── airflow/                    # Apache Airflow DAGs
│   │   ├── dags/                   # DAG 정의
│   │   ├── logs/                   # 실행 로그
│   │   ├── plugins/                # 커스텀 플러그인
│   │   └── config/                 # Airflow 설정
│   └── analytics/                  # 분석 쿼리 및 AI
│       ├── athena/                 # Athena SQL 쿼리 모음
│       │   └── queries/
│       └── text-to-sql/            # Vanna, Pydantic AI 등
│
├── tests/                          # 테스트 코드
│   ├── unit/                       # 단위 테스트
│   │   └── log_generator_test.py
│   └── integration/                # 통합 테스트
│       └── kinesis_test.py
│
├── docs/                           # 문서
│   ├── t1/                         # 아키텍처, 도메인 분석
│   ├── t2/                         # 개발 가이드
│   └── t3/                         # 배포 및 운영
│
├── .github/                        # GitHub 설정
│   ├── workflows/                  # CI/CD 파이프라인
│   ├── copilot-instructions.md     # AI 어시스턴트 가이드
│   ├── agents/                     # Spec Kit 에이전트
│   └── prompts/                    # Spec Kit 프롬프트
│
├── .specify/                       # Spec Kit 작업 디렉토리
│   ├── memory/                     # 작업 결과 저장
│   ├── scripts/                    # 실행 스크립트
│   └── templates/                  # 템플릿
│
├── docker-compose.yml              # 로컬 개발 환경 (Airflow, DB 등)
├── .gitignore                      # Git 무시 설정
├── LICENSE                         # 라이선스
├── README.md                       # 프로젝트 개요
└── pyproject.toml                  # Python 프로젝트 설정
```

## 주요 디렉토리 설명

### `/infra` - 인프라 코드
- **Terraform**: AWS 리소스를 IaC로 관리
  - `modules/`: Kinesis, S3, Glue, IAM을 모듈화
  - `environments/`: dev/prod 환경별 변수 분리
- **scripts/**: 인프라 배포 자동화 스크립트

### `/src` - 애플리케이션 코드
- **log-generator**: 광고 로그 시뮬레이터 (impression → click → conversion)
- **airflow**: 배치 데이터 처리 DAG
- **analytics**: Athena 쿼리 + AI 분석 (Vanna, Pydantic AI)

### `/tests` - 테스트
- **unit**: 함수/클래스 단위 테스트
- **integration**: AWS 서비스 통합 테스트

### `/docs` - 문서
- t1: 아키텍처, 도메인 분석
- t2: 개발 가이드, API 문서
- t3: 배포, 운영, 트러블슈팅

### `docker-compose.yml`
로컬 개발 환경 구성:
- PostgreSQL (Airflow 메타스토어)
- Airflow Webserver (UI)
- Airflow Scheduler (DAG 스케줄링)

## 환경별 배포

### 개발 환경
```bash
cd infra/terraform
terraform init
terraform plan -var-file="environments/dev/terraform.tfvars"
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### 프로덕션 환경
```bash
cd infra/terraform
terraform apply -var-file="environments/prod/terraform.tfvars"
```

## 로컬 개발 (Docker)
```bash
docker-compose up -d
# Airflow UI: http://localhost:8081
```
