"""
Slack Bot - CAPA Text-to-SQL 응답 개선 (T6)
설계 문서 §2.5~§2.6 기준

개선 항목:
- HTTP timeout: 60 → 310초 (NFR-06)
- 에러 응답: ErrorResponse 파싱 후 안내 (FR-09)
- 예외 노출 방지: str(e) → 일반화 메시지 (SEC-07)
- 차트 이미지: chart_image_base64 → files.upload_v2 (FR-08b)
- Redash 링크: redash_url → Section Block (FR-08)
- 인증 헤더: X-Internal-Token (SEC-17)
- 피드백 버튼: 👍/👎 Block Kit + Interaction 콜백 (FR-21)
"""

import base64
import logging
import os
import threading
import time

import requests
from flask import Flask, jsonify
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
VANNA_API_URL = os.environ.get(
    "VANNA_API_URL", "http://vanna-api.vanna.svc.cluster.local:8000"
)
REPORT_API_URL = os.environ.get(
    "REPORT_API_URL", "http://report-generator.report.svc.cluster.local:8000"
)
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")

# NFR-06: Slack Bot 측 timeout 310초 이상
VANNA_API_TIMEOUT = int(os.environ.get("VANNA_API_TIMEOUT", "310"))

# Phase 2: 비동기 폴링 모드 (§6.6)
ASYNC_QUERY_ENABLED = os.environ.get("ASYNC_QUERY_ENABLED", "false").lower() == "true"

# FR-24: Slack 스레드 기반 응답 (Feature Flag)
SLACK_THREAD_ENABLED = os.environ.get("SLACK_THREAD_ENABLED", "true").lower() == "true"
_ASYNC_POLL_INTERVAL = 3  # 폴링 간격 (초)
_ASYNC_POLL_MAX = 100  # 최대 폴링 횟수 (300초)

app = App(token=SLACK_BOT_TOKEN)
flask_app = Flask(__name__)


@flask_app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "slack-bot"}), 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=3000)


def _build_internal_headers() -> dict:
    """SEC-17: X-Internal-Token 헤더 포함"""
    headers = {"Content-Type": "application/json"}
    if INTERNAL_API_TOKEN:
        headers["X-Internal-Token"] = INTERNAL_API_TOKEN
    return headers


def _format_results_table(results: list, sql: str) -> str:
    """결과 데이터를 Slack mrkdwn 텍스트 테이블로 포맷 (NFR-03: 최대 10행)"""
    if not results:
        return ""
    rows = results[:10]
    cols = list(rows[0].keys())
    col_widths = [
        max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols
    ]
    sep = "┼".join("─" * (w + 2) for w in col_widths)
    header = "│".join(f" {str(c):<{w}} " for c, w in zip(cols, col_widths))
    lines = [f"┌{sep}┐", f"│{header}│", f"├{sep}┤"]
    for i, row in enumerate(rows):
        suffix = " 🥇" if i == 0 else ""
        line = "│".join(
            f" {str(row.get(c, '')):<{w}} " for c, w in zip(cols, col_widths)
        )
        lines.append(f"│{line}│{suffix}")
    lines.append(f"└{sep}┘")
    # SQL에서 테이블명·WHERE 조건 간략 추출
    sql_summary = (
        sql.split("FROM")[-1].split("GROUP")[0].strip() if "FROM" in sql else sql
    )
    return "\n".join(lines)


def _handle_error_response(
    response: requests.Response,
    say,
    thread_ts: str | None = None,
) -> None:
    """SEC-07: error_code는 로그에만, 사용자에게는 message만 노출"""
    try:
        error = response.json().get("detail", {})
        if isinstance(error, dict):
            error_code = error.get("error_code", "UNKNOWN_ERROR")
            message = error.get(
                "message", "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            )
        else:
            error_code = "UNKNOWN_ERROR"
            message = "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    except Exception:
        error_code = "PARSE_ERROR"
        message = "응답을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    logger.error(
        f"vanna-api 오류: HTTP {response.status_code}, error_code={error_code}"
    )
    say(
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *오류가 발생했습니다*\n{message}",
                },
            }
        ],
        thread_ts=thread_ts,
    )


def _build_header_blocks(result: dict) -> list:
    """① 헤더 + 질문 + SQL + 결과 테이블 블록 (차트 업로드 전 전송)"""
    question = result.get("refined_question") or result.get("original_question", "")
    sql = result.get("sql", "")
    results = result.get("results", [])

    # 헤더 + 질문 + SQL 요약
    sql_table = (
        sql.split("FROM")[-1].split("GROUP")[0].strip() if "FROM" in sql else sql
    )
    text = f"*📊 CAPA Text-to-SQL 쿼리 결과*\n\n💬 *질문:* {question}\n🔍 *SQL:* `{sql_table}`"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]

    # 결과 테이블
    if results:
        table_text = _format_results_table(results, sql)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{table_text}```"},
            }
        )

    return blocks


def _build_footer_blocks(result: dict) -> list:
    """③ AI 분석 + Redash 링크 + 피드백 버튼 (차트 업로드 후 전송)"""
    answer = result.get("answer", "")
    redash_url = result.get("redash_url")
    history_id = result.get("query_id", "")
    elapsed = result.get("elapsed_seconds")
    if elapsed is not None:
        try:
            elapsed = float(elapsed)
        except (ValueError, TypeError):
            elapsed = None

    blocks = []

    # AI 분석
    if answer:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"🤖 *AI 분석:*\n{answer}"},
            }
        )

    # Redash 링크
    if redash_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🔗 <{redash_url}|Redash에서 전체 결과 보기>",
                },
            }
        )

    # 처리 시간 — Redash 링크와 피드백 버튼 사이에 표시
    if elapsed:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"⏱ 처리 시간: {elapsed:.2f}초"},
            }
        )

    # 피드백 버튼
    if history_id:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👍 좋아요"},
                        "action_id": "feedback_positive",
                        "value": history_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👎 별로예요"},
                        "action_id": "feedback_negative",
                        "value": history_id,
                    },
                ],
            }
        )

    return blocks


@app.event("app_mention")
def handle_mention(event, say, client):
    """@capa-bot 멘션 처리"""
    text = event["text"]
    user = event["user"]
    channel_id = event.get("channel", "")
    logger.info(f"멘션 수신: user={user}, text={text[:100]}")

    # 1. "리포트 생성" 명령어
    if "리포트 생성" in text or "report" in text.lower():
        import re

        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        target_date = date_match.group(1) if date_match else None
        date_str = f" ({target_date})" if target_date else " (오늘)"
        say(
            f"📊 <@{user}>님, {date_str} 성과 리포트 생성을 시작합니다. 잠시만 기다려주세요..."
        )
        try:
            params = {"report_type": "daily"}
            if target_date:
                params["date"] = target_date
            response = requests.post(
                f"{REPORT_API_URL}/generate", params=params, timeout=5
            )
            if response.status_code in (200, 202):
                say(
                    "✅ 리포트 생성 요청이 성공했습니다. 분석이 완료되면 이 채널로 공유해 드릴게요."
                )
            else:
                say(
                    "❌ 리포트 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                )
        except Exception as e:
            logger.error(f"리포트 생성 요청 오류: {e}")
            say("⚠️ 리포트 생성 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    # 2. "echo" 명령어 (디버깅용)
    if "echo" in text.lower():
        parts = text.split("echo", 1)
        msg = parts[1].strip() if len(parts) > 1 else "Echo할 메시지가 없습니다."
        say(f"📢 Echo: {msg}")
        return

    # 3. 기본: Vanna AI 자연어 질의

    # [FR-24-01] Feature Flag: 스레드 답글 또는 채널 메시지
    # [BUG-03] event["ts"](사용자 원본 메시지 ts)를 thread_ts로 사용 → 사용자 메시지에 스레드 열림
    thread_ts = None
    if SLACK_THREAD_ENABLED:
        thread_ts = event.get("ts")
    else:
        say(f"🔍 <@{user}>님의 질문을 분석 중입니다...")

    try:
        if ASYNC_QUERY_ENABLED:
            # Phase 2: 비동기 폴링 방식 (§6.6)
            # ① POST /query → 202 + task_id
            post_resp = requests.post(
                f"{VANNA_API_URL}/query",
                json={
                    "question": text,
                    "slack_user_id": user,
                    "slack_channel_id": channel_id,
                    "conversation_id": thread_ts,  # [FR-24-02] thread_ts → FR-20 session_id
                },
                headers=_build_internal_headers(),
                timeout=30,
            )
            if post_resp.status_code not in (200, 202):
                _handle_error_response(post_resp, say, thread_ts=thread_ts)
                return

            task_id = post_resp.json().get("task_id")
            if not task_id:
                say(
                    "⚠️ AI 서버 응답에서 task_id를 찾을 수 없습니다.",
                    thread_ts=thread_ts,
                )
                return

            # ② "처리 중" 메시지 먼저 전송
            say("⏳ 처리 중입니다... 완료되면 알려드리겠습니다.", thread_ts=thread_ts)

            # ③ GET /query/{task_id} 폴링 (3초 간격, 최대 100회)
            result = None
            _progress_interval = 30  # 진행 중 메시지 전송 간격 (초)
            _elapsed = 0
            for _ in range(_ASYNC_POLL_MAX):
                time.sleep(_ASYNC_POLL_INTERVAL)
                _elapsed += _ASYNC_POLL_INTERVAL
                poll_resp = requests.get(
                    f"{VANNA_API_URL}/query/{task_id}",
                    headers=_build_internal_headers(),
                    timeout=10,
                )
                if poll_resp.status_code == 202:
                    if _elapsed % _progress_interval == 0:
                        say(f"⏳ 아직 처리 중입니다... ({_elapsed}초 경과)", thread_ts=thread_ts)
                    continue  # 아직 처리 중
                if poll_resp.status_code == 200:
                    result = poll_resp.json()
                    break
                # 오류 응답
                _handle_error_response(poll_resp, say, thread_ts=thread_ts)
                return

            if result is None:
                say(
                    "⚠️ 쿼리 처리 시간이 초과되었습니다. 조회 범위를 좁혀 다시 시도해 주세요.",
                    thread_ts=thread_ts,
                )
                return

        else:
            # Phase 1: 동기 방식 (하위 호환)
            response = requests.post(
                f"{VANNA_API_URL}/query",
                json={
                    "question": text,
                    "slack_user_id": user,
                    "slack_channel_id": channel_id,
                    "conversation_id": thread_ts,  # [FR-24-02] thread_ts → FR-20 session_id
                },
                headers=_build_internal_headers(),
                timeout=VANNA_API_TIMEOUT,  # NFR-06
            )
            if response.status_code != 200:
                _handle_error_response(response, say, thread_ts=thread_ts)
                return
            result = response.json()

        # ④ 결과 전송 (동기/비동기 공통) [FR-24-03]
        chart_base64 = result.get("chart_image_base64")

        # ① 헤더 + 질문 + SQL + 결과 테이블 먼저 전송
        say(blocks=_build_header_blocks(result), thread_ts=thread_ts)

        # ② 차트 업로드 후 채널에 실제 게시될 때까지 대기
        if chart_base64:
            try:
                image_bytes = base64.b64decode(chart_base64)
                upload_resp = client.files_upload_v2(
                    channel=channel_id,
                    thread_ts=thread_ts,  # [BUG-04] 스레드에 이미지 업로드
                    content=image_bytes,
                    filename="chart.png",
                    title="분석 차트",
                )
                # 채널에 파일이 실제로 나타날 때까지 폴링 (최대 3초)
                file_id = upload_resp["files"][0]["id"]
                for _ in range(15):
                    history = client.conversations_history(channel=channel_id, limit=5)
                    posted = any(
                        file_id in [f["id"] for f in msg.get("files", [])]
                        for msg in history.get("messages", [])
                    )
                    if posted:
                        break
                    time.sleep(0.2)
                logger.info("차트 이미지 업로드 완료")
            except Exception as e:
                logger.error(f"차트 업로드 실패: {e}")

        # ③ AI 분석 + Redash 링크 + 피드백 버튼 (차트 업로드 완료 후)
        say(blocks=_build_footer_blocks(result), thread_ts=thread_ts)

    except requests.Timeout:
        logger.error(f"vanna-api 타임아웃 ({VANNA_API_TIMEOUT}초)")
        say(
            "⚠️ AI 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
            thread_ts=thread_ts,
        )  # [FR-24-05]
    except Exception as e:
        # SEC-07: 내부 오류 상세는 로그에만 기록
        logger.error(f"vanna-api 연동 오류: {e}")
        say(
            "⚠️ AI 서버와 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            thread_ts=thread_ts,
        )  # [FR-24-05]


@app.action("feedback_positive")
def handle_positive_feedback(ack, body, client):
    """👍 피드백 처리 (FR-21)"""
    ack()
    history_id = body["actions"][0]["value"]
    slack_user_id = body["user"]["id"]
    try:
        requests.post(
            f"{VANNA_API_URL}/feedback",
            json={
                "history_id": history_id,
                "feedback": "positive",
                "slack_user_id": slack_user_id,
            },
            headers=_build_internal_headers(),
            timeout=10,
        )
        logger.info(f"긍정 피드백 전송: history_id={history_id}")
    except Exception as e:
        logger.error(f"긍정 피드백 전송 실패: {e}")


@app.action("feedback_negative")
def handle_negative_feedback(ack, body, client):
    """👎 피드백 처리 (FR-21)"""
    ack()
    history_id = body["actions"][0]["value"]
    slack_user_id = body["user"]["id"]
    try:
        requests.post(
            f"{VANNA_API_URL}/feedback",
            json={
                "history_id": history_id,
                "feedback": "negative",
                "slack_user_id": slack_user_id,
            },
            headers=_build_internal_headers(),
            timeout=10,
        )
        logger.info(f"부정 피드백 전송: history_id={history_id}")
    except Exception as e:
        logger.error(f"부정 피드백 전송 실패: {e}")


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    if not SLACK_APP_TOKEN:
        logger.error("SLACK_APP_TOKEN is missing!")
    else:
        logger.info("CAPA Slack Bot 시작 중 (Text-to-SQL 개선 버전)...")
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()
