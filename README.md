<p align="center">
  <h1 align="center">🚀 온라인 광고 로그 처리 파이프라인 및 분석 플랫폼</h1>
  <p align="center">
    <strong>Cloud-native AI Pipeline for Ad-logs (CAPA)</strong><br/>
    온라인 광고 로그 처리 파이프라인 및 분석 플랫폼
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/AWS-Cloud--native-FF9900?logo=amazonaws&logoColor=white" alt="AWS"/>
  <img src="https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform&logoColor=white" alt="Terraform"/>
  <img src="https://img.shields.io/badge/EKS-Kubernetes-326CE5?logo=kubernetes&logoColor=white" alt="EKS"/>
  <img src="https://img.shields.io/badge/Claude_3.5-Haiku-191A1B?logo=anthropic&logoColor=white" alt="Claude"/>
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License"/>
</p>

---

> _"SQL을 모르는 마케터도 Slack에서 자연어로 질문하면 수십 초 안에 데이터를 받아볼 수 있는 환경을 구축하여, 수 시간~수일 걸리던 데이터 추출 업무를 **약 99% 단축**한 클라우드 네이티브 AI 분석 플랫폼"_

---

## 📋 목차

- [프로젝트 배경](#-프로젝트-배경)
- [핵심 기능](#-핵심-기능)
- [시스템 아키텍처](#-시스템-아키텍처)
- [기술 스택 및 채택 근거](#-기술-스택-및-채택-근거)
- [프로젝트 구조](#-프로젝트-구조)
- [시작하기](#-시작하기)
- [성과 지표](#-성과-지표)
- [팀 구성](#-팀-구성)
- [문서](#-문서)
- [라이선스](#-라이선스)

---

## 🎯 프로젝트 배경

### 문제 정의 — 데이터 격차(Data Gap)

광고 대행사 및 마케팅 현장에서는 매일 수많은 데이터 분석 요청이 발생합니다. 그러나 데이터를 직접 추출할 수 있는 인력은 SQL을 아는 소수의 개발자와 데이터 엔지니어뿐입니다.

```
🕙 오전 10:03  마케터: "어제 캠페인별 ROAS 좀 뽑아주세요"
🕑 오후 03:15  데이터팀: "지금 다른 건 처리 중이라... 내일 드릴게요"
```

이 **5시간 이상의 대기 시간**은 단순한 불편이 아닌 **비즈니스 손실**로 직결됩니다.

| 문제 | 영향 |
|------|------|
| SQL 기술 장벽 | 기업 데이터의 68%가 비개발 직군에게 닿지 못하고 방치 |
| 분석팀 병목 | 모든 요청이 소수에게 집중 → 만성적 지연 |
| 실시간성 부족 | 광고 예산이 비효율적으로 소진되는 시간 발생 |

### 왜 광고 도메인인가?

광고 로그는 **초당 수만 건**씩 발생하며, CTR·CVR·ROAS 같은 핵심 KPI가 시시각각 변합니다. 데이터 확인 지연은 곧 **예산 낭비**로 이어지기 때문에, 실시간 조회와 이상 탐지가 가장 절실한 도메인입니다.

---

## ✨ 핵심 기능

CAPA는 마케터가 겪는 **4가지 고통**을 각각 해결합니다.

### 💬 Ask — 자연어 대화형 질의 (Text-to-SQL)

Slack에서 자연어로 질문하면 AI가 SQL을 생성·실행하여 결과를 즉시 반환합니다.

```
사용자: "어제 가장 ROAS가 높았던 캠페인 알려줘"
CAPA:   📊 결과 테이블 + 생성된 SQL + 시각화 차트 (수십 초 이내)
```

- **11단계 Text-to-SQL 파이프라인** (의도 분류 → 키워드 추출 → RAG 검색 → SQL 생성 → 4중 검증)
- **멀티턴 대화** 지원 (최대 5턴, DynamoDB 기반 세션 관리)
- **Self-Correction 루프**: 검증 실패 시 최대 3회 자동 수정
- **SQL 실행 정확도 80.6%** 달성 (4라운드 PDCA 개선)

### 📈 Report — 자동화 리포트

Airflow 기반 배치 시스템이 매일 아침 광고 성과를 자동 집계하여 Slack으로 전송합니다.

- 일간/주간/월간 리포트 자동 생성 및 전송
- Redash 대시보드 딥링크 제공 (원클릭 심층 분석)
- **담당자 개입 0회** — 완전 자동화

### 🚨 Alert — 실시간 이상 탐지

Prophet + Isolation Forest 앙상블 모델이 5분 주기로 광고 트래픽을 감시합니다.

- 시계열 트렌드 학습 기반 정상 범위 예측
- 이상 징후 감지 시 즉시 Slack 알림 전송
- 예산 낭비를 사전에 차단하는 디지털 안전판

### 📊 Dashboard — 셀프서비스 BI

Redash 기반 대시보드에서 SQL 지식 없이도 마케터가 직접 데이터를 탐색합니다.

- Jinja2 파라미터를 통한 날짜 필터 → Athena 파티션 자동 매핑
- 풀스캔 방지로 클라우드 비용 최소화
- 데이터 접근 주도권을 현업에 위임

---

## 🏗 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ☁️  AWS Cloud (ap-northeast-2)                   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │ Log Generator │──▶│   Kinesis     │──▶│   S3          │              │
│  │  (Python)     │    │  Streams ×3   │    │  (Parquet)    │              │
│  └──────────────┘    │  + Firehose   │    │  Partitioned  │              │
│                       └──────────────┘    └──────┬───────┘               │
│                                                   │                      │
│                       ┌──────────────┐    ┌──────▼───────┐               │
│                       │ Glue Catalog │◀──▶│   Athena      │              │
│                       │ (Schema Mgmt)│    │  (Serverless) │              │
│                       └──────────────┘    └──────┬───────┘               │
│                                                   │                      │
│  ┌────────────────────────────────────────────────┼────────────────────┐ │
│  │                    🐳 Amazon EKS Cluster       │                    │ │
│  │                                                │                    │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────▼─────────────────┐ │ │
│  │  │ Airflow  │  │ Redash   │  │         Vanna AI Service         │ │ │
│  │  │ (DAGs)   │  │ (BI)     │  │  ┌─────────┐  ┌──────────────┐  │ │ │
│  │  └────┬─────┘  └──────────┘  │  │ChromaDB │  │ Claude 3.5   │  │ │ │
│  │       │                       │  │ (RAG)   │  │   Haiku      │  │ │ │
│  │       │                       │  └─────────┘  └──────────────┘  │ │ │
│  │       │                       └─────────────────┬───────────────┘ │ │
│  │       │         ┌──────────┐                    │                 │ │
│  │       ├────────▶│ Report   │                    │                 │ │
│  │       │         │Generator │                    │                 │ │
│  │       │         └────┬─────┘                    │                 │ │
│  │       │              │         ┌────────────────▼───────────┐     │ │
│  │       │              └────────▶│       Slack Bot            │     │ │
│  │       │                        │   (Socket Mode + FastAPI)  │     │ │
│  │       │                        └────────────────────────────┘     │ │
│  │  ┌────▼──────────────┐                                            │ │
│  │  │    Karpenter      │  ◀── Spot 인스턴스 자동 스케일링           │ │
│  │  └───────────────────┘                                            │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────┐                                                       │
│  │ Terraform    │  ◀── 전체 인프라 코드화 (IaC, 25분 내 완전 배포)     │
│  └──────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────┘
         │                              ▲
         ▼                              │
   ┌───────────┐                  ┌───────────┐
   │  Slack    │◀────────────────▶│ DynamoDB  │
   │ Workspace │  자연어 질의/응답   │ (Sessions)│
   └───────────┘                  └───────────┘
```

**3단 레이어 설계**:

| 레이어 | 역할 | 주요 서비스 |
|--------|------|-------------|
| **Streaming** | 실시간 로그 수집 및 적재 | Kinesis Data Streams/Firehose → S3 (Parquet) |
| **Storage & Query** | 서버리스 데이터 레이크 및 분석 | S3 + Glue Catalog + Amazon Athena |
| **Application** | AI 엔진, 자동화, 사용자 인터페이스 | EKS (Vanna AI, Airflow, Redash, Slack Bot) |

---

## 🛠 기술 스택 및 채택 근거

> 단순 나열이 아닌 **"왜 이 기술인가?(Why)"** 에 집중합니다.  
> 모든 선정 기준: **성능** · **비용 가성비** · **운영 자동화**

### ⚡ 데이터 파이프라인

| 기술 | 역할 | 채택 근거 |
|------|------|-----------|
| **Kinesis Data Streams** | 실시간 로그 수집 | 트래픽 특성별(Impression/Click/Conversion) 독립 스트림 분리로 처리 우선순위 충돌 방지 |
| **Kinesis Firehose** | S3 적재 자동화 | 서버리스 기반 실시간 Parquet 변환 및 자동 적재 |
| **AWS Glue Catalog** | 스키마 자동 관리 | S3 데이터 스키마 변화 실시간 감지 및 자동화 |
| **Amazon S3** | 데이터 레이크 | 파티셔닝(year/month/day/hour) 기반 대용량 통합 관리 및 저비용 구조 |

### 🧠 AI & LLM

| 기술 | 역할 | 채택 근거 |
|------|------|-----------|
| **Claude 3.5 Haiku** | SQL 생성 LLM | 우수한 코드 작성 능력 및 높은 가성비 |
| **Vanna AI** | Text-to-SQL 프레임워크 | 파이프라인 추상화 및 학습 용이성 |
| **ChromaDB** | RAG 지식 베이스 (벡터 DB) | ko-sroberta 임베딩 모델 정합성 및 Vanna 호환성 |
| **ko-sroberta** | 한국어 임베딩 모델 | 한국어 질문의 의미적 유사도 검색 정확도 극대화 |

### ⚙️ 프로세싱 & 운영

| 기술 | 역할 | 채택 근거 |
|------|------|-----------|
| **Amazon EKS** | 컨테이너 오케스트레이션 | Helm 기반 통합 관리 및 파드 단위 격리·확장성 |
| **Karpenter** | 오토스케일러 | 초고속 노드 프로비저닝 및 Spot 인스턴스 기반 **비용 70% 절감** |
| **Terraform** | IaC | 인프라/K8s 리소스 단일 코드베이스 관리, **25분 내 완전 배포** |
| **Apache Airflow** | 워크플로우 오케스트레이션 | KubernetesPodOperator를 통한 리소스 격리 (OOM 방지) |
| **Amazon Athena** | 서버리스 쿼리 엔진 | 서버 운영 없는 즉시 쿼리 및 S3 파티셔닝과 결합하여 **비용 80% 절감** |

### 📈 인터페이스 & 모니터링

| 기술 | 역할 | 채택 근거 |
|------|------|-----------|
| **Slack Bot** | 사용자 인터페이스 | 챗봇 지원 및 기존 협업 환경 최적화 |
| **Redash** | BI 대시보드 | Athena 네이티브 지원 + Jinja2 파라미터 기반 파티션 매핑으로 비용 최적화 |
| **Prophet + Isolation Forest** | 이상 탐지 | 계절성+통계 앙상블로 오탐 최소화 |
| **DynamoDB** | 멀티턴 세션 저장 | 서버리스 + 낮은 지연으로 대화 이력 고속 조회 |
| **CloudWatch** | 인프라 모니터링 | Kinesis 스트림 모니터링 및 이상치 탐지 연동 |

### 🔧 Backend

| 기술 | 역할 |
|------|------|
| **Python 3.11+** | 메인 런타임 |
| **FastAPI** | 비동기 API 서버 (Pydantic 스키마 검증) |
| **Slack Bolt (async)** | Slack 이벤트 처리 |

---

## 📁 프로젝트 구조

```
CAPA/
├── infrastructure/                # 인프라 코드 (IaC)
│   ├── terraform/                 # Terraform 모듈 및 환경 설정
│   │   ├── modules/               # 재사용 모듈 (kinesis, s3, glue, eks, iam)
│   │   └── environments/dev/      # 환경별 배포 설정
│   │       ├── base/              # [Layer 1] AWS 인프라 (VPC, EKS, Kinesis, S3)
│   │       └── apps/              # [Layer 2] K8s 애플리케이션 (Helm Release)
│   └── helm-values/               # Helm Chart Values (Airflow, Vanna 등)
│
├── services/                      # 애플리케이션 소스 코드
│   ├── log-generator/             # 광고 로그 시뮬레이터 (Impression/Click/Conversion)
│   ├── vanna-api/                 # Text-to-SQL AI 엔진 (FastAPI + Vanna AI + ChromaDB)
│   ├── slack-bot/                 # Slack Bot (Socket Mode + 비동기 처리)
│   ├── airflow-dags/              # Airflow DAG (집계, 리포트, 이상탐지)
│   ├── report-generator/          # 자동 리포트 생성기
│   └── t3_anomaly_detector/       # Prophet + Isolation Forest 이상 탐지 모듈
│
├── docs/                          # 프로젝트 문서
│   ├── t1/                        # 아키텍처, 도메인 분석, 구현 가이드, 발표 시나리오
│   ├── t2/                        # 데이터 파이프라인 개발 가이드
│   └── t3/                        # 배포, 운영, 이상탐지 가이드
│
├── .github/                       # GitHub 설정 (CI/CD, PROJECT_RULES)
├── DIRECTORY_STRUCTURE.md          # 상세 디렉토리 구조 문서
├── MIGRATION_GUIDE.md             # 마이그레이션 가이드
└── LICENSE                        # MIT License
```

---

## 🚀 시작하기

### 사전 요구사항

- **AWS CLI** v2 + 유효한 AWS 자격 증명
- **Terraform** >= 1.5
- **kubectl** + **Helm** v3
- **Python** >= 3.11
- **Slack Workspace** (Bot Token, App Token)

### 1단계: 인프라 배포 (Base Layer)

```bash
cd infrastructure/terraform/environments/dev/base
terraform init
terraform plan
terraform apply    # ~20분 소요 (EKS 클러스터 생성)
```

### 2단계: 애플리케이션 배포 (Apps Layer)

```bash
cd ../apps
terraform init
terraform apply    # ~5분 소요 (Helm Release 배포)
```

### 3단계: 배포 검증

```bash
# 전체 Pod 상태 확인
kubectl get pods -A

# Airflow UI 접속
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow

# Slack Bot 연결 확인
kubectl logs -f deployment/slack-bot -n capa
```

### 환경 변수 설정

```bash
# .env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
ANTHROPIC_API_KEY=sk-ant-...
AWS_REGION=ap-northeast-2
```

---

## 📊 성과 지표

| 지표 | Before (AS-IS) | After (TO-BE) | 개선율 |
|------|:---------------:|:-------------:|:------:|
| **데이터 접근 속도** | 수 시간 ~ 수일 | 수십 초 이내 | **≈ 99% 단축** |
| **SQL 실행 정확도** | - | 80.6% (Execution Accuracy) | 4라운드 PDCA 개선 |
| **리포트 생성** | 매일 수기 엑셀 집계 | Airflow 완전 자동화 | 담당자 개입 **0회** |
| **이상 탐지** | 사람이 대시보드 직접 확인 | AI 5분 주기 실시간 감지 | **무인 모니터링** |
| **인프라 비용** | On-Demand 기준 | Karpenter + Spot | **최대 70% 절감** |
| **쿼리 비용** | 풀스캔 기준 | S3 파티셔닝 + Parquet | **약 80% 절감** |
| **인프라 배포** | 수동 설정 | Terraform IaC | **25분 완전 배포** |
| **OOM 장애** | Airflow 워커 장애 발생 | KubernetesPodOperator 격리 | 재발 **0건** |

### SQL 정확도 4라운드 개선 스토리

```
Round 1: 33.3%  ── QA 시딩 편향성 해결 + 날짜 동적 처리 (Jinja2)
Round 2: 36.1%  ── CoT 6단계 프롬프트 + 계산식 공식화 (CTR/CVR/ROAS)
Round 3: 69.4%  ── 한국어 특화 임베딩 모델 도입 (ko-sroberta)
Round 4: 80.6%  ── QA 메타데이터 기반 DDL 동적 주입 (Metadata Backtracking)
```

---

## 👥 팀 구성

| 이름 | 역할 | 담당 영역 |
|------|------|-----------|
| **장현우** | 팀장 / 인프라 & AI 엔진 | AWS 클라우드 인프라 아키텍처 설계, Text-to-SQL 엔진 (RAG 파이프라인) 구축, MVP 전체 설계 주도 |
| **김시현** | 데이터 수집 & 시각화 | Kinesis 기반 실시간 데이터 수집 파이프라인, Redash BI 대시보드 구축 |
| **김병훈** | 자동화 & 이상탐지 | Airflow 기반 리포트 자동화, Prophet + Isolation Forest 이상 탐지 시스템 |

---

## 📚 문서

| 문서 | 설명 |
|------|------|
| [Implementation Guide](docs/t1/implementation_guide.md) | 컴포넌트별 구현 가이드 및 API 스펙 |
| [MVP Schedule](docs/t1/mvp_schedule.md) | 10일 MVP 일정 및 확장 계획 |
| [Ad Domain Analysis](docs/t1/ad_domain_analysis.md) | 광고 도메인 지식 및 로그 데이터 스키마 |
| [Infrastructure README](infrastructure/README.md) | Terraform 계층 분리 및 배포 가이드 |
| [Services README](services/README.md) | 서비스별 설명 및 로컬 개발 방법 |
| [Directory Structure](DIRECTORY_STRUCTURE.md) | 상세 디렉토리 구조 |
| [Migration Guide](MIGRATION_GUIDE.md) | src → services 마이그레이션 가이드 |

### Text-to-SQL 개선 이력

순차적 개선 과정이 `docs/t1/pt-시나리오/` 하위에 기록되어 있습니다:

```
00_mvp_develop          → MVP 기본 파이프라인 구축
01_multi-turn           → 멀티턴 대화 지원
02~03_chromadb-seed     → RAG 시딩 및 업그레이드
04_evaluation           → 정확도 평가 프레임워크
05_prompt-engineering   → CoT 프롬프트 설계
06_sql-accuracy-tuning  → SQL 정확도 튜닝
07~10_rag-optimization  → RAG 검색 최적화 시리즈
11_dynamic-ddl          → DDL 동적 주입 (Round 4 핵심)
12~14_pipeline-tuning   → 파이프라인 최종 최적화
15_eks-deployment       → EKS 프로덕션 배포
```

---

## 📜 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.

---

<p align="center">
  <sub>📋 <strong>개발 규칙</strong>: 이 프로젝트는 <a href=".github/PROJECT_RULES.md">PROJECT_RULES.md</a>를 따릅니다.</sub>
</p>
