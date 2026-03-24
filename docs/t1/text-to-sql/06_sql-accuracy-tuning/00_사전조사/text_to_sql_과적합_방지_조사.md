# Text-to-SQL 과적합 없는 정확도 향상 방법 조사

## 핵심 답변: 과적합 없이 일반화하는 방법

### 왜 "케이스별 예시 추가"가 과적합인가

❌ **나쁜 방법**: "3월 14일 캠페인 CTR" 질문이 틀렸으니 그 쿼리 예시를 추가
→ 그 질문만 잘 나오고, "3월 13일 캠페인 CTR"이나 "어제 캠페인 CTR"은 여전히 틀림

✅ **좋은 방법**: "캠페인별 GROUP BY + CTR 계산 패턴"을 카테고리로 추가
→ 날짜가 바뀌어도, 필터 조건이 달라져도 패턴이 적용됨

---

## 3가지 방어선 (Defense in Depth)

### 1. 프롬프트 강화 — 즉시 적용 가능

| 추가할 내용 | 효과 |
| ----------- | ---- |
| CoT Step 1에 "DDL에 실제 존재하는 컬럼인지 확인 후 선택" 추가 | `campaign_name` 같은 hallucination 방지 |
| 테이블 선택 규칙 명시 (`_summary`=집계, 원본=개별 이벤트) | 잘못된 테이블 선택 방지 |
| "DDL에 없는 컬럼 절대 사용 금지" 규칙 | 일반적 hallucination 방지 |

### 2. 시딩 전략 — 패턴 기반으로 재설계

특정 쿼리 재현이 아니라 SQL 패턴 카테고리로 시딩:
- GROUP BY + CTR 계산 패턴 (날짜 무관)
- device_type/platform별 집계 패턴
- `ad_combined_log_summary` 써야 하는 케이스 documentation

### 3. 실행 오류 Self-Correction — 단기 구현 권장

생성된 SQL이 Athena에서 오류 나면 → 오류 메시지를 LLM에 다시 주입 → **1회 재생성**.
현재 `sql_validator.py`가 있으니 여기에 연결하면 됩니다.
→ 이게 구현되면 `campaign_name` 같은 오류는 자동 자가수정됩니다.

---

## 어떤 순서로 할까요?

1. **즉시**: `sql_generator.yaml` CoT + 테이블 선택 규칙 추가 (프롬프트만 수정)
2. **단기**: documentation 시딩에 "언제 어떤 테이블" 설명 추가
3. **중기**: Athena 오류 시 Self-Correction 1회 재시도 구현

1번만 해도 T001의 `campaign_name` 문제는 잡힐 가능성이 높습니다.
