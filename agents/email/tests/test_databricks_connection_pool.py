"""
Basic Connection Pool Tests for Email Agent
============================================

Basic tests for connection pool functionality to ensure Phase 3 compliance.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from services.databricks_connection_pool import (
    DatabricksConnectionPool,
    ConnectionPoolConfig,
    PooledConnection,
    ConnectionPoolMetrics,
    ConnectionPoolException,
    ConnectionPoolExhaustedException
)
from services.databricks_oauth_client import DatabricksOAuthClient
from services.azure_key_vault_client import AzureKeyVaultClient
from config.settings import DatabricksOAuthSettings, KeyVaultSettings


@pytest.fixture
def pool_config():
    """Create test pool configuration."""
    return ConnectionPoolConfig(
        min_connections=1,
        max_connections=3,
        connection_timeout_seconds=5,
        health_check_interval_seconds=60
    )


@pytest.fixture
def databricks_settings():
    """Create test Databricks settings."""
    return DatabricksOAuthSettings(
        server_hostname="test-workspace.databricks.com",
        http_path="/sql/1.0/warehouses/test-warehouse",
        catalog="test_catalog",
        schema_name="test_schema"
    )


@pytest.fixture
def key_vault_settings():
    """Create test Key Vault settings."""
    from pydantic import SecretStr
    return KeyVaultSettings(
        key_vault_url="https://test-vault.vault.azure.net/",
        azure_tenant_id="test-tenant",
        azure_client_id="test-client",
        azure_client_secret=SecretStr("test-secret")
    )


@pytest.fixture
def connection_pool(databricks_settings, key_vault_settings, pool_config):
    """Create connection pool for testing."""
    return DatabricksConnectionPool(
        databricks_settings,
        key_vault_settings,
        pool_config
    )


class TestConnectionPoolConfig:
    """Test connection pool configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ConnectionPoolConfig()
        
        assert config.min_connections == 2
        assert config.max_connections == 5
        assert config.connection_timeout_seconds == 30
        assert config.health_check_interval_seconds == 300
        assert config.max_connection_age_seconds == 3600


@pytest.mark.asyncio
class TestDatabricksClientPooled:
    """Test pooled DatabricksClient functionality."""
    
    async def test_databricks_client_import(self):
        """Test that DatabricksClient can import with pooling."""
        try:
            from database.databricks_client import DatabricksClient
            from services.pooled_service_base import PooledServiceBase
            
            # Verify inheritance
            assert issubclass(DatabricksClient, PooledServiceBase)
            
            # Test basic instantiation
            client = DatabricksClient()
            assert client is not None
            
        except ImportError as e:
            pytest.fail(f"Failed to import pooled DatabricksClient: {e}")
    
    async def test_databricks_client_has_pooled_methods(self):
        """Test that DatabricksClient has expected pooled methods."""
        from database.databricks_client import DatabricksClient
        
        client = DatabricksClient()
        
        # Should have base class methods
        assert hasattr(client, 'execute_with_connection')
        assert hasattr(client, 'test_connection')
        
        # Should have original methods
        assert hasattr(client, 'execute_query')


@pytest.mark.asyncio
class TestConnectionPoolBasic:
    """Test basic connection pool functionality."""
    
    async def test_pool_creation(self, connection_pool):
        """Test basic pool creation."""
        assert connection_pool.config.min_connections == 1
        assert connection_pool.config.max_connections == 3
        assert connection_pool._is_initialized is False
    
    async def test_pool_metrics(self, connection_pool):
        """Test pool metrics creation."""
        metrics = connection_pool.get_metrics()
        assert isinstance(metrics, ConnectionPoolMetrics)
        assert metrics.total_connections == 0
        assert metrics.active_connections == 0


class TestGlobalPoolManagement:
    """Test global pool management functions."""
    
    @pytest.mark.asyncio
    async def test_global_pool_not_initialized(self):
        """Test error when global pool not initialized."""
        from services.databricks_connection_pool import get_connection_pool, ConnectionPoolException
        
        with pytest.raises(ConnectionPoolException, match="not initialized"):
            await get_connection_pool()
    
    def test_connection_pool_config_in_settings(self):
        """Test that ConnectionPoolConfig is available in connection pool module."""
        from services.databricks_connection_pool import ConnectionPoolConfig
        
        config = ConnectionPoolConfig()
        assert config.min_connections == 2
        assert config.max_connections == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])