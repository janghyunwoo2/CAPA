---
name: tdd
description: PDCA Design 완료 후 TDD(Red→Green) 방식으로 Do 단계를 수행합니다. 테스트 계획서 작성 → 실패 테스트 작성 → 구현 → 결과 문서화까지 자동 진행합니다.
triggers: ["tdd", "tdd로 구현", "tdd 방식", "테스트 먼저", "red green", "test driven"]
---

# TDD Do 스킬

> PDCA **Plan → Design** 완료 후, **Do 단계를 TDD로 대체**하는 스킬.
> 버그가 발생하면 TDD 사이클을 추가한다.
> `/pdca do` 대신 `/tdd {feature}` 를 실행한다.

## 인수

| 인수 | 설명 | 예시 |
|------|------|------|
| `{feature}` | PDCA feature 이름 (Design 문서와 동일) | `/tdd slack-thread` |

---

## 실행 절차

아래 순서를 **반드시 순서대로** 실행한다. 단계를 건너뛰거나 순서를 바꾸지 않는다.

---

### 1단계: Design 문서 확인

Design 문서를 읽어 구현 범위를 파악한다.

```
탐색 우선순위:
1. docs/{담당자}/*/02-design/features/{feature}.design.md
2. docs/*/02-design/features/{feature}.design.md
3. .bkit/state/ 에서 현재 feature 경로 확인
```

**확인 항목:**
- FR ID 목록 (FR-XX-01, FR-XX-02 ...)
- 구현 대상 파일 목록 (§ 구현 파일 또는 § 파일 수정 순서)
- 성공 기준

Design 문서가 없으면 **중단**하고 사용자에게 안내한다:
> "Design 문서가 없습니다. 먼저 `/pdca design {feature}` 를 실행해 주세요."

---

### 2단계: 테스트 인프라 확인 / 생성

대상 서비스의 테스트 인프라가 없으면 생성한다.

#### pytest.ini (없을 때만 생성)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
log_cli = true
log_cli_level = INFO
```

#### tests/conftest.py (없을 때만 생성)

- 외부 서비스(Slack, AWS, DB 등) Mock 등록
- 공통 픽스처 작성
- **중요**: 테스트 대상 모듈의 외부 의존성(미설치 패키지)은 반드시 `sys.modules` Mock으로 처리

---

### 3단계: 테스트 계획서 작성

경로: `docs/{담당자 or 현재 docs 경로}/{feature-dir}/05-test/{feature}.test-plan.md`

**TC ID 규칙:** `TC-{약어}-{순번}` (예: `TC-ST-01`, `TC-ER-01`)

**테스트 케이스 설계 원칙:**
- Design 문서의 **FR ID 1개당 TC 1개 이상** 작성
- 정상 경로(Happy Path) + 에러 경로(Error Path) 분리
- Feature Flag 있으면 ON/OFF 각각 TC 작성
- 외부 API는 Mock으로 대체 (실제 호출 금지)

**테스트 계획서 형식:**

```markdown
# [Test Plan] {feature}

| 항목 | 내용 |
|------|------|
| **Feature** | {feature} |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | {design 문서 경로} |

## 테스트 케이스

### TC-{약어}-01: {FR ID} — {테스트 목적}
| 항목 | 내용 |
|------|------|
| **목적** | ... |
| **사전 조건** | ... |
| **테스트 입력** | ... |
| **기대 결과** | ... |
| **검증 코드** | `assert ...` |
```

---

### 4단계: 테스트 코드 작성 (Red)

경로: `{서비스}/tests/unit/test_{feature_snake}.py`

**작성 규칙:**
- Class 기반 구조: `class Test{기능명}:`
- 테스트 함수명: `test_{동작}_{조건}_{기대결과}` 패턴
- 픽스처는 `conftest.py`에 정의
- 외부 API: `unittest.mock.patch` 또는 `MagicMock` 사용
- `importlib.reload()`로 환경변수 변경 반영

**테스트 코드 파일 상단 docstring에 TC 목록 명시:**

```python
"""
{feature} 단위 테스트

TC 목록:
  TC-{약어}-01: {FR ID} — {설명}
  TC-{약어}-02: ...
"""
```

---

### 5단계: pytest 실행 → Red 확인

```bash
cd {서비스 디렉토리}
python -m pytest tests/unit/test_{feature_snake}.py -v --tb=short
```

**Red 확인 기준:**
- 새로 작성한 TC가 **1개 이상 FAIL** 이어야 정상
- 전부 PASS면 테스트가 구현을 검증하지 못하는 것 → TC 재검토
- Import 오류는 conftest.py Mock 추가로 해결

Red 상태를 사용자에게 보고한다:
```
🔴 Red Phase 확인
총 {N}개 TC 중 {M}개 FAIL
주요 실패 원인: {원인 요약}
```

---

### 6단계: 구현 (Green)

Design 문서의 **구현 파일 목록** 순서대로 최소한의 코드를 작성한다.

**구현 원칙:**
- 테스트를 통과시키는 **최소한의 코드**만 작성
- 테스트가 요구하지 않는 기능은 추가하지 않음
- 파일 수정 전 반드시 **Read** 후 Edit
- 코딩 규칙 준수 (`.claude/rules/coding-rules.md`)

---

### 7단계: pytest 실행 → Green 확인

```bash
python -m pytest tests/unit/test_{feature_snake}.py -v --tb=short
```

**Green 기준:** 전체 TC **100% PASS**

FAIL이 남아 있으면:
- 실패 원인 분석 후 구현 코드만 수정 (테스트 코드 수정 금지)
- 테스트가 잘못된 경우에만 TC 수정 (사유 명시 필수)

Green 상태를 사용자에게 보고한다:
```
✅ Green Phase 확인
총 {N}개 TC 전부 PASS ({실행 시간}s)
```

---

### 8단계: 테스트 결과 문서화

경로: `docs/{담당자 or 현재 docs 경로}/{feature-dir}/05-test/{feature}.test-result.md`

**test-rules.md 규칙 준수** — 결과 테이블 형식 필수:

```markdown
| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-{약어}-01 | - | {역할} | {입력} | {실제값} | `assert ...` | ✅ PASS | {이유} |
```

**TDD 사이클 요약 섹션도 포함:**
- Red Phase: 몇 개 FAIL, 주요 원인
- Green Phase: 전체 PASS, 수정 내용 요약
- 실행 로그 (pytest 출력 붙여넣기)

결과는 **문서 저장과 함께 대화창에도 동일 테이블 형식으로 출력**한다.

---

## 완료 기준

| 항목 | 기준 |
|------|------|
| 테스트 Pass율 | 100% |
| 테스트 계획서 | `05-test/{feature}.test-plan.md` 존재 |
| 테스트 결과서 | `05-test/{feature}.test-result.md` 존재 |
| 구현 코드 | Design 문서 구현 파일 목록 완료 |

완료 후 안내:
```
TDD Do 완료. 다음 단계: /pdca analyze {feature}
```

---

## 버그 발견 시 처리 방법

구현 중 설계서에 없던 버그를 발견하면 **TDD 사이클을 추가**한다.

1. 버그 TC 추가 (`BUG-{N}` 레이블 명시): Red
2. 버그 수정: Green
3. 결과 문서에 "TDD 사이클 N차" 섹션 추가

**절대 금지:** 테스트를 먼저 고쳐서 Green으로 만드는 것.
구현 코드가 잘못된 경우에만 구현 코드를 수정한다.

---

## 주의 사항

- **테스트 코드는 결과에 맞게 수정하지 않는다** — 항상 구현 코드를 수정해서 Green을 만든다
- 외부 서비스(Slack API, AWS, vanna-api 등)는 반드시 Mock 처리
- 테스트 실행은 반드시 **실제 pytest 실행** — 결과 예측으로 대체 금지
- FAIL 없이 모두 PASS면 테스트가 구현 검증을 못 하는 것이므로 TC 재검토
