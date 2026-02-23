#!/usr/bin/env python3
"""
광고 로그 데이터 생성기
AWS S3에 Parquet(zstd) 형식으로 광고 로그 데이터를 생성하여 저장합니다.
"""

import os
import sys
import json
import random
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from decimal import Decimal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from faker import Faker
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS S3 설정
S3_BUCKET_NAME = "capa-data-lake-827913617635"
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")

# 데이터 설정
BATCH_SIZE = 10000  # 배치당 레코드 수
TARGET_FILE_SIZE_MB = 150  # 목표 파일 크기 (MB)

# 카테고리 정의
USERS = [f"user_{i:06d}" for i in range(1, 100001)]
ADS = [f"ad_{i:04d}" for i in range(1, 1001)]
CAMPAIGNS = [f"campaign_{i:02d}" for i in range(1, 6)]
ADVERTISERS = [f"advertiser_{i:02d}" for i in range(1, 31)]
STORES = [f"store_{i:04d}" for i in range(1, 5001)]
PLATFORMS = ["web", "app_ios", "app_android", "tablet_ios", "tablet_android"]
DEVICE_TYPES = ["mobile", "tablet", "desktop", "others"]
OS_TYPES = ["ios", "android", "macos", "windows"]
REGIONS = ["강남구", "서초구", "마포구", "송파구", "영등포구", "종로구", "중구", 
           "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
           "도봉구", "노원구", "은평구", "서대문구", "구로구", "금천구", "관악구",
           "동작구", "양천구", "강서구", "강동구"]
FOOD_CATEGORIES = ["korean", "chinese", "japanese", "asian", "western",
                    "pork", "pizza", "chicken", "steam/soup","bunsik",
                    "cafe/dessert", "burger", "pasta", "seafood"]
AD_POSITIONS = ["home_top_rolling", "list_top_fixed", "search_ai_recommend", "checkout_bottom"]
AD_FORMATS = ["display", "native", "video", "discount_coupon"]
KEYWORDS = [f"keyword_{i:03d}" for i in range(1, 501)]
PRODUCTS = [f"prod_{i:05d}" for i in range(1, 10001)]
CONVERSION_TYPES = ["purchase", "signup", "download", "view_content", "add_to_cart"]

# CTR/CVR 설정
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

class AdLogGenerator:
    def __init__(self):
        self.faker = Faker('ko_KR')
        self.s3_client = boto3.client('s3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=S3_REGION
        )
        
        # 광고주-상점 매핑 생성
        self.advertiser_store_mapping = self._create_advertiser_store_mapping()
        
    def _create_advertiser_store_mapping(self) -> Dict[str, List[str]]:
        """광고주와 상점의 매핑을 생성합니다."""
        mapping = {}
        store_idx = 0
        
        # advertiser_01 ~ advertiser_10: 각 50개 상점
        for i in range(1, 11):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx+50]
            store_idx += 50
            
        # advertiser_11 ~ advertiser_25: 각 100개 상점
        for i in range(11, 26):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx+100]
            store_idx += 100
            
        # advertiser_26 ~ advertiser_30: 각 200개 상점
        for i in range(26, 31):
            advertiser = f"advertiser_{i:02d}"
            mapping[advertiser] = STORES[store_idx:store_idx+200]
            store_idx += 200
            
        return mapping
    
    def _get_traffic_multiplier(self, timestamp: datetime) -> float:
        """시간대별, 요일별 트래픽 멀티플라이어를 반환합니다."""
        hour = timestamp.hour
        weekday = timestamp.weekday()  # 0=월요일, 6=일요일
        
        # 시간대별 패턴
        if 0 <= hour < 7:
            hour_mult = random.uniform(0.1, 0.2)
        elif 7 <= hour < 9:
            hour_mult = random.uniform(0.4, 0.6)
        elif 9 <= hour < 11:
            hour_mult = random.uniform(0.3, 0.5)
        elif 11 <= hour < 14:
            hour_mult = random.uniform(1.5, 2.0)
        elif 14 <= hour < 17:
            hour_mult = random.uniform(0.6, 0.8)
        elif 17 <= hour < 21:
            hour_mult = random.uniform(2.0, 3.0)
        else:
            hour_mult = random.uniform(1.0, 1.5)
            
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
    
    def generate_impressions(self, start_time: datetime, num_records: int) -> pd.DataFrame:
        """노출 데이터를 생성합니다."""
        impressions = []
        
        for _ in range(num_records):
            advertiser = random.choice(ADVERTISERS)
            store = random.choice(self.advertiser_store_mapping[advertiser])
            ad_format = random.choice(AD_FORMATS)
            
            impression = {
                'impression_id': str(uuid.uuid4()),
                'timestamp': start_time + timedelta(seconds=random.randint(0, 3599)),
                'user_id': random.choice(USERS),
                'ad_id': random.choice(ADS),
                'campaign_id': random.choice(CAMPAIGNS),
                'advertiser_id': advertiser,
                'platform': random.choice(PLATFORMS),
                'device_type': random.choice(DEVICE_TYPES),
                'os': random.choice(OS_TYPES),
                'delivery_region': random.choice(REGIONS),
                'user_lat': round(random.uniform(37.4, 37.7), 6),
                'user_long': round(random.uniform(126.8, 127.1), 6),
                'store_id': store,
                'food_category': random.choice(FOOD_CATEGORIES),
                'ad_position': random.choice(AD_POSITIONS),
                'ad_format': ad_format,
                'user_agent': self.faker.user_agent(),
                'ip_address': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.0",
                'session_id': str(uuid.uuid4()),
                'keyword': random.choice(KEYWORDS),
                'cost_per_impression': round(random.uniform(0.005, 0.10), 3)
            }
            impressions.append(impression)
            
        return pd.DataFrame(impressions)
    
    def generate_clicks(self, impressions_df: pd.DataFrame) -> pd.DataFrame:
        """클릭 데이터를 생성합니다."""
        clicks = []
        
        for _, impression in impressions_df.iterrows():
            # CTR 적용
            ad_format = impression['ad_format']
            ctr_min, ctr_max = CTR_RATES.get(ad_format, (0.01, 0.03))
            ctr = random.uniform(ctr_min, ctr_max)
            
            # 지역별 가중치 (강남/서초 1.2배)
            if impression['delivery_region'] in ['강남구', '서초구']:
                ctr *= 1.2
                
            if random.random() < ctr:
                click = {
                    'click_id': str(uuid.uuid4()),
                    'impression_id': impression['impression_id'],
                    'timestamp': impression['timestamp'] + timedelta(seconds=random.randint(1, 300)),
                    'user_id': impression['user_id'],
                    'ad_id': impression['ad_id'],
                    'campaign_id': impression['campaign_id'],
                    'advertiser_id': impression['advertiser_id'],
                    'platform': impression['platform'],
                    'click_position_x': random.randint(0, 728),
                    'click_position_y': random.randint(0, 90),
                    'landing_page_url': f"https://store.example.com/{impression['advertiser_id']}/{impression['store_id']}",
                    'cost_per_click': round(random.uniform(0.1, 5.0), 2)
                }
                clicks.append(click)
                
        return pd.DataFrame(clicks)
    
    def generate_conversions(self, clicks_df: pd.DataFrame, impressions_df: pd.DataFrame) -> pd.DataFrame:
        """전환 데이터를 생성합니다."""
        conversions = []
        
        # 클릭과 노출 데이터 조인
        merged_df = clicks_df.merge(impressions_df[['impression_id', 'delivery_region', 'store_id']], 
                                    on='impression_id', how='left')
        
        for _, click in merged_df.iterrows():
            conversion_type = random.choice(CONVERSION_TYPES)
            cvr_min, cvr_max = CVR_RATES[conversion_type]
            
            if random.random() < cvr_max:
                # 전환 시간 계산 (클릭 후 1분 ~ 7일)
                min_delay = 60  # 1분
                max_delay = 7 * 24 * 60 * 60  # 7일
                conversion_delay = random.randint(min_delay, max_delay)
                
                conversion = {
                    'conversion_id': str(uuid.uuid4()),
                    'click_id': click['click_id'],
                    'impression_id': click['impression_id'],
                    'timestamp': click['timestamp'] + timedelta(seconds=conversion_delay),
                    'user_id': click['user_id'],
                    'ad_id': click['ad_id'],
                    'campaign_id': click['campaign_id'],
                    'advertiser_id': click['advertiser_id'],
                    'conversion_type': conversion_type,
                    'conversion_value': round(random.uniform(1.0, 10000.0), 2),
                    'product_id': random.choice(PRODUCTS),
                    'quantity': random.randint(1, 10),
                    'store_id': click['store_id'],
                    'delivery_region': click['delivery_region'],
                    'attribution_window': random.choice(['1day', '7day', '30day'])
                }
                conversions.append(conversion)
                
        return pd.DataFrame(conversions)
    
    def save_to_s3(self, df: pd.DataFrame, table_name: str, timestamp: datetime):
        """데이터프레임을 S3에 Parquet 형식으로 저장합니다."""
        if df.empty:
            logger.warning(f"No data to save for {table_name}")
            return
            
        # 파티션 경로 생성
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        hour = timestamp.hour
        
        s3_key = f"raw/{table_name}/year={year}/month={month:02d}/day={day:02d}/hour={hour:02d}/"
        filename = f"{table_name}_{year}{month:02d}{day:02d}_{hour:02d}_{uuid.uuid4().hex[:8]}.parquet.zstd"
        full_key = s3_key + filename
        
        # Parquet 테이블 생성
        table = pa.Table.from_pandas(df)
        
        # 메모리에 쓰기
        buf = pa.BufferOutputStream()
        pq.write_table(table, buf, compression='zstd', compression_level=3)
        
        # S3에 업로드
        try:
            self.s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=full_key,
                Body=buf.getvalue().to_pybytes()
            )
            logger.info(f"Saved {len(df)} records to s3://{S3_BUCKET_NAME}/{full_key}")
        except Exception as e:
            logger.error(f"Failed to save to S3: {e}")
            raise
    
    def generate_hourly_data(self, target_datetime: datetime):
        """특정 시간대의 데이터를 생성합니다."""
        # 기본 시간당 노출 수 계산
        base_impressions = 10000
        traffic_multiplier = self._get_traffic_multiplier(target_datetime)
        num_impressions = int(base_impressions * traffic_multiplier)
        
        logger.info(f"Generating data for {target_datetime.strftime('%Y-%m-%d %H:00')} "
                   f"with multiplier {traffic_multiplier:.2f} ({num_impressions} impressions)")
        
        # 노출 데이터 생성
        impressions_df = self.generate_impressions(target_datetime, num_impressions)
        self.save_to_s3(impressions_df, 'impressions', target_datetime)
        
        # 클릭 데이터 생성
        clicks_df = self.generate_clicks(impressions_df)
        self.save_to_s3(clicks_df, 'clicks', target_datetime)
        
        # 전환 데이터 생성
        conversions_df = self.generate_conversions(clicks_df, impressions_df)
        self.save_to_s3(conversions_df, 'conversions', target_datetime)
        
        logger.info(f"Generated: {len(impressions_df)} impressions, "
                   f"{len(clicks_df)} clicks, {len(conversions_df)} conversions")
        
        return {
            'datetime': target_datetime,
            'impressions': len(impressions_df),
            'clicks': len(clicks_df),
            'conversions': len(conversions_df),
            'ctr': len(clicks_df) / len(impressions_df) * 100 if len(impressions_df) > 0 else 0,
            'cvr': len(conversions_df) / len(impressions_df) * 100 if len(impressions_df) > 0 else 0
        }


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='광고 로그 데이터 생성기',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
사용 예시:
  # 오늘 전체 24시간 데이터 생성
  python ad_log_generator.py
  
  # 특정 날짜 전체 데이터 생성
  python ad_log_generator.py --date 2026-02-20
  
  # 특정 날짜의 특정 시간대만 생성
  python ad_log_generator.py --date 2026-02-20 --start-hour 12 --hours 6
  
  # 날짜 범위로 여러 날 데이터 생성 (3일간)
  python ad_log_generator.py --start-date 2026-02-20 --end-date 2026-02-22
  
  # 지난 7일간 데이터 생성
  python ad_log_generator.py --days-back 7
        '''
    )
    
    parser.add_argument('--date', type=str, 
                       help='생성할 단일 날짜 (YYYY-MM-DD 형식)')
    parser.add_argument('--start-date', type=str,
                       help='생성할 시작 날짜 (YYYY-MM-DD 형식)')
    parser.add_argument('--end-date', type=str,
                       help='생성할 종료 날짜 (YYYY-MM-DD 형식, 포함)')
    parser.add_argument('--days-back', type=int,
                       help='오늘부터 과거 N일간 데이터 생성')
    parser.add_argument('--hours', type=int, default=24,
                       help='날짜별 생성할 시간 수 (기본값: 24시간)')
    parser.add_argument('--start-hour', type=int, default=0,
                       help='시작 시간 (0-23, 기본값: 0)')
    
    args = parser.parse_args()
    
    # 날짜 범위 결정
    dates_to_process = []
    
    if args.date:
        # 단일 날짜 지정
        dates_to_process = [datetime.strptime(args.date, '%Y-%m-%d')]
    elif args.start_date and args.end_date:
        # 날짜 범위 지정
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        current_date = start_date
        while current_date <= end_date:
            dates_to_process.append(current_date)
            current_date += timedelta(days=1)
    elif args.days_back:
        # 과거 N일 지정
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=args.days_back - 1)
        current_date = start_date
        while current_date <= end_date:
            dates_to_process.append(current_date)
            current_date += timedelta(days=1)
    else:
        # 기본값: 오늘
        dates_to_process = [datetime.now()]
    
    # 생성기 인스턴스 생성
    generator = AdLogGenerator()
    
    # 전체 통계 수집
    all_stats = []
    
    logger.info(f"데이터 생성 시작: {len(dates_to_process)}일간")
    
    # 각 날짜별로 데이터 생성
    for target_date in dates_to_process:
        logger.info(f"\n=== {target_date.strftime('%Y-%m-%d')} 데이터 생성 중 ===")
        
        # 해당 날짜의 시간별 데이터 생성
        for hour_offset in range(args.hours):
            current_hour = (args.start_hour + hour_offset) % 24
            target_datetime = target_date.replace(hour=current_hour, minute=0, second=0, microsecond=0)
            
            if hour_offset >= 24:
                # 다음 날로 이동
                target_datetime += timedelta(days=hour_offset // 24)
                
            try:
                stat = generator.generate_hourly_data(target_datetime)
                all_stats.append(stat)
            except Exception as e:
                logger.error(f"Failed to generate data for {target_datetime}: {e}")
            
    # 전체 통계 출력
    if all_stats:
        logger.info("\n=== 전체 생성 완료 통계 ===")
        total_impressions = sum(s['impressions'] for s in all_stats)
        total_clicks = sum(s['clicks'] for s in all_stats)
        total_conversions = sum(s['conversions'] for s in all_stats)
        
        logger.info(f"처리된 날짜: {len(dates_to_process)}일")
        logger.info(f"처리된 시간: {len(all_stats)}시간")
        logger.info(f"총 노출: {total_impressions:,}")
        logger.info(f"총 클릭: {total_clicks:,}")
        logger.info(f"총 전환: {total_conversions:,}")
        logger.info(f"평균 CTR: {total_clicks/total_impressions*100:.2f}%")
        logger.info(f"평균 CVR: {total_conversions/total_impressions*100:.2f}%")


if __name__ == "__main__":
    main()