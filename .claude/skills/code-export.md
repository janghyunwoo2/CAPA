# .claude/skills/code-export.md

---
name: code-export
description: 코드를 마크다운 파일로 내보내기
triggers: ["md 코드로", "마크다운으로", "코드 내보내기", "export"]
---

## 역할

사용자가 요청한 코드/설정을 마크다운 파일 형식으로 출력합니다.
모든 파일은 파일 경로와 함께 마크다운 코드블록으로 표시되어 복사 가능합니다.

## 출력 형식

```markdown
# .claude/파일경로/파일명.확장자

[파일 설명]

```언어
[파일 내용]
```
```

## 예시

사용자: "훅 설정을 md 코드로 줘"

출력:
```markdown
# .claude/settings.json

CAPA 프로젝트 Hook 설정

```json
{
  "hooks": {
    "PostToolUse": [...]
  }
}
```
```

## 주의사항

- 각 파일은 `---` 로 구분
- 파일 경로는 `.claude/` 기준으로 표시
- 코드블록에 복사 버튼이 자동으로 생김
