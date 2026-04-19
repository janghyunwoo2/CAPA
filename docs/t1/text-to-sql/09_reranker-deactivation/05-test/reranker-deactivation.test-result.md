# [Test Result] reranker-deactivation

| 항목 | 내용 |
|------|------|
| **Feature** | reranker-deactivation |
| **실행일** | 2026-03-25 |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **최종 결과** | ✅ 4/4 PASS |

---

## 결과 테이블

| TC | Step | 스텝 역할 | 인풋 | 아웃풋 (실제값) | assert 단언 | 판정 | 왜 이렇게 나왔나 |
|----|------|-----------|------|----------------|-------------|------|-----------------|
| TC-RD-01 | - | 환경변수 파싱 | `RERANKER_ENABLED=false` | `qp.RERANKER_ENABLED = False` | `assert qp.RERANKER_ENABLED is False` | ✅ PASS | 모듈 상단 `os.getenv("RERANKER_ENABLED", "true").lower() == "true"` 정상 파싱 |
| TC-RD-02 | - | 기본값 확인 | 환경변수 미설정 | `qp.RERANKER_ENABLED = True` | `assert qp.RERANKER_ENABLED is True` | ✅ PASS | 기본값 `"true"` → `True`, 하위 호환 유지 |
| TC-RD-03 | - | Reranker 미호출 | `PHASE2=true`, `RERANKER=false` | `CrossEncoderReranker()` 호출 없음 | `mock_reranker_cls.assert_not_called()` | ✅ PASS | `RERANKER_ENABLED=false` 분기로 `CrossEncoderReranker` import/초기화 스킵 |
| TC-RD-04 | - | PHASE2 비활성 | `PHASE2=false`, `RERANKER=true` | `qp.PHASE2_RAG_ENABLED = False` | `assert qp.PHASE2_RAG_ENABLED is False` | ✅ PASS | PHASE2 비활성 시 Reranker 분기 자체 미진입 — 기존 동작 유지 |

---

## TDD 사이클 요약

### Red Phase
- 총 4개 TC 중 3개 FAIL (TC-RD-01~03)
- 주요 원인: `src.query_pipeline`에 `RERANKER_ENABLED` 속성 미존재
- TC-RD-04는 `PHASE2_RAG_ENABLED` 기존 구현으로 PASS

### Green Phase — 구현 내용
| 파일 | 수정 내용 |
|------|---------|
| `src/query_pipeline.py` | `RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"` 추가 (60번 라인) |
| `src/query_pipeline.py` | `QueryPipeline.__init__` Reranker 초기화 분기 수정 — `RERANKER_ENABLED` 조건 추가 |
| `docker-compose.local-e2e.yml` | `RERANKER_ENABLED=false` 추가 |

### pytest 실행 로그
```
collected 4 items

tests/unit/test_reranker_deactivation.py::TestRerankerDeactivation::test_reranker_enabled_false_parses_correctly PASSED [ 25%]
tests/unit/test_reranker_deactivation.py::TestRerankerDeactivation::test_reranker_enabled_default_is_true PASSED [ 50%]
tests/unit/test_reranker_deactivation.py::TestRerankerDeactivation::test_crossencoder_not_called_when_reranker_disabled PASSED [ 75%]
tests/unit/test_reranker_deactivation.py::TestRerankerDeactivation::test_phase2_disabled_reranker_irrelevant PASSED [100%]

============================== 4 passed in 2.69s ==============================
```
