# CAPA 프로젝트 - Claude Code 설정

## 프로젝트 개요

**CAPA (Cloud-native AI Pipeline for Ad-logs)**
온라인 광고 로그(impression → click → conversion)를 실시간 수집·처리·분석하는 AWS 기반 데이터 파이프라인 플랫폼.

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| 언어 | Python 3.11+ |
| 인프라 (IaC) | Terraform 1.0+ |
| 워크플로우 | Apache Airflow 2.7+ |
| 컨테이너 | Docker / Kubernetes 1.28+ |
| 클라우드 | AWS (Kinesis, S3, Glue, Athena, EKS, ECR) |
| AI 분석 | Vanna, Pydantic AI |
| BI | Redash (Athena 연동) |

## 디렉토리 구조 요약

```
CAPA/
├── services/               # 애플리케이션 서비스
│   ├── log-generator/      # 광고 로그 시뮬레이터
│   ├── airflow-dags/       # Airflow DAG 정의
│   ├── data_pipeline_t2/   # 데이터 처리 파이프라인
│   ├── vanna-api/          # AI Text-to-SQL API
│   ├── report-generator/   # 리포트 생성 서비스
│   └── slack-bot/          # Slack 알림 봇
├── infrastructure/         # 인프라 코드
│   ├── terraform/          # AWS 리소스 IaC
│   └── helm-values/        # Kubernetes Helm 설정
├── docs/                   # 프로젝트 문서
│   ├── t1/                 # t1(본인) 담당 문서
│   │   ├── text-to-sql/                        # AI Text-to-SQL 파이프라인 (주요 개발)
│   │   │   ├── 00_mvp_develop/                 # Phase 1+2 MVP 개발 완료
│   │   │   │   ├── 00-기타/                    # 사전조사, E2E 시나리오
│   │   │   │   ├── 01-plan/                    # 기획 문서
│   │   │   │   ├── 02-design/                  # 설계 문서 (Phase 1+2 RAG 고도화 포함)
│   │   │   │   ├── 03-analysis/                # Gap 분석
│   │   │   │   ├── 04-report/                  # 완료 보고서
│   │   │   │   └── 05-test/                    # 테스트 계획/결과
│   │   │   ├── 01_multi-turn-conversation/     # 멀티턴 대화 기능
│   │   │   ├── 02_txt-to-sql-slack/            # Slack 봇 연동
│   │   │   ├── 03_chromadb-seed-upgrade/       # ChromaDB 시딩 업그레이드
│   │   │   ├── 04-evaluation/                  # Spider EM/Exec 평가 체계 (진행 중)
│   │   │   └── 05_prompt-engineering-enhancement/  # 프롬프트 엔지니어링 강화
│   │   ├── airflow-dag-deployment/             # Airflow DAG 배포 문서
│   │   ├── devops/                             # DevOps 작업 기록
│   │   ├── vibe-coding/                        # 바이브 코딩 방법론 실험
│   │   └── project_concept/                    # 프로젝트 컨셉 문서
│   ├── t2/                 # t2 팀원 담당 문서
│   └── t3/                 # t3 팀원 담당 문서
└── .github/                # CI/CD, 프로젝트 규칙
```

# [통합 개발 및 에이전트 규칙]
## 2. 코딩 및 작업 원칙
- **언어**: 모든 답변과 설명은 반드시 **한국어**로 작성한다.
- **계획 우선**: 복잡한 작업은 코드를 작성하기 전 **[작업 계획]**을 요약하여 승인받는다.
- **기술 스택**: **Stable/LTS** 버전 기준, 하위 호환성 고려
- **최소 수정**: 요청 목적에 집중, 불필요한 코드 수정 지양
- **안정성**: `async/await`에 `try-catch` 필수
- **타입 엄격**: `any` 금지, Interface/Type 명시
- **의존성 확인**: 수정 전 의존성·사이드 이펙트 확인
- **자기 검증**: 출력 전 로직 오류·타입 위반 최종 검토
- **객관적 비판**: 사용자 로직이 최선이 아니면 근거와 대안 제시

# [팩트 및 데이터 엄격성 준수 규칙 (Hallucination 방지)]

1. **최신 데이터 검색 강제:** AWS 요금 등 변동 수치 → 웹 검색으로 최신 공식 자료 먼저 확인
2. **출처 및 기준일 명시:** 공식 출처(URL)·기준 리전·검색일 명시
3. **투명한 계산 과정:** 중간 계산식 시각 표시 — `단가 × 수량 × 시간 = 총액`
4. **Fact-Only:** 사용자 기대에 맞춰 수치 조작 금지, 팩트 기반 수치만 제공
5. **무지 인정:** 확인 불가 시 "계산 불가" 명시, 유추·추정 금지

## 커밋 메시지 규칙

```
<type>(<scope>): <subject>

<body>
```

- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 수정
- `refactor`: 리팩토링
- `test`: 테스트 코드
- `chore`: 빌드/설정 변경

**예시**: `feat(log-generator): impression 이벤트에 device_type 필드 추가`

## 브랜치 전략

```
main (프로덕션)
  └── develop (통합)
        ├── feat/<담당자>/<기능명>   # 예: feat/t1/Text2SQL
        ├── fix/<담당자>/<버그명>
        └── refactor/<담당자>/<대상>
```

## 자주 발생하는 실수 (팀 경험 기반)

- ❌ AWS boto3 호출 시 `try-except` 누락 사례 있음
  → async 여부와 관계없이 모든 boto3 API 호출은 `ClientError` try-except 필수
- ❌ FastAPI async 엔드포인트 반환 타입 누락 사례 있음
  → `@app.get/post` 함수는 `-> 반환타입` 또는 `response_model` 필수
- ❌ Docker 이미지 `latest` 태그 사용 사례 있음
  → 유틸 이미지(`curlimages/curl` 등)도 반드시 버전 명시 (예: `curlimages/curl:8.5.0`)


## 🚨 [중요] 팀 모드(Team Mode) 워크플로우 엄격 준수 지침

팀 작업 시 아래 순서 100% 엄수, 단계 생략·순서 변경 절대 금지.

### 핵심 원칙

CC nested spawn 제한 → Claude가 모든 에이전트 직접 병렬 spawn, CTO lead는 `SendMessage`로 조율.

### 필수 절차

1. **[1단계] `TeamCreate`**: 팀 생성 (bkit 계획 데이터만 읽지 말고 반드시 도구 실행)
2. **[2단계] `TaskCreate`**: 팀원별 작업 목록 생성 (CTO lead + 전문가 에이전트별 개별 Task)
3. **[3단계] `Agent` 병렬 spawn**: CTO lead + 전문가 에이전트 동시 spawn, 모두 `team_name` 포함

### 오케스트레이션 구조

```
[나 (Claude)] ← 메인 오케스트레이터
  │
  ├─ 1. TeamCreate("{팀이름}")
  ├─ 2. CTO lead에게 요구사항 전달 → CTO lead가 필요한 팀원 구성을 결정
  ├─ 3. TaskCreate (CTO lead가 결정한 팀원별 작업 분배)
  │
  └─ 4. 한 번의 메시지에서 병렬 Agent spawn (모두 team_name 포함):
       ├─ Agent(bkit:cto-lead, team_name="{팀이름}", name="cto-lead")  ← 조율자
       ├─ Agent({CTO가 선정한 에이전트1}, team_name="{팀이름}", name="...")
       ├─ Agent({CTO가 선정한 에이전트2}, team_name="{팀이름}", name="...")
       └─ ...

CTO lead의 역할:
  - 요구사항에 맞는 팀원 구성 결정 (어떤 전문가 에이전트가 필요한지)
  - SendMessage로 팀원에게 작업 지시/조율
  - 팀원 결과물 수합 및 품질 검토
  - 최종 보고서 작성
  ※ Task()로 에이전트 생성하지 않음 (nested spawn 불가)
```

### 트리거 방법
- 사용자가 "팀으로 작업해", "cto 팀으로", "cto 팀 써줘" 등 팀 모드를 요청하면
  → `Skill("bkit:pdca", "team {feature}")` 실행 후 위 3단계 절차 수행

### `/pdca team status` 출력 형식 (필수 준수)

`/pdca team status` 또는 상태 조회 시 반드시 아래 형식으로 출력해야 합니다:

```
📊 PDCA Team Status
─────────────────────────────────────────────────
Agent Teams: Available ✅
레벨: {Dynamic|Enterprise} | 팀: {팀이름}
오케스트레이션: {leader|swarm|council|watchdog} ({현재 PDCA 단계})
─────────────────────────────────────────────────
팀원: {현재수} / {총수} ({레벨})
─────────────────────────────────────────────────
Feature: {피처명}
  {팀원명}:  [{담당 Task}] {✅ completed|🔄 in_progress|⏳ pending} → {idle|active}
  {팀원명}:  [{담당 Task}] {상태} → {idle|active}
  ...
─────────────────────────────────────────────────
[Plan] {✅|⏳} → [Design] {✅|⏳} → [Do] {✅|⏳} → [Check] {✅|⏳} → [Act] {✅|⏳}
─────────────────────────────────────────────────

팀원 보고 요약:

┌───────────┬──────────────────┬────────┬────────────────────────────────────┐
│   팀원    │       담당       │  상태  │             핵심 기여              │
├───────────┼──────────────────┼────────┼────────────────────────────────────┤
│ {팀원명}  │ {담당 섹션/역할} │ ✅     │ {실제 기여 내용 요약}              │
│ ...       │ ...              │ ...    │ ...                                │
└───────────┴──────────────────┴────────┴────────────────────────────────────┘
```

**필수 포함 항목:**
- `레벨`: Dynamic/Enterprise
- `오케스트레이션`: leader/swarm/council/watchdog
- `팀원`: 이름·담당 Task·상태·idle/active
- `팀원 보고 요약`: 실제 수행 작업 내용
- 모델: cto-lead=`claude-opus-4-6`, 나머지=`claude-sonnet-4-6`

### ❌ 금지 사항
1. `TeamCreate` 없이 `Agent` 단독 호출 금지
2. 팀원 spawn 시 `team_name` 누락 금지
3. CTO lead만 단독 spawn 금지 — 전문가 에이전트도 반드시 함께 병렬 spawn (nested spawn 불가)
4. `Agent(bkit:cto-lead)` 호출 시 `TeamCreate` 이후 `team_name` 필수

## 참고 문서

- [세부 코딩 규칙](.claude/rules/coding-rules.md)
- [테스트 규칙](.claude/rules/test-rules.md)

---

## 작업 기록

### 2026-03-24 — Text-to-SQL RAG 정확도 개선 (jina-reranker-v2 최적화)

**작업 배경**
- `PHASE2_RAG_ENABLED=true` 환경에서 `jina-reranker-v2-base-multilingual`이 이미 활성화되어 있었으나,
  ChromaDB 검색 거리(distance) 정보가 reranker에 전달되지 않는 버그 발견

**수정 파일 및 내용**

| 파일 | 수정 내용 |
|------|----------|
| `src/query_pipeline.py` | `get_similar_question_sql` 오버라이드에서 ChromaDB `distances`를 `score = 1/(1+distance)`로 변환 후 반환<br>Phase2 활성화 시 `n_results`를 `max(n_results_sql, 20)`으로 확대하여 reranker 후보 풀 증가<br>미사용 `import uuid` 제거 |
| `src/pipeline/rag_retriever.py` | `_retrieve_sql_examples_with_score()` 메서드 신설 — score와 `Q:/SQL:` 포맷 텍스트 함께 반환<br>`_retrieve_candidates()`에서 SQL 예제에 한해 `initial_score=1.0` 고정값 → 실제 ChromaDB 유사도 점수로 교체<br>Phase1 하위 호환 `_retrieve_sql_examples()`는 위 메서드에 위임하는 구조로 리팩토링 |

**개선 효과**
- Bi-encoder(ko-sroberta) 유사도 정보가 reranker에 정확히 전달되어 재정렬 품질 향상
- 후보 풀 확대(10→20)로 구어체 질문도 관련 예제가 후보에 포함될 가능성 증가
- `Q: {question}\nSQL: {sql}` 포맷으로 reranker가 질문-SQL 맥락을 함께 평가 가능
