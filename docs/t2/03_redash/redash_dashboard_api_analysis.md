# Redash API를 통한 대시보드 접근 방법 분석

## 조사 배경
- 일간/주간/월간 대시보드를 생성하고 URL로 제공해야 함
- **핵심 질문**: URL 1개로 대시보드 여러 개를 가져올 수 있는가?

## 조사 결과 요약

### 📍 답변: URL 1개로 여러 대시보드를 동시에 가져올 수 **없음**
- Redash는 각 대시보드마다 **고유한 URL**을 부여
- 대시보드별로 개별 접근 필요

---

## Redash 대시보드 URL 구조

### 1. 대시보드 URL 형식
```
# ID 기반 접근
https://redash-url/dashboard/{dashboard_id}

# Slug 기반 접근
https://redash-url/dashboard/{dashboard_slug}

# 예시
https://redash-url/dashboard/251-account-overview
```

### 2. URL 특징
- **ID**: 대시보드 생성 시 자동 할당되는 고유 번호
- **Slug**: 대시보드 이름 기반으로 생성되는 URL-친화적 문자열
- 같은 이름의 대시보드가 여러 개일 경우, 가장 먼저 생성된 대시보드로 리다이렉트

---

## API를 통한 대시보드 접근

### 1. 대시보드 목록 조회
```bash
curl -s \
  -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/dashboards
```

### 2. 특정 대시보드 정보 조회
```bash
# ID로 조회
curl -s \
  -H "Authorization: Key $REDASH_API_KEY" \
  $REDASH_URL/api/dashboards/{dashboard_id}
```

### 3. 대시보드 생성
```bash
curl -s -X POST \
  -H "Authorization: Key $REDASH_API_KEY" \
  -H "Content-Type: application/json" \
  $REDASH_URL/api/dashboards \
  -d '{
    "name": "대시보드 이름"
  }'
```

---

## 일간/주간/월간 대시보드 구현 방안

### ✅ 권장 방안: 3개의 독립된 대시보드
```
일간 대시보드: https://redash-url/dashboard/daily-report
주간 대시보드: https://redash-url/dashboard/weekly-report  
월간 대시보드: https://redash-url/dashboard/monthly-report
```

### 장점
- 각 대시보드 독립적 관리 가능
- 명확한 URL 구조
- 개별 권한 설정 가능
- API를 통한 자동 업데이트 용이

### 구현 절차
1. **대시보드 3개 생성** (daily, weekly, monthly)
2. **각 대시보드에 위젯 배치**
   - 일간: 어제 하루 데이터
   - 주간: 지난 7일 데이터  
   - 월간: 지난 1개월 데이터
3. **매일 오전 6시 자동 업데이트**
   - 쿼리 재실행으로 데이터 갱신
   - 대시보드 URL은 변경 없음

---

## 대안 검토

### 1. ❌ 단일 대시보드에 탭/필터 사용
- Redash는 대시보드 내 탭 기능을 제공하지 않음
- 필터는 가능하나 일간/주간/월간 전환에는 부적합

### 2. ❌ Query Results Data Source 활용
- 여러 쿼리를 조합할 수는 있으나 대시보드 통합은 불가
- 데이터 조합용이지 대시보드 병합용이 아님

### 3. ⚠️ 외부 임베딩
- iframe으로 여러 대시보드를 한 페이지에 표시 가능
- 하지만 이는 Redash 외부에서 구현해야 함

---

## 결론 및 권장사항

### 최종 답변
- **URL 1개로 여러 대시보드 접근 불가**
- **일간/주간/월간 각각 별도 URL 필요** (총 3개)

### 구현 권장사항
1. 3개의 독립된 대시보드 생성 및 유지
2. 리포트 생성 시 3개 URL을 함께 제공
3. Slack 등에서 메시지 전송 시:
   ```
   📊 광고 성과 대시보드
   • 일간: https://redash-url/dashboard/daily
   • 주간: https://redash-url/dashboard/weekly  
   • 월간: https://redash-url/dashboard/monthly
   ```

### 추가 고려사항
- 대시보드 명명 규칙 통일
- 동일한 레이아웃과 시각화 스타일 유지
- API Key 보안 관리
- 자동화 스크립트에서 3개 URL 관리 방안 수립

---

## 참고 문헌
- [Redash 공식 문서 - Dashboard Editing](https://redash.io/help/user-guide/dashboards/dashboard-editing)
- [프로젝트 내부 문서 - redash_api_test.md](../redash_api_test.md)
- [프로젝트 계획 문서 - redash_init_plan.md](./redash_init_plan.md)