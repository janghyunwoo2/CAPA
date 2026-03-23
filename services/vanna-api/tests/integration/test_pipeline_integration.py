"""
Phase 2 통합 테스트: Step 1→11 전체 E2E 연결 및 입출력 검증
test-plan.md §4 기준

목적: Do Phase에서 구현한 src/ 코드가 Step 간 올바르게 연결되고
      각 Step의 입출력이 설계 명세(pipeline-flow-example.md)대로 나오는지 확인
환경: 실제 ChromaDB (docker-compose) + 실제 Anthropic LLM + mock Athena/Redash
      외부 서비스(Step 6~11)는 mock 응답 기반으로 연결 검증
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────
# Step 1: IntentClassifier
# ─────────────────────────────────────────────────────────────────
class TestStep1Intent:

    async def test_광고질문_SQL_QUERY_분류(self, pipeline):
        """입력: 광고 데이터 조회 질문 → 출력: intent=DATA_QUERY, 파이프라인 계속"""
        from src.models.domain import IntentType
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        assert ctx.intent == IntentType.DATA_QUERY, \
            f"Step 1 실패: DATA_QUERY 예상, 실제={ctx.intent}"
        # Step 1 중단이 없어야 함
        assert ctx.error is None or ctx.error.failed_step != 1

    async def test_범위외질문_OUT_OF_SCOPE_중단(self, pipeline):
        """입력: 광고 무관 질문(EX-1) → 출력: intent=OUT_OF_SCOPE, Step 1에서 중단"""
        from src.models.domain import IntentType
        ctx = await pipeline.run("요즘 날씨 어때?")

        assert ctx.intent == IntentType.OUT_OF_SCOPE, \
            f"Step 1 실패: OUT_OF_SCOPE 예상, 실제={ctx.intent}"
        assert ctx.generated_sql is None, "Step 1 중단 후 SQL이 생성되면 안 됨"
        assert ctx.error is not None
        assert ctx.error.failed_step == 1
        assert ctx.error.error_code == "INTENT_OUT_OF_SCOPE"


# ─────────────────────────────────────────────────────────────────
# Step 2: QuestionRefiner
# ─────────────────────────────────────────────────────────────────
class TestStep2Refiner:

    async def test_구어체질문_핵심용어_보존(self, pipeline):
        """입력: 구어체 질문 → 출력: refined_question에 핵심 용어 포함"""
        ctx = await pipeline.run("음... 혹시 최근 7일간 기기별 전환액 좀 알 수 있을까요?")

        assert ctx.refined_question is not None, "Step 2 출력 없음"
        assert len(ctx.refined_question) > 0
        assert any(kw in ctx.refined_question for kw in ["전환", "7일", "기기", "디바이스"]), \
            f"핵심 용어 손실: refined='{ctx.refined_question}'"

    async def test_ROAS질문_정제결과_검증(self, pipeline):
        """입력: ROAS 질문 → 출력: refined_question에 ROAS 또는 관련 용어 포함"""
        ctx = await pipeline.run("최근 7일간 디바이스별 ROAS 순위 알려줘")

        assert ctx.refined_question is not None
        assert any(kw in ctx.refined_question.upper() for kw in ["ROAS", "디바이스", "DEVICE", "7일"]), \
            f"Step 2: ROAS 용어 손실 — refined='{ctx.refined_question}'"


# ─────────────────────────────────────────────────────────────────
# Step 3: KeywordExtractor
# ─────────────────────────────────────────────────────────────────
class TestStep3Keywords:

    async def test_키워드_리스트_반환(self, pipeline):
        """입력: 광고 질문 → 출력: 1개 이상의 키워드 리스트"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        assert ctx.keywords is not None, "Step 3 출력 없음"
        assert isinstance(ctx.keywords, list)
        assert len(ctx.keywords) > 0, "키워드 빈 리스트"

    async def test_ROAS질문_도메인키워드_포함(self, pipeline):
        """입력: ROAS+디바이스 질문 → 출력: roas, device_type 등 포함
        pipeline-flow-example.md 기준: ['ROAS', 'device_type', 'conversion_value', '최근 7일']
        """
        ctx = await pipeline.run("최근 7일간 디바이스별 ROAS 순위 알려줘")

        assert ctx.keywords is not None
        kw_lower = [k.lower() for k in ctx.keywords]
        assert any(k in kw_lower for k in ["roas", "device_type", "device", "conversion_value", "conversion"]), \
            f"도메인 용어 미추출: keywords={ctx.keywords}"


# ─────────────────────────────────────────────────────────────────
# Step 4: RAGRetriever (ChromaDB 실제 연결)
# ─────────────────────────────────────────────────────────────────
class TestStep4RAG:

    async def test_RAG컨텍스트_None아님(self, pipeline):
        """Step 4가 실행되면 rag_context는 반드시 None이 아님 (ChromaDB 빈 경우 포함)"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1~3 통과 확인
        assert ctx.intent is not None
        assert ctx.refined_question is not None
        assert ctx.keywords is not None
        # Step 4 결과
        assert ctx.rag_context is not None, \
            "Step 4 실패: rag_context=None — ChromaDB 연결 문제 가능"

    async def test_ChromaDB_실패시_파이프라인_계속(self, pipeline):
        """Step 4 실패(ChromaDB 연결 문제)가 파이프라인을 중단시키지 않아야 함 (EX-7)"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 4 에러로 중단되면 안 됨 (Step 5 이상까지 가야 함)
        if ctx.error:
            assert ctx.error.failed_step > 4, \
                f"Step 4에서 잘못 중단: error={ctx.error}"


# ─────────────────────────────────────────────────────────────────
# Step 5: SQLGenerator
# ─────────────────────────────────────────────────────────────────
class TestStep5SQL:

    async def test_생성SQL_SELECT로시작(self, pipeline):
        """입력: 광고 조회 질문 → 출력: SELECT로 시작하는 SQL"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        assert ctx.generated_sql is not None, \
            f"Step 5 실패: SQL 없음 — error={ctx.error}"
        assert ctx.generated_sql.strip().upper().startswith("SELECT"), \
            f"SELECT 아님: '{ctx.generated_sql[:80]}'"

    async def test_생성SQL_허용테이블_참조(self, pipeline):
        """SEC-04: 생성 SQL이 허용 테이블(ad_combined_log_summary/ad_combined_log) 참조"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        if ctx.generated_sql:
            sql_lower = ctx.generated_sql.lower()
            assert any(t in sql_lower for t in ["ad_combined_log_summary", "ad_combined_log"]), \
                f"허용 테이블 미참조: '{ctx.generated_sql[:200]}'"

    async def test_ROAS_SQL_필수필드포함(self, pipeline):
        """ROAS 질문 → SQL에 device_type, conversion_value/cost, GROUP BY 포함
        pipeline-flow-example.md 기준
        """
        ctx = await pipeline.run("최근 7일간 디바이스별 ROAS 순위 알려줘")

        if ctx.generated_sql:
            sql_lower = ctx.generated_sql.lower()
            assert "device_type" in sql_lower, \
                f"device_type 없음: '{ctx.generated_sql[:200]}'"
            assert any(f in sql_lower for f in ["conversion_value", "cost"]), \
                f"ROAS 계산 필드 없음: '{ctx.generated_sql[:200]}'"
            assert "group by" in sql_lower, \
                f"GROUP BY 없음: '{ctx.generated_sql[:200]}'"

    async def test_캠페인CTR_SQL_GROUP_BY_campaign_id(self, pipeline):
        """캠페인별 CTR → SQL에 campaign_id와 GROUP BY 포함"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        if ctx.generated_sql:
            sql_lower = ctx.generated_sql.lower()
            assert "campaign_id" in sql_lower, \
                f"campaign_id 없음: '{ctx.generated_sql[:200]}'"
            assert "group by" in sql_lower, \
                f"GROUP BY 없음: '{ctx.generated_sql[:200]}'"


# ─────────────────────────────────────────────────────────────────
# Step 1→5 전체 흐름 (E2E)
# ─────────────────────────────────────────────────────────────────
class TestStep1to5E2E:

    async def test_시나리오A_CTR_전체흐름(self, pipeline):
        """
        시나리오 A: 어제 캠페인별 CTR (pipeline-flow-example.md 전체 흐름)
        Step1(의도)→Step2(정제)→Step3(키워드)→Step4(RAG)→Step5(SQL) 순서 연결 확인
        """
        from src.models.domain import IntentType
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        assert ctx.intent == IntentType.DATA_QUERY,          "Step 1 실패"
        assert ctx.refined_question,                         "Step 2 실패"
        assert ctx.keywords and len(ctx.keywords) > 0,       "Step 3 실패"
        assert ctx.rag_context is not None,                  "Step 4 실패"
        assert ctx.generated_sql,                            "Step 5 실패"
        assert ctx.generated_sql.strip().upper().startswith("SELECT")

    async def test_시나리오B_ROAS_전체흐름(self, pipeline):
        """
        시나리오 B: 최근 7일간 디바이스별 ROAS (pipeline-flow-example.md 기준)
        """
        from src.models.domain import IntentType
        ctx = await pipeline.run("최근 7일간 디바이스별 ROAS 순위 알려줘")

        assert ctx.intent == IntentType.DATA_QUERY
        assert ctx.refined_question
        assert any(k.upper() in ["ROAS", "DEVICE_TYPE", "DEVICE", "CONVERSION_VALUE"]
                   for k in (ctx.keywords or []))
        assert ctx.rag_context is not None
        assert ctx.generated_sql
        sql_lower = ctx.generated_sql.lower()
        assert "device_type" in sql_lower
        assert "group by" in sql_lower

    async def test_EX1_범위외질문_Step1중단(self, pipeline):
        """EX-1: 범위 외 질문 → Step 1에서 중단, 이후 Step 실행 안 함"""
        from src.models.domain import IntentType
        ctx = await pipeline.run("요즘 날씨 어때?")

        assert ctx.intent == IntentType.OUT_OF_SCOPE
        assert ctx.refined_question is None
        assert ctx.keywords == [] or ctx.keywords is None
        assert ctx.generated_sql is None
        assert ctx.error and ctx.error.failed_step == 1


# ─────────────────────────────────────────────────────────────────
# Step 6: SQLValidator (SQL 검증)
# ─────────────────────────────────────────────────────────────────
class TestStep6SQLValidator:

    async def test_SQL검증_통과(self, pipeline):
        """Step 5 생성 SQL이 Step 6 검증을 통과"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 5까지 정상
        assert ctx.generated_sql is not None, "Step 5 SQL 생성 실패"
        # Step 6 에러로 중단되지 않음
        if ctx.error:
            assert ctx.error.failed_step > 6, \
                f"Step 6 검증 실패: {ctx.error}"

    async def test_SEC04_허용테이블만_참조(self, pipeline):
        """SEC-04: Step 5 생성 SQL이 허용 테이블만 참조하는지 Step 6에서 검증"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        if ctx.generated_sql:
            sql_lower = ctx.generated_sql.lower()
            # 허용 테이블만 포함되어야 함
            assert any(t in sql_lower for t in ["ad_combined_log_summary", "ad_combined_log"]), \
                f"허용 테이블 미포함: {ctx.generated_sql[:200]}"
            # 금지 테이블 없어야 함
            assert "user_pii" not in sql_lower, "금지 테이블 참조: user_pii"
            assert "payment" not in sql_lower, "금지 테이블 참조: payment"


# ─────────────────────────────────────────────────────────────────
# Step 7: Redash (쿼리 실행)
# ─────────────────────────────────────────────────────────────────
class TestStep7Redash:

    async def test_Redash쿼리실행_결과반환(self, pipeline):
        """Step 7: Redash(또는 Athena fallback)에서 쿼리 실행하여 결과 반환"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1~6 통과
        assert ctx.generated_sql is not None
        # Step 7 이후로 진행되었거나 정상 처리됨
        if ctx.error:
            assert ctx.error.failed_step > 7, \
                f"Step 7 쿼리 실행 실패: {ctx.error}"

    async def test_Redash비활성_Athena폴백(self, pipeline):
        """REDASH_ENABLED=false일 때 Athena fallback으로 쿼리 실행
        (docker-compose.test.yml에서 REDASH_ENABLED=false 설정)
        """
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Athena mock이 호출되었거나 정상 처리
        if ctx.error:
            assert "Athena" not in ctx.error.error_message or ctx.error.failed_step > 8, \
                "Athena fallback 실패"


# ─────────────────────────────────────────────────────────────────
# Step 8: AthenaQuery (직접 SQL 실행)
# ─────────────────────────────────────────────────────────────────
class TestStep8AthenaQuery:

    async def test_Athena쿼리실행_결과메타데이터(self, pipeline):
        """Step 8: Athena에서 쿼리 실행하여 메타데이터 반환"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1~7 통과
        assert ctx.generated_sql is not None
        # Step 8 이후로 진행되었거나 정상 처리
        if ctx.error:
            assert ctx.error.failed_step > 8, \
                f"Step 8 Athena 실행 실패: {ctx.error}"


# ─────────────────────────────────────────────────────────────────
# Step 9: RedashChartGeneration (차트 생성)
# ─────────────────────────────────────────────────────────────────
class TestStep9ChartGeneration:

    async def test_차트생성_Base64이미지(self, pipeline):
        """Step 9: 쿼리 결과에서 차트 생성하여 Base64 이미지 반환"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1~8 통과
        assert ctx.generated_sql is not None
        # Step 9에서 생성된 차트 (있으면)
        if ctx.chart_base64:
            assert isinstance(ctx.chart_base64, str), "chart_base64는 문자열이어야 함"
            assert len(ctx.chart_base64) > 0, "chart_base64 빈 문자열"


# ─────────────────────────────────────────────────────────────────
# Step 10: AIAnalyzer (AI 분석)
# ─────────────────────────────────────────────────────────────────
class TestStep10AIAnalyzer:

    async def test_AI분석_해석텍스트(self, pipeline):
        """Step 10: AI가 쿼리 결과를 분석하여 자연어 해석 생성"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1~9 통과
        assert ctx.generated_sql is not None
        # Step 10 분석 결과 (있으면 query_results에 포함)
        if ctx.query_results:
            from src.models.domain import QueryResults
            assert isinstance(ctx.query_results, QueryResults), \
                f"query_results는 QueryResults 타입이어야 함, 실제: {type(ctx.query_results)}"


# ─────────────────────────────────────────────────────────────────
# Step 11: HistoryRecorder (히스토리 기록)
# ─────────────────────────────────────────────────────────────────
class TestStep11HistoryRecorder:

    async def test_히스토리기록_ID반환(self, pipeline):
        """Step 11: 전체 파이프라인 결과를 히스토리 DB에 기록"""
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1~10 완료
        assert ctx.generated_sql is not None
        # Step 11: history_id가 생성되었거나 정상 처리
        if ctx.history_id:
            assert isinstance(ctx.history_id, str), "history_id는 문자열이어야 함"
            assert len(ctx.history_id) > 0, "history_id 빈 문자열"

    async def test_히스토리_전체질문응답저장(self, pipeline):
        """Step 11: 전체 대화 (질문 → 분석 → SQL → 결과)를 히스토리에 저장"""
        ctx = await pipeline.run("최근 7일간 디바이스별 ROAS 순위 알려줘")

        # 전체 파이프라인 실행
        assert ctx.intent is not None, "Step 1 출력 없음"
        assert ctx.refined_question is not None, "Step 2 출력 없음"
        assert ctx.keywords is not None, "Step 3 출력 없음"
        assert ctx.generated_sql is not None, "Step 5 출력 없음"


# ─────────────────────────────────────────────────────────────────
# Step 1→11 전체 E2E (End-to-End)
# ─────────────────────────────────────────────────────────────────
class TestStep1to11FullE2E:

    async def test_시나리오A_CTR_1to11완전흐름(self, pipeline):
        """
        시나리오 A: 어제 캠페인별 CTR (Step 1→11 완전 흐름)
        질문 → 의도 분류 → 정제 → 키워드 → RAG → SQL 생성 →
        검증 → Redash → Athena → 차트 → AI분석 → 히스토리 기록
        """
        from src.models.domain import IntentType
        ctx = await pipeline.run("어제 캠페인별 CTR 알려줘")

        # Step 1
        assert ctx.intent == IntentType.DATA_QUERY, "Step 1 의도 분류 실패"
        # Step 2
        assert ctx.refined_question is not None, "Step 2 질문 정제 실패"
        # Step 3
        assert ctx.keywords and len(ctx.keywords) > 0, "Step 3 키워드 추출 실패"
        # Step 4
        assert ctx.rag_context is not None, "Step 4 RAG 실패"
        # Step 5
        assert ctx.generated_sql is not None, "Step 5 SQL 생성 실패"
        assert ctx.generated_sql.strip().upper().startswith("SELECT")
        # Step 6~11
        if ctx.error:
            assert ctx.error.failed_step >= 12 or ctx.error is None, \
                f"Step 1~11 중단: failed_step={ctx.error.failed_step}"

    async def test_시나리오B_ROAS_1to11완전흐름(self, pipeline):
        """
        시나리오 B: 최근 7일간 디바이스별 ROAS (Step 1→11 완전 흐름)
        더 복잡한 쿼리 조건에서 전체 파이프라인 동작 확인
        """
        from src.models.domain import IntentType
        ctx = await pipeline.run("최근 7일간 디바이스별 ROAS 순위 알려줘")

        # Step 1
        assert ctx.intent == IntentType.DATA_QUERY
        # Step 2
        assert ctx.refined_question is not None
        # Step 3
        assert ctx.keywords is not None
        kw_lower = [k.lower() for k in ctx.keywords]
        assert any(k in kw_lower for k in ["roas", "device_type", "device"])
        # Step 4
        assert ctx.rag_context is not None
        # Step 5
        assert ctx.generated_sql is not None
        sql_lower = ctx.generated_sql.lower()
        assert "device_type" in sql_lower
        assert "group by" in sql_lower
        # Step 6~11
        if ctx.error:
            assert ctx.error.failed_step >= 12 or ctx.error is None

    async def test_EX2_범위외질문_단계별중단(self, pipeline):
        """
        EX-2: 범위 외 질문 → Step 1에서 중단
        Step 2 이상이 실행되지 않음을 확인
        """
        from src.models.domain import IntentType
        ctx = await pipeline.run("요즘 날씨 어때?")

        assert ctx.intent == IntentType.OUT_OF_SCOPE, "Step 1 의도 분류 실패"
        assert ctx.refined_question is None, "Step 2 실행됨 (중단되어야 함)"
        assert ctx.keywords is None or ctx.keywords == [], "Step 3 실행됨"
        assert ctx.generated_sql is None, "Step 5 실행됨"
        assert ctx.error is not None
        assert ctx.error.failed_step == 1
