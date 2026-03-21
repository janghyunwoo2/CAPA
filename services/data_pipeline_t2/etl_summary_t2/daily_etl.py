"""
Daily ETL: 24시간 ad_combined_log + conversion 집계하여 ad_combined_log_summary 생성
매일 실행되어 전날 데이터를 처리
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
from .config import DATABASE, S3_PATHS, PARTITION_FORMATS, AWS_REGION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailyETL:
    """일별 ETL 처리 클래스"""
    
    def __init__(self, target_date: Optional[datetime] = None):
        """
        Args:
            target_date: 처리할 날짜 (None이면 어제)
        """
        self.executor = AthenaQueryExecutor()
        
        # 처리 대상 날짜 설정 (기본: 어제)
        if target_date:
            self.target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            self.target_date = today - timedelta(days=1)
        
        # 파티션 키 추출 (year/month/day)
        self.year = self.target_date.strftime("%Y")
        self.month = self.target_date.strftime("%m")
        self.day = self.target_date.strftime("%d")
        
        self.date_str = self.target_date.strftime(PARTITION_FORMATS["daily"])
        
        logger.info(f"Processing date: {self.date_str} (Partition: {self.year}/{self.month}/{self.day})")
        
    def generate_daily_etl_query(self) -> str:
        """SELECT 쿼리 생성 (데이터 필드만 35개, 파티션 컬럼은 Python에서 추가)"""
        # ad_combined_log (hourly 24건) LEFT JOIN conversions (하루치)
        # 35개 필드: hourly 27 + conversion 8
        # ✅ 파티션 컬럼(year, month, day)은 제외!
        query = f"""
        SELECT 
            -- Impression 필드 (20개) - hourly에서 상속
            acl.impression_id,
            acl.user_id,
            acl.ad_id,
            acl.campaign_id,
            acl.advertiser_id,
            acl.platform,
            acl.device_type,
            acl.os,
            acl.delivery_region,
            acl.user_lat,
            acl.user_long,
            acl.store_id,
            acl.food_category,
            acl.ad_position,
            acl.ad_format,
            acl.user_agent,
            acl.ip_address,
            acl.session_id,
            acl.keyword,
            acl.cost_per_impression,
            acl.impression_timestamp,
            
            -- Click 필드 (6개) - hourly에서 상속
            acl.click_id,
            acl.click_position_x,
            acl.click_position_y,
            acl.landing_page_url,
            acl.cost_per_click,
            acl.click_timestamp,
            
            -- is_click (1개) - hourly에서 상속
            acl.is_click,
            
            -- Conversion 필드 (7개) - daily에서만 추가
            conv.conversion_id,
            conv.conversion_type,
            conv.conversion_value,
            conv.product_id,
            conv.quantity,
            conv.attribution_window,
            conv.timestamp AS conversion_timestamp,
            
            -- is_conversion (1개) - daily에서만 추가
            CASE WHEN conv.conversion_id IS NOT NULL THEN true ELSE false END AS is_conversion
        FROM {DATABASE}.ad_combined_log acl
        LEFT JOIN {DATABASE}.conversions conv
            ON acl.impression_id = conv.impression_id
            AND conv.year = '{self.year}'
            AND conv.month = '{self.month}'
            AND conv.day = '{self.day}'
        WHERE acl.year = '{self.year}'
            AND acl.month = '{self.month}'
            AND acl.day = '{self.day}'
        """
        
        return query
        
    def _table_exists(self) -> bool:
        """테이블 존재 여부 확인 (DESCRIBE 사용)"""
        try:
            # DESCRIBE는 테이블이 없으면 실패하고, 있으면 성공
            check_query = f"DESCRIBE {DATABASE}.ad_combined_log_summary"
            query_id = self.executor.execute_query(check_query)
            # 쿼리가 성공했다 = 테이블이 존재한다
            logger.info("✅ Table ad_combined_log_summary exists")
            return True
        except Exception as e:
            # 쿼리가 실패했다 = 테이블이 없다
            logger.info(f"❌ Table does not exist: {str(e)}")
            return False
    
    def run(self):
        """ETL 실행 (CTAS로 테이블 생성, INSERT OVERWRITE로 데이터 삽입)"""
        try:
            # 0. 의존성 확인: ad_combined_log 테이블 존재 여부 (필수!)
            self._check_dependencies()
            
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
            logger.error(f"❌ Daily ETL failed: {str(e)}")
            raise
    
    def _check_dependencies(self):
        """의존성 확인: ad_combined_log 테이블이 존재해야 함"""
        try:
            check_query = f"DESCRIBE {DATABASE}.ad_combined_log"
            self.executor.execute_query(check_query)
            logger.info("✅ Dependency check passed: ad_combined_log exists")
        except Exception as e:
            error_msg = (
                f"❌ Required table '{DATABASE}.ad_combined_log' not found\n"
                f"   Please run hourly backfill first:\n"
                f"   python -m etl_summary_t2.run_etl backfill \\\n"
                f"     --start-date {self.year}-{self.month}-{self.day} \\\n"
                f"     --end-date {self.year}-{self.month}-{self.day} \\\n"
                f"     --type hourly"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def _create_table_with_ctas(self):
        """테이블이 없을 때 CREATE EXTERNAL TABLE + INSERT로 생성 (year/month/day 파티션)"""
        # Step 1: EXTERNAL 테이블 생성 (35개 필드 + 파티션)
        create_table_query = f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log_summary (
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
            
            -- is_click (1개)
            is_click BOOLEAN,
            
            -- Conversion 필드 (7개)
            conversion_id STRING,
            conversion_type STRING,
            conversion_value DOUBLE,
            product_id STRING,
            quantity INT,
            attribution_window STRING,
            conversion_timestamp BIGINT,
            
            -- is_conversion (1개)
            is_conversion BOOLEAN
        )
        PARTITIONED BY (
            year STRING,
            month STRING,
            day STRING
        )
        STORED AS PARQUET
        LOCATION '{S3_PATHS["ad_combined_log_summary"]}'
        TBLPROPERTIES (
            'classification'='parquet',
            'compressionType'='snappy'
        )
        """
        
        logger.info(f"Creating external table {DATABASE}.ad_combined_log_summary with year/month/day partitions")
        self.executor.execute_query(create_table_query)
        logger.info("✅ Table created successfully")
        
        # Step 2: 첫 번째 파티션 데이터 삽입 (Python + S3 저장)
        self._insert_data_overwrite()
    
    def _insert_data_overwrite(self):
        """✅ Athena 메타데이터에서 직접 결과 조회하여 S3에 저장 (Athena INSERT 미지원)"""
        # Athena는 INSERT INTO를 지원하지 않으므로, 다음 방식 사용:
        # 1. SELECT 쿼리로 Athena에서 데이터 조회
        # 2. Athena 메타데이터에서 결과를 Pandas DataFrame으로 변환
        # 3. S3에 Parquet으로 저장
        # 4. MSCK REPAIR TABLE로 메타데이터 갱신
        
        s3_partition_path = f"{S3_PATHS['ad_combined_log_summary']}/year={self.year}/month={self.month}/day={self.day}/"
        
        try:
            # Step 1: 24시간 데이터 존재 여부 확인
            check_query = f"""
            SELECT COUNT(DISTINCT hour) as hour_count
            FROM {DATABASE}.ad_combined_log
            WHERE year = '{self.year}'
                AND month = '{self.month}'
                AND day = '{self.day}'
            """
            
            query_id = self.executor.execute_query(check_query)
            results = self.executor.get_query_results(query_id)
            
            if results:
                hour_count = int(results[0].get('hour_count', 0))
                if hour_count < 24:
                    logger.warning(
                        f"⚠️  Only {hour_count}/24 hours of data available for {self.date_str}. "
                        f"Proceeding with available data."
                    )
            
            # Step 2: SELECT 쿼리로 데이터 조회
            logger.info(f"Querying data for {self.year}/{self.month}/{self.day}...")
            select_query = self.generate_daily_etl_query()
            
            # Athena에서 쿼리 실행
            query_id = self.executor.execute_query(select_query)
            
            # Step 3: Athena 메타데이터에서 결과 조회
            logger.info(f"Loading query results from Athena metadata...")
            results = self.executor.get_query_results(query_id)
            
            if not results:
                logger.warning(f"⚠️  No data found for {self.year}/{self.month}/{self.day}")
                return
            
            # 메타데이터를 DataFrame으로 변환
            df = pd.DataFrame(results)
            
            # ✅ 파티션 컬럼을 DataFrame에 명시적으로 추가 (경로가 아니라 데이터로)
            df['year'] = self.year
            df['month'] = self.month
            df['day'] = self.day
            
            # ✅ 타입 변환: Athena는 모든 값을 문자열로 반환하므로 명시적 타입 변환 필요
            # Boolean 필드 변환 ('true'/'false' 문자열 → bool)
            for col in ['is_click', 'is_conversion']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.lower() == 'true'
            
            # 숫자 필드 변환
            numeric_columns = ['user_lat', 'user_long', 'cost_per_impression', 'click_position_x', 
                             'click_position_y', 'cost_per_click', 'impression_timestamp', 'click_timestamp',
                             'conversion_value', 'quantity', 'conversion_timestamp']
            for col in numeric_columns:
                if col in df.columns:
                    try:
                        if col in ['click_position_x', 'click_position_y', 'quantity']:
                            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                        elif col in ['impression_timestamp', 'click_timestamp', 'conversion_timestamp']:
                            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                        else:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    except Exception:
                        logger.warning(f"⚠️  Failed to convert column {col}")
            
            logger.info(f"✅ Queried {len(df)} rows from Athena")
            
            # Step 4: PyArrow 스키마를 명시적으로 정의하여 Parquet 저장 (메타데이터 정확성 보장)
            logger.info(f"Saving {len(df)} rows to {s3_partition_path}...")
            
            # ✅ 명시적 스키마 정의 (35개 컬럼: impression 20 + click 6 + is_click 1 + conversion 7 + is_conversion 1)
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
                # Conversion 필드 (7개)
                ('conversion_id', pa.string()),
                ('conversion_type', pa.string()),
                ('conversion_value', pa.float64()),
                ('product_id', pa.string()),
                ('quantity', pa.int32()),
                ('attribution_window', pa.string()),
                ('conversion_timestamp', pa.int64()),
                # 조인 플래그 (1개)
                ('is_conversion', pa.bool_()),
                # ✅ 파티션 컬럼은 Python에서 추가되면 스키마에도 자동 추가됨
            ])
            
            # DataFrame을 PyArrow Table로 변환 (스키마 적용)
            table = pa.Table.from_pandas(df, schema=schema)
            
            s3_client = boto3.client('s3', region_name=AWS_REGION)
            
            # 임시 로컬 파일로 저장 (Windows 호환)
            temp_dir = tempfile.gettempdir()
            local_parquet_file = os.path.join(temp_dir, f"ad_combined_log_summary_{self.year}-{self.month}-{self.day}.parquet")
            
            # ✅ PyArrow로 저장 (스키마 포함)
            pq.write_table(table, local_parquet_file, compression='snappy')
            
            # S3에 업로드
            bucket_name = S3_PATHS['ad_combined_log_summary'].split('/')[2]  # s3://bucket_name/... 에서 bucket_name 추출
            s3_key = s3_partition_path.replace(f"s3://{bucket_name}/", "")
            s3_object_key = f"{s3_key}ad_combined_log_summary.parquet"
            
            s3_client.upload_file(
                local_parquet_file,
                bucket_name,
                s3_object_key
            )
            
            logger.info(f"✅ Data saved to s3://{bucket_name}/{s3_object_key}")
            
            # Step 5: 메타데이터 갱신
            self._repair_partitions()
            
        except Exception as e:
            logger.error(f"❌ Failed to insert data: {str(e)}")
            raise
    
    def _validate_results(self):
        """처리 결과 확인"""
        validation_query = f"""
        SELECT 
            COUNT(DISTINCT impression_id) as total_impressions,
            SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as total_clicks,
            SUM(CASE WHEN is_conversion THEN 1 ELSE 0 END) as total_conversions,
            COUNT(DISTINCT campaign_id) as campaign_count,
            CASE 
                WHEN COUNT(DISTINCT impression_id) > 0 
                THEN CAST(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(DISTINCT impression_id) * 100
                ELSE 0.0
            END as ctr
        FROM {DATABASE}.ad_combined_log_summary
        WHERE year = '{self.year}'
            AND month = '{self.month}'
            AND day = '{self.day}'
        """
        
        query_id = self.executor.execute_query(validation_query)
        results = self.executor.get_query_results(query_id)
        
        if results:
            result = results[0]
            logger.info(
                f"✅ Daily ETL completed ({self.year}/{self.month}/{self.day}) - "
                f"Impressions: {result.get('total_impressions', 0)}, "
                f"Clicks: {result.get('total_clicks', 0)}, "
                f"Conversions: {result.get('total_conversions', 0)}, "
                f"CTR: {float(result.get('ctr', 0)):.2f}%"
            )


    def _repair_partitions(self):
        """S3의 데이터를 Glue 카탈로그에 파티션으로 등록"""
        repair_query = f"MSCK REPAIR TABLE {DATABASE}.ad_combined_log_summary"
        
        logger.info("Repairing partitions...")
        try:
            self.executor.execute_query(repair_query)
            logger.info("✅ Partitions repaired successfully")
        except Exception as e:
            logger.warning(f"⚠️  Partition repair failed: {str(e)}")
            # 파티션 수리 실패해도 계속 진행 (데이터는 있으므로)


def main():
    """CLI 실행"""
    parser = argparse.ArgumentParser(description='Run daily ETL for ad_combined_log_summary')
    parser.add_argument(
        '--target-date',
        type=str,
        help='Target date to process (YYYY-MM-DD format). Default: yesterday'
    )
    
    args = parser.parse_args()
    
    target_date = None
    if args.target_date:
        try:
            # 입력 형식: 2026-02-24
            target_date = datetime.strptime(args.target_date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {args.target_date}")
            return
            
    etl = DailyETL(target_date)
    etl.run()


if __name__ == "__main__":
    main()