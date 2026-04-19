# 🚀 바이브 코딩 Quick Start

> PHASE별로 독립된 폴더에서 작업 → 결과물을 다음 PHASE로 복사

---

## 📋 전체 흐름 (5단계)

```
01-phase1-planning
    ↓ (output → input)
02-phase2-validation
    ↓ (output → input)
03-phase3-refinement
    ↓ (output → input)
04-phase4-architecture
    ↓ (output → input)
05-phase5-execution
```

---

## 🎯 PHASE 1: 계획서 생성

### 작업 폴더
```powershell
cd docs/vibe-coding/01-phase1-planning
```

### 작업 순서
1. **personas/ 폴더에 페르소나 파일 넣기**
   - conservative.md (보수적)
   - progressive.md (진보적)
   - moderate.md (중도)

2. **work/ 폴더에서 3가지 관점 초안 작성**
   ```
   Copilot에 요청:
   - personas/conservative.md로 draft-conservative.md 작성
   - personas/progressive.md로 draft-progressive.md 작성
   - personas/moderate.md로 draft-moderate.md 작성
   ```

3. **output/ 폴더에 최종 초안 저장**
   ```
   3개 초안을 종합하여 plan-draft.md 작성
   → output/plan-draft.md 저장
   ```

### 다음 단계로 이동
```powershell
# output을 PHASE 2의 input으로 복사
cp output/plan-draft.md ../02-phase2-validation/input/

cd ../02-phase2-validation
```

---

## 🔍 PHASE 2: 검증

### 작업 폴더
```powershell
cd docs/vibe-coding/02-phase2-validation
```

### 작업 순서
1. **input/ 폴더에서 PHASE 1 결과 확인**
   ```
   input/plan-draft.md 확인
   ```

2. **personas/critic.md로 검증 작업**
   ```
   Copilot에 요청:
   - personas/critic.md + input/plan-draft.md
   - 검증 결과를 work/validation-notes.md에 저장
   ```

3. **output/ 폴더에 검증 보고서 저장**
   ```
   - output/plan-draft.md (원본 복사)
   - output/validation.md (검증 보고서)
   ```

### 다음 단계로 이동
```powershell
# output을 PHASE 3의 input으로 복사
cp output/* ../03-phase3-refinement/input/

cd ../03-phase3-refinement
```

---

## 👥 PHASE 3: 역할별 고도화

### 작업 폴더
```powershell
cd docs/vibe-coding/03-phase3-refinement
```

### 작업 순서
1. **input/ 폴더 확인**
   ```
   - input/plan-draft.md
   - input/validation.md
   ```

2. **필요한 역할 식별**
   ```
   Copilot에 요청:
   - personas/base-developer.md로 필요 역할 파악
   예: Data Engineer, DevOps, Backend
   ```

3. **역할별 피드백 수집**
   ```
   각 역할의 페르소나로 검토:
   - personas/data-engineer.md
     → work/feedback-data-engineer.md
   - personas/devops.md
     → work/feedback-devops.md
   - personas/backend.md
     → work/feedback-backend.md
   ```

4. **output/ 폴더에 최종 계획서 저장**
   ```
   모든 피드백 반영하여
   output/plan-final.md 작성
   ```

### 다음 단계로 이동
```powershell
# output을 PHASE 4의 input으로 복사
cp output/plan-final.md ../04-phase4-architecture/input/

cd ../04-phase4-architecture
```

---

## 🏗️ PHASE 4: 아키텍처 설계

### 작업 폴더
```powershell
cd docs/vibe-coding/04-phase4-architecture
```

### 작업 순서
1. **input/plan-final.md 확인**

2. **work/ 폴더에서 아키텍처 설계**
   ```
   Copilot에 요청:
   "plan-final.md를 기반으로 시스템 아키텍처를
   ASCII 다이어그램으로 그려주세요"
   
   → work/diagram-draft.md
   → work/component-specs.md
   ```

3. **output/ 폴더에 아키텍처 문서 저장**
   ```
   output/architecture.md 작성
   ```

### 다음 단계로 이동
```powershell
# output을 PHASE 5의 input으로 복사
cp output/architecture.md ../05-phase5-execution/input/
cp ../03-phase3-refinement/output/plan-final.md ../05-phase5-execution/input/

cd ../05-phase5-execution
```

---

## ⚙️ PHASE 5: 작업 분할 및 실행

### 작업 폴더
```powershell
cd docs/vibe-coding/05-phase5-execution
```

### 작업 순서
1. **input/ 폴더 확인**
   ```
   - input/plan-final.md
   - input/architecture.md
   ```

2. **작업 분할**
   ```
   architecture.md를 보고 작업 단위로 분할:
   - task-001: Glue 테이블 정의
   - task-002: Kinesis Stream Terraform
   - task-003: Firehose 설정
   ...
   ```

3. **작업 실행 루프**
   ```
   각 작업마다:
   
   ┌─────────────────────────────────────┐
   │ 1. tasks/task-001-xxx.md 작성        │
   │    (요구사항, 구현 가이드)            │
   │         ↓                            │
   │ 2. Copilot에 실행 요청               │
   │    (personas/역할.md + task.md)      │
   │         ↓                            │
   │ 3. tasks/task-001-xxx-result.md 저장 │
   │         ↓                            │
   │ 4. 만족도 평가                       │
   │    ├─ 만족 → task-002로             │
   │    └─ 불만족 → task-001 수정 재실행  │
   └─────────────────────────────────────┘
   ```

---

## 💡 핵심 포인트

### 1. 각 PHASE는 독립된 작업 공간
```
- PHASE 1에서 작업 → output/ 저장
- output/을 다음 PHASE의 input/으로 복사
- 다음 PHASE에서 독립적으로 작업
```

### 2. 파일 이동 규칙
```powershell
# PHASE N 완료 후 항상:
cp output/* ../PHASE-N+1/input/
```

### 3. work/ 폴더는 자유롭게 사용
```
- 초안, 노트, 임시 파일 등
- 정리해서 output/으로 최종 산출물만 저장
```

### 4. 결과물 명명 규칙
```
PHASE 1: plan-draft.md
PHASE 2: validation.md
PHASE 3: plan-final.md
PHASE 4: architecture.md
PHASE 5: task-NNN-역할-작업명.md
```

---

## 📁 폴더 구조 요약

```
01-phase1-planning/
├── personas/     ← 페르소나 넣기
├── templates/    ← 템플릿 넣기
├── work/         ← 작업 공간
└── output/       ← 결과물 저장 → PHASE 2로

02-phase2-validation/
├── input/        ← PHASE 1 결과 복사
├── work/         ← 검증 작업
└── output/       ← 결과물 저장 → PHASE 3으로

03-phase3-refinement/
├── input/        ← PHASE 2 결과 복사
├── work/         ← 역할별 피드백
└── output/       ← 결과물 저장 → PHASE 4로

04-phase4-architecture/
├── input/        ← PHASE 3 결과 복사
├── work/         ← 아키텍처 작업
└── output/       ← 결과물 저장 → PHASE 5로

05-phase5-execution/
├── input/        ← PHASE 4 결과 복사
└── tasks/        ← 작업 + 결과 저장
```

---

## 🎉 완료!

모든 PHASE를 거쳐 tasks/의 모든 작업이 완료되면 Sprint 종료!
