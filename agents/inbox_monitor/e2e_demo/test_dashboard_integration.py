#!/usr/bin/env python3
"""
Comprehensive Integration Tests for Dashboard System
"""

import pytest
import asyncio
import time
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard_integration import DashboardIntegration, DashboardState
from animation_controller import AnimationController, create_dashboard_controller
from service_monitor import ServiceMonitor, ServiceHealth
from terminal_detector import TerminalDetector


class TestTerminalCompatibility:
    """Test terminal compatibility edge cases."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_very_small_terminal(self):
        """Test behavior with very small terminal (< 80 chars)."""
        with patch.dict(os.environ, {'COLUMNS': '60', 'LINES': '10'}):
            detector = TerminalDetector()
            assert detector.width == 60
            assert detector.height == 10
            assert not detector.supports_rich()  # Should fallback for small terminals
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_exotic_terminal_types(self):
        """Test behavior with unusual terminal types."""
        test_cases = [
            {'TERM': 'dumb'},
            {'TERM': 'vt100'},
            {'TERM': 'screen'},
            {'TERM': 'tmux'}
        ]
        
        for env_vars in test_cases:
            with patch.dict(os.environ, env_vars):
                detector = TerminalDetector()
                # Should not crash and should provide sensible defaults
                caps = detector.get_capabilities()
                assert 'terminal' in caps
                assert 'rich_support' in caps
                assert isinstance(caps['rich_support'], bool)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ci_environment_detection(self):
        """Test CI environment detection with various CI systems."""
        ci_environments = [
            {'CI': 'true'},
            {'GITHUB_ACTIONS': 'true'},
            {'GITLAB_CI': 'true'},
            {'JENKINS': 'true'},
            {'TRAVIS': 'true'},
            {'CIRCLECI': 'true'}
        ]
        
        for ci_env in ci_environments:
            with patch.dict(os.environ, ci_env):
                detector = TerminalDetector()
                assert detector.is_ci_environment()
                assert not detector.supports_rich()  # Should disable rich in CI
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_missing_terminal_info(self):
        """Test behavior when terminal information is missing."""
        # Remove all terminal-related environment variables
        with patch.dict(os.environ, {}, clear=True):
            detector = TerminalDetector()
            caps = detector.get_capabilities()
            
            # Should provide safe defaults
            assert caps['width'] >= 80
            assert caps['height'] >= 24
            assert caps['terminal'] == 'unknown'


class TestAnimationPerformance:
    """Test animation controller performance under various conditions."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_high_cpu_load_degradation(self):
        """Test performance degradation under high CPU load."""
        controller = create_dashboard_controller()
        
        # Start multiple animations
        controller.start_animation('loading')
        controller.start_animation('connecting')
        
        # Simulate high CPU usage by adding fake slow frame times
        controller.frame_times = [0.5, 0.6, 0.7, 0.8] * 10
        controller._monitor_performance()
        
        assert controller.performance_degraded
        
        # Test recovery
        controller.frame_times = [0.1, 0.1, 0.1, 0.1] * 10
        controller._monitor_performance()
        
        assert not controller.performance_degraded
        
        controller.stop_all_animations()
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_animation_cleanup_on_error(self):
        """Test proper cleanup when animations fail."""
        controller = AnimationController()
        
        # Mock animation sequence that will fail
        mock_sequence = Mock()
        mock_sequence.next_frame.side_effect = Exception("Animation error")
        
        controller.active_animations['failing'] = mock_sequence
        controller.animation_queue.append('failing')
        
        # Process animations - should handle error gracefully
        controller._process_animations()
        
        # Animation should be removed from queue after failure
        assert 'failing' not in controller.animation_queue
        
        controller.stop_all_animations()
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_frame_rate_limits(self):
        """Test that frame rate limits are respected."""
        from animation_controller import AnimationConfig
        
        # Create controller with strict frame rate limit
        config = AnimationConfig(max_fps=1.0)
        controller = AnimationController(config)
        
        start_time = time.time()
        
        # Start animation loop briefly
        controller.start_animation_loop()
        time.sleep(2.5)  # Let it run for 2.5 seconds
        controller.stop_animation_loop()
        
        elapsed = time.time() - start_time
        
        # Should not exceed target FPS significantly
        # At 1 FPS, should process ~2-3 frames in 2.5 seconds
        stats = controller.get_performance_stats()
        if stats.get('actual_fps', 0) > 0:
            assert stats['actual_fps'] <= 2.0  # Allow some tolerance


class TestServiceMonitorEdgeCases:
    """Test service monitor edge cases and error conditions."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_concurrent_operations(self):
        """Test concurrent operations on the same service."""
        monitor = ServiceMonitor()
        
        # Start multiple concurrent operations
        op_ids = []
        for i in range(5):
            op_id = monitor.start_operation(f"service_{i % 2}", f"operation_{i}")
            op_ids.append(op_id)
        
        # Complete them with mixed success/failure
        for i, op_id in enumerate(op_ids):
            monitor.complete_operation(op_id, success=(i % 2 == 0))
        
        # Check that metrics are calculated correctly
        summary = monitor.get_health_summary()
        assert summary['total_services'] == 2
        assert summary['active_operations'] == 0
        
        monitor.stop_monitoring()
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_stale_operation_cleanup(self):
        """Test cleanup of stale operations."""
        monitor = ServiceMonitor()
        monitor.start_monitoring()
        
        # Start operation and simulate it being stale
        op_id = monitor.start_operation("slow_service", "slow_operation")
        
        # Manually age the operation
        if op_id in monitor.active_operations:
            operation = monitor.active_operations[op_id]
            operation.start_time = operation.start_time.replace(
                year=operation.start_time.year - 1
            )
        
        # Trigger stale check
        monitor._check_stale_operations()
        
        # Operation should be marked as failed and removed
        assert op_id not in monitor.active_operations
        
        monitor.stop_monitoring()
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_service_health_assessment(self):
        """Test service health assessment logic."""
        monitor = ServiceMonitor()
        
        # Simulate service with failures
        service_name = "test_service"
        for i in range(5):
            op_id = monitor.start_operation(service_name, f"operation_{i}")
            # First 3 fail, last 2 succeed
            success = i >= 3
            monitor.complete_operation(op_id, success=success)
        
        metrics = monitor.get_service_metrics(service_name)
        assert metrics is not None
        assert metrics.total_operations == 5
        assert metrics.successful_operations == 2
        assert metrics.failed_operations == 3
        
        # Health should be degraded due to 40% success rate
        health = metrics.determine_health()
        assert health in [ServiceHealth.DEGRADED, ServiceHealth.FAILING]


class TestDashboardIntegrationStress:
    """Test dashboard integration under stress conditions."""
    
    @pytest.mark.asyncio
    async def test_rapid_updates(self):
        """Test rapid dashboard updates don't cause issues."""
        class MockConfig:
            output_format = 'simple'  # Use simple to avoid Rich dependency in tests
            output_file = None
        
        integration = DashboardIntegration(MockConfig())
        
        # Send rapid updates
        for i in range(100):
            integration.add_message(f"Message {i}", "info")
            if i % 10 == 0:
                await asyncio.sleep(0.01)  # Brief pause every 10 messages
        
        # Should handle gracefully without errors
        assert integration.state in [DashboardState.INITIALIZING, DashboardState.RUNNING]
    
    @pytest.mark.asyncio
    async def test_dashboard_recovery_from_display_failure(self):
        """Test dashboard recovery when display fails."""
        class MockConfig:
            output_format = 'dashboard'
            output_file = None
        
        integration = DashboardIntegration(MockConfig())
        
        if integration.can_use_dashboard:
            # Mock dashboard to fail
            integration.dashboard = Mock()
            integration.dashboard.create_dashboard.side_effect = Exception("Display error")
            
            # Should handle display failure gracefully
            integration._service_status_callback("test_service", 1.0, True)
            
            # Should either recover or disable dashboard
            assert integration.can_use_dashboard or not integration.live_display
    
    @pytest.mark.slow
    @pytest.mark.integration
    def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow unbounded."""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Create many service operations
        monitor = ServiceMonitor()
        
        for i in range(1000):
            op_id = monitor.start_operation(f"service_{i % 10}", "test")
            monitor.complete_operation(op_id, success=True)
        
        # Force garbage collection
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 50MB for 1000 operations)
        assert memory_increase < 50 * 1024 * 1024  # 50MB
        
        monitor.stop_monitoring()


class TestErrorRecovery:
    """Test comprehensive error recovery scenarios."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_import_failure_recovery(self):
        """Test graceful handling when Rich library missing."""
        with patch.dict('sys.modules', {'rich': None, 'rich.console': None}):
            # Should not crash when Rich is unavailable
            try:
                from dashboard_integration import DashboardIntegration
                
                class MockConfig:
                    output_format = 'dashboard'
                    output_file = None
                
                integration = DashboardIntegration(MockConfig())
                assert not integration.can_use_dashboard  # Should fallback
                
            except ImportError:
                # If import fails completely, that's also acceptable
                pass
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_thread_failure_recovery(self):
        """Test recovery when background threads fail."""
        controller = AnimationController()
        
        # Mock thread to fail on start
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread_instance.start.side_effect = Exception("Thread start failed")
            mock_thread.return_value = mock_thread_instance
            
            # Should handle thread start failure gracefully
            controller.start_animation_loop()
            assert not controller.is_running  # Should not claim to be running
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_queue_overflow_protection(self):
        """Test protection against queue overflow."""
        from dashboard_integration import DashboardIntegration, DashboardUpdate
        
        class MockConfig:
            output_format = 'dashboard'
            output_file = None
        
        integration = DashboardIntegration(MockConfig())
        
        if integration.can_use_dashboard:
            # Fill queue beyond reasonable limits
            for i in range(10000):
                try:
                    integration.update_queue.put(
                        DashboardUpdate('message', {'message': f'Test {i}'}),
                        block=False
                    )
                except:
                    break  # Queue full or other error - acceptable
            
            # System should remain stable
            assert integration.state != DashboardState.ERROR


class TestIntegrationScenarios:
    """Test complete integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_demo_simulation(self):
        """Test complete demo scenario from start to finish."""
        class MockConfig:
            output_format = 'simple'  # Use simple to avoid Rich in tests
            output_file = None
            detail_level = Mock()
            detail_level.value = 'business'
        
        integration = DashboardIntegration(MockConfig())
        
        # Simulate complete demo lifecycle
        async with integration:
            # Simulate service initialization
            services = ['azure_ai', 'email_service', 'salesforce']
            operations = []
            
            for service in services:
                op_id = integration.start_service_operation(service, 'initialize')
                if op_id:
                    operations.append((service, op_id))
            
            # Complete operations
            for service, op_id in operations:
                integration.complete_service_operation(op_id, success=True)
            
            # Simulate scenario execution
            for scenario_id in range(3):
                integration.add_message(f"Running scenario {scenario_id}", "info")
                await asyncio.sleep(0.1)  # Simulate work
                integration.add_message(f"Completed scenario {scenario_id}", "success")
        
        # Should complete without errors
        assert True  # If we get here, test passed
    
    @pytest.mark.slow
    @pytest.mark.e2e
    def test_performance_under_realistic_load(self):
        """Test system performance under realistic load."""
        start_time = time.time()
        
        # Simulate realistic dashboard usage
        class MockConfig:
            output_format = 'simple'
            output_file = None
        
        integration = DashboardIntegration(MockConfig())
        monitor = ServiceMonitor()
        controller = create_dashboard_controller()
        
        # Simulate 10 service operations across 3 services
        operations = []
        for i in range(10):
            service = f"service_{i % 3}"
            op_id = monitor.start_operation(service, "test_operation")
            operations.append(op_id)
            
            # Simulate work
            time.sleep(0.01)
            
            monitor.complete_operation(op_id, success=(i % 4 != 0))  # 75% success rate
        
        elapsed = time.time() - start_time
        
        # Should complete quickly (< 1 second for 10 operations)
        assert elapsed < 1.0
        
        # Cleanup
        monitor.stop_monitoring()
        controller.stop_all_animations()


def run_integration_tests():
    """Run all integration tests."""
    print("=== Running Enhanced Integration Tests ===")
    
    # Run tests using pytest if available, otherwise run manually
    try:
        import pytest
        pytest.main([__file__, '-v'])
    except ImportError:
        print("pytest not available, running manual tests...")
        
        # Manual test execution
        test_classes = [
            TestTerminalCompatibility(),
            TestAnimationPerformance(),
            TestServiceMonitorEdgeCases(),
            TestDashboardIntegrationStress(),
            TestErrorRecovery(),
            TestIntegrationScenarios()
        ]
        
        for test_class in test_classes:
            class_name = test_class.__class__.__name__
            print(f"\n--- {class_name} ---")
            
            for method_name in dir(test_class):
                if method_name.startswith('test_'):
                    try:
                        method = getattr(test_class, method_name)
                        if asyncio.iscoroutinefunction(method):
                            asyncio.run(method())
                        else:
                            method()
                        print(f"✅ {method_name}")
                    except Exception as e:
                        print(f"❌ {method_name}: {e}")
    
    print("\n=== Integration Tests Complete ===")


if __name__ == "__main__":
    run_integration_tests()