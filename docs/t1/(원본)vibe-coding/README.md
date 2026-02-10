# 🎵 바이브 코딩 방법론 - CAPA 프로젝트 적용 가이드

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  바이브 코딩 (Vibe Coding) 워크플로우                                        ║
║  버전: 1.0.0 | 적용 프로젝트: CAPA                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MD 파일 기반의 체계적인 AI 협업 개발 방법론                                 ║
║  계획 → 검증 → 역할 고도화 → 아키텍처 → 작업 분할 → 실행 → 반복             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 📋 전체 워크플로우 개요

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      바이브 코딩 5단계 프로세스                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [PHASE 1] 계획서 생성 ──────────────────────────────────────────────────   │
│      │                                                                      │
│      ├─► 🔴 보수적 페르소나: 안정성/검증된 기술 중심                         │
│      ├─► 🔵 진보적 페르소나: 혁신/최신 기술 도전                            │
│      ├─► 🟢 중도 페르소나: 균형/실용적 접근                                 │
│      │                                                                      │
│      └─► 📄 계획서 초안 (plan-draft.md)                                    │
│                          │                                                  │
│                          ▼                                                  │
│  [PHASE 2] 검증 ─────────────────────────────────────────────────────────   │
│      │                                                                      │
│      ├─► 🔍 검증 페르소나: 논리적 결함, 기술적 리스크, 일정 현실성 체크      │
│      │                                                                      │
│      └─► 📄 검증 보고서 (validation-report.md)                             │
│                          │                                                  │
│                          ▼                                                  │
│  [PHASE 3] 역할 고도화 ──────────────────────────────────────────────────   │
│      │                                                                      │
│      ├─► 범용 개발자 프롬프트 + 계획서 투입                                 │
│      ├─► 역할별 전문가 프롬프트 생성 (BE, FE, Data, DevOps 등)              │
│      ├─► 역할별 계획서 피드백 반영                                          │
│      │                                                                      │
│      └─► 📄 최종 계획서 (plan-final.md) + 역할별 프롬프트                   │
│                          │                                                  │
│                          ▼                                                  │
│  [PHASE 4] 아키텍처 설계 ────────────────────────────────────────────────   │
│      │                                                                      │
│      ├─► 계획서 기반 시스템 아키텍처 설계                                   │
│      ├─► ASCII 아트 / Mermaid 다이어그램                                   │
│      │                                                                      │
│      └─► 📄 아키텍처 문서 (architecture.md)                                │
│                          │                                                  │
│                          ▼                                                  │
│  [PHASE 5] 작업 분할 및 실행 ────────────────────────────────────────────   │
│      │                                                                      │
│      ├─► 작업.md 생성 (규모/역할별)                                        │
│      ├─► 실행 → 결과.md 저장                                               │
│      ├─► 불만족 시 → 작업.md 수정 후 재실행                                │
│      │                                                                      │
│      └─► ✅ 만족 → 다음 작업.md로 이동                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 디렉토리 구조

```
docs/vibe-coding/
│
├── README.md                    # 본 가이드 문서
│
├── 00-templates/                # 템플릿 모음
│   ├── plan-template.md        # 계획서 템플릿
│   ├── validation-template.md  # 검증 보고서 템플릿
│   ├── task-template.md        # 작업.md 템플릿
│   └── result-template.md      # 결과.md 템플릿
│
├── 01-personas/                 # 페르소나 프롬프트
│   ├── planner/                # 계획 페르소나
│   │   ├── conservative.md    # 🔴 보수적 페르소나
│   │   ├── progressive.md     # 🔵 진보적 페르소나
│   │   └── moderate.md        # 🟢 중도 페르소나
│   │
│   ├── validator/              # 검증 페르소나
│   │   └── critic.md          # 비판적 검증자
│   │
│   └── developers/             # 개발자 페르소나 (역할별)
│       ├── base-developer.md  # 범용 개발자 프롬프트
│       ├── backend.md         # 백엔드 개발자
│       ├── frontend.md        # 프론트엔드 개발자
│       ├── data-engineer.md   # 데이터 엔지니어
│       ├── devops.md          # DevOps 엔지니어
│       └── ml-engineer.md     # ML 엔지니어
│
├── 02-plans/                    # 계획서 저장소
│   ├── sprint-001/
│   │   ├── plan-draft.md      # 초안
│   │   ├── validation.md      # 검증 보고서
│   │   ├── plan-final.md      # 최종 계획서
│   │   └── architecture.md    # 아키텍처
│   └── sprint-NNN/
│
└── 03-tasks/                    # 작업 및 결과
    ├── sprint-001/
    │   ├── task-001-infra.md           # 인프라 작업
    │   ├── task-001-infra-result.md    # 인프라 결과
    │   ├── task-002-backend.md         # 백엔드 작업
    │   ├── task-002-backend-result.md  # 백엔드 결과
    │   └── ...
    └── sprint-NNN/
```

---

## 🚀 CAPA 프로젝트 적용 예시

### 현재 CAPA 개발 단계에 맞춘 첫 번째 스프린트 예시

| 작업 번호 | 작업명 | 담당 역할 | 의존성 |
|----------|--------|----------|--------|
| task-001 | Kinesis 스트림 + Firehose 설정 | DevOps/Data Engineer | - |
| task-002 | S3 파티셔닝 전략 구현 | Data Engineer | task-001 |
| task-003 | Glue 테이블 스키마 정의 | Data Engineer | task-002 |
| task-004 | Airflow DAG 개발 | Data Engineer | task-003 |
| task-005 | Athena 쿼리 최적화 | Data Engineer | task-003 |
| task-006 | Text-to-SQL API 개발 | Backend/ML Engineer | task-005 |

---

## 📌 사용 방법

### Step 1: 새 스프린트 시작

```bash
# 새 스프린트 디렉토리 생성
mkdir -p docs/vibe-coding/02-plans/sprint-001
mkdir -p docs/vibe-coding/03-tasks/sprint-001
```

### Step 2: 계획서 작성 (3개 페르소나 활용)

1. `01-personas/planner/conservative.md` 프롬프트로 계획서 초안 A 생성
2. `01-personas/planner/progressive.md` 프롬프트로 계획서 초안 B 생성
3. `01-personas/planner/moderate.md` 프롬프트로 계획서 초안 C 생성
4. 세 초안을 병합하여 `plan-draft.md` 생성

### Step 3: 검증

1. `01-personas/validator/critic.md` 프롬프트로 `plan-draft.md` 검증
2. `validation.md` 생성

### Step 4: 역할별 고도화

1. `01-personas/developers/base-developer.md` + 계획서 → 역할 식별
2. 필요한 역할별 개발자 프롬프트로 계획서 피드백
3. `plan-final.md` 완성

### Step 5: 아키텍처 설계

1. `plan-final.md` 기반 아키텍처 설계
2. `architecture.md` 생성 (ASCII + Mermaid)

### Step 6: 작업 분할 및 실행

1. `task-NNN-역할.md` 파일 생성
2. Copilot/LLM에 작업.md 제공하여 실행
3. 결과를 `task-NNN-역할-result.md`에 저장
4. 불만족 시 작업.md 수정 후 재실행
5. 만족 시 다음 작업으로 진행

---

## ⚡ 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **MD 파일 = 단일 진실의 원천** | 모든 계획, 검증, 작업은 MD 파일로 관리 |
| **페르소나 분리** | 역할별로 다른 관점의 피드백 확보 |
| **점진적 고도화** | 반복을 통해 계획서와 프롬프트 품질 향상 |
| **결과 추적** | 모든 실행 결과를 MD로 기록하여 히스토리 관리 |
| **만족할 때까지 반복** | 결과가 만족스러울 때까지 작업.md 수정 |

---

## 🔗 관련 문서

- [프로젝트 컨셉](../t1/project_concept_v3.md)
- [시스템 아키텍처](../t1/architecture.md)
- [글로벌 페르소나 구조](../t1/persona/persona_global.md)
