"""
Ad Log Generator - 메인 실행 스크립트
로그 생성 + Kinesis Streams 3개 전송
"""

import time
import json
import random
import os
from datetime import datetime
from dotenv import load_dotenv

from generator import AdLogGenerator
from kinesis_stream_sender import KinesisStreamSender

# .env 파일 로드 (상위 디렉토리의 .env 파일 사용)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)


# =============================================================================
# 설정
# =============================================================================

class Config:
    """환경 변수 기반 설정"""
    
    # Kinesis Stream 설정 (이벤트 타입별 3개 분리)
    KINESIS_IMPRESSION = os.getenv("KINESIS_IMPRESSION", "capa-knss-imp-00")
    KINESIS_CLICK = os.getenv("KINESIS_CLICK", "capa-knss-clk-00")
    KINESIS_CONVERSION = os.getenv("KINESIS_CONVERSION", "capa-knss-cvs-00")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
    
    # AWS 자격증명
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # 로그 생성 설정 (ad_log_generator.py와 동일하게 적용)
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
    
    # 기본 sleep 시간 (초)
    BASE_SLEEP = 0.1  # 기본 0.1초 (시간당 36,000개)


# =============================================================================
# 트래픽 패턴 (ad_log_generator.py와 동일)
# =============================================================================

def get_traffic_multiplier(timestamp: datetime) -> float:
    """시간대별, 요일별 트래픽 멀티플라이어를 반환합니다."""
    hour = timestamp.hour
    weekday = timestamp.weekday()  # 0=월요일, 6=일요일
    
    # 시간대별 패턴
    if 0 <= hour < 1:
        hour_mult = random.uniform(0.2, 1.0)  # 새벽 완충지대
    elif 1 <= hour < 6:
        hour_mult = random.uniform(0.1, 0.2)  # 새벽    
    elif 6 <= hour < 7:
        hour_mult = random.uniform(0.15, 0.45)  # 아침 완충지대  
    elif 7 <= hour < 9:
        hour_mult = random.uniform(0.4, 0.6)  # 아침
    elif 9 <= hour < 11:
        hour_mult = random.uniform(0.3, 0.5)  # 오전
    elif 11 <= hour < 12:
        hour_mult = random.uniform(0.4, 1.0)  # 오전 완충지대
    elif 12 <= hour < 13:
        hour_mult = random.uniform(1.5, 2.0)  # 점심
    elif 13 <= hour < 14:
        hour_mult = random.uniform(0.75, 1.6)  # 점심 완충지대
    elif 14 <= hour < 17:
        hour_mult = random.uniform(0.6, 0.8)  # 오후
    elif 17 <= hour < 18:
        hour_mult = random.uniform(0.75, 2.1)  # 오후 완충지대
    elif 18 <= hour < 21:
        hour_mult = random.uniform(2.0, 3.0)  # 저녁/피크
    elif 21 <= hour < 22:
        hour_mult = random.uniform(1.3, 2.2)  # 저녁 완충지대
    elif 22 <= hour < 23:
        hour_mult = random.uniform(1.0, 1.5)  # 밤 
    else:
        hour_mult = random.uniform(0.5, 1.0)  # 밤 완충지대
        
    # 요일별 패턴
    if weekday < 4:  # 월-목
        day_mult = random.uniform(0.8, 1.0)
    elif weekday == 4:  # 금
        day_mult = random.uniform(1.2, 1.5)
    elif weekday == 5:  # 토
        day_mult = random.uniform(1.5, 2.0)
    else:  # 일
        day_mult = random.uniform(1.3, 1.7)
        
    return hour_mult * day_mult


# =============================================================================
# 메인 실행
# =============================================================================

def main():
    """메인 실행 함수"""
    
    print("=" * 60, flush=True)
    print("🚀 Ad Log Generator 시작", flush=True)
    print("=" * 60, flush=True)
    
    # 로그 생성기 초기화
    generator = AdLogGenerator()
    print("✅ 로그 생성기 초기화 완료", flush=True)
    
    # Kinesis Stream Sender 초기화 (이벤트 타입별 3개 Stream)
    sender = KinesisStreamSender(
        stream_names={
            "impression": Config.KINESIS_IMPRESSION,
            "click": Config.KINESIS_CLICK,
            "conversion": Config.KINESIS_CONVERSION,
        },
        region=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )
    print(f"✅ Kinesis 전송 활성화 ({Config.AWS_REGION})", flush=True)
    
    print("=" * 60, flush=True)
    target = "Kinesis Streams (imp/clk/cvs)"
    print(f"Starting Ad Log Generator (Target: {target})...", flush=True)
    print("=" * 60, flush=True)
    
    # 메인 루프 (개선된 트래픽 패턴 적용)
    loop_count = 0
    start_time = time.time()
    impression_count = 0
    
    try:
        while True:
            # 현재 시간 기준 트래픽 멀티플라이어 계산
            current_time = datetime.now()
            traffic_mult = get_traffic_multiplier(current_time)
            
            # 1. 노출 발생
            impr = generator.generate_impression()
            
            # Kinesis 전송
            sender.send(impr)
            
            # 내부 데이터 저장 (클릭/전환에서 사용)
            internal_data = impr.get('_internal', {})
            ad_format = internal_data.get('ad_format', 'display')
            delivery_region = internal_data.get('delivery_region', '')
            
            # 2. 클릭 확률 (개선된 CTR 적용)
            if generator.should_click(ad_format, delivery_region):
                time.sleep(random.uniform(0.5, 2.0))  # 클릭 딜레이
                
                click = generator.generate_click(impr)
                
                sender.send(click)
                
                # 3. 전환 확률 (개선된 CVR 적용)
                if generator.should_convert():
                    time.sleep(random.uniform(1.0, 5.0))  # 전환 딜레이
                    
                    conv = generator.generate_conversion(click)
                    
                    sender.send(conv)
            
            # 동적 대기 시간 (트래픽 패턴에 따라 조정)
            sleep_time = Config.BASE_SLEEP / traffic_mult
            time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60, flush=True)
        print("🛑 로그 생성 중지됨", flush=True)
        
        stats = sender.get_stats()
        stats_by_type = sender.get_stats_by_type()
        print(f"\n📊 Kinesis 전송 통계:", flush=True)
        print(f"  - 전체: 성공 {stats['success']} / 실패 {stats['error']} / 합계 {stats['total']}", flush=True)
        for etype, s in stats_by_type.items():
            print(f"  - {etype}: 성공 {s['success']} / 실패 {s['error']}", flush=True)
        
        print("=" * 60, flush=True)


if __name__ == "__main__":
    main()