# Redash 시간 컬럼 폭 문제 분석

## 문제 상황
"시간별 트렌드 분석 (개선된 버전)" 쿼리 실행 시 "시간" 컬럼의 폭이 비정상적으로 넓게 표시되는 문제

## AS-IS
```sql
hour as "시간"
```
- hour 컬럼을 그대로 SELECT
- 데이터 타입이나 포맷에 대한 명시적 처리 없음

## 원인 분석

### 1. 데이터 타입 문제
- `hour` 필드가 VARCHAR로 저장되어 있을 가능성
- Athena 파티션 컬럼은 기본적으로 STRING(VARCHAR) 타입
- Redash가 VARCHAR 컬럼에 대해 기본적으로 넓은 폭을 할당

### 2. Redash 자동 폭 조정
- Redash는 VARCHAR/STRING 타입 컬럼에 대해 안전하게 넓은 폭을 할당
- 실제 데이터는 "0", "1", ... "23" 같은 짧은 값이지만, 타입 때문에 넓게 표시

### 3. 파티션 컬럼 특성
- S3 파티션 경로: `year=2026/month=03/day=19/hour=15/`
- 파티션 컬럼은 문자열로 저장됨

## TO-BE (해결 방안)

### 방안 1: 명시적 타입 변환 (권장)
```sql
CAST(hour AS INTEGER) as "시간"
```
- hour를 정수로 변환하여 Redash가 숫자 컬럼으로 인식
- 컬럼 폭이 자동으로 좁아짐

### 방안 2: 포맷팅 적용
```sql
LPAD(hour, 2, '0') || '시' as "시간"
```
- "00시", "01시" 형태로 표시
- 고정 길이로 표시되어 일관성 있음

### 방안 3: 정수 변환 + 포맷팅
```sql
CAST(hour AS INTEGER) || '시' as "시간"
```
- 숫자 변환 후 '시' 추가
- "0시", "1시", ... "23시" 형태

## 권장 수정 쿼리

```sql
-- 시간별 노출수와 클릭수 추이 - 기본값은 어제, 파라미터로 변경 가능
WITH date_params AS (
    SELECT 
        DATE('{{ target_date }}') as target_date,
        CAST(YEAR(DATE('{{ target_date }}')) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as day_val
)
SELECT 
    target_date as "조회날짜",
    CAST(hour AS INTEGER) as "시간",  -- 정수로 변환
    COUNT(*) as "노출수",
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as "클릭수",
    SUM(cost_per_impression) + SUM(CASE WHEN is_click THEN cost_per_click ELSE 0 END) as "광고비",
    SUM(CASE WHEN is_click THEN 15000.0 ELSE 0 END) as "매출",
    COUNT(DISTINCT advertiser_id) as "활성_광고주수"
FROM ad_combined_log
CROSS JOIN date_params
WHERE 
    year = year_val
    AND month = month_val
    AND day = day_val
GROUP BY target_date, hour
ORDER BY CAST(hour AS INTEGER)  -- ORDER BY도 정수로 변환
```

## 추가 고려사항

### Redash 설정
1. 쿼리 결과 테이블 설정에서 컬럼 폭 수동 조정 가능
2. Visualization 편집 모드에서 컬럼 속성 변경 가능

### 다른 시간 관련 쿼리도 동일하게 수정 필요
- 시간대별 ROAS 패턴 분석
- 시간대별 성과 비교
- 비용 효율성 분석 (CPC, CPM, CPA)

## 검증 방법
1. 수정된 쿼리 실행
2. "시간" 컬럼 폭 확인
3. 정렬 순서 확인 (0, 1, 2, ... 23 순서)