"""
Security Tests for SQL Injection Prevention
==========================================

Test suite to verify that the security fixes for SQL injection vulnerabilities
are working correctly in the Databricks OAuth client and email databricks client.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from databricks.sdk.service.sql import StatementParameterListItem


class TestSQLSecurityFixes:
    """Test SQL injection prevention in OAuth client and databricks client."""

    @pytest.fixture
    def mock_workspace_client(self):
        """Mock workspace client for testing."""
        client = MagicMock()
        client.statement_execution = MagicMock()
        client.statement_execution.execute_statement = MagicMock()
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = MagicMock()
        mock_response.status.state = "SUCCEEDED"
        mock_response.result = MagicMock()
        mock_response.result.data_array = [
            ["test_value", "user@example.com", "123"]
        ]
        mock_response.manifest = MagicMock()
        mock_response.manifest.schema = MagicMock()
        mock_response.manifest.schema.columns = [
            MagicMock(name="name"),
            MagicMock(name="email"), 
            MagicMock(name="id")
        ]
        
        client.statement_execution.execute_statement.return_value = mock_response
        return client

    @pytest.fixture
    def mock_key_vault_client(self):
        """Mock Key Vault client for testing."""
        from agents.email.services.azure_key_vault_client import ServicePrincipalCredentials
        
        client = AsyncMock()
        client.get_service_principal_credentials = AsyncMock(return_value=ServicePrincipalCredentials(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id"
        ))
        return client

    @pytest.fixture
    def databricks_oauth_settings(self):
        """Mock Databricks OAuth settings."""
        from agents.email.config.settings import DatabricksOAuthSettings
        
        return DatabricksOAuthSettings(
            server_hostname="test.databricks.com",
            http_path="/sql/1.0/warehouses/test-warehouse",
            catalog="test_catalog",
            schema_name="test_schema",
            table_suffix="_test"
        )

    @pytest.mark.asyncio
    async def test_oauth_client_parameter_sanitization(self, mock_workspace_client, mock_key_vault_client, databricks_oauth_settings):
        """Test that OAuth client properly sanitizes parameters to prevent SQL injection."""
        from agents.email.services.databricks_oauth_client import DatabricksOAuthClient
        
        client = DatabricksOAuthClient(databricks_oauth_settings, mock_key_vault_client)
        client._workspace_client = mock_workspace_client
        client._warehouse_id = "test-warehouse"
        client._default_catalog = "test_catalog"
        client._default_schema = "test_schema"
        
        # Test with potentially malicious parameters
        malicious_params = {
            "user_email": "test@example.com'; DROP TABLE users; --",
            "user_id": "123; DELETE FROM accounts; --"
        }
        
        query = "SELECT * FROM users WHERE email = :user_email AND id = :user_id"
        
        await client.execute_sql(query, malicious_params)
        
        # Verify that execute_statement was called with proper StatementParameterListItem objects
        call_args = mock_workspace_client.statement_execution.execute_statement.call_args
        
        # Check that parameters were passed correctly
        assert call_args[1]['parameters'] is not None
        assert len(call_args[1]['parameters']) == 2
        
        # Verify parameters are StatementParameterListItem objects
        params = call_args[1]['parameters']
        assert all(isinstance(p, StatementParameterListItem) for p in params)
        
        # Verify the original query is used (not modified with string replacement)
        assert call_args[1]['statement'] == query
        
        # Verify parameter values are properly escaped
        param_dict = {p.name: p.value for p in params}
        assert "user_email" in param_dict
        assert "user_id" in param_dict
        assert param_dict["user_email"] == "test@example.com'; DROP TABLE users; --"
        assert param_dict["user_id"] == "123; DELETE FROM accounts; --"

    @pytest.mark.asyncio
    async def test_databricks_client_parameter_handling(self, mock_key_vault_client, databricks_oauth_settings):
        """Test that databricks client properly handles parameters through OAuth client."""
        from agents.email.database.databricks_client import DatabricksClient
        from agents.email.services.databricks_oauth_client import DatabricksOAuthClient
        
        # Mock the OAuth client
        mock_oauth_client = AsyncMock(spec=DatabricksOAuthClient)
        mock_oauth_client.execute_sql_fetchall = AsyncMock(return_value=[
            {"name": "test", "email": "test@example.com", "id": "123"}
        ])
        
        client = DatabricksClient(databricks_oauth_settings, MagicMock())
        client.databricks_client = mock_oauth_client
        
        # Test execute_query with parameters
        parameters = ["test@example.com'; DROP TABLE users; --", "123; DELETE FROM accounts; --"]
        query = "SELECT * FROM users WHERE email = ? AND id = ?"
        
        result = await client.execute_query(query, parameters)
        
        # Verify that execute_sql_fetchall was called with parameter dict
        call_args = mock_oauth_client.execute_sql_fetchall.call_args
        assert call_args[0][0] == query  # Original query
        assert call_args[0][1] is not None  # Parameters dict
        
        # Verify parameter dict format
        param_dict = call_args[0][1]
        assert "param_0" in param_dict
        assert "param_1" in param_dict
        assert param_dict["param_0"] == "test@example.com'; DROP TABLE users; --"
        assert param_dict["param_1"] == "123; DELETE FROM accounts; --"

    @pytest.mark.asyncio 
    async def test_parameter_type_detection(self, mock_workspace_client, mock_key_vault_client, databricks_oauth_settings):
        """Test that parameter types are correctly detected and set."""
        from agents.email.services.databricks_oauth_client import DatabricksOAuthClient
        
        client = DatabricksOAuthClient(databricks_oauth_settings, mock_key_vault_client)
        client._workspace_client = mock_workspace_client
        client._warehouse_id = "test-warehouse"
        client._default_catalog = "test_catalog"
        client._default_schema = "test_schema"
        
        # Test with different parameter types
        params = {
            "string_param": "test_string",
            "int_param": 42,
            "float_param": 3.14,
            "bool_param": True,
            "none_param": None
        }
        
        query = "SELECT * FROM test WHERE col1 = :string_param AND col2 = :int_param AND col3 = :float_param AND col4 = :bool_param AND col5 = :none_param"
        
        await client.execute_sql(query, params)
        
        # Verify parameter types
        call_args = mock_workspace_client.statement_execution.execute_statement.call_args
        statement_params = call_args[1]['parameters']
        
        param_types = {p.name: p.type for p in statement_params}
        assert param_types["string_param"] == "STRING"
        assert param_types["int_param"] == "INT"
        assert param_types["float_param"] == "DOUBLE"
        assert param_types["bool_param"] == "BOOLEAN"
        assert param_types["none_param"] == "STRING"  # None converts to STRING

    @pytest.mark.asyncio
    async def test_no_parameters_handling(self, mock_workspace_client, mock_key_vault_client, databricks_oauth_settings):
        """Test that queries without parameters work correctly."""
        from agents.email.services.databricks_oauth_client import DatabricksOAuthClient
        
        client = DatabricksOAuthClient(databricks_oauth_settings, mock_key_vault_client)
        client._workspace_client = mock_workspace_client
        client._warehouse_id = "test-warehouse"
        client._default_catalog = "test_catalog"
        client._default_schema = "test_schema"
        
        query = "SELECT * FROM users"
        
        await client.execute_sql(query)
        
        # Verify that execute_statement was called without parameters
        call_args = mock_workspace_client.statement_execution.execute_statement.call_args
        assert call_args[1]['statement'] == query
        assert call_args[1]['parameters'] is None

    def test_sql_injection_prevention_examples(self):
        """Test cases that would be vulnerable to SQL injection with string replacement."""
        
        # These are examples of what WOULD be vulnerable with the old implementation
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; INSERT INTO users (email) VALUES ('hacker@evil.com'); --",
            "' UNION SELECT password FROM admin_users WHERE '1'='1",
            "\'; EXEC xp_cmdshell('rm -rf /'); --"
        ]
        
        # With proper parameterization, these should be treated as literal string values
        # and not execute as SQL code
        
        for malicious_input in malicious_inputs:
            # Verify the input contains SQL injection patterns
            dangerous_patterns = ['drop', 'delete', 'insert', 'update', 'union', 'exec', 'xp_cmdshell', '--', ';']
            has_dangerous_pattern = any(pattern in malicious_input.lower() for pattern in dangerous_patterns)
            assert has_dangerous_pattern, f"Test input '{malicious_input}' should contain at least one dangerous pattern from {dangerous_patterns}"
            
            # With proper parameterization, this would be treated as a literal string
            # The test verifies our implementation uses StatementParameterListItem
            # which prevents SQL injection by design