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


def send_report_to_slack(pdf_path: str, report_date: str = None, report_type: str = "daily", only_upload: bool = False) -> bool:
    """PDF 보고서를 Slack으로 전송합니다.

    Args:
        pdf_path: PDF 파일 경로
        report_date: 보고서 날짜 (YYYY-MM-DD 형식)
        report_type: 보고서 타입 (daily/weekly/monthly)
        only_upload: 메시지 없이 파일만 업로드할지 여부

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
        # 보고서 타입별 이모지 및 라벨
        type_labels = {
            "daily": ("🔵", "일간"),
            "weekly": ("📅", "주간"),
            "monthly": ("📊", "월간"),
        }
        emoji, label = type_labels.get(report_type, ("📋", "보고서"))

        # 메시지 구성
        if only_upload:
            title = f"PDF - {label} ({report_date if report_date else ''})"
            comment = None
        elif report_date:
            daily_url = os.getenv("DAILY_DASHBOARD_URL", "")
            period_url = os.getenv("PERIOD_DASHBOARD_URL", "")
            title = f"CAPA 광고 성과 보고서 - [{label}] ({report_date})"
            comment = f"{emoji} [{label}] {report_date} 보고서 생성 완료"
            if daily_url or period_url:
                if daily_url: comment += f"\n🔗 *일간 대시보드*: <{daily_url}|클릭하여이동>"
                if period_url: comment += f"\n🔗 *기간 대시보드*: <{period_url}|클릭하여이동>"
        else:
            daily_url = os.getenv("DAILY_DASHBOARD_URL", "")
            period_url = os.getenv("PERIOD_DASHBOARD_URL", "")
            title = f"CAPA 광고 성과 보고서 - [{label}]"
            comment = f"{emoji} [{label}] 보고서 생성 완료"
            if daily_url or period_url:
                if daily_url: comment += f"\n🔗 *일간 대시보드*: <{daily_url}|클릭하여이동>"
                if period_url: comment += f"\n🔗 *기간 대시보드*: <{period_url}|클릭하여이동>"

        # PDF 파일 업로드
        slack_app.client.files_upload_v2(
            channel=slack_channel_id,
            file=pdf_path,
            title=title,
            initial_comment=comment,
        )
        logger.info(f"✓ Slack 파일 업로드 완료 ({label}, only_upload={only_upload})")
        return True

    except Exception as e:
        logger.error(f"✗ Slack 전송 실패: {e}")
        return False


def send_combined_notification(report_types: list[str], report_date: str) -> bool:
    """여러 보고서가 생성되었음을 알리는 통합 메시지를 전송합니다.

    Args:
        report_types: 생성된 보고서 타입 리스트 (예: ['daily', 'weekly'])
        report_date: 보고서 날짜

    Returns:
        성공 여부
    """
    slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
    daily_url = os.getenv("DAILY_DASHBOARD_URL", "")
    period_url = os.getenv("PERIOD_DASHBOARD_URL", "")

    if not slack_app or not slack_channel_id:
        return False

    try:
        type_to_label = {
            "daily": "일간",
            "weekly": "주간",
            "monthly": "월간",
        }
        labels = [type_to_label.get(t, t) for t in report_types]
        labels_str = ", ".join(labels)

        dashboard_text = ""
        if daily_url: dashboard_text += f"🔗 *일간 대시보드*: <{daily_url}|클릭하여이동>\n"
        if period_url: dashboard_text += f"🔗 *기간 대시보드*: <{period_url}|클릭하여이동>\n"

        message = (
            f"🚀 *CAPA 광고 성과 보고서 생성 완료* ({report_date})\n\n"
            f"{dashboard_text}"
            f"✅ *포함된 보고서*: {labels_str}\n\n"
            f"_상단에 업로드된 PDF 파일들을 확인해 주세요._"
        )

        slack_app.client.chat_postMessage(
            channel=slack_channel_id,
            text=message,
        )
        logger.info(f"✓ Slack 통합 알림 전송 완료 ({labels_str})")
        return True
    except Exception as e:
        logger.error(f"✗ Slack 통합 알림 전송 실패: {e}")
        return False
