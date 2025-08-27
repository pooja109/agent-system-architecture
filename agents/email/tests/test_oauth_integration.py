"""
OAuth Integration Tests for Email Agent
=======================================

Integration tests that verify OAuth authentication works with real services
when integration testing is enabled via environment variables.
"""

import pytest
import os
from unittest.mock import AsyncMock
from pydantic import SecretStr

from services.databricks_oauth_client import DatabricksOAuthClient
from services.azure_key_vault_client import AzureKeyVaultClient
from database.databricks_client import DatabricksClient
from config.settings import DatabricksOAuthSettings, KeyVaultSettings


@pytest.mark.integration
class TestOAuthIntegration:
    """Integration tests for OAuth functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled. Set RUN_INTEGRATION_TESTS=1")
    
    @pytest.fixture
    def key_vault_settings(self):
        """Create Key Vault settings from environment."""
        return KeyVaultSettings(
            key_vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
            azure_tenant_id=os.getenv("AZURE_TENANT_ID"),
            azure_client_id=os.getenv("AZURE_CLIENT_ID"),
            azure_client_secret=SecretStr(os.getenv("AZURE_CLIENT_SECRET"))
        )
    
    @pytest.fixture
    def databricks_settings(self):
        """Create Databricks OAuth settings from environment."""
        return DatabricksOAuthSettings(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
            http_path=os.getenv("DATABRICKS_HTTP_PATH"),
            catalog=os.getenv("DATABRICKS_CATALOG", "test_catalog"),
            schema_name=os.getenv("DATABRICKS_SCHEMA", "test_schema"),
            table_suffix=os.getenv("DATABRICKS_TABLE_SUFFIX", "_test")
        )
    
    @pytest.mark.asyncio
    async def test_key_vault_oauth_integration(self, key_vault_settings):
        """Test Key Vault OAuth integration."""
        async with AzureKeyVaultClient(key_vault_settings) as client:
            # Test connection
            connection_result = await client.test_connection()
            assert connection_result is True
            
            # Test credential retrieval
            credentials = await client.get_databricks_credentials()
            assert credentials.tenant_id is not None
            assert credentials.client_id is not None
            assert credentials.client_secret is not None
    
    @pytest.mark.asyncio
    async def test_databricks_oauth_integration(self, databricks_settings, key_vault_settings):
        """Test Databricks OAuth integration."""
        async with AzureKeyVaultClient(key_vault_settings) as kv_client:
            async with DatabricksOAuthClient(databricks_settings, kv_client) as db_client:
                # Test basic connection
                connection_result = await db_client.test_connection()
                assert connection_result is True
                
                # Test SQL execution
                result = await db_client.execute_sql("SELECT 1 as test_value")
                assert result.row_count == 1
                assert result.rows[0]["test_value"] == 1
                
                # Test fetchall compatibility
                rows = await db_client.execute_sql_fetchall("SELECT 'test' as message")
                assert len(rows) == 1
                assert rows[0]["message"] == "test"
                
                # Test fetchone compatibility
                row = await db_client.execute_sql_fetchone("SELECT 'single' as result")
                assert row is not None
                assert row["result"] == "single"
    
    @pytest.mark.asyncio
    async def test_databricks_client_oauth_integration(self, databricks_settings, key_vault_settings):
        """Test DatabricksClient (email agent) with OAuth integration."""
        async with DatabricksClient(databricks_settings, key_vault_settings) as client:
            # Test connection
            connection_result = await client.test_connection()
            assert connection_result is True
            
            # Test query execution
            result = await client.execute_query("SELECT 'OAuth integration test' as message")
            assert len(result) == 1
            assert result[0]["message"] == "OAuth integration test"
            
            # Test query with parameters (basic substitution)
            result = await client.execute_query(
                "SELECT ? as param_value", 
                ["test_parameter"]
            )
            assert len(result) == 1
            assert "test_parameter" in str(result[0])
    
    @pytest.mark.asyncio
    async def test_email_stats_oauth_integration(self, databricks_settings, key_vault_settings):
        """Test email statistics with OAuth integration."""
        async with DatabricksClient(databricks_settings, key_vault_settings) as client:
            # This might fail if the email table doesn't exist, which is expected
            try:
                stats = await client.get_email_stats(days=1)
                if "error" not in stats:
                    # If table exists and query succeeds
                    assert "total_processed" in stats
                    assert "sent" in stats
                    assert "failed" in stats
                    assert "success_rate" in stats
            except Exception as e:
                # Table might not exist in test environment
                assert "does not exist" in str(e).lower() or "not found" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_oauth_error_handling(self, databricks_settings):
        """Test OAuth error handling with invalid credentials."""
        # Create invalid Key Vault settings
        invalid_kv_settings = KeyVaultSettings(
            key_vault_url="https://invalid-vault.vault.azure.net/",
            azure_tenant_id="invalid-tenant",
            azure_client_id="invalid-client",
            azure_client_secret=SecretStr("invalid-secret")
        )
        
        # This should fail gracefully
        try:
            client = DatabricksClient(databricks_settings, invalid_kv_settings)
            result = await client.connect()
            assert result is False
        except Exception as e:
            # Authentication errors are expected
            assert "authentication" in str(e).lower() or "unauthorized" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_oauth_token_info(self, databricks_settings, key_vault_settings):
        """Test OAuth token information retrieval."""
        async with AzureKeyVaultClient(key_vault_settings) as kv_client:
            async with DatabricksOAuthClient(databricks_settings, kv_client) as db_client:
                token_info = await db_client.get_current_token_info()
                
                assert token_info is not None
                assert "client_id" in token_info
                assert "tenant_id" in token_info
                assert "warehouse_id" in token_info
                assert "catalog" in token_info
                assert "schema" in token_info
                
                # Verify sensitive data is not exposed
                assert "client_secret" not in token_info
                assert "access_token" not in token_info
    
    @pytest.mark.asyncio
    async def test_sql_execution_compatibility(self, databricks_settings, key_vault_settings):
        """Test SQL execution compatibility between old and new implementations."""
        async with DatabricksClient(databricks_settings, key_vault_settings) as client:
            # Test both execute_query and execute_update methods
            try:
                # Test simple query
                result = await client.execute_query("SELECT CURRENT_TIMESTAMP() as current_time")
                assert len(result) == 1
                assert "current_time" in result[0]
                
                # Test update query (this will likely fail due to table not existing, which is expected)
                try:
                    await client.execute_update("SELECT 1")  # Simple statement that should work
                except Exception as e:
                    # Expected if test environment doesn't have proper tables
                    pass
                    
            except Exception as e:
                # Connection or permission issues are expected in test environments
                assert "connection" in str(e).lower() or "permission" in str(e).lower() or "not found" in str(e).lower()