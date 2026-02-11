# 🏗️ PHASE 4: 아키텍처 설계

> 최종 계획서를 기반으로 구현 가능한 시스템 아키텍처를 설계하는 단계

---

## 📂 폴더 설명

```
04-phase4-architecture/
├── input/            # PHASE 3 결과물
│   └── plan-final.md
│
├── work/             # 아키텍처 작업
│   ├── diagram-draft.md
│   └── component-specs.md
│
└── output/           # 아키텍처 문서
    └── architecture.md  ← 이 파일을 PHASE 5로 이동
```

---

## 🔄 작업 순서

### 1단계: PHASE 3 결과물 확인
```powershell
# input/plan-final.md 확인
# 주요 컴포넌트, 기술 스택, 데이터 플로우 파악
```

### 2단계: 아키텍처 다이어그램 작성
```
Copilot에 요청:
"plan-final.md를 기반으로 시스템 아키텍처를 
ASCII 다이어그램 또는 Mermaid로 그려주세요.
다음을 포함해주세요:
- 주요 컴포넌트
- 데이터 플로우
- 통합 포인트
- 네트워크 구성"

결과를 work/diagram-draft.md에 저장
```

### 3단계: 컴포넌트 상세 명세
```
각 컴포넌트에 대해:
- 역할 및 책임
- 입력/출력
- 기술 스택
- 설정 사항

work/component-specs.md에 작성
```

### 4단계: 아키텍처 문서 완성
```
1. work/ 폴더의 내용 종합
2. ASCII/Mermaid 다이어그램 + 상세 설명
3. output/architecture.md로 저장
```

---

## 📋 아키텍처 문서 구조

```markdown
# 시스템 아키텍처

## 1. 아키텍처 개요
[전체 시스템 다이어그램]

## 2. 컴포넌트 상세
### Kinesis Data Stream
- 역할: ...
- 설정: ...

### Firehose
...

## 3. 데이터 플로우
[데이터 흐름 다이어그램]

## 4. 네트워크 구성
[네트워크 다이어그램]

## 5. 배포 구조
[배포 다이어그램]
```

---

## ➡️ 다음 단계

PHASE 4 완료 후:
```powershell
# output 파일을 PHASE 5의 input으로 복사
cp output/architecture.md ../05-phase5-execution/input/
# plan-final.md도 함께 복사
cp ../03-phase3-refinement/output/plan-final.md ../05-phase5-execution/input/

# PHASE 5로 이동
cd ../05-phase5-execution
```

---

## 📋 체크리스트

- [ ] input/plan-final.md 확인
- [ ] work/ 폴더에 다이어그램 초안 작성
- [ ] 컴포넌트 상세 명세 작성
- [ ] output/architecture.md 완성
- [ ] 다이어그램이 명확하고 구현 가능한지 확인
- [ ] PHASE 5로 파일 복사
