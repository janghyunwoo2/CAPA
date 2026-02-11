# 📋 계획서 템플릿 (중도 접근)

> 스프린트/기능: CAPA MVP Phase 1 - Hybrid Foundation  
> 작성일: 2026-02-11  
> 버전: v0.1 (실용적 초안)

---

## 1. 목표 정의

### 1.1 핵심 목표
본 프로젝트는 **안정적인 데이터 파이프라인 구축**을 기반으로 하되, **AI 기반 분석 가능성**을 MVP 단계에서 검증하는 균형 잡힌 접근을 취합니다. 핵심 비즈니스 로직은 보수적으로 보호하고, 분석 편의성은 혁신적으로 개선합니다.

```
[목표 요약]
- **Core Pipeline**: Kinesis-S3-Athena 기반의 검증된 로그 수집/저장 환경 구축 (안정성 보장)
- **AI Module (Experimental)**: Vanna AI 기반의 Text-to-SQL 프로토타입 격리 구현 (혁신성 검증)
- **Data Quality**: Glue Data Catalog를 통한 체계적인 메타데이터 관리
```

### 1.2 성공 기준 (Definition of Done)
시스템 안정성과 새로운 가치(AI) 증명을 동시에 고려합니다.

| 기준 | 측정 방법 | 목표값 (현실적) |
|------|----------|--------|
| 파이프라인 가용성 | Kinesis/Firehose Uptime | 99.9% (표준 SLA) |
| 데이터 지연 | 적재 완료 시간 | < 5분 |
| AI 질문 처리율 | Text-to-SQL 성공률 (샘플 50개) | > 80% (초기 목표) |
| 쿼리 정확도 | 생성된 SQL의 문법적 오류 없음 | 95% 이상 |

### 1.3 범위 (Scope)
핵심 파이프라인은 필수 범위이며, AI 기능은 '격리된 모듈'로서 안전하게 포함합니다.

**포함 (In Scope)**:
- [ ] **Core**: Kinesis Data Stream (On-demand) & Firehose (Dynamic Partitioning)
- [ ] **Storage**: S3 Standard (Parquet 포맷) + Glue Catalog
- [ ] **Analytics**: Athena V3 표준 구성
- [ ] **AI (Beta)**: Vanna AI 컨테이너 (ECS/Fargate) 및 기본 질문 셋 학습
- [ ] **UI**: Slack Bot (질문 수신 -> Vanna 전달 -> 답변)

**제외 (Out of Scope)**:
- [ ] 복잡한 Agent 오케스트레이션 (Pydantic AI 등은 Phase 2 고려)
- [ ] 실시간 시계열 예측 (Prophet) - CloudWatch 알람으로 대체
- [ ] Iceberg 등 최신 테이블 포맷 (Parquet으로 충분, v2에서 검토)

---

## 2. 배경 및 문제 정의

### 2.1 현재 상황
데이터는 쌓이고 있으나 활용이 어렵고, 단순 조회 요청 처리에 데이터 팀 리소스가 낭비되고 있습니다. 완전한 자동화보다는 "분석 보조 도구"로서의 AI 도입이 시급합니다.

### 2.2 해결해야 할 문제
안정성을 해치지 않으면서 분석 생산성을 높여야 합니다.

| 문제 | 영향 | 해결 방향 (균형) |
|------|------|------------------|
| 반복적인 SQL 요청 | 팀 생산성 저하 | AI가 초안 쿼리 작성 (인간 검토) |
| 데이터 유입 변동성 | 파이프라인 병목 | Kinesis On-demand로 유연하게 대응 |
| 신뢰성 부족 | 의사결정 지연 | Core 파이프라인은 보수적 아키텍처 유지 |

---

## 3. 기술 스택 및 아키텍처 방향

### 3.1 사용 기술
**Core는 Stable, AI는 Modern** 전략을 사용합니다.

| 영역 | 기술 | 버전 | 선택 이유 |
|------|------|------|-----------|
| 데이터 수집 | Kinesis Data Stream | On-demand | 관리 요소 제거 및 트래픽 변동 대응 (비용 효율성) |
| 데이터 적재 | Kinesis Firehose | Dynamic Partitioning | Lambda 없이 파티셔닝 처리 가능 (운영 간소화) |
| 저장소 | S3 | Parquet | 가장 범용적이고 성숙한 포맷 |
| AI (격리) | Vanna AI | Latest | RAG 기반 Text-to-SQL의 사실상 표준 라이브러리 |
| 벡터 DB | ChromaDB | Embedded | 별도 서버 구축 없이 가볍게 시작 가능 |
| 인프라 | Terraform | Stable | 표준 IaC 도구 |

### 3.2 아키텍처 개요
Core 파이프라인과 AI 서비스를 느슨하게 결합(Loose Coupling)하여 리스크를 격리합니다.

```
[Hybrid Architecture]

(Stable Core)                     (Experimental Module)
Log Gen -> Kinesis -> Firehose    Slack Bot -> [API Gateway -> Lambda]
                      │                              │
                      ▼                              ▼
                 [S3 (Parquet)] <--- [Athena] <--- [Vanna AI Container]
                                         │              ▲
                                         └--- (Meta) ---┘
```

---

## 4. 작업 분해 (WBS)
일정에는 학습 곡선과 안정화를 고려해 **20%의 버퍼**를 포함합니다.

### 4.1 작업 목록

| ID | 작업명 | 담당 역할 | 예상 시간 | 버퍼 | 총계 | 의존성 |
|----|--------|----------|----------|---|---|--------|
| T-001 | Terraform 기본 인프라 (VPC, IAM, S3) | Infra | 2일 | 0.5일 | 2.5일 | - |
| T-002 | Kinesis On-demand & Firehose 구성 | DE | 2일 | 0.5일 | 2.5일 | T-001 |
| T-003 | Glue Crawler & Athena 테이블 최적화 | DE | 2일 | 0.5일 | 2.5일 | T-002 |
| T-004 | Vanna AI 학습 데이터(DDL) 준비 및 테스트 | AI/DE | 3일 | 1.0일 | 4.0일 | T-003 |
| T-005 | Slack Bot API 개발 (AI 연동) | Backend | 3일 | 0.5일 | 3.5일 | T-004 |
| T-006 | 통합 테스트 (E2E) | 전원 | 2일 | 0.5일 | 2.5일 | T-005 |

### 4.2 마일스톤

```
┌─────────────────────────────────────────────────────────────────────┐
│ 타임라인 (실용적 접근)                                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Week 1        Week 2        Week 3        Week 4                   │
│  ├─────────────┼─────────────┼─────────────┼─────────────┤          │
│  │             │             │             │             │          │
│  ▼ M1: Core    ▼ M2: Data    ▼ M3: AI      ▼ M4: 통합   │          │
│    Infra         Ready         Proto         Release      │          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. 리스크 및 대응 방안 (Balanced)

| 리스크 | 영향도 | 발생 확률 | 대응 방안 |
|--------|--------|----------|-----------|
| AI 답변 환각 (Hallucination) | 높음 | 중간 | SQL 실행 전 사용자에게 쿼리 노출 및 확인 절차 추가 ("이 쿼리가 맞나요?") |
| Kinesis 비용 증가 | 중간 | 중간 | On-demand 사용량 모니터링 및 일일 예산 알람 설정 |
| Vanna 학습 품질 저하 | 중간 | 높음 | 초기 학습 데이터(DDL/Documentation)를 고품질로 큐레이션 |
| 파이썬 패키지 호환성 | 낮음 | 중간 | AI 모듈은 Docker Container로 격리 배포하여 의존성 충돌 방지 |

---

## 6. 리소스 요구사항

### 6.1 인프라
- [ ] **AWS Fargate**: Vanna AI / API 서버 구동용 (관리 부담 최소화)
- [ ] **S3**: Lifecycle Policy 적용 (30일 후 IA 전환)
- [ ] **VPC**: Private Subnet 구성 (보안)

### 6.2 도구
- [ ] **GitHub Actions**: CI/CD (Lint, Unit Test)
- [ ] **Redash**: KPI 수동 대시보드 (AI 보완재)

### 6.3 인력
- [ ] **Backend/AI Eng**: 1.5MD (Vanna 연동 및 튜닝)
- [ ] **Data Engineer**: 1.5MD (파이프라인 및 데이터 모델링)

---

## 7. 검토 및 승인

| 항목 | 검토자 | 상태 | 날짜 |
|------|--------|------|------|
| 아키텍처 리뷰 | DE Lead | 대기 | |
| 비용 효율성 검토 | PM | 대기 | |
| 최종 승인 | PO | 대기 | |

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| v0.1 | 2026-02-11 | 중도 페르소나 기반 초안 작성 | CAPA Team |
