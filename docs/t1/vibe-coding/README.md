# 🎵 바이브 코딩 방법론 - PHASE별 작업 흐름

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  바이브 코딩 (Vibe Coding) - PHASE별 독립 작업 방식                          ║
║  각 PHASE 폴더에서 작업 → 결과물을 다음 PHASE로 이동                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 📂 폴더 구조

```
docs/vibe-coding/
│
├── 01-phase1-planning/      # PHASE 1: 계획서 생성
│   ├── personas/            # 사용할 페르소나 (보수/진보/중도)
│   ├── templates/           # 계획서 템플릿
│   ├── work/                # 작업 파일 (초안 A, B, C)
│   └── output/              # 최종 결과물 → PHASE 2로 이동
│
├── 02-phase2-validation/    # PHASE 2: 검증
│   ├── personas/            # 검증 페르소나
│   ├── templates/           # 검증 보고서 템플릿
│   ├── input/               # PHASE 1 결과물 (복사해서 가져옴)
│   ├── work/                # 검증 작업
│   └── output/              # 검증 보고서 → PHASE 3으로 이동
│
├── 03-phase3-refinement/    # PHASE 3: 역할별 고도화
│   ├── personas/            # 역할별 개발자 페르소나
│   ├── input/               # PHASE 2 결과물
│   ├── work/                # 역할별 피드백
│   └── output/              # 최종 계획서 → PHASE 4로 이동
│
├── 04-phase4-architecture/  # PHASE 4: 아키텍처 설계
│   ├── input/               # PHASE 3 결과물
│   ├── work/                # 아키텍처 다이어그램 작업
│   └── output/              # 아키텍처 문서 → PHASE 5로 이동
│
└── 05-phase5-execution/     # PHASE 5: 작업 분할 및 실행
    ├── personas/            # 역할별 개발자 페르소나
    ├── templates/           # 작업/결과 템플릿
    ├── input/               # PHASE 4 결과물
    └── tasks/               # 작업 명세서 + 결과
        ├── task-001-xxx.md
        └── task-001-xxx-result.md
```

---

## 🔄 작업 흐름

```
┌──────────────────────────────────────────────────────────────────────┐
│                         PHASE별 작업 흐름                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  01-phase1-planning/                                                 │
│    └─ work/ 에서 작업                                                │
│    └─ output/ 에 결과물 저장                                         │
│            │                                                         │
│            ▼ 복사                                                    │
│  02-phase2-validation/                                               │
│    └─ input/ 에 PHASE 1 결과 복사                                    │
│    └─ work/ 에서 검증 작업                                           │
│    └─ output/ 에 검증 보고서 저장                                    │
│            │                                                         │
│            ▼ 복사                                                    │
│  03-phase3-refinement/                                               │
│    └─ input/ 에 PHASE 2 결과 복사                                    │
│    └─ work/ 에서 역할별 피드백                                       │
│    └─ output/ 에 최종 계획서 저장                                    │
│            │                                                         │
│            ▼ 복사                                                    │
│  04-phase4-architecture/                                             │
│    └─ input/ 에 PHASE 3 결과 복사                                    │
│    └─ work/ 에서 아키텍처 설계                                       │
│    └─ output/ 에 아키텍처 문서 저장                                  │
│            │                                                         │
│            ▼ 복사                                                    │
│  05-phase5-execution/                                                │
│    └─ input/ 에 PHASE 4 결과 복사                                    │
│    └─ tasks/ 에서 작업 실행 및 결과 저장                             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 사용 방법

### PHASE 1 시작
```powershell
cd docs/vibe-coding/01-phase1-planning

# 1. personas/ 폴더에 페르소나 파일 넣기
# 2. templates/ 폴더에 계획서 템플릿 넣기
# 3. work/ 폴더에서 작업
# 4. output/ 폴더에 최종 결과 저장
```

### PHASE 2로 이동
```powershell
# PHASE 1 완료 후
cp output/* ../02-phase2-validation/input/

cd ../02-phase2-validation
# work/ 폴더에서 검증 작업
# output/ 폴더에 결과 저장
```

### 이후 PHASE도 동일한 방식으로 진행

---

## 💡 각 폴더의 역할

| 폴더 | 용도 |
|------|------|
| **personas/** | 해당 PHASE에서 사용할 페르소나 프롬프트 저장 |
| **templates/** | 해당 PHASE에서 사용할 문서 템플릿 저장 |
| **input/** | 이전 PHASE의 output을 복사해서 가져옴 |
| **work/** | 실제 작업 파일 (초안, 검토 등) |
| **output/** | 완성된 결과물 (다음 PHASE로 이동) |
| **tasks/** | PHASE 5 전용 - 작업 명세서와 결과 |

---

## 📋 각 PHASE 상세

각 PHASE 폴더에 들어가면 해당 단계의 상세 가이드가 있습니다.

- [PHASE 1: 계획서 생성](./01-phase1-planning/README.md)
- [PHASE 2: 검증](./02-phase2-validation/README.md)
- [PHASE 3: 역할별 고도화](./03-phase3-refinement/README.md)
- [PHASE 4: 아키텍처 설계](./04-phase4-architecture/README.md)
- [PHASE 5: 작업 분할 및 실행](./05-phase5-execution/README.md)
