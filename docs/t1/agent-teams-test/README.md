# Agent Teams 실습 (Starter Level)

## 목표
Claude Code의 Agent Teams 기능을 간단하게 테스트하고 팀 에이전트 동작 방식 이해

## 실습 환경
- **브랜치**: `feat/t1/agent-teams-test`
- **환경 변수**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- **모델**: Haiku (haiku-4-5-20251001)
- **레벨**: Starter

## 진행 상황

### ✅ 완료
- [x] 테스트 브랜치 생성 (`feat/t1/agent-teams-test`)
- [x] 테스트 폴더 생성 (`docs/t1/agent-teams-test/`)
- [x] 환경 변수 설정 확인 (`$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)
- [x] .gitignore 정리 (bkit 로컬 파일 제외)
- [x] settings.json 추가 (Permissions, Hooks 설정)

### ⏳ 대기 중
- [ ] VSCode Claude Code 재시작 (환경 변수 적용)
- [ ] `/pdca team agent-teams-test` 실행
- [ ] Agent Teams 동작 확인 및 팀 에이전트 테스트

## 다음 단계

1. **VSCode 재시작**
   - Claude Code 프로세스 종료
   - VSCode 완전히 닫기
   - 다시 열기

2. **Agent Teams 실습 시작**
   ```
   /pdca team agent-teams-test
   ```

3. **테스트 시나리오** (예상)
   - 팀 에이전트 활성화 확인
   - PDCA 팀 모드 동작 관찰
   - 병렬 에이전트 실행 테스트

## 메모
- 환경 변수는 Claude 프로세스 시작 시에만 적용되므로 재시작 필수
- bkit Agent Teams: Dynamic(최대 3명), Enterprise(최대 5명)
- 현재 Haiku 모델 사용 (빠른 테스트용)

---
**마지막 업데이트**: 2026-03-09
**세션**: agent-teams-test (테스트 실습)