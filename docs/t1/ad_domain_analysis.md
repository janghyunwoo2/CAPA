# 광고 도메인 지식 및 로그 데이터 스키마 (배달앱 시나리오)

## 1. 개요
본 문서는 "배달앱 서비스"를 가정하여, 광고 시스템에서 발생하는 핵심 로그(노출, 클릭, 전환)의 흐름과 각 로그에 포함되어야 할 필수 데이터를 정의합니다. 이를 통해 로그 생성기가 만들어낼 데이터의 구조를 파악하고 도메인 지식을 함양하는 것을 목표로 합니다.

## 2. 사용자 시나리오 (User Journey)
1.  **진입 (Entry)**: 사용자가 배달앱을 켭니다.
2.  **노출 (Impression)**: 앱 메인 화면 상단 배너 혹은 검색 결과 리스트 최상단에 "치킨 가게 A"의 광고가 **보여집니다**.
3.  **클릭 (Click)**: 사용자가 해당 광고 배너를 **터치(클릭)**하여 가게 상세 페이지로 이동합니다.
4.  **전환 (Conversion)**:
    *   상세 메뉴를 둘러봅니다 (View Menu).
    *   메뉴를 장바구니에 담습니다 (Add to Cart).
    *   **최종적으로 주문을 완료합니다 (Order Complete).**

---

## 3. 로그 데이터 정의

각 단계별로 생성되어야 할 데이터 필드와 그 이유(Why)를 정의합니다.

### 3.1. 광고 노출 로그 (Ad Impression Log)
사용자에게 광고가 성공적으로 렌더링되었을 때 발생하는 이벤트입니다.

| 필드명 (Field Name) | 데이터 타입 | 설명 (Description) & Why |
| :--- | :--- | :--- |
| `event_id` | UUID | 개별 로그의 고유 식별자. 중복 제거 및 추적용. |
| `timestamp` | DateTime | 이벤트 발생 시각 (UTC 기준 권장). |
| `user_id` | UUID/String | 어떤 사용자가 광고를 봤는지 식별. (개인화, 타겟팅 분석용) |
| `ad_id` | UUID | **어떤 광고 소재**가 노출되었는지 식별. |
| `campaign_id` | UUID | 광고가 속한 마케팅 캠페인 ID. (예: "여름 치킨 할인 이벤트") |
| `shop_id` | UUID | 광고주(가게) ID. 정산 및 성과 리포트용. |
| `placement` | String | 광고가 노출된 위치. (예: `main_banner`, `search_top`, `list_middle`) |
| `platform` | String | Android, iOS, Web 등 접속 환경. |
| `bid_price` | Float | (내부용) 해당 노출 입찰가. 광고 효율 분석용. |

### 3.2. 광고 클릭 로그 (Ad Click Log)
사용자가 광고를 클릭했을 때 발생하는 이벤트입니다. **가장 중요한 것은 어떤 노출(Impression)에서 이 클릭이 발생했는지 연결하는 것입니다.**

| 필드명 (Field Name) | 데이터 타입 | 설명 (Description) & Why |
| :--- | :--- | :--- |
| `event_id` | UUID | 클릭 이벤트 고유 ID. |
| `timestamp` | DateTime | 클릭 발생 시각. |
| `user_id` | UUID/String | 클릭한 사용자 ID. |
| `ad_id` | UUID | 클릭된 광고 ID. |
| `impression_id` | UUID | **Key Field.** 클릭이 발생한 원본 **노출 로그의 `event_id`**. (CTR 계산 및 Fraud 방지) |
| `shop_id` | UUID | 광고주 ID. (CPC 과금 기준) |
| `clickspot_x` | Integer | (Optional) 배너 내 터치 X 좌표. (히트맵 분석용) |
| `clickspot_y` | Integer | (Optional) 배너 내 터치 Y 좌표. |

### 3.3. 광고 전환 로그 (Ad Conversion Log)
광고 클릭 이후 발생한 유의미한 행동(장바구니, 주문 등)입니다. **기여(Attribution)** 분석의 핵심입니다.

| 필드명 (Field Name) | 데이터 타입 | 설명 (Description) & Why |
| :--- | :--- | :--- |
| `event_id` | UUID | 전환 이벤트 고유 ID. |
| `timestamp` | DateTime | 전환 발생 시각. |
| `user_id` | UUID/String | 사용자 ID. |
| `shop_id` | UUID | 가게 ID. |
| `click_id` | UUID | **Key Field.** 이 전환을 유발한 **클릭 로그의 `event_id`**. (기여도 측정) |
| `ad_id` | UUID | (Optional) 편의상 포함하지만, `click_id`를 통해 조인 가능. |
| `action_type` | String | 행동 유형 (`view_menu`, `add_to_cart`, `order`) |
| `total_amount` | Float | (`order`일 경우) 주문 총액. ROAS(광고비 대비 매출액) 계산용. |
| `item_count` | Integer | 주문/장바구니 아이템 개수. |

---

## 5. 핵심 용어 및 지표 (Terminology & Metrics)

사용자가 요청한 주요 도메인 용어에 대한 정의입니다.

### 5.1. 엔티티 (Entities)
*   **광고 지면 (Ad Slot / Placement)**: 광고가 노출되는 공간 (메인 배너, 검색 결과 상단 등). 로그의 `placement` 필드.
*   **광고주 (Advertiser)**: 광고를 집행하는 주체 (치킨 가게 사장님). 로그의 `shop_id` 필드.
*   **캠페인 (Campaign)**: 광고주가 설정한 마케팅 단위 (예: "여름방학 할인 이벤트"). 로그의 `campaign_id` 필드.
*   **크리에이티브 (Creative)**: 사용자에게 실제로 보여지는 광고 소재 (이미지, 문구). 로그의 `ad_id`가 이를 식별합니다.

### 5.2. 성과 지표 (Key Metrics)
*   **노출 (Impression)**: 광고가 사용자에게 1회 보여지는 것.
*   **클릭 (Click)**: 사용자가 광고를 누르는 것.
*   **전환 (Conversion)**: 클릭 후 구매, 장바구니 담기 등 목표 행동을 달성하는 것.
*   **CPC (Cost Per Click)**: **클릭 당 과금**. (예: 클릭 1회당 500원 광고비 차감). 배달앱 검색 광고의 주된 과금 방식.
*   **CTR (Click-Through Rate, 클릭률)**: 노출 대비 클릭 비율. (`Clicks / Impressions * 100`). 광고 소재의 매력도를 판단하는 핵심 지표.
*   **CVR (Conversion Rate, 전환율)**: 클릭 대비 전환 비율. (`Conversions / Clicks * 100`). 상세 페이지나 상품의 경쟁력을 판단.
*   **RPM (Revenue Per Mille)**: 1,000회 노출 당 예상 매출. (`Total Revenue / Impressions * 1000`). 플랫폼 입장에서 지면의 가치를 평가하는 지표.

---

## 6. 데이터 흐름 요약 (Example)

1.  **Impression (사용자 노출 로그)**:
    *   `event_id`: **IMP_001**
    *   `user_id`: U_100
    *   `ad_id` (Creative): AD_50
    *   `shop_id` (Advertiser): SHOP_A
2.  **Click (사용자 클릭 로그)**:
    *   `event_id`: **CLK_999**
    *   `impression_id`: **IMP_001** (위의 노출과 연결됨)
    *   `user_id`: U_100
3.  **Conversion (사용자 전환 로그)**:
    *   `event_id`: CNV_888
    *   `click_id`: **CLK_999** (위의 클릭과 연결됨)
    *   `action_type`: "order"
    *   `total_amount`: 25,000 (매출 발생 -> ROAS 분석 가능)

## 7. 학습 포인트
*   **Funnel (깔때기) 구조**: 노출 > 클릭 > 전환으로 이어지는 사용자의 수와 비율을 이해해야 합니다.
*   **Join Key**: 분산된 로그 환경(로그 파일이 다름)에서 `impression_id`와 `click_id`를 통해 어떻게 하나의 여정으로 묶을지 고민해야 합니다.
*   **Conversion Window**: 클릭 후 몇 시간/며칠 이내의 구매까지 광고 성과로 인정할 것인가? (보통 배달앱은 당일 혹은 1~2시간 이내)
