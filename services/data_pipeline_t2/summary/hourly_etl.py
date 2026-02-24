"""
Hourly ETL: impression + click 조인하여 ad_combined_log 생성
매시간 실행되어 해당 시간의 데이터를 처리
"""

import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional

from athena_utils import AthenaQueryExecutor, create_external_table, repair_table_partitions
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
            
        self.hour_str = self.target_hour.strftime(PARTITION_FORMATS["hourly"])
        
        logger.info(f"Processing hour: {self.hour_str}")
        
    def create_tables_if_not_exists(self):
        """필요한 테이블이 없으면 생성"""
        # ad_combined_log 테이블 생성
        schema = """
            imp_event_id STRING,
            user_id STRING,
            campaign_id STRING,
            creative_id STRING,
            device_type STRING,
            timestamp BIGINT,
            is_click BOOLEAN,
            bid_price DOUBLE,
            click_timestamp BIGINT
        """
        
        query = create_external_table(
            table_name="ad_combined_log",
            schema=schema,
            location=S3_PATHS["ad_combined_log"],
            partition_keys=[("dt", "STRING")]
        )
        
        logger.info("Creating ad_combined_log table if not exists")
        self.executor.execute_query(query)
        
    def generate_hourly_etl_query(self) -> str:
        """시간별 ETL 쿼리 생성"""
        # Raw 데이터의 파티션 정보
        year = self.target_hour.strftime(PARTITION_FORMATS["raw"]["year"])
        month = self.target_hour.strftime(PARTITION_FORMATS["raw"]["month"])
        day = self.target_hour.strftime(PARTITION_FORMATS["raw"]["day"])
        hour = self.target_hour.strftime(PARTITION_FORMATS["raw"]["hour"])
        
        # Unix timestamp 범위 (milliseconds)
        start_ts = int(self.target_hour.timestamp() * 1000)
        end_ts = int((self.target_hour + timedelta(hours=1)).timestamp() * 1000)
        
        query = f"""
        INSERT OVERWRITE TABLE {DATABASE}.ad_combined_log
        PARTITION (dt='{self.hour_str}')
        SELECT 
            imp.event_id AS imp_event_id,
            imp.user_id,
            imp.campaign_id,
            imp.creative_id,
            imp.device_type,
            imp.timestamp,
            CASE WHEN clk.event_id IS NOT NULL THEN true ELSE false END AS is_click,
            imp.bid_price,
            clk.timestamp AS click_timestamp
        FROM {DATABASE}.ad_events_raw imp
        LEFT JOIN {DATABASE}.ad_events_raw clk
            ON imp.event_id = clk.imp_event_id
            AND clk.event_type = 'click'
            AND clk.year = '{year}'
            AND clk.month = '{month}'
            AND clk.day = '{day}'
            AND clk.timestamp >= {start_ts}
            AND clk.timestamp < {end_ts}
        WHERE imp.event_type = 'impression'
            AND imp.year = '{year}'
            AND imp.month = '{month}'
            AND imp.day = '{day}'
            AND imp.timestamp >= {start_ts}
            AND imp.timestamp < {end_ts}
        """
        
        return query
        
    def run(self):
        """ETL 실행"""
        try:
            # 1. 테이블 생성 (필요시)
            self.create_tables_if_not_exists()
            
            # 2. 임시 테이블로 CTAS 실행 (Athena에서 INSERT OVERWRITE 대신 사용)
            temp_table = f"ad_combined_log_temp_{self.hour_str.replace('-', '_')}"
            
            # 임시 테이블 삭제
            drop_query = f"DROP TABLE IF EXISTS {DATABASE}.{temp_table}"
            self.executor.execute_query(drop_query)
            
            # CTAS 쿼리 생성
            ctas_query = f"""
            CREATE TABLE {DATABASE}.{temp_table}
            WITH (
                format = 'PARQUET',
                write_compression = 'ZSTD',
                external_location = '{S3_PATHS["ad_combined_log"]}dt={self.hour_str}/'
            ) AS
            SELECT 
                imp.event_id AS imp_event_id,
                imp.user_id,
                imp.campaign_id,
                imp.creative_id,
                imp.device_type,
                imp.timestamp,
                CASE WHEN clk.event_id IS NOT NULL THEN true ELSE false END AS is_click,
                imp.bid_price,
                clk.timestamp AS click_timestamp
            FROM {DATABASE}.ad_events_raw imp
            LEFT JOIN {DATABASE}.ad_events_raw clk
                ON imp.event_id = clk.imp_event_id
                AND clk.event_type = 'click'
                AND clk.year = '{self.target_hour.strftime("%Y")}'
                AND clk.month = '{self.target_hour.strftime("%m")}'
                AND clk.day = '{self.target_hour.strftime("%d")}'
                AND clk.timestamp >= {int(self.target_hour.timestamp() * 1000)}
                AND clk.timestamp < {int((self.target_hour + timedelta(hours=1)).timestamp() * 1000)}
            WHERE imp.event_type = 'impression'
                AND imp.year = '{self.target_hour.strftime("%Y")}'
                AND imp.month = '{self.target_hour.strftime("%m")}'
                AND imp.day = '{self.target_hour.strftime("%d")}'
                AND imp.timestamp >= {int(self.target_hour.timestamp() * 1000)}
                AND imp.timestamp < {int((self.target_hour + timedelta(hours=1)).timestamp() * 1000)}
            """
            
            logger.info(f"Executing CTAS query for {self.hour_str}")
            self.executor.execute_query(ctas_query)
            
            # 3. 임시 테이블 삭제
            self.executor.execute_query(drop_query)
            
            # 4. 파티션 복구 (새 파티션 인식)
            repair_query = repair_table_partitions("ad_combined_log")
            logger.info("Repairing partitions")
            self.executor.execute_query(repair_query)
            
            # 5. 처리 결과 확인
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
                    f"Hourly ETL completed - "
                    f"Impressions: {result.get('total_impressions', 0)}, "
                    f"Clicks: {result.get('total_clicks', 0)}, "
                    f"CTR: {float(result.get('ctr', 0)):.2f}%"
                )
            
        except Exception as e:
            logger.error(f"Hourly ETL failed: {str(e)}")
            raise


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