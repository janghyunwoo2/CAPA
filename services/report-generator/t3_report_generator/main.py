"""보고서 생성 메인 모듈.

매일 아침 08:00에 Airflow DAG에서 호출됩니다.
날짜에 따라 일간/주간/월간 섹션을 동적으로 추가하여 보고서를 생성합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from athena_client import (
    get_daily_kpi,
    get_weekly_list,
    get_category_performance,
    get_shop_top10,
    get_shop_bottom10,
    get_funnel_data,
)
import markdown_builder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_month_start(date: datetime) -> datetime:
    """주어진 날짜의 월초(1일)를 반환합니다."""
    return date.replace(day=1)


def get_previous_month_end(date: datetime) -> datetime:
    """주어진 날짜의 전월 마지막 날을 반환합니다."""
    first_day = date.replace(day=1)
    last_day_prev_month = first_day - timedelta(days=1)
    return last_day_prev_month


def is_monday(date: datetime) -> bool:
    """월요일 여부를 반환합니다 (0=월요일)."""
    return date.weekday() == 0


def is_month_start(date: datetime) -> bool:
    """월초(1일) 여부를 반환합니다."""
    return date.day == 1


def generate_report(date: datetime = None) -> str:
    """보고서를 생성합니다.

    Args:
        date: 보고서 생성 날짜 (기본값: 오늘)

    Returns:
        마크다운 형식의 보고서 문자열
    """
    if date is None:
        date = datetime.now()

    logger.info(f"보고서 생성 시작: {date.strftime('%Y-%m-%d %H:%M:%S')}")

    # =========================================================================
    # 1단계: 날짜 판단
    # =========================================================================
    is_mon = is_monday(date)
    is_first_day = is_month_start(date)

    logger.info(f"  - 월요일: {is_mon}, 1일: {is_first_day}")

    # =========================================================================
    # 2단계: 데이터 범위 결정
    # =========================================================================
    month_start = get_month_start(date)
    yesterday = date - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    if is_first_day:
        # 1일: 전월 데이터 조회
        prev_month_end = get_previous_month_end(date)
        prev_month_start = prev_month_end.replace(day=1)

        daily_start_str = prev_month_start.strftime("%Y-%m-%d")
        daily_end_str = prev_month_end.strftime("%Y-%m-%d")

        logger.info(f"  - 월초(1일) 모드: 전월 {daily_start_str} ~ {daily_end_str}")
    else:
        # 2~31일: 현월 누적 데이터 조회
        daily_start_str = month_start.strftime("%Y-%m-%d")
        daily_end_str = yesterday_str

        logger.info(f"  - 월중 모드: 현월 {daily_start_str} ~ {daily_end_str}")

    # =========================================================================
    # 3단계: 데이터 조회
    # =========================================================================
    logger.info("  - 데이터 조회 시작...")

    # 일간 데이터
    try:
        daily_data = get_daily_kpi(daily_start_str, daily_end_str)
        logger.info(f"    ✓ 일간 데이터 조회 완료: {len(daily_data.get('daily_breakdown', []))} 일")
    except Exception as e:
        logger.error(f"    ✗ 일간 데이터 조회 실패: {e}")
        raise

    # 주간 데이터 (월요일일 때만)
    weekly_list = None
    if is_mon:
        try:
            month_start_str = month_start.strftime("%Y-%m-%d")
            weekly_list = get_weekly_list(month_start_str, daily_end_str)
            logger.info(f"    ✓ 주간 데이터 조회 완료: {len(weekly_list)} 주차")
        except Exception as e:
            logger.error(f"    ✗ 주간 데이터 조회 실패: {e}")
            # 주간 데이터 실패는 보고서 중단이 아님
            weekly_list = None

    # 월간 데이터 (1일일 때만)
    monthly_data = None
    if is_first_day:
        try:
            categories = get_category_performance(daily_start_str, daily_end_str)
            top10 = get_shop_top10(daily_start_str, daily_end_str)
            bottom10 = get_shop_bottom10(daily_start_str, daily_end_str)
            funnel = get_funnel_data(daily_start_str, daily_end_str)

            monthly_data = {
                "summary": daily_data["summary"],
                "categories": categories,
                "top10": top10,
                "bottom10": bottom10,
                "funnel": funnel,
            }
            logger.info(
                f"    ✓ 월간 데이터 조회 완료: "
                f"카테고리 {len(categories)}, 상점 {len(top10)}+{len(bottom10)}"
            )
        except Exception as e:
            logger.error(f"    ✗ 월간 데이터 조회 실패: {e}")
            # 월간 데이터 실패는 보고서 중단이 아님
            monthly_data = None

    # =========================================================================
    # 4단계: 마크다운 생성
    # =========================================================================
    logger.info("  - 마크다운 생성 시작...")

    try:
        markdown = markdown_builder.build(
            date=date,
            daily_data=daily_data,
            weekly_list=weekly_list,
            monthly_data=monthly_data,
        )
        logger.info("    ✓ 마크다운 생성 완료")
    except Exception as e:
        logger.error(f"    ✗ 마크다운 생성 실패: {e}")
        raise

    # =========================================================================
    # 5단계: 결과 반환
    # =========================================================================
    logger.info("✓ 보고서 생성 완료")

    return markdown


def main(date_str: str = None) -> dict[str, Any]:
    """진입점 함수. Airflow DAG에서 호출됩니다.

    Args:
        date_str: 보고서 생성 날짜 (YYYY-MM-DD 형식, 기본값: 오늘)

    Returns:
        {
            "status": "success" | "error",
            "date": "YYYY-MM-DD",
            "markdown": "...",
            "error": "..." (error인 경우만)
        }
    """
    try:
        # 날짜 파싱
        if date_str:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date = datetime.now()

        # 보고서 생성
        markdown = generate_report(date)

        return {
            "status": "success",
            "date": date.strftime("%Y-%m-%d"),
            "markdown": markdown,
        }

    except Exception as e:
        logger.error(f"✗ 보고서 생성 실패: {e}", exc_info=True)

        return {
            "status": "error",
            "date": date.strftime("%Y-%m-%d") if date else "unknown",
            "error": str(e),
        }


if __name__ == "__main__":
    # 테스트 실행
    import sys

    if len(sys.argv) > 1:
        result = main(sys.argv[1])
    else:
        result = main()

    if result["status"] == "success":
        print(result["markdown"])
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
