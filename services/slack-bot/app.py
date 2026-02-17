import os
import logging
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from flask import Flask, jsonify
import threading

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
VANNA_API_URL = os.environ.get(
    "VANNA_API_URL", "http://vanna-api.vanna.svc.cluster.local:8000"
)
REPORT_API_URL = os.environ.get(
    "REPORT_API_URL", "http://report-generator.report.svc.cluster.local:8000"
)

# Slack App 초기화
app = App(token=SLACK_BOT_TOKEN)

# 헬스 체크용 Flask 앱
flask_app = Flask(__name__)


@flask_app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "slack-bot"}), 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=3000)


@app.event("app_mention")
def handle_mention(event, say):
    """@capa-bot 멘션 처리"""
    text = event["text"]
    user = event["user"]
    logger.info(f"Received mention from {user}: {text}")

    # 1. "리포트 생성" 명령어 확인
    if "리포트 생성" in text or "report" in text.lower():
        say(
            f"📊 <@{user}>님, 오늘의 성과 리포트 생성을 시작합니다. 잠시만 기다려주세요..."
        )
        try:
            response = requests.post(
                f"{REPORT_API_URL}/generate", params={"report_type": "daily"}, timeout=5
            )
            if response.status_code == 202 or response.status_code == 200:
                say(
                    "✅ 리포트 생성 요청이 성공했습니다. 분석이 완료되면 이 채널로 공유해 드릴게요."
                )
            else:
                say(f"❌ 리포트 서버 응답 오류: {response.status_code}")
        except Exception as e:
            logger.error(f"Error calling report generator: {e}")
            say(f"⚠️ 리포트 생성 요청 중 오류가 발생했습니다: {e}")
        return

    # 2. "echo" 명령어 확인 (디버깅용 유지)
    if "echo" in text.lower():
        message_parts = text.split("echo", 1)
        message = (
            message_parts[1].strip()
            if len(message_parts) > 1
            else "Echo할 메시지가 없습니다."
        )
        say(f"📢 Echo: {message}")
        return

    # 3. 기본: Vanna AI 자연어 질의
    say(f"🔍 <@{user}>님의 질문을 분석 중입니다: `{text}`")
    try:
        response = requests.post(
            f"{VANNA_API_URL}/query", json={"question": text}, timeout=60
        )
        if response.status_code == 200:
            result = response.json()
            answer = result.get("answer", "죄송합니다. 답변을 생성하지 못했습니다.")
            say(f"🤖 **AI 분석 결과:**\n{answer}")
        else:
            logger.error(f"Vanna API error: {response.status_code} - {response.text}")
            say(
                f"❌ AI 서버 응답 오류 ({response.status_code}). 잠시 후 다시 시도해주세요."
            )
    except Exception as e:
        logger.error(f"Error calling Vanna AI: {e}")
        say(f"⚠️ AI 연동 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    # 헬스 체크 서버 백그라운드 실행
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Slack Socket Mode 실행
    if not SLACK_APP_TOKEN:
        logger.error("SLACK_APP_TOKEN is missing!")
    else:
        logger.info("⚡️ CAPA Slack Bot starting (Vanna + Report Integrated)...")
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()
