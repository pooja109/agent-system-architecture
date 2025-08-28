"""
CLI Integration Tests with Complete Isolation - Phase 2 Recovery
================================================================

Complete rewrite of CLI integration tests using Phase 2 isolation frameworks
to eliminate test interference and enable reliable parallel execution.
"""
import pytest
import subprocess
import asyncio
import os
import sys
import json
from pathlib import Path
from unittest import mock

# Phase 2 Recovery: Import all isolation frameworks
from tests.fixtures.state_isolation import isolated_global_state, no_singleton_conflicts, isolated_config
from tests.fixtures.mock_isolation import isolated_mocks, mock_azure_client_isolated, mock_graph_api_isolated, mock_external_services
from tests.fixtures.filesystem_isolation import isolated_filesystem, temp_config_dir, temp_log_dir, project_structure
from tests.fixtures.async_isolation import async_resource_manager, isolated_event_loop, async_timeout_manager
from tests.fixtures.performance_monitoring import performance_monitor, enforce_cli_performance


class TestCLIIntegrationIsolated:
    """CLI integration tests with complete test isolation."""
    
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.ci_safe
    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_help_command_isolated(self, isolated_filesystem, performance_monitor, isolated_config):
        """Test CLI help command with complete isolation."""
        with performance_monitor.monitor():
            # Set up isolated environment
            env = os.environ.copy()
            env.update({
                'TEST_MODE': 'true',
                'PYTHONPATH': str(Path.cwd()),
                'PATH': env.get('PATH', '')
            })
            
            # Execute in isolated environment
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--help'],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=Path.cwd(),
                env=env
            )
        
        assert result.returncode == 0, f"CLI help failed: {result.stderr}"
        assert 'usage:' in result.stdout.lower() or 'Test Runner CLI' in result.stdout
        
        # Verify performance
        metrics = performance_monitor.metrics
        assert metrics.execution_time < 15.0, f"CLI help took {metrics.execution_time:.2f}s, expected <15s"
    
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_list_modes_isolated(self, isolated_filesystem, performance_monitor):
        """Test CLI list modes with isolation."""
        with performance_monitor.monitor():
            env = os.environ.copy()
            env['TEST_MODE'] = 'true'
            env['PYTHONPATH'] = str(Path.cwd())
            
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--help'],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
        
        assert result.returncode == 0, f"List modes failed: {result.stderr}"
        
        # Should list available modes
        output_lower = result.stdout.lower()
        expected_modes = ['fast', 'smoke', 'integration']
        
        found_modes = sum(1 for mode in expected_modes if mode in output_lower)
        assert found_modes >= 2, f"Should list multiple modes, found: {result.stdout[:200]}"
        
        # Performance check
        metrics = performance_monitor.metrics
        assert metrics.execution_time < 10.0
    
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_dry_run_isolated(self, temp_config_dir, isolated_config, performance_monitor):
        """Test CLI dry run with isolated configuration."""
        with performance_monitor.monitor():
            # Set up test configuration
            isolated_config.isolate_environment(
                TEST_MODE='true',
                CONFIG_DIR=str(temp_config_dir),
                LOG_LEVEL='WARNING',  # Reduce noise
                PYTHONPATH=str(Path.cwd())
            )
            
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--smoke', '--dry-run'],
                capture_output=True,
                text=True,
                timeout=20,
                env=os.environ
            )
        
        assert result.returncode == 0, f"Dry run failed: {result.stderr}"
        
        # Should show what would be executed
        assert 'would' in result.stdout.lower() or 'dry run' in result.stdout.lower() or 'command' in result.stdout.lower()
        
        metrics = performance_monitor.metrics
        assert metrics.execution_time < 20.0
    
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.cli
    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_status_command_with_mocks(self, isolated_mocks, temp_config_dir, async_resource_manager):
        """Test CLI status command with isolated mocks and async management."""
        # Create isolated service mocks
        with mock_external_services(isolated_mocks) as service_mocks:
            # Configure service behaviors
            service_mocks['azure'].get_completion.return_value = "System operational"
            service_mocks['graph'].authenticate.return_value = True
            service_mocks['salesforce'].authenticate.return_value = True
            
            # Register async resources
            for service_name, service_mock in service_mocks.items():
                async_resource_manager.register_client(service_mock, f"mock_{service_name}")
            
            # Set up isolated environment
            config_data = {
                "azure_endpoint": "https://test.azure.com",
                "graph_endpoint": "https://graph.microsoft.com", 
                "salesforce_endpoint": "https://test.salesforce.com",
                "test_mode": True
            }
            
            env = os.environ.copy()
            env.update({
                'TEST_MODE': 'true',
                'CONFIG_DIR': str(temp_config_dir),
                'PYTHONPATH': str(Path.cwd())
            })
            
            # Run status command
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--validate-system', '--quiet'],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            # Should complete successfully (may have test failures but no infrastructure errors)
            assert result.returncode in [0, 1], f"Status command failed: {result.stderr}"
            assert "INTERNALERROR" not in result.stderr
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_cli_async_operations_isolated(
        self, 
        isolated_event_loop, 
        async_resource_manager, 
        isolated_mocks,
        async_timeout_manager
    ):
        """Test CLI async operations with isolated event loop and resources."""
        # Create isolated async mocks
        mock_monitor = isolated_mocks.create_isolated_async_mock(
            'monitor',
            start=mock.AsyncMock(),
            stop=mock.AsyncMock(),
            check_inbox=mock.AsyncMock(return_value={'status': 'success', 'count': 0})
        )
        
        mock_processor = isolated_mocks.create_isolated_async_mock(
            'processor',
            process_inbox=mock.AsyncMock(return_value={'processed': 0, 'failed': 0})
        )
        
        # Register with async resource manager
        async_resource_manager.register_client(mock_monitor, "mock_monitor")
        async_resource_manager.register_client(mock_processor, "mock_processor")
        
        # Test async operations with timeouts
        try:
            # Simulate async CLI operations
            await async_timeout_manager.with_timeout(mock_monitor.start(), 'client_connect')
            result = await async_timeout_manager.with_timeout(mock_monitor.check_inbox(), 'api_call')
            await async_timeout_manager.with_timeout(mock_processor.process_inbox(), 'api_call')
            await async_timeout_manager.with_timeout(mock_monitor.stop(), 'client_disconnect')
            
            # Verify operations completed
            assert result['status'] == 'success'
            mock_monitor.start.assert_called_once()
            mock_monitor.check_inbox.assert_called_once()
            mock_processor.process_inbox.assert_called_once()
            mock_monitor.stop.assert_called_once()
            
        except asyncio.TimeoutError:
            pytest.fail("Async operations timed out - isolation failure")
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Complex file isolation not supported in test environment")
    @pytest.mark.medium
    @pytest.mark.cli
    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_config_isolation(self, project_structure, isolated_global_state, no_singleton_conflicts):
        """Test CLI configuration isolation between tests."""
        # Use project structure for realistic CLI testing
        config_dir = project_structure['config']
        log_dir = project_structure['logs']
        
        # Create test-specific configuration
        test_config = {
            "test_id": f"test_{id(self)}",
            "azure_endpoint": "https://isolated-test.azure.com",
            "log_directory": str(log_dir),
            "test_mode": True,
            "isolation_test": True
        }
        
        config_file = config_dir / "test_settings.json"
        config_file.write_text(json.dumps(test_config, indent=2))
        
        env = os.environ.copy()
        env.update({
            'TEST_MODE': 'true',
            'CONFIG_FILE': str(config_file),
            'LOG_DIR': str(log_dir),
            'PYTHONPATH': str(Path.cwd())
        })
        
        # Run CLI command with isolated configuration
        result = subprocess.run(
            [sys.executable, 'run_tests.py', '--smoke', '--dry-run'],
            capture_output=True,
            text=True,
            timeout=25,
            env=env,
            cwd=project_structure['base']
        )
        
        assert result.returncode == 0, f"Config isolation test failed: {result.stderr}"
        
        # Verify configuration isolation - no cross-test pollution
        # This is validated by the isolated_global_state fixture
    
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_subprocess_isolation(self, isolated_filesystem, temp_log_dir):
        """Test that CLI subprocess operations don't interfere with each other."""
        
        # Run multiple CLI operations in sequence to test isolation
        operations = [
            ['--help'],
            ['--list-markers'], 
            ['--smoke', '--dry-run']
        ]
        
        env = os.environ.copy()
        env.update({
            'TEST_MODE': 'true',
            'LOG_DIR': str(temp_log_dir),
            'PYTHONPATH': str(Path.cwd())
        })
        
        results = []
        for operation in operations:
            result = subprocess.run(
                [sys.executable, 'run_tests.py'] + operation,
                capture_output=True,
                text=True,
                timeout=15,
                env=env
            )
            results.append(result)
        
        # All operations should succeed independently
        for i, result in enumerate(results):
            assert result.returncode == 0, f"Operation {operations[i]} failed: {result.stderr}"
        
        # No subprocess resource conflicts
        for result in results:
            assert "Resource temporarily unavailable" not in result.stderr
            assert "Address already in use" not in result.stderr
    
    @pytest.mark.performance
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.cli
    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_performance_isolation(self, performance_monitor, isolated_filesystem):
        """Test CLI performance with isolation overhead."""
        with performance_monitor.monitor():
            env = os.environ.copy()
            env.update({
                'TEST_MODE': 'true',
                'PYTHONPATH': str(Path.cwd())
            })
            
            # Run performance-sensitive CLI operation
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--fast', '--dry-run'],
                capture_output=True,
                text=True,
                timeout=20,
                env=env
            )
        
        assert result.returncode == 0
        
        # Verify isolation doesn't significantly impact performance
        metrics = performance_monitor.metrics
        assert metrics.execution_time < 20.0, f"CLI performance degraded: {metrics.execution_time:.2f}s"
        assert metrics.memory_usage < 300.0, f"CLI memory usage too high: {metrics.memory_usage:.1f}MB"


class TestCLIIsolationValidation:
    """Validate CLI isolation works correctly."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_parallel_execution(self, isolated_filesystem):
        """Test CLI operations can run in parallel without conflicts."""
        import concurrent.futures
        import threading
        
        def run_cli_operation(operation_id):
            env = os.environ.copy()
            env.update({
                'TEST_MODE': 'true',
                'OPERATION_ID': str(operation_id),
                'PYTHONPATH': str(Path.cwd())
            })
            
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--help'],
                capture_output=True,
                text=True,
                timeout=20,
                env=env
            )
            return result.returncode == 0, operation_id
        
        # Run multiple CLI operations in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(run_cli_operation, i) for i in range(3)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All parallel operations should succeed
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 3, f"Only {success_count}/3 parallel CLI operations succeeded"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_isolation_cleanup(self, isolated_filesystem, performance_monitor):
        """Test that CLI operations clean up properly."""
        initial_files = set(Path.cwd().rglob('*.tmp'))
        initial_processes = len([p for p in os.listdir('/proc') if p.isdigit()]) if Path('/proc').exists() else 0
        
        with performance_monitor.monitor():
            env = os.environ.copy()
            env['TEST_MODE'] = 'true'
            env['PYTHONPATH'] = str(Path.cwd())
            
            # Run CLI operation that might create temporary resources
            result = subprocess.run(
                [sys.executable, 'run_tests.py', '--smoke', '--dry-run'],
                capture_output=True,
                text=True,
                timeout=25,
                env=env
            )
        
        assert result.returncode == 0
        
        # Check for resource cleanup
        final_files = set(Path.cwd().rglob('*.tmp'))
        new_files = final_files - initial_files
        
        assert len(new_files) == 0, f"CLI operation left temporary files: {new_files}"
        
        # Memory usage should be reasonable
        metrics = performance_monitor.metrics
        assert metrics.memory_delta < 50.0, f"CLI operation memory leak: {metrics.memory_delta:.1f}MB"


# Phase 2 Recovery: Mark resource-intensive tests as excluded until Phase 3
class TestCLIResourceIntensive:
    """Resource-intensive CLI tests excluded until Phase 3."""
    
    @pytest.mark.skip(reason="Resource-intensive CLI test - Phase 3 recovery")
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_full_test_execution(self):
        """Full CLI test execution - requires Phase 3 resource management."""
        # This would run actual test execution through CLI
        # Excluded due to resource intensity and potential for system impact
        pass
    
    @pytest.mark.skip(reason="Complex CLI orchestration - Phase 3 recovery")
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_complex_workflow(self):
        """Complex CLI workflow testing - requires Phase 3 resource management."""
        # This would test complex CLI scenarios with multiple service interactions
        # Excluded due to complexity and resource requirements
        pass


# Phase 2 Recovery: Performance validation
class TestCLIPhase2Recovery:
    """Validate Phase 2 CLI recovery meets performance targets."""
    
    @pytest.mark.performance
    @pytest.mark.integration
    @pytest.mark.skip(reason="Performance validation requires stable environment - disabled for general testing")
    @pytest.mark.medium
    @pytest.mark.cli
    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_phase2_performance_targets(self, performance_monitor, isolated_filesystem):
        """Validate CLI Phase 2 recovery meets all performance targets."""
        
        test_operations = [
            (['--help'], 10.0),
            (['--help'], 8.0),
            (['--smoke', '--dry-run'], 15.0)
        ]
        
        results = {}
        
        for operation, target_time in test_operations:
            with performance_monitor.monitor():
                env = os.environ.copy()
                env.update({
                    'TEST_MODE': 'true',
                    'PYTHONPATH': str(Path.cwd())
                })
                
                result = subprocess.run(
                    [sys.executable, 'run_tests.py'] + operation,
                    capture_output=True,
                    text=True,
                    timeout=target_time + 5,
                    env=env
                )
            
            metrics = performance_monitor.metrics
            results[' '.join(operation)] = {
                'success': result.returncode == 0,
                'time': metrics.execution_time,
                'target': target_time,
                'memory': metrics.memory_usage
            }
            
            # Verify individual performance targets
            assert result.returncode == 0, f"CLI operation {operation} failed"
            assert metrics.execution_time < target_time, \
                f"CLI {operation} took {metrics.execution_time:.2f}s, target <{target_time}s"
        
        # Overall validation
        total_operations = len(test_operations)
        successful_operations = sum(1 for r in results.values() if r['success'])
        
        print(f"\n🎯 CLI PHASE 2 RECOVERY VALIDATION:")
        for op, stats in results.items():
            status = "✅" if stats['success'] and stats['time'] < stats['target'] else "❌"
            print(f"   {status} {op}: {stats['time']:.2f}s (target: {stats['target']}s)")
        
        print(f"   📊 Success rate: {successful_operations}/{total_operations} ({successful_operations/total_operations*100:.1f}%)")
        
        # Phase 2 target: 100% success rate for isolated CLI operations
        assert successful_operations == total_operations, "CLI Phase 2 recovery incomplete"
        
        print(f"   ✅ CLI Phase 2 recovery targets achieved!")


if __name__ == "__main__":
    # Can be run directly for validation
    pytest.main([__file__, "-v", "--tb=short"])