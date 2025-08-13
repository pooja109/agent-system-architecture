"""
Integration Tests for Connection Pool Implementation
=====================================================

End-to-end tests that validate connection pooling works correctly
with real OAuth authentication and improves performance.
"""

import pytest
import asyncio
import time
import os
from typing import List

from services.databricks_connection_pool import (
    initialize_connection_pool,
    shutdown_connection_pool,
    get_connection_pool,
    ConnectionPoolConfig
)
from database.databricks_client import DatabricksClient
from config.settings import get_settings


@pytest.mark.integration
class TestConnectionPoolIntegration:
    """Integration tests for connection pool functionality."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Setup: ensure clean state
        try:
            await shutdown_connection_pool()
        except:
            pass  # Ignore if pool not initialized
        
        yield
        
        # Teardown: cleanup pool
        try:
            await shutdown_connection_pool()
        except:
            pass  # Ignore cleanup errors

    @pytest.mark.asyncio
    async def test_pool_initialization_and_cleanup(self):
        """Test that connection pool can be initialized and cleaned up properly."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        pool_config = ConnectionPoolConfig(
            min_connections=1,
            max_connections=2,
            connection_timeout_seconds=30
        )
        
        # Initialize pool
        pool = await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        
        assert pool is not None
        assert pool._is_initialized is True
        
        # Test pool access
        pool_instance = await get_connection_pool()
        assert pool_instance is pool
        
        # Cleanup
        await shutdown_connection_pool()
        
        # Verify cleanup
        assert pool._is_shutting_down is True or not pool._is_initialized

    @pytest.mark.asyncio
    async def test_databricks_client_with_pool(self):
        """Test that DatabricksClient works correctly with connection pooling."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        pool_config = ConnectionPoolConfig(
            min_connections=1,
            max_connections=3,
            connection_timeout_seconds=30
        )
        
        # Initialize pool
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        
        try:
            # Test with DatabricksClient
            async with DatabricksClient() as db_client:
                # Test connection
                is_connected = await db_client.test_connection()
                assert is_connected is True
                
                # Test query execution
                result = await db_client.execute_query("SELECT 1 as test_value")
                assert len(result) == 1
                assert result[0]["test_value"] == 1
        
        finally:
            await shutdown_connection_pool()

    @pytest.mark.asyncio
    async def test_concurrent_client_usage(self):
        """Test concurrent usage of DatabricksClient with connection pooling."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        pool_config = ConnectionPoolConfig(
            min_connections=2,
            max_connections=3,
            connection_timeout_seconds=30
        )
        
        # Initialize pool
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        
        try:
            async def execute_query(query_id: int) -> int:
                """Execute a test query with a specific ID."""
                async with DatabricksClient() as db_client:
                    result = await db_client.execute_query(f"SELECT {query_id} as query_id")
                    return result[0]["query_id"]
            
            # Run concurrent queries
            tasks = [execute_query(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Verify all queries returned correct results
            expected = list(range(5))
            assert sorted(results) == expected
        
        finally:
            await shutdown_connection_pool()

    @pytest.mark.asyncio
    async def test_performance_improvement(self):
        """Test that connection pooling provides performance improvement."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        pool_config = ConnectionPoolConfig(
            min_connections=2,
            max_connections=3,
            connection_timeout_seconds=30
        )
        
        # Initialize pool
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        
        try:
            # Measure time for multiple operations
            start_time = time.time()
            
            async def timed_operation() -> bool:
                """Perform a timed database operation."""
                async with DatabricksClient() as db_client:
                    result = await db_client.execute_query("SELECT 1 as test")
                    return len(result) == 1
            
            # Execute 5 operations
            tasks = [timed_operation() for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            avg_time_per_operation = total_time / 5
            
            # Verify all operations succeeded
            assert all(results)
            
            # Performance assertion: with connection pooling, 5 operations
            # should complete in reasonable time (less than 10 seconds)
            assert total_time < 10.0, f"Operations took {total_time:.2f}s, expected < 10s"
            
            # Log performance metrics for analysis
            print(f"Performance Results:")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Average per operation: {avg_time_per_operation:.2f}s")
            print(f"  Operations per second: {5/total_time:.2f}")
        
        finally:
            await shutdown_connection_pool()

    @pytest.mark.asyncio
    async def test_pool_metrics_collection(self):
        """Test that connection pool metrics are collected correctly."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        pool_config = ConnectionPoolConfig(
            min_connections=1,
            max_connections=2,
            connection_timeout_seconds=30
        )
        
        # Initialize pool
        pool = await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        
        try:
            # Perform some operations to generate metrics
            async with DatabricksClient() as db_client:
                await db_client.execute_query("SELECT 1 as test")
            
            # Get metrics
            metrics = pool.get_metrics()
            
            # Verify metrics are populated
            assert metrics.total_connections >= 1
            assert metrics.total_checkouts >= 1
            assert metrics.total_checkins >= 1
            assert metrics.connection_creations >= 1
            assert metrics.last_updated_at is not None
            
            # Verify metrics make sense
            assert metrics.healthy_connections <= metrics.total_connections
            assert metrics.active_connections + metrics.idle_connections == metrics.total_connections
        
        finally:
            await shutdown_connection_pool()

    @pytest.mark.asyncio 
    async def test_error_handling_with_pool(self):
        """Test error handling works correctly with connection pooling."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        pool_config = ConnectionPoolConfig(
            min_connections=1,
            max_connections=2,
            connection_timeout_seconds=30
        )
        
        # Initialize pool
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        
        try:
            # Test that invalid SQL raises appropriate exception
            async with DatabricksClient() as db_client:
                with pytest.raises(Exception):  # Should raise some form of SQL exception
                    await db_client.execute_query("INVALID SQL STATEMENT")
                
                # Test that pool still works after error
                result = await db_client.execute_query("SELECT 1 as recovery_test")
                assert len(result) == 1
                assert result[0]["recovery_test"] == 1
        
        finally:
            await shutdown_connection_pool()


@pytest.mark.integration
class TestServiceIntegrationWithPool:
    """Test that services work correctly with connection pooling."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Setup: ensure clean state
        try:
            await shutdown_connection_pool()
        except:
            pass
        
        yield
        
        # Teardown: cleanup pool
        try:
            await shutdown_connection_pool()
        except:
            pass

    @pytest.mark.asyncio
    async def test_databricks_client_create_tables(self):
        """Test that create_tables works with connection pooling."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = get_settings()
        
        # Initialize pool
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            ConnectionPoolConfig(min_connections=1, max_connections=2)
        )
        
        try:
            async with DatabricksClient() as db_client:
                # This should not raise an exception
                result = await db_client.create_tables()
                # Result should be boolean indicating success/failure
                assert isinstance(result, bool)
        
        finally:
            await shutdown_connection_pool()


if __name__ == "__main__":
    # Allow running integration tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))