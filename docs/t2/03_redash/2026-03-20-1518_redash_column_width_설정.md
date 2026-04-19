# Redash 컬럼 폭 설정 방법

## 문제 상황
- 광고주ID(advertiser_id) 컬럼이 실제 데이터 길이보다 훨씬 넓게 표시됨
- 특히 UUID 같은 긴 ID를 사용할 때 테이블이 가로로 너무 넓어짐

## 해결 방법

### 1. 테이블 시각화 편집
1. 쿼리 실행 후 "New Visualization" 클릭
2. "Visualization Type"에서 "Table" 선택
3. "Edit Visualization" 클릭

### 2. 컬럼 설정
1. "Column" 탭에서 광고주ID 컬럼 찾기
2. 다음 설정 옵션 사용:
   - **Width**: 픽셀 단위로 고정 폭 설정 (예: 120px)
   - **Auto-size**: "Fit to content"로 설정하면 텍스트 길이에 맞춤
   - **Max Width**: 최대 폭 제한 설정 가능

### 3. 추가 옵션
- **Text Wrapping**: 긴 텍스트를 여러 줄로 표시
- **Truncate**: 텍스트가 길면 "..." 으로 자르기
- **Tooltip**: 마우스 오버시 전체 내용 표시

## SQL 레벨에서의 해결책
```sql
-- 광고주ID를 축약하여 표시
SELECT 
    SUBSTR(advertiser_id, 1, 8) || '...' as "광고주ID",  -- 앞 8자리만 표시
    -- 또는
    CASE 
        WHEN LENGTH(advertiser_id) > 12 
        THEN SUBSTR(advertiser_id, 1, 12) || '...'
        ELSE advertiser_id 
    END as "광고주ID"
```

## 추천 설정
1. Redash 테이블 시각화에서:
   - Column Width: "Fit to content" 또는 120px
   - Text Overflow: "Ellipsis" (...)
   - Show Full Text on Hover: Yes

2. 대시보드에서 공간이 부족한 경우:
   - SQL에서 ID 축약 처리
   - 또는 별칭 테이블 조인하여 짧은 이름 사용