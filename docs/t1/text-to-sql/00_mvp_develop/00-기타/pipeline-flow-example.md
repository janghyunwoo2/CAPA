# Text-to-SQL 처리 파이프라인 상세 설명 (기기별 성과 분석 사례)

> **작성일**: 2026-03-13
> **작성자**: Antigravity (AI 에이전트)

마케터들이 아주 자주 묻는 **"기기별 전환 성과 분석"** 사례를 들어 전체 처리 파이프라인을 상세히 설명합니다.

---

### 🚀 시나리오: "최근 7일간 디바이스별 구매 전환액과 ROAS 순위 알려줘"

#### [Phase 1: 입구] Slack Bot → vanna-api
1.  **Slack 메시지 수신**: 마케터가 슬랙에 질문을 올립니다.
2.  **POST /query 호출**: `slack-bot`은 `vanna-api`로 질문을 토스합니다. 이때 내부 보안 토큰(`X-Internal-Token`)을 함께 보냅니다.

---

#### [Phase 2: 비즈니스 로직] 11-Step Pipeline

**Step 1. IntentClassifier (의도 분류)**
*   **작업**: 질문이 "데이터 조회"인지 판단합니다.
*   **결과**: `intent = SQL_QUERY` (정상 진행)

**Step 2. QuestionRefiner (질문 정제)**
*   **작업**: 불필요한 수식어를 제거하고 명확하게 바꿉니다.
*   **결과**: "최근 7일간 device_type별 총 conversion_value와 ROAS(광고비 대비 매출액) 상위 순위"

**Step 3. KeywordExtractor (키워드 추출)**
*   **작업**: RAG 검색을 위한 검색어들을 뽑습니다.
*   **결과**: `["ROAS", "device_type", "conversion_value", "최근 7일", "구매", "purchase"]`

**Step 4. RAGRetriever (지식 검색)**
*   **작업**: ChromaDB에서 지식을 가져옵니다.
    *   **sql-ddl**: `ad_combined_log_summary` 테이블 구조 (conversion_value 컬럼 확인)
    *   **sql-docs**: "ROAS = SUM(conversion_value) / SUM(cost) * 100", "device_type 종류(mobile/tablet/desktop)"
    *   **sql-qa**: 비슷한 과거 질문-SQL 쌍 검색

**Step 5. SQLGenerator (SQL 생성)**
*   **작업**: 가져온 지식을 바탕으로 Athena SQL을 만듭니다.
*   **결과**: `SELECT device_type, SUM(conversion_value) as revenue, ... FROM ad_combined_log_summary WHERE day >= '2026-03-06' ... GROUP BY 1 ORDER BY ROAS DESC`

**Step 6. SQLValidator (SQL 검증)**
*   **작업**: 
    1. `sqlglot`으로 **SELECT**문인지, 허용된 테이블인지 검사합니다.
    2. Athena **EXPLAIN**을 날려 문법 오류나 비용 초과(1GB) 여부를 체크합니다. (실제 데이터 조회 X)

**Step 7. RedashQueryCreator (리대시 등록)**
*   **작업**: 검증된 SQL을 Redash API로 저장하고 고유 번호를 받습니다.
*   **결과**: `redash_query_id = 105`

**Step 8. RedashExecutor (실행 및 대기)**
*   **작업**: Redash에 "이 105번 쿼리 지금 실행해!"라고 시킵니다.
*   **결과**: Athena가 실제 S3 데이터를 뒤지기 시작하며, 파이프라인은 리대시를 3초마다 체크(Polling)하며 기다립니다.

**Step 9. ResultCollector (결과 수집)**
*   **작업**: 실행이 끝나면 리대시에서 데이터를 가져옵니다. (최대 1000행 수집, Slack 응답 시 10행으로 슬라이싱 — 전체 결과는 Redash URL로 안내)
*   **결과**: `[{"device_type": "mobile", "revenue": 500000, "ROAS": 450}, ...]`

**Step 10. AIAnalyzer (인사이트 분석)**
*   **작업**: 수집된 데이터를 보고 AI가 비즈니스 의미를 해석합니다.
*   **결과**: "모바일 기기의 ROAS가 450%로 가장 높습니다. 데스크톱 대비 전환액은 2배지만 광고비 효율은 1.5배 좋습니다." + **차트 타입: "bar" 추천**

**Step 10.5. ChartRenderer (차트 생성)**
*   **작업**: `matplotlib`을 이용해 기기별 ROAS를 막대그래프로 그립니다.
*   **결과**: PNG 이미지를 만들고 이를 문자열(Base64)로 변환합니다.

**Step 11. HistoryRecorder (이력 저장)**
*   **작업**: 이번 질문과 답변이 성공했으므로 `query_history.jsonl` 파일에 기록합니다.

---

#### [Phase 3: 출력] vanna-api → Slack Bot
1.  **응답 반환**: `vanna-api`가 최종 결과를 `slack-bot`에 돌려줍니다.
2.  **슬랙 게시**: `slack-bot`은 예쁜 카드(Block Kit) 형태로 조립해서 채널에 뿌립니다.
    *   ✅ 질문 내용
    *   📊 **[방금 만든 막대그래프 이미지]**
    *   💡 AI의 날카로운 분석 멘트
    *   🔗 **Redash 원본 보기 링크**
    *   [👍/👎 피드백 버튼]

---

#### [Phase 4: 자가학습] Feedback Loop
1.  **👍 클릭**: 마케터가 "오, 정확해!" 하고 따봉을 누르면 `POST /feedback`이 호출됩니다.
2.  **자동 학습**: 시스템은 즉시 `vanna.train()`을 호출하여, **이 질문과 SQL 조합을 ChromaDB에 영구 저장**합니다. 다음에 비슷한 질문이 오면 더 정확해집니다.
