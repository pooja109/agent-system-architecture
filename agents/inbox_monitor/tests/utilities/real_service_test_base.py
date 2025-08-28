"""
Real Service Test Base Class
Common functionality for real service integration testing.
"""
import os
import time
from typing import Dict, Any, Optional
import pytest
import structlog

logger = structlog.get_logger()

class RealServiceTestBase:
    """
    Base class for real service integration testing.
    
    Provides common setup, teardown, and utility methods
    for testing against live Azure and Databricks services.
    """
    
    @classmethod
    def setup_class(cls):
        """Common setup for real service testing."""
        logger.info(f"Starting real service testing for {cls.__name__}")
        
        # Verify test environment
        cls._verify_test_environment()
        
        # Initialize performance tracking
        cls.test_start_time = time.time()
        cls.performance_data = {}
        
        # Set test configuration
        os.environ['REAL_SERVICE_TESTING'] = 'true'
        os.environ['ENABLE_PERFORMANCE_MEASUREMENT'] = 'true'
    
    @classmethod
    def _verify_test_environment(cls):
        """Verify that test environment is properly configured."""
        required_env_vars = [
            'AZURE_TENANT_ID',
            'AZURE_CLIENT_ID', 
            'AZURE_CLIENT_SECRET',
            'AZURE_KEY_VAULT_URL',
            'DATABRICKS_SERVER_HOSTNAME'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            pytest.skip(f"Real service testing requires environment variables: {missing_vars}")
        
        # Verify Key Vault URL format
        kv_url = os.getenv('AZURE_KEY_VAULT_URL')
        if not (kv_url.startswith('https://') and kv_url.endswith('.vault.azure.net/')):
            pytest.skip(f"Invalid Key Vault URL format: {kv_url}")
        
        # Verify Databricks hostname format
        db_hostname = os.getenv('DATABRICKS_SERVER_HOSTNAME')
        if not (db_hostname.endswith('.databricks.com') or db_hostname.endswith('.cloud.databricks.com')):
            pytest.skip(f"Invalid Databricks hostname format: {db_hostname}")
        
        logger.info("Real service test environment verified")
    
    def record_performance_metric(self, metric_name: str, value: float):
        """Record a performance metric for analysis."""
        self.performance_data[metric_name] = value
        logger.info(f"Performance metric recorded: {metric_name} = {value:.3f}s")
    
    def validate_performance_requirement(self, metric_name: str, max_allowed: float):
        """Validate that a performance metric meets requirements."""
        actual_value = self.performance_data.get(metric_name)
        if actual_value is None:
            pytest.fail(f"Performance metric '{metric_name}' not recorded")
        
        if actual_value > max_allowed:
            pytest.fail(f"Performance requirement failed: {metric_name} = {actual_value:.3f}s > {max_allowed}s")
        
        logger.info(f"Performance requirement met: {metric_name} = {actual_value:.3f}s <= {max_allowed}s")
    
    @classmethod
    def teardown_class(cls):
        """Common teardown for real service testing."""
        total_test_time = time.time() - cls.test_start_time
        logger.info(f"Real service testing completed for {cls.__name__} in {total_test_time:.2f}s")
        
        # Clean up environment
        os.environ.pop('REAL_SERVICE_TESTING', None)
        os.environ.pop('ENABLE_PERFORMANCE_MEASUREMENT', None)