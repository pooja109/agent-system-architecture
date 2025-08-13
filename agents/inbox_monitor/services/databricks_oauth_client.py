"""
Databricks OAuth Client with Service Principal Authentication
============================================================

OAuth-authenticated client for Databricks using service principal credentials
retrieved from Azure Key Vault, with automatic token refresh and SQL execution compatibility.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
import structlog
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config, DatabricksError
from databricks.sdk.service.sql import ExecuteStatementRequest, StatementResponse
from databricks.sdk.service.sql import StatementState, StatementStatus, StatementParameterListItem, State
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
        buffer_time = datetime.now(timezone.utc) + timedelta(minutes=buffer_minutes)
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
            
            # Test SQL warehouse connectivity and check status
            warehouses = list(self._workspace_client.warehouses.list())
            target_warehouse = None
            for w in warehouses:
                if w.id == self._warehouse_id:
                    target_warehouse = w
                    break
            
            if not target_warehouse:
                available_ids = [w.id for w in warehouses]
                raise ValueError(
                    f"SQL warehouse {self._warehouse_id} not found or not accessible. "
                    f"Available warehouses: {available_ids}"
                )
            
            # Check warehouse state
            self.logger.info(
                "Found SQL warehouse",
                warehouse_id=self._warehouse_id,
                warehouse_name=getattr(target_warehouse, 'name', 'Unknown'),
                warehouse_state=getattr(target_warehouse, 'state', 'Unknown'),
                warehouse_size=getattr(target_warehouse, 'cluster_size', 'Unknown')
            )
            
            # Check if warehouse is running
            if hasattr(target_warehouse, 'state'):
                from databricks.sdk.service.sql import State
                if target_warehouse.state != State.RUNNING:
                    self.logger.warning(
                        "SQL warehouse is not in RUNNING state",
                        warehouse_id=self._warehouse_id,
                        current_state=target_warehouse.state,
                        message="Warehouse may need to be started before queries can execute"
                    )
            
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
    
    async def wait_for_warehouse_ready(
        self, 
        max_wait_minutes: int = 10, 
        check_interval_seconds: int = 30
    ) -> bool:
        """Wait for SQL warehouse to reach RUNNING state.
        
        Args:
            max_wait_minutes: Maximum time to wait in minutes
            check_interval_seconds: How often to check warehouse status
            
        Returns:
            True if warehouse is running, False if timeout
        """
        if not self._workspace_client or not self._warehouse_id:
            self.logger.error("Cannot check warehouse status - client not initialized")
            return False
        
        max_wait_seconds = max_wait_minutes * 60
        start_time = time.time()
        
        self.logger.info(
            "Waiting for warehouse to be ready",
            warehouse_id=self._warehouse_id,
            max_wait_minutes=max_wait_minutes,
            check_interval_seconds=check_interval_seconds
        )
        
        while time.time() - start_time < max_wait_seconds:
            try:
                # Get current warehouse status
                warehouse = self._workspace_client.warehouses.get(self._warehouse_id)
                
                if warehouse.state == State.RUNNING:
                    self.logger.info(
                        "Warehouse is now running and ready",
                        warehouse_id=self._warehouse_id,
                        wait_time_seconds=int(time.time() - start_time)
                    )
                    return True
                
                elif warehouse.state == State.STARTING:
                    self.logger.info(
                        "Warehouse is starting, continuing to wait",
                        warehouse_id=self._warehouse_id,
                        current_state=warehouse.state,
                        elapsed_seconds=int(time.time() - start_time),
                        remaining_seconds=int(max_wait_seconds - (time.time() - start_time))
                    )
                    
                elif warehouse.state == State.STOPPED:
                    self.logger.info(
                        "Warehouse is stopped, attempting to start",
                        warehouse_id=self._warehouse_id
                    )
                    
                    try:
                        self._workspace_client.warehouses.start(self._warehouse_id)
                        self.logger.info(
                            "Initiated warehouse startup",
                            warehouse_id=self._warehouse_id
                        )
                    except Exception as e:
                        self.logger.warning(
                            "Failed to start warehouse, continuing to wait",
                            warehouse_id=self._warehouse_id,
                            error=str(e)
                        )
                
                elif warehouse.state in [State.DELETING, State.DELETED]:
                    self.logger.error(
                        "Warehouse is being deleted or deleted",
                        warehouse_id=self._warehouse_id,
                        current_state=warehouse.state
                    )
                    return False
                
                else:
                    self.logger.warning(
                        "Warehouse in unexpected state",
                        warehouse_id=self._warehouse_id,
                        current_state=warehouse.state
                    )
                
                # Wait before next check
                await asyncio.sleep(check_interval_seconds)
                
            except Exception as e:
                self.logger.warning(
                    "Error checking warehouse status, retrying",
                    warehouse_id=self._warehouse_id,
                    error=str(e)
                )
                await asyncio.sleep(check_interval_seconds)
        
        self.logger.error(
            "Timeout waiting for warehouse to be ready",
            warehouse_id=self._warehouse_id,
            max_wait_minutes=max_wait_minutes,
            total_wait_seconds=int(time.time() - start_time)
        )
        return False
    
    async def _cleanup(self) -> None:
        """Clean up client resources."""
        if self._workspace_client:
            try:
                # Workspace client cleanup is handled automatically
                pass
            except Exception as e:
                self.logger.warning("Error during workspace client cleanup", extra={"error_message": str(e)})
        
        self._workspace_client = None
        self._current_token = None
        self._service_principal_creds = None
    
    async def execute_sql(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 600,  # Increased default from 300 to 600 seconds
        max_retries: int = 3,
        retry_backoff_base: float = 2.0
    ) -> SQLExecutionResult:
        """Execute SQL query with warehouse startup handling and exponential backoff.
        
        Args:
            query: SQL query to execute
            parameters: Query parameters (not directly supported, must be substituted)
            timeout_seconds: Query timeout in seconds (increased default to 600)
            max_retries: Maximum number of retry attempts for warehouse startup
            retry_backoff_base: Base for exponential backoff calculation
            
        Returns:
            SQLExecutionResult with columns, rows, and metadata
            
        Raises:
            SQLExecutionError: If query execution fails after all retries
        """
        if not self._workspace_client:
            raise OAuthException("OAuth client not initialized")
        
        # Implement retry logic with exponential backoff
        last_exception = None
        for attempt in range(max_retries + 1):  # +1 to include initial attempt
            try:
                start_time = datetime.now(timezone.utc)
                
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
                        parameter_count=len(statement_parameters),
                        attempt=attempt + 1
                    )
                
                self.logger.debug(
                    "Executing SQL query",
                    query_preview=query[:100] + "..." if len(query) > 100 else query,
                    warehouse_id=self._warehouse_id,
                    attempt=attempt + 1
                )
                
                # Execute statement using SQL execution API with proper parameterization
                # For warehouse startup scenarios, use longer wait timeout for first attempt
                base_wait_timeout = 50 if attempt == 0 else min(50, 30 + (attempt * 10))
                wait_timeout = f"{base_wait_timeout}s"
                    
                response = self._workspace_client.statement_execution.execute_statement(
                    warehouse_id=self._warehouse_id,
                    statement=query,
                    parameters=statement_parameters,
                    catalog=self._default_catalog,
                    schema=self._default_schema,
                    wait_timeout=wait_timeout
                )
                
                # If response comes back as PENDING, the warehouse might not be running
                # or the query is taking longer than wait_timeout to start
                if response.status and response.status.state == StatementState.PENDING:
                    if attempt < max_retries:
                        self.logger.warning(
                            "SQL execution pending - warehouse may be starting, will retry after waiting",
                            wait_timeout=wait_timeout,
                            query_preview=query[:100],
                            warehouse_id=self._warehouse_id,
                            attempt=attempt + 1,
                            max_retries=max_retries
                        )
                        
                        # Check if warehouse is starting and wait if needed
                        try:
                            warehouse_ready = await self.wait_for_warehouse_ready(
                                max_wait_minutes=5,  # Wait up to 5 minutes for warehouse
                                check_interval_seconds=15
                            )
                            if not warehouse_ready:
                                self.logger.warning(
                                    "Warehouse still not ready after wait, will retry with exponential backoff",
                                    warehouse_id=self._warehouse_id,
                                    attempt=attempt + 1
                                )
                        except Exception as wait_error:
                            self.logger.warning(
                                "Error while waiting for warehouse, proceeding with backoff retry",
                                error=str(wait_error),
                                attempt=attempt + 1
                            )
                        
                        # Store exception and continue to retry logic
                        last_exception = SQLExecutionError(
                            f"SQL execution timed out in PENDING state after {wait_timeout}. "
                            f"Warehouse {self._warehouse_id} may be starting."
                        )
                        continue
                        
                    else:
                        # Final attempt failed
                        self.logger.error(
                            "SQL execution failed after all retry attempts",
                            wait_timeout=wait_timeout,
                            query_preview=query[:100],
                            warehouse_id=self._warehouse_id,
                            total_attempts=attempt + 1
                        )
                        raise SQLExecutionError(
                            f"SQL execution timed out in PENDING state after {wait_timeout} "
                            f"and {max_retries} retry attempts. "
                            f"Check if warehouse {self._warehouse_id} is running and accessible."
                        )
                
                # Check for execution errors first
                if response.status and response.status.state:
                    state = response.status.state
                    if state == StatementState.FAILED:
                        error_msg = "SQL execution failed"
                        if response.status.error:
                            if hasattr(response.status.error, 'message'):
                                error_msg = f"{error_msg}: {response.status.error.message}"
                            elif hasattr(response.status.error, 'error_code'):
                                error_msg = f"{error_msg}: Error code {response.status.error.error_code}"
                            else:
                                error_msg = f"{error_msg}: {str(response.status.error)}"
                        
                        self.logger.error(
                            "SQL execution failed with error status",
                            state=state.value if hasattr(state, 'value') else str(state),
                            error=error_msg,
                            query_preview=query[:100],
                            attempt=attempt + 1
                        )
                        raise SQLExecutionError(error_msg)
                    
                    elif state == StatementState.CANCELED:
                        error_msg = "SQL execution was canceled"
                        self.logger.error("SQL execution canceled", extra={"query_preview": query[:100], "attempt": attempt + 1})
                        raise SQLExecutionError(error_msg)
                    
                    elif state == StatementState.CLOSED:
                        error_msg = "SQL execution was closed before completion"
                        self.logger.error("SQL execution closed", extra={"query_preview": query[:100], "attempt": attempt + 1})
                        raise SQLExecutionError(error_msg)
                    
                    elif state not in [StatementState.SUCCEEDED, StatementState.RUNNING]:
                        error_msg = f"SQL execution in unexpected state: {state}"
                        self.logger.error("SQL execution in unexpected state", extra={"state": str(state), "query_preview": query[:100], "attempt": attempt + 1})
                        raise SQLExecutionError(error_msg)
                
                # Process results - successful execution
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
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
                    columns_count=len(columns),
                    attempt=attempt + 1
                )
                
                return result
                
            except SQLExecutionError:
                # Re-raise SQL execution errors immediately (don't retry)
                raise
            except DatabricksError as e:
                error_msg = f"Databricks SQL execution failed: {e}"
                last_exception = SQLExecutionError(error_msg)
                
                if attempt < max_retries:
                    self.logger.warning(
                        "Databricks error occurred, will retry with exponential backoff",
                        error=str(e),
                        query_preview=query[:100],
                        attempt=attempt + 1,
                        max_retries=max_retries
                    )
                else:
                    self.logger.error(
                        "Databricks SQL execution failed after all attempts",
                        error=str(e),
                        query_preview=query[:100],
                        total_attempts=attempt + 1
                    )
                    raise last_exception from e
                    
            except Exception as e:
                error_msg = f"Unexpected SQL execution error: {e}"
                last_exception = SQLExecutionError(error_msg)
                
                if attempt < max_retries:
                    self.logger.warning(
                        "Unexpected error occurred, will retry with exponential backoff",
                        error=str(e),
                        query_preview=query[:100],
                        attempt=attempt + 1,
                        max_retries=max_retries
                    )
                else:
                    self.logger.error(
                        "Unexpected error during SQL execution after all attempts",
                        error=str(e),
                        query_preview=query[:100],
                        total_attempts=attempt + 1
                    )
                    raise last_exception from e
            
            # Exponential backoff before retry (skip on last attempt)
            if attempt < max_retries:
                backoff_seconds = min(300, retry_backoff_base ** attempt)  # Cap at 5 minutes
                self.logger.info(
                    "Waiting before retry with exponential backoff",
                    backoff_seconds=backoff_seconds,
                    attempt=attempt + 1,
                    max_retries=max_retries
                )
                await asyncio.sleep(backoff_seconds)
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise SQLExecutionError("SQL execution failed after all retry attempts")
    
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
            
            # Test with a simple query with longer timeout and more retries for connection test
            test_query = "SELECT 1 as test_connection"
            result = await self.execute_sql(
                test_query, 
                timeout_seconds=600,  # 10 minutes for initial connection test
                max_retries=5,  # More retries for connection tests
                retry_backoff_base=1.5  # Shorter backoff for testing
            )
            
            success = (result.row_count == 1 and 
                      int(result.rows[0].get("test_connection", 0)) == 1)
            
            if success:
                self.logger.info("Databricks OAuth connection test successful")
            else:
                self.logger.error("Databricks OAuth connection test failed - unexpected result")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Databricks OAuth connection test failed: {e}")
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
                "initialized_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            self.logger.warning("Failed to get token info", extra={"error_message": str(e)})
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