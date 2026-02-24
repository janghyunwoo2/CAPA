"""
Daily ETL: 24시간 ad_combined_log + conversion 집계하여 ad_combined_log_summary 생성
매일 실행되어 전날 데이터를 처리
"""

import os
import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional

from athena_utils import AthenaQueryExecutor, create_external_table, repair_table_partitions
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
            
        self.date_str = self.target_date.strftime(PARTITION_FORMATS["daily"])
        
        logger.info(f"Processing date: {self.date_str}")
        
    def create_tables_if_not_exists(self):
        """필요한 테이블이 없으면 생성"""
        # ad_combined_log_summary 테이블 생성
        schema = """
            campaign_id STRING,
            ad_id STRING,
            advertiser_id STRING,
            device_type STRING,
            impressions BIGINT,
            clicks BIGINT,
            conversions BIGINT,
            ctr DOUBLE,
            cvr DOUBLE
        """
        
        query = create_external_table(
            table_name="ad_combined_log_summary",
            schema=schema,
            location=S3_PATHS["ad_combined_log_summary"],
            partition_keys=[("dt", "STRING")]
        )
        
        logger.info("Creating ad_combined_log_summary table if not exists")
        self.executor.execute_query(query)
        
    def generate_daily_etl_query(self) -> str:
        """일별 ETL 쿼리 생성"""
        # 24시간 파티션 범위 생성
        start_hour = self.target_date.strftime(PARTITION_FORMATS["hourly"])  # 00시
        end_date = self.target_date + timedelta(days=1)
        
        # Raw conversion 데이터의 파티션 정보
        year = self.target_date.strftime(PARTITION_FORMATS["raw"]["year"])
        month = self.target_date.strftime(PARTITION_FORMATS["raw"]["month"])
        day = self.target_date.strftime(PARTITION_FORMATS["raw"]["day"])
        
        # CTAS 쿼리
        query = f"""
        WITH daily_combined AS (
            SELECT 
                campaign_id,
                ad_id,
                advertiser_id,
                device_type,
                COUNT(DISTINCT impression_id) as impressions,
                SUM(CASE WHEN is_click THEN 1 ELSE 0 END) as clicks
            FROM {DATABASE}.ad_combined_log
            WHERE dt >= '{self.date_str}-00' 
                AND dt <= '{self.date_str}-23'
            GROUP BY campaign_id, ad_id, advertiser_id, device_type
        ),
        daily_conversions AS (
            SELECT 
                campaign_id,
                device_type,
                COUNT(DISTINCT conversion_id) as conversions
            FROM {DATABASE}.conversions
            WHERE year = '{year}'
                AND month = '{month}'
                AND day = '{day}'
            GROUP BY campaign_id, device_type
        )
        SELECT 
            dc.campaign_id,
            dc.ad_id,
            dc.advertiser_id,
            dc.device_type,
            dc.impressions,
            dc.clicks,
            COALESCE(cv.conversions, 0) as conversions,
            CASE 
                WHEN dc.impressions > 0 
                THEN CAST(dc.clicks AS DOUBLE) / CAST(dc.impressions AS DOUBLE) * 100
                ELSE 0.0
            END as ctr,
            CASE 
                WHEN dc.clicks > 0 
                THEN CAST(COALESCE(cv.conversions, 0) AS DOUBLE) / CAST(dc.clicks AS DOUBLE) * 100
                ELSE 0.0
            END as cvr
        FROM daily_combined dc
        LEFT JOIN daily_conversions cv
            ON dc.campaign_id = cv.campaign_id 
            AND dc.device_type = cv.device_type
        """
        
        return query
        
    def run(self):
        """ETL 실행"""
        try:
            # 1. 테이블 생성 (필요시)
            self.create_tables_if_not_exists()
            
            # 2. 24시간 데이터 존재 여부 확인
            check_query = f"""
            SELECT COUNT(DISTINCT dt) as hour_count
            FROM {DATABASE}.ad_combined_log
            WHERE dt >= '{self.date_str}-00' 
                AND dt <= '{self.date_str}-23'
            """
            
            query_id = self.executor.execute_query(check_query)
            results = self.executor.get_query_results(query_id)
            
            if results:
                hour_count = int(results[0].get('hour_count', 0))
                if hour_count < 24:
                    logger.warning(
                        f"Only {hour_count}/24 hours of data available for {self.date_str}. "
                        f"Proceeding with available data."
                    )
            
            # 3. 임시 테이블로 CTAS 실행
            temp_table = f"ad_combined_log_summary_temp_{self.date_str.replace('-', '_')}"
            
            # 임시 테이블 삭제
            drop_query = f"DROP TABLE IF EXISTS {DATABASE}.{temp_table}"
            self.executor.execute_query(drop_query)
            
            # CTAS 쿼리
            ctas_query = f"""
            CREATE TABLE {DATABASE}.{temp_table}
            WITH (
                format = 'PARQUET',
                write_compression = 'ZSTD',
                external_location = '{S3_PATHS["ad_combined_log_summary"]}dt={self.date_str}/'
            ) AS
            {self.generate_daily_etl_query()}
            """
            
            logger.info(f"Executing CTAS query for {self.date_str}")
            self.executor.execute_query(ctas_query)
            
            # 4. 임시 테이블 삭제
            self.executor.execute_query(drop_query)
            
            # 5. 파티션 복구
            repair_query = repair_table_partitions("ad_combined_log_summary")
            logger.info("Repairing partitions")
            self.executor.execute_query(repair_query)
            
            # 6. 처리 결과 확인
            validation_query = f"""
            SELECT 
                COUNT(*) as campaign_count,
                SUM(impressions) as total_impressions,
                SUM(clicks) as total_clicks,
                SUM(conversions) as total_conversions,
                AVG(ctr) as avg_ctr,
                AVG(cvr) as avg_cvr,
                SUM(total_cost) as total_cost
            FROM {DATABASE}.ad_combined_log_summary
            WHERE dt = '{self.date_str}'
            """
            
            query_id = self.executor.execute_query(validation_query)
            results = self.executor.get_query_results(query_id)
            
            if results:
                result = results[0]
                logger.info(
                    f"Daily ETL completed - "
                    f"Campaigns: {result.get('campaign_count', 0)}, "
                    f"Impressions: {result.get('total_impressions', 0)}, "
                    f"Clicks: {result.get('total_clicks', 0)}, "
                    f"Conversions: {result.get('total_conversions', 0)}, "
                    f"Avg CTR: {float(result.get('avg_ctr', 0)):.2f}%, "
                    f"Avg CVR: {float(result.get('avg_cvr', 0)):.2f}%"
                )
            
        except Exception as e:
            logger.error(f"Daily ETL failed: {str(e)}")
            raise


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