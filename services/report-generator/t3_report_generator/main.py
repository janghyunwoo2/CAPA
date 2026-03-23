"""보고서 생성 메인 모듈.

Airflow DAG 또는 직접 실행으로 호출됩니다.
일간/주간/월간 보고서를 각각 독립적으로 생성합니다.
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Any
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from athena_client import (
    get_daily_kpi,
    get_category_performance,
    get_shop_top5,
    get_shop_bottom5,
    get_funnel_data,
)
import markdown_builder
import pdf_exporter
import slack_notifier

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ============================================================================
# 날짜 유틸
# ============================================================================

def _parse_date(date_str: str = None) -> datetime:
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d")
    kst_tz = ZoneInfo('Asia/Seoul')
    return datetime.now(kst_tz)


def _get_month_start(date: datetime) -> datetime:
    return date.replace(day=1)


def _get_previous_month_range(date: datetime) -> tuple[str, str]:
    """전월 1일 ~ 전월 마지막 날"""
    first_day = date.replace(day=1)
    prev_month_end = first_day - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    return prev_month_start.strftime("%Y-%m-%d"), prev_month_end.strftime("%Y-%m-%d")


def _save_and_send(markdown: str, daily_breakdown: list, date: datetime, report_type: str, only_upload: bool = False):
    """마크다운 저장 → PDF 생성 → Slack 전송"""
    date_str = date.strftime("%Y-%m-%d")

    # 마크다운 저장
    md_filename = f"report_{report_type}_{date_str}.md"
    try:
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(markdown)
        logger.info(f"마크다운 저장: {md_filename}")
    except Exception as e:
        logger.warning(f"마크다운 저장 실패: {e}")

    # PDF 생성
    pdf_filename = f"report_{report_type}_{date_str}.pdf"
    try:
        pdf_path = pdf_exporter.create_pdf(
            report_markdown=markdown,
            daily_breakdown=daily_breakdown,
            output_path=pdf_filename,
        )
        logger.info(f"PDF 저장: {pdf_path}")

        # Slack 전송
        if slack_notifier.send_report_to_slack(pdf_path, date_str, report_type, only_upload=only_upload):
            logger.info(f"Slack 전송 완료 (only_upload={only_upload})")
        else:
            logger.info("Slack 전송 실패 또는 설정 안 됨")

        return pdf_path
    except Exception as e:
        logger.warning(f"PDF 생성 실패: {e}")
        return None


# ============================================================================
# 일간 보고서
# ============================================================================

def generate_daily_report(date_str: str = None, only_upload: bool = False) -> dict[str, Any]:
    """일간 보고서 생성 - 현월 누적 (월초~어제)"""
    date = _parse_date(date_str)
    logger.info(f"[일간] 보고서 생성 시작: {date.strftime('%Y-%m-%d')}")

    yesterday = date - timedelta(days=1)
    start_str = _get_month_start(date).strftime("%Y-%m-%d")
    end_str = yesterday.strftime("%Y-%m-%d")

    logger.info(f"[일간] 데이터 범위: {start_str} ~ {end_str}")

    try:
        data = get_daily_kpi(start_str, end_str)
        markdown = markdown_builder.build_daily(date, data, start_str, end_str)

        _save_and_send(markdown, data.get("daily_breakdown", []), date, "daily", only_upload=only_upload)

        logger.info("[일간] 보고서 생성 완료")
        return {"status": "success", "date": date.strftime("%Y-%m-%d"), "markdown": markdown}

    except Exception as e:
        logger.error(f"[일간] 보고서 생성 실패: {e}", exc_info=True)
        return {"status": "error", "date": date.strftime("%Y-%m-%d"), "error": str(e)}


# ============================================================================
# 주간 보고서
# ============================================================================

def generate_weekly_report(date_str: str = None, only_upload: bool = False) -> dict[str, Any]:
    """주간 보고서 생성 - 지난주 월요일~일요일"""
    date = _parse_date(date_str)
    logger.info(f"[주간] 보고서 생성 시작: {date.strftime('%Y-%m-%d')}")

    current_monday = date - timedelta(days=date.weekday())
    prev_week_start = current_monday - timedelta(days=7)
    prev_week_end = current_monday - timedelta(days=1)

    start_str = prev_week_start.strftime("%Y-%m-%d")
    end_str = prev_week_end.strftime("%Y-%m-%d")

    logger.info(f"[주간] 데이터 범위: {start_str} ~ {end_str}")

    try:
        data = get_daily_kpi(start_str, end_str)
        weekly_data = {
            "start_date": start_str,
            "end_date": end_str,
            "summary": data["summary"],
            "daily_breakdown": data["daily_breakdown"],
        }
        markdown = markdown_builder.build_weekly(date, weekly_data)

        _save_and_send(markdown, data.get("daily_breakdown", []), date, "weekly", only_upload=only_upload)

        logger.info("[주간] 보고서 생성 완료")
        return {"status": "success", "date": date.strftime("%Y-%m-%d"), "markdown": markdown}

    except Exception as e:
        logger.error(f"[주간] 보고서 생성 실패: {e}", exc_info=True)
        return {"status": "error", "date": date.strftime("%Y-%m-%d"), "error": str(e)}


# ============================================================================
# 월간 보고서
# ============================================================================

def generate_monthly_report(date_str: str = None, only_upload: bool = False) -> dict[str, Any]:
    """월간 보고서 생성 - 전월 전체"""
    date = _parse_date(date_str)
    logger.info(f"[월간] 보고서 생성 시작: {date.strftime('%Y-%m-%d')}")

    start_str, end_str = _get_previous_month_range(date)

    logger.info(f"[월간] 데이터 범위: {start_str} ~ {end_str}")

    try:
        summary_data = get_daily_kpi(start_str, end_str)
        categories = get_category_performance(start_str, end_str)
        top10 = get_shop_top5(start_str, end_str)
        bottom10 = get_shop_bottom5(start_str, end_str)
        funnel = get_funnel_data(start_str, end_str)

        monthly_data = {
            "summary": summary_data["summary"],
            "daily_breakdown": summary_data["daily_breakdown"],
            "categories": categories,
            "top10": top10,
            "bottom10": bottom10,
            "funnel": funnel,
        }
        markdown = markdown_builder.build_monthly(date, monthly_data, start_str, end_str)

        _save_and_send(markdown, summary_data.get("daily_breakdown", []), date, "monthly", only_upload=only_upload)

        logger.info("[월간] 보고서 생성 완료")
        return {"status": "success", "date": date.strftime("%Y-%m-%d"), "markdown": markdown}

    except Exception as e:
        logger.error(f"[월간] 보고서 생성 실패: {e}", exc_info=True)
        return {"status": "error", "date": date.strftime("%Y-%m-%d"), "error": str(e)}


def send_final_notification(report_types: list[str], date_str: str = None) -> bool:
    """통합 알림 전송 래퍼"""
    date = _parse_date(date_str)
    return slack_notifier.send_combined_notification(report_types, date.strftime("%Y-%m-%d"))


# ============================================================================
# CLI 진입점 (venv 테스트용)
# ============================================================================

if __name__ == "__main__":
    # 사용법:
    #   python main.py 2026-03-23 daily
    #   python main.py 2026-03-23 weekly --only-upload
    #   python main.py 2026-03-23 notify (일간/주간/월간 여부를 날짜 기준으로 자동 판단하여 통합알림)

    import sys
    
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    type_arg = sys.argv[2] if len(sys.argv) > 2 else "daily"
    # 세 번째 인자에 --only-upload가 있는지 확인
    only_upload = "--only-upload" in sys.argv

    if type_arg == "notify":
        # 알림 로직: 날짜를 기준으로 어떤 리포트가 생성되어야 하는지 판단하여 통합 알림 발송
        date = _parse_date(date_arg)
        reports = ["daily"]
        if date.weekday() == 0:  # 월요일
            reports.append("weekly")
        if date.day == 3:       # 3일
            reports.append("monthly")
        
        logger.info(f"통합 알림 발송 시도: {reports} (기준일: {date.strftime('%Y-%m-%d')})")
        if send_final_notification(reports, date_arg):
            logger.info("통합 알림 전송 성공")
        else:
            logger.info("통합 알림 전송 실패")
        sys.exit(0)

    dispatch = {
        "daily": generate_daily_report,
        "weekly": generate_weekly_report,
        "monthly": generate_monthly_report,
    }

    if type_arg not in dispatch:
        print(f"[오류] 알 수 없는 타입: {type_arg} (daily/weekly/monthly/notify 중 선택)", file=sys.stderr)
        sys.exit(1)

    result = dispatch[type_arg](date_arg, only_upload=only_upload)

    if result["status"] == "success":
        try:
            # 마크다운 내용 출력 (로그용)
            # print(result["markdown"]) 
            pass
        except:
            pass
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
