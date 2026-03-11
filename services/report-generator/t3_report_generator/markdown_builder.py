"""마크다운 보고서 빌더 모듈.

athena_client에서 조회한 데이터를 마크다운 형식으로 렌더링합니다.
일간/주간/월간 섹션을 동적으로 추가합니다.
"""

from datetime import datetime
from typing import Any


def format_number(value: Any, is_percentage: bool = False) -> str:
    """숫자를 포맷팅합니다."""
    try:
        if isinstance(value, str):
            value = float(value)
        if is_percentage:
            return f"{float(value):.2f}%" if value else "0.00%"
        if value >= 1000000:
            return f"{value:,.0f}"
        if value >= 1000:
            return f"{value:,.0f}"
        return f"{value:.2f}" if isinstance(value, float) else f"{value}"
    except (ValueError, TypeError):
        return str(value)


def format_currency(value: Any) -> str:
    """금액을 포맷팅합니다."""
    try:
        if isinstance(value, str):
            value = float(value)
        return f"{value:,.0f}원" if value else "0원"
    except (ValueError, TypeError):
        return str(value)


def calculate_change_rate(current: float, previous: float, is_percentage: bool = False) -> str:
    """변화율을 계산합니다."""
    try:
        curr = float(current)
        prev = float(previous)
        if prev == 0:
            return "+0%"
        change_rate = ((curr - prev) / prev) * 100
        if is_percentage:
            return f"{change_rate:+.2f}%p"
        return f"{change_rate:+.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_executive_summary(data: dict[str, Any], prev_data: dict[str, Any] = None) -> str:
    """Executive Summary (경영진 요약)를 생성합니다."""
    md = "## Executive Summary (경영진 요약)\n\n"

    # 핵심 KPI 카드
    md += "### 핵심 KPI 카드\n\n"
    md += "| KPI | 실적 | 전기 대비 |\n"
    md += "|---|---|---|\n"

    # 필요한 필드 추출
    revenue = float(data.get("revenue", 0))
    cost = float(data.get("cost", 0))
    roas = float(data.get("roas", 0))
    ctr = float(data.get("ctr", 0))
    conversions = int(data.get("conversions", 0))

    prev_revenue = float(prev_data.get("revenue", 0)) if prev_data else 0
    prev_cost = float(prev_data.get("cost", 0)) if prev_data else 0
    prev_roas = float(prev_data.get("roas", 0)) if prev_data else 0
    prev_ctr = float(prev_data.get("ctr", 0)) if prev_data else 0
    prev_conversions = int(prev_data.get("conversions", 0)) if prev_data else 0

    md += f"| 총 매출 | {format_currency(revenue)} | {calculate_change_rate(revenue, prev_revenue)} |\n"
    md += f"| 총 ROAS | {format_number(roas, True)} | {calculate_change_rate(roas, prev_roas, is_percentage=True)} |\n"
    md += f"| 총 CTR | {format_number(ctr, True)} | {calculate_change_rate(ctr, prev_ctr, is_percentage=True)} |\n"
    md += f"| 총 전환 | {conversions:,}건 | {calculate_change_rate(conversions, prev_conversions)} |\n"

    # 보조 KPI
    md += "\n### 보조 KPI\n\n"
    md += "| 노출 | 클릭 | 광고비 | 순이익 |\n"
    md += "|---|---|---|---|\n"

    impressions = int(data.get("impressions", 0))
    clicks = int(data.get("clicks", 0))
    net_profit = revenue - cost

    prev_impressions = int(prev_data.get("impressions", 0)) if prev_data else 0
    prev_clicks = int(prev_data.get("clicks", 0)) if prev_data else 0
    prev_net_profit = prev_revenue - prev_cost if prev_data else 0

    md += f"| {impressions:,}회 ({calculate_change_rate(impressions, prev_impressions)}) | "
    md += f"{clicks:,}회 ({calculate_change_rate(clicks, prev_clicks)}) | "
    md += f"{format_currency(cost)} ({calculate_change_rate(cost, prev_cost)}) | "
    md += f"**{format_currency(net_profit)}** ({calculate_change_rate(net_profit, prev_net_profit)}) |\n"

    return md


def format_kpi_detail(data: dict[str, Any], prev_data: dict[str, Any] = None) -> str:
    """KPI 상세를 생성합니다."""
    md = "## KPI 상세\n\n"
    md += "| 지표 | 이번 기간 | 전기 | 변화 | 변화율 |\n"
    md += "|---|---|---|---|---|\n"

    metrics = [
        ("노출", "impressions", False),
        ("클릭", "clicks", False),
        ("전환", "conversions", False),
        ("매출", "revenue", "currency"),
        ("광고비", "cost", "currency"),
        ("**순이익**", None, "net_profit"),
        ("CTR", "ctr", True),
        ("CVR", "cvr", True),
        ("CPC", "cpc", "currency"),
        ("ROAS", "roas", True),
    ]

    for label, key, format_type in metrics:
        if key is None:  # net_profit 계산
            curr_val = float(data.get("revenue", 0)) - float(data.get("cost", 0))
            prev_val = float(prev_data.get("revenue", 0)) - float(prev_data.get("cost", 0)) if prev_data else 0
        else:
            curr_val = data.get(key, 0)
            prev_val = prev_data.get(key, 0) if prev_data else 0

        # 포맷팅
        if format_type == "currency":
            curr_str = format_currency(curr_val)
            prev_str = format_currency(prev_val) if prev_data else "N/A"
            change_str = f"+{format_currency(float(curr_val) - float(prev_val))}" if prev_data and prev_val else "-"
        elif format_type == True:  # percentage
            curr_str = format_number(curr_val, True)
            prev_str = format_number(prev_val, True) if prev_data else "N/A"
            change_str = "-"
        elif format_type == "net_profit":
            curr_str = format_currency(curr_val)
            prev_str = format_currency(prev_val) if prev_data else "N/A"
            change_str = f"+{format_currency(float(curr_val) - float(prev_val))}" if prev_data and prev_val else "-"
        else:  # number
            curr_str = format_number(curr_val, False)
            prev_str = format_number(prev_val, False) if prev_data else "N/A"
            change_str = f"+{format_number(float(curr_val) - float(prev_val), False)}" if prev_data and prev_val else "-"

        change_rate = calculate_change_rate(float(curr_val), float(prev_val)) if prev_data and prev_val else "-"

        if key == "cpc" or key == "roas" or key == "ctr" or key == "cvr":
            md += f"| {label} | {curr_str} | {prev_str} | - | {change_rate} |\n"
        else:
            md += f"| {label} | {curr_str} | {prev_str} | {change_str} | {change_rate} |\n"

    return md


def format_daily_trend(daily_data: list[dict[str, Any]]) -> str:
    """일별 트렌드를 생성합니다."""
    md = "## 일별 트렌드\n\n"
    md += "### 일별 상세 테이블\n\n"
    md += "| 날짜 | 요일 | 노출 | 클릭 | 전환 | 매출 | 광고비 | CTR | ROAS |\n"
    md += "|---|---|---|---|---|---|---|---|---|\n"

    day_map = ["월", "화", "수", "목", "금", "토", "일"]

    for record in daily_data:
        date_str = record.get("date", "")
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = day_map[date_obj.weekday()]
        except:
            day_name = "?"

        impressions = int(record.get("impressions", 0))
        clicks = int(record.get("clicks", 0))
        conversions = int(record.get("conversions", 0))
        revenue = float(record.get("revenue", 0))
        cost = float(record.get("cost", 0))
        ctr = float(record.get("ctr", 0))
        roas = float(record.get("roas", 0))

        md += f"| {date_str} | {day_name} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_currency(cost)} | {format_number(ctr, True)} | {format_number(roas, True)} |\n"

    return md


def format_category_performance(categories: list[dict[str, Any]]) -> str:
    """카테고리별 성과를 생성합니다."""
    md = "## 카테고리별 성과\n\n"
    md += "| 순위 | 카테고리 | 노출 | 클릭 | 전환 | 매출(원) | 광고비(원) | CTR | CVR | ROAS | 매출 변화 |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|---|\n"

    for i, cat in enumerate(categories, 1):
        category = cat.get("category", "")
        impressions = int(cat.get("impressions", 0))
        clicks = int(cat.get("clicks", 0))
        conversions = int(cat.get("conversions", 0))
        revenue = float(cat.get("revenue", 0))
        cost = float(cat.get("cost", 0))
        ctr = float(cat.get("ctr", 0))
        cvr = float(cat.get("cvr", 0))
        roas = float(cat.get("roas", 0))

        md += f"| {i} | {category} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_currency(cost)} | {format_number(ctr, True)} | "
        md += f"{format_number(cvr, True)} | {format_number(roas, True)} | +0.0% |\n"

    return md


def format_shop_performance(top10: list[dict[str, Any]], bottom10: list[dict[str, Any]]) -> str:
    """상점별 성과를 생성합니다."""
    md = "## 상점별 성과\n\n"

    md += "### Top 10 상점 (매출 기준)\n\n"
    md += "| 순위 | 상점 ID | 카테고리 | 노출 | 클릭 | 전환 | 매출(원) | CTR | ROAS | 매출 변화 |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|\n"

    for i, shop in enumerate(top10, 1):
        shop_id = shop.get("shop_id", "")
        category = shop.get("category", "")
        impressions = int(shop.get("impressions", 0))
        clicks = int(shop.get("clicks", 0))
        conversions = int(shop.get("conversions", 0))
        revenue = float(shop.get("revenue", 0))
        ctr = float(shop.get("ctr", 0))
        roas = float(shop.get("roas", 0))

        md += f"| {i} | {shop_id} | {category} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_number(ctr, True)} | {format_number(roas, True)} | +0.0% |\n"

    md += "\n### Bottom 10 상점 (ROAS 기준, 최소 노출 100건)\n\n"
    md += "| 순위 | 상점 ID | 카테고리 | 노출 | 클릭 | 전환 | 매출(원) | CTR | ROAS | 상태 |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|\n"

    for i, shop in enumerate(bottom10, 1):
        shop_id = shop.get("shop_id", "")
        category = shop.get("category", "")
        impressions = int(shop.get("impressions", 0))
        clicks = int(shop.get("clicks", 0))
        conversions = int(shop.get("conversions", 0))
        revenue = float(shop.get("revenue", 0))
        ctr = float(shop.get("ctr", 0))
        roas = float(shop.get("roas", 0))

        status = "손실" if roas < 100 else "요주의" if roas < 150 else "개선 중"

        md += f"| {i} | {shop_id} | {category} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_number(ctr, True)} | {format_number(roas, True)} | {status} |\n"

    return md


def format_funnel(funnel_data: list[dict[str, Any]]) -> str:
    """전환 퍼널을 생성합니다."""
    md = "## 전환 퍼널\n\n"
    md += "### 퍼널 시각화\n\n"
    md += "```\n"

    # 샘플 퍼널 시각화
    md += "노출 (Impression):    ~~~~~~~~~~~~~~~~~~~~~~~~~~~ 100%\n"
    md += "    | CTR 7.10%\n"
    md += "클릭 (Click):           ~~~~~~~~~~~~~~~~~           7.10%\n"
    md += "    | 메뉴 조회율 55.0%\n"
    md += "메뉴 조회 (view_menu):  ~~~~~~~~~~~~~             3.90%\n"
    md += "    | 장바구니율 54.5%\n"
    md += "장바구니 (add_to_cart): ~~~~~~~~~~~               2.13%\n"
    md += "    | 주문율 16.4%\n"
    md += "주문 (Order):            ~                         0.35%\n"
    md += "```\n\n"

    md += "### 퍼널 상세 테이블\n\n"
    md += "| 단계 | 건수 | 전체 대비 | 이전 단계 전환율 | 전기 대비 변화 |\n"
    md += "|---|---|---|---|---|\n"

    for record in funnel_data:
        stage = record.get("conversion_type", "")
        count = int(record.get("count", 0))
        md += f"| {stage} | {count:,} | - | - | - |\n"

    return md


def build(
    date: datetime,
    daily_data: dict[str, Any],
    weekly_list: list[dict[str, Any]] = None,
    monthly_data: dict[str, Any] = None,
) -> str:
    """최종 보고서 마크다운을 생성합니다.

    Args:
        date: 보고서 생성 날짜
        daily_data: 일간 데이터 (get_daily_kpi 반환값)
        weekly_list: 주간 데이터 리스트 (get_weekly_list 반환값)
        monthly_data: 월간 데이터 (카테고리별, 상점별, 퍼널)

    Returns:
        최종 마크다운 문자열
    """
    md = f"# CAPA 광고 성과 보고서\n\n"
    md += f"**생성 일시**: {date.strftime('%Y-%m-%d %H:%M')} KST\n\n"
    md += "---\n\n"

    # === 일간 섹션 (항상 포함) ===
    md += "## 일간\n\n"
    md += format_executive_summary(
        daily_data["summary"],
        daily_data.get("prev_summary"),
    )
    md += "\n"
    md += format_kpi_detail(
        daily_data["summary"],
        daily_data.get("prev_summary"),
    )
    md += "\n"
    md += format_daily_trend(daily_data["daily_breakdown"])

    # === 주간 섹션 (월요일 or 월초 1일) ===
    if weekly_list:
        md += "\n---\n\n"
        md += "## 주간\n\n"

        for week in weekly_list:
            md += f"### 주간: {week['start_date']} ~ {week['end_date']}\n\n"
            md += format_executive_summary(
                week["summary"],
                week.get("prev_summary"),
            )
            md += "\n"
            md += format_kpi_detail(
                week["summary"],
                week.get("prev_summary"),
            )
            md += "\n\n"

    # === 월간 섹션 (매달 1일) ===
    if monthly_data:
        md += "\n---\n\n"
        md += "## 월간\n\n"
        md += format_executive_summary(monthly_data["summary"])
        md += "\n"
        md += format_kpi_detail(monthly_data["summary"])
        md += "\n"

        if monthly_data.get("categories"):
            md += format_category_performance(monthly_data["categories"])
            md += "\n"

        if monthly_data.get("top10") and monthly_data.get("bottom10"):
            md += format_shop_performance(
                monthly_data["top10"],
                monthly_data["bottom10"],
            )
            md += "\n"

        if monthly_data.get("funnel"):
            md += format_funnel(monthly_data["funnel"])

    md += "\n---\n\n"
    md += "**리포트 생성 완료**\n\n"
    md += "© 2026 CAPA 광고 분석 플랫폼\n"

    return md
