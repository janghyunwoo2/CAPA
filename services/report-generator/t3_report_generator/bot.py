"""Slack 봇 모듈.

Slack 멘션 이벤트를 처리하여 광고 성과 리포트를 PDF로 생성합니다.
Claude API를 사용하여 데이터 분석 보고서를 작성합니다.
FastAPI 기반 헬스 체크 서버를 별도 스레드로 실행합니다. 
"""

import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

import athena_client
import report_writer as rw
import pdf_exporter

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)

# Slack 앱 초기화
app: App = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# 봇 사용자 ID 캐싱
_bot_user_id: str | None = None

# 리포트 키워드
REPORT_KEYWORDS: list[str] = ["리포트", "보고서", "report"]


def _get_bot_user_id() -> str:
    """캐싱된 봇 사용자 ID를 반환합니다."""
    global _bot_user_id
    if _bot_user_id is None:
        _bot_user_id = app.client.auth_test()["user_id"]
        logger.info(f"봇 사용자 ID 확인: {_bot_user_id}")
    return _bot_user_id


# --- FastAPI 헬스 체크 서버 ---
health_app: FastAPI = FastAPI()


@health_app.get("/health")
def health_check() -> dict[str, str]:
    """헬스 체크 엔드포인트."""
    return {"status": "ok", "service": "report-generator"}


def _start_health_server() -> None:
    """헬스 체크 서버를 별도 스레드에서 시작합니다."""
    uvicorn.run(health_app, host="0.0.0.0", port=8000, log_level="warning")


# --- Slack 이벤트 핸들러 ---


@app.event("app_mention")
def handle_mention(event: dict, say: callable) -> None:
    """멘션 이벤트를 처리합니다.

    Args:
        event: Slack 이벤트 데이터
        say: 메시지 전송 함수
    """
    bot_user_id: str = _get_bot_user_id()
    text: str = event["text"].replace(f"<@{bot_user_id}>", "").strip()
    logger.info(f"수신된 메시지: {text}")

    try:
        if any(keyword in text.lower() for keyword in REPORT_KEYWORDS):
            _handle_report_request(event, say, text)
        else:
            say(
                "안녕하세요! 리포트가 필요하시면 '리포트' 또는 '보고서'라고 말씀해주세요.\n"
                "예: `@Bot 주간 리포트 작성해줘`"
            )
    except Exception as e:
        logger.error(f"요청 처리 중 오류 발생: {e}", exc_info=True)
        say(f"죄송합니다. 처리 중 오류가 발생했습니다.\nError: {str(e)}")


def _handle_report_request(event: dict, say: callable, text: str) -> None:
    """리포트 생성 요청을 처리합니다.

    Athena 데이터 조회 → Claude API 보고서 작성 → PDF 생성 → Slack 업로드

    Args:
        event: Slack 이벤트 데이터
        say: 메시지 전송 함수
        text: 사용자 메시지 텍스트
    """
    say(f"'{text}' 요청을 확인했습니다. 리포트를 생성 중입니다... 잠시만 기다려주세요.")

    # 날짜 범위 설정 (최근 30일)
    end_date: str = datetime.now().strftime("%Y-%m-%d")
    start_date: str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # 1. Athena에서 데이터 조회
    logger.info(f"Athena 데이터 조회 중: {start_date} ~ {end_date}")
    daily_df = athena_client.query_daily_summary(start_date, end_date)
    kpi_df = athena_client.query_kpi_summary(start_date, end_date)
    category_df = athena_client.query_category_performance(start_date, end_date)
    shop_df = athena_client.query_shop_performance(start_date, end_date)

    # 2. Claude API로 보고서 작성
    logger.info("Claude API로 보고서 작성 중...")
    writer = rw.ReportWriter()
    report_text: str = writer.generate_report(
        daily_df, kpi_df, category_df, shop_df, start_date, end_date
    )

    # 3. PDF 생성
    logger.info("PDF 생성 중...")
    pdf_filename: str = f"ad_report_{start_date}_{end_date}.pdf"
    pdf_path: str = pdf_exporter.create_pdf(report_text, daily_df, pdf_filename)

    # 4. Slack에 PDF 업로드
    logger.info("Slack에 PDF 업로드 중...")
    app.client.files_upload_v2(
        channel=event["channel"],
        file=pdf_path,
        title=f"광고 성과 리포트 ({start_date} ~ {end_date})",
        initial_comment="요청하신 리포트입니다.",
    )
    logger.info(f"리포트 업로드 완료: {pdf_path}")

    # 임시 PDF 파일 정리
    pdf_file = Path(pdf_path)
    if pdf_file.exists():
        pdf_file.unlink()


def main() -> None:
    """봇을 시작합니다. 헬스 체크 서버와 Slack 봇을 동시에 실행합니다."""
    # 봇 사용자 ID 사전 캐싱
    _get_bot_user_id()

    # 헬스 체크 서버를 별도 스레드로 시작
    health_thread: threading.Thread = threading.Thread(
        target=_start_health_server, daemon=True
    )
    health_thread.start()
    logger.info("헬스 체크 서버 시작 (port=8000)")

    # Slack 봇 시작 (메인 스레드)
    handler: SocketModeHandler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Slack 봇 연결 완료. 멘션을 기다리는 중...")
    handler.start()


if __name__ == "__main__":
    main()
