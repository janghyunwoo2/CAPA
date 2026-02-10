"""
Ad Log Generator - 메인 실행 스크립트
로그 생성 + Kinesis 전송 (환경 변수로 제어)
"""

import time
import json
import random
import os
from dotenv import load_dotenv

from generator import AdLogGenerator
from kinesis_sender import KinesisSender

# .env 파일 로드
load_dotenv()


# =============================================================================
# 설정
# =============================================================================

class Config:
    """환경 변수 기반 설정"""
    
    # Kinesis 설정
    ENABLE_KINESIS = os.getenv("ENABLE_KINESIS", "false").lower() == "true"
    KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "capa-ad-logs-dev")
    AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
    
    # AWS 자격증명 (선택)
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # 로그 생성 설정
    USERS_COUNT = int(os.getenv("USERS_COUNT", "200"))
    SHOPS_COUNT = int(os.getenv("SHOPS_COUNT", "30"))


# =============================================================================
# 메인 실행
# =============================================================================

def main():
    """메인 실행 함수"""
    
    print("=" * 60, flush=True)
    print("🚀 Ad Log Generator 시작", flush=True)
    print("=" * 60, flush=True)
    
    # 로그 생성기 초기화
    generator = AdLogGenerator(
        users_count=Config.USERS_COUNT,
        shops_count=Config.SHOPS_COUNT
    )
    print(f"✅ 로그 생성기 초기화 완료 (유저: {Config.USERS_COUNT}, 가게: {Config.SHOPS_COUNT})", flush=True)
    
    # Kinesis Sender 초기화 (활성화된 경우)
    sender = None
    if Config.ENABLE_KINESIS:
        sender = KinesisSender(
            stream_name=Config.KINESIS_STREAM_NAME,
            region=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY
        )
        print(f"✅ Kinesis 전송 활성화: {Config.KINESIS_STREAM_NAME} ({Config.AWS_REGION})", flush=True)
    else:
        print("ℹ️  Kinesis 전송 비활성화 (stdout만 사용)", flush=True)
    
    print("=" * 60, flush=True)
    print("📊 로그 생성 시작...\n", flush=True)
    
    # 메인 루프
    try:
        while True:
            # 1. Impression 생성
            impr = generator.generate_impression()
            category = impr.pop("_category")  # 내부용 필드 제거
            
            # stdout 출력
            print(json.dumps(impr, ensure_ascii=False), flush=True)
            
            # Kinesis 전송
            if sender:
                sender.send(impr)
            
            # 2. 클릭 여부 결정
            if generator.should_click(category):
                time.sleep(random.uniform(0.3, 1.5))
                
                click = generator.generate_click(impr)
                print(json.dumps(click, ensure_ascii=False), flush=True)
                
                if sender:
                    sender.send(click)
                
                # 3. 전환 여부 결정
                action = random.choices(
                    ["view_menu", "add_to_cart", "order"],
                    weights=[0.55, 0.30, 0.15],
                    k=1
                )[0]
                
                if generator.should_convert(action):
                    time.sleep(random.uniform(0.5, 3.0))
                    
                    conv = generator.generate_conversion(click)
                    print(json.dumps(conv, ensure_ascii=False), flush=True)
                    
                    if sender:
                        sender.send(conv)
            
            # 기본 대기
            time.sleep(random.uniform(0.1, 0.5))
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60, flush=True)
        print("🛑 로그 생성 중지됨", flush=True)
        
        if sender:
            stats = sender.get_stats()
            print(f"\n📊 Kinesis 전송 통계:", flush=True)
            print(f"  - 성공: {stats['success']}", flush=True)
            print(f"  - 실패: {stats['error']}", flush=True)
            print(f"  - 전체: {stats['total']}", flush=True)
        
        print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
