# Redash Athena LPAD 함수 및 파라미터 오류 해결

## 문제 상황
Redash에서 다음 쿼리 실행 시 오류 발생:

```sql
select
  *
from
  capa_ad_logs.ad_combined_log_summary
WHERE
  year = '{{year}}'
  AND month = '{{month}}'
  AND day BETWEEN LPAD(CAST('{{ start_day }}'), 2, '0')
  AND LPAD(CAST('{{ end_day }}'), 2, '0')
limit
  50;
```

**오류 메시지**: 
```
Error running query: An error occurred (InvalidRequestException) when calling the StartQueryExecution operation: Queries of this type are not supported
```

## 문제 원인 분석

### 1. Redash 파라미터 따옴표 중복 문제
- Redash는 텍스트 파라미터에 **자동으로 따옴표를 추가**
- `'{{ start_day }}'` → 실제 실행: `''10''` (따옴표 중복)
- 이로 인해 CAST 함수가 올바르게 작동하지 않음

### 2. Athena(Presto) LPAD 함수 사용법
- Athena의 LPAD 함수: `lpad(string, length, padstring)`
- **3개의 인자가 모두 필요**
- 잘못된 예: `LPAD(CAST('10'), 2, '0')` - CAST 결과가 정수가 될 수 있음

### 3. 데이터 타입 불일치
- `day` 컬럼은 문자열 타입 (`STRING`)
- BETWEEN 연산자에 문자열과 숫자가 혼재되면 오류 발생 가능

## AS-IS (현재 - 오류 발생)
```sql
-- Redash 파라미터가 따옴표를 자동 추가하여 문제 발생
WHERE
  year = '{{year}}'  -- OK: year가 문자열이면 정상
  AND month = '{{month}}'  -- OK: month가 문자열이면 정상
  AND day BETWEEN LPAD(CAST('{{ start_day }}'), 2, '0')  -- 문제!
  AND LPAD(CAST('{{ end_day }}'), 2, '0')  -- 문제!
```

## TO-BE (수정 후)

### 방법 1: IN 절로 파티션 명시 (파티션 프루닝 최적화)
```sql
-- Python으로 day 리스트 생성 후 Redash에서 사용
-- 예: start_day=25, end_day=31 → '25','26','27','28','29','30','31'
SELECT
  *
FROM
  capa_ad_logs.ad_combined_log_summary
WHERE
  year = {{ year }}
  AND month = {{ month }}
  AND day IN ({{ day_list }})  -- '25','26','27','28','29','30','31' 형식
LIMIT
  50;
```

**Redash 파라미터 설정**:
- `year`: Text (예: '2026')
- `month`: Text (예: '03')
- `day_list`: Text (예: '25','26','27','28','29','30','31')

**주의**: 범위 조건(>=, <=)은 파티션 프루닝이 제대로 작동하지 않아 전체 월 데이터를 스캔할 수 있음

### 방법 1-1: 월 전체 데이터 조회 (간단하지만 효율적)
```sql
-- 특정 월의 모든 데이터가 필요한 경우
SELECT
  *
FROM
  capa_ad_logs.ad_combined_log_summary
WHERE
  year = {{ year }}
  AND month = {{ month }}
  -- day 조건 없이 월 전체 조회 (파티션 프루닝 정상 작동)
ORDER BY day
LIMIT 1000;
```

### 방법 2: 동적 SQL로 IN 절 생성 (Redash Python 데이터소스 활용)
```python
# Redash Python 데이터소스에서 실행
import pandas as pd

# 파라미터 받기
year = '{{ year }}'
month = '{{ month }}'
start_day = int('{{ start_day }}')
end_day = int('{{ end_day }}')

# day 리스트 생성
days = [f"'{d:02d}'" for d in range(start_day, end_day + 1)]
day_condition = f"({','.join(days)})"

# Athena 쿼리 실행
query = f"""
SELECT *
FROM capa_ad_logs.ad_combined_log_summary  
WHERE year = '{year}'
  AND month = '{month}'
  AND day IN {day_condition}
LIMIT 50
"""
# 쿼리 실행 코드...
```

### 방법 3: 날짜 형식으로 변환하여 비교
```sql
SELECT
  *
FROM
  capa_ad_logs.ad_combined_log_summary
WHERE
  date_parse(
    CONCAT(year, '-', month, '-', day), 
    '%Y-%m-%d'
  ) 
  BETWEEN date '{{ start_date }}'  -- 2026-03-01
  AND date '{{ end_date }}'         -- 2026-03-31
LIMIT
  50;
```

**Redash 파라미터 설정**:
- `start_date`: Date 타입
- `end_date`: Date 타입

## 추가 주의사항

### 1. 파티션 컬럼 타입 확인
```sql
-- 테이블 스키마 확인
DESCRIBE capa_ad_logs.ad_combined_log_summary;
```

### 2. 파티션 프루닝 최적화
- `year`, `month`, `day`는 파티션 컬럼
- **범위 조건의 문제점**:
  - `day >= '25' AND day <= '31'` 사용 시, Athena가 해당 월의 **모든 day 파티션을 스캔**할 가능성
  - 예: month='03'의 경우 01~31까지 모든 파티션 스캔 → 성능 저하 및 비용 증가
- **권장 방법**:
  - `=` 조건: 단일 파티션만 스캔
  - `IN` 조건: 명시된 파티션만 스캔 (가장 효율적)
  - 예: `day IN ('25','26','27','28','29','30','31')` → 7개 파티션만 정확히 스캔

### 3. Redash 파라미터 타입별 동작
| 파라미터 타입 | 자동 따옴표 | 권장 사용처 |
|--------------|------------|------------|
| Text | O (추가됨) | 문자열 컬럼 |
| Number | X (추가 안됨) | 숫자 컬럼 |
| Date | 형식 변환 | 날짜 비교 |
| Dropdown | 선택된 값에 따름 | 제한된 옵션 |

## 권장 솔루션

### 최적 방법: 파티션 프루닝을 고려한 쿼리
1. **단일 날짜 조회**: `year='2026' AND month='03' AND day='15'`
2. **특정 날짜들 조회**: `day IN ('25','26','27','28','29','30','31')`
3. **월 단위 조회**: `year='2026' AND month='03'` (day 조건 제외)

### 피해야 할 패턴
- ❌ `day >= '25' AND day <= '31'` → 전체 월 스캔 위험
- ❌ `day BETWEEN '25' AND '31'` → 동일한 문제
- ❌ LPAD 함수 사용 → 불필요한 연산 + 파라미터 오류

### Redash에서 날짜 범위 처리 방법
```python
# Python 스크립트로 day 리스트 생성
start_day = 25
end_day = 31
day_list = ','.join([f"'{d:02d}'" for d in range(start_day, end_day + 1)])
# 결과: '25','26','27','28','29','30','31'
```

이 값을 Redash 파라미터에 복사하여 사용하면 파티션 프루닝이 최적화됩니다.

## 실제 사용 시나리오별 권장사항

### 1. 마지막 7일 데이터 조회
```sql
-- ❌ 비효율적: 범위 조건
WHERE day >= '25' AND day <= '31'

-- ✅ 효율적: IN 절 사용
WHERE day IN ('25','26','27','28','29','30','31')
```

### 2. 특정 월 전체 데이터 조회
```sql
-- ✅ 가장 효율적: day 조건 제외
WHERE year = '2026' AND month = '03'
```

### 3. 분기별 데이터 조회
```sql
-- ✅ 월 단위로 명시
WHERE year = '2026' AND month IN ('01','02','03')
```

### 4. 성능 비교
| 쿼리 패턴 | 스캔 범위 | 성능 |
|---------|---------|------|
| `day = '15'` | 1개 파티션 | 최상 |
| `day IN ('15','16','17')` | 3개 파티션 | 좋음 |
| `day >= '15' AND day <= '17'` | 전체 월 (31개) | 나쁨 |
| `month = '03'` (day 조건 없음) | 31개 파티션 | 보통 |