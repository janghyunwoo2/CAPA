# ⚙️ PHASE 5: 작업 분할 및 실행

> 아키텍처를 작업 단위로 쪼개서 실행하고 결과를 기록하는 단계

---

## 📂 폴더 설명

```
05-phase5-execution/
├── personas/          # 역할별 개발자 페르소나
│   ├── data-engineer.md
│   ├── devops.md
│   ├── backend.md
│   └── ml-engineer.md
│
├── templates/         # 작업/결과 템플릿
│   ├── task-template.md
│   └── result-template.md
│
├── input/            # PHASE 4 결과물
│   ├── plan-final.md
│   └── architecture.md
│
└── tasks/            # 작업 명세서 + 결과
    ├── task-001-data-glue-table.md
    ├── task-001-data-glue-table-result.md
    ├── task-002-devops-kinesis.md
    ├── task-002-devops-kinesis-result.md
    └── ...
```

---

## 🔄 작업 순서

### 1단계: 작업 분할
```
input/architecture.md를 보고 작업 단위로 분할:

예시:
- task-001: Glue 테이블 정의
- task-002: Kinesis Stream Terraform
- task-003: Firehose 설정
- task-004: S3 버킷 생성
- task-005: Log Generator 연동
...
```

### 2단계: 작업 명세서 작성
```
templates/task-template.md를 참고하여:

1. tasks/task-001-data-glue-table.md 작성
   - 작업 목표
   - 요구사항
   - 구현 가이드
   - 완료 기준
   - 의존성
```

### 3단계: 작업 실행
```
1. 해당 역할 페르소나 선택 (예: data-engineer.md)
2. Copilot에 페르소나 + task-001.md 제공
3. 실행 요청
```

### 4단계: 결과 기록
```
templates/result-template.md를 참고하여:

1. tasks/task-001-data-glue-table-result.md 작성
   - 완료 항목
   - 생성/수정된 파일
   - 테스트 결과
   - 발견 이슈
   - 만족도 평가
```

### 5단계: 만족도 평가
```
만족 (✅)
  └─► task-002로 진행

불만족 (❌)
  └─► task-001.md 수정 후 재실행
```

---

## 📝 작업 명명 규칙

```
task-XXX-역할-작업명.md
task-XXX-역할-작업명-result.md

예시:
- task-001-data-glue-table.md
- task-001-data-glue-table-result.md
- task-002-devops-kinesis-terraform.md
- task-002-devops-kinesis-terraform-result.md
```

---

## 📊 작업 상태 관리

각 task.md 파일 상단에 상태 표시:

```markdown
> **상태**: 🔴 대기 / 🟡 진행중 / 🟢 완료 / 🔵 검토중 / ⚫ 보류
```

---

## 🔁 반복 작업

```
┌─────────────────────────────────────────────────────┐
│  작업 루프                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. task-NNN.md 작성                                │
│     ↓                                               │
│  2. Copilot에 실행 요청                             │
│     ↓                                               │
│  3. task-NNN-result.md 저장                         │
│     ↓                                               │
│  4. 만족도 평가                                     │
│     ├─ 만족 → 다음 작업 (task-NNN+1)                │
│     └─ 불만족 → task-NNN.md 수정 후 재실행          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 📋 체크리스트

- [ ] input/ 폴더에 plan-final.md, architecture.md 확인
- [ ] 작업 목록 작성 (WBS)
- [ ] 작업 간 의존성 파악
- [ ] task-001.md 작성
- [ ] 역할별 페르소나로 실행
- [ ] task-001-result.md 작성
- [ ] 만족 시 task-002로, 불만족 시 재작업
- [ ] 모든 작업 완료까지 반복

---

## ✅ 완료 조건

모든 작업이 완료되고 통합 테스트 통과 시 PHASE 5 종료
→ Sprint 완료! 🎉
