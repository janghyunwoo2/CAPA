# Redash 파라미터에서 CAST 함수 vs 따옴표 사용 비교

## CAST 함수란?

### 정의
CAST는 SQL에서 **데이터 타입을 명시적으로 변환**하는 표준 함수입니다. 한 데이터 타입의 값을 다른 데이터 타입으로 변환할 때 사용합니다.

### 기본 문법
```sql
CAST(expression AS target_type)
```

### 주요 사용 목적
1. **타입 불일치 해결**: 함수나 연산자가 특정 타입을 요구할 때
2. **명시적 변환**: 암시적 변환에 의존하지 않고 의도를 명확히 표현
3. **데이터 정제**: 문자열을 숫자로, 숫자를 문자열로 변환

### 예시
```sql
-- 숫자를 문자열로 변환
CAST(123 AS VARCHAR)         -- '123'

-- 문자열을 숫자로 변환
CAST('456' AS INTEGER)       -- 456

-- 날짜 변환
CAST('2024-01-01' AS DATE)   -- DATE 타입으로 변환

-- Athena/Presto에서의 사용
CAST(month_number AS VARCHAR)  -- 숫자형 month를 문자열로
```

### Redash 파라미터와 CAST
Redash의 Number 타입 파라미터는 **숫자로 치환**되므로, 문자열 함수(LPAD, CONCAT 등)에 사용하려면 CAST가 필요합니다.

---

## CAST가 필요한 이유

### 1. 숫자 파라미터의 동작 방식
Redash에서 **Number 타입 파라미터**를 사용하면:
```sql
-- 사용자가 2를 입력했을 때
WHERE month = {{ month }}
-- 실제 실행되는 SQL:
WHERE month = 2    -- 숫자 2로 치환됨
```

### 2. LPAD는 문자열 함수
LPAD 함수는 **문자열만** 입력받을 수 있습니다:
```sql
-- ❌ 오류 발생 (숫자를 직접 전달)
LPAD(2, 2, '0')    -- 타입 에러!

-- ✅ 정상 작동 (문자열 전달)
LPAD('2', 2, '0')  -- '02' 반환
```

### 3. 따옴표로 감싸면?

네, 맞습니다! 따옴표로 감싸는 방법도 있어요:

```sql
-- 방법 1: CAST 사용
WHERE month = LPAD(CAST({{ month }} AS VARCHAR), 2, '0')

-- 방법 2: 따옴표로 감싸기
WHERE month = LPAD('{{ month }}', 2, '0')
```

### 두 방법의 차이점

| 구분 | CAST 방식 | 따옴표 방식 |
|------|----------|------------|
| **SQL 인젝션 방어** | ✅ 안전 (숫자만 허용) | ⚠️ 주의 필요 |
| **파라미터 타입** | Number 타입 유지 | Number여도 문자열로 처리 |
| **데이터베이스 호환성** | 모든 DB에서 동일 | DB마다 처리 방식 다를 수 있음 |

### 실제 예시

```sql
-- 사용자가 숫자 2 입력 시

-- CAST 방식:
LPAD(CAST(2 AS VARCHAR), 2, '0')  -- 명확하게 타입 변환

-- 따옴표 방식:
LPAD('2', 2, '0')  -- 문자열로 직접 처리
```

### 권장사항

**따옴표 방식도 작동하지만**, CAST를 사용하는 것이 더 안전한 이유:

1. **명시적 타입 변환**: 코드 의도가 명확함
2. **보안**: Number 파라미터의 숫자 검증 기능 유지
3. **호환성**: 모든 데이터베이스에서 일관된 동작

### 더 간단한 대안

가장 간단한 방법은 처음부터 **Dropdown List**를 사용하는 것입니다:
```sql
-- 드롭다운에 '01', '02', ... 설정
WHERE month = '{{ month }}'  -- 이미 문자열이므로 LPAD 불필요!
```

## 결론

- CAST가 번거로워 보이지만, 보안과 명확성을 위해 권장됩니다
- 따옴표 방식도 충분히 작동하지만 보안상 주의가 필요합니다
- 가장 간단한 해결책은 Dropdown List를 사용하는 것입니다

## 실제 Athena에서의 사용 예시

```sql
-- Athena/Presto에서 권장되는 방식
SELECT *
FROM ad_combined_log_summary
WHERE year = '{{ year }}'
  AND month = LPAD(CAST({{ month }} AS VARCHAR), 2, '0')
  AND day = LPAD(CAST({{ day }} AS VARCHAR), 2, '0')
```