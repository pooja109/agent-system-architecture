"""
System-wide resource monitoring and automatic intervention.

This module provides comprehensive system resource monitoring to prevent test execution
from interfering with system stability and automatically intervenes when limits are exceeded.
"""
import pytest
import psutil
import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class SystemLimits:
    """System resource limits for test execution."""
    max_memory_percent: float  # Percentage of system memory
    max_cpu_percent: float     # Average CPU usage
    max_disk_usage_percent: float
    max_network_mbps: float
    max_open_files: int
    monitoring_interval: float = 1.0


class SystemMonitor:
    """System-wide resource monitoring with automatic intervention."""
    
    def __init__(self):
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.intervention_callbacks: List[Callable] = []
        self.resource_history: List[Dict[str, float]] = []
        self.logger = logging.getLogger(__name__)
        
        # Default system limits (conservative for CI environments)
        self.default_limits = SystemLimits(
            max_memory_percent=70.0,  # 70% of system memory
            max_cpu_percent=60.0,     # 60% average CPU
            max_disk_usage_percent=80.0,
            max_network_mbps=50.0,
            max_open_files=1000
        )
        
        self.current_limits = self.default_limits
    
    def set_limits(self, limits: SystemLimits):
        """Set system resource limits."""
        self.current_limits = limits
    
    def get_system_resources(self) -> Dict[str, float]:
        """Get current system resource usage."""
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage('/').percent
        network = self.get_network_usage()
        
        try:
            open_files = len(psutil.Process().open_files())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            open_files = 0
        
        return {
            'memory_percent': memory.percent,
            'cpu_percent': cpu,
            'disk_percent': disk,
            'network_mbps': network,
            'open_files': open_files,
            'available_memory_gb': memory.available / 1024 / 1024 / 1024
        }
    
    def get_network_usage(self) -> float:
        """Get network usage in MB/s (simplified)."""
        try:
            net_io = psutil.net_io_counters()
            # This is a simplified calculation - in real implementation
            # you'd track deltas over time
            return (net_io.bytes_sent + net_io.bytes_recv) / 1024 / 1024
        except Exception:
            return 0.0
    
    def check_resource_limits(self) -> List[str]:
        """Check if any resource limits are exceeded."""
        resources = self.get_system_resources()
        violations = []
        
        if resources['memory_percent'] > self.current_limits.max_memory_percent:
            violations.append(f"Memory usage {resources['memory_percent']:.1f}% exceeds limit {self.current_limits.max_memory_percent}%")
        
        if resources['cpu_percent'] > self.current_limits.max_cpu_percent:
            violations.append(f"CPU usage {resources['cpu_percent']:.1f}% exceeds limit {self.current_limits.max_cpu_percent}%")
        
        if resources['disk_percent'] > self.current_limits.max_disk_usage_percent:
            violations.append(f"Disk usage {resources['disk_percent']:.1f}% exceeds limit {self.current_limits.max_disk_usage_percent}%")
        
        if resources['open_files'] > self.current_limits.max_open_files:
            violations.append(f"Open files {resources['open_files']} exceeds limit {self.current_limits.max_open_files}")
        
        return violations
    
    def start_monitoring(self):
        """Start system resource monitoring."""
        self.monitoring_active = True
        self.resource_history.clear()
        
        def monitor_resources():
            while self.monitoring_active:
                try:
                    resources = self.get_system_resources()
                    self.resource_history.append({
                        'timestamp': time.time(),
                        **resources
                    })
                    
                    # Keep history limited
                    if len(self.resource_history) > 1000:
                        self.resource_history = self.resource_history[-500:]
                    
                    violations = self.check_resource_limits()
                    if violations:
                        self.logger.warning(f"Resource limit violations: {violations}")
                        
                        # Trigger intervention callbacks
                        for callback in self.intervention_callbacks:
                            try:
                                callback(resources, violations)
                            except Exception as e:
                                self.logger.error(f"Intervention callback error: {e}")
                
                except Exception as e:
                    self.logger.error(f"Resource monitoring error: {e}")
                
                time.sleep(self.current_limits.monitoring_interval)
        
        self.monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return resource statistics."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        if not self.resource_history:
            return {}
        
        # Calculate statistics
        memory_values = [r['memory_percent'] for r in self.resource_history]
        cpu_values = [r['cpu_percent'] for r in self.resource_history]
        
        return {
            'peak_memory_percent': max(memory_values),
            'average_memory_percent': sum(memory_values) / len(memory_values),
            'peak_cpu_percent': max(cpu_values),
            'average_cpu_percent': sum(cpu_values) / len(cpu_values),
            'monitoring_duration': len(self.resource_history) * self.current_limits.monitoring_interval,
            'resource_violations': sum(1 for _ in self.resource_history if self.check_resource_limits())
        }
    
    def register_intervention_callback(self, callback: Callable[[Dict[str, float], List[str]], None]):
        """Register callback for resource limit violations."""
        self.intervention_callbacks.append(callback)
    
    @contextmanager
    def system_monitoring(self, limits: Optional[SystemLimits] = None):
        """Context manager for system resource monitoring."""
        if limits:
            original_limits = self.current_limits
            self.set_limits(limits)
        else:
            original_limits = None
        
        self.start_monitoring()
        try:
            yield self
        finally:
            self.stop_monitoring()
            if original_limits:
                self.set_limits(original_limits)


# Automatic intervention strategies
class ResourceInterventionManager:
    """Manages automatic interventions for resource violations."""
    
    def __init__(self):
        self.interventions_triggered = 0
        self.logger = logging.getLogger(__name__)
    
    def memory_pressure_intervention(self, resources: Dict[str, float], violations: List[str]):
        """Handle memory pressure situations."""
        if any('Memory usage' in v for v in violations):
            self.interventions_triggered += 1
            self.logger.warning(f"Memory intervention #{self.interventions_triggered}: {resources['memory_percent']:.1f}%")
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # If memory is critical, raise exception
            if resources['memory_percent'] > 85.0:
                raise MemoryError(f"Critical memory pressure: {resources['memory_percent']:.1f}%")
    
    def cpu_pressure_intervention(self, resources: Dict[str, float], violations: List[str]):
        """Handle CPU pressure situations."""
        if any('CPU usage' in v for v in violations):
            self.interventions_triggered += 1
            self.logger.warning(f"CPU intervention #{self.interventions_triggered}: {resources['cpu_percent']:.1f}%")
            
            # Brief sleep to reduce CPU pressure
            time.sleep(0.5)
    
    def disk_pressure_intervention(self, resources: Dict[str, float], violations: List[str]):
        """Handle disk pressure situations."""
        if any('Disk usage' in v for v in violations):
            self.interventions_triggered += 1
            self.logger.warning(f"Disk intervention #{self.interventions_triggered}: {resources['disk_percent']:.1f}%")
            
            # Log warning - disk cleanup requires manual intervention
            self.logger.critical(f"Disk usage critical: {resources['disk_percent']:.1f}%")
    
    def file_handle_intervention(self, resources: Dict[str, float], violations: List[str]):
        """Handle file handle exhaustion."""
        if any('Open files' in v for v in violations):
            self.interventions_triggered += 1
            self.logger.warning(f"File handle intervention #{self.interventions_triggered}: {resources['open_files']} files")
            
            # Force garbage collection to close unreferenced files
            import gc
            gc.collect()


class SystemHealthChecker:
    """Checks system health before and after test execution."""
    
    def __init__(self):
        self.baseline_resources = {}
        self.health_thresholds = {
            'memory_percent': 80.0,
            'cpu_percent': 70.0,
            'disk_percent': 85.0,
            'open_files': 800
        }
    
    def capture_baseline(self, monitor: SystemMonitor):
        """Capture baseline system resources."""
        self.baseline_resources = monitor.get_system_resources()
    
    def check_system_health(self, monitor: SystemMonitor) -> Dict[str, Any]:
        """Check current system health status."""
        current_resources = monitor.get_system_resources()
        health_issues = []
        
        for resource, threshold in self.health_thresholds.items():
            if resource in current_resources:
                value = current_resources[resource]
                if value > threshold:
                    health_issues.append(f"{resource}: {value:.1f} > {threshold}")
        
        return {
            'healthy': len(health_issues) == 0,
            'issues': health_issues,
            'resources': current_resources,
            'baseline': self.baseline_resources
        }
    
    def get_resource_delta(self, monitor: SystemMonitor) -> Dict[str, float]:
        """Get resource usage delta from baseline."""
        if not self.baseline_resources:
            return {}
        
        current = monitor.get_system_resources()
        delta = {}
        
        for key in self.baseline_resources:
            if key in current:
                delta[f"{key}_delta"] = current[key] - self.baseline_resources[key]
        
        return delta


class SystemPerformanceProfiler:
    """Profiles system performance during test execution."""
    
    def __init__(self):
        self.performance_snapshots = []
        self.profiling_active = False
    
    def start_profiling(self, monitor: SystemMonitor):
        """Start performance profiling."""
        self.profiling_active = True
        self.performance_snapshots.clear()
        
        def profile_performance():
            while self.profiling_active:
                try:
                    resources = monitor.get_system_resources()
                    snapshot = {
                        'timestamp': time.time(),
                        'resources': resources,
                        'cpu_per_core': psutil.cpu_percent(percpu=True, interval=0.1),
                        'memory_details': psutil.virtual_memory()._asdict(),
                        'disk_io': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
                        'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}
                    }
                    self.performance_snapshots.append(snapshot)
                    
                    # Limit snapshot history
                    if len(self.performance_snapshots) > 500:
                        self.performance_snapshots = self.performance_snapshots[-250:]
                
                except Exception as e:
                    logging.getLogger(__name__).error(f"Performance profiling error: {e}")
                
                time.sleep(2.0)  # Profile every 2 seconds
        
        self.profile_thread = threading.Thread(target=profile_performance, daemon=True)
        self.profile_thread.start()
    
    def stop_profiling(self) -> Dict[str, Any]:
        """Stop profiling and return performance analysis."""
        self.profiling_active = False
        if hasattr(self, 'profile_thread'):
            self.profile_thread.join(timeout=1.0)
        
        if not self.performance_snapshots:
            return {}
        
        # Analyze performance
        cpu_values = [s['resources']['cpu_percent'] for s in self.performance_snapshots]
        memory_values = [s['resources']['memory_percent'] for s in self.performance_snapshots]
        
        return {
            'snapshot_count': len(self.performance_snapshots),
            'duration_seconds': (self.performance_snapshots[-1]['timestamp'] - 
                               self.performance_snapshots[0]['timestamp']),
            'cpu_analysis': {
                'min': min(cpu_values),
                'max': max(cpu_values),
                'avg': sum(cpu_values) / len(cpu_values),
                'spikes': len([c for c in cpu_values if c > 80.0])
            },
            'memory_analysis': {
                'min': min(memory_values),
                'max': max(memory_values),
                'avg': sum(memory_values) / len(memory_values),
                'pressure_events': len([m for m in memory_values if m > 75.0])
            }
        }


@pytest.fixture(scope="function")
def system_monitor():
    """Provide system monitoring for each test."""
    monitor = SystemMonitor()
    intervention_manager = ResourceInterventionManager()
    
    # Register default interventions
    monitor.register_intervention_callback(intervention_manager.memory_pressure_intervention)
    monitor.register_intervention_callback(intervention_manager.cpu_pressure_intervention)
    monitor.register_intervention_callback(intervention_manager.disk_pressure_intervention)
    monitor.register_intervention_callback(intervention_manager.file_handle_intervention)
    
    try:
        yield monitor
    finally:
        monitor.stop_monitoring()


@pytest.fixture(scope="function")
def system_health_checker():
    """Provide system health checking."""
    return SystemHealthChecker()


@pytest.fixture(scope="function")
def system_performance_profiler():
    """Provide system performance profiling."""
    return SystemPerformanceProfiler()


# System monitoring decorators
def system_resource_limits(memory_percent: float = 70.0, cpu_percent: float = 60.0):
    """Decorator to enforce system resource limits on test functions."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            limits = SystemLimits(
                max_memory_percent=memory_percent,
                max_cpu_percent=cpu_percent,
                max_disk_usage_percent=80.0,
                max_network_mbps=50.0,
                max_open_files=1000
            )
            
            monitor = SystemMonitor()
            monitor.set_limits(limits)
            
            with monitor.system_monitoring():
                return test_func(*args, **kwargs)
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


def with_system_health_check(fail_on_unhealthy: bool = False):
    """Decorator to add system health checking to test functions."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            monitor = SystemMonitor()
            health_checker = SystemHealthChecker()
            
            # Capture baseline
            health_checker.capture_baseline(monitor)
            
            try:
                result = test_func(*args, **kwargs)
                
                # Check final health
                health_status = health_checker.check_system_health(monitor)
                if not health_status['healthy']:
                    warning_msg = f"System health issues detected: {health_status['issues']}"
                    if fail_on_unhealthy:
                        raise RuntimeError(warning_msg)
                    else:
                        logging.getLogger(__name__).warning(warning_msg)
                
                return result
                
            finally:
                # Log resource deltas
                delta = health_checker.get_resource_delta(monitor)
                if delta:
                    logging.getLogger(__name__).info(f"Resource usage delta: {delta}")
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


# Utility functions
def wait_for_system_stabilization(target_cpu: float = 20.0, target_memory: float = 50.0, 
                                 timeout: float = 30.0) -> bool:
    """Wait for system resources to stabilize below target levels."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            cpu = psutil.cpu_percent(interval=1.0)
            memory = psutil.virtual_memory().percent
            
            if cpu <= target_cpu and memory <= target_memory:
                return True
                
        except Exception:
            pass
        
        time.sleep(1.0)
    
    return False


def get_system_resource_summary() -> Dict[str, Any]:
    """Get comprehensive system resource summary."""
    try:
        memory = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu': {
                'count': psutil.cpu_count(),
                'usage_percent': psutil.cpu_percent(interval=1.0),
                'frequency_mhz': cpu_freq.current if cpu_freq else None
            },
            'memory': {
                'total_gb': memory.total / 1024 / 1024 / 1024,
                'available_gb': memory.available / 1024 / 1024 / 1024,
                'usage_percent': memory.percent
            },
            'disk': {
                'total_gb': disk.total / 1024 / 1024 / 1024,
                'free_gb': disk.free / 1024 / 1024 / 1024,
                'usage_percent': (disk.used / disk.total) * 100
            }
        }
    except Exception as e:
        return {'error': str(e)}


# Export commonly used components
__all__ = [
    'SystemMonitor', 'SystemLimits', 'ResourceInterventionManager',
    'SystemHealthChecker', 'SystemPerformanceProfiler',
    'system_monitor', 'system_health_checker', 'system_performance_profiler',
    'system_resource_limits', 'with_system_health_check',
    'wait_for_system_stabilization', 'get_system_resource_summary'
]