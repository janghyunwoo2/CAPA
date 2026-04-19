# 📝 PHASE 1: 계획서 생성

> 3가지 관점(보수적/진보적/중도)에서 계획서 초안을 작성하는 단계

---

## 📂 폴더 설명

```
01-phase1-planning/
├── personas/          # 여기에 페르소나 파일 넣기
│   ├── conservative.md
│   ├── progressive.md
│   └── moderate.md
│
├── templates/         # 여기에 계획서 템플릿 넣기
│   └── plan-template.md
│
├── work/             # 여기서 작업 (초안 A, B, C)
│   ├── draft-conservative.md
│   ├── draft-progressive.md
│   └── draft-moderate.md
│
└── output/           # 최종 계획서 초안 저장
    └── plan-draft.md  ← 이 파일을 PHASE 2로 이동
```

---

## 🔄 작업 순서

### 1단계: 페르소나 파일 준비
```powershell
# personas/ 폴더에 3개 페르소나 파일 넣기
# - conservative.md (보수적)
# - progressive.md (진보적)
# - moderate.md (중도)
```

### 2단계: 보수적 관점 계획서
```
1. personas/conservative.md를 Copilot에 붙여넣기
2. 요구사항 전달
3. 결과를 work/draft-conservative.md에 저장
```

### 3단계: 진보적 관점 계획서
```
1. personas/progressive.md를 Copilot에 붙여넣기
2. 동일한 요구사항 전달
3. 결과를 work/draft-progressive.md에 저장
```

### 4단계: 중도 관점 계획서
```
1. personas/moderate.md를 Copilot에 붙여넣기
2. 동일한 요구사항 전달
3. 결과를 work/draft-moderate.md에 저장
```

### 5단계: 3개 초안 종합
```
1. work/ 폴더의 3개 초안을 종합
2. 최종 계획서 초안을 output/plan-draft.md로 저장
```

---

## ➡️ 다음 단계

PHASE 1 완료 후:
```powershell
# output 파일을 PHASE 2의 input으로 복사
cp output/plan-draft.md ../02-phase2-validation/input/

# PHASE 2로 이동
cd ../02-phase2-validation
```

---

## 📋 체크리스트

- [ ] personas/ 폴더에 페르소나 파일 3개 준비
- [ ] templates/ 폴더에 계획서 템플릿 준비
- [ ] work/ 폴더에서 3개 초안 작성
- [ ] output/ 폴더에 최종 초안 저장
- [ ] PHASE 2로 파일 복사
