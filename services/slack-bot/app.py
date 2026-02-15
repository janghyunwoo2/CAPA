import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from flask import Flask, jsonify
import threading

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack App 초기화
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

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

    # "@capa-bot echo <메시지>" 파싱
    if "echo" in text.lower():
        try:
            # "echo" 이후의 텍스트 추출
            message_parts = text.split("echo", 1)
            if len(message_parts) > 1:
                message = message_parts[1].strip()
                say(f"Echo: {message}")
            else:
                say("Echo할 메시지가 없습니다.")
        except Exception as e:
            logger.error(f"Error processing echo: {e}")
            say(f"오류가 발생했습니다: {e}")
    else:
        say(f"안녕하세요 <@{user}>님! 'echo <메시지>'를 입력해보세요.")


if __name__ == "__main__":
    # 헬스 체크 서버 백그라운드 실행
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Slack Socket Mode 실행
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        logger.error("SLACK_APP_TOKEN is missing!")
    else:
        logger.info("⚡️ Slack Bot Echo starting...")
        handler = SocketModeHandler(app, app_token)
        handler.start()
