# [Design] Text-To-SQL — Phase 2 RAG 고도화

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | text-to-sql Phase 2 RAG 고도화 |
| **작성일** | 2026-03-19 |
| **담당** | t1 |
| **Phase** | Design — **Phase 2 (RAG 품질 강화) 범위** |
| **참고 문서** | `docs/t1/text-to-sql/01-plan/features/text-to-sql.plan.md` §7 Phase 2, §12.4 |
| **선행 문서** | `docs/t1/text-to-sql/02-design/features/phase-1-text-to-sql.design.md` |
| **팀 작성** | rag-upgrade-design 팀 (CTO lead + enterprise-expert + infra-architect) |

### Value Delivered (4관점)

| 관점 | Phase 1 | Phase 2 변경 |
|------|---------|-------------|
| **Problem** | 기본 벡터 검색만으로 노이즈 포함 컨텍스트가 LLM에 전달, 즉시 학습으로 품질 미검증 데이터 축적, 동기 응답으로 300초 점유 | 3단계 RAG로 노이즈 제거, 배치 검증으로 품질 보장, 비동기 응답으로 리소스 효율화 |
| **Solution** | 11-Step 파이프라인 (벡터검색 1단계) | Step 4를 3단계 RAG(벡터→Reranker→LLM)로 확장, Airflow DAG 배치 학습, BackgroundTasks 비동기 |
| **Function UX Effect** | Slack에서 최대 300초 대기 후 응답 | 즉시 "처리 중" 응답 + 완료 시 자동 알림, 중복 쿼리 재사용으로 응답 속도 향상 |
| **Core Value** | 수동 시딩 기반 ChromaDB + 즉시 피드백 학습 | 자동화된 품질 관리 파이프라인으로 SQL 정확도 85% 이상 달성 |

### Phase 2 KPI 목표 (Plan §10 기준)

| 지표 | Phase 1 목표 | Phase 2 목표 |
|------|-------------|-------------|
| SQL 정확도 | >= 70% | **>= 85%** |
| EXPLAIN 검증 통과율 | >= 85% | **>= 95%** |
| SQL 실행 실패율 | <= 15% | **<= 5%** |
| 전체 평균 응답시간 | <= 30초 | **<= 25초** |
| RAG 검색 시간 | <= 3초 | **<= 5초** (Reranker 추가 허용) |
| 피드백 루프 성공률 | - (수동) | **>= 95%** |
| ChromaDB 자동 누적 | 수동 50건+ | **200건+/월** |

---

## 1. 설계 개요

### 1.1 범위

본 설계서는 **Phase 2 (RAG 품질 강화) 범위**를 다룬다. Phase 1 설계서(`phase-1-text-to-sql.design.md`)의 11-Step 파이프라인을 기반으로, Plan 문서의 FR-12~FR-18 기능 요구사항을 구현하기 위한 아키텍처 변경, 신규 컴포넌트, 인프라 추가 설계를 포함한다.

### 1.2 설계 원칙

1. **Phase 1 호환성**: 기존 11-Step 파이프라인 구조를 유지하며 점진적 확장
2. **품질 우선**: 즉시 학습을 폐기하고 검증된 데이터만 ChromaDB에 반영
3. **비동기 전환**: 사용자 경험과 서버 리소스 효율을 동시에 개선
4. **운영 자동화**: Airflow DAG으로 ChromaDB 관리를 코드화
5. **Feature Flag 기반 점진 전환**: 모든 Phase 2 기능은 환경변수 플래그로 on/off 가능

### 1.3 대상 FR/NFR

> **Phase 1 완료 사항 (참조)**: FR-13a (비즈니스 용어 초기 시딩), FR-14a (Athena 특화 지식 초기 시딩), FR-15a (정책 데이터 초기 시딩) — Phase 1에서 ChromaDB 1회 수동 시딩 완료. 학습 데이터 **추가**는 Phase 1 피드백 루프에서 구현됨. Phase 2(FR-13~15)에서 **삭제** (`DELETE /training-data/{id}`) 추가로 지속 관리 체계 완성.

| ID | 요구사항 | 핵심 변경 |
|----|---------|----------|
| FR-11 | History 저장소 전환 | JSON Lines → DynamoDB |
| FR-12 | 3단계 RAG 파이프라인 | Step 4 확장 (벡터→Reranker→LLM) |
| FR-13 | 비즈니스 용어 사전 지속 관리 | Phase 1(FR-13a) 시딩 완료 → `DELETE /training-data/{id}` 삭제 관리 추가 |
| FR-14 | Athena 특화 지식 지속 관리 | Phase 1(FR-14a) 시딩 완료 → `DELETE /training-data/{id}` 삭제 관리 추가 |
| FR-15 | 정책 데이터 지속 관리 | Phase 1(FR-15a) 시딩 완료 → `DELETE /training-data/{id}` 삭제 관리 추가 |
| FR-16 | 피드백 루프 품질 제어 | 즉시 학습 폐기 → Airflow 배치 검증 |
| FR-18 | Airflow DAG 연동 | `capa_chromadb_refresh` DAG 신규 (피드백 배치 처리) |
| FR-19 | 비동기 쿼리 처리 | BackgroundTasks: POST /query → 202 + 폴링 |
| NFR-05 | SQL 생성 프롬프트 영어 XML 구조화 | Phase 1 원칙 유지 + 3단계 RAG 컨텍스트 동일 적용 |

---

## 2. Phase 2 전체 파이프라인 개요

### 2.1 Phase 1 대비 파이프라인 변경점

Phase 1의 11-Step 파이프라인은 그대로 유지하되, 아래 항목이 변경/추가된다.

| Step | Phase 1 | Phase 2 변경 내용 |
|------|---------|-----------------|
| Step 4 (RAG 검색) | 기본 벡터 검색 1단계 | **3단계 확장** (벡터 → Reranker → LLM 선별) |
| Step 11 (History 저장) | 로컬 JSON Lines | **DynamoDB** (TTL 기반) |
| Step 13 (피드백 처리) | 👍 시 즉시 `vanna.train()` | **DynamoDB 저장만** → Airflow 배치 검증 (FR-16) |
| **전체 API** | 동기 응답 (최대 300초 점유) | **BackgroundTasks 비동기** (202 Accepted + 폴링) |
| [신규] Airflow DAG | 없음 | 매주 월 09:00 KST 검증 배치 (FR-18) |

### 2.2 Phase 2 전체 구조도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                                   │
│                                                                              │
│  ┌──────────────┐          ┌──────────────────────────────────────────┐      │
│  │  Slack Bot   │──HTTP──▶│  FastAPI (vanna-api)                      │      │
│  │ (Socket Mode)│◀─HTTP───│  POST /query → 202 Accepted + task_id    │      │
│  │              │          │  GET /query/{task_id} ← 폴링             │      │
│  │              │          │  POST /feedback                          │      │
│  └──────────────┘          └──────────────┬───────────────────────────┘      │
└───────────────────────────────────────────┼──────────────────────────────────┘
                                            │
┌───────────────────────────────────────────┼──────────────────────────────────┐
│                         BUSINESS LAYER    │                                   │
│                                           ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │                QueryPipeline (BackgroundTasks)                    │        │
│  │                                                                   │        │
│  │  Step 1.  IntentClassifier                                        │        │
│  │  Step 2.  QuestionRefiner                                         │        │
│  │  Step 3.  KeywordExtractor                                        │        │
│  │  Step 4.  RAGRetriever [변경: 3단계 RAG]                         │        │
│  │    ├─ Step 4-1. 벡터 유사도 검색 (ChromaDB)                      │        │
│  │    ├─ Step 4-2. Reranker 재평가 (Cross-Encoder) [신규]           │        │
│  │    └─ Step 4-3. LLM 최종 선별 (Claude) [신규]                    │        │
│  │  Step 5.  SQLGenerator                                            │        │
│  │  Step 6.  SQLValidator                                            │        │
│  │  Step 7.  RedashQueryCreator [변경: 중복 쿼리 재사용]            │        │
│  │  Step 8.  RedashExecutor                                          │        │
│  │  Step 9.  ResultCollector                                         │        │
│  │  Step 10. AIAnalyzer                                              │        │
│  │  Step 10.5 ChartRenderer                                          │        │
│  │  Step 11. HistoryRecorder [변경: DynamoDB]                        │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                                                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐              │
│  │ RedashClient   │  │ AthenaClient   │  │ FeedbackManager    │              │
│  │ [변경: 해시]   │  │ (boto3)        │  │ [변경: DynamoDB]   │              │
│  └────────────────┘  └────────────────┘  └────────────────────┘              │
│                                                                               │
│  ┌────────────────────┐  ┌────────────────────┐                              │
│  │ CrossEncoderReranker│  │ AsyncQueryManager  │ ← [신규]                    │
│  │ [신규]              │  │ [신규]              │                              │
│  └────────────────────┘  └────────────────────┘                              │
└───────────────────────────────────────────────────────────────────────────────┘
                                            │
┌───────────────────────────────────────────┼───────────────────────────────────┐
│                         DATA LAYER        │                                    │
│                                           ▼                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  ChromaDB    │  │  AWS Athena  │  │  Redash      │  │  DynamoDB    │      │
│  │  (벡터DB)   │  │  (쿼리엔진)  │  │  (BI/영속화) │  │  [신규]      │      │
│  │              │  │              │  │              │  │  - History   │      │
│  │  - DDL 스키마│  │  - EXPLAIN   │  │  - Query 저장│  │  - Feedback  │      │
│  │  - Few-shot  │  │  - S3 결과   │  │  - 실행/폴링 │  │              │      │
│  │  - 용어 사전 │  │              │  │  - 시각화    │  │              │      │
│  │  - 정책 문서 │  │              │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                                                │
│  ┌──────────────────────┐                                                      │
│  │  Airflow DAG [신규]  │                                                      │
│  │  capa_chromadb_refresh│                                                     │
│  │  매주 월 09:00 KST   │                                                      │
│  └──────────────────────┘                                                      │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. FR-12: 3단계 RAG 파이프라인 설계

> **Phase 1 대비 변경점**: `RAGRetriever.retrieve()` 메서드가 1단계 벡터 검색에서 3단계(벡터→Reranker→LLM)로 확장됨. 신규 `CrossEncoderReranker` 클래스 추가.

### 3.1 전체 흐름

```
[정제된 질문 + 키워드]
        │
        ▼  Step 4-1
[벡터 유사도 검색 — ChromaDB]
  - vanna.get_related_ddl()          → DDL 후보 N개 (기본 N=5)
  - vanna.get_related_documentation() → Doc 후보 N개
  - vanna.get_similar_question_sql()  → SQL 예제 후보 N개
  - 출력: CandidateDocument 리스트 (text, source, score)
        │
        ▼  Step 4-2
[Reranker 재평가 — Cross-Encoder]
  - 모델: cross-encoder/ms-marco-MiniLM-L-6-v2 (sentence-transformers)
  - 입력: (질문, 후보 문서) 쌍
  - 출력: relevance_score 재계산 → 내림차순 정렬
  - 상위 K개 유지 (기본 K=5)
        │
        ▼  Step 4-3
[LLM 최종 선별 — Claude]
  - 입력: Reranker 상위 K개 문서
  - 프롬프트: "아래 문서 중 SQL 생성에 실제로 도움이 되는 것만 선택하라. 0개도 허용."
  - 출력: 선별된 RAGContext (ddl_context, documentation_context, sql_examples)
  - 0개 선별 시: 빈 RAGContext → LLM 자체 지식으로 SQL 생성
```

### 3.2 데이터 모델

```python
# src/models/rag.py (신규)
from pydantic import BaseModel
from typing import Literal, Optional

class CandidateDocument(BaseModel):
    """3단계 RAG 후보 문서"""
    text: str
    source: Literal["ddl", "documentation", "sql_example"]
    initial_score: float       # Step 4-1 벡터 유사도 점수
    rerank_score: Optional[float] = None  # Step 4-2 Cross-Encoder 점수

class RerankResult(BaseModel):
    """Step 4-2 Reranker 출력"""
    candidates: list[CandidateDocument]  # rerank_score 기준 내림차순
    top_k: int

class LLMFilterResult(BaseModel):
    """Step 4-3 LLM 선별 출력"""
    selected_indices: list[int]  # 선별된 문서 인덱스
    reason: str                  # 선별 근거 (디버깅용)
```

### 3.3 Reranker 컴포넌트

```python
# src/pipeline/reranker.py (신규)
from sentence_transformers import CrossEncoder
import logging
from ..models.rag import CandidateDocument

logger = logging.getLogger(__name__)

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

class CrossEncoderReranker:
    """Step 4-2 — Cross-Encoder 기반 문서 재평가"""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self._model = CrossEncoder(model_name)
        logger.info(f"Reranker 모델 로드 완료: {model_name}")

    def rerank(
        self,
        query: str,
        candidates: list[CandidateDocument],
        top_k: int = 5,
    ) -> list[CandidateDocument]:
        """후보 문서를 Cross-Encoder로 재평가하고 상위 K개 반환."""
        if not candidates:
            return []

        pairs = [(query, doc.text) for doc in candidates]
        try:
            scores = self._model.predict(pairs)
            for doc, score in zip(candidates, scores):
                doc.rerank_score = float(score)

            sorted_candidates = sorted(
                candidates, key=lambda d: d.rerank_score or 0, reverse=True
            )
            return sorted_candidates[:top_k]
        except Exception as e:
            logger.error(f"Reranker 재평가 실패: {e}, 원본 순서 유지")
            return candidates[:top_k]
```

### 3.4 RAGRetriever 수정

Phase 1의 `retrieve()` 메서드는 하위 호환을 위해 유지하고, Phase 2 전용 `retrieve_v2()` 메서드를 추가한다. `PHASE2_RAG_ENABLED` 플래그로 분기한다.

```python
# src/pipeline/rag_retriever.py — Phase 2 수정
class RAGRetriever:
    def __init__(
        self,
        vanna_instance: Any,
        reranker: Optional[CrossEncoderReranker] = None,  # Phase 2 신규 주입
        anthropic_client: Optional[Any] = None,            # LLM 선별용
    ) -> None:
        self._vanna = vanna_instance
        self._reranker = reranker
        self._anthropic = anthropic_client

    def retrieve(self, question: str, keywords: list[str]) -> RAGContext:
        """Phase 1 인터페이스 — PHASE2_RAG_ENABLED=false 시 사용 (하위 호환)"""
        # 기존 Phase 1 로직 그대로 유지
        ...

    def retrieve_v2(self, question: str, keywords: list[str]) -> RAGContext:
        """Phase 2 3단계 RAG — PHASE2_RAG_ENABLED=true 시 사용"""
        search_query = question
        if keywords:
            search_query = f"{question} {' '.join(keywords)}"
        try:
            # Step 4-1: 벡터 유사도 검색
            candidates = self._retrieve_candidates(search_query)
            # Step 4-2: Reranker 재평가
            reranked = self._reranker.rerank(
                question=search_query, candidates=candidates, top_k=7
            )
            # Step 4-3: LLM 최종 선별
            return self._llm_filter(question=search_query, candidates=reranked)
        except Exception as e:
            logger.error(f"RAG 3단계 검색 실패: {e}, 빈 컨텍스트로 진행")
            return RAGContext()

    def _retrieve_candidates(self, query: str) -> list[CandidateDocument]: ...
    def _llm_filter(self, question: str, candidates: list[CandidateDocument]) -> RAGContext: ...
```

> **QueryPipeline 분기**: `query_pipeline.py` Step 4에서 플래그에 따라 `retrieve()` 또는 `retrieve_v2()` 호출.
> ```python
> if os.getenv("PHASE2_RAG_ENABLED", "false").lower() == "true":
>     ctx.rag_context = self._rag_retriever.retrieve_v2(question, keywords)
> else:
>     ctx.rag_context = self._rag_retriever.retrieve(question, keywords)
> ```

### 3.5 Reranker 모델 선택 근거

| 항목 | 선택 | 근거 |
|------|------|------|
| 모델 | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 경량 (66M 파라미터), GPU 불필요, 한국어/영어 혼용 준수 성능 |
| 라이브러리 | `sentence-transformers>=2.6.1` | HuggingFace 공식, Reranker API 안정적 |
| 대안 | Cohere Rerank API 제외 | 외부 API 의존성 + 비용 발생 → 자체 모델 선호 |
| 컨테이너 | 모델 캐시 마운트 필요 | PVC 마운트로 재다운로드 방지 (`/root/.cache/huggingface`) |

### 3.6 에러 처리

| 실패 지점 | 동작 |
|-----------|------|
| Step 4-1 벡터 검색 실패 | 빈 RAGContext 반환 → LLM 자체 지식으로 SQL 생성 (Phase 1과 동일) |
| Step 4-2 Reranker 실패 | Step 4-1 결과를 원본 순서 그대로 사용 (graceful degradation) |
| Step 4-3 LLM 선별 실패 | Step 4-2 결과 전체를 RAGContext로 사용 |
| Reranker 모델 로드 실패 | 앱 시작 시 로그 경고, Step 4-2 스킵 |

---

## 4. FR-16~17: 피드백 루프 + 중복 쿼리 방지 설계

### 4.1 FR-16: 피드백 루프 품질 제어

> **Phase 1 대비 변경점**: `FeedbackManager.record_positive()`에서 `vanna.train()` 즉시 호출을 제거하고, DynamoDB `pending_feedbacks`에 저장만 수행. 실제 학습은 Airflow DAG(FR-18)에서 검증 후 배치 실행.

#### 4.1.1 Phase 1 vs Phase 2 비교

| 항목 | Phase 1 (즉시 학습) | Phase 2 (배치 검증) |
|------|-------------------|-------------------|
| 👍 클릭 시 동작 | `vanna.train()` 즉시 호출 | DynamoDB `pending_feedbacks` 저장만 |
| 학습 시점 | 즉시 | Airflow DAG (매주 월 09:00 KST) |
| 품질 보장 | 없음 | EXPLAIN 재검증 + SQL 해시 중복 제거 |
| 데이터 저장 | `query_history.jsonl` (로컬) | DynamoDB (`feedback_status` 필드) |

#### 4.1.2 👍 클릭 → DynamoDB 저장 플로우

```
[Slack 사용자] 👍 클릭
        │
        ▼
[slack-bot] POST /feedback {history_id, feedback="positive"}
        │
        ▼
[FeedbackManager.record_positive()]  ← Phase 2 수정
  1. DynamoDB History 테이블에서 generated_sql, refined_question 조회
  2. DynamoDB `pending_feedbacks` 테이블에 저장:
     {
       "feedback_id": uuid,
       "history_id": history_id,
       "question": refined_question,
       "sql": generated_sql,
       "sql_hash": compute_sql_hash(generated_sql),
       "status": "pending",              ← Airflow 처리 후 "trained" 으로 변경
       "created_at": "ISO8601",
       "ttl": unix_epoch + 90_days
     }
  3. vanna.train() 호출하지 않음 (Phase 1과의 핵심 차이)
        │
        ▼
[응답] { "status": "accepted", "trained": false, "message": "피드백이 기록되었습니다. 주간 학습 배치에서 검증 후 반영됩니다." }
```

#### 4.1.3 FeedbackManager 수정 (Phase 2)

```python
# src/feedback_manager.py — Phase 2 수정
class FeedbackManager:
    def __init__(
        self,
        vanna_instance: Any,
        history_store: DynamoDBHistoryStore,      # Phase 1: HistoryRecorder → Phase 2: DynamoDB
        feedback_store: DynamoDBFeedbackStore,    # 신규
    ) -> None:
        self._vanna = vanna_instance
        self._history = history_store
        self._feedback = feedback_store

    def record_positive(
        self, history_id: str, slack_user_id: str
    ) -> tuple[bool, str]:
        record = self._history.get_record(history_id)
        if not record:
            return False, "이력 레코드를 찾을 수 없습니다"

        # Phase 2: DynamoDB pending_feedbacks에 저장만 (즉시 학습 제거)
        if record.refined_question and record.generated_sql:
            self._feedback.save_pending(
                history_id=history_id,
                question=record.refined_question,
                sql=record.generated_sql,
            )

        self._history.update_feedback(
            history_id=history_id,
            feedback="positive",
            trained=False,  # Phase 2: Airflow 배치 후에 True로 변경
        )
        return False, "피드백이 기록되었습니다. 주간 학습 배치에서 검증 후 반영됩니다."
```

---

## 4.3 FR-13~15: 학습 데이터 삭제 관리

> **Phase 1 현황**: `GET /training-data`(조회), `POST /feedback`(추가)는 구현 완료. **삭제만 미구현** — Phase 1 테스트 결과서 §10 "다음 단계"에 `DELETE /training-data/{id}` 추가 항목으로 명시됨.

### 4.3.1 왜 삭제가 필요한가

| 시나리오 | 문제 | 삭제 필요 |
|---------|------|---------|
| 잘못된 SQL 예제를 👍 피드백으로 학습한 경우 | 나쁜 SQL이 계속 Few-shot으로 사용됨 | ✅ |
| 비즈니스 용어 정의가 변경된 경우 | 구 버전 documentation이 LLM을 혼란시킴 | ✅ |
| 테스트 중 시딩한 임시 데이터 정리 | ChromaDB에 노이즈 데이터 축적 | ✅ |

### 4.3.2 API 설계

```
DELETE /training-data/{training_id}
  - training_id: GET /training-data 응답의 id 필드
  - 인증: X-Internal-Token 헤더 필수 (SEC-05)
  - 응답: 200 {"status": "deleted", "training_id": "..."}
  - 오류: 404 (존재하지 않는 id), 400 (삭제 실패)
```

### 4.3.3 구현 설계

```python
# src/main.py — DELETE /training-data/{training_id} 추가
@app.delete("/training-data/{training_id}")
async def delete_training_data(
    training_id: str,
    _: None = Depends(verify_internal_token),
) -> dict[str, str]:
    try:
        vanna.remove_training_data(id=training_id)
        logger.info(f"학습 데이터 삭제 완료: {training_id}")
        return {"status": "deleted", "training_id": training_id}
    except Exception as e:
        logger.error(f"학습 데이터 삭제 실패: {training_id}: {e}")
        raise HTTPException(status_code=400, detail="학습 데이터 삭제에 실패했습니다.")
```

### 4.3.4 Vanna SDK 삭제 메서드

```python
# Vanna SDK 공식 메서드
vanna.remove_training_data(id=training_id)
# training_id: GET /training-data 응답에서 id 필드로 제공되는 ChromaDB 내부 document ID
```

> **주의**: `remove_training_data()`는 Vanna SDK 내부적으로 ChromaDB collection에서 document를 직접 삭제한다. `GET /training-data`가 반환하는 `id` 필드값을 그대로 사용하면 된다.

### 4.3.5 테스트 포인트

| 시나리오 | 검증 방법 |
|---------|---------|
| 정상 삭제 | `GET /training-data` count 감소 확인 |
| 존재하지 않는 id 삭제 시도 | 400 또는 404 반환 확인 |
| 인증 없이 DELETE 요청 | 401 반환 확인 (SEC-05) |

---

## 5. FR-18: Airflow DAG 설계

> **Phase 1 대비 변경점**: 완전 신규. `capa_chromadb_refresh` DAG가 매주 월요일 09:00 KST에 실행되어 피드백 검증 + ChromaDB 학습을 자동화.

### 5.1 DAG 정의

```python
# services/airflow-dags/capa_chromadb_refresh.py (신규)
from datetime import datetime, timedelta
from airflow import DAG

default_args = {
    "owner": "capa-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="capa_chromadb_refresh",
    default_args=default_args,
    description="Phase 2 — 주간 ChromaDB 학습 데이터 검증 + 자동 학습",
    schedule_interval="0 0 * * 1",   # UTC 월요일 00:00 = KST 월요일 09:00
    start_date=datetime(2026, 3, 24),
    catchup=False,
    tags=["capa", "text-to-sql", "chromadb", "phase2"],
    max_active_runs=1,
) as dag:
    ...
```

### 5.2 Task 그래프

```
extract_pending_feedbacks     (Task 1 — DynamoDB pending 항목 추출)
        │
        ▼
validate_and_deduplicate      (Task 2 — EXPLAIN + 해시 중복 제거)
        │
        ▼
batch_train_chromadb          (Task 3 — vanna.train() 배치 실행)
```

> **범위 제외**: S3 → ChromaDB 동기화 Task 및 Slack 알림 Task는 포함하지 않음. DAG 실행 결과는 Airflow 웹 UI에서 직접 확인. FR-13~15 지식 베이스 관리는 `DELETE /training-data/{id}` API 방식으로 처리 (§4.3 참조).

### 5.3 Task별 상세 설계

#### Task 1: `extract_pending_feedbacks`

```python
def extract_pending_feedbacks(**kwargs) -> list[dict]:
    """DynamoDB pending_feedbacks에서 status='pending' 항목 추출"""
    # DynamoDB Scan: FilterExpression = Attr('status').eq('pending')
    # 반환: [{"feedback_id", "question", "sql", "sql_hash"}, ...]
    # XCom으로 다음 Task에 전달
```

- **입력**: DynamoDB `capa-{env}-pending-feedbacks` 테이블
- **출력**: XCom `pending_items` (list[dict])
- **조건**: 항목 0건이면 이후 Task 스킵 (ShortCircuitOperator)

#### Task 2: `validate_and_deduplicate`

```python
def validate_and_deduplicate(**kwargs) -> list[dict]:
    """SQL EXPLAIN 재검증 + SQL 해시 중복 제거"""
    pending = kwargs['ti'].xcom_pull(task_ids='extract_pending_feedbacks')
    validated = []
    for item in pending:
        # 1. SQL EXPLAIN 검증 (Athena)
        if not athena_explain_check(item['sql']):
            update_feedback_status(item['feedback_id'], 'explain_failed')
            continue
        # 2. 기존 ChromaDB sql-qa 컬렉션과 해시 중복 체크
        if is_duplicate_hash(item['sql_hash']):
            update_feedback_status(item['feedback_id'], 'duplicate')
            continue
        validated.append(item)
    return validated
```

- **입력**: XCom `pending_items`
- **출력**: XCom `validated_items` (검증 통과 항목만)
- **실패 처리**: EXPLAIN 실패 → `explain_failed`, 중복 → `duplicate` 상태로 마킹

#### Task 3: `batch_train_chromadb`

```python
def batch_train_chromadb(**kwargs) -> dict:
    """검증된 질문-SQL 쌍을 ChromaDB에 배치 학습"""
    validated = kwargs['ti'].xcom_pull(task_ids='validate_and_deduplicate')
    trained_count = 0
    for item in validated:
        try:
            vanna.train(question=item['question'], sql=item['sql'])
            update_feedback_status(item['feedback_id'], 'trained')
            trained_count += 1
        except Exception as e:
            logger.error(f"학습 실패: {item['feedback_id']}: {e}")
            update_feedback_status(item['feedback_id'], 'train_failed')
    return {"trained": trained_count, "total": len(validated)}
```

- **입력**: XCom `validated_items`
- **출력**: 학습 결과 통계 (Airflow XCom에 저장, Airflow 웹 UI에서 확인)
- **실패 처리**: 개별 항목 실패 시 `train_failed` 마킹, 나머지 계속 진행

### 5.4 DAG 배포

- **경로**: `s3://capa-{env}-airflow-dags/dags/capa_chromadb_refresh.py`
- **Airflow Scheduler**: S3 sync로 자동 감지

---

## 6. BackgroundTasks 비동기 응답 설계

> **Phase 1 대비 변경점**: `POST /query` 엔드포인트가 동기(최대 300초)에서 비동기(즉시 202 반환)로 전환. 신규 `GET /query/{task_id}` 폴링 엔드포인트 추가.

### 6.1 API 변경

#### Phase 1 (현재)

```
POST /query → [파이프라인 300초 실행] → 200 QueryResponse
```

#### Phase 2 (비동기)

```
POST /query → 즉시 202 Accepted + { "task_id": "uuid", "status": "pending" }
                  │
                  ├─ BackgroundTasks에서 파이프라인 비동기 실행
                  │
GET /query/{task_id} → 폴링
  - status: "pending"    → 202 (처리 중)
  - status: "running"    → 202 (실행 중, progress 포함)
  - status: "completed"  → 200 QueryResponse (결과 포함)
  - status: "failed"     → 200 ErrorResponse (에러 정보 포함)
```

### 6.2 AsyncQueryManager

```python
# src/async_query_manager.py (신규)
import uuid
from datetime import datetime
from typing import Optional
from .models.async_task import AsyncTaskStatus, AsyncTaskRecord

class AsyncQueryManager:
    """비동기 쿼리 실행 관리자"""

    def __init__(self, dynamodb_client: Any, table_name: str) -> None:
        self._db = dynamodb_client
        self._table = table_name

    def create_task(self, question: str, slack_user_id: str) -> str:
        """신규 비동기 Task 생성 → task_id 반환"""
        task_id = str(uuid.uuid4())
        record = AsyncTaskRecord(
            task_id=task_id,
            status=AsyncTaskStatus.PENDING,
            question=question,
            slack_user_id=slack_user_id,
            created_at=datetime.utcnow(),
        )
        # DynamoDB에 저장
        return task_id

    def update_status(
        self, task_id: str, status: AsyncTaskStatus, result: Optional[dict] = None
    ) -> None:
        """Task 상태 업데이트"""
        # DynamoDB UpdateItem

    def get_task(self, task_id: str) -> Optional[AsyncTaskRecord]:
        """Task 조회"""
        # DynamoDB GetItem
```

### 6.3 상태 머신

```
PENDING  →  RUNNING  →  COMPLETED
                    →  FAILED

                    (TTL 만료 후)
                    →  EXPIRED (DynamoDB TTL 자동 삭제)
```

### 6.4 데이터 모델

```python
# src/models/async_task.py (신규)
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class AsyncTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AsyncTaskRecord(BaseModel):
    task_id: str
    status: AsyncTaskStatus
    question: str
    slack_user_id: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None         # 완료 시 QueryResponse 직렬화
    error: Optional[dict] = None          # 실패 시 ErrorResponse 직렬화
    ttl: Optional[int] = None             # DynamoDB TTL (epoch, 24시간 후)
```

### 6.5 main.py 엔드포인트 변경

```python
# POST /query — Phase 2 비동기 버전
@app.post("/query", status_code=202)
async def query_natural_language(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    manager: AsyncQueryManager = app.state.async_manager
    task_id = manager.create_task(
        question=request.question,
        slack_user_id=request.slack_user_id,
    )
    background_tasks.add_task(
        _run_pipeline_async, task_id, request
    )
    return {"task_id": task_id, "status": "pending"}

# GET /query/{task_id} — 결과 조회 (신규)
@app.get("/query/{task_id}")
async def get_query_result(task_id: str) -> dict:
    manager: AsyncQueryManager = app.state.async_manager
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in (AsyncTaskStatus.PENDING, AsyncTaskStatus.RUNNING):
        return JSONResponse(
            status_code=202,
            content={"task_id": task_id, "status": task.status.value},
        )
    if task.status == AsyncTaskStatus.COMPLETED:
        return task.result
    # FAILED
    raise HTTPException(status_code=500, detail=task.error)
```

### 6.6 Slack Bot 연동 변경

```python
# services/slack-bot/app.py — Phase 2 변경
# AS-IS: response = requests.post(f"{API}/query", ..., timeout=310)
# TO-BE:
# 1. POST /query → 202 + task_id (즉시)
# 2. say("처리 중입니다... 완료되면 알려드리겠습니다.")
# 3. 폴링 루프: GET /query/{task_id} (3초 간격, 최대 100회)
# 4. 완료 시 결과 메시지 전송
```

### 6.7 하위 호환성

Phase 2 전환 기간 동안 `ASYNC_QUERY_ENABLED` 환경변수로 동기/비동기 모드를 전환할 수 있다.

```python
ASYNC_QUERY_ENABLED = os.getenv("ASYNC_QUERY_ENABLED", "false").lower() == "true"
```

`false`일 때는 Phase 1과 동일한 동기 응답 유지.

---

## 7. History 저장소 전환: JSON Lines → DynamoDB

> **Phase 1 대비 변경점**: `HistoryRecorder` 내부 구현이 파일 I/O에서 DynamoDB 호출로 전환. 외부 인터페이스(메서드 시그니처)는 동일 유지.

### 7.1 DynamoDB 테이블 설계

#### 7.1.1 `capa-{env}-query-history`

| 속성 | 타입 | 역할 |
|------|------|------|
| `history_id` (PK) | String | UUID |
| `timestamp` | String | ISO 8601 |
| `slack_user_id` | String | SHA-256 해시 (PII) |
| `slack_channel_id` | String | |
| `original_question` | String | |
| `refined_question` | String | |
| `intent` | String | data_query / general / out_of_scope |
| `keywords` | List | |
| `generated_sql` | String | |
| `sql_validated` | Boolean | |
| `row_count` | Number | |
| `redash_query_id` | Number | |
| `redash_url` | String | |
| `feedback` | String | positive / negative / null |
| `feedback_at` | String | ISO 8601 |
| `trained` | Boolean | |
| `ttl` | Number | Unix epoch + 90일 |

**GSI**:

| GSI 이름 | PK | SK | 용도 |
|---------|----|----|------|
| `feedback-status-index` | `feedback` | `timestamp` | 피드백별 이력 조회 |
| `channel-index` | `slack_channel_id` | `timestamp` | 채널별 이력 조회 |

#### 7.1.2 `capa-{env}-pending-feedbacks`

| 속성 | 타입 | 역할 |
|------|------|------|
| `feedback_id` (PK) | String | UUID |
| `history_id` | String | query-history 참조 |
| `question` | String | refined_question |
| `sql` | String | generated_sql |
| `sql_hash` | String | SHA-256 해시 |
| `status` | String | pending / trained / explain_failed / duplicate / train_failed |
| `created_at` | String | ISO 8601 |
| `processed_at` | String | Airflow 처리 일시 |
| `ttl` | Number | Unix epoch + 90일 |

**GSI**:

| GSI 이름 | PK | SK | 용도 |
|---------|----|----|------|
| `status-index` | `status` | `created_at` | Airflow DAG Task 1에서 pending 항목 추출 |

### 7.2 HistoryRecorder 수정

Phase 2에서는 기존 `HistoryRecorder` 클래스를 유지하고 `DynamoDBHistoryRecorder` 서브클래스를 추가한다. `DYNAMODB_ENABLED` 플래그로 구현체를 선택한다.

```python
# src/history_recorder.py — Phase 2 수정
# 기존 HistoryRecorder (JSON Lines) 유지 + DynamoDB 서브클래스 추가
class DynamoDBHistoryRecorder(HistoryRecorder):
    def __init__(self, dynamodb_resource: Any = None, table_name: str = "") -> None:
        self._table = dynamodb_resource.Table(table_name)

    def record(self, ctx: PipelineContext) -> str:
        history_id = str(uuid.uuid4())
        item = {
            "history_id": history_id,
            "timestamp": datetime.utcnow().isoformat(),
            # ... (기존 필드 동일)
            "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp()),
        }
        try:
            self._table.put_item(Item=item)
        except ClientError as e:
            logger.error(f"DynamoDB 이력 저장 실패: {e}")
        return history_id

    def get_record(self, history_id: str) -> Optional[QueryHistoryRecord]:
        try:
            resp = self._table.get_item(Key={"history_id": history_id})
            item = resp.get("Item")
            return QueryHistoryRecord(**item) if item else None
        except ClientError as e:
            logger.error(f"DynamoDB 이력 조회 실패: {e}")
            return None

    def update_feedback(self, history_id: str, feedback: str, trained: bool = False) -> bool:
        try:
            self._table.update_item(
                Key={"history_id": history_id},
                UpdateExpression="SET feedback = :fb, feedback_at = :fa, trained = :tr",
                ExpressionAttributeValues={
                    ":fb": feedback,
                    ":fa": datetime.utcnow().isoformat(),
                    ":tr": trained,
                },
            )
            return True
        except ClientError as e:
            logger.error(f"DynamoDB 피드백 업데이트 실패: {e}")
            return False
```

---

## 8. 환경 변수 목록

### 8.1 신규 환경 변수

| 변수명 | 분류 | 예시값 | 설명 |
|--------|------|--------|------|
| `DYNAMODB_HISTORY_TABLE` | ConfigMap | `capa-dev-query-history` | History DynamoDB 테이블명 |
| `DYNAMODB_FEEDBACK_TABLE` | ConfigMap | `capa-dev-pending-feedbacks` | Pending Feedback DynamoDB 테이블명 |
| `RERANKER_MODEL_NAME` | ConfigMap | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranker 모델명 |
| `RERANKER_TOP_K` | ConfigMap | `5` | Reranker 상위 K개 |
| `RAG_VECTOR_TOP_N` | ConfigMap | `10` | 벡터 검색 후보 N개 |

### 8.2 기존 환경 변수 변경

| 변수명 | Phase 1 | Phase 2 변경 |
|--------|---------|-------------|
| `REDASH_ENABLED` | `true/false` | 유지 (변경 없음) |
| `CHROMA_HOST` | 유지 | 유지 |
| `ANTHROPIC_API_KEY` | 유지 | 유지 |

---

## 9. K8s / Terraform 변경사항

### 9.1 DynamoDB 리소스 (Terraform)

> **무료 요금 범위 (25GB까지)**: 과금 없이 완전히 무료로 운영하려면, 용량 모드를 **프로비저닝됨(Provisioned)**으로 설정해야 합니다. 온디맨드(On-Demand) 모드는 프리 티어가 없어 모든 요청에 과금됩니다.
> **⚠️ 중요**: 25 WCU / 25 RCU 프리 티어는 단일 테이블 기준이 아니라 **AWS 계정 내 모든 테이블 + GSI 합산** 기준입니다.
> - query_history: 테이블 8 + feedback-status-index GSI 3 + channel-index GSI 3 = **14 WCU/RCU**
> - pending_feedbacks: 테이블 7 + status-index GSI 4 = **11 WCU/RCU**
> - **총합: 25 WCU / 25 RCU** (프리 티어 범위 내)

```hcl
# infrastructure/terraform/13-dynamodb.tf (신규)
# 무료 요금 범위 (25 WCU/RCU 이하): 테이블 + GSI 전체 합산
#   query_history: 8 + 3 + 3 = 14
#   pending_feedbacks: 7 + 4 = 11
#   합계: 25 WCU/RCU

resource "aws_dynamodb_table" "query_history" {
  name           = "capa-${var.env}-query-history"
  billing_mode   = "PROVISIONED"
  hash_key       = "history_id"

  # 테이블 기본 용량 8 WCU/RCU
  write_capacity = 8
  read_capacity  = 8

  attribute {
    name = "history_id"
    type = "S"
  }
  attribute {
    name = "feedback"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
  attribute {
    name = "slack_channel_id"
    type = "S"
  }

  # GSI-1: 피드백 상태별 조회 (3 WCU/RCU)
  global_secondary_index {
    name               = "feedback-status-index"
    hash_key           = "feedback"
    range_key          = "timestamp"
    projection_type    = "ALL"
    write_capacity     = 3
    read_capacity      = 3
  }

  # GSI-2: Slack 채널별 조회 (3 WCU/RCU)
  global_secondary_index {
    name               = "channel-index"
    hash_key           = "slack_channel_id"
    range_key          = "timestamp"
    projection_type    = "ALL"
    write_capacity     = 3
    read_capacity      = 3
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project     = "CAPA"
    Environment = var.env
    ManagedBy   = "Terraform"
    Feature     = "text-to-sql-phase2"
  }
}

resource "aws_dynamodb_table" "pending_feedbacks" {
  name           = "capa-${var.env}-pending-feedbacks"
  billing_mode   = "PROVISIONED"
  hash_key       = "feedback_id"

  # 테이블 기본 용량 7 WCU/RCU
  write_capacity = 7
  read_capacity  = 7

  attribute {
    name = "feedback_id"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }

  # GSI-1: 피드백 상태별 조회 (4 WCU/RCU)
  global_secondary_index {
    name               = "status-index"
    hash_key           = "status"
    range_key          = "created_at"
    projection_type    = "ALL"
    write_capacity     = 4
    read_capacity      = 4
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project     = "CAPA"
    Environment = var.env
    ManagedBy   = "Terraform"
    Feature     = "text-to-sql-phase2"
  }
}

```

### 9.2 IAM 정책 변경 (IRSA)

```hcl
# vanna-api ServiceAccount에 DynamoDB 권한 추가
resource "aws_iam_policy" "vanna_dynamodb" {
  name = "capa-${var.env}-vanna-dynamodb"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = [
          aws_dynamodb_table.query_history.arn,
          "${aws_dynamodb_table.query_history.arn}/index/*",
          aws_dynamodb_table.pending_feedbacks.arn,
          "${aws_dynamodb_table.pending_feedbacks.arn}/index/*",
        ]
      }
    ]
  })

  tags = {
    Project     = "CAPA"
    Environment = var.env
    ManagedBy   = "Terraform"
  }
}
```

### 9.3 K8s 변경사항

| 항목 | 변경 내용 |
|------|----------|
| vanna-api ConfigMap | DynamoDB 테이블명 2개(History, Feedback), Reranker 설정 추가 |
| vanna-api 메모리 | **1.5Gi** (Reranker 모델 로드 포함, NFR-07 기준 유지) |
| Airflow DAG S3 | `capa_chromadb_refresh.py` 배포 |

---

## 10. 구현 파일 목록

### 10.1 신규 파일

| 파일 | 설명 | 관련 FR |
|------|------|---------|
| `src/pipeline/reranker.py` | Cross-Encoder Reranker | FR-12 |
| `src/pipeline/sql_hash.py` | SQL 정규화 + SHA-256 해시 (피드백 중복 제거용) | FR-16/FR-18 |
| `src/models/rag.py` | CandidateDocument, RerankResult 모델 | FR-12 |
| `src/models/async_task.py` | AsyncTaskStatus, AsyncTaskRecord 모델 | BackgroundTasks |
| `src/async_query_manager.py` | 비동기 쿼리 실행 관리 | BackgroundTasks |
| `src/stores/dynamodb_history.py` | DynamoDB History Store | History 전환 |
| `src/stores/dynamodb_feedback.py` | DynamoDB Feedback Store | FR-16 |
| `services/airflow-dags/capa_chromadb_refresh.py` | Airflow DAG | FR-18 |
| `infrastructure/terraform/13-dynamodb.tf` | DynamoDB 테이블 정의 (2개) | 인프라 |

### 10.2 수정 파일

| 파일 | 변경 내용 | 관련 FR |
|------|----------|---------|
| `src/pipeline/rag_retriever.py` | 3단계 RAG 통합 (Reranker + LLM 선별) | FR-12 |
| `src/feedback_manager.py` | 즉시 학습 제거 → DynamoDB 저장 | FR-16 |
| `src/history_recorder.py` | JSON Lines → DynamoDB | History 전환 |
| `src/main.py` | BackgroundTasks 비동기 + GET /query/{task_id} | 전체 |
| `src/query_pipeline.py` | AsyncQueryManager 연동 | BackgroundTasks |
| `services/slack-bot/app.py` | 비동기 폴링 방식으로 전환 | BackgroundTasks |
| `infrastructure/terraform/11-k8s-apps.tf` | ConfigMap/메모리 변경 | 인프라 |
| `requirements.txt` | `sentence-transformers`, `boto3` DynamoDB 추가 | 의존성 |

---

## 10.3 NFR-05: SQL 생성 프롬프트 구조 설계 (영어 XML 기반)

> **Phase 1 대비 변경점**: 프롬프트 구조 자체는 동일하게 유지. Phase 2에서 3단계 RAG가 정제된 컨텍스트를 제공하여 프롬프트 품질이 향상됨.

### 요구사항

- SQL 생성 프롬프트는 **영어 기반 XML 구조**로 작성 (토큰 효율 + LLM SQL 생성 정확도 향상)
- 한국어 질문을 그대로 LLM에 전달하지 않고, 영어 XML 태그로 구조화된 컨텍스트와 함께 전달

### 현재 구현 (Phase 1 유지)

`sql_generator.py`의 `generate()` 메서드는 날짜 컨텍스트 prefix를 붙여 Vanna `generate_sql()`에 전달한다.

```python
# services/vanna-api/src/pipeline/sql_generator.py
date_context = (
    f"[날짜 컨텍스트: 오늘={today}, 어제={yesterday}, "
    f"이번달={today.strftime('%Y-%m')}-01~{today}, "
    f"지난달={last_month_start}~{last_month_end}] "
)
prompt = f"{date_context}{question}"
self._vanna.generate_sql(question=prompt)
```

Vanna SDK 내부의 `generate_sql()`은 ChromaDB에서 검색된 DDL·SQL 예시·문서를 아래와 같은 **영어 XML 구조**로 조립하여 LLM에 전달한다:

```xml
<context>
  <ddl>CREATE TABLE ...</ddl>
  <sql_examples>SELECT ...</sql_examples>
  <documentation>...</documentation>
</context>
<question>{user_question}</question>
```

커스텀 코드(`sql_generator.py`)는 XML 구조를 별도로 구성하지 않으며, Vanna SDK가 이 역할을 담당한다.

### Phase 2 변경점 및 영향

| 항목 | Phase 1 | Phase 2 |
|------|---------|---------|
| RAG 컨텍스트 소스 | 기본 벡터 검색 Top-K | 3단계 RAG (벡터 → Reranker → LLM 선별) |
| XML에 삽입되는 예시 품질 | 유사도 기반 Top-K | Cross-Encoder로 정제된 고품질 Top-N |
| 프롬프트 XML 구조 | Vanna SDK 기본 | **변경 없음** (Vanna SDK 유지) |
| 커스텀 날짜 컨텍스트 | prefix 추가 | **변경 없음** |

**핵심**: 3단계 RAG(`RAGRetriever.retrieve_v2()`)가 반환하는 정제된 SQL 예시·DDL·문서가 Vanna 내부 XML 프롬프트에 삽입되어 LLM이 더 정확한 SQL을 생성한다. 프롬프트 구조(영어 XML) 자체는 Phase 1과 동일.

### 설계 결정

- Vanna SDK의 XML 프롬프트 구조를 커스텀 오버라이드하지 **않음**: SDK 업그레이드 시 자동 개선 효과를 누리기 위함
- 날짜 컨텍스트는 한국어로 유지: Athena 쿼리 날짜 범위 정확도를 위한 Phase 1 검증된 접근

---

## 11. 결정 근거 요약 (Decision Log)

| # | 결정 | 대안 | 채택 근거 |
|---|------|------|----------|
| D-01 | Reranker로 `cross-encoder/ms-marco-MiniLM-L-6-v2` 선택 | Cohere Rerank API | 외부 API 비용/의존성 제거, 66M 경량 모델로 GPU 불필요 |
| D-02 | History 저장소로 DynamoDB 선택 | PostgreSQL, Redis | Serverless + TTL 자동 삭제 + Airflow DAG에서 직접 Scan 가능, AWS 네이티브 |
| D-03 | BackgroundTasks 비동기 응답 채택 | WebSocket, SSE (Server-Sent Events) | FastAPI 내장 기능으로 추가 인프라 불필요, Slack Bot은 이미 폴링 패턴 사용 중 |
| D-04 | Airflow DAG 배치 학습 (즉시 학습 폐기) | 즉시 학습 유지 + 품질 필터 추가 | Plan FR-16 명시적 요구, 검증 없는 즉시 학습은 ChromaDB 품질 저하 위험 |
| D-05 | ChromaDB Collection 구조 변경 없음 | 커스텀 Collection 추가 | Vanna SDK 호환성 유지 |

---

## 12. 에이전트 기여 내역 (Agent Attribution)

### 12.1 에이전트별 수행 작업

| 에이전트 | 모델 | 수행 작업 |
|---------|------|----------|
| `cto-lead` | claude-opus-4-6 | 전체 디자인 방향 설정, 팀원 작업 지시, 결과물 수합 및 최종 문서 통합 |
| `enterprise-expert` | claude-sonnet-4-6 | 3단계 RAG 설계(FR-12), 피드백 루프(FR-16), BackgroundTasks 아키텍처, History 전환 |
| `infra-architect` | claude-sonnet-4-6 | Airflow DAG 상세 설계(FR-18), DynamoDB 테이블 설계, Terraform 변경사항, 환경 변수 목록, BackgroundTasks 인프라 |

### 12.2 섹션별 주요 기여 에이전트

| 섹션 | 기여 에이전트 | 기여 내용 |
|------|-------------|----------|
| §1~2 설계 개요/전체 구조 | `cto-lead` | 디자인 방향, Phase 1 대비 변경점 총괄 |
| §3 FR-12 3단계 RAG | `enterprise-expert` | Reranker 모델 선정, 3단계 흐름 설계, 에러 처리 전략 |
| §4 FR-16 피드백 루프 | `enterprise-expert` | FeedbackManager 수정 |
| §5 FR-18 Airflow DAG | `infra-architect` | DAG 정의, Task 그래프, 각 Task 상세 로직 |
| §6 BackgroundTasks | `enterprise-expert` + `infra-architect` | 아키텍처는 enterprise, 인프라/상태관리는 infra |
| §7 DynamoDB 설계 | `infra-architect` | 테이블 스키마(2개), GSI, TTL 설계 |
| §8 환경 변수 | `infra-architect` | 신규 변수 목록 |
| §9 Terraform | `infra-architect` | DynamoDB 2테이블 리소스, IAM 정책 |
| §10 파일 목록 | `cto-lead` | 전체 신규/수정 파일 통합 정리 |
| §11 Decision Log | `cto-lead` | 전체 결정 근거 종합 |
