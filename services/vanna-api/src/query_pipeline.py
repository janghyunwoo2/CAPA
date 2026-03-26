"""
QueryPipeline — 11-Step 파이프라인 오케스트레이터
설계 문서 §2.3 기준 (T1)

Step 1.  IntentClassifier    → SQL_QUERY / GENERAL / OUT_OF_SCOPE
Step 2.  QuestionRefiner     → 정제된 질문
Step 3.  KeywordExtractor    → 도메인 키워드 리스트
Step 4.  RAGRetriever        → 스키마 + Few-shot + 문서
Step 5.  SQLGenerator        → Vanna + Claude SQL 생성
Step 6.  SQLValidator        → EXPLAIN 검증 + sqlglot AST
Step 7.  RedashQueryCreator  → Redash query_id 획득
Step 8.  RedashExecutor      → 실행 + 폴링 대기
Step 9.  ResultCollector     → rows/columns 수집
Step 10. AIAnalyzer          → 인사이트 + 차트 유형 결정
Step 10.5 ChartRenderer      → matplotlib PNG → Base64
Step 11. HistoryRecorder     → 질문-SQL-결과 이력 저장
"""

import logging
import os
from datetime import datetime, timezone, timedelta

_KST = timezone(timedelta(hours=9))
from typing import Any, Optional

import boto3
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from vanna.anthropic import Anthropic_Chat
from vanna.chromadb import ChromaDB_VectorStore
from vanna.utils import deterministic_uuid

# 한국어 특화 임베딩 모델 (영어 전용 all-MiniLM-L6-v2 대체)
_KO_EMBEDDING_FUNCTION = SentenceTransformerEmbeddingFunction(
    model_name="jhgan/ko-sroberta-multitask"
)

from .models.domain import IntentType, PipelineContext, PipelineError
from .models.redash import RedashConfig
from .pipeline.intent_classifier import IntentClassifier
from .pipeline.question_refiner import QuestionRefiner
from .pipeline.keyword_extractor import KeywordExtractor
from .pipeline.rag_retriever import RAGRetriever
from .pipeline.sql_generator import SQLGenerator, SQLGenerationError
from .pipeline.sql_validator import SQLValidator
from .pipeline.ai_analyzer import AIAnalyzer
from .pipeline.chart_renderer import ChartRenderer
from .pipeline.conversation_history_retriever import ConversationHistoryRetriever
from .redash_client import (
    RedashClient,
    RedashAPIError,
    RedashTimeoutError,
    run_athena_fallback,
)
from .history_recorder import HistoryRecorder

logger = logging.getLogger(__name__)

PHASE2_RAG_ENABLED = os.getenv("PHASE2_RAG_ENABLED", "false").lower() == "true"
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
MULTI_TURN_ENABLED = os.getenv("MULTI_TURN_ENABLED", "false").lower() == "true"
# SCHEMA_MAPPER_ENABLED 제거 — SchemaMapper 삭제 (Design §3.2)
SELF_CORRECTION_ENABLED = os.getenv("SELF_CORRECTION_ENABLED", "false").lower() == "true"
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))

# Self-Correction 재시도 가능 에러 코드 (보안 차단은 제외)
_RETRYABLE_CORRECTION_ERRORS = frozenset({
    "SQL_PARSE_ERROR",
    "SQL_DISALLOWED_TABLE",
    "SQL_NO_TABLE",
})


class _VannaAthena(ChromaDB_VectorStore, Anthropic_Chat):
    """환경변수 기반 자동 초기화용 내부 Vanna 구현체

    ChromaDB 저장 방식 오버라이드:
    - 기본 Vanna: question+SQL 전체 JSON을 하나의 document로 임베딩 → 검색 불일치
    - 오버라이드: question만 document로 임베딩, SQL은 metadata로 분리 → 질문 유사도 정확도 향상
    """

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)
        self._ensure_cosine_collections()

    def _ensure_cosine_collections(self) -> None:
        """sql-collection, documentation-collection의 hnsw:space=cosine 보장.

        ChromaDB_VectorStore 초기화 후 L2로 생성된 컬렉션을 cosine으로 교체.
        seed_chromadb.py에서 reset_collections() 선행 후 호출되므로,
        통상 이미 삭제된 상태 → 신규 생성 시 cosine 적용됨.
        Design §2.1 FR-PRO-01 기준.
        """
        client = getattr(self, "chroma_client", None)
        if client is None:
            return
        for col_attr in ["sql_collection", "documentation_collection"]:
            col = getattr(self, col_attr, None)
            if col is None:
                continue
            if col.metadata and col.metadata.get("hnsw:space") == "cosine":
                continue  # 이미 cosine
            try:
                name = col.name
                client.delete_collection(name)
                new_col = client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                    embedding_function=_KO_EMBEDDING_FUNCTION,
                )
                setattr(self, col_attr, new_col)
                logger.info(f"{name}: cosine 메트릭으로 재생성 완료")
            except Exception as e:
                logger.warning(f"{col_attr} cosine 재생성 실패 (무시): {e}")

    def add_question_sql(self, question: str, sql: str, tables: list[str] | None = None, **kwargs) -> str:
        """question만 document로 저장, SQL과 tables는 metadata로 분리.

        tables: 해당 QA 예제가 참조하는 테이블 목록 — DDL 역추적에 사용.
        ChromaDB metadata는 str만 허용하므로 str(list)로 직렬화.
        Design §3.2 기준.
        """
        id = deterministic_uuid(question + sql) + "-sql"
        metadata: dict = {"sql": sql}
        if tables:
            metadata["tables"] = str(tables)
        self.sql_collection.add(
            documents=question,
            metadatas=[metadata],
            ids=[id],
        )
        return id

    def get_similar_question_sql(self, question: str, **kwargs) -> list:
        """metadata에서 SQL을 꺼내 {question, sql, score, tables} dict 리스트로 반환.

        distance 값을 score로 변환:
        - cosine distance: 0=동일, 1=직교 (정규화 벡터 기준)
        - score = max(0.0, 1.0 - distance)  — cosine similarity 직접 반환
        Design §2.2 FR-PRO-02 기준.
        """
        # Phase2 활성화 시 n_results 확대 (DDL 역추적 후보 풀 + Few-shot 증가)
        # Design §5.1 FR-PRO-07 기준
        n_results = self.n_results_sql
        if PHASE2_RAG_ENABLED:
            n_results = max(n_results, 20)

        results = self.sql_collection.query(
            query_texts=[question],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        if not results or "documents" not in results:
            return []

        docs = results["documents"][0] if results["documents"] else []
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {
                "question": doc,
                "sql": meta.get("sql", ""),
                "tables": meta.get("tables", ""),   # DDL 역추적용
                "score": max(0.0, 1.0 - dist),      # cosine similarity
            }
            for doc, meta, dist in zip(docs, metas, distances)
            if meta.get("sql")
        ]

    def get_related_ddl_with_score(self, question: str, **kwargs) -> list[dict]:
        """DDL을 ChromaDB distance 기반 score와 함께 반환.

        Returns:
            list of {"text": str, "score": float}  (score = 1/(1+distance))
        """
        try:
            n_results = getattr(self, "n_results_ddl", 10)
            results = self.ddl_collection.query(
                query_texts=[question],
                n_results=n_results,
                include=["documents", "distances"],
            )
            if not results or "documents" not in results:
                return []
            docs = results["documents"][0] if results["documents"] else []
            distances = results.get("distances", [[]])[0]
            return [
                {"text": doc, "score": 1.0 / (1.0 + dist)}
                for doc, dist in zip(docs, distances)
            ]
        except Exception:
            fallback = self.get_related_ddl(question=question)
            return [{"text": doc, "score": 1.0} for doc in (fallback or [])]

    def get_related_documentation_with_score(self, question: str, **kwargs) -> list[dict]:
        """Documentation을 ChromaDB cosine distance 기반 score와 함께 반환.

        Returns:
            list of {"text": str, "score": float}  (score = max(0.0, 1.0 - distance))
        Design §2.2 FR-PRO-02 기준.
        """
        try:
            n_results = getattr(self, "n_results_documentation", 10)
            results = self.documentation_collection.query(
                query_texts=[question],
                n_results=n_results,
                include=["documents", "distances"],
            )
            if not results or "documents" not in results:
                return []
            docs = results["documents"][0] if results["documents"] else []
            distances = results.get("distances", [[]])[0]
            return [
                {"text": doc, "score": max(0.0, 1.0 - dist)}  # cosine similarity
                for doc, dist in zip(docs, distances)
            ]
        except Exception:
            fallback = self.get_related_documentation(question=question)
            return [{"text": doc, "score": 1.0} for doc in (fallback or [])]


class QueryPipeline:
    """11-Step Text-to-SQL 파이프라인 오케스트레이터"""

    def __init__(
        self,
        vanna_instance: Any = None,
        anthropic_api_key: Optional[str] = None,
        athena_client: Any = None,
        database: Optional[str] = None,
        workgroup: Optional[str] = None,
        s3_staging_dir: Optional[str] = None,
        redash_config: Optional[RedashConfig] = None,
        history_recorder: Optional[HistoryRecorder] = None,
        llm_model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        # 환경변수 fallback
        anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        database = database or os.getenv("ATHENA_DATABASE", "capa_db")
        workgroup = workgroup or os.getenv("ATHENA_WORKGROUP", "capa-workgroup")
        s3_staging_dir = s3_staging_dir or os.getenv("S3_STAGING_DIR", "")
        aws_region = os.getenv("AWS_REGION", "ap-northeast-2")

        if athena_client is None:
            athena_client = boto3.client("athena", region_name=aws_region)

        if vanna_instance is None:
            chroma_host = os.getenv(
                "CHROMA_HOST", "chromadb.chromadb.svc.cluster.local"
            )
            chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
            chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            vanna_instance = _VannaAthena(
                config={
                    "api_key": anthropic_api_key,
                    "model": llm_model,
                    "client": chroma_client,
                    "embedding_function": _KO_EMBEDDING_FUNCTION,
                }
            )

        self._vanna = vanna_instance
        self._api_key = anthropic_api_key
        self._athena = athena_client
        self._database = database
        self._workgroup = workgroup
        self._s3_staging_dir = s3_staging_dir
        self._redash_config = redash_config
        self._recorder = history_recorder or HistoryRecorder()
        self._model = llm_model

        # Anthropic 클라이언트 — QuestionRefiner(멀티턴) + Phase 2(LLM 필터/SQL 생성) 공용
        import anthropic as _anthropic
        _anthropic_client = _anthropic.Anthropic(api_key=anthropic_api_key)

        # 컴포넌트 초기화
        self._intent_classifier = IntentClassifier(
            api_key=anthropic_api_key, model=llm_model
        )
        self._question_refiner = QuestionRefiner(
            llm_client=_anthropic_client, model=llm_model
        )
        self._keyword_extractor = KeywordExtractor(
            api_key=anthropic_api_key, model=llm_model
        )
        # Phase 2: PHASE2_RAG_ENABLED=true 시 retrieve_v2 사용 (Reranker 영구 비활성화)
        # Design §3.2: Reranker 주석처리, _reranker=None 고정
        if PHASE2_RAG_ENABLED:
            _phase2_client = _anthropic_client
            # 주석처리: Reranker 영구 비활성화 (Design §3.2)
            # if RERANKER_ENABLED:
            #     from .pipeline.reranker import CrossEncoderReranker
            #     _reranker = CrossEncoderReranker()
            # else:
            #     _reranker = None
            _reranker = None
            logger.info("Reranker 영구 비활성화 (Design §3.2)")
        else:
            _reranker = None
            _phase2_client = None                # Phase 1: Vanna 경로 유지

        self._rag_retriever = RAGRetriever(
            vanna_instance=vanna_instance,
            reranker=_reranker,
            anthropic_client=_phase2_client,
        )

        # Step 3.5 제거: SchemaMapper 삭제 (Design §3.2)
        # if SCHEMA_MAPPER_ENABLED:
        #     from .pipeline.schema_mapper import SchemaMapper
        #     self._schema_mapper: Optional[Any] = SchemaMapper()
        # else:
        #     self._schema_mapper = None
        self._sql_generator = SQLGenerator(
            vanna_instance=vanna_instance,
            anthropic_client=_phase2_client,   # Phase 1: None(Vanna 경로), Phase 2: client
            model=llm_model,
        )
        self._sql_validator = SQLValidator(
            athena_client=athena_client,
            database=database,
            workgroup=workgroup,
            s3_staging_dir=s3_staging_dir,
        )
        self._ai_analyzer = AIAnalyzer(api_key=anthropic_api_key, model=llm_model)
        self._chart_renderer = ChartRenderer()

        # Step 0: 멀티턴 대화 이력 조회 (FR-20, MULTI_TURN_ENABLED=true 시)
        if MULTI_TURN_ENABLED:
            _dynamodb = boto3.resource("dynamodb", region_name=aws_region)
            self._conversation_retriever = ConversationHistoryRetriever(_dynamodb)
        else:
            self._conversation_retriever = None

    async def _generate_and_validate_with_correction(
        self,
        ctx: "PipelineContext",
    ) -> tuple[str, "ValidationResult"]:
        """Step 5 + 6 + 6.5: SQL 생성 → 검증 → Self-Correction Loop.

        SELF_CORRECTION_ENABLED=true 이고 검증 실패 에러가 재시도 가능한 경우에만
        generate_with_error_feedback()를 통해 최대 MAX_CORRECTION_ATTEMPTS회 재시도.
        보안 차단 에러(SQL_BLOCKED_KEYWORD 등)는 재시도하지 않음.
        """
        question = ctx.refined_question or ctx.original_question
        rag_context = getattr(ctx, "rag_context", None)
        conv_history = ctx.conversation_history if MULTI_TURN_ENABLED else None

        sql = self._sql_generator.generate(
            question=question,
            rag_context=rag_context,
            conversation_history=conv_history,
        )
        validation = self._sql_validator.validate(sql)

        if not SELF_CORRECTION_ENABLED or validation.is_valid:
            return sql, validation

        for attempt in range(1, MAX_CORRECTION_ATTEMPTS + 1):
            error_code = getattr(validation, "error_code", "")
            if error_code not in _RETRYABLE_CORRECTION_ERRORS:
                logger.info(
                    f"Self-Correction 불가 (error_code={error_code}) — 원래 SQL 반환"
                )
                break

            logger.info(
                f"Self-Correction 시도 {attempt}/{MAX_CORRECTION_ATTEMPTS}: "
                f"{validation.error_message}"
            )
            try:
                sql = self._sql_generator.generate_with_error_feedback(
                    question=question,
                    failed_sql=sql,
                    error_message=validation.error_message or "",
                    rag_context=rag_context,
                    conversation_history=conv_history,
                )
            except SQLGenerationError as e:
                logger.warning(f"Self-Correction {attempt}회 생성 실패: {e}")
                break

            validation = self._sql_validator.validate(sql)
            if validation.is_valid:
                logger.info(f"Self-Correction {attempt}회 만에 성공")
                break

        return sql, validation

    async def run(
        self,
        question: str,
        slack_user_id: str = "",
        slack_channel_id: str = "",
        conversation_id: str = "",
    ) -> PipelineContext:
        """파이프라인을 실행하고 PipelineContext를 반환.
        어느 단계에서 실패해도 ctx.error에 실패 정보를 담아 반환 (FR-09).
        """
        ctx = PipelineContext(
            original_question=question,
            slack_user_id=slack_user_id,
            slack_channel_id=slack_channel_id,
            session_id=conversation_id or None,
        )

        # Step 0: 멀티턴 대화 이력 조회 (FR-20)
        if MULTI_TURN_ENABLED and ctx.session_id and self._conversation_retriever:
            ctx = self._conversation_retriever.retrieve(ctx)
            logger.info(
                f"Step 0 대화 이력: session_id={ctx.session_id}, turn={ctx.turn_number}, history={len(ctx.conversation_history)}건"
            )

        # Step 1: 의도 분류
        ctx.intent = self._intent_classifier.classify(question)
        logger.info(f"Step 1 의도 분류: {ctx.intent}")

        if ctx.intent == IntentType.OUT_OF_SCOPE:
            ctx.error = PipelineError(
                failed_step=1,
                step_name="의도 분류",
                error_code="INTENT_OUT_OF_SCOPE",
                error_message="광고 데이터 분석과 관련된 질문만 답변할 수 있습니다.",
            )
            return ctx

        if ctx.intent == IntentType.GENERAL:
            ctx.error = PipelineError(
                failed_step=1,
                step_name="의도 분류",
                error_code="INTENT_GENERAL",
                error_message="데이터 조회가 필요하지 않은 질문입니다. 직접 답변이 필요하면 다시 질문해 주세요.",
            )
            return ctx

        # Step 2: 질문 정제
        ctx.refined_question = self._question_refiner.refine(
            question,
            conversation_history=ctx.conversation_history
            if MULTI_TURN_ENABLED
            else None,
        )
        logger.info(f"Step 2 정제된 질문: {ctx.refined_question}")

        # Step 3: 키워드 추출 (멀티턴 시 이전 대화 맥락 포함)
        ctx.keywords = self._keyword_extractor.extract(
            ctx.refined_question,
            conversation_history=ctx.conversation_history if MULTI_TURN_ENABLED else None,
        )
        logger.info(f"Step 3 키워드: {ctx.keywords}")

        # Step 3.5 제거: SchemaMapper 삭제 (Design §3.2)
        # if SCHEMA_MAPPER_ENABLED and self._schema_mapper is not None:
        #     ctx.schema_hint = self._schema_mapper.map(ctx.keywords)

        # Step 4: RAG 검색 (Phase 2: PHASE2_RAG_ENABLED=true 시 3단계 RAG 사용)
        if PHASE2_RAG_ENABLED:
            ctx.rag_context = await self._rag_retriever.retrieve_v2(
                question=ctx.refined_question,
                keywords=ctx.keywords,
            )
        else:
            ctx.rag_context = self._rag_retriever.retrieve(
                question=ctx.refined_question,
                keywords=ctx.keywords,
            )

        # Step 5+6: SQL 생성 + 검증 (Self-Correction Loop 포함)
        try:
            ctx.generated_sql, ctx.validation_result = (
                await self._generate_and_validate_with_correction(ctx)
            )
        except SQLGenerationError as e:
            logger.error(f"Step 5 SQL 생성 실패: {e}")
            ctx.error = PipelineError(
                failed_step=5,
                step_name="SQL 생성",
                error_code="SQL_GENERATION_FAILED",
                error_message="SQL을 생성할 수 없습니다. 질문을 다시 표현해 주세요.",
            )
            return ctx

        if not ctx.validation_result.is_valid:
            logger.warning(
                f"Step 6 SQL 검증 실패: {ctx.validation_result.error_message}"
            )
            ctx.error = PipelineError(
                failed_step=6,
                step_name="SQL 검증",
                error_code="SQL_VALIDATION_FAILED",
                error_message=ctx.validation_result.error_message
                or "SQL 검증에 실패했습니다.",
                generated_sql=ctx.generated_sql,
            )
            return ctx

        validated_sql = ctx.validation_result.normalized_sql or ctx.generated_sql

        # Step 7~9: Redash 실행 또는 Athena 폴백
        redash_enabled = (
            self._redash_config is not None
            and self._redash_config.enabled
            and os.getenv("REDASH_ENABLED", "true").lower() == "true"
        )

        if redash_enabled and self._redash_config:
            ctx = await self._run_redash_steps(ctx, validated_sql)
        else:
            ctx = await self._run_athena_fallback(ctx, validated_sql)

        if ctx.error:
            return ctx

        # Step 10: AI 분석
        if ctx.query_results:
            ctx.analysis = self._ai_analyzer.analyze(
                question=ctx.refined_question or question,
                sql=validated_sql,
                query_results=ctx.query_results,
            )

            # Step 10.5: 차트 렌더링
            if ctx.analysis and ctx.analysis.chart_type.value != "none":
                ctx.chart_base64 = self._chart_renderer.render(
                    query_results=ctx.query_results,
                    chart_type=ctx.analysis.chart_type,
                )

        # Step 11: 이력 저장
        try:
            ctx.history_id = self._recorder.record(ctx)
        except Exception as e:
            logger.error(f"Step 11 이력 저장 실패 (사용자 영향 없음): {e}")

        elapsed = (datetime.utcnow() - ctx.started_at).total_seconds()
        logger.info(f"파이프라인 완료: {elapsed:.2f}초")
        return ctx

    async def _run_redash_steps(
        self, ctx: PipelineContext, sql: str
    ) -> PipelineContext:
        """Step 7~9: Redash 경유 실행"""
        redash = RedashClient(config=self._redash_config)  # type: ignore[arg-type]

        # Step 7: Redash 쿼리 생성
        try:
            query_name = f"CAPA: {ctx.refined_question or ctx.original_question} [{datetime.now(_KST).strftime('%Y-%m-%d %H:%M')}]"
            ctx.redash_query_id = await redash.create_query(
                sql=sql,
                name=query_name,
            )
            ctx.redash_url = redash.build_public_url(ctx.redash_query_id)
        except RedashAPIError as e:
            logger.error(f"Step 7 Redash 쿼리 생성 실패: {e}")
            ctx.error = PipelineError(
                failed_step=7,
                step_name="Redash 쿼리 생성",
                error_code="REDASH_ERROR",
                error_message="Redash에 쿼리를 저장하는 중 오류가 발생했습니다.",
                generated_sql=sql,
            )
            return ctx

        # Step 8: Redash 실행 + 폴링
        try:
            job_id = await redash.execute_query(ctx.redash_query_id)
            ctx.redash_job_id = job_id
            ctx.redash_query_result_id = await redash.poll_job(job_id)
        except RedashTimeoutError:
            ctx.error = PipelineError(
                failed_step=8,
                step_name="Redash 실행",
                error_code="QUERY_TIMEOUT",
                error_message="쿼리 실행 시간이 초과되었습니다 (300초). 조회 범위를 좁혀 다시 시도해 주세요.",
                generated_sql=sql,
            )
            return ctx
        except RedashAPIError as e:
            logger.error(f"Step 8 Redash 실행 실패: {e}")
            ctx.error = PipelineError(
                failed_step=8,
                step_name="Redash 실행",
                error_code="REDASH_ERROR",
                error_message="Redash 쿼리 실행 중 오류가 발생했습니다.",
                generated_sql=sql,
            )
            return ctx

        # Step 9: 결과 수집
        try:
            ctx.query_results = await redash.get_results(ctx.redash_query_id)
        except RedashAPIError as e:
            logger.error(f"Step 9 결과 수집 실패: {e}")
            ctx.error = PipelineError(
                failed_step=9,
                step_name="결과 수집",
                error_code="REDASH_ERROR",
                error_message="쿼리 결과를 가져오는 중 오류가 발생했습니다.",
                generated_sql=sql,
            )

        return ctx

    async def _run_athena_fallback(
        self, ctx: PipelineContext, sql: str
    ) -> PipelineContext:
        """Step 9 폴백: Athena 직접 실행 (REDASH_ENABLED=false)"""
        try:
            ctx.query_results = await run_athena_fallback(
                sql=sql,
                athena_client=self._athena,
                database=self._database,
                s3_staging_dir=self._s3_staging_dir,
                workgroup=self._workgroup,
            )
        except RedashTimeoutError:
            ctx.error = PipelineError(
                failed_step=9,
                step_name="Athena 직접 실행",
                error_code="QUERY_TIMEOUT",
                error_message="쿼리 실행 시간이 초과되었습니다. 조회 범위를 좁혀 다시 시도해 주세요.",
                generated_sql=sql,
            )
        except RedashAPIError as e:
            logger.error(f"Step 9 Athena 폴백 실패: {e}")
            ctx.error = PipelineError(
                failed_step=9,
                step_name="Athena 직접 실행",
                error_code="ATHENA_EXECUTION_FAILED",
                error_message="데이터 조회 중 오류가 발생했습니다.",
                generated_sql=sql,
            )

        return ctx
