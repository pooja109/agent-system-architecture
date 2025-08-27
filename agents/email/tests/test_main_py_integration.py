"""
Integration Tests for main.py Commands
=====================================

Comprehensive integration tests for all main.py command-line interface options.
These tests use real production workflows without mocks or stubs.

Test Configuration:
- Creates test tables with '_test' suffix in the configured catalog/schema
- Uses TEST_EMAIL_OVERRIDE from .env for email testing
- Prompts for cleanup of test resources after successful completion
"""

import asyncio
import pytest
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog
import aiohttp

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    run_continuous,
    process_once,
    send_test_email,
    setup_database,
    show_status,
    show_stats,
    create_health_check_server
)
from config.settings import get_settings, AppSettings
from services.databricks_connection_pool import initialize_connection_pool, shutdown_connection_pool
from database.databricks_client import DatabricksClient


class TestMainPyIntegration:
    """Integration tests for main.py command-line interface."""
    
    def __init__(self):
        """Initialize test suite."""
        self.logger = structlog.get_logger(__name__)
        self.settings: Optional[AppSettings] = None
        self.test_results: Dict[str, Any] = {}
        self.test_tables_created: List[str] = []
        self.original_table_suffix = None
    
    async def setup(self):
        """Setup test environment."""
        self.logger.info("Setting up main.py integration tests")
        
        # Get settings and modify for testing
        self.settings = await get_settings()
        
        # Store original table suffix and set test suffix
        self.original_table_suffix = self.settings.databricks_oauth.table_suffix
        # Create a copy of settings with modified table suffix
        # We can't modify the original because it's used by other functions
        
        # Set environment variable for test suffix to be picked up by get_settings calls
        os.environ["DATABRICKS_TABLE_SUFFIX"] = "_test"
        
        # Ensure test mode is enabled
        os.environ["TEST_MODE"] = "true"
        if not os.getenv("TEST_EMAIL_OVERRIDE"):
            os.environ["TEST_EMAIL_OVERRIDE"] = "jgroenlund@microsoft.com"
        
        self.logger.info(
            "Test environment configured",
            catalog=self.settings.databricks_oauth.catalog,
            schema=self.settings.databricks_oauth.schema_name,
            table_suffix="_test",
            test_email=os.getenv("TEST_EMAIL_OVERRIDE")
        )
    
    async def teardown(self):
        """Teardown test environment and cleanup resources."""
        self.logger.info("Starting test teardown")
        
        # Restore original environment variables
        if self.original_table_suffix is not None:
            os.environ["DATABRICKS_TABLE_SUFFIX"] = self.original_table_suffix
        
        # Prompt for test table cleanup if any were created
        if self.test_tables_created:
            await self._prompt_for_cleanup()
    
    async def _prompt_for_cleanup(self):
        """Prompt user to delete test tables."""
        print("\n" + "="*60)
        print("TEST CLEANUP")
        print("="*60)
        print(f"The following test tables were created:")
        for table in self.test_tables_created:
            print(f"  - {table}")
        
        print("\nDo you want to delete these test tables? (yes/no): ", end="", flush=True)
        
        # Get user input
        user_input = input().strip().lower()
        
        if user_input == 'yes':
            await self._cleanup_test_tables()
        else:
            print("Test tables retained for manual review.")
    
    async def _cleanup_test_tables(self):
        """Delete all test tables created during testing."""
        print("\nDeleting test tables...")
        
        try:
            # Get fresh settings with test configuration
            settings = await get_settings()
            
            # Initialize connection pool for cleanup
            await initialize_connection_pool(
                settings.databricks_oauth,
                settings.key_vault,
                settings.connection_pool
            )
            
            async with DatabricksClient() as db_client:
                for table_name in self.test_tables_created:
                    try:
                        # Drop table
                        await db_client.execute_update(f"DROP TABLE IF EXISTS {table_name}")
                        print(f"  ✓ Deleted {table_name}")
                    except Exception as e:
                        print(f"  ✗ Failed to delete {table_name}: {e}")
            
            await shutdown_connection_pool()
            print("\nTest cleanup completed.")
            
        except Exception as e:
            print(f"\nError during cleanup: {e}")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all main.py command integration tests."""
        self.logger.info("Starting main.py integration test suite")
        start_time = time.time()
        
        try:
            await self.setup()
            
            # Test 1: Setup Command (database tables)
            await self._test_setup_command()
            
            # Test 2: Status Command
            await self._test_status_command()
            
            # Test 3: Test Email Command
            await self._test_test_email_command()
            
            # Test 4: Process Command
            await self._test_process_command()
            
            # Test 5: Stats Command
            await self._test_stats_command()
            
            # Test 6: Run Command (with health endpoints)
            await self._test_run_command()
            
            total_time = time.time() - start_time
            
            self.test_results.update({
                "overall_status": "PASSED",
                "total_test_time_seconds": round(total_time, 2),
                "tests_completed": 6,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            self.logger.info(
                "Main.py integration test suite completed successfully",
                total_time=total_time,
                tests_passed=len([r for r in self.test_results.values() if isinstance(r, dict) and r.get("status") == "PASSED"])
            )
            
            return self.test_results
            
        except Exception as e:
            self.test_results.update({
                "overall_status": "FAILED",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            self.logger.error("Main.py integration test suite failed", error=str(e))
            raise
        finally:
            await self.teardown()
    
    async def _test_setup_command(self) -> None:
        """Test 'python main.py setup' command."""
        self.logger.info("Testing setup command")
        test_start = time.time()
        
        try:
            # Run setup_database to create test tables
            result = await setup_database()
            assert result is True, "Setup command failed"
            
            # Verify tables were created - get fresh settings with test configuration
            settings = await get_settings()
            await initialize_connection_pool(
                settings.databricks_oauth,
                settings.key_vault,
                settings.connection_pool
            )
            
            async with DatabricksClient() as db_client:
                # Check email_communication_pipeline_test table
                table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.email_communication_pipeline_test"
                check_query = f"DESCRIBE TABLE {table_name}"
                
                try:
                    result = await db_client.execute_query(check_query)
                    assert len(result) > 0, "Table structure not found"
                    self.test_tables_created.append(table_name)
                    
                    # Verify expected columns exist
                    columns = {row["col_name"] for row in result}
                    expected_columns = {"batch_id", "customer_id", "run_date", "status", "is_email_sent"}
                    assert expected_columns.issubset(columns), f"Missing columns: {expected_columns - columns}"
                    
                except Exception as e:
                    assert False, f"Failed to verify table creation: {e}"
            
            await shutdown_connection_pool()
            
            test_time = time.time() - test_start
            self.test_results["setup_command"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "tables_created": self.test_tables_created,
                "table_verification": True
            }
            
        except Exception as e:
            self.test_results["setup_command"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_status_command(self) -> None:
        """Test 'python main.py status' command."""
        self.logger.info("Testing status command")
        test_start = time.time()
        
        try:
            # Run show_status
            result = await show_status()
            assert result is True, "Status command failed"
            
            # Status command should validate configuration and test connections
            # The function returns True if all checks pass
            
            test_time = time.time() - test_start
            self.test_results["status_command"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "configuration_valid": True,
                "connections_tested": True
            }
            
        except Exception as e:
            self.test_results["status_command"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_test_email_command(self) -> None:
        """Test 'python main.py test <email>' command."""
        self.logger.info("Testing test email command")
        test_start = time.time()
        
        try:
            # Use TEST_EMAIL_OVERRIDE from environment
            test_email = os.getenv("TEST_EMAIL_OVERRIDE", "jgroenlund@microsoft.com")
            
            # Run send_test_email
            result = await send_test_email(test_email)
            assert result is True, "Test email command failed"
            
            test_time = time.time() - test_start
            self.test_results["test_email_command"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "test_email_sent_to": test_email,
                "email_sent_successfully": True
            }
            
        except Exception as e:
            self.test_results["test_email_command"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_process_command(self) -> None:
        """Test 'python main.py process' command."""
        self.logger.info("Testing process command")
        test_start = time.time()
        
        try:
            # First, insert a test record to process
            await self._insert_test_record()
            
            # Run process_once
            result = await process_once()
            assert result is True, "Process command failed"
            
            # Verify the test record was processed
            processed = await self._verify_test_record_processed()
            assert processed is True, "Test record was not processed"
            
            test_time = time.time() - test_start
            self.test_results["process_command"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "test_record_inserted": True,
                "test_record_processed": True,
                "email_processing_completed": True
            }
            
        except Exception as e:
            self.test_results["process_command"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_stats_command(self) -> None:
        """Test 'python main.py stats' command."""
        self.logger.info("Testing stats command")
        test_start = time.time()
        
        try:
            # Run show_stats with default 7 days
            result = await show_stats(days=7)
            assert result is True, "Stats command failed"
            
            # Also test with custom days parameter
            result_30 = await show_stats(days=30)
            assert result_30 is True, "Stats command with 30 days failed"
            
            test_time = time.time() - test_start
            self.test_results["stats_command"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "stats_7_days": True,
                "stats_30_days": True
            }
            
        except Exception as e:
            self.test_results["stats_command"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            raise
    
    async def _test_run_command(self) -> None:
        """Test 'python main.py run' command with health endpoints."""
        self.logger.info("Testing run command with health endpoints")
        test_start = time.time()
        
        try:
            # Create health check server
            health_port = 8081
            health_app = await create_health_check_server(health_port)
            
            # Start the server
            runner = aiohttp.web.AppRunner(health_app)
            await runner.setup()
            site = aiohttp.web.TCPSite(runner, "0.0.0.0", health_port)
            await site.start()
            
            # Test health endpoints
            async with aiohttp.ClientSession() as session:
                # Test /health endpoint
                async with session.get(f"http://localhost:{health_port}/health") as resp:
                    assert resp.status in [200, 503], f"Unexpected health status: {resp.status}"
                    health_data = await resp.json()
                    assert "status" in health_data, "Health response missing status"
                
                # Test /health/detailed endpoint
                async with session.get(f"http://localhost:{health_port}/health/detailed") as resp:
                    assert resp.status in [200, 503], f"Unexpected detailed health status: {resp.status}"
                    detailed_data = await resp.json()
                    assert "overall_status" in detailed_data, "Detailed health missing overall_status"
                
                # Test /ready endpoint
                async with session.get(f"http://localhost:{health_port}/ready") as resp:
                    assert resp.status in [200, 503], f"Unexpected readiness status: {resp.status}"
                    ready_data = await resp.json()
                    assert "ready" in ready_data, "Readiness response missing ready field"
                
                # Test root endpoint
                async with session.get(f"http://localhost:{health_port}/") as resp:
                    assert resp.status == 200, f"Root endpoint failed: {resp.status}"
                    root_data = await resp.json()
                    assert root_data["service"] == "email", "Service name incorrect"
                    assert "endpoints" in root_data, "Root response missing endpoints"
            
            # Cleanup
            await runner.cleanup()
            
            test_time = time.time() - test_start
            self.test_results["run_command"] = {
                "status": "PASSED",
                "test_time_seconds": round(test_time, 2),
                "health_endpoint_tested": True,
                "detailed_health_tested": True,
                "readiness_probe_tested": True,
                "root_endpoint_tested": True,
                "health_check_port": health_port
            }
            
        except Exception as e:
            self.test_results["run_command"] = {
                "status": "FAILED",
                "error": str(e),
                "test_time_seconds": round(time.time() - test_start, 2)
            }
            # Ensure cleanup on failure
            try:
                await runner.cleanup()
            except:
                pass
            raise
    
    async def _insert_test_record(self) -> None:
        """Insert a test record for processing."""
        # Get fresh settings with test configuration
        settings = await get_settings()
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            settings.connection_pool
        )
        
        try:
            async with DatabricksClient() as db_client:
                table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.email_communication_pipeline_test"
                
                # Insert test record
                insert_query = f"""
                INSERT INTO {table_name} 
                (batch_id, run_date, agent_name, status, customer_id, 
                 input_file, output_file, is_email_sent, send_status, created_at, updated_at)
                VALUES 
                (9999, '2025-08-05', 'communication', 'S', 'TEST_CUSTOMER_001',
                 '20250805/TEST_CUSTOMER_001/communication_output/TEST_CUSTOMER_001_research_output.json',
                 '20250805/TEST_CUSTOMER_001/communication_output/TEST_CUSTOMER_001_email.html',
                 false, 'pending', current_timestamp(), current_timestamp())
                """
                
                await db_client.execute_update(insert_query)
                self.logger.info("Test record inserted successfully")
                
        finally:
            await shutdown_connection_pool()
    
    async def _verify_test_record_processed(self) -> bool:
        """Verify the test record was processed."""
        # Get fresh settings with test configuration
        settings = await get_settings()
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            settings.connection_pool
        )
        
        try:
            async with DatabricksClient() as db_client:
                table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.email_communication_pipeline_test"
                
                # Check if record was processed
                check_query = f"""
                SELECT is_email_sent, send_status 
                FROM {table_name}
                WHERE customer_id = 'TEST_CUSTOMER_001' 
                AND batch_id = 9999
                """
                
                result = await db_client.execute_query(check_query)
                if len(result) > 0:
                    row = result[0]
                    # Record is considered processed if is_email_sent is true or send_status is not 'pending'
                    return row["is_email_sent"] or row["send_status"] != "pending"
                
                return False
                
        finally:
            await shutdown_connection_pool()
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        passed_tests = len([r for r in self.test_results.values() if isinstance(r, dict) and r.get("status") == "PASSED"])
        total_tests = len([k for k in self.test_results.keys() if k not in ["overall_status", "total_test_time_seconds", "tests_completed", "timestamp"]])
        
        return {
            "test_results_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "total_test_time": self.test_results.get("total_test_time_seconds", 0),
                "overall_status": self.test_results.get("overall_status", "UNKNOWN")
            },
            "test_details": {k: v for k, v in self.test_results.items() if isinstance(v, dict) and "status" in v}
        }


# Pytest integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration tests require RUN_INTEGRATION_TESTS=true"
)
class TestMainPyCommands:
    """Pytest wrapper for main.py integration tests."""
    
    @pytest.mark.asyncio
    async def test_complete_main_py_suite(self):
        """Test complete main.py command suite."""
        test_suite = TestMainPyIntegration()
        results = await test_suite.run_all_tests()
        
        assert results["overall_status"] == "PASSED", f"Test suite failed: {results.get('error', 'Unknown error')}"
        assert results["tests_completed"] == 6, f"Expected 6 tests, got {results['tests_completed']}"
        
        # Get and display test summary
        summary = test_suite.get_test_summary()
        print(f"\nTest Summary:")
        print(f"  Total Tests: {summary['test_results_summary']['total_tests']}")
        print(f"  Passed: {summary['test_results_summary']['passed_tests']}")
        print(f"  Failed: {summary['test_results_summary']['failed_tests']}")
        print(f"  Total Time: {summary['test_results_summary']['total_test_time']}s")
        
        # Display individual test results
        print(f"\nIndividual Test Results:")
        for test_name, test_result in summary['test_details'].items():
            status = "✓" if test_result["status"] == "PASSED" else "✗"
            print(f"  {status} {test_name}: {test_result['test_time_seconds']}s")
    
    @pytest.mark.asyncio
    async def test_setup_command_only(self):
        """Test only setup command for focused testing."""
        test_suite = TestMainPyIntegration()
        await test_suite.setup()
        
        try:
            await test_suite._test_setup_command()
            assert test_suite.test_results["setup_command"]["status"] == "PASSED"
        finally:
            await test_suite.teardown()
    
    @pytest.mark.asyncio
    async def test_health_endpoints_only(self):
        """Test only health endpoints for focused testing."""
        test_suite = TestMainPyIntegration()
        await test_suite.setup()
        
        try:
            await test_suite._test_run_command()
            assert test_suite.test_results["run_command"]["status"] == "PASSED"
        finally:
            await test_suite.teardown()


if __name__ == "__main__":
    async def main():
        """Run the complete test suite when executed directly."""
        print("="*60)
        print("MAIN.PY INTEGRATION TEST SUITE")
        print("="*60)
        print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        test_suite = TestMainPyIntegration()
        try:
            results = await test_suite.run_all_tests()
            summary = test_suite.get_test_summary()
            
            print(f"\nTest Results:")
            print(f"Overall Status: {results['overall_status']}")
            print(f"Tests Completed: {results['tests_completed']}")
            print(f"Total Time: {results['total_test_time_seconds']}s")
            
            print(f"\nDetailed Results:")
            for test_name, test_result in summary['test_details'].items():
                status = "PASS" if test_result["status"] == "PASSED" else "FAIL"
                print(f"  [{status}] {test_name}: {test_result['test_time_seconds']}s")
                if test_result["status"] == "FAILED":
                    print(f"        Error: {test_result.get('error', 'Unknown error')}")
            
            return 0 if results['overall_status'] == "PASSED" else 1
            
        except Exception as e:
            print(f"\nTest suite failed with error: {e}")
            return 1
    
    import sys
    sys.exit(asyncio.run(main()))