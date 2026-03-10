# Agent Teams Test Planning Document

> **Summary**: Agent Teams 기능을 Dynamic 레벨(3인 팀)으로 테스트하여 팀 에이전트 동작 방식을 검증한다.
>
> **Project**: CAPA (Cloud-native AI Pipeline for Ad-logs)
> **Version**: 1.0
> **Author**: CTO Lead (cto-lead)
> **Date**: 2026-03-09
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | Agent Teams 기능의 동작 방식과 팀 협업 패턴이 아직 검증되지 않아 실무 적용 가능성을 판단할 수 없다 |
| **Solution** | Dynamic 레벨 3인 팀(developer, frontend, qa)을 구성하여 PDCA 전 주기를 실습 테스트한다 |
| **Function/UX Effect** | 팀 모드 활성화, 역할 기반 작업 분배, PDCA 단계별 자동 전환이 정상 동작함을 확인한다 |
| **Core Value** | Agent Teams 기반 병렬 개발 워크플로우를 확립하고 실무 프로젝트에 적용할 수 있는 기반을 마련한다 |

---

## 1. Overview

### 1.1 Purpose

Claude Code Agent Teams 기능(`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)이 CAPA 프로젝트에서 정상적으로 동작하는지 검증한다. CTO Lead가 오케스트레이터로서 3명의 팀원 에이전트를 지휘하는 패턴을 테스트하고, PDCA 각 단계에서의 협업 흐름을 확인한다.

### 1.2 Background

- Agent Teams는 Claude Code의 실험적 기능으로, 여러 에이전트가 역할을 나누어 병렬로 작업할 수 있다
- CAPA 프로젝트는 다수의 서비스(log-generator, airflow-dags, vanna-api 등)를 포함하여 병렬 개발의 이점이 크다
- 팀 모드의 실제 동작 방식, 한계, 활용 패턴을 파악하기 위해 테스트가 필요하다

### 1.3 Related Documents

- bkit PDCA Skill 문서: `.claude/plugins/cache/bkit-marketplace/bkit/1.6.1/skills/pdca/SKILL.md`
- 프로젝트 규칙: `.claude/CLAUDE.md`

---

## 2. Scope

### 2.1 In Scope

- [x] Dynamic 레벨 팀 구성 전략 수립 (3인 팀: developer, frontend, qa)
- [x] 각 팀원 역할 및 PDCA 단계별 책임 정의
- [x] PDCA Plan 문서 작성 (본 문서)
- [ ] 팀 모드 활성화 및 팀원 에이전트 생성 테스트
- [ ] PDCA 단계별 오케스트레이션 패턴 테스트 (Leader, Swarm, Council)
- [ ] 팀원 간 메시지 교환 (write, broadcast, readMailbox) 테스트
- [ ] Quality Gate 검증 (90% Match Rate 기준)

### 2.2 Out of Scope

- Enterprise 레벨(5인 팀) 테스트
- 실제 프로덕션 코드 구현
- PM Agent Team (`/pdca pm`) 테스트
- Background Agent 및 `/loop` 모니터링 테스트

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Agent Teams 환경변수 설정 후 팀 모드가 정상 활성화된다 | High | Pending |
| FR-02 | Dynamic 레벨에서 3명(developer, frontend, qa)의 팀원이 생성된다 | High | Pending |
| FR-03 | CTO Lead가 각 팀원에게 작업을 분배할 수 있다 | High | Pending |
| FR-04 | PDCA 단계별 오케스트레이션 패턴이 올바르게 적용된다 | Medium | Pending |
| FR-05 | 팀원 간 메시지 교환이 정상 동작한다 | Medium | Pending |
| FR-06 | `/pdca team status` 명령으로 팀 상태를 조회할 수 있다 | Medium | Pending |
| FR-07 | `/pdca team cleanup` 명령으로 팀 세션을 종료할 수 있다 | Low | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| 안정성 | 팀 세션이 에러 없이 시작/종료된다 | 수동 테스트 |
| 응답성 | 팀원 에이전트가 작업 할당 후 응답한다 | 수동 확인 |
| 재현성 | 동일 구성으로 반복 테스트 시 동일 결과가 나온다 | 2회 반복 테스트 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 팀 모드 활성화 및 3명 팀원 생성 확인
- [ ] 최소 1개 PDCA 단계에서 팀원 협업 동작 확인
- [ ] 팀 상태 조회 및 세션 종료 정상 동작 확인
- [ ] 테스트 결과 문서화 완료

### 4.2 Quality Criteria

- [ ] 모든 FR 항목 테스트 완료
- [ ] 발견된 이슈 문서화
- [ ] 실무 적용 가이드라인 도출

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Agent Teams가 실험적 기능이라 예상치 못한 에러 발생 | Medium | High | 에러 로그를 기록하고 우회 방안 문서화 |
| 팀원 에이전트의 응답 지연 또는 무응답 | Medium | Medium | timeout 설정 확인, 단일 세션 모드로 폴백 |
| 환경변수 미설정으로 팀 모드 비활성화 | Low | Low | 사전 환경변수 확인 체크리스트 작성 |
| CC 버전 호환성 이슈 (v2.1.71 미만) | High | Low | CC 버전 확인 후 진행 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| **Starter** | 단순 구조, 팀 모드 불가 | 정적 사이트, 포트폴리오 | - |
| **Dynamic** | 3명 팀원, CTO Lead 오케스트레이션 | 웹앱, SaaS MVP, 풀스택 앱 | **Selected** |
| **Enterprise** | 5명 팀원, 전체 아키텍처 검증 | 대규모 시스템 | - |

### 6.2 Team Architecture (Dynamic Level)

```
CTO Lead (claude-opus-4-6, Orchestrator)
├── developer (bkend-expert)
│   └── 담당: Do(백엔드 구현), Act(Gap 수정)
├── frontend (frontend-architect)
│   └── 담당: Do(프론트엔드 구현), Design(UI 아키텍처 의견)
└── qa (qa-strategist + gap-detector)
    └── 담당: Check(Gap 분석, Match Rate 산출)
```

### 6.3 Orchestration Patterns per PDCA Phase

| PDCA Phase | Pattern | Description |
|------------|---------|-------------|
| Plan | Leader | CTO Lead가 직접 Plan 문서 작성 및 방향 설정 |
| Design | Leader | CTO Lead가 설계 결정, 팀원에게 리뷰 요청 |
| Do | Swarm | developer + frontend가 병렬로 구현 작업 수행 |
| Check | Council | qa가 다각도 검증, developer/frontend가 자체 검증 보고 |
| Act | Leader | CTO Lead가 Gap 우선순위 판단 후 수정 작업 배분 |

### 6.4 Communication Protocol

| Method | Usage | Example |
|--------|-------|---------|
| `write` | 1:1 메시지 전송 | CTO -> developer: "API 엔드포인트 구현 시작" |
| `broadcast` | 전체 공지 | "Design 단계 완료, Do 단계로 전환합니다" |
| `readMailbox` | 수신 메시지 확인 | 팀원의 완료 보고 확인 |
| `approvePlan` | Plan 승인 | 팀원이 제출한 Plan 승인 |
| `rejectPlan` | Plan 반려 | 수정 필요 시 사유와 함께 반려 |

---

## 7. Convention Prerequisites

### 7.1 Existing Project Conventions

- [x] `CLAUDE.md` has coding conventions section
- [ ] `docs/01-plan/conventions.md` exists
- [ ] ESLint configuration
- [ ] Prettier configuration
- [ ] TypeScript configuration

### 7.2 Environment Requirements

| Variable | Purpose | Required Value |
|----------|---------|---------------|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Agent Teams 활성화 | `1` |

### 7.3 CC Version Requirement

- Recommended: CC v2.1.71+ (stdin freeze fix, background agent recovery)
- Minimum: CC v2.1.69+ (Agent Teams 기본 지원)

---

## 8. Test Plan

### 8.1 Test Scenarios

| # | Scenario | Expected Result | Priority |
|---|----------|-----------------|----------|
| T-01 | `/pdca team agent-teams-test` 실행 | 팀 모드 시작, 3명 팀원 표시 | High |
| T-02 | `/pdca team status` 실행 | 팀 상태 정보 출력 | High |
| T-03 | CTO -> developer `write` 메시지 전송 | 메시지 전달 확인 | Medium |
| T-04 | `broadcast` 전체 메시지 전송 | 전체 팀원 수신 확인 | Medium |
| T-05 | PDCA Do 단계 Swarm 패턴 테스트 | developer + frontend 병렬 작업 | Medium |
| T-06 | PDCA Check 단계 Council 패턴 테스트 | qa의 Gap 분석 결과 수신 | Medium |
| T-07 | `/pdca team cleanup` 실행 | 팀 세션 종료, 단일 모드 복귀 | Low |

---

## 9. Next Steps

1. [ ] 본 Plan 문서 리뷰 및 승인
2. [ ] Design 문서 작성 (`agent-teams-test.design.md`)
3. [ ] 팀 모드 활성화 및 테스트 실행 (Do 단계)
4. [ ] Gap 분석 및 결과 문서화 (Check 단계)
5. [ ] 테스트 결과 리포트 작성 (Report 단계)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-09 | Initial draft - 팀 구성 전략 및 역할 정의 포함 | CTO Lead |
