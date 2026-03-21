---
name: pr
description: 현재 브랜치의 커밋을 분석해 CAPA 컨벤션에 맞는 한국어 PR을 GitHub에 자동으로 생성합니다.
triggers: ["PR 만들어줘", "pr 생성해줘", "풀리퀘 만들어", "pr 올려줘", "pull request 만들어", "PR 올려줘", "pr해줘"]
---

## 역할

현재 브랜치와 베이스 브랜치 간의 커밋/diff를 분석해 CAPA 프로젝트 컨벤션에 맞는
**한국어 Pull Request**를 GitHub에 자동 생성합니다.

## 실행 절차

아래 순서를 **반드시 순서대로** 실행합니다.

### 1단계: 현재 상태 파악 (병렬 실행)

다음 명령을 동시에 실행합니다.

```bash
git status
git branch -vv
git log --oneline -10
```

### 2단계: 베이스 브랜치 결정

브랜치 이름 패턴으로 베이스 브랜치를 결정합니다.

| 현재 브랜치 패턴 | 베이스 브랜치 |
|----------------|-------------|
| `feat/*`, `fix/*`, `refactor/*` | `main` |
| `hotfix/*` | `main` |
| 기타 | `main` |

> CAPA 프로젝트는 develop 브랜치 없이 `feat/담당자/기능명` → `main` 직행 전략을 사용합니다.

### 3단계: 변경 내용 분석

```bash
git log main...HEAD --oneline
git diff main...HEAD --stat
```

커밋 목록과 변경 파일 통계를 파악합니다.

### 4단계: PR 제목 결정

커밋 메시지 패턴과 변경 내용을 분석해 PR 제목을 결정합니다.

#### 제목 규칙

- **형식**: `[<type>] <subject>`
- **한국어**로 작성
- 70자 이내
- 여러 커밋이 있을 경우 핵심 변경을 대표하는 제목 하나 선택

#### type 결정 (커밋 type 중 가장 비중 높은 것 선택)

| 커밋 type 비중 | PR 제목 type |
|--------------|------------|
| `feat` 위주 | `[feat]` |
| `fix` 위주 | `[fix]` |
| `docs` 위주 | `[docs]` |
| `refactor` 위주 | `[refactor]` |
| `test` 위주 | `[test]` |
| `chore` 위주 | `[chore]` |
| 혼합 | `[feat]` 또는 가장 핵심 type |

**예시:**
```
[feat] Text-to-SQL Phase 2 RAG 고도화 구현
[fix] vanna-api Reranker 미주입 및 SQL 해시 중복 방지 수정
[refactor] FR-17 Redash query_id DynamoDB 캐싱 기능 제거
[docs] Phase 2 Gap 분석 및 테스트 결과 문서 업데이트
```

### 5단계: PR 본문 작성

아래 형식으로 PR 본문을 작성합니다.

```markdown
## 개요

<변경의 목적과 배경을 2~4문장으로 설명. 왜 이 변경이 필요한가?>

## 주요 변경 사항

- <변경 항목 1>
- <변경 항목 2>
- <변경 항목 3>
...

## 관련 커밋

<git log main...HEAD --oneline 결과 목록>

## 테스트

- [ ] 단위 테스트 통과 확인
- [ ] 로컬 도커 환경에서 동작 확인
- [ ] 관련 문서 업데이트

## 참고

<관련 문서, 이슈, 설계서 경로 등 (있는 경우)>

🤖 Generated with Claude Sonnet 4.6
```

### 6단계: 원격 브랜치 푸시 (필요한 경우)

로컬 브랜치가 원격에 없거나 뒤처진 경우에만 실행합니다.

```bash
git push -u origin <현재 브랜치명>
```

이미 업스트림이 설정되어 있고 최신이면 생략합니다.

### 7단계: PR 생성

`gh` CLI로 PR을 생성합니다.

```bash
gh pr create \
  --base main \
  --title "<결정된 PR 제목>" \
  --body "$(cat <<'EOF'
<작성된 PR 본문>
EOF
)"
```

### 8단계: 결과 보고

PR 생성 완료 후 아래 형식으로 보고합니다.

```
PR 생성 완료
- PR URL: <url>
- 제목: <제목>
- 베이스: <base> ← <현재 브랜치>
- 포함 커밋: <n>개
```

## 주의 사항

- **민감 파일 미포함 확인**: `.env`, `*.key`, `credentials*` 파일이 커밋에 포함된 경우 PR 생성을 중단하고 사용자에게 알립니다.
- **main 브랜치 직접 PR 금지**: 현재 브랜치가 `main`이면 PR 생성을 중단합니다.
- **force push 금지**: 원격에 이미 푸시된 커밋은 수정하지 않습니다.
- `gh` CLI가 설치되어 있지 않거나 인증이 안 된 경우 사용자에게 안내합니다.
