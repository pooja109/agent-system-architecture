"""
Performance monitoring utilities for test execution optimization.
"""
import time
import resource
import psutil
import threading
from contextlib import contextmanager
from typing import Dict, Any, Optional
import pytest


class TestPerformanceMonitor:
    """
    Monitor test performance and resource usage.
    """
    
    def __init__(self):
        self.execution_stats = {}
        self.resource_stats = {}
        self.baseline_memory = self._get_memory_usage()
        self.start_time = time.time()
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss // (1024 * 1024)
        except Exception:
            return 0
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            process = psutil.Process()
            return process.cpu_percent()
        except Exception:
            return 0.0
    
    def _get_open_files_count(self) -> int:
        """Get count of open file descriptors."""
        try:
            process = psutil.Process()
            return len(process.open_files())
        except Exception:
            return 0
    
    @contextmanager
    def monitor_test_execution(self, test_name: str):
        """
        Context manager to monitor individual test execution.
        
        Args:
            test_name: Name of the test being monitored
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()
        start_files = self._get_open_files_count()
        
        try:
            yield
        finally:
            execution_time = time.time() - start_time
            end_memory = self._get_memory_usage()
            end_files = self._get_open_files_count()
            
            self.execution_stats[test_name] = {
                'execution_time': execution_time,
                'memory_delta': end_memory - start_memory,
                'files_delta': end_files - start_files,
                'peak_cpu': self._get_cpu_usage()
            }
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Returns:
            Dictionary with performance statistics and recommendations
        """
        total_execution_time = time.time() - self.start_time
        current_memory = self._get_memory_usage()
        memory_growth = current_memory - self.baseline_memory
        
        # Identify slow tests
        slow_tests = []
        for test_name, stats in self.execution_stats.items():
            if stats['execution_time'] > 5.0:  # Slower than 5 seconds
                slow_tests.append((test_name, stats['execution_time']))
        
        # Identify memory leaks
        memory_leaks = []
        for test_name, stats in self.execution_stats.items():
            if stats['memory_delta'] > 10:  # More than 10MB growth
                memory_leaks.append((test_name, stats['memory_delta']))
        
        # Identify file handle leaks  
        file_leaks = []
        for test_name, stats in self.execution_stats.items():
            if stats['files_delta'] > 0:  # Any file handle growth
                file_leaks.append((test_name, stats['files_delta']))
        
        return {
            'total_execution_time': total_execution_time,
            'memory_growth': memory_growth,
            'tests_executed': len(self.execution_stats),
            'slow_tests': sorted(slow_tests, key=lambda x: x[1], reverse=True)[:10],
            'memory_leaks': sorted(memory_leaks, key=lambda x: x[1], reverse=True)[:10],
            'file_leaks': sorted(file_leaks, key=lambda x: x[1], reverse=True)[:10],
            'recommendations': self._generate_recommendations(slow_tests, memory_leaks, file_leaks)
        }
    
    def _generate_recommendations(self, slow_tests, memory_leaks, file_leaks) -> list:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        if slow_tests:
            recommendations.append(f"Optimize {len(slow_tests)} slow tests taking >5 seconds")
        
        if memory_leaks:
            recommendations.append(f"Fix {len(memory_leaks)} tests with memory leaks >10MB")
        
        if file_leaks:
            recommendations.append(f"Fix {len(file_leaks)} tests with file handle leaks")
        
        return recommendations


class TimeoutManager:
    """
    Manage test timeouts to prevent hanging.
    """
    
    # Default timeout values by test type
    TIMEOUT_CONFIG = {
        'fast': 5,      # Fast tests: 5 seconds
        'medium': 30,   # Medium tests: 30 seconds
        'slow': 120,    # Slow tests: 2 minutes
        'integration': 60,  # Integration tests: 1 minute
        'default': 10   # Default timeout: 10 seconds
    }
    
    @classmethod
    def get_timeout_for_markers(cls, markers) -> int:
        """
        Get appropriate timeout based on test markers.
        
        Args:
            markers: Pytest markers for the test
            
        Returns:
            Timeout value in seconds
        """
        marker_names = [marker.name for marker in markers]
        
        # Check performance markers first
        for perf_marker in ['fast', 'medium', 'slow']:
            if perf_marker in marker_names:
                return cls.TIMEOUT_CONFIG[perf_marker]
        
        # Check functional markers
        if 'integration' in marker_names:
            return cls.TIMEOUT_CONFIG['integration']
        
        return cls.TIMEOUT_CONFIG['default']
    
    @staticmethod
    @contextmanager
    def timeout_context(seconds: int, test_name: str):
        """
        Context manager that implements test timeout.
        
        Args:
            seconds: Timeout duration in seconds
            test_name: Name of test for timeout message
        """
        def timeout_handler():
            raise TimeoutError(f"Test {test_name} exceeded timeout of {seconds} seconds")
        
        timer = threading.Timer(seconds, timeout_handler)
        timer.start()
        
        try:
            yield
        finally:
            timer.cancel()


# Global performance monitor instance
performance_monitor = TestPerformanceMonitor()


@pytest.fixture(scope="session")
def test_performance_monitor():
    """Session-scoped fixture providing performance monitoring."""
    return performance_monitor


@pytest.fixture
def monitor_test_performance(request):
    """
    Fixture that monitors individual test performance.
    """
    test_name = f"{request.cls.__name__ if request.cls else 'module'}::{request.function.__name__}"
    
    with performance_monitor.monitor_test_execution(test_name):
        yield


@pytest.fixture
def test_timeout(request):
    """
    Fixture that applies appropriate timeout based on test markers.
    """
    timeout = TimeoutManager.get_timeout_for_markers(request.node.iter_markers())
    test_name = f"{request.cls.__name__ if request.cls else 'module'}::{request.function.__name__}"
    
    with TimeoutManager.timeout_context(timeout, test_name):
        yield