# 가중치 분포 로그 생성기 적용

**작성일**: 2026-03-26 14:42  
**작업 범위**: `services/data_pipeline_t2/gen_adlog_t2/realtime/`

---

## 요청 배경

기존 `generator.py`는 모든 컬럼 값을 `random.choice()`로 균등 선택하여  
분석 시 지표가 지나치게 고르게 분산되는 문제가 있었습니다.  
실제 서비스에서는 특정 지역·플랫폼·카테고리에 편중이 발생하므로  
각 컬럼에 가중치를 부여하여 현실적인 데이터 분포를 만들고자 했습니다.

---

## AS-IS vs TO-BE

### AS-IS (기존 `generator.py`)

| 컬럼 | 선택 방식 | 결과 |
|------|-----------|------|
| PLATFORMS | `random.choice(PLATFORMS)` | 5개 항목이 각 20% 균등 분포 |
| DEVICE_TYPES | `random.choice(DEVICE_TYPES)` | 4개 항목이 각 25% 균등 분포 |
| REGIONS | `random.choice(REGIONS)` | 25개 구가 각 4% 균등 분포 |
| FOOD_CATEGORIES | `random.choice(FOOD_CATEGORIES)` | 14개 카테고리 균등 분포 |
| AD_POSITIONS | `random.choice(AD_POSITIONS)` | 4개 위치 각 25% 균등 |
| AD_FORMATS | `random.choice(AD_FORMATS)` | 4개 포맷 각 25% 균등 |
| CONVERSION_TYPES | `random.choice(CONVERSION_TYPES)` | 5개 타입 각 20% 균등 |
| CAMPAIGNS | `random.choice(CAMPAIGNS)` | 5개 캠페인 각 20% 균등 |

→ 분석 대시보드에서 모든 항목이 비슷한 수치로 나타나 **인사이트 도출 불가**

---

### TO-BE (신규 `generator_weighted.py`)

#### 핵심 변경 사항

1. `random.choice()` → `random.choices(population, weights=..., k=1)[0]`  
2. 각 컬럼별 기준 가중치(base weight) 정의  
3. `random.uniform(±15%)` 노이즈 적용 → 매 이벤트마다 미세하게 다른 분포, 패턴 고정 방지  
4. `_normalize()` 함수로 합계가 항상 100%가 되도록 정규화  

---

## 컬럼별 가중치 설계

### PLATFORMS (합계 100%)

| 값 | 기준 가중치 | 설계 근거 |
|----|-------------|-----------|
| app_android | **35%** | 국내 Android 점유율 우세 |
| app_ios | **30%** | iOS 고가치 유저 |
| web | 15% | 데스크탑/비앱 접근 |
| tablet_ios | 12% | 태블릿 소수 |
| tablet_android | 8% | 태블릿 소수 |

### DEVICE_TYPES (합계 100%)

| 값 | 기준 가중치 | 설계 근거 |
|----|-------------|-----------|
| mobile | **70%** | 배달앱 = 모바일 중심 |
| tablet | 15% | |
| desktop | 12% | |
| others | 3% | |

### OS_TYPES (합계 100%)

| 값 | 기준 가중치 | 설계 근거 |
|----|-------------|-----------|
| android | **48%** | 국내 Android 점유율 |
| ios | 38% | |
| macos | 8% | |
| windows | 6% | |

### REGIONS (합계 100%)

| 구 | 기준 가중치 | 설계 근거 |
|----|-------------|-----------|
| 강남구 | **12%** | 배달앱 소비 최다 지역 |
| 서초구 | 10% | |
| 송파구 | 9% | |
| 마포구 | 7% | 젊은층 밀집 |
| 영등포구 | 6% | |
| 나머지 20개 구 | 합계 ~56% | 분산 |

> CTR 보정도 함께 적용:  
> - 강남·서초·송파 → CTR ×1.2  
> - 마포·영등포 → CTR ×1.1

### FOOD_CATEGORIES (합계 100%)

| 카테고리 | 기준 가중치 | 설계 근거 |
|----------|-------------|-----------|
| korean | **20%** | 한식 1위 |
| chicken | 18% | 배달 주문 2위 |
| pizza | 12% | |
| burger | 10% | |
| chinese | 8% | |
| cafe/dessert | 7% | |
| 나머지 8개 | 합계 ~25% | |

### AD_POSITIONS (합계 100%)

| 위치 | 기준 가중치 | 설계 근거 |
|------|-------------|-----------|
| home_top_rolling | **45%** | 홈 진입 시 노출 최다 |
| list_top_fixed | 30% | 검색 결과 상단 |
| search_ai_recommend | 15% | AI 추천 |
| checkout_bottom | 10% | 결제 직전, 전환 의도 높음 |

### AD_FORMATS (합계 100%)

| 포맷 | 기준 가중치 |
|------|-------------|
| display | **40%** |
| native | 30% |
| video | 20% |
| discount_coupon | 10% |

### CONVERSION_TYPES (합계 100%)

| 타입 | 기준 가중치 | 설계 근거 |
|------|-------------|-----------|
| view_content | **35%** | 페이지 조회가 가장 많음 |
| add_to_cart | 28% | |
| purchase | 20% | |
| signup | 10% | |
| download | 7% | |

### CAMPAIGNS (합계 100%)

| 캠페인 | 기준 가중치 | 설계 근거 |
|--------|-------------|-----------|
| campaign_01 | **35%** | 주력 캠페인 |
| campaign_02 | 28% | |
| campaign_03 | 18% | |
| campaign_04 | 12% | |
| campaign_05 | 7% | 보조 캠페인 |

---

## 노이즈 설계

```python
def _jitter(base: float, noise: float = 0.15) -> float:
    """기준값에 ±15% 범위의 uniform 노이즈 적용"""
    return base * random.uniform(1.0 - noise, 1.0 + noise)
```

- 매 이벤트마다 가중치 자체가 ±15% 변동 → 누적 분포는 기준 비율에 수렴
- 고정 편향을 방지하고 자연스러운 변동성 확보

---

## 신규 파일

| 파일 | 역할 |
|------|------|
| `generator_weighted.py` | 가중치 기반 로그 생성 클래스 `AdLogGeneratorWeighted` |
| `main_weighted.py` | `AdLogGeneratorWeighted` 사용, 기존 main.py와 동일한 실행 구조 |

---

## 실행 방법

```bash
# 기존 버전
python main.py

# 가중치 버전
python main_weighted.py
```

---

## 기대 효과

- 분석 대시보드에서 **강남3구 집중**, **모바일 앱 우세**, **한식·치킨 상위** 등 현실적인 인사이트 확인 가능
- campaign_01/02로 예산·성과 집중 현상 가시화
- checkout_bottom 포지션의 높은 전환율 vs 낮은 노출량 대비 분석 가능
- 전체 데이터 생성 개수는 기존과 동일하게 유지
