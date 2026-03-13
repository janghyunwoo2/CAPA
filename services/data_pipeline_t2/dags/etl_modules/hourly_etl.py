"""
Hourly ETL: impression + click 조인하여 ad_combined_log 생성
매시간 실행되어 해당 시간의 데이터를 처리
"""

import os
import logging
import argparse
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .athena_utils import AthenaQueryExecutor
from .config import DATABASE, S3_PATHS, PARTITION_FORMATS, SUMMARY_HOURLY_PATH, AWS_REGION, ATHENA_OUTPUT_LOCATION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HourlyETL:
    """시간별 ETL 처리 클래스"""
    
    def __init__(self, target_hour: Optional[datetime] = None):
        """
        Args:
            target_hour: 처리할 시간 (None이면 현재 시간 - 1시간)
        """
        self.executor = AthenaQueryExecutor()
        
        # 처리 대상 시간 설정 (기본: 1시간 전 데이터)
        if target_hour:
            self.target_hour = target_hour.replace(minute=0, second=0, microsecond=0)
        else:
            current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            self.target_hour = current_hour - timedelta(hours=1)
        
        # 파티션 키 추출 (year/month/day/hour)
        self.year = self.target_hour.strftime("%Y")
        self.month = self.target_hour.strftime("%m")
        self.day = self.target_hour.strftime("%d")
        self.hour = self.target_hour.strftime("%H")
        
        self.hour_str = self.target_hour.strftime(PARTITION_FORMATS["hourly"])
        
        logger.info(f"Processing hour: {self.hour_str} (Partition: {self.year}/{self.month}/{self.day}/{self.hour})")
        
    def generate_hourly_etl_query(self) -> str:
        """SELECT 쿼리 생성 (데이터 필드만 27개, 파티션 컬럼은 Python에서 추가)"""
        # 27개 필드: impression 20 + click 6 + is_click 1
        # ✅ 파티션 컬럼(year, month, day, hour)은 제외!
        query = f"""
        SELECT 
            -- Impression 필드 (20개)
            imp.impression_id,
            imp.user_id,
            imp.ad_id,
            imp.campaign_id,
            imp.advertiser_id,
            imp.platform,
            imp.device_type,
            imp.os,
            imp.delivery_region,
            imp.user_lat,
            imp.user_long,
            imp.store_id,
            imp.food_category,
            imp.ad_position,
            imp.ad_format,
            imp.user_agent,
            imp.ip_address,
            imp.session_id,
            imp.keyword,
            imp.cost_per_impression,
            imp.timestamp AS impression_timestamp,
            
            -- Click 필드 (6개)
            clk.click_id,
            clk.click_position_x,
            clk.click_position_y,
            clk.landing_page_url,
            clk.cost_per_click,
            clk.timestamp AS click_timestamp,
            
            -- 조인 플래그 (1개)
            CASE WHEN clk.click_id IS NOT NULL THEN true ELSE false END AS is_click
        FROM {DATABASE}.impressions imp
        LEFT JOIN {DATABASE}.clicks clk
            ON imp.impression_id = clk.impression_id
            AND clk.year = '{self.year}'
            AND clk.month = '{self.month}'
            AND clk.day = '{self.day}'
            AND clk.hour = '{self.hour}'
        WHERE imp.year = '{self.year}'
            AND imp.month = '{self.month}'
            AND imp.day = '{self.day}'
            AND imp.hour = '{self.hour}'
        """
        
        return query
        
    def _table_exists(self) -> bool:
        """테이블 존재 여부 확인 (DESCRIBE 사용)"""
        try:
            # DESCRIBE는 테이블이 없으면 실패하고, 있으면 성공
            check_query = f"DESCRIBE {DATABASE}.ad_combined_log"
            query_id = self.executor.execute_query(check_query)
            # 쿼리가 성공했다 = 테이블이 존재한다
            logger.info("✅ Table ad_combined_log exists")
            return True
        except Exception as e:
            # 쿼리가 실패했다 = 테이블이 없다
            logger.info(f"❌ Table does not exist: {str(e)}")
            return False
    
    def run(self):
        """ETL 실행 (CTAS로 테이블 생성, INSERT OVERWRITE로 데이터 삽입)"""
        try:
            # 1. 테이블 존재 여부 확인
            if not self._table_exists():
                # 테이블이 없으면 CTAS로 생성 (1회만 실행)
                logger.info("📌 Table does not exist, creating with CTAS...")
                self._create_table_with_ctas()
            else:
                # 테이블이 있으면 INSERT OVERWRITE로 데이터 삽입
                logger.info("✅ Table exists, inserting data with INSERT OVERWRITE...")
                self._insert_data_overwrite()
            
            # 2. 처리 결과 확인
            self._validate_results()
            
        except Exception as e:
            logger.error(f"❌ Hourly ETL failed: {str(e)}")
            raise
    
    def _create_table_with_ctas(self):
        """테이블이 없을 때 CREATE EXTERNAL TABLE + CTAS + UNLOAD로 생성 (year/month/day/hour 파티션)"""
        # Step 0: 기존 테이블 제거 (잘못된 이름으로 생성된 경우 대비)
        try:
            drop_query = f"DROP TABLE IF EXISTS {DATABASE}.ad_combined_log"
            logger.info("Dropping existing table if exists...")
            self.executor.execute_query(drop_query)
            logger.info("✅ Old table dropped (if existed)")
        except Exception as e:
            logger.warning(f"⚠️  Failed to drop old table: {str(e)}")
        
        # Step 1: EXTERNAL 테이블 생성 (27개 필드 + 파티션)
        create_table_query = f"""
        CREATE EXTERNAL TABLE {DATABASE}.ad_combined_log (
            -- Impression 필드 (20개)
            impression_id STRING,
            user_id STRING,
            ad_id STRING,
            campaign_id STRING,
            advertiser_id STRING,
            platform STRING,
            device_type STRING,
            os STRING,
            delivery_region STRING,
            user_lat DOUBLE,
            user_long DOUBLE,
            store_id STRING,
            food_category STRING,
            ad_position STRING,
            ad_format STRING,
            user_agent STRING,
            ip_address STRING,
            session_id STRING,
            keyword STRING,
            cost_per_impression DOUBLE,
            impression_timestamp BIGINT,
            
            -- Click 필드 (6개)
            click_id STRING,
            click_position_x INT,
            click_position_y INT,
            landing_page_url STRING,
            cost_per_click DOUBLE,
            click_timestamp BIGINT,
            
            -- 조인 플래그 (1개)
            is_click BOOLEAN
        )
        PARTITIONED BY (
            year STRING,
            month STRING,
            day STRING,
            hour STRING
        )
        STORED AS PARQUET
        LOCATION '{S3_PATHS["ad_combined_log"]}'
        TBLPROPERTIES (
            'classification'='parquet',
            'compressionType'='snappy'
        )
        """
        
        logger.info(f"Creating external table {DATABASE}.ad_combined_log with year/month/day/hour partitions")
        self.executor.execute_query(create_table_query)
        logger.info("✅ Table created successfully")
        
        # Step 2: CTAS + UNLOAD로 첫 번째 파티션 데이터 삽입 (INSERT 미지원)
        self._insert_data_overwrite()
    
    def _insert_data_overwrite(self):
        """✅ Athena 메타데이터에서 직접 결과 조회하여 S3에 저장 (Athena INSERT 미지원)"""
        # Athena는 INSERT INTO를 지원하지 않으므로, 다음 방식 사용:
        # 1. SELECT 쿼리로 Athena에서 데이터 조회
        # 2. Athena 메타데이터에서 결과를 Pandas DataFrame으로 변환
        # 3. S3에 Parquet으로 저장
        # 4. MSCK REPAIR TABLE로 메타데이터 갱신
        
        s3_partition_path = f"{S3_PATHS['ad_combined_log']}/year={self.year}/month={self.month}/day={self.day}/hour={self.hour}/"
        
        try:
            # Step 1: SELECT 쿼리로 데이터 조회
            logger.info(f"Querying data for {self.year}/{self.month}/{self.day}/{self.hour}...")
            select_query = self.generate_hourly_etl_query()
            
            # Athena에서 쿼리 실행
            query_id = self.executor.execute_query(select_query)
            
            # Step 2: Athena 메타데이터에서 결과 조회
            logger.info(f"Loading query results from Athena metadata...")
            results = self.executor.get_query_results(query_id)
            
            if not results:
                logger.warning(f"⚠️  No data found for {self.year}/{self.month}/{self.day}/{self.hour}")
                return
            
            # 메타데이터를 DataFrame으로 변환
            df = pd.DataFrame(results)
            
            # ✅ 파티션 컬럼을 DataFrame에 명시적으로 추가 (경로가 아니라 데이터로)
            df['year'] = self.year
            df['month'] = self.month
            df['day'] = self.day
            df['hour'] = self.hour
            
            # ✅ 타입 변환: Athena는 모든 값을 문자열로 반환하므로 명시적 타입 변환 필요
            # Boolean 필드 변환 ('true'/'false' 문자열 → bool)
            if 'is_click' in df.columns:
                df['is_click'] = df['is_click'].astype(str).str.lower() == 'true'
            
            # 숫자 필드 변환
            numeric_columns = ['user_lat', 'user_long', 'cost_per_impression', 'click_position_x', 
                             'click_position_y', 'cost_per_click', 'impression_timestamp', 'click_timestamp']
            for col in numeric_columns:
                if col in df.columns:
                    try:
                        if col in ['click_position_x', 'click_position_y']:
                            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                        elif col in ['impression_timestamp', 'click_timestamp']:
                            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                        else:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    except Exception:
                        logger.warning(f"⚠️  Failed to convert column {col}")
            
            logger.info(f"✅ Queried {len(df)} rows from Athena")
            
            # Step 3: PyArrow 스키마를 명시적으로 정의하여 Parquet 저장 (메타데이터 정확성 보장)
            logger.info(f"Saving {len(df)} rows to {s3_partition_path}...")
            
            # ✅ 명시적 스키마 정의 (데이터 타입 정확성 + Glue 자동감지 안정성)
            schema = pa.schema([
                # Impression 필드 (20개)
                ('impression_id', pa.string()),
                ('user_id', pa.string()),
                ('ad_id', pa.string()),
                ('campaign_id', pa.string()),
                ('advertiser_id', pa.string()),
                ('platform', pa.string()),
                ('device_type', pa.string()),
                ('os', pa.string()),
                ('delivery_region', pa.string()),
                ('user_lat', pa.float64()),
                ('user_long', pa.float64()),
                ('store_id', pa.string()),
                ('food_category', pa.string()),
                ('ad_position', pa.string()),
                ('ad_format', pa.string()),
                ('user_agent', pa.string()),
                ('ip_address', pa.string()),
                ('session_id', pa.string()),
                ('keyword', pa.string()),
                ('cost_per_impression', pa.float64()),
                ('impression_timestamp', pa.int64()),
                # Click 필드 (6개)
                ('click_id', pa.string()),
                ('click_position_x', pa.int32()),
                ('click_position_y', pa.int32()),
                ('landing_page_url', pa.string()),
                ('cost_per_click', pa.float64()),
                ('click_timestamp', pa.int64()),
                # 조인 플래그 (1개)
                ('is_click', pa.bool_()),
                # ✅ 파티션 컬럼은 Python에서 추가되면 스키마에도 자동 추가됨
            ])
            
            # DataFrame을 PyArrow Table로 변환 (스키마 적용)
            table = pa.Table.from_pandas(df, schema=schema)
            
            s3_client = boto3.client('s3', region_name=AWS_REGION)
            
            # 임시 로컬 파일로 저장 (Windows 호환)
            temp_dir = tempfile.gettempdir()
            local_parquet_file = os.path.join(temp_dir, f"ad_combined_log_{self.year}-{self.month}-{self.day}-{self.hour}.parquet")
            
            # ✅ PyArrow로 저장 (스키마 포함)
            pq.write_table(table, local_parquet_file, compression='snappy')
            
            # S3에 업로드
            bucket_name = S3_PATHS['ad_combined_log'].split('/')[2]  # s3://bucket_name/... 에서 bucket_name 추출
            s3_key = s3_partition_path.replace(f"s3://{bucket_name}/", "")
            s3_object_key = f"{s3_key}ad_combined_log.parquet"
            
            s3_client.upload_file(
                local_parquet_file,
                bucket_name,
                s3_object_key
            )
            
            logger.info(f"✅ Data saved to s3://{bucket_name}/{s3_object_key}")
            
            # Step 4: 메타데이터 갱신
            self._repair_partitions()
            
        except Exception as e:
            logger.error(f"❌ Failed to insert data: {str(e)}")
            raise
    
    def _repair_partitions(self):
        """S3의 데이터를 Glue 카탈로그에 파티션으로 등록"""
        repair_query = f"MSCK REPAIR TABLE {DATABASE}.ad_combined_log"
        
        logger.info("Repairing partitions...")
        try:
            self.executor.execute_query(repair_query)
            logger.info("✅ Partitions repaired successfully")
        except Exception as e:
            logger.warning(f"⚠️  Partition repair failed: {str(e)}")
            # 파티션 수리 실패해도 계속 진행 (데이터는 있으므로)
    
    def _validate_results(self):
        """처리 결과 확인"""
        validation_query = f"""
        SELECT 
            COUNT(*) as total_impressions,
            SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as total_clicks,
            COUNT(DISTINCT click_id) as unique_clicks,
            CASE 
                WHEN COUNT(*) > 0 
                THEN CAST(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) * 100
                ELSE 0.0
            END as ctr
        FROM {DATABASE}.ad_combined_log
        WHERE year = '{self.year}'
            AND month = '{self.month}'
            AND day = '{self.day}'
            AND hour = '{self.hour}'
        """
        
        query_id = self.executor.execute_query(validation_query)
        results = self.executor.get_query_results(query_id)
        
        if results:
            result = results[0]
            logger.info(
                f"✅ Hourly ETL completed ({self.year}/{self.month}/{self.day}/{self.hour}) - "
                f"Impressions: {result.get('total_impressions', 0)}, "
                f"Clicks: {result.get('total_clicks', 0)}, "
                f"CTR: {float(result.get('ctr', 0)):.2f}%"
            )


def main():
    """CLI 실행"""
    parser = argparse.ArgumentParser(description='Run hourly ETL for ad_combined_log')
    parser.add_argument(
        '--target-hour',
        type=str,
        help='Target hour to process (YYYY-MM-DD-HH format). Default: previous hour'
    )
    
    args = parser.parse_args()
    
    target_hour = None
    if args.target_hour:
        try:
            # 입력 형식: 2026-02-24-14
            target_hour = datetime.strptime(args.target_hour, "%Y-%m-%d-%H")
        except ValueError:
            logger.error(f"Invalid hour format: {args.target_hour}")
            return
            
    etl = HourlyETL(target_hour)
    etl.run()


if __name__ == "__main__":
    main()