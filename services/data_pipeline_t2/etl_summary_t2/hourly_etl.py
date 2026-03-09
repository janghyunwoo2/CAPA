"""
Hourly ETL: impression + click 조인하여 ad_combined_log 생성
매시간 실행되어 해당 시간의 데이터를 처리
"""

import os
import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional

from athena_utils import AthenaQueryExecutor
from config import DATABASE, S3_PATHS, PARTITION_FORMATS

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
            current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            self.target_hour = current_hour - timedelta(hours=1)
        
        # 파티션 키 추출 (year/month/day/hour)
        self.year = self.target_hour.strftime("%Y")
        self.month = self.target_hour.strftime("%m")
        self.day = self.target_hour.strftime("%d")
        self.hour = self.target_hour.strftime("%H")
        
        self.hour_str = self.target_hour.strftime(PARTITION_FORMATS["hourly"])
        
        logger.info(f"Processing hour: {self.hour_str} (Partition: {self.year}/{self.month}/{self.day}/{self.hour})")
        
    def generate_hourly_etl_query(self) -> str:
        """INSERT INTO 쿼리 생성 (dt 파티션 기반)"""
        # 기존 테이블이 dt 파티션 사용 (year/month/day/hour가 아님)
        query = f"""
        SELECT 
            imp.impression_id,
            imp.user_id,
            imp.ad_id,
            imp.campaign_id,
            imp.advertiser_id,
            imp.platform,
            imp.device_type,
            imp.timestamp,
            CASE WHEN clk.click_id IS NOT NULL THEN true ELSE false END AS is_click,
            clk.timestamp AS click_timestamp,
            '{self.hour_str}' AS dt
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
        """테이블이 없을 때 CREATE EXTERNAL TABLE + INSERT로 생성 (dt 파티션)"""
        # Step 1: EXTERNAL 테이블 생성 (dt 파티션 기반)
        create_table_query = f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log (
            impression_id STRING,
            user_id STRING,
            ad_id STRING,
            campaign_id STRING,
            advertiser_id STRING,
            platform STRING,
            device_type STRING,
            timestamp BIGINT,
            is_click BOOLEAN,
            click_timestamp BIGINT
        )
        PARTITIONED BY (
            dt STRING
        )
        STORED AS PARQUET
        LOCATION '{S3_PATHS["ad_combined_log"]}'
        TBLPROPERTIES (
            'classification'='parquet',
            'compressionType'='snappy'
        )
        """
        
        logger.info(f"Creating external table {DATABASE}.ad_combined_log")
        self.executor.execute_query(create_table_query)
        logger.info("✅ Table created successfully")
        
        # Step 2: 첫 번째 파티션 데이터 삽입
        insert_query = f"""
        INSERT INTO {DATABASE}.ad_combined_log
        {self.generate_hourly_etl_query()}
        """
        
        logger.info(f"Inserting first partition data for {self.hour_str}")
        self.executor.execute_query(insert_query)
        logger.info("✅ First partition data inserted")
        
        # Step 3: 파티션 등록
        self._repair_partitions()
    
    def _insert_data_overwrite(self):
        """기존 테이블에 DELETE + INSERT로 데이터 삽입 (dt 파티션 기반)"""
        # Step 1: 기존 파티션 데이터 삭제 (dt 파티션 사용)
        delete_query = f"""
        DELETE FROM {DATABASE}.ad_combined_log
        WHERE dt = '{self.hour_str}'
        """
        
        logger.info(f"Deleting existing partition data for {self.hour_str}")
        try:
            self.executor.execute_query(delete_query)
            logger.info("✅ Existing data deleted")
        except Exception as e:
            # DELETE가 지원되지 않을 경우 경고 후 계속 진행
            logger.warning(f"⚠️  DELETE not supported, attempting INSERT anyway: {str(e)}")
        
        # Step 2: 새 데이터 삽입
        insert_query = f"""
        INSERT INTO {DATABASE}.ad_combined_log
        {self.generate_hourly_etl_query()}
        """
        
        logger.info(f"Executing INSERT INTO for {self.hour_str}")
        self.executor.execute_query(insert_query)
        logger.info("✅ Data inserted successfully")
        
        # Step 3: 파티션 등록 (MSCK REPAIR TABLE)
        self._repair_partitions()
    
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
            CASE 
                WHEN COUNT(*) > 0 
                THEN CAST(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) * 100
                ELSE 0.0
            END as ctr
        FROM {DATABASE}.ad_combined_log
        WHERE dt = '{self.hour_str}'
        """
        
        query_id = self.executor.execute_query(validation_query)
        results = self.executor.get_query_results(query_id)
        
        if results:
            result = results[0]
            logger.info(
                f"✅ Hourly ETL completed - "
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