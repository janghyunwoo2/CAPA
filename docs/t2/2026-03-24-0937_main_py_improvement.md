# main.py 일관성 개선 계획

## 개요

광고 로그 실시간 생성기(main.py)를 백필 생성기(ad_log_generator.py)와 일관성 있게 개선합니다. ad_log_generator.py의 패턴을 직접 구현하여 독립적으로 구동하도록 합니다.

## AS-IS (현재 상태)

### main.py 현재 문제점
1. **고정된 생성량**: 0.3초마다 1개 → 시간당 12,000개 고정
2. **고정된 CTR/CVR**: 
   - CTR: 10% 고정 (비현실적으로 높음)
   - CVR: 20% 고정 (비현실적으로 높음)
3. **트래픽 패턴 부재**: 시간대별/요일별 변화 없음

### ad_log_generator.py의 장점
1. **동적 생성량**: 시간대/요일별 트래픽 패턴 적용 (800~60,000개/시간)
2. **현실적인 CTR/CVR**:
   - CTR: 1~5% (ad_format별 차등)
   - CVR: 1~10% (conversion_type별 차등)
3. **지역별 가중치**: 강남/서초 지역 × 1.2

## TO-BE (개선 방향)


### 1. 트래픽 멀티플라이어 구현
```python
def _get_traffic_multiplier(timestamp: datetime) -> float:
    """시간대별, 요일별 트래픽 멀티플라이어 계산"""
    # 시간대별 패턴
    # 새벽(0-7): 0.1~0.2
    # 아침(7-9): 0.4~0.6
    # 오전(9-11): 0.3~0.5
    # 점심(11-14): 1.5~2.0
    # 오후(14-17): 0.6~0.8
    # 저녁(17-21): 2.0~3.0 (피크)
    # 밤(21-24): 1.0~1.5
    
    # 요일별 패턴
    # 월-목: 0.8~1.0
    # 금: 1.2~1.5
    # 토: 1.5~2.0
    # 일: 1.3~1.7
```

### 2. 동적 sleep 시간 적용
```python
# 기본 sleep: 0.1초 (시간당 36,000개)
base_sleep = 0.1
traffic_mult = _get_traffic_multiplier(datetime.now())
sleep_time = base_sleep / traffic_mult

# 예시:
# 새벽 3시 평일: 0.1 / (0.15 * 0.9) = 0.74초 → 시간당 4,860개
# 저녁 7시 토요일: 0.1 / (2.5 * 1.75) = 0.023초 → 시간당 156,500개
```

### 3. CTR/CVR 패턴 적용
```python
CTR_RATES = {
    "display": (0.01, 0.03),
    "native": (0.02, 0.04),
    "video": (0.03, 0.05),
    "discount_coupon": (0.025, 0.045)
}

CVR_RATES = {
    "view_content": (0.05, 0.10),
    "add_to_cart": (0.03, 0.07),
    "signup": (0.02, 0.05),
    "download": (0.02, 0.05),
    "purchase": (0.01, 0.03)
}
```

### 4. 지역별 가중치
```python
# 강남/서초 지역은 CTR 1.2배
if region in ["강남구", "서초구"]:
    ctr = ctr * 1.2
```

## 구현 상세

### 변경 파일
- `services/data_pipeline_t2/gen_adlog_t2/realtime/main.py`
- `services/data_pipeline_t2/gen_adlog_t2/realtime/generator.py` (필요시)

### 주요 변경사항
1. Config 클래스에 CTR_RATES, CVR_RATES 딕셔너리 추가
2. _get_traffic_multiplier() 함수 추가
3. main() 함수의 sleep 로직 수정
4. generator.should_click()과 should_convert() 메서드 개선

### 예상 결과
- **생성량**: 시간대에 따라 800~60,000개/시간 (현재: 12,000개 고정)
- **CTR**: 1~5% (현재: 10% 고정)
- **CVR**: 1~10% (현재: 20% 고정)
- **현실성**: 실제 광고 트래픽 패턴에 근접

## 테스트 계획
1. 트래픽 멀티플라이어 계산 검증
2. 시간대별 생성량 측정
3. CTR/CVR 비율 확인
4. 24시간 실행 후 전체 통계 비교