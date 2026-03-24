# 데이터 생성량 비교: ad_log_generator.py vs main.py

## 개요

광고 로그 생성기의 두 가지 구현체 간 데이터 생성량 차이를 비교 분석합니다.

- **ad_log_generator.py**: 백필(backfill)용 대량 데이터 생성기
- **main.py**: 실시간 스트리밍 데이터 생성기

## AS-IS (현재 상태)

### ad_log_generator.py (백필용)
- **위치**: `services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py`
- **용도**: 과거 데이터 대량 생성, 특정 날짜/시간대 데이터 백필
- **생성 방식**: 시간당 데이터를 한 번에 생성

### main.py (실시간)
- **위치**: `services/data_pipeline_t2/gen_adlog_t2/realtime/main.py`
- **용도**: 실시간 스트리밍, Kinesis로 즉시 전송
- **생성 방식**: 개별 이벤트를 연속적으로 생성

## 데이터 생성량 비교

### 1. Impression 생성량

| 구분 | ad_log_generator.py | main.py |
|------|-------------------|---------|
| **기본 생성 로직** | `base_impressions = 10000`<br>`× traffic_multiplier` | `time.sleep(0.3)`<br>0.3초마다 1개 |
| **5분당 생성량** | 833 ~ 2,500개 (예상)¹ | **1,000개** (고정) |
| **1시간당 생성량** | 1,000 ~ 30,000개² | **12,000개** (고정) |

¹ 시간당 데이터를 5분 단위로 나눈 추정치
² traffic_multiplier 범위: 0.1 ~ 3.0

### 2. Traffic Multiplier 상세 (ad_log_generator.py)

#### 시간대별 가중치
```python
- 00:00~07:00: 0.1 ~ 0.2 (새벽)
- 07:00~09:00: 0.4 ~ 0.6 (아침)
- 09:00~11:00: 0.3 ~ 0.5 (오전)
- 11:00~14:00: 1.5 ~ 2.0 (점심)
- 14:00~17:00: 0.6 ~ 0.8 (오후)
- 17:00~21:00: 2.0 ~ 3.0 (저녁/피크)
- 21:00~24:00: 1.0 ~ 1.5 (밤)
```

#### 요일별 가중치
```python
- 월~목: 0.8 ~ 1.0
- 금요일: 1.2 ~ 1.5
- 토요일: 1.5 ~ 2.0
- 일요일: 1.3 ~ 1.7
```

### 3. Click & Conversion 생성 비율

| 이벤트 | ad_log_generator.py | main.py |
|--------|-------------------|---------|
| **CTR** | 1~5% (ad_format별 차등) | **10%** (고정) |
| **CVR** | 1~10% (conversion_type별 차등) | **20%** (고정) |

#### CTR 상세 비교
- **ad_log_generator.py**:
  - display: 1~3%
  - native: 2~4%
  - video: 3~5%
  - discount_coupon: 2.5~4.5%
  - 강남/서초 지역: ×1.2 가중치

- **main.py**: 
  - 모든 ad_format: 10% 고정

#### CVR 상세 비교
- **ad_log_generator.py**:
  - view_content: 5~10%
  - add_to_cart: 3~7%
  - signup/download: 2~5%
  - purchase: 1~3%

- **main.py**: 
  - 모든 conversion_type: 20% 고정

## TO-BE (개선 방향)

### 문제점
1. **실시간 생성기(main.py)의 낮은 생성량**: 피크 시간대에 비현실적으로 적은 데이터
2. **고정된 CTR/CVR**: 실제 패턴을 반영하지 못함
3. **트래픽 패턴 부재**: 시간대별/요일별 변화 없음

### 개선안

1. **실시간 생성 속도 조정**
   ```python
   # 현재: time.sleep(0.3) → 12,000개/시간
   # 개선: 동적 sleep 시간
   base_sleep = 0.1  # 기본 0.1초 (36,000개/시간)
   sleep_time = base_sleep / traffic_multiplier
   ```

2. **실시간 CTR/CVR 패턴 적용**
   ```python
   # ad_log_generator.py의 CTR_RATES, CVR_RATES 재사용
   from local.ad_log_generator import CTR_RATES, CVR_RATES
   ```

3. **실시간 트래픽 패턴 적용**
   ```python
   # ad_log_generator.py의 _get_traffic_multiplier 재사용
   from local.ad_log_generator import AdLogGenerator
   traffic_mult = generator._get_traffic_multiplier(datetime.now())
   ```

## 실제 예시 계산

### 평일 점심시간 (12:00)
- **ad_log_generator.py**: 10,000 × (1.5~2.0) × (0.8~1.0) = **12,000~20,000개/시간**
- **main.py**: 12,000개/시간 (고정)

### 주말 저녁 피크 (19:00)
- **ad_log_generator.py**: 10,000 × (2.0~3.0) × (1.5~2.0) = **30,000~60,000개/시간**
- **main.py**: 12,000개/시간 (고정)

### 평일 새벽 (03:00)
- **ad_log_generator.py**: 10,000 × (0.1~0.2) × (0.8~1.0) = **800~2,000개/시간**
- **main.py**: 12,000개/시간 (고정)

## 결론

1. **생성량 차이**: 
   - 백필용은 시간대에 따라 **800~60,000개/시간**의 변동폭
   - 실시간은 **12,000개/시간** 고정
   
2. **현실성**:
   - 백필용이 실제 트래픽 패턴을 더 잘 반영
   - 실시간은 일정하지만 비현실적

3. **통합 필요성**:
   - 두 시스템 간 데이터 일관성을 위해 동일한 생성 로직 공유 필요
   - 실시간도 트래픽 패턴을 반영하도록 개선 필요