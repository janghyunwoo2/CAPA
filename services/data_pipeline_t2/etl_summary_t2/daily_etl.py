"""
Daily ETL: 24시간 ad_combined_log + conversion 집계하여 ad_combined_log_summary 생성
매일 실행되어 전날 데이터를 처리
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
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            self.target_date = today - timedelta(days=1)
        
        # 파티션 키 추출 (year/month/day)
        self.year = self.target_date.strftime("%Y")
        self.month = self.target_date.strftime("%m")
        self.day = self.target_date.strftime("%d")
        
        self.date_str = self.target_date.strftime(PARTITION_FORMATS["daily"])
        
        logger.info(f"Processing date: {self.date_str} (Partition: {self.year}/{self.month}/{self.day})")
        
    def generate_daily_etl_query(self) -> str:
        """INSERT INTO 쿼리 생성 (dt 파티션 기반)"""
        # ad_combined_log는 dt 파티션 사용 (year/month/day/hour이 아님)
        query = f"""
        WITH combined_with_conversions AS (
            SELECT 
                acl.campaign_id,
                acl.ad_id,
                acl.advertiser_id,
                acl.device_type,
                acl.impression_id,
                acl.is_click,
                CASE WHEN cv.conversion_id IS NOT NULL THEN 1 ELSE 0 END as is_conversion
            FROM {DATABASE}.ad_combined_log acl
            LEFT JOIN {DATABASE}.conversions cv
                ON acl.impression_id = cv.impression_id
                AND cv.year = '{self.year}'
                AND cv.month = '{self.month}'
                AND cv.day = '{self.day}'
            WHERE acl.dt LIKE '{self.year}-{self.month}-{self.day}-%'
        )
        SELECT 
            campaign_id,
            ad_id,
            advertiser_id,
            device_type,
            COUNT(DISTINCT impression_id) as impressions,
            SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks,
            SUM(is_conversion) as conversions,
            '{self.date_str}' AS dt
        FROM combined_with_conversions
        GROUP BY campaign_id, ad_id, advertiser_id, device_type
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
    
    def _create_table_with_ctas(self):
        """테이블이 없을 때 CREATE EXTERNAL TABLE + INSERT로 생성 (dt 파티션)"""
        # Step 1: EXTERNAL 테이블 생성 (dt 파티션 기반)
        create_table_query = f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.ad_combined_log_summary (
            campaign_id STRING,
            ad_id STRING,
            advertiser_id STRING,
            device_type STRING,
            impressions BIGINT,
            clicks BIGINT,
            conversions BIGINT
        )
        PARTITIONED BY (
            dt STRING
        )
        STORED AS PARQUET
        LOCATION '{S3_PATHS["ad_combined_log_summary"]}'
        TBLPROPERTIES (
            'classification'='parquet',
            'compressionType'='snappy'
        )
        """
        
        logger.info(f"Creating external table {DATABASE}.ad_combined_log_summary")
        self.executor.execute_query(create_table_query)
        logger.info("✅ Table created successfully")
        
        # Step 2: 첫 번째 파티션 데이터 삽입
        insert_query = f"""
        INSERT INTO {DATABASE}.ad_combined_log_summary
        {self.generate_daily_etl_query()}
        """
        
        logger.info(f"Inserting first partition data for {self.date_str}")
        self.executor.execute_query(insert_query)
        logger.info("✅ First partition data inserted")
        
        # Step 3: 파티션 등록
        self._repair_partitions()
    
    def _insert_data_overwrite(self):
        """기존 테이블에 DELETE + INSERT로 데이터 삽입 (Athena는 INSERT OVERWRITE 미지원)"""
        # Step 1: 24시간 데이터 존재 여부 확인 (dt 파티션 기반)
        check_query = f"""
        SELECT COUNT(DISTINCT dt) as hour_count
        FROM {DATABASE}.ad_combined_log
        WHERE dt LIKE '{self.year}-{self.month}-{self.day}-%'
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
        
        # Step 2: 기존 파티션 데이터 삭제 (dt 파티션 사용)
        delete_query = f"""
        DELETE FROM {DATABASE}.ad_combined_log_summary
        WHERE dt = '{self.date_str}'
        """
        
        logger.info(f"Deleting existing partition data for {self.date_str}")
        try:
            self.executor.execute_query(delete_query)
            logger.info("✅ Existing data deleted")
        except Exception as e:
            # DELETE가 지원되지 않을 경우 경고 후 계속 진행
            logger.warning(f"⚠️  DELETE not supported, attempting INSERT anyway: {str(e)}")
        
        # Step 3: 새 데이터 삽입
        insert_query = f"""
        INSERT INTO {DATABASE}.ad_combined_log_summary
        {self.generate_daily_etl_query()}
        """
        
        logger.info(f"Executing INSERT INTO for {self.date_str}")
        self.executor.execute_query(insert_query)
        logger.info("✅ Data inserted successfully")
        
        # Step 4: 파티션 등록
        self._repair_partitions()
    
    def _validate_results(self):
        """처리 결과 확인"""
        validation_query = f"""
        SELECT 
            COUNT(*) as campaign_count,
            SUM(impressions) as total_impressions,
            SUM(clicks) as total_clicks,
            SUM(conversions) as total_conversions
        FROM {DATABASE}.ad_combined_log_summary
        WHERE dt = '{self.date_str}'
        """
        
        query_id = self.executor.execute_query(validation_query)
        results = self.executor.get_query_results(query_id)
        
        if results:
            result = results[0]
            logger.info(
                f"✅ Daily ETL completed - "
                f"Campaigns: {result.get('campaign_count', 0)}, "
                f"Impressions: {result.get('total_impressions', 0)}, "
                f"Clicks: {result.get('total_clicks', 0)}, "
                f"Conversions: {result.get('total_conversions', 0)}"
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