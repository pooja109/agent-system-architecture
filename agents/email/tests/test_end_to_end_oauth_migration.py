"""
End-to-End OAuth Migration Integration Tests
============================================

Comprehensive integration tests validating the complete OAuth migration
including Key Vault integration, connection pooling, and service operations.
"""

import asyncio
import pytest
import time
from datetime import datetime
from typing import Dict, List, Any
import structlog
import os

from services.databricks_connection_pool import (
    DatabricksConnectionPool,
    ConnectionPoolConfig,
    initialize_connection_pool,
    shutdown_connection_pool
)
from services.azure_key_vault_client import AzureKeyVaultClient
from database.databricks_client import DatabricksClient
from config.settings import get_settings


class EndToEndOAuthMigrationTest:
    """Comprehensive end-to-end testing for OAuth migration."""
    
    def __init__(self):
        """Initialize end-to-end test suite."""
        self.logger = structlog.get_logger(__name__)
        self.settings = get_settings()
        self.test_results: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, float] = {}
    
    async def run_complete_test_suite(self) -> Dict[str, Any]:
        """Run complete end-to-end test suite.
        
        Returns:
            Dictionary with comprehensive test results
        """
        self.logger.info("Starting comprehensive OAuth migration test suite")
        start_time = time.time()
        
        try:
            # Test 1: Key Vault Integration
            await self._test_key_vault_integration()
            
            # Test 2: OAuth Authentication Flow
            await self._test_oauth_authentication_flow()
            
            # Test 3: Connection Pool Operations
            await self._test_connection_pool_operations()
            
            # Test 4: Service Integration
            await self._test_service_integration()
            
            # Test 5: Concurrent Operations
            await self._test_concurrent_operations()
            
            # Test 6: Error Handling and Recovery
            await self._test_error_handling_recovery()
            
            # Test 7: Performance Validation
            await self._test_performance_characteristics()
            
            # Test 8: Resource Management
            await self._test_resource_management()
            
            total_time = time.time() - start_time
            
            self.test_results.update({
                "overall_status": "PASSED",
                "total_test_time_seconds": round(total_time, 2),
                "tests_completed": 8,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            self.logger.info(
                "OAuth migration test suite completed successfully",
                total_time=total_time,
                tests_passed=len([r for r in self.test_results.values() if r.get("status") == "PASSED"])
            )
            
            return self.test_results
            
        except Exception as e:
            self.test_results.update({
                "overall_status": "FAILED",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            self.logger.error("OAuth migration test suite failed", error=str(e))
            raise
    
    async def _test_key_vault_integration(self) -> None:
        """Test complete Key Vault integration functionality."""
        self.logger.info("Testing Key Vault integration")
        test_start = time.time()
        
        try:
            async with AzureKeyVaultClient(self.settings.key_vault) as kv_client:
                # Test connection
                connection_result = await kv_client.test_connection()
                assert connection_result, "Key Vault connection test failed"
                
                # Test credential retrieval
                credentials = await kv_client.get_databricks_credentials()
                assert credentials.tenant_id, "Tenant ID not retrieved"
                assert credentials.client_id, "Client ID not retrieved"
                assert credentials.client_secret.get_secret_value(), "Client secret not retrieved"
                
                # Test credential caching
                cached_credentials = await kv_client.get_databricks_credentials()
                assert cached_credentials.tenant_id == credentials.tenant_id, "Credential caching failed"
                
                # Test forced refresh
                fresh_credentials = await kv_client.get_databricks_credentials(force_refresh=True)
                assert fresh_credentials.client_id == credentials.client_id, "Forced refresh failed"
            
            test_time = time.time() - test_start
            self.test_results["key_vault_integration"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "connection_test": True,
                "credential_retrieval": True,
                "credential_caching": True,
                "forced_refresh": True
            }
            self.performance_metrics["key_vault_operation_time"] = test_time
            
        except Exception as e:
            self.test_results["key_vault_integration"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_oauth_authentication_flow(self) -> None:
        """Test OAuth authentication flow end-to-end."""
        self.logger.info("Testing OAuth authentication flow")
        test_start = time.time()
        
        try:
            async with AzureKeyVaultClient(self.settings.key_vault) as kv_client:
                from services.databricks_oauth_client import DatabricksOAuthClient
                
                async with DatabricksOAuthClient(self.settings.databricks, kv_client) as oauth_client:
                    # Test OAuth client initialization
                    token_info = await oauth_client.get_current_token_info()
                    assert token_info, "OAuth token info not available"
                    assert token_info["client_id"], "Client ID not in token info"
                    
                    # Test SQL execution with OAuth
                    result = await oauth_client.execute_sql("SELECT 'OAuth test' as message")
                    assert result.row_count == 1, "OAuth SQL execution failed"
                    assert result.rows[0]["message"] == "OAuth test", "OAuth SQL result incorrect"
                    
                    # Test connection health
                    health_result = await oauth_client.test_connection()
                    assert health_result, "OAuth connection health test failed"
                    
                    # Test multiple operations (token reuse)
                    for i in range(3):
                        result = await oauth_client.execute_sql(f"SELECT {i} as iteration")
                        assert result.rows[0]["iteration"] == i, f"OAuth operation {i} failed"
            
            test_time = time.time() - test_start
            self.test_results["oauth_authentication_flow"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "token_info_available": True,
                "sql_execution": True,
                "connection_health": True,
                "multiple_operations": True
            }
            self.performance_metrics["oauth_flow_time"] = test_time
            
        except Exception as e:
            self.test_results["oauth_authentication_flow"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_connection_pool_operations(self) -> None:
        """Test connection pool functionality comprehensively."""
        self.logger.info("Testing connection pool operations")
        test_start = time.time()
        
        try:
            # Initialize connection pool
            pool_config = ConnectionPoolConfig(
                min_connections=2,
                max_connections=4,
                connection_timeout_seconds=30
            )
            
            pool = await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                pool_config
            )
            
            # Test pool initialization
            assert pool._is_initialized, "Connection pool not initialized"
            assert len(pool._connections) >= 2, "Minimum connections not created"
            
            # Test connection acquisition and return
            async with pool.get_connection() as connection:
                result = await connection.test_connection()
                assert result, "Pooled connection test failed"
            
            # Test multiple concurrent acquisitions
            async def use_connection(conn_id):
                async with pool.get_connection() as connection:
                    result = await connection.execute_sql(f"SELECT {conn_id} as conn_id")
                    return result.rows[0]["conn_id"]
            
            # Test concurrent access
            tasks = [use_connection(i) for i in range(6)]  # More than max pool size
            results = await asyncio.gather(*tasks)
            assert results == list(range(6)), "Concurrent connection access failed"
            
            # Test pool metrics
            metrics = pool.get_metrics()
            assert metrics.total_connections >= 2, "Pool metrics incorrect"
            assert metrics.total_checkouts >= 7, "Checkout count incorrect"  # 1 + 6 concurrent
            
            # Test pool status
            status = pool.get_pool_status()
            assert status["is_initialized"], "Pool status incorrect"
            assert len(status["connection_details"]) >= 2, "Connection details missing"
            
            await pool.shutdown()
            
            test_time = time.time() - test_start
            self.test_results["connection_pool_operations"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "pool_initialization": True,
                "connection_acquisition": True,
                "concurrent_access": True,
                "pool_metrics": True,
                "pool_shutdown": True,
                "concurrent_operations_completed": 6
            }
            self.performance_metrics["connection_pool_time"] = test_time
            
        except Exception as e:
            self.test_results["connection_pool_operations"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            # Ensure cleanup
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _test_service_integration(self) -> None:
        """Test all services with connection pooling integration."""
        self.logger.info("Testing service integration with connection pooling")
        test_start = time.time()
        
        try:
            # Initialize connection pool for services
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                ConnectionPoolConfig()
            )
            
            # Test DatabricksClient with connection pooling
            async with DatabricksClient() as db_client:
                db_result = await db_client.test_connection()
                assert db_result, "DatabricksClient pooled connection failed"
                
                # Test service operations
                test_query = "SELECT 'email_agent_test' as test_message"
                query_result = await db_client.execute_sql(test_query)
                assert query_result.row_count == 1, "DatabricksClient query execution failed"
                assert query_result.rows[0]["test_message"] == "email_agent_test", "Query result incorrect"
            
            # Test service concurrent usage
            async def test_concurrent_service_usage():
                async with DatabricksClient() as service:
                    return await service.test_connection()
            
            # Run multiple services concurrently
            concurrent_tasks = [test_concurrent_service_usage() for _ in range(3)]
            concurrent_results = await asyncio.gather(*concurrent_tasks)
            assert all(concurrent_results), "Concurrent service usage failed"
            
            await shutdown_connection_pool()
            
            test_time = time.time() - test_start
            self.test_results["service_integration"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "databricks_client": True,
                "concurrent_service_usage": True,
                "services_tested": 1
            }
            self.performance_metrics["service_integration_time"] = test_time
            
        except Exception as e:
            self.test_results["service_integration"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            # Ensure cleanup
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _test_concurrent_operations(self) -> None:
        """Test concurrent operations under load."""
        self.logger.info("Testing concurrent operations under load")
        test_start = time.time()
        
        try:
            # Initialize connection pool with higher limits for concurrency testing
            pool_config = ConnectionPoolConfig(
                min_connections=3,
                max_connections=8,
                connection_timeout_seconds=30
            )
            
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                pool_config
            )
            
            # Test high concurrency operations
            async def concurrent_operation(operation_id: int):
                async with DatabricksClient() as service:
                    start_op = time.time()
                    result = await service.test_connection()
                    operation_time = time.time() - start_op
                    return {
                        "operation_id": operation_id,
                        "success": result,
                        "operation_time": operation_time
                    }
            
            # Run 15 concurrent operations (more than pool max)
            concurrency_level = 15
            tasks = [concurrent_operation(i) for i in range(concurrency_level)]
            
            concurrent_start = time.time()
            results = await asyncio.gather(*tasks)
            concurrent_time = time.time() - concurrent_start
            
            # Validate all operations succeeded
            successful_ops = [r for r in results if r["success"]]
            assert len(successful_ops) == concurrency_level, f"Only {len(successful_ops)}/{concurrency_level} operations succeeded"
            
            # Performance validation
            avg_operation_time = sum(r["operation_time"] for r in results) / len(results)
            assert avg_operation_time < 5.0, f"Average operation time {avg_operation_time}s too high"
            
            # Throughput validation
            throughput = concurrency_level / concurrent_time
            assert throughput > 3.0, f"Throughput {throughput} ops/sec too low"
            
            await shutdown_connection_pool()
            
            test_time = time.time() - test_start
            self.test_results["concurrent_operations"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "concurrency_level": concurrency_level,
                "successful_operations": len(successful_ops),
                "average_operation_time": round(avg_operation_time, 3),
                "throughput_ops_per_sec": round(throughput, 2),
                "total_concurrent_time": round(concurrent_time, 2)
            }
            self.performance_metrics["concurrent_operations_time"] = test_time
            self.performance_metrics["average_operation_time"] = avg_operation_time
            self.performance_metrics["throughput"] = throughput
            
        except Exception as e:
            self.test_results["concurrent_operations"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _test_error_handling_recovery(self) -> None:
        """Test error handling and recovery scenarios."""
        self.logger.info("Testing error handling and recovery scenarios")
        test_start = time.time()
        
        try:
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                ConnectionPoolConfig()
            )
            
            # Test 1: Invalid SQL execution
            async with DatabricksClient() as service:
                try:
                    # This should fail gracefully
                    await service.execute_sql("INVALID SQL STATEMENT")
                    assert False, "Invalid SQL should have failed"
                except Exception as e:
                    assert "INVALID" in str(e).upper() or "SYNTAX" in str(e).upper(), "Expected SQL syntax error"
            
            # Test 2: Service recovery after error
            async with DatabricksClient() as service:
                # Service should still work after the error
                result = await service.test_connection()
                assert result, "Service did not recover after error"
            
            # Test 3: Connection pool resilience
            from services.databricks_connection_pool import get_connection_pool
            pool = get_connection_pool()
            initial_metrics = pool.get_metrics()
            
            # Force some connection errors and verify pool recovery
            error_count = 0
            for _ in range(3):
                try:
                    async with pool.get_connection() as conn:
                        await conn.execute_sql("INVALID SQL")
                except Exception:
                    error_count += 1
            
            assert error_count == 3, "Expected 3 SQL errors"
            
            # Pool should still be functional
            async with pool.get_connection() as conn:
                result = await conn.test_connection()
                assert result, "Pool not functional after errors"
            
            final_metrics = pool.get_metrics()
            assert final_metrics.total_connections >= initial_metrics.total_connections, "Pool connections decreased"
            
            await shutdown_connection_pool()
            
            test_time = time.time() - test_start
            self.test_results["error_handling_recovery"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "invalid_sql_handled": True,
                "service_recovery": True,
                "pool_resilience": True,
                "errors_handled": error_count
            }
            self.performance_metrics["error_handling_time"] = test_time
            
        except Exception as e:
            self.test_results["error_handling_recovery"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _test_performance_characteristics(self) -> None:
        """Test performance characteristics and validate requirements."""
        self.logger.info("Testing performance characteristics")
        test_start = time.time()
        
        try:
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                ConnectionPoolConfig(min_connections=3, max_connections=6)
            )
            
            # Test 1: Connection acquisition time
            acquisition_times = []
            for _ in range(10):
                acq_start = time.time()
                from services.databricks_connection_pool import get_connection_pool
                pool = get_connection_pool()
                async with pool.get_connection() as conn:
                    acquisition_time = time.time() - acq_start
                    acquisition_times.append(acquisition_time)
                    await conn.test_connection()
            
            avg_acquisition_time = sum(acquisition_times) / len(acquisition_times)
            max_acquisition_time = max(acquisition_times)
            p95_acquisition_time = sorted(acquisition_times)[int(0.95 * len(acquisition_times))]
            
            # Validate performance requirements
            assert avg_acquisition_time < 0.5, f"Average acquisition time {avg_acquisition_time}s exceeds 500ms"
            assert p95_acquisition_time < 0.5, f"P95 acquisition time {p95_acquisition_time}s exceeds 500ms"
            
            # Test 2: Query execution performance
            query_times = []
            async with DatabricksClient() as service:
                for i in range(5):
                    query_start = time.time()
                    await service.test_connection()
                    query_time = time.time() - query_start
                    query_times.append(query_time)
            
            avg_query_time = sum(query_times) / len(query_times)
            assert avg_query_time < 2.0, f"Average query time {avg_query_time}s too high"
            
            # Test 3: Throughput under normal load
            throughput_start = time.time()
            throughput_tasks = []
            
            async def throughput_operation():
                async with DatabricksClient() as service:
                    return await service.test_connection()
            
            for _ in range(20):  # Normal load test
                throughput_tasks.append(throughput_operation())
            
            throughput_results = await asyncio.gather(*throughput_tasks)
            throughput_time = time.time() - throughput_start
            throughput = len(throughput_results) / throughput_time
            
            assert throughput > 5.0, f"Throughput {throughput} ops/sec below minimum 5 ops/sec"
            assert all(throughput_results), "Not all throughput operations succeeded"
            
            await shutdown_connection_pool()
            
            test_time = time.time() - test_start
            self.test_results["performance_characteristics"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "avg_acquisition_time_ms": round(avg_acquisition_time * 1000, 2),
                "max_acquisition_time_ms": round(max_acquisition_time * 1000, 2),
                "p95_acquisition_time_ms": round(p95_acquisition_time * 1000, 2),
                "avg_query_time_ms": round(avg_query_time * 1000, 2),
                "throughput_ops_per_sec": round(throughput, 2),
                "performance_requirements_met": True
            }
            self.performance_metrics["avg_acquisition_time"] = avg_acquisition_time
            self.performance_metrics["p95_acquisition_time"] = p95_acquisition_time
            self.performance_metrics["avg_query_time"] = avg_query_time
            self.performance_metrics["normal_load_throughput"] = throughput
            
        except Exception as e:
            self.test_results["performance_characteristics"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _test_resource_management(self) -> None:
        """Test resource management and cleanup."""
        self.logger.info("Testing resource management and cleanup")
        test_start = time.time()
        
        try:
            # Test 1: Connection pool lifecycle
            pool_config = ConnectionPoolConfig(min_connections=2, max_connections=4)
            pool = await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                pool_config
            )
            
            initial_connections = len(pool._connections)
            assert initial_connections >= 2, "Initial connections not created"
            
            # Use connections and verify they're returned to pool
            async with pool.get_connection() as conn1:
                async with pool.get_connection() as conn2:
                    active_connections = len([c for c in pool._connections if c.is_busy])
                    assert active_connections >= 2, "Connections not marked as active"
            
            # Connections should be returned to pool
            await asyncio.sleep(0.1)  # Brief wait for cleanup
            idle_connections = len([c for c in pool._connections if not c.is_busy])
            assert idle_connections >= 2, "Connections not returned to pool"
            
            # Test pool shutdown
            await pool.shutdown()
            assert not pool._is_initialized, "Pool not properly shut down"
            
            # Test 2: Service resource cleanup
            service_created = False
            async with DatabricksClient() as service:
                service_created = True
                await service.test_connection()
            
            assert service_created, "Service context manager failed"
            
            # Test 3: Key Vault client cleanup
            kv_created = False
            async with AzureKeyVaultClient(self.settings.key_vault) as kv_client:
                kv_created = True
                await kv_client.test_connection()
            
            assert kv_created, "Key Vault client context manager failed"
            
            test_time = time.time() - test_start
            self.test_results["resource_management"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "connection_pool_lifecycle": True,
                "connection_return_to_pool": True,
                "pool_shutdown": True,
                "service_cleanup": True,
                "key_vault_cleanup": True
            }
            self.performance_metrics["resource_management_time"] = test_time
            
        except Exception as e:
            self.test_results["resource_management"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics summary."""
        return {
            "performance_metrics": self.performance_metrics,
            "test_results_summary": {
                "total_tests": len([k for k in self.test_results.keys() if k not in ["overall_status", "total_test_time_seconds", "tests_completed", "timestamp"]]),
                "passed_tests": len([r for r in self.test_results.values() if isinstance(r, dict) and r.get("status") == "PASSED"]),
                "total_test_time": self.test_results.get("total_test_time_seconds", 0),
                "overall_status": self.test_results.get("overall_status", "UNKNOWN")
            }
        }


# Pytest integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration tests require RUN_INTEGRATION_TESTS=true"
)
class TestEndToEndOAuthMigration:
    """Pytest wrapper for end-to-end OAuth migration tests."""
    
    @pytest.mark.asyncio
    async def test_complete_oauth_migration_suite(self):
        """Test complete OAuth migration functionality."""
        test_suite = EndToEndOAuthMigrationTest()
        results = await test_suite.run_complete_test_suite()
        
        assert results["overall_status"] == "PASSED", f"Test suite failed: {results.get('error', 'Unknown error')}"
        assert results["tests_completed"] == 8, f"Expected 8 tests, got {results['tests_completed']}"
        
        # Performance validation
        performance_summary = test_suite.get_performance_summary()
        assert performance_summary["test_results_summary"]["passed_tests"] == 8, "Not all tests passed"
        
        # Log performance metrics for analysis
        print(f"\nPerformance Summary:")
        for metric, value in performance_summary["performance_metrics"].items():
            print(f"  {metric}: {value}")
    
    @pytest.mark.asyncio
    async def test_key_vault_integration_only(self):
        """Test only Key Vault integration for focused testing."""
        test_suite = EndToEndOAuthMigrationTest()
        await test_suite._test_key_vault_integration()
        
        assert test_suite.test_results["key_vault_integration"]["status"] == "PASSED"
    
    @pytest.mark.asyncio
    async def test_oauth_flow_only(self):
        """Test only OAuth authentication flow for focused testing."""
        test_suite = EndToEndOAuthMigrationTest()
        await test_suite._test_oauth_authentication_flow()
        
        assert test_suite.test_results["oauth_authentication_flow"]["status"] == "PASSED"
    
    @pytest.mark.asyncio
    async def test_connection_pool_only(self):
        """Test only connection pool operations for focused testing."""
        test_suite = EndToEndOAuthMigrationTest()
        await test_suite._test_connection_pool_operations()
        
        assert test_suite.test_results["connection_pool_operations"]["status"] == "PASSED"


if __name__ == "__main__":
    async def main():
        """Run the complete test suite when executed directly."""
        test_suite = EndToEndOAuthMigrationTest()
        try:
            results = await test_suite.run_complete_test_suite()
            print(f"\nTest Results:")
            print(f"Overall Status: {results['overall_status']}")
            print(f"Tests Completed: {results['tests_completed']}")
            print(f"Total Time: {results['total_test_time_seconds']}s")
            
            performance_summary = test_suite.get_performance_summary()
            print(f"\nPerformance Metrics:")
            for metric, value in performance_summary["performance_metrics"].items():
                print(f"  {metric}: {value}")
                
        except Exception as e:
            print(f"Test suite failed: {e}")
            return 1
        
        return 0
    
    import sys
    sys.exit(asyncio.run(main()))