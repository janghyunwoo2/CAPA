# [Test Plan] reranker-deactivation

| 항목 | 내용 |
|------|------|
| **Feature** | reranker-deactivation |
| **테스트 방법** | TDD — pytest 단위 테스트 |
| **참고 계획서** | `docs/t1/text-to-sql/09_reranker-deactivation/01-plan/features/reranker-deactivation.plan.md` |

---

## 테스트 케이스

### TC-RD-01: FR-RD-01 — RERANKER_ENABLED=false → 모듈 변수 False
| 항목 | 내용 |
|------|------|
| **목적** | 환경변수 `RERANKER_ENABLED=false` 설정 시 모듈 레벨 변수가 `False`로 파싱되는지 확인 |
| **사전 조건** | `RERANKER_ENABLED=false` 환경변수 설정 |
| **테스트 입력** | `os.environ["RERANKER_ENABLED"] = "false"` → `importlib.reload()` |
| **기대 결과** | `query_pipeline.RERANKER_ENABLED is False` |
| **검증 코드** | `assert qp.RERANKER_ENABLED is False` |

---

### TC-RD-02: FR-RD-01 — RERANKER_ENABLED 미설정 → 기본값 True (하위 호환)
| 항목 | 내용 |
|------|------|
| **목적** | 환경변수 미설정 시 기본값 `true`로 동작하여 기존 동작 유지 확인 |
| **사전 조건** | `RERANKER_ENABLED` 환경변수 없음 |
| **테스트 입력** | 환경변수 미설정 → `importlib.reload()` |
| **기대 결과** | `query_pipeline.RERANKER_ENABLED is True` |
| **검증 코드** | `assert qp.RERANKER_ENABLED is True` |

---

### TC-RD-03: FR-RD-01 — PHASE2=true + RERANKER=false → CrossEncoderReranker 미호출
| 항목 | 내용 |
|------|------|
| **목적** | `PHASE2_RAG_ENABLED=true`, `RERANKER_ENABLED=false` 조합 시 `CrossEncoderReranker` 초기화가 스킵되는지 확인 |
| **사전 조건** | `PHASE2_RAG_ENABLED=true`, `RERANKER_ENABLED=false` |
| **테스트 입력** | 환경변수 설정 → `importlib.reload()` |
| **기대 결과** | `CrossEncoderReranker()` 호출 없음 |
| **검증 코드** | `mock_reranker_cls.assert_not_called()` |

---

### TC-RD-04: FR-RD-01 — PHASE2=false → RERANKER_ENABLED 무관하게 Reranker 미호출
| 항목 | 내용 |
|------|------|
| **목적** | `PHASE2_RAG_ENABLED=false` 시 기존대로 Reranker가 동작하지 않음을 확인 |
| **사전 조건** | `PHASE2_RAG_ENABLED=false`, `RERANKER_ENABLED=true` |
| **테스트 입력** | 환경변수 설정 → `importlib.reload()` |
| **기대 결과** | `query_pipeline.PHASE2_RAG_ENABLED is False` → Reranker 분기 미진입 |
| **검증 코드** | `assert qp.PHASE2_RAG_ENABLED is False` |
