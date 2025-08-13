"""
Performance monitoring fixtures for test execution timing and resource usage.

This module provides comprehensive performance monitoring to ensure recovered tests
meet performance targets and prevent future performance regressions.
"""
import pytest
import time
import psutil
import os
import threading
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class PerformanceMetrics:
    """Container for test performance metrics."""
    execution_time: float
    memory_usage: float  # MB
    cpu_percent: float
    start_memory: float
    end_memory: float
    memory_delta: float
    peak_memory: float = 0.0
    memory_samples: List[float] = None
    
    def __post_init__(self):
        if self.memory_samples is None:
            self.memory_samples = []


class PerformanceMonitor:
    """Monitor test performance and resource usage."""
    
    def __init__(self):
        try:
            self.process = psutil.Process(os.getpid())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self.process = None
        
        self.start_time: Optional[float] = None
        self.start_memory: Optional[float] = None
        self.metrics: Optional[PerformanceMetrics] = None
        self.monitoring_active = False
        self.memory_samples: List[float] = []
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_monitoring_flag = threading.Event()
    
    def start_monitoring(self):
        """Begin performance monitoring."""
        self.start_time = time.perf_counter()
        
        if self.process:
            try:
                memory_info = self.process.memory_info()
                self.start_memory = memory_info.rss / 1024 / 1024  # Convert to MB
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.start_memory = 0.0
        else:
            self.start_memory = 0.0
        
        self.monitoring_active = True
        self.memory_samples = [self.start_memory]
        
        # Start background memory monitoring
        self.stop_monitoring_flag.clear()
        self.monitoring_thread = threading.Thread(target=self._background_memory_monitoring, daemon=True)
        self.monitoring_thread.start()
    
    def _background_memory_monitoring(self):
        """Background thread to monitor memory usage."""
        while not self.stop_monitoring_flag.is_set():
            if self.process:
                try:
                    memory_info = self.process.memory_info()
                    current_memory = memory_info.rss / 1024 / 1024  # MB
                    self.memory_samples.append(current_memory)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sample every 100ms
            self.stop_monitoring_flag.wait(0.1)
    
    def stop_monitoring(self) -> PerformanceMetrics:
        """Stop monitoring and return metrics."""
        if self.start_time is None or self.start_memory is None:
            raise RuntimeError("Monitoring not started")
        
        # Stop background monitoring
        self.monitoring_active = False
        if self.monitoring_thread:
            self.stop_monitoring_flag.set()
            self.monitoring_thread.join(timeout=1.0)  # Wait max 1 second
        
        end_time = time.perf_counter()
        
        if self.process:
            try:
                memory_info = self.process.memory_info()
                end_memory = memory_info.rss / 1024 / 1024  # MB
                cpu_percent = self.process.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                end_memory = self.start_memory
                cpu_percent = 0.0
        else:
            end_memory = self.start_memory
            cpu_percent = 0.0
        
        # Calculate peak memory usage
        peak_memory = max(self.memory_samples) if self.memory_samples else end_memory
        
        self.metrics = PerformanceMetrics(
            execution_time=end_time - self.start_time,
            memory_usage=end_memory,
            cpu_percent=cpu_percent,
            start_memory=self.start_memory,
            end_memory=end_memory,
            memory_delta=end_memory - self.start_memory,
            peak_memory=peak_memory,
            memory_samples=self.memory_samples.copy()
        )
        
        return self.metrics
    
    @contextmanager
    def monitor(self):
        """Context manager for performance monitoring."""
        self.start_monitoring()
        try:
            yield self
        finally:
            self.stop_monitoring()
    
    def get_memory_profile(self) -> Dict[str, float]:
        """Get detailed memory usage profile."""
        if not self.memory_samples:
            return {}
        
        return {
            'min_memory': min(self.memory_samples),
            'max_memory': max(self.memory_samples),
            'avg_memory': sum(self.memory_samples) / len(self.memory_samples),
            'memory_variance': self._calculate_variance(self.memory_samples),
            'sample_count': len(self.memory_samples)
        }
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of memory samples."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance


class PerformanceThresholds:
    """Performance threshold definitions for different test types."""
    
    # Standard thresholds for different test categories
    UNIT_TEST = {
        'max_time': 2.0,      # 2 seconds
        'max_memory_mb': 25.0, # 25 MB
        'max_memory_delta_mb': 10.0  # 10 MB growth
    }
    
    INTEGRATION_TEST = {
        'max_time': 10.0,     # 10 seconds
        'max_memory_mb': 100.0, # 100 MB
        'max_memory_delta_mb': 50.0  # 50 MB growth
    }
    
    LOGGER_TEST = {
        'max_time': 30.0,      # 30 seconds - more lenient for tests
        'max_memory_mb': 500.0, # 500 MB - much more lenient
        'max_memory_delta_mb': 200.0  # 200 MB growth - more lenient
    }
    
    CLI_TEST = {
        'max_time': 30.0,     # 30 seconds (down from 60s timeouts)
        'max_memory_mb': 100.0, # 100 MB
        'max_memory_delta_mb': 50.0  # 50 MB growth
    }


# Performance assertion helpers
def assert_performance_within_limits(metrics: PerformanceMetrics, 
                                    max_time: float = 10.0,
                                    max_memory_mb: float = 100.0,
                                    max_memory_delta_mb: float = 50.0):
    """Assert test performance is within acceptable limits."""
    assert metrics.execution_time < max_time, \
        f"Test execution time {metrics.execution_time:.2f}s exceeds limit {max_time}s"
    
    assert metrics.memory_usage < max_memory_mb, \
        f"Test memory usage {metrics.memory_usage:.1f}MB exceeds limit {max_memory_mb}MB"
    
    assert abs(metrics.memory_delta) < max_memory_delta_mb, \
        f"Test memory delta {metrics.memory_delta:.1f}MB exceeds limit {max_memory_delta_mb}MB"


def assert_logger_test_performance(metrics: PerformanceMetrics):
    """Assert performance specifically for logger tests."""
    thresholds = PerformanceThresholds.LOGGER_TEST
    assert_performance_within_limits(
        metrics,
        max_time=thresholds['max_time'],
        max_memory_mb=thresholds['max_memory_mb'],
        max_memory_delta_mb=thresholds['max_memory_delta_mb']
    )


def assert_cli_test_performance(metrics: PerformanceMetrics):
    """Assert performance specifically for CLI tests."""
    thresholds = PerformanceThresholds.CLI_TEST
    assert_performance_within_limits(
        metrics,
        max_time=thresholds['max_time'],
        max_memory_mb=thresholds['max_memory_mb'],
        max_memory_delta_mb=thresholds['max_memory_delta_mb']
    )


def assert_unit_test_performance(metrics: PerformanceMetrics):
    """Assert performance specifically for unit tests."""
    thresholds = PerformanceThresholds.UNIT_TEST
    assert_performance_within_limits(
        metrics,
        max_time=thresholds['max_time'],
        max_memory_mb=thresholds['max_memory_mb'],
        max_memory_delta_mb=thresholds['max_memory_delta_mb']
    )


@pytest.fixture(scope="function")
def performance_monitor():
    """Provide performance monitoring for tests."""
    monitor = PerformanceMonitor()
    return monitor


@pytest.fixture(scope="function")
def enforce_performance_limits(performance_monitor):
    """Automatically enforce performance limits on tests."""
    with performance_monitor.monitor():
        yield
    
    # Automatically check performance after test
    metrics = performance_monitor.metrics
    if metrics:
        assert_performance_within_limits(metrics)


@pytest.fixture(scope="function")
def enforce_logger_performance(performance_monitor):
    """Automatically enforce logger-specific performance limits."""
    with performance_monitor.monitor():
        yield
    
    # Check logger-specific performance requirements
    metrics = performance_monitor.metrics
    if metrics:
        assert_logger_test_performance(metrics)


@pytest.fixture(scope="function")
def enforce_cli_performance(performance_monitor):
    """Automatically enforce CLI-specific performance limits."""
    with performance_monitor.monitor():
        yield
    
    # Check CLI-specific performance requirements
    metrics = performance_monitor.metrics  
    if metrics:
        assert_cli_test_performance(metrics)


class PerformanceRegressor:
    """Track performance over time to detect regressions."""
    
    def __init__(self):
        self.baseline_metrics: Dict[str, float] = {}
        self.historical_metrics: List[PerformanceMetrics] = []
    
    def set_baseline(self, test_name: str, metrics: PerformanceMetrics):
        """Set baseline performance for a test."""
        self.baseline_metrics[test_name] = metrics.execution_time
    
    def check_regression(self, test_name: str, metrics: PerformanceMetrics, 
                        regression_threshold: float = 1.5) -> bool:
        """Check if current metrics show performance regression."""
        if test_name not in self.baseline_metrics:
            # No baseline, set current as baseline
            self.set_baseline(test_name, metrics)
            return False
        
        baseline_time = self.baseline_metrics[test_name]
        current_time = metrics.execution_time
        
        # Check if current execution is significantly slower than baseline
        return current_time > (baseline_time * regression_threshold)


# Global performance regressor for session-wide tracking
_performance_regressor = PerformanceRegressor()


@pytest.fixture(scope="function")
def performance_regressor():
    """Provide performance regression tracking."""
    return _performance_regressor