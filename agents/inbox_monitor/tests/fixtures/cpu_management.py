"""
CPU resource control and monitoring for test execution.

This module provides comprehensive CPU resource management to prevent CPU saturation
and ensure tests complete within reasonable time and resource budgets.
"""
import pytest
import psutil
import time
import threading
import multiprocessing
from typing import Dict, Optional, Callable, List, Any
from dataclasses import dataclass
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed


@dataclass
class CPUBudget:
    """CPU resource budget for test execution."""
    max_cpu_percent: float
    max_execution_time: float
    throttle_threshold: float
    max_concurrent_operations: int


class CPUManager:
    """CPU resource management for test execution."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.cpu_budgets: Dict[str, CPUBudget] = {}
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.start_time: Optional[float] = None
        self.peak_cpu = 0.0
        self.throttle_callbacks: List[Callable] = []
        
        # Default budgets by test category
        self.default_budgets = {
            'unit': CPUBudget(30.0, 10.0, 25.0, 2),
            'integration': CPUBudget(50.0, 30.0, 40.0, 4),
            'edge_case': CPUBudget(70.0, 60.0, 60.0, 6),
            'e2e': CPUBudget(80.0, 120.0, 70.0, 8),
            'performance': CPUBudget(90.0, 300.0, 80.0, multiprocessing.cpu_count())
        }
    
    def set_cpu_budget(self, test_category: str, budget: CPUBudget):
        """Set CPU budget for test category."""
        self.cpu_budgets[test_category] = budget
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        return self.process.cpu_percent(interval=0.1)
    
    def start_monitoring(self, test_category: str = 'integration'):
        """Start CPU monitoring for test execution."""
        budget = self.cpu_budgets.get(test_category, self.default_budgets[test_category])
        
        self.monitoring_active = True
        self.start_time = time.perf_counter()
        self.peak_cpu = 0.0
        
        def monitor_cpu():
            while self.monitoring_active:
                current_cpu = self.get_cpu_usage()
                self.peak_cpu = max(self.peak_cpu, current_cpu)
                execution_time = time.perf_counter() - self.start_time
                
                # Check time budget
                if execution_time > budget.max_execution_time:
                    raise TimeoutError(
                        f"Test execution time {execution_time:.1f}s exceeds limit {budget.max_execution_time}s"
                    )
                
                # Check CPU budget
                if current_cpu > budget.max_cpu_percent:
                    # Trigger throttling
                    for callback in self.throttle_callbacks:
                        try:
                            callback(current_cpu, budget.max_cpu_percent)
                        except Exception:
                            pass
                    
                    time.sleep(0.5)  # Brief pause to reduce CPU
                
                elif current_cpu > budget.throttle_threshold:
                    time.sleep(0.1)  # Gentle throttling
                
                time.sleep(0.5)  # Monitor interval
        
        self.monitor_thread = threading.Thread(target=monitor_cpu, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, float]:
        """Stop monitoring and return CPU statistics."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        execution_time = time.perf_counter() - self.start_time if self.start_time else 0.0
        final_cpu = self.get_cpu_usage()
        
        return {
            'peak_cpu_percent': self.peak_cpu,
            'final_cpu_percent': final_cpu,
            'execution_time_seconds': execution_time
        }
    
    def register_throttle_callback(self, callback: Callable[[float, float], None]):
        """Register callback for CPU throttling events."""
        self.throttle_callbacks.append(callback)
    
    @contextmanager
    def managed_cpu(self, test_category: str = 'integration'):
        """Context manager for managed CPU execution."""
        self.start_monitoring(test_category)
        try:
            yield self
        finally:
            self.stop_monitoring()


# Parallel execution utilities with resource limits
class ParallelExecutionManager:
    """Manages parallel execution with resource constraints."""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(4, multiprocessing.cpu_count())
        self.active_futures = []
    
    @contextmanager
    def thread_pool_executor(self, max_workers: Optional[int] = None):
        """Provide thread pool executor with resource limits."""
        workers = max_workers or self.max_workers
        with ThreadPoolExecutor(max_workers=workers) as executor:
            yield executor
    
    @contextmanager
    def process_pool_executor(self, max_workers: Optional[int] = None):
        """Provide process pool executor with resource limits."""
        workers = max_workers or min(self.max_workers, multiprocessing.cpu_count())
        with ProcessPoolExecutor(max_workers=workers) as executor:
            yield executor
    
    def execute_with_budget(self, operations: List[Callable], 
                          cpu_budget: CPUBudget,
                          use_processes: bool = False):
        """Execute operations within CPU budget constraints."""
        max_concurrent = min(len(operations), cpu_budget.max_concurrent_operations)
        
        if use_processes:
            executor_context = self.process_pool_executor(max_concurrent)
        else:
            executor_context = self.thread_pool_executor(max_concurrent)
        
        with executor_context as executor:
            # Submit operations
            futures = [executor.submit(op) for op in operations[:max_concurrent]]
            results = []
            
            # Collect results with timeout
            for future in as_completed(futures, timeout=cpu_budget.max_execution_time):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(e)
            
            return results


class CPUThrottleManager:
    """Manages CPU throttling strategies."""
    
    def __init__(self):
        self.throttle_events = []
        self.current_throttle_level = 0.0
    
    def adaptive_throttle(self, current_cpu: float, max_cpu: float):
        """Adaptive CPU throttling based on current usage."""
        if current_cpu > max_cpu:
            # Calculate throttle level based on how much we're over
            overage_factor = (current_cpu - max_cpu) / max_cpu
            throttle_time = min(1.0, 0.1 * (1 + overage_factor))
            
            self.throttle_events.append({
                'timestamp': time.time(),
                'cpu_percent': current_cpu,
                'throttle_seconds': throttle_time
            })
            
            time.sleep(throttle_time)
            self.current_throttle_level = throttle_time
    
    def get_throttle_statistics(self) -> Dict[str, float]:
        """Get throttling statistics."""
        if not self.throttle_events:
            return {'throttle_events': 0, 'total_throttle_time': 0.0}
        
        total_time = sum(event['throttle_seconds'] for event in self.throttle_events)
        avg_cpu = sum(event['cpu_percent'] for event in self.throttle_events) / len(self.throttle_events)
        
        return {
            'throttle_events': len(self.throttle_events),
            'total_throttle_time': total_time,
            'average_cpu_during_throttle': avg_cpu,
            'current_throttle_level': self.current_throttle_level
        }


@pytest.fixture(scope="function")
def cpu_manager():
    """Provide CPU management for each test."""
    manager = CPUManager()
    try:
        yield manager
    finally:
        manager.stop_monitoring()


@pytest.fixture(scope="function")
def parallel_executor():
    """Provide parallel execution manager."""
    return ParallelExecutionManager()


@pytest.fixture(scope="function")
def cpu_throttle_manager():
    """Provide CPU throttle management."""
    return CPUThrottleManager()


class CPUIntensiveTestManager:
    """Manages CPU-intensive test operations with intelligent optimization."""
    
    def __init__(self, cpu_manager: CPUManager):
        self.cpu_manager = cpu_manager
        self.operation_cache = {}
        self.optimization_strategies = {
            'batch_processing': self._batch_process_operations,
            'intelligent_sampling': self._sample_operations,
            'parallel_chunks': self._parallelize_operations
        }
    
    def _batch_process_operations(self, operations: List[Callable], batch_size: int = 10):
        """Process operations in batches to reduce CPU spikes."""
        results = []
        for i in range(0, len(operations), batch_size):
            batch = operations[i:i + batch_size]
            batch_results = [op() for op in batch]
            results.extend(batch_results)
            
            # Small pause between batches
            time.sleep(0.1)
        
        return results
    
    def _sample_operations(self, operations: List[Callable], sample_rate: float = 0.1):
        """Sample operations to reduce total CPU load."""
        import random
        sample_size = max(1, int(len(operations) * sample_rate))
        sampled_ops = random.sample(operations, sample_size)
        return [op() for op in sampled_ops]
    
    def _parallelize_operations(self, operations: List[Callable], max_workers: int = 2):
        """Parallelize operations with controlled concurrency."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(op) for op in operations]
            results = []
            
            for future in as_completed(futures, timeout=30.0):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append(e)
            
            return results
    
    def execute_cpu_intensive_test(self, operations: List[Callable], 
                                 strategy: str = 'batch_processing',
                                 **strategy_params) -> List[Any]:
        """Execute CPU-intensive test with optimization strategy."""
        if strategy not in self.optimization_strategies:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        strategy_func = self.optimization_strategies[strategy]
        return strategy_func(operations, **strategy_params)


@pytest.fixture(scope="function")
def cpu_intensive_manager(cpu_manager):
    """Provide CPU-intensive test manager."""
    return CPUIntensiveTestManager(cpu_manager)


# CPU monitoring decorators
def cpu_limit(max_cpu_percent: float, max_execution_time: float = 60.0):
    """Decorator to enforce CPU limits on test functions."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            manager = CPUManager()
            budget = CPUBudget(max_cpu_percent, max_execution_time, max_cpu_percent * 0.8, 4)
            manager.set_cpu_budget('custom', budget)
            
            with manager.managed_cpu('custom'):
                return test_func(*args, **kwargs)
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


def with_cpu_throttling(throttle_threshold: float = 50.0):
    """Decorator to add CPU throttling to test functions."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            throttle_manager = CPUThrottleManager()
            
            def throttle_callback(current_cpu: float, max_cpu: float):
                throttle_manager.adaptive_throttle(current_cpu, max_cpu)
            
            manager = CPUManager()
            manager.register_throttle_callback(throttle_callback)
            
            with manager.managed_cpu():
                result = test_func(*args, **kwargs)
                
                # Log throttling statistics
                stats = throttle_manager.get_throttle_statistics()
                if stats['throttle_events'] > 0:
                    print(f"\nCPU Throttling Stats: {stats}")
                
                return result
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


# System CPU monitoring utilities
def get_system_cpu_info() -> Dict[str, Any]:
    """Get comprehensive system CPU information."""
    return {
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'cpu_count_physical': psutil.cpu_count(logical=False),
        'cpu_percent_per_cpu': psutil.cpu_percent(percpu=True, interval=1.0),
        'cpu_percent_total': psutil.cpu_percent(interval=1.0),
        'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
        'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
    }


def wait_for_cpu_cooldown(target_cpu: float = 20.0, timeout: float = 30.0):
    """Wait for system CPU to cool down below target percentage."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        current_cpu = psutil.cpu_percent(interval=1.0)
        if current_cpu <= target_cpu:
            return True
        time.sleep(1.0)
    
    return False


# Export commonly used components
__all__ = [
    'CPUManager', 'CPUBudget', 'ParallelExecutionManager', 'CPUThrottleManager',
    'CPUIntensiveTestManager', 'cpu_manager', 'parallel_executor', 'cpu_throttle_manager',
    'cpu_intensive_manager', 'cpu_limit', 'with_cpu_throttling', 'get_system_cpu_info',
    'wait_for_cpu_cooldown'
]