# 👥 PHASE 3: 역할별 고도화

> 검증 피드백을 반영하고 역할별 전문가 관점에서 계획서를 고도화하는 단계

---

## 📂 폴더 설명

```
03-phase3-refinement/
├── personas/          # 역할별 개발자 페르소나
│   ├── base-developer.md
│   ├── data-engineer.md
│   ├── devops.md
│   ├── backend.md
│   └── ml-engineer.md
│
├── input/            # PHASE 2 결과물
│   ├── plan-draft.md
│   └── validation.md
│
├── work/             # 역할별 피드백
│   ├── feedback-data-engineer.md
│   ├── feedback-devops.md
│   └── feedback-backend.md
│
└── output/           # 최종 계획서
    └── plan-final.md  ← 이 파일을 PHASE 4로 이동
```

---

## 🔄 작업 순서

### 1단계: PHASE 2 결과물 확인
```powershell
# input/ 폴더에 있는 파일 확인
# - plan-draft.md (원본 계획서)
# - validation.md (검증 보고서)
```

### 2단계: 필요한 역할 식별
```
1. personas/base-developer.md를 Copilot에 붙여넣기
2. input/plan-draft.md 전달
3. 필요한 역할 식별 (예: Data Engineer, DevOps, Backend)
```

### 3단계: 역할별 피드백 수집
```
각 역할의 페르소나로 검토:

# Data Engineer
1. personas/data-engineer.md 사용
2. input/plan-draft.md + input/validation.md 전달
3. 피드백을 work/feedback-data-engineer.md에 저장

# DevOps
1. personas/devops.md 사용
2. 피드백을 work/feedback-devops.md에 저장

# Backend
1. personas/backend.md 사용
2. 피드백을 work/feedback-backend.md에 저장
```

### 4단계: 최종 계획서 작성
```
1. plan-draft.md를 기반으로
2. validation.md의 Critical/Major 이슈 수정
3. 각 역할의 피드백 반영
4. output/plan-final.md로 저장
```

---

## ➡️ 다음 단계

PHASE 3 완료 후:
```powershell
# output 파일을 PHASE 4의 input으로 복사
cp output/plan-final.md ../04-phase4-architecture/input/

# PHASE 4로 이동
cd ../04-phase4-architecture
```

---

## 📋 체크리스트

- [ ] input/ 폴더에 plan-draft.md, validation.md 확인
- [ ] base-developer.md로 필요 역할 식별
- [ ] 역할별 페르소나로 피드백 수집
- [ ] work/ 폴더에 역할별 피드백 저장
- [ ] 모든 피드백 반영하여 plan-final.md 작성
- [ ] output/ 폴더에 최종 계획서 저장
- [ ] PHASE 4로 파일 복사
