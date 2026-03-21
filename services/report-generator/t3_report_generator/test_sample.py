"""테스트 샘플 데이터로 보고서 생성을 테스트합니다.

실제 Athena 쿼리 없이 샘플 데이터로 마크다운 렌더링을 테스트할 수 있습니다.
"""

from datetime import datetime
import markdown_builder


def get_sample_daily_data():
    """샘플 일간 데이터를 반환합니다."""
    return {
        "summary": {
            "impressions": "2468567",
            "clicks": "175308",
            "conversions": "8641",
            "cost": "8912000",
            "revenue": "3621840000",
            "ctr": "7.10",
            "cvr": "4.93",
            "cpc": "50.8",
            "roas": "342.1",
        },
        "prev_summary": {
            "impressions": "2200000",
            "clicks": "179042",
            "conversions": "8176",
            "cost": "8400000",
            "revenue": "3360832000",
            "ctr": "6.80",
            "cvr": "5.03",
            "cpc": "46.9",
            "roas": "326.9",
        },
        "daily_breakdown": [
            {
                "date": "2026-03-01",
                "impressions": "2841219",
                "clicks": "198891",
                "conversions": "9944",
                "revenue": "518864000",
                "cost": "10240000",
                "ctr": "7.0",
                "roas": "344.0",
            },
            {
                "date": "2026-03-02",
                "impressions": "2750000",
                "clicks": "192500",
                "conversions": "9625",
                "revenue": "498000000",
                "cost": "9800000",
                "ctr": "7.0",
                "roas": "347.0",
            },
            {
                "date": "2026-03-03",
                "impressions": "2962500",
                "clicks": "207375",
                "conversions": "10368",
                "revenue": "540600000",
                "cost": "9920000",
                "ctr": "7.0",
                "roas": "355.0",
            },
        ],
    }


def get_sample_weekly_list():
    """샘플 주간 데이터를 반환합니다."""
    return [
        {
            "start_date": "2026-03-01",
            "end_date": "2026-03-01",
            "summary": {
                "impressions": "2841219",
                "clicks": "198891",
                "conversions": "9944",
                "cost": "10240000",
                "revenue": "518864000",
                "ctr": "7.10",
                "cvr": "5.00",
                "cpc": "51.5",
                "roas": "342.1",
            },
            "prev_summary": {
                "impressions": "2760000",
                "clicks": "193200",
                "conversions": "9688",
                "cost": "10080000",
                "revenue": "504624000",
                "ctr": "6.85",
                "cvr": "5.01",
                "cpc": "52.1",
                "roas": "335.8",
            },
            "daily_breakdown": [
                {
                    "date": "2026-03-01",
                    "impressions": "2841219",
                    "clicks": "198891",
                    "conversions": "9944",
                    "revenue": "518864000",
                    "cost": "10240000",
                    "ctr": "7.0",
                    "roas": "344.0",
                }
            ],
        },
        {
            "start_date": "2026-03-02",
            "end_date": "2026-03-08",
            "summary": {
                "impressions": "16907317",
                "clicks": "1203573",
                "conversions": "59024",
                "cost": "61056000",
                "revenue": "3102976000",
                "ctr": "7.11",
                "cvr": "4.90",
                "cpc": "50.7",
                "roas": "341.8",
            },
            "prev_summary": {
                "impressions": "15840000",
                "clicks": "1239136",
                "conversions": "57344",
                "cost": "59840000",
                "revenue": "2923648000",
                "ctr": "6.78",
                "cvr": "4.62",
                "cpc": "48.3",
                "roas": "329.4",
            },
            "daily_breakdown": [
                {
                    "date": "2026-03-02",
                    "impressions": "2750000",
                    "clicks": "192500",
                    "conversions": "9625",
                    "revenue": "498000000",
                    "cost": "9800000",
                    "ctr": "7.0",
                    "roas": "347.0",
                },
                {
                    "date": "2026-03-03",
                    "impressions": "2962500",
                    "clicks": "207375",
                    "conversions": "10368",
                    "revenue": "540600000",
                    "cost": "9920000",
                    "ctr": "7.0",
                    "roas": "355.0",
                },
            ],
        },
    ]


def get_sample_monthly_data():
    """샘플 월간 데이터를 반환합니다."""
    return {
        "summary": {
            "impressions": "143900000",
            "clicks": "10220000",
            "conversions": "503456",
            "cost": "5212800000",
            "revenue": "26432000000",
            "ctr": "7.10",
            "cvr": "4.93",
            "cpc": "50.8",
            "roas": "342.1",
        },
        "categories": [
            {
                "category": "치킨",
                "impressions": "40600000",
                "clicks": "3248000",
                "conversions": "162400",
                "revenue": "7456000000",
                "cost": "1728000",
                "ctr": "8.0",
                "cvr": "5.0",
                "roas": "375.0",
            },
            {
                "category": "분식",
                "impressions": "36250000",
                "clicks": "3262500",
                "conversions": "130500",
                "revenue": "5520000000",
                "cost": "1380000",
                "ctr": "9.0",
                "cvr": "4.0",
                "roas": "400.0",
            },
            {
                "category": "피자",
                "impressions": "29000000",
                "clicks": "2030000",
                "conversions": "101500",
                "revenue": "4640000000",
                "cost": "1160000",
                "ctr": "7.0",
                "cvr": "5.0",
                "roas": "400.0",
            },
        ],
        "top10": [
            {
                "shop_id": "shop_0042",
                "category": "치킨",
                "impressions": "220800",
                "clicks": "17664",
                "conversions": "883",
                "revenue": "3557000",
                "ctr": "8.0",
                "roas": "380.0",
            },
            {
                "shop_id": "shop_0128",
                "category": "분식",
                "impressions": "214800",
                "clicks": "19332",
                "conversions": "773",
                "revenue": "3335000",
                "ctr": "9.0",
                "roas": "410.0",
            },
        ],
        "bottom10": [
            {
                "shop_id": "shop_0891",
                "category": "카페",
                "impressions": "36250",
                "clicks": "1087",
                "conversions": "29",
                "revenue": "116000",
                "ctr": "3.0",
                "roas": "45.0",
            },
            {
                "shop_id": "shop_0732",
                "category": "중식",
                "impressions": "26100",
                "clicks": "783",
                "conversions": "14",
                "revenue": "72500",
                "ctr": "3.0",
                "roas": "62.0",
            },
        ],
        "funnel": [
            {"conversion_type": "impression", "count": "143900000"},
            {"conversion_type": "click", "count": "10220000"},
            {"conversion_type": "view_menu", "count": "5621000"},
            {"conversion_type": "add_to_cart", "count": "3063943"},
            {"conversion_type": "order", "count": "503456"},
        ],
    }


def test_daily_only():
    """일간만 테스트합니다."""
    date = datetime(2026, 3, 3)
    daily_data = get_sample_daily_data()

    markdown = markdown_builder.build(date=date, daily_data=daily_data)

    # 파일로 저장
    with open("test_output_daily.md", "w", encoding="utf-8") as f:
        f.write(markdown)


def test_daily_and_weekly():
    """일간 + 주간 테스트합니다."""
    date = datetime(2026, 3, 9)
    daily_data = get_sample_daily_data()
    weekly_list = get_sample_weekly_list()

    markdown = markdown_builder.build(
        date=date,
        daily_data=daily_data,
        weekly_list=weekly_list,
    )

    # 파일로 저장
    with open("test_output_weekly.md", "w", encoding="utf-8") as f:
        f.write(markdown)


def test_all_sections():
    """일간 + 주간 + 월간 테스트합니다."""
    date = datetime(2026, 4, 1)
    daily_data = get_sample_daily_data()
    weekly_list = get_sample_weekly_list()
    monthly_data = get_sample_monthly_data()

    markdown = markdown_builder.build(
        date=date,
        daily_data=daily_data,
        weekly_list=weekly_list,
        monthly_data=monthly_data,
    )

    # 파일로 저장
    with open("test_output_monthly.md", "w", encoding="utf-8") as f:
        f.write(markdown)


if __name__ == "__main__":
    test_daily_only()
    test_daily_and_weekly()
    test_all_sections()
