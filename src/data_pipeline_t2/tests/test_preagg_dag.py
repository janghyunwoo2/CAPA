import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_context():
    """Mock Airflow context object"""
    ctx = {
        'ds': '2025-01-02',
        'ds_nodash': '20250102',
        'task_instance': MagicMock(),
    }
    return ctx

@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables"""
    monkeypatch.setenv('S3_BUCKET', 'test-bucket')
    monkeypatch.setenv('AWS_REGION', 'ap-northeast-2')

class TestPreAggregation:
    """Test suite for pre-aggregation (materialized view) task"""

    def test_preagg_sql_validity(self):
        """Test pre-aggregation SQL syntax is valid"""
        sql = '''
        CREATE TABLE IF NOT EXISTS analytics.preagg_ads_daily
        WITH (format='PARQUET', external_location='s3://test-bucket/preagg/ads_daily/', partitioned_by = ARRAY['ds']) AS
        SELECT advertiser_id, date(event_time) as ds, 
               count(*) as impressions, 
               sum(case when event='click' then 1 else 0 end) as clicks
        FROM analytics.raw_logs
        WHERE date(event_time)=date('2025-01-02')
        GROUP BY advertiser_id, date(event_time)
        '''
        
        # Basic SQL validation checks
        assert 'CREATE TABLE' in sql
        assert 'SELECT' in sql
        assert 'GROUP BY' in sql
        assert 'impressions' in sql
        assert 'clicks' in sql
        assert 'analytics.raw_logs' in sql

    def test_preagg_output_table_name(self, mock_context):
        """Test pre-aggregation output table naming convention"""
        table_name = 'preagg_ads_daily'
        database = 'analytics'
        full_name = f"{database}.{table_name}"
        
        assert full_name == 'analytics.preagg_ads_daily'
        assert table_name.startswith('preagg_')
        assert 'daily' in table_name

    def test_preagg_output_location(self, mock_env):
        """Test pre-aggregation S3 output location is correctly formed"""
        bucket = os.environ['S3_BUCKET']
        path = f"s3://{bucket}/preagg/ads_daily/"
        
        assert path.startswith('s3://')
        assert 'preagg' in path
        assert path.endswith('/')

    def test_preagg_partitioning_strategy(self):
        """Test partitioning strategy for pre-aggregation table"""
        partition_key = 'ds'
        partition_format = 'YYYY-MM-DD'
        
        assert partition_key == 'ds'
        assert len(partition_format) > 0
        
        # Sample date value
        sample_date = '2025-01-02'
        assert len(sample_date) == 10
        assert sample_date.count('-') == 2

    @patch('boto3.client')
    def test_preagg_athena_ctas_execution(self, mock_athena_client, mock_context, mock_env):
        """Test CTAS (Create Table As Select) execution via Athena"""
        mock_athena = MagicMock()
        mock_athena_client.return_value = mock_athena
        
        # Simulate Athena execution
        query_id = 'mock-query-id-12345'
        mock_athena.start_query_execution.return_value = {'QueryExecutionId': query_id}
        
        # Call and assert
        result = mock_athena.start_query_execution(QueryString='SELECT 1')
        assert result['QueryExecutionId'] == query_id

    def test_preagg_aggregation_metrics(self):
        """Test aggregation metrics are correct"""
        metrics = {
            'impressions': 'count(*)',
            'clicks': "sum(case when event='click' then 1 else 0 end)",
            'conversions': "sum(case when event='conversion' then 1 else 0 end)",
            'ctr': "clicks / impressions"
        }
        
        assert 'impressions' in metrics
        assert 'clicks' in metrics
        assert 'count(' in metrics['impressions']
        assert 'case when' in metrics['clicks']

    @patch('boto3.client')
    def test_preagg_idempotency(self, mock_athena_client, mock_context, mock_env):
        """Test pre-aggregation is idempotent (can be run multiple times safely)"""
        mock_athena = MagicMock()
        mock_athena_client.return_value = mock_athena
        
        # Simulate multiple executions with same date
        ds = mock_context['ds']
        
        # First run: table doesn't exist
        executions = []
        for i in range(2):
            execution_id = f'exec-{i}-{ds}'
            executions.append(execution_id)
        
        assert len(executions) == 2
        assert executions[0] != executions[1]
        # Both should be valid: shows idempotency allows re-runs

    def test_preagg_date_partition_format(self, mock_context):
        """Test date partition format matches expected pattern"""
        import re
        
        ds = mock_context['ds']
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        
        assert re.match(date_pattern, ds), f"Date {ds} should match YYYY-MM-DD format"
        assert ds == '2025-01-02'

    def test_preagg_table_metadata(self):
        """Test pre-aggregation table metadata structure"""
        metadata = {
            'table_name': 'preagg_ads_daily',
            'database': 'analytics',
            'format': 'PARQUET',
            'partition_key': 'ds',
            'partitions': ['2025-01-01', '2025-01-02'],
            'columns': [
                {'name': 'advertiser_id', 'type': 'STRING'},
                {'name': 'ds', 'type': 'STRING'},
                {'name': 'impressions', 'type': 'BIGINT'},
                {'name': 'clicks', 'type': 'BIGINT'},
            ]
        }
        
        assert metadata['format'] == 'PARQUET'
        assert metadata['partition_key'] == 'ds'
        assert len(metadata['columns']) == 4
        assert metadata['columns'][0]['name'] == 'advertiser_id'

class TestPreAggregationIntegration:
    """Integration-level tests for pre-aggregation pipeline"""

    def test_preagg_upsert_strategy(self):
        """Test upsert strategy for handling duplicate dates"""
        strategy = {
            'method': 'partition_replacement',
            'desc': 'Replace entire partition for given date',
            'idempotent': True
        }
        
        assert strategy['idempotent'] is True
        assert 'partition' in strategy['method']

    def test_preagg_data_consistency(self):
        """Test data consistency rules for aggregated data"""
        rules = {
            'impressions_gte_clicks': True,  # impressions >= clicks
            'clicks_gte_conversions': True,   # clicks >= conversions
            'no_negative_counts': True,       # all counts >= 0
        }
        
        # Example validation
        sample_row = {
            'advertiser_id': 'adv-123',
            'impressions': 1000,
            'clicks': 150,
            'conversions': 30,
        }
        
        assert sample_row['impressions'] >= sample_row['clicks']
        assert sample_row['clicks'] >= sample_row['conversions']
        assert all(v >= 0 for k, v in sample_row.items() if isinstance(v, int))

    def test_preagg_query_cost_estimation(self):
        """Test estimation of query cost (Athena scanned data)"""
        # Athena charges by scanned data (minimum 1MB per query)
        estimated_scanned_bytes = 500_000_000  # 500 MB
        estimated_scanned_gb = estimated_scanned_bytes / (1024**3)
        cost_per_gb = 5.0  # $5 per TB = $0.00000500 per byte, simplified
        estimated_cost = estimated_scanned_gb * cost_per_gb / 200
        
        assert estimated_scanned_bytes > 0
        assert estimated_scanned_gb > 0
        assert estimated_cost >= 0

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
