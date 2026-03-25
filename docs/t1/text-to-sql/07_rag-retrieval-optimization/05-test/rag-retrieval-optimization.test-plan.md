# [Test Plan] rag-retrieval-optimization

| 항목 | 내용 |
|------|------|
| **Feature** | rag-retrieval-optimization |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 설계서** | `docs/t1/text-to-sql/07_rag-retrieval-optimization/02-design/rag-retrieval-optimization.design.md` |
| **테스트 파일** | `services/vanna-api/tests/unit/test_rag_retrieval_optimization.py` |

---

## Phase A — DDL/Docs ChromaDB score 실측 반영

### TC-A-01: get_related_ddl_with_score() 반환 형식 검증

| 항목 | 내용 |
|------|------|
| **목적** | DDL 검색 결과가 `[{"text": str, "score": float}]` 형태인지 확인 |
| **사전 조건** | `ddl_collection.query()` Mock이 distance=0.5 반환 |
| **테스트 입력** | question="어제 CTR 보여줘" |
| **기대 결과** | `[{"text": "CREATE TABLE ...", "score": 0.667}]` (score=1/(1+0.5)) |
| **검증 코드** | `assert result[0]["score"] == pytest.approx(1/(1+0.5), rel=1e-3)` |

### TC-A-02: score 변환 공식 검증 (distance=0 → score=1.0)

| 항목 | 내용 |
|------|------|
| **목적** | distance=0 (완벽 일치) 시 score=1.0인지 확인 |
| **사전 조건** | `ddl_collection.query()` Mock이 distance=0.0 반환 |
| **테스트 입력** | question="ad_combined_log" |
| **기대 결과** | score == 1.0 |
| **검증 코드** | `assert result[0]["score"] == 1.0` |

### TC-A-03: DDL 컬렉션 실패 시 fallback 동작

| 항목 | 내용 |
|------|------|
| **목적** | ChromaDB 접근 실패 시 기존 `get_related_ddl()` fallback 호출 확인 |
| **사전 조건** | `ddl_collection.query()` 가 Exception 발생 |
| **테스트 입력** | question="아무거나" |
| **기대 결과** | `get_related_ddl()` 호출됨, score=1.0 고정 반환 |
| **검증 코드** | `mock_vanna.get_related_ddl.assert_called_once()` |

### TC-A-04: get_related_documentation_with_score() 반환 형식 검증

| 항목 | 내용 |
|------|------|
| **목적** | Documentation 검색 결과도 `[{"text": str, "score": float}]` 형태인지 확인 |
| **사전 조건** | `documentation_collection.query()` Mock이 distance=1.0 반환 |
| **테스트 입력** | question="CTR 정의" |
| **기대 결과** | score == 0.5 (1/(1+1.0)) |
| **검증 코드** | `assert result[0]["score"] == pytest.approx(0.5)` |

---

## Phase B — SchemaMapper 키워드→테이블 매핑

### TC-B-01: CVR 키워드 → summary 확정

| 항목 | 내용 |
|------|------|
| **목적** | 전환율 관련 키워드가 ad_combined_log_summary를 확정 선택하는지 확인 |
| **테스트 입력** | keywords=["CVR"] |
| **기대 결과** | `tables=["ad_combined_log_summary"]`, `is_definitive=True`, `confidence=1.0` |
| **검증 코드** | `assert hint.tables == ["ad_combined_log_summary"] and hint.is_definitive is True` |

### TC-B-02: ROAS 키워드 → summary 확정

| 항목 | 내용 |
|------|------|
| **목적** | 수익률 관련 키워드가 summary 테이블을 확정하는지 확인 |
| **테스트 입력** | keywords=["ROAS"] |
| **기대 결과** | `tables=["ad_combined_log_summary"]`, `is_definitive=True` |
| **검증 코드** | `assert hint.is_definitive is True` |

### TC-B-03: 시간대 키워드 → log 확정

| 항목 | 내용 |
|------|------|
| **목적** | 시간대 분석 키워드가 ad_combined_log를 확정 선택하는지 확인 |
| **테스트 입력** | keywords=["시간대"] |
| **기대 결과** | `tables=["ad_combined_log"]`, `is_definitive=True`, `confidence=1.0` |
| **검증 코드** | `assert hint.tables == ["ad_combined_log"] and hint.is_definitive is True` |

### TC-B-04: 피크타임 키워드 → log 확정

| 항목 | 내용 |
|------|------|
| **목적** | 피크타임 키워드가 hour 파티션이 있는 log 테이블을 확정하는지 확인 |
| **테스트 입력** | keywords=["피크타임"] |
| **기대 결과** | `tables=["ad_combined_log"]`, `is_definitive=True` |
| **검증 코드** | `assert hint.tables == ["ad_combined_log"]` |

### TC-B-05: CTR+날짜 키워드 → summary 선호 (모호)

| 항목 | 내용 |
|------|------|
| **목적** | 확정 키워드 없이 일반 지표만 있을 때 is_definitive=False인지 확인 |
| **테스트 입력** | keywords=["CTR", "어제"] |
| **기대 결과** | `is_definitive=False`, `confidence=0.8`, `tables=["ad_combined_log_summary"]` |
| **검증 코드** | `assert hint.is_definitive is False and hint.confidence == 0.8` |

### TC-B-06: 빈 키워드 → 모호 처리

| 항목 | 내용 |
|------|------|
| **목적** | 키워드가 없을 때 완전 모호로 처리되는지 확인 |
| **테스트 입력** | keywords=[] |
| **기대 결과** | `tables=[]`, `is_definitive=False`, `confidence=0.5` |
| **검증 코드** | `assert hint.is_definitive is False and hint.confidence == 0.5` |

### TC-B-07: 충돌 키워드 (전환+시간대) → 모호 처리

| 항목 | 내용 |
|------|------|
| **목적** | summary 확정 + log 확정 키워드가 동시에 있을 때 모호로 처리되는지 확인 |
| **테스트 입력** | keywords=["전환", "시간대"] |
| **기대 결과** | `is_definitive=False` (충돌로 인해 확정 불가) |
| **검증 코드** | `assert hint.is_definitive is False` |

### TC-B-08: is_conversion 컬럼명 직접 언급 → summary 확정

| 항목 | 내용 |
|------|------|
| **목적** | 컬럼명 직접 언급 시에도 올바른 테이블을 매핑하는지 확인 |
| **테스트 입력** | keywords=["is_conversion"] |
| **기대 결과** | `tables=["ad_combined_log_summary"]`, `is_definitive=True` |
| **검증 코드** | `assert hint.tables == ["ad_combined_log_summary"]` |

---

## Phase C — DDL 검색 최적화

### TC-C-01: is_definitive=True 시 DDL 직접 주입 (벡터 검색 생략)

| 항목 | 내용 |
|------|------|
| **목적** | 테이블이 확정된 경우 ChromaDB 벡터 검색 없이 DDL을 직접 반환하는지 확인 |
| **사전 조건** | `schema_hint.is_definitive=True`, `tables=["ad_combined_log_summary"]` |
| **기대 결과** | DDL 텍스트에 "ad_combined_log_summary" 포함, `ddl_collection.query()` 미호출 |
| **검증 코드** | `mock_vanna.ddl_collection.query.assert_not_called()` |

### TC-C-02: is_definitive=False 시 벡터 검색 경로 사용

| 항목 | 내용 |
|------|------|
| **목적** | 테이블이 모호한 경우 기존 벡터 검색을 사용하는지 확인 |
| **사전 조건** | `schema_hint.is_definitive=False` |
| **기대 결과** | `get_related_ddl_with_score()` 또는 `get_related_ddl()` 호출됨 |
| **검증 코드** | `mock_vanna.get_related_ddl.called or mock_vanna.ddl_collection.query.called` |

---

## Phase D — LLM 선별 조건부 실행

### TC-D-01: is_definitive=True 시 LLM filter 호출 안 됨

| 항목 | 내용 |
|------|------|
| **목적** | Schema 확정 시 Haiku LLM 선별 단계가 생략되는지 확인 |
| **사전 조건** | `schema_hint.is_definitive=True`, `anthropic_client` Mock 제공 |
| **기대 결과** | `anthropic_client.messages.create()` 미호출 |
| **검증 코드** | `mock_anthropic.messages.create.assert_not_called()` |

### TC-D-02: is_definitive=False 시 LLM filter 호출됨

| 항목 | 내용 |
|------|------|
| **목적** | Schema 모호 시 기존 LLM 선별이 실행되는지 확인 |
| **사전 조건** | `schema_hint.is_definitive=False`, `anthropic_client` Mock 제공 |
| **기대 결과** | `anthropic_client.messages.create()` 1회 호출됨 |
| **검증 코드** | `mock_anthropic.messages.create.assert_called_once()` |

### TC-D-03: is_definitive=True 시 Reranker top_k=5

| 항목 | 내용 |
|------|------|
| **목적** | Schema 확정 시 Reranker가 top_k=5로 호출되는지 확인 |
| **사전 조건** | `schema_hint.is_definitive=True`, reranker Mock 제공 |
| **기대 결과** | `reranker.rerank()` 호출 시 `top_k=5` |
| **검증 코드** | `assert mock_reranker.rerank.call_args.kwargs["top_k"] == 5` |

### TC-D-04: is_definitive=False 시 Reranker top_k=7 (기본값)

| 항목 | 내용 |
|------|------|
| **목적** | Schema 모호 시 Reranker가 기존 기본값 top_k=7로 호출되는지 확인 |
| **사전 조건** | `schema_hint.is_definitive=False`, reranker Mock 제공 |
| **기대 결과** | `reranker.rerank()` 호출 시 `top_k=7` |
| **검증 코드** | `assert mock_reranker.rerank.call_args.kwargs["top_k"] == 7` |

---

## 총 TC 수

| Phase | TC 수 |
|-------|-------|
| Phase A | 4 |
| Phase B | 8 |
| Phase C | 2 |
| Phase D | 4 |
| **합계** | **18** |
