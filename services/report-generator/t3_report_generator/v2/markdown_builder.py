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
        return f"{int(value):,}" if isinstance(value, float) and value == int(value) else f"{value:.2f}" if isinstance(value, float) else f"{value}"
    except (ValueError, TypeError):
        return str(value)


def format_currency(value: Any) -> str:
    """금액을 포맷팅합니다."""
    try:
        if isinstance(value, str):
            value = float(value)
        return f"{value:,.2f}원" if value else "0.00원"
    except (ValueError, TypeError):
        return str(value)


def calculate_change_rate(current: float, previous: float, is_percentage: bool = False) -> str:
    """변화율을 계산합니다."""
    try:
        curr = float(current)
        prev = float(previous)
        if prev == 0:
            return "N/A"
        change_rate = ((curr - prev) / prev) * 100
        if is_percentage:
            return f"{change_rate:+.2f}%p"
        return f"{change_rate:+.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def _safe_float(value: Any, default: float = 0.0) -> float:
    """빈 문자열, None 등을 안전하게 float으로 변환합니다."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """빈 문자열, None 등을 안전하게 int로 변환합니다."""
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def format_executive_summary(data: dict[str, Any], prev_data: dict[str, Any] = None, curr_label: str = "", prev_label: str = "", comparison_label: str = "전기 대비") -> str:
    """Executive Summary (경영진 요약)를 생성합니다."""
    md = "## Executive Summary (경영진 요약)\n\n"

    # 핵심 KPI 카드
    md += "### 핵심 KPI 카드\n\n"
    curr_header = f"실적 ({curr_label})" if curr_label else "실적"
    prev_header = f"{comparison_label} ({prev_label})" if prev_label else comparison_label
    md += f"| KPI | {curr_header} | {prev_header} |\n"
    md += "|---|---|---|\n"

    # 필요한 필드 추출
    revenue = _safe_float(data.get("revenue", 0))
    cost = _safe_float(data.get("cost", 0))
    roas = _safe_float(data.get("roas", 0))
    ctr = _safe_float(data.get("ctr", 0))
    conversions = _safe_int(data.get("conversions", 0))

    prev_revenue = _safe_float(prev_data.get("revenue", 0)) if prev_data else 0
    prev_cost = _safe_float(prev_data.get("cost", 0)) if prev_data else 0
    prev_roas = _safe_float(prev_data.get("roas", 0)) if prev_data else 0
    prev_ctr = _safe_float(prev_data.get("ctr", 0)) if prev_data else 0
    prev_conversions = _safe_int(prev_data.get("conversions", 0)) if prev_data else 0

    md += f"| 광고 기여 매출 | {format_currency(revenue)} | {calculate_change_rate(revenue, prev_revenue)} |\n"
    md += f"| 총 ROAS | {format_number(roas, True)} | {calculate_change_rate(roas, prev_roas, is_percentage=True)} |\n"
    md += f"| 총 CTR | {format_number(ctr, True)} | {calculate_change_rate(ctr, prev_ctr, is_percentage=True)} |\n"
    md += f"| 총 전환 | {conversions:,}건 | {calculate_change_rate(conversions, prev_conversions)} |\n"

    # 보조 KPI
    curr_label_str = f" ({curr_label})" if curr_label else ""
    prev_label_str = f" (vs {prev_label})" if prev_label else ""
    md += f"\n### 보조 KPI{curr_label_str}\n\n"
    md += f"| 노출{prev_label_str} | 클릭{prev_label_str} | 광고비 (광고 수수료){prev_label_str} | 순이익{prev_label_str} |\n"
    md += "|---|---|---|---|\n"

    impressions = _safe_int(data.get("impressions", 0))
    clicks = _safe_int(data.get("clicks", 0))
    net_profit = revenue - cost

    prev_impressions = _safe_int(prev_data.get("impressions", 0)) if prev_data else 0
    prev_clicks = _safe_int(prev_data.get("clicks", 0)) if prev_data else 0
    prev_net_profit = prev_revenue - prev_cost if prev_data else 0

    md += f"| {impressions:,}회 ({calculate_change_rate(impressions, prev_impressions)}) | "
    md += f"{clicks:,}회 ({calculate_change_rate(clicks, prev_clicks)}) | "
    md += f"{format_currency(cost)} ({calculate_change_rate(cost, prev_cost)}) | "
    md += f"**{format_currency(net_profit)}** ({calculate_change_rate(net_profit, prev_net_profit)}) |\n"

    return md


def format_kpi_detail(data: dict[str, Any], prev_data: dict[str, Any] = None, curr_label: str = "", prev_label: str = "") -> str:
    """KPI 상세를 생성합니다."""
    curr_header = f"이번 기간 ({curr_label})" if curr_label else "이번 기간"
    prev_header = f"전기 ({prev_label})" if prev_label else "전기"

    sections = [
        ("매출", [
            ("광고 기여 매출", "revenue", "currency"),
            ("광고비 (광고 수수료)", "cost", "currency"),
            ("**순이익**", None, "net_profit"),
            ("ROAS", "roas", True),
        ]),
        ("볼륨", [
            ("노출", "impressions", False),
            ("클릭", "clicks", False),
            ("전환", "conversions", False),
        ]),
        ("효율", [
            ("CTR", "ctr", True),
            ("CVR", "cvr", True),
            ("CPC", "cpc", "currency"),
        ]),
    ]

    md = "## KPI 상세\n\n"

    for section_name, metrics in sections:
        md += f"**{section_name}**\n\n"
        md += f"| 지표 | {curr_header} | {prev_header} | 변화 | 변화율 |\n"
        md += "|---|---|---|---|---|\n"

        for label, key, format_type in metrics:
            if key is None:  # net_profit 계산
                curr_val = _safe_float(data.get("revenue", 0)) - _safe_float(data.get("cost", 0))
                prev_val = _safe_float(prev_data.get("revenue", 0)) - _safe_float(prev_data.get("cost", 0)) if prev_data and len(prev_data) > 0 else 0
            else:
                curr_val = data.get(key, 0)
                prev_val = _safe_float(prev_data.get(key, 0)) if prev_data and len(prev_data) > 0 else 0

            if format_type == "currency":
                curr_str = format_currency(curr_val)
                prev_str = format_currency(prev_val) if prev_data and len(prev_data) > 0 else "N/A"
                diff = _safe_float(curr_val) - _safe_float(prev_val)
                change_str = (f"+{format_currency(diff)}" if diff >= 0 else format_currency(diff)) if prev_data and len(prev_data) > 0 and prev_val else "-"
            elif format_type == True:  # percentage
                curr_str = format_number(curr_val, True)
                prev_str = format_number(prev_val, True) if prev_data and len(prev_data) > 0 else "N/A"
                change_str = "-"
            elif format_type == "net_profit":
                curr_str = format_currency(curr_val)
                prev_str = format_currency(prev_val) if prev_data and len(prev_data) > 0 else "N/A"
                diff = _safe_float(curr_val) - _safe_float(prev_val)
                change_str = (f"+{format_currency(diff)}" if diff >= 0 else format_currency(diff)) if prev_data and len(prev_data) > 0 and prev_val else "-"
            else:  # number
                curr_str = format_number(curr_val, False)
                prev_str = format_number(prev_val, False) if prev_data and len(prev_data) > 0 else "N/A"
                diff = _safe_float(curr_val) - _safe_float(prev_val)
                change_str = (f"+{format_number(diff, False)}" if diff >= 0 else format_number(diff, False)) if prev_data and len(prev_data) > 0 and prev_val else "-"

            change_rate = calculate_change_rate(_safe_float(curr_val), _safe_float(prev_val)) if prev_data and len(prev_data) > 0 and prev_val else "-"

            if key in ("roas", "ctr", "cvr"):
                diff = _safe_float(curr_val) - _safe_float(prev_val)
                pct_change = (f"+{diff:.2f}%p" if diff >= 0 else f"{diff:.2f}%p") if prev_data and len(prev_data) > 0 and prev_val else "-"
                md += f"| {label} | {curr_str} | {prev_str} | {pct_change} | {change_rate} |\n"
            elif key == "cpc":
                md += f"| {label} | {curr_str} | {prev_str} | {change_str} | {change_rate} |\n"
            else:
                md += f"| {label} | {curr_str} | {prev_str} | {change_str} | {change_rate} |\n"

        md += "\n"

    return md


def format_daily_trend(daily_data: list[dict[str, Any]]) -> str:
    """일별 트렌드를 생성합니다."""
    md = "## 일별 추이\n\n"
    md += "### 일별 상세 테이블\n\n"
    md += "| 날짜 | 요일 | 노출 | 클릭 | 전환 | 광고 기여 매출 | 광고비 (광고 수수료) | CTR | ROAS |\n"
    md += "|---|---|---|---|---|---|---|---|---|\n"

    day_map = ["월", "화", "수", "목", "금", "토", "일"]

    for record in daily_data:
        date_str = record.get("date", "")
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = day_map[date_obj.weekday()]
        except:
            day_name = "?"

        impressions = _safe_int(record.get("impressions", 0))
        clicks = _safe_int(record.get("clicks", 0))
        conversions = _safe_int(record.get("conversions", 0))
        revenue = _safe_float(record.get("revenue", 0))
        cost = _safe_float(record.get("cost", 0))
        ctr = _safe_float(record.get("ctr", 0))
        roas = _safe_float(record.get("roas", 0))

        md += f"| {date_str} | {day_name} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_currency(cost)} | {format_number(ctr, True)} | {format_number(roas, True)} |\n"

    return md


def format_category_performance(categories: list[dict[str, Any]]) -> str:
    """카테고리별 성과를 생성합니다."""
    md = "## 카테고리별 성과\n\n"
    md += "| 순위 | 카테고리 | 노출 | 클릭 | 전환 | 광고 기여 매출(원) | 광고비(원) | CTR | CVR | ROAS | 매출 변화 |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|---|\n"

    for i, cat in enumerate(categories, 1):
        category = cat.get("category", "")
        impressions = _safe_int(cat.get("impressions", 0))
        clicks = _safe_int(cat.get("clicks", 0))
        conversions = _safe_int(cat.get("conversions", 0))
        revenue = _safe_float(cat.get("revenue", 0))
        cost = _safe_float(cat.get("cost", 0))
        ctr = _safe_float(cat.get("ctr", 0))
        cvr = _safe_float(cat.get("cvr", 0))
        roas = _safe_float(cat.get("roas", 0))
        prev_revenue = _safe_float(cat.get("prev_revenue"))

        # 매출 변화 계산
        if prev_revenue is None or prev_revenue == 0:
            revenue_change = "N/A"
        else:
            change_pct = ((revenue - prev_revenue) / prev_revenue) * 100
            sign = "+" if change_pct >= 0 else ""
            revenue_change = f"{sign}{change_pct:.1f}%"

        md += f"| {i} | {category} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_currency(cost)} | {format_number(ctr, True)} | "
        md += f"{format_number(cvr, True)} | {format_number(roas, True)} | {revenue_change} |\n"

    return md


def format_shop_performance(top10: list[dict[str, Any]], bottom10: list[dict[str, Any]]) -> str:
    """상점별 성과를 생성합니다."""
    md = "## 상점별 성과\n\n"

    md += "### Top 5 상점 (매출 기준)\n\n"
    md += "| 순위 | 상점 ID | 카테고리 | 노출 | 클릭 | 전환 | 광고 기여 매출(원) | CTR | ROAS | 매출 변화 |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|\n"

    for i, shop in enumerate(top10, 1):
        shop_id = shop.get("shop_id", "")
        category = shop.get("category", "")
        impressions = _safe_int(shop.get("impressions", 0))
        clicks = _safe_int(shop.get("clicks", 0))
        conversions = _safe_int(shop.get("conversions", 0))
        revenue = _safe_float(shop.get("revenue", 0))
        ctr = _safe_float(shop.get("ctr", 0))
        roas = _safe_float(shop.get("roas", 0))
        prev_revenue = _safe_float(shop.get("prev_revenue"))

        # 매출 변화 계산
        if prev_revenue is None or prev_revenue == 0:
            revenue_change = "N/A"
        else:
            change_pct = ((revenue - prev_revenue) / prev_revenue) * 100
            sign = "+" if change_pct >= 0 else ""
            revenue_change = f"{sign}{change_pct:.1f}%"

        md += f"| {i} | {shop_id} | {category} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_number(ctr, True)} | {format_number(roas, True)} | {revenue_change} |\n"

    md += "\n### Bottom 5 상점 (ROAS 기준, 최소 노출 100건)\n\n"
    md += "| 순위 | 상점 ID | 카테고리 | 노출 | 클릭 | 전환 | 광고 기여 매출(원) | CTR | ROAS |\n"
    md += "|---|---|---|---|---|---|---|---|---|\n"

    for i, shop in enumerate(bottom10, 1):
        shop_id = shop.get("shop_id", "")
        category = shop.get("category", "")
        impressions = _safe_int(shop.get("impressions", 0))
        clicks = _safe_int(shop.get("clicks", 0))
        conversions = _safe_int(shop.get("conversions", 0))
        revenue = _safe_float(shop.get("revenue", 0))
        ctr = _safe_float(shop.get("ctr", 0))
        roas = _safe_float(shop.get("roas", 0))

        md += f"| {i} | {shop_id} | {category} | {impressions:,} | {clicks:,} | {conversions:,} | "
        md += f"{format_currency(revenue)} | {format_number(ctr, True)} | {format_number(roas, True)} |\n"

    return md


def format_funnel(funnel_data: list[dict[str, Any]]) -> str:
    """전환 퍼널을 생성합니다."""
    md = "## 전환 퍼널\n\n"
    md += "### 퍼널 상세 테이블\n\n"
    md += "| 단계 | 건수 | 전체 대비 | 이전 단계 전환율 | 전기 대비 변화 |\n"
    md += "|---|---|---|---|---|\n"

    if not funnel_data:
        md += "| - | - | - | - | N/A |\n"
        return md

    # 데이터 정리 (conversion_type별로 정렬)
    stage_order = ["view_content", "add_to_cart", "purchase"]
    stage_labels = {
        "view_content": "메뉴 조회",
        "add_to_cart": "장바구니",
        "purchase": "구매"
    }

    # 현재 데이터 맵
    current_map = {}
    prev_map = {}
    for record in funnel_data:
        stage = record.get("conversion_type", "")
        count = _safe_int(record.get("count", 0))
        prev_count = record.get("prev_count")
        current_map[stage] = count
        prev_map[stage] = _safe_int(prev_count) if prev_count else None

    # 각 단계별 테이블 생성
    prev_count_for_rate = None
    for i, stage in enumerate(stage_order):
        if stage not in current_map:
            continue

        count = current_map[stage]
        prev_count = prev_map.get(stage)
        label = stage_labels.get(stage, stage)

        # 전체 대비 %: 첫 단계(view_content)의 건수를 100%로 기준
        total_count = current_map.get("view_content", 1)
        total_pct = (count / total_count * 100) if total_count > 0 else 0

        # 이전 단계 전환율
        if prev_count_for_rate and prev_count_for_rate > 0:
            conversion_rate = (count / prev_count_for_rate * 100)
            conversion_rate_str = f"{conversion_rate:.1f}%"
        else:
            conversion_rate_str = "-"

        # 전기 대비 변화
        if prev_count is not None and prev_count > 0:
            change_pct = ((count - prev_count) / prev_count * 100)
            sign = "+" if change_pct >= 0 else ""
            change_str = f"{sign}{change_pct:.1f}%"
        else:
            change_str = "N/A"

        md += f"| {label} | {count:,} | {total_pct:.2f}% | {conversion_rate_str} | {change_str} |\n"

        # 다음 단계를 위해 현재 단계 건수 저장
        prev_count_for_rate = count

    return md


def build(
    date: datetime,
    daily_data: dict[str, Any],
    start_date_str: str = "",
    end_date_str: str = "",
    weekly_list: list[dict[str, Any]] = None,
    monthly_data: dict[str, Any] = None,
) -> str:
    """최종 보고서 마크다운을 생성합니다.

    Args:
        date: 보고서 생성 날짜
        daily_data: 일간 데이터 (get_daily_kpi 반환값)
        start_date_str: 데이터 집계 시작일
        end_date_str: 데이터 집계 종료일
        weekly_list: 주간 데이터 리스트 (get_weekly_list 반환값)
        monthly_data: 월간 데이터 (카테고리별, 상점별, 퍼널)

    Returns:
        최종 마크다운 문자열
    """
    md = f"# CAPA 광고 성과 보고서\n\n"
    actual_run_time = datetime.now()
    md += f"**생성 일시**: {actual_run_time.strftime('%Y-%m-%d %H:%M')} KST\n\n"
    md += "---\n\n"

    # === 일간 및 누적 섹션 ===
    md += "## 일간 (당월 누적 실적)\n\n"
    # 전기 날짜 계산
    prev_label = ""
    if start_date_str and end_date_str:
        md += f"> **[집계 기준]** {start_date_str} ~ {end_date_str} (당월 누적 실적)\n"
        md += "> *전기 대비 수치는 지난달 같은 기간과의 비교입니다.*\n\n"
        try:
            from datetime import timedelta
            _start = datetime.strptime(start_date_str, "%Y-%m-%d")
            _prev_end = _start - timedelta(days=1)
            _prev_start = _prev_end.replace(day=1)
            _prev_end_day = _prev_start.replace(day=int(end_date_str.split("-")[2]))
            prev_label = f"{_prev_start.strftime('%m/%d')}~{_prev_end_day.strftime('%m/%d')}"
        except:
            prev_label = "전기"
    md += format_executive_summary(
        daily_data["summary"],
        daily_data.get("prev_summary"),
        curr_label=f"{start_date_str[5:].replace('-', '/')}~{end_date_str[5:].replace('-', '/')}" if start_date_str else "",
        prev_label=prev_label,
    )
    md += "\n"
    md += format_kpi_detail(
        daily_data["summary"],
        daily_data.get("prev_summary"),
        curr_label=f"{start_date_str[5:].replace('-', '/')}~{end_date_str[5:].replace('-', '/')}" if start_date_str else "",
        prev_label=prev_label,
    )
    md += "\n"
    md += format_daily_trend(daily_data["daily_breakdown"])

    # === 주간 섹션 (월요일 or 월초 1일) ===
    if weekly_list:
        md += "\n---\n\n"
        md += "## 주간\n\n"

        for i, week in enumerate(weekly_list):
            md += f"### 주간: {week['start_date']} ~ {week['end_date']}\n\n"
            w_start = week['start_date'][5:].replace('-', '/')
            w_end = week['end_date'][5:].replace('-', '/')

            # 전주 라벨 계산
            prev_label = ""
            if week.get("prev_summary"):
                # prev_week_start/prev_week_end가 있으면 그걸 사용
                if week.get("prev_week_start") and week.get("prev_week_end"):
                    p_start = week['prev_week_start'][5:].replace('-', '/')
                    p_end = week['prev_week_end'][5:].replace('-', '/')
                    prev_label = f"{p_start}~{p_end}"
                elif i > 0:
                    # 아니면 이전 주차 데이터 사용
                    prev_week = weekly_list[i - 1]
                    p_start = prev_week['start_date'][5:].replace('-', '/')
                    p_end = prev_week['end_date'][5:].replace('-', '/')
                    prev_label = f"{p_start}~{p_end}"
                else:
                    prev_label = "N/A"
            else:
                prev_label = "N/A"

            md += format_executive_summary(
                week["summary"],
                week.get("prev_summary"),
                curr_label=f"{w_start}~{w_end}",
                prev_label=prev_label,
                comparison_label="전주 대비",
            )
            md += "\n"
            md += format_kpi_detail(
                week["summary"],
                week.get("prev_summary"),
                curr_label=f"{w_start}~{w_end}",
                prev_label=prev_label,
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
