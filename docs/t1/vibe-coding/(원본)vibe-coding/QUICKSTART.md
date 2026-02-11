# 🚀 바이브 코딩 Quick Start Guide

> CAPA 프로젝트에서 바이브 코딩 방법론을 바로 시작하는 가이드

---

## 📋 5분 안에 시작하기

### Step 1: 새 스프린트 디렉토리 생성

```powershell
# 새 스프린트 디렉토리 생성
mkdir docs/vibe-coding/02-plans/sprint-NNN
mkdir docs/vibe-coding/03-tasks/sprint-NNN
```

### Step 2: 계획서 초안 작성 (3개 페르소나 활용)

Copilot 채팅에서 다음과 같이 진행:

```
1. 보수적 페르소나 프롬프트 복사 (01-personas/planner/conservative.md)
2. Copilot에 붙여넣기 + 요구사항 전달
3. 결과를 "plan-conservative.md"로 임시 저장

4. 진보적 페르소나 프롬프트 복사 (01-personas/planner/progressive.md)
5. 동일 요구사항으로 결과 생성
6. 결과를 "plan-progressive.md"로 임시 저장

7. 중도 페르소나 프롬프트 복사 (01-personas/planner/moderate.md)
8. 세 관점을 종합하여 "plan-draft.md" 생성
```

### Step 3: 검증

```
1. 검증 페르소나 프롬프트 복사 (01-personas/validator/critic.md)
2. plan-draft.md 내용 전달
3. 검증 결과를 "validation.md"로 저장
4. Critical/Major 이슈 수정
```

### Step 4: 역할별 고도화

```
1. 범용 개발자 프롬프트 (01-personas/developers/base-developer.md)로 역할 식별
2. 필요한 역할별 페르소나로 추가 검토
   - Data Engineer: developers/data-engineer.md
   - DevOps: developers/devops.md
   - Backend: developers/backend.md
   - ML Engineer: developers/ml-engineer.md
3. 피드백 반영하여 "plan-final.md" 완성
```

### Step 5: 작업 분할 및 실행

```
1. plan-final.md 기반으로 task-XXX-역할.md 생성
2. 각 task.md를 Copilot에 전달하여 실행
3. 결과를 task-XXX-역할-result.md로 저장
4. 만족 → 다음 task / 불만족 → task.md 수정 후 재실행
```

---

## 🎯 실전 예시: Kinesis 파이프라인 구축

### 요구사항
```
"광고 로그(impression, click, conversion)를 Kinesis로 수집하고 
S3에 Parquet 포맷으로 적재하는 파이프라인 구축"
```

### Copilot 대화 예시

#### 1단계: 계획서 생성

```markdown
@workspace 

다음 페르소나 프롬프트를 적용해주세요:
[01-personas/planner/moderate.md 내용 붙여넣기]

요구사항:
- Kinesis Data Stream으로 광고 로그 수집
- Firehose로 S3에 Parquet 포맷 적재
- event_type/year/month/day 파티셔닝
- Glue 테이블 정의
- Athena 쿼리 가능하게

계획서를 00-templates/plan-template.md 형식으로 작성해주세요.
```

#### 2단계: 검증

```markdown
@workspace

다음 검증 페르소나로 계획서를 검토해주세요:
[01-personas/validator/critic.md 내용 붙여넣기]

검토 대상:
[plan-draft.md 내용 붙여넣기]
```

#### 3단계: 작업 실행

```markdown
@workspace

다음 Data Engineer 페르소나로 작업을 수행해주세요:
[01-personas/developers/data-engineer.md 내용 붙여넣기]

작업 지시:
[task-001-data-glue-table.md 내용 붙여넣기]
```

---

## 📂 디렉토리 구조 요약

```
docs/vibe-coding/
├── README.md              # 전체 방법론 설명
├── QUICKSTART.md          # 본 가이드 (빠른 시작)
│
├── 00-templates/          # 템플릿
│   ├── plan-template.md
│   ├── validation-template.md
│   ├── task-template.md
│   └── result-template.md
│
├── 01-personas/           # 페르소나 프롬프트
│   ├── planner/           # 계획 페르소나
│   │   ├── conservative.md
│   │   ├── progressive.md
│   │   └── moderate.md
│   ├── validator/         # 검증 페르소나
│   │   └── critic.md
│   └── developers/        # 개발자 페르소나
│       ├── base-developer.md
│       ├── data-engineer.md
│       ├── devops.md
│       ├── backend.md
│       └── ml-engineer.md
│
├── 02-plans/              # 스프린트별 계획서
│   └── sprint-001/
│       ├── plan-draft.md
│       ├── validation.md
│       ├── plan-final.md
│       └── architecture.md
│
└── 03-tasks/              # 스프린트별 작업
    └── sprint-001/
        ├── task-001-xxx.md
        ├── task-001-xxx-result.md
        └── ...
```

---

## ⚡ 핵심 팁

### 1. 페르소나 선택
| 상황 | 권장 페르소나 |
|------|--------------|
| 미션 크리티컬 | 보수적 → 검증 |
| 신기술 도입 | 진보적 → 검증 → 보수적 검토 |
| 일반 작업 | 중도 → 검증 |

### 2. 반복 규칙
```
계획서 불만족 → 페르소나 피드백 → 수정 → 재검증
작업 결과 불만족 → task.md 수정 → 재실행
```

### 3. 버전 관리
```
- 모든 md 파일은 Git으로 버전 관리
- 주요 변경 시 변경 이력 섹션 업데이트
- 폐기된 계획은 _archive/ 로 이동
```

---

## 🔗 관련 문서

- [전체 방법론 가이드](./README.md)
- [계획서 템플릿](./00-templates/plan-template.md)
- [Sprint 001 예시](./02-plans/sprint-001/plan-draft.md)
- [CAPA 프로젝트 컨셉](../t1/project_concept_v3.md)
