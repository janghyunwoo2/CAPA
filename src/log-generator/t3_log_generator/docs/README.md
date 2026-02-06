# 광고 로그 생성기 (t3_log_generator) - 최소+확장 구조

## 🎯 핵심 컨셉

**"기본은 가볍게, 필요하면 확장"**

- **기본 모드**: Impression 8개, Click 7개, Conversion 7개 필드
- **확장 모드**: Config 설정만 바꾸면 최대 20개 필드로 확장

---

## 📊 전체 구조

```
Config (설정)
  ↓
MasterData (마스터 데이터 생성)
  ↓
AdLogGenerator (로그 생성기)
  ↓
Impression → Click → Conversion 퍼널
```

---

## 1️⃣ Config (설정)

```python
class Config:
    # 마스터 데이터 크기
    USERS_COUNT = 200
    SHOPS_COUNT = 30
    
    # 확장 필드 on/off
    ENABLE_SESSION = False       # 세션 추적
    ENABLE_DEVICE_INFO = False   # 디바이스 정보
    ENABLE_GEO_INFO = False      # 지역 정보
    ENABLE_ADVANCED = False      # 고급 필드
```

**이 설정만 바꾸면 필드가 추가됩니다!**

---

## 2️⃣ 마스터 데이터

### 기본 모드

| 데이터 | 개수 | 포함 정보 |
|--------|------|-----------|
| 유저 | 200명 | user_id만 |
| 가게 | 30개 | shop_id, shop_name, category |

### 확장 모드 (ENABLE_GEO_INFO = True)

| 데이터 | 개수 | 포함 정보 |
|--------|------|-----------|
| 유저 | 200명 | user_id, region, city |
| 가게 | 30개 | shop_id, shop_name, category |

---

## 3️⃣ Impression (노출) 로그

### 기본 필드 (8개)

```json
{
  "event_type": "impression",
  "event_id": "...",
  "timestamp": "2026-02-10T17:30:00.000000",
  "user_id": "...",
  "ad_id": "...",
  "shop_id": "...",
  "category": "치킨",
  "bid_price": 1200.5
}
```

### 확장 필드 (설정에 따라 추가)

| 설정 | 추가되는 필드 |
|------|--------------|
| `ENABLE_SESSION = True` | `session_id` |
| `ENABLE_DEVICE_INFO = True` | `platform`, `device_type` |
| `ENABLE_GEO_INFO = True` | `geo_region`, `geo_city` |
| `ENABLE_ADVANCED = True` | `campaign_id`, `win_price`, `is_viewable` |

---

## 4️⃣ Click (클릭) 로그

### 기본 필드 (7개)

```json
{
  "event_type": "click",
  "event_id": "...",
  "timestamp": "2026-02-10T17:30:03.500000",
  "impression_id": "...",
  "user_id": "...",
  "shop_id": "...",
  "cpc_cost": 980.0
}
```

### 확장 필드

| 설정 | 추가되는 필드 |
|------|--------------|
| `ENABLE_SESSION = True` | `session_id` |
| `ENABLE_ADVANCED = True` | `clickspot_x`, `clickspot_y`, `click_delay_ms` |

---

## 5️⃣ Conversion (전환) 로그

### 기본 필드 (7개)

```json
{
  "event_type": "conversion",
  "event_id": "...",
  "timestamp": "2026-02-10T17:30:13.200000",
  "click_id": "...",
  "user_id": "...",
  "shop_id": "...",
  "action_type": "order",
  "total_amount": 28000
}
```

### 확장 필드

| 설정 | 추가되는 필드 |
|------|--------------|
| `ENABLE_SESSION = True` | `session_id` |
| `ENABLE_ADVANCED = True` | `item_count`, `conversion_delay_ms` |

---

## 6️⃣ CTR/CVR (확률)

### CTR (Click Through Rate)

**카테고리별 차등** (기본 모드에서도 유지!)

| 카테고리 | 기본 CTR | 입찰가 범위 |
|---------|---------|------------|
| 치킨 | 8% | 800~2,000원 |
| 피자 | 7% | 700~1,800원 |
| 한식 | 6% | 500~1,500원 |
| 중식 | 6% | 600~1,600원 |
| 카페 | 5% | 200~800원 |
| 분식 | 9% | 300~1,000원 |

**±20% 랜덤 변동**으로 실행할 때마다 조금씩 달라집니다.

### CVR (Conversion Rate)

**action_type별 차등**

```python
view_menu: 40%      # 메뉴 보기 (쉬움)
add_to_cart: 15%    # 장바구니 (중간)
order: 5%           # 주문 (어려움)
```

---

## 7️⃣ 실행 흐름

```python
while True:  # 무한 반복
    # 1. Impression 생성 (100%)
    impression = generate_impression()
    print(JSON)
    
    # 2. CTR 확률로 Click 생성
    ctr = _get_ctr(category)  # 치킨 8%, 카페 5% 등
    if random.random() < ctr:
        click = generate_click(impression)
        print(JSON)
        
        # 3. CVR 확률로 Conversion 생성
        cvr = _get_cvr(action_type)
        if random.random() < cvr:
            conversion = generate_conversion(click)
            print(JSON)
    
    # 4. 대기
    time.sleep(0.1~0.5초)
```

---

## 8️⃣ 실행 방법

### 로컬 (uv)
```bash
cd t3_log_generator
uv run main.py
```

### 로컬 (pip)
```bash
cd t3_log_generator
pip install faker
python main.py
```

### Docker
```bash
cd t3_log_generator
docker build -t ad-log-gen .
docker run ad-log-gen
```

### 파일로 저장
```bash
python main.py > logs.json
```

---

## 9️⃣ 확장 방법

### 1단계: Config 수정

`main.py` 파일 상단의 `Config` 클래스를 수정:

```python
class Config:
    ENABLE_SESSION = True  # ← False를 True로 변경
```

### 2단계: 재실행

```bash
python main.py
```

그러면 `session_id` 필드가 추가된 로그가 생성됩니다!

---

## 🔟 필드 수 비교

| 모드 | Impression | Click | Conversion | 총합 |
|------|-----------|-------|-----------|------|
| **기본** | 8개 | 7개 | 7개 | 22개 |
| + SESSION | 9개 | 8개 | 8개 | 25개 |
| + DEVICE_INFO | 10개 | 7개 | 7개 | 24개 |
| + GEO_INFO | 10개 | 7개 | 7개 | 24개 |
| **모두 활성화** | 15개 | 10개 | 10개 | 35개 |

---

## 📊 데이터 파이프라인 연결

### 방법 1: stdout → 파일
```bash
python main.py > logs.json
```

### 방법 2: Kinesis 실시간 스트리밍 ⭐

```
Log Generator
    ↓ (boto3)
Kinesis Data Stream (capa-ad-logs-dev)
    ↓
Kinesis Data Firehose
    ↓ (Parquet 변환)
Amazon S3
    ↓
AWS Athena / Glue
    ↓
분석 / 시각화
```

**설정 방법:**

1. `.env` 파일 생성:
```bash
ENABLE_KINESIS=true
KINESIS_STREAM_NAME=capa-ad-logs-dev
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
```

2. 실행:
```bash
uv run main.py
```

3. AWS 콘솔에서 확인:
   - Kinesis → `capa-ad-logs-dev` → 모니터링 탭
   - "수신 데이터 합계" 그래프 확인

> **ℹ️ 자세한 AWS 인프라 설정(Firehose, Glue, S3)은 [INFRASTRUCTURE.md](INFRASTRUCTURE.md) 문서를 참고하세요.**

---

## 💡 핵심 특징

### ✅ 기본 모드에서도 유지되는 것
- Impression → Click → Conversion 퍼널
- 카테고리별 CTR 차등 (치킨 8%, 카페 5%)
- action_type별 CVR 차등 (order 5%, view_menu 40%)
- 마스터 데이터 (유저 200명, 가게 30개 재사용)
- ID 연결 (impression_id, click_id로 퍼널 추적)

### ⚡ 확장 가능한 것
- 세션 추적 (`ENABLE_SESSION`)
- 디바이스 정보 (`ENABLE_DEVICE_INFO`)
- 지역 정보 (`ENABLE_GEO_INFO`)
- 고급 필드 (`ENABLE_ADVANCED`)

---

## 🎯 사용 시나리오

### 시나리오 1: 파이프라인 테스트
```python
# 모든 확장 기능 OFF (기본 모드)
```
→ 가볍게 Kinesis → S3 연결 확인

### 시나리오 2: CTR/CVR 분석
```python
ENABLE_SESSION = True
```
→ 세션별 전환율 분석

### 시나리오 3: 디바이스별 분석
```python
ENABLE_DEVICE_INFO = True
```
→ Android vs iOS 비교

### 시나리오 4: 최종 발표
```python
# 모든 확장 기능 ON
ENABLE_SESSION = True
ENABLE_DEVICE_INFO = True
ENABLE_GEO_INFO = True
ENABLE_ADVANCED = True
```
→ 현업 수준 데이터

---

## 📈 분석 활용 예시

이 데이터로 할 수 있는 분석:

1. **CTR 분석**: 카테고리별 클릭률 비교
2. **CVR 분석**: action_type별 전환율
3. **ROAS 계산**: 광고비 대비 매출
4. **퍼널 분석**: Impression → Click → Conversion 전환율
5. **세션 분석** (확장 시): 유저별 광고 노출 빈도

---

## 🚀 다음 단계

1. **지금**: 기본 모드로 실행해서 로그 확인
2. **필요하면**: Config 설정 변경해서 필드 추가
3. **나중에**: 부하 테스트 기능 추가 (별도 작업)
