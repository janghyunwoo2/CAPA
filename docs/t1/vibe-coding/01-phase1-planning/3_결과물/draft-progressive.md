# 📋 계획서 템플릿 (진보적 접근)

> 스프린트/기능: CAPA MVP Phase 1 - AI-Native Pipeline  
> 작성일: 2026-02-11  
> 버전: v0.1 (혁신적 초안)

---

## 1. 목표 정의

### 1.1 핵심 목표
본 프로젝트는 **AI-Native 데이터 플랫폼**을 목표로, 최신 기술 스택을 통한 **초고속 개발 생산성**과 **차별화된 분석 경험**을 제공합니다. 레거시 패턴을 배제하고, 미래 확장이 용이한 Modern Data Stack을 구축합니다.

```
[목표 요약]
- **Modern Data Lake**: Apache Iceberg 도입으로 스키마 진화 및 Time-travel 지원
- **AI-First Analytics**: Text-to-SQL(Vanna) 및 AI Agent(Pydantic AI) 초기 통합
- **Serverless & Automation**: 100% 서버리스 아키텍처로 운영 오버헤드 제로화
```

### 1.2 성공 기준 (Definition of Done)
단순 기능 구현을 넘어, 사용자 경험(UX)과 개발 생산성 향상에 초점을 둡니다.

| 기준 | 측정 방법 | 목표값 (도전적) |
|------|----------|--------|
| 배포 속도 | PR Merge부터 배포 완료까지 | < 5분 (CI/CD 완전 자동화) |
| AI 답변 속도 | 질문 입력 ~ 답변 출력 | < 10초 |
| 데이터 신선도 | 리얼타임 대시보드 반영 | < 1분 (Near Real-time) |
| 스키마 변경 | 컬럼 추가/변경 시 다운타임 | 0초 (Iceberg Evolution) |

### 1.3 범위 (Scope)
실험적인 AI 기능까지 MVP에 과감하게 포함하여 시장 반응을 빠르게 확인합니다 (Fail Fast).

**포함 (In Scope)**:
- [ ] **Ingestion**: Kinesis Data Stream (On-demand) -> Firehose
- [ ] **Lakehouse**: S3 + Apache Iceberg (Glue Catalog 연동)
- [ ] **AI Core**: Vanna AI (RAG) + Pydantic AI (Agentic Workflow)
- [ ] **Observability**: OpenTelemetry + CloudWatch Evidently (A/B 테스트)
- [ ] **Infra**: AWS CDK (TypeScript) 기반 IaC

**제외 (Out of Scope)**:
- [ ] 고정된 대시보드 (Redash 대신 AI 리포트 생성 우선)
- [ ] 레거시 배포 방식 (EC2/VM 배제)

---

## 2. 배경 및 문제 정의

### 2.1 현재 상황
느린 데이터 조회 속도와 경직된 스키마는 비즈니스 민첩성을 저해하고 있습니다. 기존 방식의 점진적 개선으로는 급변하는 시장 요구를 따라잡을 수 없습니다.

### 2.2 해결해야 할 문제
단순 조회 업무 제거를 넘어, 데이터 소비 방식의 패러다임을 전환해야 합니다.

| 문제 | 영향 | 해결 방향 (혁신) |
|------|------|------------------|
| 스키마 변경의 어려움 | 신규 지표 수집 지연 | **Apache Iceberg**로 유연한 스키마 대응 |
| 수동 분석의 한계 | 인사이트 발견 실패 | **AI Agent**가 이상 징후 능동 탐지 |
| 운영 리소스 부족 | 개발 속도 저하 | **Serverless/On-demand**로 인프라 관리 제거 |

---

## 3. 기술 스택 및 아키텍처 방향

### 3.1 사용 기술
**Cloud-Native & AI-Driven** 최신 스택을 적극 채택합니다.

| 영역 | 기술 | 버전 | 선택 이유 |
|------|------|------|-----------|
| 언어 | Python | 3.12+ | 최신 성능 개선 및 타입 힌트 활용 |
| 데이터 수집 | Kinesis | On-demand | 트래픽 예측 불필요, 무한 오토스케일링 |
| 데이터 레이크 | Iceberg | 1.4+ | ACID 트랜잭션, 파티션 진화 지원 |
| 쿼리 엔진 | Athena | V3 | Iceberg 네이티브 지원 |
| AI 프레임워크 | LangChain / Vanna | Latest | LLM 오케스트레이션 사실상 표준 |
| AI 에이전트 | Pydantic AI | Beta | 타입 안전성을 보장하는 최신 에이전트 프레임워크 |
| IaC | AWS CDK | v2 | 프로그래밍 언어(TS)로 인프라 정의 (생산성 ⬆️) |

### 3.2 아키텍처 개요
Event-Driven 및 Microservices(Lambda) 아키텍처로 유연성을 극대화합니다.

```
[Modern AI Architecture]

[Log Gen] -> [Kinesis On-demand] -> [Firehose] -> [S3 (Iceberg Table)]
                                                         │
                                                  [Athena / Glue]
                                                         │
[Slack UI] <-> [Lambda (FastAPI)] <-> [AI Agent (Pydantic/Vanna)]
                     │                           │
              [DynamoDB (Cache)]         [ChromaDB (Vector Memory)]
```

---

## 4. 작업 분해 (WBS)
MVP 우선 원칙에 따라 핵심 기능을 병렬로 개발하며, **자동화**를 통해 개발 속도를 가속화합니다.

### 4.1 작업 목록

| ID | 작업명 | 담당 역할 | 예상 시간 | 우선순위 | 의존성 |
|----|--------|----------|----------|----------|--------|
| T-001 | AWS CDK 모듈 세팅 및 CI/CD 구축 | DevOps | 1일 | P0 | - |
| T-002 | Kinesis -> Iceberg 파이프라인 (CDK) | DE | 2일 | P0 | T-001 |
| T-003 | Vanna + Pydantic AI 베이스라인 구축 | AI Eng | 2일 | P0 | T-001 |
| T-004 | Slack Bot (App Manifest 자동화) | Backend | 1일 | P1 | - |
| T-005 | 통합 및 AI 답변 품질 튜닝 | 전원 | 2일 | P0 | T-002, T-003|

> *참고: 예상 시간은 숙련된 엔지니어가 최신 도구(Copilot 등)를 활용했을 때 기준입니다.*

### 4.2 마일스톤

```
┌─────────────────────────────────────────────────────────────────────┐
│ 타임라인 (Fast & Furious)                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Week 1        Week 2                                               │
│  ├─────────────┼─────────────┤                                      │
│  │             │             │                                      │
│  ▼ Sprint 1    ▼ Sprint 2    │                                      │
│    Pipeline &    AI Integration                                     │
│    Platform      & Launch                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. 리스크 및 대응 방안 (Progressive)

| 리스크 | 영향도 | 발생 확률 | 대응 방안 |
|--------|--------|----------|-----------|
| 최신 기술 버그 | 높음 | 중간 | 오픈소스 커뮤니티 기여 또는 빠른 우회 구현 (Patch mindset) |
| 학습 곡선 | 중간 | 높음 | 페어 프로그래밍 및 AI 코딩 어시스턴트 적극 활용 |
| 비용 초과 | 낮음 | 중간 | AWS Budget Action으로 예산 초과 시 즉시 알림/중지 |
| LLM API 비용 | 중간 | 중간 | 작은 모델(gpt-3.5/haiku)로 캐싱 및 1차 필터링 |

---

## 6. 리소스 요구사항

### 6.1 인프라
- [ ] **OpenAI API / Anthropic API**: 티어 2 이상 확보 (Rate Limit 해제)
- [ ] **AWS Lambda**: SnapStart 활성화 (Java/Python 콜드스타트 제거)
- [ ] **GitHub Copilot**: 전원 지급 (생산성 30% 향상 목표)

### 6.2 도구
- [ ] **Poetry**: 의존성 관리
- [ ] **Ruff**: 고성능 Python Linter (Pre-commit)

### 6.3 인력
- [ ] **Full Stack Engineer**: 2명 (구분 없이 기능 단위 개발)
- [ ] **AI Engineer**: 1명 (프롬프트 엔지니어링 및 RAG 최적화)

---

## 7. 검토 및 승인
빠른 의사결정을 위해 비동기 리뷰를 지향합니다.

| 항목 | 검토자 | 상태 | 방식 |
|------|--------|------|------|
| 기술 검토 | CTO | 대기 | PR Review |
| 승인 | PO | 대기 | MVP 데모 시연 |

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| v0.1 | 2026-02-11 | 진보적 페르소나 기반 초안 작성 | CAPA Team |
