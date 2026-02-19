"""
Pytest configuration and shared fixtures for Airflow DAG tests
"""
import pytest
import os
from unittest.mock import MagicMock

@pytest.fixture(scope='session')
def airflow_home():
    """Set up Airflow home directory for tests"""
    home = os.environ.get('AIRFLOW_HOME', '/tmp/airflow_test')
    os.makedirs(home, exist_ok=True)
    return home

@pytest.fixture
def aws_credentials(monkeypatch):
    """Mock AWS credentials for testing"""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_REGION', 'ap-northeast-2')

@pytest.fixture
def db_credentials(monkeypatch):
    """Mock database credentials for testing"""
    monkeypatch.setenv('DB_USER', 'testuser')
    monkeypatch.setenv('DB_PASS', 'testpass')
    monkeypatch.setenv('DB_HOST', 'localhost')
    monkeypatch.setenv('DB_PORT', '5432')
    monkeypatch.setenv('DB_NAME', 'testdb')

@pytest.fixture
def s3_bucket(monkeypatch):
    """Mock S3 bucket name"""
    bucket = 'test-bucket'
    monkeypatch.setenv('S3_BUCKET', bucket)
    return bucket

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )
