# [Design] Text-To-SQL Sample Queries & Schema

본 문서는 Text-To-SQL 시스템 구축을 위한 데이터 소스 명세와 학습/검증용 자연어 질의어 예시(Sample Queries)를 정의한다.

---

## 1. 데이터 소스 명세 (Schema)

### 1.1 ad_combined_log (Hourly Log)
광고 노출 및 클릭 이벤트가 시간 단위로 기록되는 원천 로그 테이블이다.

| 섹션 | 컬럼명 | 타입 | 설명 | 카테고리/범위 |
| --- | --- | --- | --- | --- |
| **Impression** | `impression_id` | STRING | 광고 노출 고유 ID | UUID v4 |
| | `user_id` | STRING | 사용자 ID | user_000001 ~ user_100000 |
| | `ad_id` | STRING | 광고 ID | ad_0001 ~ ad_1000 |
| | `campaign_id` | STRING | 캠페인 ID | campaign_01 ~ campaign_05 |
| | `advertiser_id` | STRING | 광고주 ID | advertiser_01 ~ advertiser_30 |
| | `platform` | STRING | 플랫폼 | web, app_ios, app_android, tablet_ios, tablet_android |
| | `device_type` | STRING | 기기 타입 | mobile, tablet, desktop, others |
| | `os` | STRING | 운영체제 | ios, android, macos, windows |
| | `delivery_region` | STRING | 배달 지역 | 강남구, 서초구, 마포구 등 서울 25개 자치구 |
| | `user_lat` | DOUBLE | 사용자 위도 | 37.4 ~ 37.7 (서울 범위) |
| | `user_long` | DOUBLE | 사용자 경도 | 126.8 ~ 127.1 (서울 범위) |
| | `store_id` | STRING | 가게 ID | store_0001 ~ store_5000 |
| | `food_category` | STRING | 음식 카테고리 | chicken, pizza, korean, chinese, dessert 등 15개 |
| | `ad_position` | STRING | 광고 위치 | home_top_rolling, list_top_fixed, search_ai_recommend, checkout_bottom |
| | `ad_format` | STRING | 광고 포맷 | display, native, video, discount_coupon |
| | `user_agent` | STRING | 사용자 에이전트 | 표준 Mobile UA 문자열 |
| | `ip_address` | STRING | IP 주소 | 익명화된 IP (XXX.XXX.XXX.0) |
| | `session_id` | STRING | 세션 ID | UUID v4 |
| | `keyword` | STRING | 검색 키워드 | NULL 또는 검색어 문자열 (선택적 입력) |
| | `cost_per_impression` | DOUBLE | 노출당 비용 | 0.005 ~ 0.10 |
| | `impression_timestamp` | BIGINT | 노출 시각 | UNIX timestamp |
| **Click** | `click_id` | STRING | 클릭 ID (NULL이면 클릭 없음) | UUID v4 |
| | `click_position_x` | INT | 클릭 X 좌표 | 광고 영역 내 |
| | `click_position_y` | INT | 클릭 Y 좌표 | 광고 영역 내 |
| | `landing_page_url` | STRING | 랜딩 페이지 URL | 광고주별 URL |
| | `cost_per_click` | DOUBLE | 클릭당 비용 | 0.1 ~ 5.0 |
| | `click_timestamp` | BIGINT | 클릭 시각 | UNIX timestamp |
| **Flag** | `is_click` | BOOLEAN | 클릭 여부 | true, false |
| **Partition** | `year` | STRING | 년도 | `'2026'` (STRING, 4자리) |
| | `month` | STRING | 월 | `'02'` ~ `'03'` (STRING, 2자리 zero-padded) |
| | `day` | STRING | 일 | `'01'` ~ `'31'` (STRING, 2자리 zero-padded) |
| | `hour` | STRING | 시간 | `'00'` ~ `'23'` (STRING, 2자리 zero-padded) |

> [!NOTE]
> **플랫폼 vs 디바이스 타입 구분**
>
> - **디바이스 타입 (device_type)**: 사용자가 사용하는 **물리적 하드웨어 기기**의 형태를 분류합니다. (예: 스마트폰 휴대 여부, 화면 크기 기준)
> - **플랫폼 (platform)**: 광고가 소비되는 **구체적인 소프트웨어 환경 또는 앱 채널**을 분류하며, OS 정보를 포함하기도 합니다. (예: 동일한 하드웨어라도 웹 브라우저 접속인지 전용 앱 접속인지 구분)

### 1.2 ad_combined_log_summary (Daily Summary)
일 단위로 집계된 성과 지표와 전환(Conversion) 데이터가 포함된 요약 테이블이다.

| 섹션 | 컬럼명 | 타입 | 설명 | 카테고리/범위 |
| --- | --- | --- | --- | --- |
| **Impression** | `impression_id` | STRING | 광고 노출 고유 ID | UUID v4 |
| | `user_id` | STRING | 사용자 ID | user_000001 ~ user_100000 |
| | `ad_id` | STRING | 광고 ID | ad_0001 ~ ad_1000 |
| | `campaign_id` | STRING | 캠페인 ID | campaign_01 ~ campaign_05 |
| | `advertiser_id` | STRING | 광고주 ID | advertiser_01 ~ advertiser_30 |
| | `platform` | STRING | 플랫폼 | web, app_ios, app_android, tablet_ios, tablet_android |
| | `device_type` | STRING | 기기 타입 | mobile, tablet, desktop, others |
| | `os` | STRING | 운영체제 | ios, android, macos, windows |
| | `delivery_region` | STRING | 배달 지역 | 강남구, 서초구, 마포구 등 서울 25개 자치구 |
| | `user_lat` | DOUBLE | 사용자 위도 | 37.4 ~ 37.7 (서울 범위) |
| | `user_long` | DOUBLE | 사용자 경도 | 126.8 ~ 127.1 (서울 범위) |
| | `store_id` | STRING | 가게 ID | store_0001 ~ store_5000 |
| | `food_category` | STRING | 음식 카테고리 | chicken, pizza, korean, chinese, dessert 등 15개 |
| | `ad_position` | STRING | 광고 위치 | home_top_rolling, list_top_fixed, search_ai_recommend, checkout_bottom |
| | `ad_format` | STRING | 광고 포맷 | display, native, video, discount_coupon |
| | `user_agent` | STRING | 사용자 에이전트 | 표준 Mobile UA 문자열 |
| | `ip_address` | STRING | IP 주소 | 익명화된 IP (XXX.XXX.XXX.0) |
| | `session_id` | STRING | 세션 ID | UUID v4 |
| | `keyword` | STRING | 검색 키워드 | NULL 또는 검색어 문자열 (선택적 입력) |
| | `cost_per_impression` | DOUBLE | 노출당 비용 | 0.005 ~ 0.10 |
| | `impression_timestamp` | BIGINT | 노출 시각 | UNIX timestamp |
| **Click** | `click_id` | STRING | 클릭 ID (NULL이면 클릭 없음) | UUID v4 |
| | `click_position_x` | INT | 클릭 X 좌표 | 광고 영역 내 |
| | `click_position_y` | INT | 클릭 Y 좌표 | 광고 영역 내 |
| | `landing_page_url` | STRING | 랜딩 페이지 URL | 광고주별 URL |
| | `cost_per_click` | DOUBLE | 클릭당 비용 | 0.1 ~ 5.0 |
| | `click_timestamp` | BIGINT | 클릭 시각 | UNIX timestamp |
| **Click Flag** | `is_click` | BOOLEAN | 클릭 여부 | true, false |
| **Conversion** | `conversion_id` | STRING | 전환 ID (NULL이면 전환 없음) | UUID v4 |
| | `conversion_type` | STRING | 전환 타입 | purchase, signup, download, view_content, add_to_cart |
| | `conversion_value` | DOUBLE | 전환 가치(매출액) | 1.0 ~ 10000.0 |
| | `product_id` | STRING | 구매 상품 ID | prod_00001 ~ prod_10000 |
| | `quantity` | INT | 구매 수량 | 1 ~ 10 |
| | `attribution_window` | STRING | 귀속 기간 | 1day, 7day, 30day |
| | `conversion_timestamp` | BIGINT | 전환 시각 | UNIX timestamp |
| **Conversion Flag** | `is_conversion` | BOOLEAN | 전환 여부 | true, false |
| **Partition** | `year` | STRING | 년도 | `'2026'` (STRING, 4자리) |
| | `month` | STRING | 월 | `'02'` ~ `'03'` (STRING, 2자리 zero-padded) |
| | `day` | STRING | 일 | `'01'` ~ `'31'` (STRING, 2자리 zero-padded) |

---

## 2. 샘플 질의어 (Sample Queries)

이 샘플들은 사용자가 Slack에서 입력할 것으로 예상되는 자연어 질문들이다.

### 2.1 일간 리포트 (Daily Reports - 25개)

1. "어제 전체 광고 노출수, 클릭수, 전환수, 클릭률(CTR)을 보여줘"
2. "오늘 각 캠페인별로 노출, 클릭, 전환, 전환율(CVR)을 상세 비교해줘"
3. "어제 캠페인별 노출수, 클릭수, 클릭률을 집계해줘. TOP 10은?"
4. "오늘 시간대별로 노출과 클릭의 분포를 보여줘. 피크타임은?"
5. "어제 캠페인별로 노출, 클릭, 전환을 비교하고 순위를 매겨줘"
6. "오늘 데스크톱/모바일/태블릿 기기별 노출, 클릭, 전환을 비교해줘"
7. "어제 서울 지역구별로 노출수, CTR, 전환수를 순위대로 보여줘"
8. "어제 상품 카테고리별로 노출, 클릭, 전환을 보여줘. 탑 10은?"
9. "오늘 평균 CTR 대비 20% 이상 떨어진 캠페인이 있으면 알려줘"
10. "어제 전환이 0인 캠페인을 찾아줘. 해당 캠페인의 노출과 클릭은?"
11. "어제 전일 대비 주요 지표(노출, 클릭, 전환) 변화율을 보여줘"
12. "오늘 전환율이 높은 캠페인 TOP 10을 보여줘"
13. "오늘 클릭은 많은데 전환율이 낮은 캠페인을 찾아줘"
14. "어제 신규로 시작된 캠페인과 그 첫날 성과를 보여줘"
15. "어제 각 캠페인별 노출당 전환율(CVR)을 비교해줘"
16. "오늘 광고주별 전환 수를 집계하고 순위를 보여줘"
17. "어제 기기별로 시간대별 클릭 패턴을 분석해줘. 어느 시간에 모바일 트래픽이 많아?"
18. "오늘 각 카테고리별 전환율(CVR) 상위 5개를 찾아줘"
19. "어제 서울 지역구별 클릭수 증가율이 높은 TOP 5를 보여줘"
20. "오늘 캠페인별 노출 대비 클릭 비율이 높은 TOP 5를 찾아줘"
21. "어제 광고주별 노출수, 클릭수, 전환수를 집계해줘. 매출 기여도 TOP 10은?"
22. "오늘 광고채널별(검색, 디스플레이, SNS) 성과를 비교해줘. 어느 채널이 가장 효율적이야?"
23. "어제 상품 카테고리별 CTR이 높지만 전환이 낮은 카테고리를 찾아줘"
24. "오늘 강남구, 종로구, 중구 등 서울 주요 지역구별 노출 TOP 5를 보여줘"
25. "어제 오후 시간대(14시~18시) vs 저녁시간(19시~23시) 어느 때 클릭이 더 많았어?"

### 2.2 주간 리포트 (Weekly Reports - 19개)

1. "지난 7일간 일일 노출, 클릭, 전환, CTR 추이를 보여줘"
2. "지난주(Mon~Sun) vs 그 전주의 캠페인별 노출, 클릭, 전환 성장률을 비교해줘"
3. "지난 7일간 광고채널별(검색, 디스플레이, SNS) 노출수 기준 상위 10개와 각각의 CTR, CVR을 보여줘"
4. "지난 7일간 기기별(desktop, mobile, tablet)로 매일 노출과 클릭을 보여줘. 어느 기기가 트렌드?"
5. "지난 7일간 광고주별 노출, 클릭, 전환을 정렬해서 보여줘. TOP 15는?"
6. "지난 7일간 상품 카테고리별로 클릭수 증가율이 높은 TOP 10을 보여줘"
7. "지난 7일간 요일별(평일 vs 주말) 노출, 클릭, 전환 성과 차이를 보여줘"
8. "지난 7일간 캠페인별 전환율(CVR) 지표를 보여줘. TOP 10은?"
9. "지난 7일간 광고채널별(검색, 디스플레이, SNS) 각 채널의 CTR, CVR을 분석해줘"
10. "지난 7일간 서울 지역구별 노출 수와 전환수를 상세히 보여줘"
11. "지난 7일간 시간대별 클릭 패턴을 분석해줘. 어느 시간대가 피크?"
12. "지난 7일간 카테고리별 전환율(CVR)이 높은 TOP 5를 찾아줘"
13. "지난 7일간 카테고리별 노출대비 클릭 비율을 비교해줘"
14. "지난 7일간 노출과 전환이 모두 많은 고성과 캠페인 TOP 10을 보여줘"
15. "지난 7일간 강남구, 종로구, 중구 등 서울 주요 지역구별 클릭수 증가율 TOP 5를 보여줘"
16. "지난 7일간 광고주별 전환율(CVR)을 비교해줘. 가장 효율적인 광고주는?"
17. "지난 7일간 기기(desktop/mobile/tablet)별 시간대별 클릭 분포를 분석해줘"
18. "지난 7일간 상품 카테고리별 CTR이 높지만 전환이 낮은 카테고리를 찾아줘"
19. "지난 7일간 월요일~일요일 일일 노출과 전환 추이를 상세히 보여줘"

### 2.3 월간 리포트 (Monthly Reports - 15개)

1. "이번 달 전체 노출수, 클릭수, 전환수, 고유사용자수를 보여줘"
2. "이번 달 캠페인별 전환 수 순위 TOP 20을 보여줘. 각 캠페인의 CTR, CVR도 함께"
3. "이번 달 기기별 성과를 장치유형(desktop/mobile/tablet)으로 상세 비교해줘"
4. "지난달 대비 이번달 노출, 클릭, 전환의 증감률을 보여줘. 어느 지표가 가장 커?"
5. "이번 달 상품 카테고리별 노출수와 전환수를 보여줘. 전환이 가장 많은 카테고리는?"
6. "이번 달 CTR이 높지만 전환율이 낮은 캠페인을 찾아줘"
7. "이번 달 광고채널별(검색, 디스플레이, SNS) 노출수, 클릭수, 전환율을 상세히 보여줘"
8. "이번 달과 지난달 동기간 비교: 기기별 노출 및 클릭 추이"
9. "이번 달 전환율(CVR)이 가장 높은 TOP 10 캠페인과 그 특징을 보여줘"
10. "이번 달 서울 지역구별 노출수, 클릭수, 전환수를 보여줘. 성과가 가장 좋은 지역구는?"
11. "이번 달 광고주별 노출수 대비 전환수 효율 순위를 보여줘. TOP 10은?"
12. "이번 달 상품 카테고리별 CTR 순위와 CVR 순위를 비교해줘. 불균형한 카테고리는?"
13. "이번 달 주중(월~금)과 주말(토~일) 기기별 클릭 패턴 차이를 분석해줘"
14. "이번 달 광고채널별 시간대별(아침/낮/저녁/밤) 성과를 비교해줘"
15. "지난 3개월(저번달, 지난달, 이번달) 월별 노출, 클릭, 전환 추이를 보여줘"
