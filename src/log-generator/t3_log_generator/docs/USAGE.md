# 최소+확장 구조 사용 가이드

## 🎯 개요

**기본은 가볍게, 필요하면 확장**하는 구조입니다.

- **기본 모드**: Impression 8개, Click 7개, Conversion 7개 필드
- **확장 모드**: 설정 변경만으로 필드 추가 가능

---

## 🚀 빠른 시작

### 1. 기본 모드 (최소 필드)

```bash
python main.py
```

**생성되는 로그:**
```json
// Impression (8개 필드)
{
  "event_type": "impression",
  "event_id": "...",
  "timestamp": "...",
  "user_id": "...",
  "ad_id": "...",
  "shop_id": "...",
  "category": "치킨",
  "bid_price": 1200.0
}

// Click (7개 필드)
{
  "event_type": "click",
  "event_id": "...",
  "timestamp": "...",
  "impression_id": "...",
  "user_id": "...",
  "shop_id": "...",
  "cpc_cost": 980.0
}

// Conversion (7개 필드)
{
  "event_type": "conversion",
  "event_id": "...",
  "timestamp": "...",
  "click_id": "...",
  "user_id": "...",
  "shop_id": "...",
  "action_type": "order",
  "total_amount": 28000
}
```

---

## ⚙️ 확장 기능 사용법

`main.py` 파일 상단의 `Config` 클래스를 수정하세요.

### Config 클래스 위치

```python
class Config:
    # === 마스터 데이터 크기 ===
    USERS_COUNT = 200
    SHOPS_COUNT = 30
    
    # === 확장 필드 활성화 ===
    ENABLE_SESSION = False       # ← 여기를 True로 변경
    ENABLE_DEVICE_INFO = False
    ENABLE_GEO_INFO = False
    ENABLE_ADVANCED = False
```

---

### 확장 옵션 설명

| 옵션 | 추가되는 필드 | 용도 |
|------|--------------|------|
| `ENABLE_SESSION` | `session_id` | 세션 추적, 유저 행동 분석 |
| `ENABLE_DEVICE_INFO` | `platform`, `device_type` | 디바이스별 성과 분석 |
| `ENABLE_GEO_INFO` | `geo_region`, `geo_city` | 지역별 성과 분석 |
| `ENABLE_ADVANCED` | `campaign_id`, `win_price`, `is_viewable` 등 | 고급 분석 |

---

### 예시 1: 세션 추적 활성화

```python
class Config:
    ENABLE_SESSION = True  # ← True로 변경
```

**결과:**
```json
{
  "event_type": "impression",
  "event_id": "...",
  "session_id": "session-abc-123",  // ← 추가됨!
  "user_id": "...",
  ...
}
```

---

### 예시 2: 모든 확장 기능 활성화

```python
class Config:
    ENABLE_SESSION = True
    ENABLE_DEVICE_INFO = True
    ENABLE_GEO_INFO = True
    ENABLE_ADVANCED = True
```

**결과:** Impression 20개 필드 (최대)

---

## 📊 필드 수 비교

| 모드 | Impression | Click | Conversion | 총합 |
|------|-----------|-------|-----------|------|
| **기본** | 8개 | 7개 | 7개 | 22개 |
| + SESSION | 9개 | 8개 | 8개 | 25개 |
| + DEVICE_INFO | 11개 | 7개 | 7개 | 25개 |
| + GEO_INFO | 10개 | 7개 | 7개 | 24개 |
| **모두 활성화** | 20개 | 12개 | 13개 | 45개 |

---

## 🎨 카테고리별 특성

### 자동으로 반영되는 것들

| 카테고리 | 입찰가 범위 | 기본 CTR |
|---------|------------|---------|
| 치킨 | 800~2,000원 | 8% |
| 피자 | 700~1,800원 | 7% |
| 한식 | 500~1,500원 | 6% |
| 중식 | 600~1,600원 | 6% |
| 카페 | 200~800원 | 5% |
| 분식 | 300~1,000원 | 9% |

**CTR은 ±20% 랜덤 변동**이 있어서 실행할 때마다 조금씩 달라집니다.

---

## 🔧 마스터 데이터 크기 조절

```python
class Config:
    USERS_COUNT = 200   # 유저 수 (기본 200명)
    SHOPS_COUNT = 30    # 가게 수 (기본 30개)
```

- **많이 하면**: 더 다양한 패턴, 메모리 사용 증가
- **적게 하면**: 반복 패턴 증가, 메모리 절약

---

## 💡 추천 사용 시나리오

### 시나리오 1: 파이프라인 테스트
```python
# 가볍게 시작
ENABLE_SESSION = False
ENABLE_DEVICE_INFO = False
ENABLE_GEO_INFO = False
ENABLE_ADVANCED = False
```
→ 최소 필드로 Kinesis → S3 연결 확인

### 시나리오 2: CTR/CVR 분석
```python
# 세션만 추가
ENABLE_SESSION = True
```
→ 세션별 전환율 분석 가능

### 시나리오 3: 디바이스별 성과 분석
```python
# 디바이스 정보 추가
ENABLE_DEVICE_INFO = True
```
→ Android vs iOS 비교

### 시나리오 4: 지역별 분석
```python
# 지역 정보 추가
ENABLE_GEO_INFO = True
```
→ 서울 vs 경기 vs 부산 비교

### 시나리오 5: 최종 발표용
```python
# 모든 기능 활성화
ENABLE_SESSION = True
ENABLE_DEVICE_INFO = True
ENABLE_GEO_INFO = True
ENABLE_ADVANCED = True
```
→ 현업 수준 데이터

---

## 📝 주요 특징

### ✅ 유지되는 것 (기본 모드에서도)
- Impression → Click → Conversion 퍼널
- 카테고리별 CTR 차등 (치킨 8%, 카페 5%)
- action_type별 CVR 차등 (order 5%, view_menu 40%)
- 마스터 데이터 (유저 200명, 가게 30개 재사용)
- ID 연결 (impression_id, click_id로 퍼널 추적)

### ❌ 제거된 것 (기본 모드)
- 시간대별 트래픽 패턴 (균일하게 생성)
- 복잡한 광고주/캠페인 구조
- 디바이스/지역 정보
- 세션 추적

### ⚡ 언제든 추가 가능
- Config 설정만 바꾸면 됨
- 코드 수정 불필요

---

## 🚀 실행 방법

### 로컬 (pip)
```bash
pip install faker
python main.py
```

### 로컬 (uv)
```bash
uv run main.py
```

### Docker
```bash
docker build -t ad-log-gen .
docker run ad-log-gen
```

### 파일로 저장
```bash
python main.py > logs.json
```

### Kinesis로 전송 (실시간 스트리밍)

**1. 환경 변수 설정 (`.env` 파일)**

```bash
# Kinesis 설정
ENABLE_KINESIS=true
KINESIS_STREAM_NAME=capa-ad-logs-dev
AWS_REGION=ap-northeast-2

# AWS 자격증명
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

**2. 실행**

```bash
uv run main.py
```

**출력:**
```
============================================================
🚀 Ad Log Generator 시작
============================================================
✅ 로그 생성기 초기화 완료 (유저: 200, 가게: 30)
✅ Kinesis 전송 활성화: capa-ad-logs-dev (ap-northeast-2)
============================================================
📊 로그 생성 시작...

{"event_type": "impression", ...}
```

**3. Kinesis 비활성화 (로컬 테스트)**

```bash
# .env 파일에서
ENABLE_KINESIS=false
```

→ stdout으로만 출력 (Kinesis 전송 안 함)

---

## 📈 다음 단계

1. **지금**: 기본 모드로 실행해서 로그 확인
2. **필요하면**: Config 설정 변경해서 필드 추가
3. **나중에**: 부하 테스트 기능 추가 (config.py, load_test.py)

---

## 🔍 코드 구조

```python
# 1. 설정
class Config:
    # 확장 기능 on/off

# 2. 마스터 데이터
class MasterData:
    # 유저/가게 미리 생성

# 3. 로그 생성기
class AdLogGenerator:
    def generate_impression():
        # 기본 필드 생성
        # + Config에 따라 확장 필드 추가
    
    def generate_click():
        # ...
    
    def generate_conversion():
        # ...
```

---

## ❓ FAQ

**Q: 기본 모드와 확장 모드 중 뭘 써야 하나요?**  
A: 처음엔 기본 모드로 시작하세요. 필요할 때 하나씩 켜면 됩니다.

**Q: 설정을 바꾸면 재실행해야 하나요?**  
A: 네, `Ctrl+C`로 멈추고 다시 `python main.py` 실행하세요.

**Q: 마스터 데이터는 매번 똑같나요?**  
A: 네, `random.seed(42)`로 고정되어 있어서 항상 같은 유저/가게가 생성됩니다.

**Q: 시간대별 트래픽 패턴은 없나요?**  
A: 기본 모드에는 없습니다. 나중에 추가할 예정입니다.
