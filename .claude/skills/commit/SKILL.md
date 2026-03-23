---
name: commit
description: 변경된 파일을 분석해 CAPA 컨벤션에 맞는 한국어 커밋 메시지를 자동으로 작성하고 커밋합니다.
triggers: ["커밋해줘", "지금 커밋", "커밋 해줘", "커밋해", "commit now", "변경사항 커밋"]
---

## 역할

변경된 파일 목록과 diff를 분석해 CAPA 프로젝트 커밋 컨벤션에 맞는 **한국어 커밋 메시지**를 자동 생성하고 커밋합니다.

## 실행 절차

아래 순서를 **반드시 순서대로** 실행합니다.

### 1단계: 현재 상태 파악 (병렬 실행)

다음 세 명령을 동시에 실행합니다.

```bash
git status
git diff HEAD
git log --oneline -5
```

### 2단계: 파일 분석 → 커밋 메시지 결정

변경된 파일 경로와 내용을 보고 아래 규칙으로 type과 scope를 결정합니다.

#### type 결정 규칙

| 조건 | type |
|------|------|
| 새 기능 코드 추가 | `feat` |
| 버그 수정 | `fix` |
| `.md`, `docs/` 문서 수정 | `docs` |
| 리팩토링 (기능 변화 없음) | `refactor` |
| 테스트 파일 (`test_*.py`) | `test` |
| 설정/빌드/CI 파일 (`.json`, `.yaml`, `.tf`, `Dockerfile`, `.github/`) | `chore` |

#### scope 결정 규칙 (파일 경로 기준)

| 파일 경로 패턴 | scope |
|---------------|-------|
| `services/log-generator/` | `log-generator` |
| `services/airflow-dags/` | `airflow-dags` |
| `services/vanna-api/` | `vanna-api` |
| `services/data_pipeline_t2/` | `data-pipeline` |
| `services/report-generator/` | `report-generator` |
| `services/slack-bot/` | `slack-bot` |
| `infrastructure/terraform/` | `terraform` |
| `infrastructure/helm-values/` | `helm` |
| `docs/` | `docs` |
| `.github/` | `ci` |
| `.claude/` | `claude` |
| 여러 영역에 걸침 | 가장 핵심 영역 하나 선택 |

#### subject 작성 규칙

- **한국어**로 작성
- 변경의 핵심 내용을 동사로 시작 (추가, 수정, 제거, 개선, 설정)
- 50자 이내로 간결하게
- 파일명을 그대로 쓰지 말고 **무엇을 했는지** 기술

**예시:**
```
feat(log-generator): impression 이벤트에 device_type 필드 추가
fix(vanna-api): Athena 연결 타임아웃 에러 처리 누락 수정
docs(airflow-dags): DAG 스케줄 설정 주석 보완
chore(terraform): S3 버킷 태그 ManagedBy 항목 추가
refactor(data-pipeline): Glue Job 중복 로직 공통 함수로 분리
```

### 3단계: 스테이징 및 커밋 실행

**중요**: 민감 파일(`.env`, `*.key`, `credentials*`)이 포함되어 있으면 커밋을 중단하고 사용자에게 알립니다.

스테이징할 파일을 확인 후:

```bash
git add <변경된 파일들>   # -A 대신 파일 명시
git commit -m "$(cat <<'EOF'
<결정된 커밋 메시지>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git status
```

### 4단계: 결과 보고

커밋 완료 후 아래 형식으로 보고합니다.

```
커밋 완료
- 커밋 해시: <hash>
- 메시지: <type>(<scope>): <subject>
- 변경 파일: <n>개
```

커밋할 변경사항이 없으면 "현재 커밋할 변경사항이 없습니다." 라고 안내합니다.
