"""
Pooled Service Base Class
=========================

Base class for services that use connection pooling for Databricks operations.
Provides common patterns for connection management and error handling.
"""

import structlog
from typing import Any

try:
    from services.databricks_connection_pool import get_connection_pool, DatabricksConnectionPool
    from services.databricks_oauth_client import DatabricksOAuthClient
except ImportError:
    from .databricks_connection_pool import get_connection_pool, DatabricksConnectionPool
    from .databricks_oauth_client import DatabricksOAuthClient


class PooledServiceBase:
    """Base class for services using connection pooling."""
    
    def __init__(self):
        """Initialize pooled service base."""
        self.logger = structlog.get_logger(__name__)
        self._connection_pool: DatabricksConnectionPool | None = None
    
    async def __aenter__(self) -> "PooledServiceBase":
        """Async context manager entry."""
        # Connection pool should already be initialized globally
        self._connection_pool = await get_connection_pool()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        # Don't shutdown global pool, just release reference
        self._connection_pool = None
    
    async def execute_with_connection(self, operation_func, *args, **kwargs):
        """Execute operation with pooled connection.
        
        Args:
            operation_func: Async function that takes DatabricksOAuthClient as first parameter
            *args: Additional arguments for operation_func
            **kwargs: Additional keyword arguments for operation_func
            
        Returns:
            Result from operation_func
        """
        if not self._connection_pool:
            raise RuntimeError("Service not initialized - use async context manager")
        
        async with self._connection_pool.get_connection() as connection:
            return await operation_func(connection, *args, **kwargs)
    
    def get_connection(self):
        """Get connection context manager for direct database operations.
        
        Returns:
            Connection context manager that yields DatabricksOAuthClient
        """
        if not self._connection_pool:
            raise RuntimeError("Service not initialized - use async context manager or ensure connection pool is set")
        
        return self._connection_pool.get_connection()
    
    async def test_connection(self) -> bool:
        """Test connection pool connectivity.
        
        Returns:
            True if connection test successful, False otherwise
        """
        try:
            if not self._connection_pool:
                self._connection_pool = await get_connection_pool()
            
            async with self._connection_pool.get_connection() as connection:
                return await connection.test_connection()
                
        except Exception as e:
            self.logger.error("Connection test failed", error=str(e))
            return False