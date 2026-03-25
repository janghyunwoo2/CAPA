# [Analysis] Slack 스레드 기반 응답 출력 — Gap 분석 (FR-24)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | txt-to-sql-slack-thread |
| **FR ID** | FR-24 |
| **분석일** | 2026-03-21 |
| **담당** | t1 |
| **Match Rate** | **100%** (7/7 FR 구현 완료) |
| **설계서** | `docs/t1/text-to-sql/02_txt-to-sql-slack/02-design/features/txt-to-sql-slack-thread.design.md` |
| **구현 파일** | `services/slack-bot/app.py` |

---

## 1. 전체 분석 결과

| 카테고리 | 점수 | 상태 |
|----------|:----:|:----:|
| FR 설계 반영률 | 100% | ✅ |
| Feature Flag 구현 | 100% | ✅ |
| 에러 처리 구조 | 100% | ✅ |
| Phase 2 연계 준비 | 100% | ✅ |
| **종합** | **100%** | ✅ |

---

## 2. 구현된 항목 (7/7)

| FR | 설계 내용 | 구현 위치 | 판정 |
|----|-----------|-----------|:----:|
| **FR-24-01** | Feature Flag(`SLACK_THREAD_ENABLED`)로 스레드 루트 메시지 생성, `say("🔄 처리 중...")` 전송 | `app.py:41-42, 213-218` | ✅ |
| **FR-24-02** | `thread_ts` 캡처 후 vanna-api `/query` 요청에 `conversation_id`로 전달 | `app.py:231, 278` | ✅ |
| **FR-24-03** | 헤더 블록, 차트, 푸터 블록 모두 `thread_ts=thread_ts` 인자로 스레드 답글 전송 | `app.py:292, 320` | ✅ |
| **FR-24-04** | 처리 완료 후 `client.chat_update()`로 루트 메시지를 "✅ 완료: {질문요약}"으로 업데이트 | `app.py:322-329` | ✅ |
| **FR-24-05** | `requests.Timeout` 및 일반 `Exception` 모두 `thread_ts` 유지하며 에러 메시지 스레드 전송 | `app.py:331-337` | ✅ |
| **FR-24-06** | `SLACK_THREAD_ENABLED` 환경변수로 스레드/채널 메시지 전환 가능, 기본값 `"true"` | `app.py:41-42` | ✅ |
| **FR-24-07** | 동기/비동기 양쪽 경로 모두 `"conversation_id": thread_ts` 포함하여 vanna-api 전달 | `app.py:231, 278` | ✅ |

---

## 3. Gap 항목

### 🔴 미구현 항목

없음

### 🟡 낮은 수준 불일치 (기능 영향 없음)

| 항목 | 설계 | 구현 | 영향 |
|------|------|------|------|
| **SlackApiError 폴백** | 설계 §5.1: 루트 메시지 생성 실패 시 `except SlackApiError`로 `thread_ts=None` 폴백 | `app.py:214-217`: `isinstance(thread_response, dict)` 체크로 실질적 폴백 처리되나, `SlackApiError` 명시적 catch 없음 | 낮음 — 기능적으로 동등 |
| **비동기 폴링 경로** | 설계 미포함 | `app.py:38-39, 222-268`: ASYNC_QUERY_ENABLED 비동기 폴링 흐름에도 conversation_id 포함. 2026-03-25 기준 `ASYNC_QUERY_ENABLED=true` 정식 활성화, 30초마다 진행 중 메시지 전송 기능 추가 | 추가 기능 — 정식 운영 모드로 전환 완료 |

---

## 4. 세부 관찰

- **FR-24-02 이중 경로 처리**: 동기(`else` 블록, line 278)와 비동기(`if ASYNC_QUERY_ENABLED` 블록, line 231) 양쪽 모두 `conversation_id: thread_ts` 포함. 설계 요구보다 철저하게 반영됨.
- **루트 업데이트 질문 요약 로직**: 설계 §2.1.2와 동일하게 `text[:30] + "..."` 구현 (line 324).
- **thread_ts None 안전 처리**: `say(..., thread_ts=thread_ts)`에서 `thread_ts=None`이면 채널 메시지로 자동 전환 — 설계 §2.1.3 Feature Flag 로직 정확히 반영.

---

## 5. 권고 사항

| 우선순위 | 항목 | 내용 |
|----------|------|------|
| 낮음 | `SlackApiError` 명시적 catch | 현재 `isinstance` 체크로 대체 가능하나, 향후 가독성을 위해 명시적 catch 추가 고려 |
| ~~백로그~~ ✅ 완료 | `ASYNC_QUERY_ENABLED` 정식 활성화 | 2026-03-25: `docker-compose.local-e2e.yml` vanna-api `ASYNC_QUERY_ENABLED=true`로 변경, 30초마다 진행 중 메시지 전송 기능 추가(`app.py` 폴링 루프 내 `_elapsed % 30 == 0` 조건) |

---

## 6. 결론

설계서 FR-24-01 ~ FR-24-07 전체 7개 요구사항이 `services/slack-bot/app.py`에 완전히 구현됨.
**Match Rate 100%** — `/pdca report`로 완료 보고서 작성 진행 가능.
