import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# 환경 변수 로드 (.env 파일에서 토큰 가져오기)
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# Slack 앱 초기화
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.message("ping")
def message_hello(message, say):
    """
    사용자가 'ping'이라고 말하면 'Pong!'이라고 대답합니다.
    """
    say(f"Pong! 🏓 (받은 메시지: {message['text']})")

@app.message("안녕")
def message_hi(message, say):
    """
    '안녕' 인사에 반응합니다.
    """
    say("안녕하세요! 저는 테스트 봇입니다. 👋 무엇을 도와드릴까요?")

@app.event("app_mention")
def handle_mention(event, say):
    """
    봇을 멘션(@Bot)했을 때 반응합니다.
    """
    text = event["text"]
    
    if "ping" in text:
         say(f"Pong! 🏓 (받은 메시지: {text})")
    elif "안녕" in text:
        say("안녕하세요! 저는 테스트 봇입니다. 👋 무엇을 도와드릴까요?")
    else:
        say("부르셨나요? 테스트 중입니다! 🛠️\n('ping'이나 '안녕'이라고 말해보세요)")

def main():
    # Socket Mode로 봇 실행
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        print("❌ 에러: .env 파일에 SLACK_APP_TOKEN이 없습니다.")
        return

    handler = SocketModeHandler(app, app_token)
    print("🚀 테스트 봇이 실행되었습니다! Slack에서 말을 걸어보세요.")
    handler.start()

if __name__ == "__main__":
    main()
