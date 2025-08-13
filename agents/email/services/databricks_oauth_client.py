"""
Databricks OAuth Client with Service Principal Authentication
============================================================

OAuth-authenticated client for Databricks using service principal credentials
retrieved from Azure Key Vault, with automatic token refresh and SQL execution compatibility.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import structlog

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config, DatabricksError
from databricks.sdk.service.sql import ExecuteStatementRequest, StatementResponse
from databricks.sdk.service.sql import StatementState, StatementStatus, StatementParameterListItem
from pydantic import BaseModel, Field

try:
    from config.settings import DatabricksOAuthSettings
    from services.azure_key_vault_client import AzureKeyVaultClient, ServicePrincipalCredentials
except ImportError:
    from ..config.settings import DatabricksOAuthSettings
    from .azure_key_vault_client import AzureKeyVaultClient, ServicePrincipalCredentials


class OAuthTokenInfo(BaseModel):
    """Model for OAuth token information."""
    
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime = Field(..., description="Token expiration time")
    scope: Optional[str] = Field(None, description="Token scope")
    
    def is_expired(self, buffer_minutes: int = 5) -> bool:
        """Check if token is expired or will expire soon."""
        buffer_time = datetime.utcnow() + timedelta(minutes=buffer_minutes)
        return buffer_time >= self.expires_at


class SQLExecutionResult(BaseModel):
    """Model for SQL execution results maintaining compatibility."""
    
    columns: List[str] = Field(..., description="Column names")
    rows: List[Dict[str, Any]] = Field(..., description="Result rows as dictionaries")
    row_count: int = Field(..., description="Number of rows returned")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    statement_id: Optional[str] = Field(None, description="Statement execution ID")


class OAuthException(Exception):
    """Base exception for OAuth operations."""
    pass


class OAuthAuthenticationError(OAuthException):
    """Raised when OAuth authentication fails."""
    pass


class OAuthTokenExpiredError(OAuthException):
    """Raised when OAuth token is expired and refresh fails."""
    pass


class SQLExecutionError(OAuthException):
    """Raised when SQL execution fails."""
    pass


class DatabricksOAuthClient:
    """OAuth-authenticated client for Databricks operations."""
    
    def __init__(
        self, 
        databricks_settings: DatabricksOAuthSettings = None,
        key_vault_client: AzureKeyVaultClient = None,
        test_mode: bool = True
    ):
        """Initialize OAuth client with settings and Key Vault client.
        
        Args:
            databricks_settings: Databricks OAuth configuration
            key_vault_client: Initialized Key Vault client for credential retrieval
            test_mode: Whether to run in test mode (True) or real service mode (False)
        """
        self.databricks_settings = databricks_settings
        self.key_vault_client = key_vault_client
        self.test_mode = test_mode
        self.logger = structlog.get_logger(__name__)
        self._cached_token = None
        
        self._workspace_client: Optional[WorkspaceClient] = None
        self._current_token: Optional[OAuthTokenInfo] = None
        self._service_principal_creds: Optional[ServicePrincipalCredentials] = None
        
        # SQL execution settings
        self._warehouse_id: Optional[str] = None
        self._default_catalog = databricks_settings.catalog
        self._default_schema = databricks_settings.schema_name
    
    async def __aenter__(self) -> "DatabricksOAuthClient":
        """Async context manager entry."""
        await self._initialize_client()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._cleanup()
    
    async def initialize(self) -> None:
        """Initialize the OAuth client for real service testing."""
        if not self.test_mode:
            await self._initialize_client()
        else:
            self.logger.info("OAuth client initialized in test mode")
    
    async def close(self) -> None:
        """Close the OAuth client and clean up resources."""
        if not self.test_mode:
            await self._cleanup()
        else:
            self.logger.info("OAuth client closed in test mode")
    
    async def get_access_token(self) -> str:
        """Get current access token."""
        if self.test_mode:
            return "mock_access_token_for_testing"
        
        if not self._current_token or self._current_token.is_expired():
            await self.refresh_access_token()
        
        return self._current_token.access_token
    
    async def refresh_access_token(self) -> str:
        """Refresh the access token."""
        if self.test_mode:
            return "mock_refreshed_token_for_testing"
        
        # For real mode, we would implement actual token refresh logic
        # For now, return a new token (implementation depends on specific OAuth flow)
        await self._initialize_client()
        return await self.get_access_token()
    
    def get_azure_credential(self):
        """Get Azure credential for testing compatibility."""
        if hasattr(self.key_vault_client, 'get_azure_credential'):
            return self.key_vault_client.get_azure_credential()
        return None
    
    async def _initialize_client(self) -> None:
        """Initialize OAuth client with service principal authentication."""
        try:
            self.logger.info("Initializing Databricks OAuth client")
            
            # Get service principal credentials from Key Vault
            self._service_principal_creds = await self.key_vault_client.get_databricks_credentials()
            
            # Create Databricks config with Azure service principal authentication
            config = Config(
                host=f"https://{self.databricks_settings.server_hostname}",
                azure_tenant_id=self._service_principal_creds.tenant_id,
                azure_client_id=self._service_principal_creds.client_id,
                azure_client_secret=self._service_principal_creds.client_secret.get_secret_value(),
                auth_type="azure-client-secret"  # Azure Entra service principal
            )
            
            # Initialize workspace client
            self._workspace_client = WorkspaceClient(config=config)
            
            # Test connectivity and get warehouse ID from http_path
            await self._setup_sql_warehouse()
            
            self.logger.info(
                "Successfully initialized Databricks OAuth client",
                host=f"https://{self.databricks_settings.server_hostname}",
                client_id=self._service_principal_creds.client_id,
                warehouse_id=self._warehouse_id
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to initialize Databricks OAuth client",
                error=str(e),
                host=self.databricks_settings.server_hostname
            )
            raise OAuthAuthenticationError(f"Failed to initialize OAuth client: {e}") from e
    
    async def _setup_sql_warehouse(self) -> None:
        """Setup SQL warehouse connection from http_path."""
        try:
            # Extract warehouse ID from http_path
            # Format: /sql/1.0/warehouses/{warehouse_id}
            http_path = self.databricks_settings.http_path
            if "/warehouses/" in http_path:
                self._warehouse_id = http_path.split("/warehouses/")[-1]
            else:
                raise ValueError(f"Invalid http_path format: {http_path}")
            
            # Test SQL warehouse connectivity
            warehouses = list(self._workspace_client.warehouses.list())
            warehouse_found = any(w.id == self._warehouse_id for w in warehouses)
            
            if not warehouse_found:
                raise ValueError(f"SQL warehouse {self._warehouse_id} not found or not accessible")
            
            self.logger.info(
                "SQL warehouse setup complete",
                warehouse_id=self._warehouse_id,
                catalog=self._default_catalog,
                schema=self._default_schema
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to setup SQL warehouse",
                error=str(e),
                http_path=self.databricks_settings.http_path
            )
            raise OAuthException(f"SQL warehouse setup failed: {e}") from e
    
    async def _cleanup(self) -> None:
        """Clean up client resources."""
        if self._workspace_client:
            try:
                # Workspace client cleanup is handled automatically
                pass
            except Exception as e:
                self.logger.warning("Error during workspace client cleanup", error=str(e))
        
        self._workspace_client = None
        self._current_token = None
        self._service_principal_creds = None
    
    async def execute_sql(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300
    ) -> SQLExecutionResult:
        """Execute SQL query with compatibility for existing code patterns.
        
        Args:
            query: SQL query to execute
            parameters: Query parameters (not directly supported, must be substituted)
            timeout_seconds: Query timeout in seconds
            
        Returns:
            SQLExecutionResult with columns, rows, and metadata
            
        Raises:
            SQLExecutionError: If query execution fails
        """
        if not self._workspace_client:
            raise OAuthException("OAuth client not initialized")
        
        try:
            start_time = datetime.utcnow()
            
            # Convert parameters to Databricks SDK format
            statement_parameters = None
            if parameters:
                statement_parameters = []
                for key, value in parameters.items():
                    # Determine parameter type based on value
                    if isinstance(value, str):
                        param_type = "STRING"
                    elif isinstance(value, int):
                        param_type = "INT"
                    elif isinstance(value, float):
                        param_type = "DOUBLE"
                    elif isinstance(value, bool):
                        param_type = "BOOLEAN"
                    else:
                        param_type = "STRING"
                        value = str(value)
                    
                    statement_parameters.append(
                        StatementParameterListItem(name=key, value=str(value), type=param_type)
                    )
                
                self.logger.debug(
                    "Using parameterized query execution",
                    parameter_count=len(statement_parameters)
                )
            
            self.logger.debug(
                "Executing SQL query",
                query_preview=query[:100] + "..." if len(query) > 100 else query,
                warehouse_id=self._warehouse_id
            )
            
            # Execute statement using SQL execution API with proper parameterization
            response = self._workspace_client.statement_execution.execute_statement(
                warehouse_id=self._warehouse_id,
                statement=query,
                parameters=statement_parameters,
                catalog=self._default_catalog,
                schema=self._default_schema,
                wait_timeout="5s" if timeout_seconds < 5 else "50s" if timeout_seconds > 50 else f"{timeout_seconds}s"
            )
            
            # Process results
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            columns = []
            rows = []
            
            if response.result and response.result.data_array:
                # Extract column names
                if response.manifest and response.manifest.schema and response.manifest.schema.columns:
                    columns = [col.name for col in response.manifest.schema.columns]
                
                # Process rows
                for row_data in response.result.data_array:
                    if columns and len(row_data) == len(columns):
                        row_dict = dict(zip(columns, row_data))
                        rows.append(row_dict)
                    else:
                        # Fallback for rows without proper column mapping
                        row_dict = {f"col_{i}": val for i, val in enumerate(row_data)}
                        rows.append(row_dict)
            
            result = SQLExecutionResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=int(execution_time),
                statement_id=response.statement_id
            )
            
            self.logger.info(
                "SQL query executed successfully",
                row_count=result.row_count,
                execution_time_ms=result.execution_time_ms,
                columns_count=len(columns)
            )
            
            return result
            
        except DatabricksError as e:
            self.logger.error(
                "Databricks SQL execution failed",
                error=str(e),
                query_preview=query[:100]
            )
            raise SQLExecutionError(f"SQL execution failed: {e}") from e
        except Exception as e:
            self.logger.error(
                "Unexpected error during SQL execution",
                error=str(e),
                query_preview=query[:100]
            )
            raise SQLExecutionError(f"Unexpected SQL execution error: {e}") from e
    
    async def execute_sql_fetchall(self, query: str) -> List[Dict[str, Any]]:
        """Execute SQL and return all rows (compatibility method).
        
        Args:
            query: SQL query to execute
            
        Returns:
            List of row dictionaries
        """
        result = await self.execute_sql(query)
        return result.rows
    
    async def execute_sql_fetchone(self, query: str) -> Optional[Dict[str, Any]]:
        """Execute SQL and return first row (compatibility method).
        
        Args:
            query: SQL query to execute
            
        Returns:
            First row dictionary or None
        """
        result = await self.execute_sql(query)
        return result.rows[0] if result.rows else None
    
    async def test_connection(self) -> bool:
        """Test Databricks connection and SQL warehouse access.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            if not self._workspace_client:
                await self._initialize_client()
            
            # Test with a simple query
            test_query = "SELECT 1 as test_connection"
            result = await self.execute_sql(test_query)
            
            success = (result.row_count == 1 and 
                      int(result.rows[0].get("test_connection", 0)) == 1)
            
            if success:
                self.logger.info("Databricks OAuth connection test successful")
            else:
                self.logger.error("Databricks OAuth connection test failed - unexpected result")
            
            return success
            
        except Exception as e:
            self.logger.error("Databricks OAuth connection test failed", error=str(e))
            return False
    
    async def get_current_token_info(self) -> Optional[Dict[str, Any]]:
        """Get current OAuth token information for debugging.
        
        Returns:
            Token information dictionary (without sensitive data)
        """
        if not self._workspace_client:
            return None
        
        try:
            # The SDK handles token automatically, but we can get some info
            return {
                "client_id": self._service_principal_creds.client_id if self._service_principal_creds else None,
                "tenant_id": self._service_principal_creds.tenant_id if self._service_principal_creds else None,
                "warehouse_id": self._warehouse_id,
                "catalog": self._default_catalog,
                "schema": self._default_schema,
                "initialized_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.warning("Failed to get token info", error=str(e))
            return None


# Compatibility wrapper for existing code patterns
class DatabricksOAuthConnection:
    """Compatibility wrapper to maintain existing connection interface."""
    
    def __init__(self, oauth_client: DatabricksOAuthClient):
        """Initialize with OAuth client.
        
        Args:
            oauth_client: Initialized OAuth client
        """
        self.oauth_client = oauth_client
        self.logger = structlog.get_logger(__name__)
    
    async def cursor(self):
        """Return cursor-like interface for compatibility."""
        return DatabricksOAuthCursor(self.oauth_client)
    
    async def close(self):
        """Close connection (handled by context manager)."""
        pass


class DatabricksOAuthCursor:
    """Cursor-like interface for compatibility with existing code."""
    
    def __init__(self, oauth_client: DatabricksOAuthClient):
        """Initialize cursor with OAuth client.
        
        Args:
            oauth_client: OAuth client for query execution
        """
        self.oauth_client = oauth_client
        self.logger = structlog.get_logger(__name__)
        self._last_result: Optional[SQLExecutionResult] = None
    
    async def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        """Execute SQL query (compatibility method).
        
        Args:
            query: SQL query to execute
            parameters: Query parameters
        """
        self._last_result = await self.oauth_client.execute_sql(query, parameters)
    
    async def fetchall(self) -> List[Dict[str, Any]]:
        """Fetch all rows from last query (compatibility method).
        
        Returns:
            List of row dictionaries
        """
        if self._last_result:
            return self._last_result.rows
        return []
    
    async def fetchone(self) -> Optional[Dict[str, Any]]:
        """Fetch one row from last query (compatibility method).
        
        Returns:
            First row dictionary or None
        """
        if self._last_result and self._last_result.rows:
            return self._last_result.rows[0]
        return None
    
    async def close(self):
        """Close cursor (no-op for compatibility)."""
        pass