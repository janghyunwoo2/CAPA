# Agent Teams Test Design Document

> **Summary**: Dynamic 레벨 3인 Agent Teams의 아키텍처와 PDCA 전 주기 동작 방식을 상세 설계한다.
>
> **Project**: CAPA (Cloud-native AI Pipeline for Ad-logs)
> **Version**: 1.0
> **Author**: Frontend Architect (frontend-architect)
> **Date**: 2026-03-09
> **Status**: Draft
> **Related Plan**: `docs/01-plan/features/agent-teams-test.plan.md`

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | Agent Teams의 역할 분담 구조와 PDCA 단계별 협업 프로토콜이 명확하지 않으면 팀 에이전트 간 충돌, 중복 작업, 단계 전환 실패가 발생한다 |
| **Solution** | CTO Lead-Orchestrator 구조 아래 developer/frontend/qa 3인이 명확한 책임 경계와 메시지 프로토콜(write/broadcast/readMailbox)로 협업하는 아키텍처를 설계한다 |
| **Function/UX Effect** | Plan→Design→Do→Check→Act 각 단계에서 오케스트레이션 패턴(Leader/Swarm/Council)이 자동 전환되고, 각 에이전트가 역할 범위 안에서 독립적으로 작업하여 병렬 효율을 극대화한다 |
| **Core Value** | 검증된 Agent Teams 협업 아키텍처를 CAPA 실무 개발에 적용하여 다수 서비스(log-generator, airflow-dags, vanna-api)의 병렬 개발 속도를 높이고 Quality Gate 90% 기준을 달성한다 |

---

## 1. 상세 아키텍처

### 1.1 팀 구조 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CTO Lead (Orchestrator)                           │
│                 Model: claude-opus-4-6                               │
│           Role: 전체 PDCA 흐름 조율, Plan/Design 직접 작성           │
│                 Quality Gate 최종 판단, Act 방향 결정                │
└───────────────────┬────────────────────────────────────────────────-┘
                    │  Agent Teams Protocol
         ┌──────────┼──────────┐
         │          │          │
         ▼          ▼          ▼
┌─────────────┐ ┌───────────────────┐ ┌──────────────────────────┐
│  developer  │ │     frontend      │ │           qa             │
│(bkend-expert│ │(frontend-architect│ │  (qa-strategist +        │
│    )        │ │    )              │ │   gap-detector)          │
├─────────────┤ ├───────────────────┤ ├──────────────────────────┤
│ PDCA Phase  │ │   PDCA Phase      │ │     PDCA Phase           │
│ Do: 백엔드  │ │ Design: UI아키텍처│ │ Check: Gap 분석          │
│  구현 주도  │ │ Do: 프론트 구현   │ │   Match Rate 산출        │
│ Act: Gap    │ │ Act: UI Gap 수정  │ │ Act: 검증 보고서 제출    │
│  백엔드 수정│ │                   │ │                          │
└─────────────┘ └───────────────────┘ └──────────────────────────┘
```

### 1.2 메시지 프로토콜

Agent Teams는 3가지 메시지 메서드로 팀원 간 통신한다.

| 메서드 | 방향 | 용도 | 예시 |
|--------|------|------|------|
| `write(to, message)` | 1:1 지정 전송 | 특정 팀원에게 작업 지시 또는 질의 | `write("developer", "POST /api/logs 엔드포인트 구현 시작")` |
| `broadcast(message)` | 전체 공지 | 단계 전환 알림, 전체 공유 정보 | `broadcast("Design 단계 완료. Do 단계로 전환합니다")` |
| `readMailbox()` | 수신 확인 | 팀원의 완료 보고 및 중간 결과 수신 | CTO Lead가 주기적으로 호출하여 팀원 응답 수집 |
| `approvePlan(agentId)` | 승인 | 팀원이 제출한 작업 계획 승인 | `approvePlan("developer")` |
| `rejectPlan(agentId, reason)` | 반려 | 수정 필요 시 사유 전달 | `rejectPlan("frontend", "반응형 대응 누락")` |

#### 메시지 페이로드 구조

```json
{
  "from": "cto-lead",
  "to": "developer",
  "phase": "Do",
  "priority": "High",
  "task": "POST /api/logs 엔드포인트 구현",
  "acceptance_criteria": [
    "타입 힌트 필수",
    "try-except 에러 핸들링 포함",
    "logging 모듈 사용"
  ],
  "deadline": "Do 단계 종료 전"
}
```

### 1.3 팀원 간 상호작용 시퀀스 (전체 개요)

```
CTO Lead          developer         frontend          qa
    │                 │                 │               │
    │──broadcast()────▶─────────────────▶───────────────▶
    │  "Plan 완료, Design 시작"
    │                 │                 │               │
    │──write()────────▶                 │               │
    │  "API 구조 리뷰 요청"             │               │
    │                 │                 │               │
    │──write()────────────────────────▶ │               │
    │  "UI 컴포넌트 설계 리뷰 요청"     │               │
    │                 │                 │               │
    │◀───readMailbox()────────────────── │               │
    │  (developer, frontend 리뷰 결과 수집)             │
    │                 │                 │               │
    │──broadcast()────▶─────────────────▶───────────────▶
    │  "Design 완료, Do 단계 시작 (Swarm)"
    │                 │                 │               │
    │  (병렬 작업)    │◀────write()─────│               │
    │                 │  "API 인터페이스 공유"          │
    │                 │                 │               │
    │◀───readMailbox()─────────────────────────────────▶│
    │  (developer, frontend 완료 보고 수집)             │
    │                 │                 │               │
    │──write()────────────────────────────────────────▶ │
    │  "Check 단계 Gap 분석 시작"                       │
    │                 │                 │               │
    │◀───readMailbox()──────────────────────────────────│
    │  (qa Gap 분석 결과 수신)                          │
    │                 │                 │               │
    │──broadcast()────▶─────────────────▶───────────────▶
    │  "Act 단계: Gap 수정 작업 배분"
```

---

## 2. 테스트 시나리오별 상세 설계

### T-01: 팀 모드 활성화 (`/pdca team agent-teams-test`)

**목적**: Agent Teams 환경이 정상적으로 초기화되는지 검증

**사전 조건**:
- 환경변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정
- CC v2.1.71 이상 설치

**실행 흐름**:
```
1. 사용자: /pdca team agent-teams-test 입력
2. CTO Lead: docs/01-plan/features/agent-teams-test.plan.md 로드
3. CTO Lead: Dynamic 레벨 확인 → 팀 구성 (3인)
4. 시스템: developer, frontend, qa 에이전트 초기화
5. CTO Lead: broadcast("팀 초기화 완료. 팀원: developer, frontend, qa")
6. 출력: 팀 구성표 및 각 역할 요약
```

**검증 기준**:
- [ ] 3명 팀원 목록이 표시된다
- [ ] 각 팀원의 역할이 올바르게 매핑된다
- [ ] 에러 없이 팀 세션이 시작된다

**예상 출력**:
```
Agent Teams 초기화 완료
- CTO Lead (Orchestrator): claude-opus-4-6
- developer (bkend-expert): 백엔드 구현 담당
- frontend (frontend-architect): UI 아키텍처 및 구현 담당
- qa (qa-strategist): Gap 분석 및 품질 검증 담당

현재 Phase: Plan → Design 단계로 이동 준비 중
```

---

### T-02: 팀 상태 조회 (`/pdca team status`)

**목적**: 팀 세션 활성 상태와 각 팀원의 현재 작업 상태 조회 검증

**실행 흐름**:
```
1. 사용자: /pdca team status 입력
2. CTO Lead: 각 팀원 에이전트 상태 쿼리
3. 출력: 팀 상태 테이블 렌더링
```

**검증 기준**:
- [ ] 활성 팀원 수 표시 (3/3)
- [ ] 현재 PDCA 단계 표시
- [ ] 각 팀원의 마지막 활동 시간 표시

**예상 출력**:
```
┌────────────────────────────────────────────────┐
│ Agent Teams Status - agent-teams-test          │
├─────────────┬────────────────┬─────────────────┤
│ Agent       │ Status         │ Current Task    │
├─────────────┼────────────────┼─────────────────┤
│ developer   │ Active         │ Standby         │
│ frontend    │ Active         │ Standby         │
│ qa          │ Active         │ Standby         │
├─────────────┼────────────────┼─────────────────┤
│ Phase       │ Design         │                 │
│ Session     │ Active         │ 00:05:32 elapsed│
└─────────────┴────────────────┴─────────────────┘
```

---

### T-03: 1:1 메시지 전송 (`write`)

**목적**: CTO Lead → developer 간 1:1 메시지 전달 및 수신 확인

**실행 흐름**:
```
1. CTO Lead: write("developer", "CAPA log-generator 서비스의 POST /api/logs 엔드포인트 구현 계획서를 제출하라")
2. developer: 메시지 수신 확인 (readMailbox)
3. developer: 계획서 작성 후 write("cto-lead", "계획서 제출: ...")
4. CTO Lead: readMailbox() 호출로 developer 응답 수신
```

**검증 기준**:
- [ ] write() 호출 후 대상 에이전트가 메시지를 수신한다
- [ ] 수신 에이전트가 readMailbox()로 메시지를 확인한다
- [ ] 응답 메시지가 발신자에게 전달된다

**테스트 메시지 예시**:
```
[CTO → developer]
"log-generator 서비스에서 사용하는 Kinesis PUT 함수에 대해
try-except ClientError 처리가 누락되지 않았는지 확인하고 보고하라.
CLAUDE.md의 에러 핸들링 규칙을 참조할 것."
```

---

### T-04: 전체 공지 (`broadcast`)

**목적**: CTO Lead가 전체 팀원에게 단계 전환 공지 전송 및 수신 확인

**실행 흐름**:
```
1. CTO Lead: broadcast("Design 단계 완료. Do 단계로 전환합니다. developer와 frontend는 Swarm 패턴으로 병렬 작업을 시작하라.")
2. developer: readMailbox() → 메시지 수신 확인
3. frontend: readMailbox() → 메시지 수신 확인
4. qa: readMailbox() → 메시지 수신 확인 (대기 상태 유지)
```

**검증 기준**:
- [ ] broadcast() 1회 호출로 3명 전원이 메시지를 수신한다
- [ ] 각 팀원이 역할에 맞게 대응한다 (developer/frontend는 작업 시작, qa는 대기)
- [ ] 중복 수신 없이 1회 전달된다

---

### T-05: Swarm 패턴 테스트 (Do 단계 병렬 작업)

**목적**: developer와 frontend가 Do 단계에서 독립적으로 병렬 작업을 수행하는지 검증

**설계 구조**:
```
CTO Lead
  ├── write("developer", "services/log-generator/kinesis_producer.py 에러 핸들링 검토")
  └── write("frontend", "docs/02-design/features/agent-teams-test.design.md UI 섹션 리뷰")

[병렬 실행]
developer:                          frontend:
  1. services/ 디렉토리 탐색           1. design 문서 읽기
  2. kinesis_producer.py 읽기          2. UI 아키텍처 섹션 확인
  3. ClientError 누락 여부 확인        3. 컴포넌트 구조 검토
  4. 결과 write("cto-lead", ...)       4. 결과 write("cto-lead", ...)

CTO Lead: readMailbox() → 양쪽 결과 수집
```

**검증 기준**:
- [ ] developer와 frontend가 동시에(또는 순차적으로) 작업을 수행한다
- [ ] 각자의 작업이 서로 간섭하지 않는다
- [ ] CTO Lead가 양쪽 결과를 모두 수집한다

**병렬성 확인 지표**:
- 두 에이전트의 완료 보고가 readMailbox에서 함께 수신될 경우 병렬 동작 확인
- 순차 동작이더라도 역할 분리가 명확하면 합격

---

### T-06: Council 패턴 테스트 (Check 단계 Gap 분석)

**목적**: qa 에이전트가 Check 단계에서 Gap 분석을 수행하고 Match Rate를 산출하는지 검증

**설계 구조**:
```
CTO Lead: write("qa", "Do 단계 결과물을 검토하고 Gap 분석 보고서를 제출하라")

qa (Council 모드):
  1. Plan 문서 로드 (docs/01-plan/features/agent-teams-test.plan.md)
  2. Do 단계 결과물 수집
  3. FR-01~FR-07 각 항목 달성 여부 평가
  4. Match Rate 산출: (달성 항목 수 / 전체 항목 수) * 100
  5. Gap 목록 작성 (미달 항목)
  6. write("cto-lead", Gap 분석 보고서)

CTO Lead: readMailbox() → 분석 결과 수신
          Match Rate >= 90% → Act(경미한 수정)
          Match Rate < 90%  → Do 단계 재실행 검토
```

**Gap 분석 보고서 템플릿**:
```markdown
## Gap 분석 결과 (qa-strategist)

### Match Rate
- 평가 항목: 7개 (FR-01 ~ FR-07)
- 달성 항목: N개
- Match Rate: N/7 * 100 = N%

### 달성 항목
- [x] FR-01: 팀 모드 활성화 확인
- [x] FR-02: 3명 팀원 생성 확인
...

### Gap 항목 (미달)
- [ ] FR-05: 팀원 간 메시지 교환 (실제 전달 지연 관찰됨)

### 권고사항
- FR-05: write() 호출 후 readMailbox() 폴링 간격을 조정할 것
```

**검증 기준**:
- [ ] qa가 모든 FR 항목을 평가한다
- [ ] Match Rate가 수치로 산출된다
- [ ] Gap 항목이 구체적으로 기술된다
- [ ] 권고사항이 실행 가능한 수준으로 작성된다

---

### T-07: 팀 세션 종료 (`/pdca team cleanup`)

**목적**: 팀 세션 종료 후 단일 세션 모드로 복귀하는지 검증

**실행 흐름**:
```
1. 사용자: /pdca team cleanup 입력
2. CTO Lead: broadcast("팀 세션을 종료합니다. 수고하셨습니다.")
3. 시스템: developer, frontend, qa 에이전트 해제
4. 출력: 세션 종료 확인 메시지
5. 이후: 단일 Claude 세션 모드로 복귀
```

**검증 기준**:
- [ ] 에러 없이 팀 세션이 종료된다
- [ ] 종료 후 일반 Claude 세션으로 복귀한다
- [ ] 세션 중 생성된 파일이 보존된다

---

## 3. 각 팀원 역할별 작업 정의

### 3.1 developer (bkend-expert)

**역할 정의**: CAPA 백엔드 서비스의 코드 품질 검토 및 규칙 준수 확인

| PDCA 단계 | 작업 | 산출물 |
|-----------|------|--------|
| Design | API 구조 리뷰 의견 제출 (요청 시) | write("cto-lead", 리뷰 결과) |
| Do | services/ 디렉토리 Python 코드 검토 | 검토 보고서 (메시지) |
| Do | CAPA 코딩 규칙(타입 힌트, 에러 핸들링, 로깅) 위반 탐지 | 위반 목록 |
| Act | 식별된 Gap의 백엔드 코드 수정 지침 제공 | 수정 권고 메시지 |

**도구 권한**: Read, Glob, Grep (코드 탐색 및 읽기 전용)

**작업 경계**:
- 허용: services/ 내 .py 파일 읽기 및 분석
- 불허: 파일 직접 수정 (Act 단계 수정은 CTO Lead 승인 후)
- 불허: frontend, qa 작업 영역 개입

**세부 작업 체크리스트** (Do 단계):
```markdown
- [ ] services/ 디렉토리 탐색 (Glob)
- [ ] .py 파일 목록 수집
- [ ] 각 파일별 타입 힌트 확인 (Grep: "def.*\(.*\):" 패턴)
- [ ] async 함수에 try-except 존재 여부 확인
- [ ] print() 사용 여부 확인 (Grep: "print(")
- [ ] Pydantic BaseModel 사용 여부 확인
- [ ] 결과 집계 후 CTO Lead에게 보고
```

---

### 3.2 frontend (frontend-architect)

**역할 정의**: UI/UX 아키텍처 설계 검토 및 프론트엔드 관련 문서 리뷰

| PDCA 단계 | 작업 | 산출물 |
|-----------|------|--------|
| Design | 컴포넌트 구조, 상태 관리 패턴 리뷰 | write("cto-lead", 설계 리뷰) |
| Do | Design 문서의 UI 섹션 검토 | UI 일관성 검토 보고서 |
| Do | Phase 3 Mockup / Phase 5 Design System 기준 검토 | 컴포넌트 매핑 검토 |
| Act | UI Gap 수정 권고 (접근성, 타입 안전성 기준) | 수정 권고 메시지 |

**도구 권한**: Read, Glob, Grep

**작업 경계**:
- 허용: docs/, mockup/ 내 UI 관련 문서 읽기 및 분석
- 허용: 컴포넌트 구조 및 TypeScript 타입 검토 의견 제시
- 불허: Python 백엔드 코드 직접 검토 (developer 영역)
- 불허: 인프라 Terraform 코드 검토

**설계 검토 기준**:
```markdown
컴포넌트 설계 원칙:
1. 단일 책임 원칙 - 각 컴포넌트의 책임이 명확한가
2. Props 인터페이스 - TypeScript 타입 정의가 완전한가
3. 접근성 - WCAG 2.1 AA 기준 충족 여부
4. 상태 관리 - Server/Client 상태 분리가 적절한가
5. 성능 - 불필요한 리렌더링 방지 패턴 적용 여부
```

---

### 3.3 qa (qa-strategist + gap-detector)

**역할 정의**: PDCA Check 단계의 Gap 분석 수행, Match Rate 산출, 품질 보고서 작성

| PDCA 단계 | 작업 | 산출물 |
|-----------|------|--------|
| Check | Plan 문서 대비 Do 단계 결과물 평가 | Gap 분석 보고서 |
| Check | FR-01~FR-07 각 항목 달성률 측정 | Match Rate (수치) |
| Check | 미달 항목(Gap) 목록화 및 원인 분석 | Gap 목록 + 원인 |
| Act | 수정 완료 항목 재검증 | 재검증 보고서 |

**도구 권한**: Read, Glob, Grep

**Gap 분석 방법론**:

```
Step 1: 기준선 설정
  - Plan 문서의 FR 항목 목록 추출
  - 각 항목의 완료 기준(Acceptance Criteria) 확인

Step 2: 증거 수집
  - Do 단계 결과물(파일, 메시지) 수집
  - 각 FR 항목에 대한 증거 파일 매핑

Step 3: 평가
  - 각 항목: 완료(✅) / 미완료(❌) / 부분완료(⚠️) 판정
  - 판정 근거 기록

Step 4: Match Rate 산출
  - Match Rate = (완료 항목 + 부분완료 * 0.5) / 전체 항목 * 100
  - 기준: >= 90% (Go), 70~89% (조건부 Go), < 70% (No-Go)

Step 5: 보고
  - write("cto-lead", 분석 결과)
```

**Quality Gate 기준**:
| Match Rate | 판정 | 다음 단계 |
|------------|------|-----------|
| >= 90% | Go | Act (경미한 수정) |
| 70% ~ 89% | 조건부 Go | Act (주요 수정) |
| < 70% | No-Go | Do 재실행 |

---

## 4. PDCA 단계별 상세 동작 흐름

### 4.1 Plan 단계 (Leader 패턴)

```
[Leader 패턴: CTO Lead 단독 수행]

CTO Lead
  │
  ├── docs/01-plan/features/agent-teams-test.plan.md 확인
  │
  ├── 팀 구성 결정
  │   ├── Dynamic 레벨: 3인 팀
  │   ├── developer: bkend-expert
  │   ├── frontend: frontend-architect
  │   └── qa: qa-strategist
  │
  ├── PDCA 단계별 책임 배정
  │
  └── broadcast("Plan 완료. Design 단계로 전환합니다.")
         │
         ▼
      [developer, frontend, qa 수신 대기]
```

**단계 출력물**: `docs/01-plan/features/agent-teams-test.plan.md` (기완성)

---

### 4.2 Design 단계 (Leader 패턴)

```
[Leader 패턴: CTO Lead 주도, 팀원 리뷰 참여]

CTO Lead
  │
  ├── Design 문서 초안 작성 (본 문서)
  │
  ├── write("developer", "API 구조 및 에러 핸들링 설계 리뷰 요청")
  │         │
  │         └── developer: readMailbox() → 읽기 → write("cto-lead", 리뷰 결과)
  │
  ├── write("frontend", "UI 아키텍처 및 컴포넌트 설계 리뷰 요청")
  │         │
  │         └── frontend: readMailbox() → 읽기 → write("cto-lead", 리뷰 결과)
  │
  ├── readMailbox() → 두 팀원의 리뷰 결과 수집
  │
  ├── Design 문서 최종 확정 (리뷰 반영)
  │
  └── broadcast("Design 완료. Do 단계 시작 (Swarm 패턴)")
```

**단계 출력물**: `docs/02-design/features/agent-teams-test.design.md` (본 문서)

---

### 4.3 Do 단계 (Swarm 패턴)

```
[Swarm 패턴: developer + frontend 병렬 작업]

CTO Lead
  ├── write("developer", "Do 작업: services/ Python 코드 규칙 준수 검토")
  └── write("frontend", "Do 작업: Design 문서 UI 섹션 검토 및 컴포넌트 설계 검토")

[병렬 실행]
developer                              frontend
  │                                      │
  ├── readMailbox()                       ├── readMailbox()
  ├── services/ Glob                     ├── docs/ Read
  ├── .py 파일 분석                      ├── UI 섹션 검토
  │   ├── 타입 힌트 확인                 ├── 컴포넌트 구조 평가
  │   ├── try-except 확인                ├── TypeScript 타입 검토
  │   └── print() 확인                  └── write("cto-lead", 결과)
  └── write("cto-lead", 결과)

CTO Lead
  ├── readMailbox() → developer 결과 수신
  ├── readMailbox() → frontend 결과 수신
  └── 결과 통합 후 qa에 전달 준비
```

**단계 출력물**: 팀원별 검토 보고서 (메시지 형태)

---

### 4.4 Check 단계 (Council 패턴)

```
[Council 패턴: qa 중심, developer/frontend 자체 검증 보고]

CTO Lead
  ├── write("qa", "Gap 분석 시작. FR-01~FR-07 기준으로 Do 결과물 평가하라")
  ├── write("developer", "자체 검증 보고서 제출: 작업 완료 항목 및 미완료 항목")
  └── write("frontend", "자체 검증 보고서 제출: 작업 완료 항목 및 미완료 항목")

[순차 수집]
qa
  ├── readMailbox()
  ├── Plan 문서 로드
  ├── FR-01~FR-07 평가
  ├── Match Rate 산출
  └── write("cto-lead", Gap 분석 보고서)

developer                              frontend
  └── write("cto-lead", 자체 보고)     └── write("cto-lead", 자체 보고)

CTO Lead
  ├── readMailbox() → qa 분석 수신
  ├── readMailbox() → developer 자체 보고 수신
  ├── readMailbox() → frontend 자체 보고 수신
  ├── Match Rate 확인
  │   ├── >= 90%: Act 진행
  │   └── < 90%: Do 재실행 결정
  └── broadcast("Check 완료. Match Rate: N%. Act 단계로 전환합니다.")
```

**단계 출력물**: Gap 분석 보고서 (qa 작성, 메시지 형태)

---

### 4.5 Act 단계 (Leader 패턴)

```
[Leader 패턴: CTO Lead 우선순위 결정, 팀원 수정 수행]

CTO Lead
  ├── Gap 목록 우선순위 정렬 (Critical > High > Medium > Low)
  ├── write("developer", "Gap #1 수정 지침: ...")  [Critical 항목]
  ├── write("frontend", "Gap #2 수정 지침: ...")   [High 항목]
  │
  │   [팀원 수정 작업]
  │   developer: 수정 수행 → write("cto-lead", "수정 완료")
  │   frontend:  수정 수행 → write("cto-lead", "수정 완료")
  │
  ├── readMailbox() → 수정 완료 보고 수집
  ├── write("qa", "수정 완료 항목 재검증 요청")
  │         │
  │         └── qa: 재검증 → write("cto-lead", "재검증 결과")
  │
  ├── readMailbox() → 재검증 결과 수신
  └── 최종 판정: 완료 또는 추가 반복
```

**단계 출력물**: 수정 완료 보고 및 재검증 결과

---

## 5. 검증 기준 및 성공 조건

### 5.1 정량적 기준

| 지표 | 목표값 | 측정 방법 |
|------|--------|-----------|
| Match Rate | >= 90% | qa Gap 분석 결과 |
| FR 달성률 | 7/7 (100%) | FR-01~FR-07 체크리스트 |
| 팀 세션 오류율 | 0건 | 에러 로그 확인 |
| 메시지 전달 성공률 | >= 95% | write/readMailbox 성공 횟수 |
| 테스트 완료 시나리오 | 7/7 | T-01~T-07 체크리스트 |

### 5.2 정성적 기준

| 항목 | 합격 기준 |
|------|-----------|
| 역할 분리 명확성 | developer/frontend/qa의 작업 영역이 중복되지 않는다 |
| 오케스트레이션 패턴 | Leader/Swarm/Council이 단계별로 올바르게 적용된다 |
| 메시지 프로토콜 | write, broadcast, readMailbox가 의도대로 동작한다 |
| 결과 재현성 | 동일 시나리오 2회 실행 시 동일 결과가 나온다 |
| 문서화 품질 | 테스트 결과가 다음 실무 적용을 위한 가이드로 활용 가능하다 |

### 5.3 Quality Gate

```
┌─────────────────────────────────────────────────────────────┐
│                    Quality Gate v1.0                        │
├────────────────────┬────────────────────────────────────────┤
│ Gate 1: 팀 초기화  │ 3명 팀원 정상 생성 (T-01 통과)        │
│ Gate 2: 통신 검증  │ write + broadcast 정상 동작 (T-03,T-04)│
│ Gate 3: 병렬 작업  │ Swarm 패턴 동작 확인 (T-05)           │
│ Gate 4: 품질 분석  │ Match Rate >= 90% (T-06)              │
│ Gate 5: 세션 종료  │ cleanup 정상 완료 (T-07)              │
├────────────────────┴────────────────────────────────────────┤
│ 최종 판정: Gate 1~5 모두 통과 시 Done                      │
│           Gate 미통과 시 해당 시나리오 재실행 후 재평가     │
└─────────────────────────────────────────────────────────────┘
```

### 5.4 실무 적용 가능성 판단 기준

테스트 완료 후 아래 항목을 기반으로 CAPA 실무 개발 적용 여부를 결정한다.

| 항목 | 적용 조건 |
|------|-----------|
| 병렬 작업 효과 | Swarm 패턴이 단일 세션 대비 체감 속도 향상이 있다 |
| 역할 전문화 효과 | 각 팀원이 역할에 특화된 결과물을 산출한다 |
| 안정성 | 세션 중 비정상 종료 없이 전체 PDCA 완료 가능하다 |
| 학습 비용 | 팀 모드 설정 및 명령이 5분 이내 이해 가능하다 |
| 추천 여부 | 위 4가지 조건 충족 시 CAPA 실무 적용 권장 |

---

## 6. 파일 구조 및 산출물 목록

```
docs/
├── 01-plan/
│   └── features/
│       └── agent-teams-test.plan.md          [완료]
├── 02-design/
│   └── features/
│       └── agent-teams-test.design.md        [본 문서 - 완료]
└── t1/
    └── agent-teams-test/
        └── README.md                          [진행 상황 추적]
```

**Do 단계 예상 산출물** (테스트 실행 후 생성):
```
docs/
└── t1/
    └── agent-teams-test/
        ├── do-results/
        │   ├── developer-report.md            [developer 검토 보고서]
        │   └── frontend-report.md             [frontend 검토 보고서]
        └── check-results/
            └── gap-analysis.md                [qa Gap 분석 보고서]
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-09 | Initial design - 팀 아키텍처, 시나리오별 상세 설계, PDCA 흐름도 포함 | frontend-architect |
