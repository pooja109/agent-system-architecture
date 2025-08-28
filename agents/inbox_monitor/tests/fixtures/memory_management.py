"""
Advanced memory management for resource-intensive tests.

This module provides comprehensive memory management to safely execute tests that would
otherwise exhaust system memory, particularly those with large data processing patterns.
"""
import pytest
import gc
import psutil
import sys
import weakref
import threading
import time
from typing import Dict, List, Optional, Any, Callable, Iterator
from dataclasses import dataclass
from contextlib import contextmanager
from unittest import mock


@dataclass
class MemoryBudget:
    """Memory budget allocation for test execution."""
    max_memory_mb: float
    warning_threshold_mb: float
    critical_threshold_mb: float
    cleanup_interval_seconds: float = 5.0


class MemoryManager:
    """Advanced memory management for test execution."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.memory_budgets: Dict[str, MemoryBudget] = {}
        self.allocated_objects: List[weakref.ref] = []
        self.cleanup_callbacks: List[Callable] = []
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.peak_memory = 0.0
        
        # Default budgets by test category
        self.default_budgets = {
            'unit': MemoryBudget(50.0, 40.0, 45.0),
            'integration': MemoryBudget(100.0, 80.0, 90.0),
            'edge_case': MemoryBudget(200.0, 160.0, 180.0),  # Higher for resource-intensive
            'e2e': MemoryBudget(300.0, 240.0, 270.0),
            'performance': MemoryBudget(500.0, 400.0, 450.0)  # Highest for performance tests
        }
    
    def set_memory_budget(self, test_category: str, budget: MemoryBudget):
        """Set memory budget for test category."""
        self.memory_budgets[test_category] = budget
    
    def get_current_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def start_monitoring(self, test_category: str = 'integration'):
        """Start memory monitoring for test execution."""
        budget = self.memory_budgets.get(test_category, self.default_budgets.get(test_category, self.default_budgets['integration']))
        
        self.monitoring_active = True
        self.peak_memory = self.get_current_memory_usage()
        
        def monitor_memory():
            while self.monitoring_active:
                current_memory = self.get_current_memory_usage()
                self.peak_memory = max(self.peak_memory, current_memory)
                
                if current_memory > budget.critical_threshold_mb:
                    # Critical memory usage - force cleanup
                    self.force_cleanup()
                    
                    # If still over critical, raise exception
                    if self.get_current_memory_usage() > budget.critical_threshold_mb:
                        raise MemoryError(
                            f"Critical memory usage: {current_memory:.1f}MB > {budget.critical_threshold_mb}MB"
                        )
                
                elif current_memory > budget.warning_threshold_mb:
                    # Warning level - gentle cleanup
                    self.gentle_cleanup()
                
                time.sleep(budget.cleanup_interval_seconds)
        
        self.monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, float]:
        """Stop monitoring and return memory statistics."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        final_memory = self.get_current_memory_usage()
        return {
            'peak_memory_mb': self.peak_memory,
            'final_memory_mb': final_memory,
            'memory_delta_mb': final_memory - (self.peak_memory - final_memory)
        }
    
    def gentle_cleanup(self):
        """Perform gentle memory cleanup."""
        # Run garbage collection
        gc.collect()
        
        # Call custom cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception:
                pass
    
    def force_cleanup(self):
        """Force aggressive memory cleanup."""
        # Aggressive garbage collection
        for _ in range(3):
            gc.collect()
        
        # Clean up tracked objects
        dead_refs = []
        for ref in self.allocated_objects:
            if ref() is None:
                dead_refs.append(ref)
        
        for dead_ref in dead_refs:
            self.allocated_objects.remove(dead_ref)
        
        # Run all cleanup callbacks
        self.gentle_cleanup()
    
    def register_large_object(self, obj: Any, cleanup_callback: Optional[Callable] = None):
        """Register large object for tracking and cleanup."""
        weak_ref = weakref.ref(obj)
        self.allocated_objects.append(weak_ref)
        
        if cleanup_callback:
            self.cleanup_callbacks.append(cleanup_callback)
    
    @contextmanager
    def managed_memory(self, test_category: str = 'integration'):
        """Context manager for managed memory execution."""
        self.start_monitoring(test_category)
        try:
            yield self
        finally:
            stats = self.stop_monitoring()
            self.force_cleanup()


# Data sampling utilities for large datasets
class DataSampler:
    """Utilities for sampling large datasets in tests."""
    
    @staticmethod
    def sample_range(start: int, stop: int, max_samples: int = 100) -> Iterator[int]:
        """Sample from a large range instead of processing all values."""
        total_range = stop - start
        if total_range <= max_samples:
            yield from range(start, stop)
        else:
            # Geometric sampling for better coverage
            step = max(1, total_range // max_samples)
            for i in range(start, stop, step):
                yield i
            
            # Always include the last value
            if stop - 1 not in range(start, stop, step):
                yield stop - 1
    
    @staticmethod
    def sample_list(data: List[Any], max_samples: int = 100) -> List[Any]:
        """Sample from a large list."""
        if len(data) <= max_samples:
            return data
        
        # Stratified sampling
        step = len(data) // max_samples
        sampled = data[::step]
        
        # Ensure we have exactly max_samples or fewer
        return sampled[:max_samples]
    
    @staticmethod
    def create_test_data(size: int, max_size: int = 1000) -> List[Dict[str, Any]]:
        """Create test data with size limits."""
        actual_size = min(size, max_size)
        return [
            {
                'id': i,
                'data': f'test_data_{i}',
                'value': i,  # Use i instead of i*2 to get both even and odd numbers
                'metadata': {'index': i, 'category': 'test'}
            }
            for i in range(actual_size)
        ]
    
    @staticmethod
    def create_test_recipients(count: int, max_count: int = 100) -> List[Dict[str, Any]]:
        """Create test email recipients with count limits to prevent memory exhaustion."""
        actual_count = min(count, max_count)
        return [
            {"emailAddress": {"address": f"user{i}@example.com", "name": f"Test User {i}"}}
            for i in range(actual_count)
        ]
    
    @staticmethod
    def create_test_categories(count: int, max_count: int = 50) -> List[str]:
        """Create test categories with count limits."""
        actual_count = min(count, max_count)
        return [f"Category{i}" for i in range(actual_count)]
    
    @staticmethod
    def create_test_headers(count: int, max_count: int = 100) -> List[Dict[str, str]]:
        """Create test headers with count limits."""
        actual_count = min(count, max_count)
        return [
            {"name": f"Header{i}", "value": f"Value{i}"}
            for i in range(actual_count)
        ]


@pytest.fixture(scope="function")
def memory_manager():
    """Provide memory management for each test."""
    manager = MemoryManager()
    try:
        yield manager
    finally:
        manager.stop_monitoring()
        manager.force_cleanup()


@pytest.fixture(scope="function") 
def data_sampler():
    """Provide data sampling utilities."""
    return DataSampler()


@pytest.fixture(scope="function")
def managed_memory_test(memory_manager):
    """Automatically manage memory for tests."""
    with memory_manager.managed_memory('integration') as manager:
        yield manager

@pytest.fixture(scope="function")
def managed_memory_edge_case(memory_manager):
    """Automatically manage memory for edge case tests with higher limits."""
    with memory_manager.managed_memory('edge_case') as manager:
        yield manager


class MemoryProfiler:
    """Memory profiler for detailed memory analysis."""
    
    def __init__(self):
        self.snapshots = []
        self.process = psutil.Process()
        
    def take_snapshot(self, label: str):
        """Take a memory snapshot with label."""
        try:
            memory_info = self.process.memory_info()
            snapshot = {
                'label': label,
                'timestamp': time.time(),
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': self.process.memory_percent(),
                'num_threads': self.process.num_threads()
            }
            self.snapshots.append(snapshot)
            return snapshot
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def get_memory_growth(self) -> Dict[str, float]:
        """Calculate memory growth between first and last snapshots."""
        if len(self.snapshots) < 2:
            return {}
        
        first = self.snapshots[0]
        last = self.snapshots[-1]
        
        return {
            'rss_growth_mb': last['rss_mb'] - first['rss_mb'],
            'vms_growth_mb': last['vms_mb'] - first['vms_mb'],
            'percent_growth': last['percent'] - first['percent'],
            'duration_seconds': last['timestamp'] - first['timestamp']
        }
    
    def get_peak_memory(self) -> Dict[str, float]:
        """Get peak memory usage from snapshots."""
        if not self.snapshots:
            return {}
        
        peak_rss = max(s['rss_mb'] for s in self.snapshots)
        peak_vms = max(s['vms_mb'] for s in self.snapshots)
        peak_percent = max(s['percent'] for s in self.snapshots)
        
        return {
            'peak_rss_mb': peak_rss,
            'peak_vms_mb': peak_vms,
            'peak_percent': peak_percent
        }


@pytest.fixture(scope="function")
def memory_profiler():
    """Provide memory profiler for detailed analysis."""
    profiler = MemoryProfiler()
    profiler.take_snapshot('test_start')
    yield profiler
    profiler.take_snapshot('test_end')


# Memory-aware test decorators
def memory_limit(max_memory_mb: float):
    """Decorator to enforce memory limits on test functions."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            manager = MemoryManager()
            budget = MemoryBudget(max_memory_mb, max_memory_mb * 0.8, max_memory_mb * 0.9)
            manager.set_memory_budget('custom', budget)
            
            with manager.managed_memory('custom'):
                return test_func(*args, **kwargs)
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


def with_data_sampling(max_items: int = 100):
    """Decorator to provide data sampling utilities with custom limits."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            sampler = DataSampler()
            # Override default limits
            original_methods = {}
            
            # Save original methods
            original_methods['create_test_recipients'] = sampler.create_test_recipients
            original_methods['create_test_categories'] = sampler.create_test_categories 
            original_methods['create_test_headers'] = sampler.create_test_headers
            
            # Create custom methods with new limits
            def limited_recipients(count, max_count=max_items):
                return original_methods['create_test_recipients'](count, max_count)
            def limited_categories(count, max_count=max_items):
                return original_methods['create_test_categories'](count, max_count)
            def limited_headers(count, max_count=max_items):
                return original_methods['create_test_headers'](count, max_count)
            
            # Patch methods
            sampler.create_test_recipients = limited_recipients
            sampler.create_test_categories = limited_categories
            sampler.create_test_headers = limited_headers
            
            try:
                # Inject sampler into kwargs if expected
                if 'data_sampler' in test_func.__code__.co_varnames:
                    kwargs['data_sampler'] = sampler
                return test_func(*args, **kwargs)
            finally:
                # Restore original methods
                for method_name, original_method in original_methods.items():
                    setattr(sampler, method_name, original_method)
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


# Export commonly used components
__all__ = [
    'MemoryManager', 'MemoryBudget', 'DataSampler', 'MemoryProfiler',
    'memory_manager', 'data_sampler', 'managed_memory_test', 'memory_profiler',
    'memory_limit', 'with_data_sampling'
]