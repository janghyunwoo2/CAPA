# 🔍 PHASE 2: 검증

> PHASE 1에서 만든 계획서 초안을 비판적으로 검증하는 단계

---

## 📂 폴더 설명

```
02-phase2-validation/
├── personas/          # 검증 페르소나
│   └── critic.md
│
├── templates/         # 검증 보고서 템플릿
│   └── validation-template.md
│
├── input/            # PHASE 1 결과물 (여기로 복사)
│   └── plan-draft.md
│
├── work/             # 검증 작업
│   └── validation-notes.md
│
└── output/           # 검증 보고서 저장
    ├── plan-draft.md        ← 원본 (수정 없이 그대로)
    └── validation.md        ← 검증 보고서
```

---

## 🔄 작업 순서

### 1단계: PHASE 1 결과물 가져오기
```powershell
# PHASE 1의 output을 이 폴더 input으로 복사 (이미 완료됨)
# input/plan-draft.md 확인
```

### 2단계: 검증 작업
```
1. personas/critic.md를 Copilot에 붙여넣기
2. input/plan-draft.md 내용 전달
3. 검증 결과를 work/validation-notes.md에 작성
```

### 3단계: Critical/Major 이슈 확인
```
- 🔴 Critical Issues: 반드시 수정해야 할 문제
- 🟠 Major Issues: 강력히 권고되는 수정
- 🟡 Minor Issues: 개선 제안
```

### 4단계: 검증 보고서 완성
```
1. work/validation-notes.md를 정리
2. output/validation.md로 저장
3. output/plan-draft.md도 함께 저장 (원본 유지)
```

---

## ➡️ 다음 단계

PHASE 2 완료 후:
```powershell
# output 파일들을 PHASE 3의 input으로 복사
cp output/* ../03-phase3-refinement/input/

# PHASE 3로 이동
cd ../03-phase3-refinement
```

---

## 📋 체크리스트

- [ ] input/ 폴더에 plan-draft.md 확인
- [ ] personas/critic.md로 검증 수행
- [ ] work/ 폴더에서 검증 노트 작성
- [ ] output/ 폴더에 validation.md 저장
- [ ] Critical/Major 이슈 목록 확인
- [ ] PHASE 3로 파일 복사
