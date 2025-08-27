"""
Test suite for Databricks OAuth Client (Email Agent)
===================================================

Comprehensive tests for OAuth-authenticated Databricks client functionality
including authentication, SQL execution, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import DatabricksError
from pydantic import SecretStr

from services.databricks_oauth_client import (
    DatabricksOAuthClient,
    SQLExecutionResult,
    OAuthException,
    OAuthAuthenticationError,
    SQLExecutionError
)
from services.azure_key_vault_client import AzureKeyVaultClient, ServicePrincipalCredentials
from config.settings import DatabricksOAuthSettings, KeyVaultSettings


class TestDatabricksOAuthClient:
    """Test Databricks OAuth client functionality."""
    
    @pytest.fixture
    def databricks_settings(self):
        """Create test Databricks OAuth settings."""
        return DatabricksOAuthSettings(
            server_hostname="test-workspace.databricks.com",
            http_path="/sql/1.0/warehouses/test-warehouse-id",
            catalog="test_catalog",
            schema_name="test_schema",
            table_suffix="_test"
        )
    
    @pytest.fixture
    def key_vault_client(self):
        """Create mock Key Vault client."""
        mock_client = Mock(spec=AzureKeyVaultClient)
        mock_client.get_databricks_credentials = AsyncMock(return_value=ServicePrincipalCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-secret")
        ))
        return mock_client
    
    @pytest.fixture
    def oauth_client(self, databricks_settings, key_vault_client):
        """Create OAuth client for testing."""
        return DatabricksOAuthClient(databricks_settings, key_vault_client)
    
    @pytest.mark.asyncio
    async def test_client_initialization_success(self, oauth_client):
        """Test successful OAuth client initialization."""
        with patch('services.databricks_oauth_client.WorkspaceClient') as mock_workspace, \
             patch.object(oauth_client, '_setup_sql_warehouse') as mock_setup:
            
            mock_workspace_instance = Mock()
            mock_workspace.return_value = mock_workspace_instance
            mock_setup.return_value = None
            
            await oauth_client._initialize_client()
            
            # Verify workspace client creation
            mock_workspace.assert_called_once()
            call_args = mock_workspace.call_args[1]  # Get keyword arguments
            
            assert call_args['config'].host == "https://test-workspace.databricks.com"
            assert call_args['config'].client_id == "test-client-id"
            assert call_args['config'].auth_type == "oauth-m2m"
            
            # Verify SQL warehouse setup was called
            mock_setup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_client_initialization_key_vault_failure(self, oauth_client):
        """Test OAuth client initialization with Key Vault failure."""
        oauth_client.key_vault_client.get_databricks_credentials.side_effect = Exception("Key Vault error")
        
        with pytest.raises(OAuthAuthenticationError, match="Failed to initialize OAuth client"):
            await oauth_client._initialize_client()
    
    @pytest.mark.asyncio
    async def test_sql_warehouse_setup_success(self, oauth_client):
        """Test successful SQL warehouse setup."""
        # Mock workspace client with warehouse list
        mock_warehouse = Mock()
        mock_warehouse.id = "test-warehouse-id"
        
        mock_workspace = Mock()
        mock_workspace.warehouses.list.return_value = [mock_warehouse]
        oauth_client._workspace_client = mock_workspace
        
        await oauth_client._setup_sql_warehouse()
        
        assert oauth_client._warehouse_id == "test-warehouse-id"
    
    @pytest.mark.asyncio
    async def test_sql_warehouse_setup_invalid_path(self, oauth_client):
        """Test SQL warehouse setup with invalid http_path."""
        oauth_client.databricks_settings.http_path = "/invalid/path"
        
        with pytest.raises(ValueError, match="Invalid http_path format"):
            await oauth_client._setup_sql_warehouse()
    
    @pytest.mark.asyncio
    async def test_sql_warehouse_setup_warehouse_not_found(self, oauth_client):
        """Test SQL warehouse setup when warehouse not accessible."""
        mock_workspace = Mock()
        mock_workspace.warehouses.list.return_value = []  # Empty list
        oauth_client._workspace_client = mock_workspace
        
        with pytest.raises(ValueError, match="SQL warehouse test-warehouse-id not found"):
            await oauth_client._setup_sql_warehouse()
    
    @pytest.mark.asyncio
    async def test_execute_sql_success(self, oauth_client):
        """Test successful SQL execution."""
        # Mock workspace client and response
        mock_response = Mock()
        mock_response.statement_id = "test-statement-id"
        mock_response.result.data_array = [["value1", "value2"], ["value3", "value4"]]
        
        mock_column1 = Mock()
        mock_column1.name = "col1"
        mock_column2 = Mock()
        mock_column2.name = "col2"
        
        mock_response.manifest.schema.columns = [mock_column1, mock_column2]
        
        mock_workspace = Mock()
        mock_workspace.statement_execution.execute_statement.return_value = mock_response
        oauth_client._workspace_client = mock_workspace
        oauth_client._warehouse_id = "test-warehouse-id"
        
        result = await oauth_client.execute_sql("SELECT * FROM test_table")
        
        assert isinstance(result, SQLExecutionResult)
        assert result.columns == ["col1", "col2"]
        assert len(result.rows) == 2
        assert result.rows[0] == {"col1": "value1", "col2": "value2"}
        assert result.rows[1] == {"col1": "value3", "col2": "value4"}
        assert result.row_count == 2
        assert result.statement_id == "test-statement-id"
    
    @pytest.mark.asyncio
    async def test_execute_sql_with_parameters(self, oauth_client):
        """Test SQL execution with parameter substitution."""
        mock_response = Mock()
        mock_response.statement_id = "test-statement-id"
        mock_response.result.data_array = [["test_value"]]
        
        mock_column = Mock()
        mock_column.name = "result"
        mock_response.manifest.schema.columns = [mock_column]
        
        mock_workspace = Mock()
        mock_workspace.statement_execution.execute_statement.return_value = mock_response
        oauth_client._workspace_client = mock_workspace
        oauth_client._warehouse_id = "test-warehouse-id"
        
        query = "SELECT * FROM test_table WHERE id = :id AND name = :name"
        parameters = {"id": 123, "name": "test_name"}
        
        await oauth_client.execute_sql(query, parameters)
        
        # Verify parameter substitution occurred
        call_args = mock_workspace.statement_execution.execute_statement.call_args
        executed_query = call_args[1]['statement']  # Get statement from kwargs
        
        assert ":id" not in executed_query
        assert ":name" not in executed_query
        assert "123" in executed_query
        assert "'test_name'" in executed_query
    
    @pytest.mark.asyncio
    async def test_execute_sql_databricks_error(self, oauth_client):
        """Test SQL execution with Databricks error."""
        mock_workspace = Mock()
        mock_workspace.statement_execution.execute_statement.side_effect = DatabricksError("SQL error")
        oauth_client._workspace_client = mock_workspace
        oauth_client._warehouse_id = "test-warehouse-id"
        
        with pytest.raises(SQLExecutionError, match="SQL execution failed"):
            await oauth_client.execute_sql("SELECT * FROM test_table")
    
    @pytest.mark.asyncio
    async def test_execute_sql_fetchall_compatibility(self, oauth_client):
        """Test fetchall compatibility method."""
        mock_response = Mock()
        mock_response.result.data_array = [["value1"], ["value2"]]
        mock_column = Mock()
        mock_column.name = "col1"
        mock_response.manifest.schema.columns = [mock_column]
        
        mock_workspace = Mock()
        mock_workspace.statement_execution.execute_statement.return_value = mock_response
        oauth_client._workspace_client = mock_workspace
        oauth_client._warehouse_id = "test-warehouse-id"
        
        rows = await oauth_client.execute_sql_fetchall("SELECT * FROM test_table")
        
        assert len(rows) == 2
        assert rows[0] == {"col1": "value1"}
        assert rows[1] == {"col1": "value2"}
    
    @pytest.mark.asyncio
    async def test_execute_sql_fetchone_compatibility(self, oauth_client):
        """Test fetchone compatibility method."""
        mock_response = Mock()
        mock_response.result.data_array = [["value1"], ["value2"]]
        mock_column = Mock()
        mock_column.name = "col1"
        mock_response.manifest.schema.columns = [mock_column]
        
        mock_workspace = Mock()
        mock_workspace.statement_execution.execute_statement.return_value = mock_response
        oauth_client._workspace_client = mock_workspace
        oauth_client._warehouse_id = "test-warehouse-id"
        
        row = await oauth_client.execute_sql_fetchone("SELECT * FROM test_table")
        
        assert row == {"col1": "value1"}
    
    @pytest.mark.asyncio
    async def test_execute_sql_fetchone_no_results(self, oauth_client):
        """Test fetchone with no results."""
        mock_response = Mock()
        mock_response.result.data_array = []
        mock_response.manifest.schema.columns = []
        
        mock_workspace = Mock()
        mock_workspace.statement_execution.execute_statement.return_value = mock_response
        oauth_client._workspace_client = mock_workspace
        oauth_client._warehouse_id = "test-warehouse-id"
        
        row = await oauth_client.execute_sql_fetchone("SELECT * FROM test_table WHERE 1=0")
        
        assert row is None
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, oauth_client):
        """Test successful connection test."""
        with patch.object(oauth_client, '_initialize_client'), \
             patch.object(oauth_client, 'execute_sql') as mock_execute:
            
            mock_execute.return_value = SQLExecutionResult(
                columns=["test_connection"],
                rows=[{"test_connection": 1}],
                row_count=1
            )
            
            result = await oauth_client.test_connection()
            assert result is True
            
            # Verify test query was executed
            mock_execute.assert_called_once_with("SELECT 1 as test_connection")
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self, oauth_client):
        """Test connection test failure."""
        with patch.object(oauth_client, '_initialize_client'), \
             patch.object(oauth_client, 'execute_sql') as mock_execute:
            
            mock_execute.side_effect = SQLExecutionError("Connection failed")
            
            result = await oauth_client.test_connection()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_current_token_info(self, oauth_client):
        """Test getting current token information."""
        oauth_client._service_principal_creds = ServicePrincipalCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-secret")
        )
        oauth_client._warehouse_id = "test-warehouse-id"
        oauth_client._workspace_client = Mock()
        
        token_info = await oauth_client.get_current_token_info()
        
        assert token_info is not None
        assert token_info["client_id"] == "test-client-id"
        assert token_info["tenant_id"] == "test-tenant-id"
        assert token_info["warehouse_id"] == "test-warehouse-id"
        assert "client_secret" not in token_info  # Should not expose secret


@pytest.mark.integration
class TestDatabricksOAuthIntegration:
    """Integration tests for Databricks OAuth client (requires actual Databricks access)."""
    
    @pytest.mark.asyncio
    async def test_real_databricks_oauth_connection(self):
        """Test connection to real Databricks with OAuth (requires environment setup)."""
        import os
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        # This test requires actual service principal and Databricks access
        key_vault_settings = KeyVaultSettings(
            key_vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
            azure_tenant_id=os.getenv("AZURE_TENANT_ID"),
            azure_client_id=os.getenv("AZURE_CLIENT_ID"),
            azure_client_secret=SecretStr(os.getenv("AZURE_CLIENT_SECRET"))
        )
        
        databricks_settings = DatabricksOAuthSettings(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
            http_path=os.getenv("DATABRICKS_HTTP_PATH"),
            catalog=os.getenv("DATABRICKS_CATALOG"),
            schema_name=os.getenv("DATABRICKS_SCHEMA")
        )
        
        async with AzureKeyVaultClient(key_vault_settings) as key_vault_client:
            async with DatabricksOAuthClient(databricks_settings, key_vault_client) as oauth_client:
                # Test connection
                connection_result = await oauth_client.test_connection()
                assert connection_result is True
                
                # Test SQL execution
                result = await oauth_client.execute_sql("SELECT 'OAuth test' as message")
                assert result.row_count == 1
                assert result.rows[0]["message"] == "OAuth test"
                
                # Test token info retrieval
                token_info = await oauth_client.get_current_token_info()
                assert token_info is not None
                assert "client_id" in token_info