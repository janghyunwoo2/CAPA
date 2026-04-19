"""
Ad Log Generator - 메인 실행 스크립트
로그 생성 + Kinesis Streams 3개 전송
"""

import time
import json
import random
import os
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
    
    # 로그 생성 설정
    CTR_RATE = 0.10  # 10% CTR (main.py 기준)
    CVR_RATE = 0.20  # 20% CVR (main.py 기준)


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
    
    # 메인 루프 (main.py 로직 따라감)
    try:
        while True:
            # 1. 노출 발생
            impr = generator.generate_impression()
            
            # Kinesis 전송
            sender.send(impr)
            
            # 내부 데이터 저장 (클릭/전환에서 사용)
            internal_data = impr.get('_internal', {})
            
            # 2. 클릭 확률 (CTR: 10% 가정)
            if generator.should_click(internal_data.get('ad_format', 'display')):
                time.sleep(random.uniform(0.5, 2.0))  # 클릭 딜레이
                
                click = generator.generate_click(impr)
                
                sender.send(click)
                
                # 3. 전환 확률 (CVR: 20% 가정)
                if generator.should_convert():
                    time.sleep(random.uniform(1.0, 5.0))  # 전환 딜레이
                    
                    conv = generator.generate_conversion(click)
                    
                    sender.send(conv)
            
            # 기본 대기 (1초에 하나씩)
            time.sleep(0.3)
    
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