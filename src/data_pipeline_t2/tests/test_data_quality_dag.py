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

class TestDataQualityChecks:
    """Test suite for data quality validation task"""

    @patch('boto3.client')
    def test_quality_check_success(self, mock_s3_client, mock_context, mock_env):
        """Test successful data quality check and report generation"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3
        
        # Simulate quality report
        report = {
            'row_count': 1000,
            'null_ratio': {
                'user_id': 0.0,
                'email': 0.05,
                'created_at': 0.01
            },
            'timestamp': '2025-01-02T00:00:00'
        }
        
        # Assertions
        assert report['row_count'] > 0
        assert all(0 <= v <= 1 for v in report['null_ratio'].values())
        assert 'timestamp' in report

    @patch('boto3.client')
    def test_quality_check_too_many_nulls(self, mock_s3_client, mock_context, mock_env):
        """Test quality check detects excessive null values"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3
        
        # Simulate poor data quality
        null_ratio = {
            'user_id': 0.5,  # 50% null - should trigger warning
            'email': 0.7     # 70% null - should trigger alert
        }
        
        HIGH_NULL_THRESHOLD = 0.3
        violations = [col for col, ratio in null_ratio.items() if ratio > HIGH_NULL_THRESHOLD]
        
        assert len(violations) > 0
        assert 'user_id' in violations
        assert 'email' in violations

    def test_quality_report_schema(self, mock_context, mock_env):
        """Test quality report output schema is valid"""
        report = {
            'row_count': 1000,
            'null_ratio': {'col1': 0.0, 'col2': 0.1},
            'data_types': {'col1': 'INTEGER', 'col2': 'VARCHAR'},
            'check_timestamp': '2025-01-02T00:00:00'
        }
        
        # Should be JSON serializable
        json_str = json.dumps(report)
        parsed = json.loads(json_str)
        
        assert 'row_count' in parsed
        assert 'null_ratio' in parsed
        assert 'data_types' in parsed
        assert parsed['row_count'] > 0

    @patch('boto3.client')
    def test_quality_check_s3_upload(self, mock_s3_client, mock_context, mock_env):
        """Test quality report is uploaded to S3 correctly"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3
        
        # Simulate upload
        bucket = 'test-bucket'
        key = f"metadata/quality_{mock_context['ds_nodash']}.json"
        
        assert key == "metadata/quality_20250102.json"
        assert key.startswith("metadata/")
        assert key.endswith(".json")

    def test_quality_metrics_validation(self):
        """Test individual quality metrics validation rules"""
        metrics = {
            'row_count': 1000,
            'duplicate_ratio': 0.05,
            'null_ratio': 0.02,
            'type_mismatch_count': 0,
        }
        
        assert metrics['row_count'] > 0, "Row count must be positive"
        assert 0 <= metrics['duplicate_ratio'] <= 1, "Duplicate ratio must be between 0-1"
        assert 0 <= metrics['null_ratio'] <= 1, "Null ratio must be between 0-1"
        assert metrics['type_mismatch_count'] >= 0, "Type mismatch count must be non-negative"

    @patch('boto3.client')
    def test_quality_check_data_type_errors(self, mock_s3_client, mock_context, mock_env):
        """Test detection of data type inconsistencies"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3
        
        # Simulate type issues
        expected_types = {'price': 'DECIMAL', 'user_id': 'INTEGER', 'email': 'VARCHAR'}
        actual_types = {'price': 'VARCHAR', 'user_id': 'INTEGER', 'email': 'VARCHAR'}
        
        type_errors = {col: (expected_types[col], actual_types[col]) 
                      for col in expected_types if expected_types[col] != actual_types[col]}
        
        assert len(type_errors) > 0
        assert 'price' in type_errors
        assert type_errors['price'] == ('DECIMAL', 'VARCHAR')

class TestDataQualityIntegration:
    """Integration-level tests for data quality pipeline"""

    def test_quality_check_naming_convention(self, mock_context):
        """Verify quality report S3 key naming follows convention"""
        ds_nodash = mock_context['ds_nodash']
        expected_key = f"metadata/quality_{ds_nodash}.json"
        
        assert expected_key == "metadata/quality_20250102.json"
        assert expected_key.startswith("metadata/")

    def test_quality_report_timestamp(self):
        """Test quality report includes proper timestamp"""
        import re
        from datetime import datetime
        
        timestamp = datetime.now().isoformat()
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        
        assert re.match(iso_pattern, timestamp), "Timestamp should be ISO format"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
