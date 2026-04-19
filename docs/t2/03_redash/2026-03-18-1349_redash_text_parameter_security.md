# Redash 텍스트 파라미터 보안 경고 분석

## 경고 메시지
```
For your security, sharing is currently not supported for dashboards containing queries with text parameters. 
Consider changing the text parameters in your query to a different type.
```

## 의미
Redash에서 **텍스트 파라미터(Text Parameter)**가 포함된 쿼리를 가진 대시보드는 **보안상의 이유로 공유 기능이 제한**된다는 경고입니다.

## 원인

### 1. SQL 인젝션 위험
- 텍스트 파라미터는 사용자가 **자유롭게 문자열을 입력**할 수 있음
- 악의적인 사용자가 SQL 인젝션 공격을 시도할 가능성
- 예: `'; DROP TABLE users; --` 같은 악성 코드 삽입 가능

### 2. Redash의 보안 정책
- 대시보드 공유 시 **인증되지 않은 사용자**도 접근 가능
- 텍스트 파라미터는 입력값 검증이 어려워 위험도가 높음
- 따라서 텍스트 파라미터가 있는 대시보드는 공유를 차단

### 3. 공유 링크의 특성
- 공유된 대시보드는 **로그인 없이** 접근 가능
- 파라미터 값을 URL에서 직접 조작 가능
- 텍스트 파라미터는 모든 입력을 허용하므로 보안 취약점

## 해결 방법

### 1. 파라미터 타입 변경
텍스트 파라미터를 더 안전한 타입으로 변경:

| 타입 | 설명 | 보안성 |
|------|------|--------|
| **Dropdown List** | 미리 정의된 값만 선택 가능 | 높음 |
| **Query Based Dropdown** | 쿼리 결과에서 값 선택 | 높음 |
| **Date/DateTime** | 날짜 형식만 입력 가능 | 높음 |
| **Number** | 숫자만 입력 가능 | 중간 |

### 2. 쿼리 수정 예시

#### 기존 (텍스트 파라미터)
```sql
SELECT *
FROM ad_performance
WHERE campaign_name = '{{ campaign_name }}'
  AND advertiser_id = '{{ advertiser_id }}'
```

#### 변경안 1: 드롭다운 리스트
```sql
-- 쿼리는 동일
SELECT *
FROM ad_performance
WHERE campaign_name = '{{ campaign_name }}'
  AND advertiser_id = '{{ advertiser_id }}'

-- 파라미터 설정에서:
-- 1. Type을 "Dropdown List"로 변경
-- 2. 허용된 값 목록 입력
```

#### 변경안 2: Query Based Dropdown
```sql
-- 별도 쿼리로 드롭다운 값 생성
SELECT DISTINCT campaign_name
FROM ad_performance
ORDER BY campaign_name

-- 메인 쿼리에서 해당 파라미터 사용
```

### 3. Redash에서 파라미터 설정 변경 방법

1. **쿼리 편집 모드 진입**
   - 해당 쿼리 열기
   - "Edit" 버튼 클릭

2. **파라미터 설정**
   - 파라미터 옆의 톱니바퀴 아이콘 클릭
   - "Type" 드롭다운 메뉴 열기

3. **안전한 타입 선택**
   - "Text" 대신 다른 타입 선택
   - Dropdown List 선택 시 값 목록 설정

4. **저장 및 테스트**
   - 변경사항 저장
   - 대시보드 공유 기능 재확인

## 권장사항

### 1. 파라미터 타입 선택 가이드
- **고정된 값 집합**: Dropdown List 사용
- **데이터베이스 값**: Query Based Dropdown 사용
- **날짜 범위**: Date/DateTime Range 사용
- **ID/숫자**: Number 타입 사용

### 2. 보안 고려사항
- 가능한 텍스트 파라미터 사용 최소화
- 필요시 서버 측에서 입력값 검증
- 민감한 데이터는 공유 대시보드에 포함하지 않음

### 3. 대안 방안
- **Private Dashboard**: 공유가 필요 없다면 비공개 유지
- **User Groups**: 특정 그룹에게만 권한 부여
- **API Integration**: 프로그래밍 방식으로 안전한 접근 제어

## 파티셔닝을 위한 문자열 입력 해결방법

### 문제 상황
- S3 파티셔닝 경로에서 `month='02'`, `day='03'`과 같이 0이 포함된 문자열 필요
- 숫자 파라미터는 02를 2로 변환하여 파티션 조회 실패
- 텍스트 파라미터는 보안상 공유 불가

### 실제 적용 가능한 해결방법

#### LPAD 함수란?
LPAD(Left Pad)는 문자열의 왼쪽에 특정 문자를 채워 원하는 길이로 만드는 SQL 함수입니다.

**문법**: `LPAD(문자열, 목표길이, 채울문자)`

**예시**:
- `LPAD('2', 2, '0')` → `'02'`
- `LPAD('12', 2, '0')` → `'12'` (이미 2자리이므로 변경 없음)
- `LPAD('5', 3, '0')` → `'005'`
- `LPAD('abc', 5, '*')` → `'**abc'`

**파티셔닝에서의 활용**:
- S3 파티션은 `month='02'` 형식으로 저장됨
- 사용자는 숫자 2를 입력하지만 '02'로 변환 필요
- LPAD로 한 자리 숫자 앞에 0을 추가

#### 각 방법의 작동 원리

**방법 1 원리**: 숫자 입력을 SQL 내에서 문자열로 변환
- 사용자는 숫자로 입력 (보안상 안전)
- SQL 실행 시 LPAD 함수가 자동으로 형식 변환
- 장점: 유연하고 보안적으로 안전
- 단점: SQL 함수 지원 여부 확인 필요

**방법 2 원리**: 미리 정의된 값만 선택 가능
- 드롭다운에 '01', '02' 등 문자열 직접 저장
- 사용자는 선택만 가능 (입력 불가)
- 장점: 가장 간단하고 직관적
- 단점: 값이 고정되어 유연성 낮음

**방법 3 원리**: 데이터베이스의 실제 값을 동적으로 가져옴
- 별도 쿼리로 존재하는 월/일 값 조회
- 실제 데이터가 있는 값만 선택 가능
- 장점: 데이터와 항상 동기화
- 단점: 추가 쿼리 필요

**방법 4 원리**: 날짜 타입을 활용한 자동 변환
- Date 파라미터로 전체 날짜 입력
- SQL에서 년/월/일로 분리 후 형식 맞춤
- 장점: 사용자 편의성 높음 (달력 UI)
- 단점: 복잡한 SQL 함수 사용

#### 방법 1: 숫자 파라미터 + SQL 함수 사용 (권장)
```sql
-- 파라미터는 Number 타입으로 설정
-- SQL 내에서 LPAD 함수로 2자리 문자열 변환
SELECT *
FROM ad_combined_log_summary
WHERE year = '{{ year }}'
  AND month = LPAD(CAST({{ month }} AS VARCHAR), 2, '0')
  AND day = LPAD(CAST({{ day }} AS VARCHAR), 2, '0')

-- PostgreSQL/MySQL: LPAD 사용
-- SQL Server: FORMAT({{ month }}, '00')
-- Presto/Athena: LPAD(CAST({{ month }} AS VARCHAR), 2, '0')
```

**작동 과정**:
1. 사용자가 숫자 2 입력
2. Redash가 쿼리에 숫자 2 전달
3. CAST 함수가 숫자 2를 문자열 '2'로 변환
4. LPAD 함수가 '2'를 '02'로 변환 (왼쪽에 0 추가)
5. WHERE 절에서 month = '02' 조건으로 실행

#### 방법 2: Dropdown List로 미리 정의
```sql
-- 쿼리는 그대로 유지
SELECT *
FROM ad_combined_log_summary
WHERE year = {{ year }}
  AND month = '{{ month }}'
  AND day = '{{ day }}'

-- 파라미터 설정:
-- 1. month 파라미터 타입: "Dropdown List"
-- 2. Dropdown Values에 입력:
--    01,02,03,04,05,06,07,08,09,10,11,12
-- 3. day 파라미터도 동일하게 설정:
--    01,02,03,...,29,30,31
```

**작동 과정**:
1. 드롭다운에서 '02' 선택
2. Redash가 선택된 값 그대로 '02' 전달
3. WHERE 절에서 month = '02' 직접 매칭
4. 추가 변환 없이 바로 실행

#### 방법 3: Query Based Dropdown (동적 생성)
```sql
-- 월 드롭다운용 쿼리 (별도 쿼리로 생성)
SELECT DISTINCT 
    month as value,
    month as name
FROM ad_combined_log_summary
WHERE year = {{ year }}
ORDER BY month

-- 일 드롭다운용 쿼리 (별도 쿼리로 생성)
SELECT DISTINCT 
    day as value,
    day as name
FROM ad_combined_log_summary
WHERE year = {{ year }}
  AND month = '{{ month }}'
ORDER BY day

-- 메인 쿼리
SELECT *
FROM ad_combined_log_summary
WHERE year = {{ year }}
  AND month = '{{ month }}'
  AND day = '{{ day }}'
```

**작동 과정**:
1. 첫 번째 쿼리가 데이터베이스에서 가능한 월 값 조회
2. 두 번째 쿼리가 선택된 월에 대한 일 값 조회
3. 사용자는 실제 존재하는 데이터만 선택 가능
4. 선택된 값이 메인 쿼리에 전달되어 실행

#### 방법 4: 연도-월 통합 파라미터
```sql
-- Date 파라미터를 사용하고 SQL에서 분리
SELECT *
FROM ad_combined_log_summary
WHERE year = EXTRACT(YEAR FROM DATE '{{ date_param }}')
  AND month = LPAD(CAST(EXTRACT(MONTH FROM DATE '{{ date_param }}') AS VARCHAR), 2, '0')
  AND day = LPAD(CAST(EXTRACT(DAY FROM DATE '{{ date_param }}') AS VARCHAR), 2, '0')

-- 또는 DATE_FORMAT 함수 사용 (MySQL/MariaDB)
WHERE year = YEAR('{{ date_param }}')
  AND month = DATE_FORMAT('{{ date_param }}', '%m')
  AND day = DATE_FORMAT('{{ date_param }}', '%d')
```

**작동 과정**:
1. 사용자가 날짜 선택기에서 2024-02-03 선택
2. EXTRACT/DATE_FORMAT 함수가 날짜를 분해
3. 년: 2024, 월: 02 (자동으로 2자리), 일: 03 (자동으로 2자리)
4. 각 파티션 조건에 맞게 자동 변환되어 적용

### 구현 단계별 가이드

#### Dropdown List 방식 구현 (가장 간단)
1. Redash에서 쿼리 편집 모드로 진입
2. `{{ month }}` 파라미터 옆 톱니바퀴 클릭
3. Type을 "Dropdown List"로 변경
4. Dropdown Values에 입력: `01,02,03,04,05,06,07,08,09,10,11,12`
5. `{{ day }}` 파라미터도 동일하게 설정
6. 쿼리에서 따옴표 추가: `month = '{{ month }}'`

#### 숫자 파라미터 + LPAD 방식 구현 (유연성 높음)
1. 파라미터를 Number 타입으로 유지
2. WHERE 절에서 LPAD 함수 적용
3. Athena/Presto 환경: `LPAD(CAST({{ param }} AS VARCHAR), 2, '0')`
4. 테스트: 2 입력 시 '02'로 변환 확인

### 데이터베이스별 LPAD 함수

각 데이터베이스는 문자열 패딩을 위한 고유한 함수나 문법을 제공합니다:

| 데이터베이스 | 함수 예시 | 설명 |
|------------|---------|------|
| **Athena/Presto** | `LPAD(CAST({{ month }} AS VARCHAR), 2, '0')` | CAST로 숫자를 문자열로 변환 후 LPAD 적용 |
| **PostgreSQL** | `LPAD({{ month }}::TEXT, 2, '0')` | :: 연산자로 타입 변환 후 LPAD 적용 |
| **MySQL** | `LPAD({{ month }}, 2, '0')` | 자동 타입 변환되므로 직접 LPAD 사용 가능 |
| **SQL Server** | `FORMAT({{ month }}, '00')` | LPAD 없음, FORMAT 함수로 대체 |
| **Oracle** | `LPAD(TO_CHAR({{ month }}), 2, '0')` | TO_CHAR로 문자열 변환 후 LPAD 적용 |

**주의사항**:
- **타입 변환**: 대부분의 DB에서 숫자를 문자열로 변환 필요
- **함수 차이**: SQL Server는 LPAD가 없어 FORMAT 사용
- **자동 변환**: MySQL은 자동 타입 변환 지원으로 가장 간단

## 참고사항
- 이 제한은 Redash의 기본 보안 정책
- 텍스트 파라미터를 유지하면서는 공유 불가
- 다른 BI 도구들도 유사한 보안 정책 적용
- 파티셔닝된 테이블 조회 시 위 방법들로 대부분 해결 가능

## 추가 팁

### 성능 고려사항
- **LPAD 사용 시**: 인덱스가 있어도 함수 적용으로 인해 성능 저하 가능
- **권장**: 가능하면 드롭다운 방식 사용 (함수 실행 오버헤드 없음)
- **대용량 데이터**: 파티션 프루닝이 정상 작동하는지 실행계획 확인

### 파티셔닝 규칙 통일
- **저장 시**: 항상 2자리 문자열로 저장 ('01', '02', ..., '12')
- **조회 시**: 위 방법들로 형식 맞춤
- **일관성**: 모든 ETL 파이프라인에서 동일한 형식 사용

### 디버깅 방법
```sql
-- 파라미터 값 확인용 쿼리
SELECT 
    {{ month }} as input_number,
    LPAD(CAST({{ month }} AS VARCHAR), 2, '0') as padded_string,
    LENGTH(LPAD(CAST({{ month }} AS VARCHAR), 2, '0')) as string_length
```

이 쿼리로 입력값이 올바르게 변환되는지 확인할 수 있습니다.