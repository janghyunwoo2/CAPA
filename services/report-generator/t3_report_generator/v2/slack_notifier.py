"""Slack 알림 모듈.

생성된 PDF 보고서를 Slack 채널로 전송합니다.
"""

import logging
import os
from pathlib import Path

from slack_bolt import App

logger = logging.getLogger(__name__)

# Slack 앱 초기화
slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
slack_app = App(token=slack_bot_token) if slack_bot_token else None


def send_report_to_slack(pdf_path: str, report_date: str = None) -> bool:
    """PDF 보고서를 Slack으로 전송합니다.

    Args:
        pdf_path: PDF 파일 경로
        report_date: 보고서 날짜 (YYYY-MM-DD 형식)

    Returns:
        성공 여부
    """
    # 환경 변수 로드
    slack_channel_id = os.getenv("SLACK_CHANNEL_ID")

    if not slack_app or not slack_channel_id:
        logger.info("SLACK_BOT_TOKEN 또는 SLACK_CHANNEL_ID가 설정되지 않음. Slack 전송 스킵.")
        return False

    # PDF 파일 확인
    if not Path(pdf_path).exists():
        logger.error(f"PDF 파일이 없음: {pdf_path}")
        return False

    try:
        # 메시지 구성
        if report_date:
            title = f"CAPA 광고 성과 보고서 ({report_date})"
            comment = f"📊 {report_date} 보고서 생성 완료"
        else:
            title = "CAPA 광고 성과 보고서"
            comment = "📊 CAPA 광고 성과 보고서 생성 완료"

        # PDF 파일 업로드
        slack_app.client.files_upload_v2(
            channel=slack_channel_id,
            file=pdf_path,
            title=title,
            initial_comment=comment,
        )
        logger.info("✓ Slack 전송 완료")
        return True

    except Exception as e:
        logger.error(f"✗ Slack 전송 실패: {e}")
        return False
