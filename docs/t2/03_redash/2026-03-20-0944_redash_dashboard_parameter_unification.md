# Redash 대시보드 파라미터 통합 관리 방법

## 요청사항
- 대시보드에서 각 위젯별로 생성된 target_date 파라미터를 하나로 통합하여 관리
- 현재 p_w19_target_date, p_w20_target_date, p_w21_target_date 등 개별 파라미터가 생성되는 문제 해결

## AS-IS (현재 상태)
### 문제점
1. **위젯별 개별 파라미터**: 각 쿼리 위젯마다 독립적인 target_date 파라미터 생성
2. **중복 입력 필요**: 날짜 변경 시 모든 위젯의 파라미터를 각각 변경해야 함
3. **복잡한 URL**: `p_w19_target_date`, `p_w20_target_date` 등 위젯별 파라미터로 URL이 복잡해짐

## TO-BE (개선된 방식)
### 목표
1. **대시보드 레벨 파라미터**: 하나의 target_date로 모든 위젯 제어
2. **단일 입력**: 날짜 변경 시 한 번만 입력하면 모든 위젯에 적용
3. **간단한 URL**: `p_target_date` 하나로 통합

## 구현 방법

### 1. 쿼리 파라미터 이름 통일
모든 쿼리에서 동일한 파라미터 이름 사용:

```sql
-- ❌ 잘못된 방법: 쿼리마다 다른 파라미터 이름
-- 쿼리 1: {{ query1_date }}
-- 쿼리 2: {{ report_date }}
-- 쿼리 3: {{ analysis_date }}

-- ✅ 올바른 방법: 모든 쿼리에서 동일한 파라미터 이름
-- 모든 쿼리: {{ target_date }}
```

### 2. 대시보드 레벨 파라미터 설정

#### 2.1 쿼리 수정
각 쿼리에서 파라미터 이름을 동일하게 수정:

```sql
-- 일간 KPI 요약 쿼리
WITH date_params AS (
    SELECT 
        DATE('{{ target_date }}') as target_date,  -- 통일된 파라미터명
        CAST(YEAR(DATE('{{ target_date }}')) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as day_val
)
```

#### 2.2 대시보드 설정
1. 대시보드 편집 모드로 진입
2. 대시보드 설정에서 "Dashboard Parameters" 활성화
3. 파라미터 타입을 "Date"로 설정
4. 기본값을 "yesterday" 또는 "d_yesterday"로 설정

### 3. 위젯 파라미터 매핑

#### 3.1 자동 매핑 (권장)
쿼리에서 동일한 파라미터 이름을 사용하면 자동으로 대시보드 파라미터와 연결됨

#### 3.2 수동 매핑 (필요 시)
1. 각 위젯의 설정 아이콘 클릭
2. "Widget Parameters" 섹션에서 매핑
3. 위젯 파라미터를 대시보드 파라미터로 연결

### 4. 실제 적용 단계별 가이드

#### Step 1: 모든 쿼리 파라미터 이름 확인
```sql
-- 쿼리 목록 확인 및 파라미터 이름 통일 필요 여부 파악
-- 예시: 시간별 트렌드 쿼리
-- 기존: {{ w19_target_date }}
-- 변경: {{ target_date }}
```

#### Step 2: 각 쿼리 수정
```sql
-- 광고주별 실적 쿼리 수정 예시
WITH date_params AS (
    SELECT 
        DATE('{{ target_date }}') as target_date,  -- 통일된 이름 사용
        CAST(YEAR(DATE('{{ target_date }}')) AS VARCHAR) as year_val,
        LPAD(CAST(MONTH(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as month_val,
        LPAD(CAST(DAY(DATE('{{ target_date }}')) AS VARCHAR), 2, '0') as day_val
)
SELECT 
    advertiser_id,
    COUNT(*) as impressions,
    SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks
FROM ad_combined_log_summary
CROSS JOIN date_params
WHERE 
    year = year_val
    AND month = month_val
    AND day = day_val
GROUP BY advertiser_id
```

#### Step 3: 대시보드 파라미터 설정
1. 대시보드 편집 모드 진입
2. 대시보드 설정(⚙️) 클릭
3. "Use Dashboard Level Filters" 활성화
4. 파라미터 추가:
   - Name: `target_date`
   - Type: `Date`
   - Default Value: `yesterday`

#### Step 4: 기존 위젯 재추가
파라미터 이름을 변경한 쿼리의 위젯은 다시 추가해야 할 수 있음:
1. 기존 위젯 제거
2. 수정된 쿼리로 새 위젯 추가
3. 대시보드 파라미터와 자동 연결 확인

### 5. 고급 활용법

#### 5.1 다중 날짜 파라미터 관리
```sql
-- 날짜 범위를 사용하는 경우
WITH date_params AS (
    SELECT 
        DATE('{{ start_date }}') as start_date,
        DATE('{{ end_date }}') as end_date
)
-- 대시보드에서 start_date, end_date 두 개의 파라미터로 관리
```

#### 5.2 기존 파라미터와의 호환성
```sql
-- 기존 year, month, day 파라미터와 병행 사용
WITH date_params AS (
    SELECT 
        -- 새로운 방식 우선, 없으면 기존 방식 사용
        CASE 
            WHEN '{{ target_date }}' != '' THEN DATE('{{ target_date }}')
            ELSE DATE(CONCAT('{{ year }}', '-', '{{ month }}', '-', '{{ day }}'))
        END as effective_date
)
```

#### 5.3 파라미터 그룹화
날짜 관련 파라미터를 그룹으로 관리:
- 기본 날짜: `target_date`
- 비교 날짜: `compare_date`
- 날짜 범위: `start_date`, `end_date`

### 6. 트러블슈팅

#### 문제 1: 파라미터가 자동으로 연결되지 않음
**원인**: 쿼리 파라미터 이름과 대시보드 파라미터 이름이 다름
**해결**: 쿼리에서 정확히 동일한 파라미터 이름 사용

#### 문제 2: 위젯별 파라미터가 계속 표시됨
**원인**: 대시보드 레벨 필터가 비활성화됨
**해결**: 대시보드 설정에서 "Use Dashboard Level Filters" 활성화

#### 문제 3: 기본값이 작동하지 않음
**원인**: 파라미터 타입이 잘못 설정됨
**해결**: 파라미터 타입을 "Date"로 설정하고 기본값을 "yesterday" 형식으로 입력

### 7. 마이그레이션 체크리스트

- [ ] 모든 쿼리의 파라미터 이름 확인
- [ ] 파라미터 이름을 `target_date`로 통일
- [ ] 각 쿼리 테스트 실행
- [ ] 대시보드 설정에서 Dashboard Level Filters 활성화
- [ ] 대시보드 파라미터 추가 (name: target_date, type: Date)
- [ ] 기존 위젯 제거 및 재추가
- [ ] 전체 대시보드 동작 테스트
- [ ] URL 파라미터 단순화 확인

### 8. 예상 결과

#### Before (AS-IS)
```
URL: /dashboards/...?p_w19_target_date=2026-03-19&p_w20_target_date=2026-03-19&p_w21_target_date=2026-03-19
```

#### After (TO-BE)
```
URL: /dashboards/...?p_target_date=2026-03-19
```

### 9. 장점

1. **운영 효율성**
   - 날짜 변경 시 한 번만 입력
   - 실수로 인한 날짜 불일치 방지
   - 대시보드 관리 단순화

2. **사용자 경험**
   - 직관적인 인터페이스
   - 빠른 날짜 변경
   - 깔끔한 URL

3. **확장성**
   - 새 위젯 추가 시 자동으로 파라미터 연결
   - 다양한 날짜 파라미터 조합 가능
   - 템플릿으로 재사용 용이

## 추가 팁

### Redash API를 통한 일괄 수정
많은 쿼리를 수정해야 하는 경우 API 활용:
```python
# Redash API를 통한 쿼리 파라미터 일괄 수정 예시
import requests

# 모든 쿼리 조회
queries = requests.get(f"{REDASH_URL}/api/queries", headers=headers).json()

# target_date 파라미터 사용 쿼리 찾기 및 수정
for query in queries:
    if "{{ " in query.get("query", ""):
        # 파라미터 이름 통일 로직
        updated_query = query["query"].replace("{{ w19_target_date }}", "{{ target_date }}")
        # API를 통한 업데이트
```

이러한 방식으로 구현하면 대시보드의 모든 위젯이 하나의 날짜 파라미터로 통합 관리되어 운영이 훨씬 간편해집니다.