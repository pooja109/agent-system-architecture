"""
Load testing framework for performance validation within source constraints.
"""
import asyncio
import concurrent.futures
import threading
import time
from contextlib import contextmanager
from typing import Callable, List, Dict, Any, Optional, Union, Tuple
import pytest
import statistics


class LoadTestExecutor:
    """
    Execute load tests with concurrency control and performance monitoring.
    """
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.results = []
        self.errors = []
    
    def execute_concurrent_load(
        self,
        target_function: Callable,
        test_data: List[Any],
        concurrency_level: int = 5,
        duration_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute load test with specified concurrency.
        
        Args:
            target_function: Function to test under load
            test_data: List of data to pass to target function
            concurrency_level: Number of concurrent executions
            duration_seconds: Maximum duration for load test
            
        Returns:
            Dictionary with load test results
        """
        # Input validation with enhanced error messages
        if target_function is None:
            raise ValueError("Target function cannot be None for load testing")
        
        if not callable(target_function):
            raise TypeError(f"Target function must be callable, got: {type(target_function).__name__}")
        
        if not test_data:
            raise ValueError("Test data list cannot be empty for load testing")
        
        if not isinstance(concurrency_level, int) or concurrency_level <= 0:
            raise ValueError(f"Concurrency level must be a positive integer, got: {concurrency_level}")
        
        if duration_seconds is not None and (not isinstance(duration_seconds, int) or duration_seconds <= 0):
            raise ValueError(f"Duration seconds must be a positive integer or None, got: {duration_seconds}")
        
        start_time = time.time()
        self.results.clear()
        self.errors.clear()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency_level) as executor:
            # Submit all tasks
            futures = []
            for data_item in test_data:
                if duration_seconds:
                    # Check if we've exceeded duration
                    if time.time() - start_time > duration_seconds:
                        break
                
                future = executor.submit(self._execute_single_test, target_function, data_item)
                futures.append(future)
            
            # Wait for completion with timeout
            timeout = duration_seconds if duration_seconds else 60
            completed_futures = concurrent.futures.as_completed(futures, timeout=timeout)
            
            for future in completed_futures:
                try:
                    result = future.result(timeout=5)
                    self.results.append(result)
                except concurrent.futures.TimeoutError:
                    self.errors.append({"error": "timeout", "timestamp": time.time()})
                except Exception as e:
                    self.errors.append({"error": str(e), "timestamp": time.time()})
        
        end_time = time.time()
        
        return self._calculate_load_test_metrics(start_time, end_time)
    
    def _execute_single_test(self, target_function: Callable, data: Any) -> Dict[str, Any]:
        """
        Execute a single test iteration with timing.
        
        Args:
            target_function: Function to execute
            data: Data to pass to function
            
        Returns:
            Dictionary with execution results
        """
        start_time = time.time()
        
        try:
            result = target_function(data)
            end_time = time.time()
            
            return {
                'success': True,
                'execution_time': end_time - start_time,
                'result': result,
                'timestamp': start_time
            }
        
        except Exception as e:
            end_time = time.time()
            return {
                'success': False,
                'execution_time': end_time - start_time,
                'error': str(e),
                'timestamp': start_time
            }
    
    def _calculate_load_test_metrics(self, start_time: float, end_time: float) -> Dict[str, Any]:
        """
        Calculate performance metrics from load test results.
        
        Args:
            start_time: Load test start time
            end_time: Load test end time
            
        Returns:
            Dictionary with performance metrics
        """
        total_duration = end_time - start_time
        successful_results = [r for r in self.results if r.get('success', False)]
        failed_results = [r for r in self.results if not r.get('success', False)]
        
        execution_times = [r['execution_time'] for r in successful_results]
        
        metrics = {
            'total_duration': total_duration,
            'total_requests': len(self.results) + len(self.errors),
            'successful_requests': len(successful_results),
            'failed_requests': len(failed_results) + len(self.errors),
            'success_rate': len(successful_results) / (len(self.results) + len(self.errors)) if self.results or self.errors else 0,
            'requests_per_second': (len(self.results) + len(self.errors)) / total_duration if total_duration > 0 else 0
        }
        
        if execution_times:
            metrics.update({
                'avg_response_time': statistics.mean(execution_times),
                'min_response_time': min(execution_times),
                'max_response_time': max(execution_times),
                'median_response_time': statistics.median(execution_times),
                'p95_response_time': self._calculate_percentile(execution_times, 95),
                'p99_response_time': self._calculate_percentile(execution_times, 99)
            })
        
        return metrics
    
    @staticmethod
    def _calculate_percentile(values: List[float], percentile: int) -> float:
        """Calculate percentile value from list of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        if index >= len(sorted_values):
            index = len(sorted_values) - 1
        
        return sorted_values[index]


class MemoryLoadTester:
    """
    Specialized load tester for memory-intensive operations.
    """
    
    def __init__(self):
        self.memory_snapshots = []
    
    @contextmanager
    def monitor_memory_usage(self):
        """Context manager to monitor memory usage during load testing."""
        try:
            import psutil
            process = psutil.Process()
        except ImportError:
            # Fallback if psutil not available
            yield {"memory_monitoring": "unavailable"}
            return
        
        initial_memory = process.memory_info().rss
        self.memory_snapshots = [initial_memory]
        
        # Start memory monitoring thread
        monitoring_active = threading.Event()
        monitoring_active.set()
        
        def memory_monitor():
            while monitoring_active.is_set():
                try:
                    current_memory = process.memory_info().rss
                    self.memory_snapshots.append(current_memory)
                    time.sleep(0.1)  # Monitor every 100ms
                except Exception:
                    break
        
        monitor_thread = threading.Thread(target=memory_monitor, daemon=True)
        monitor_thread.start()
        
        try:
            yield  # Allow the context manager to be used
        finally:
            monitoring_active.clear()
            monitor_thread.join(timeout=1)
            
            # Create memory metrics but don't yield them again
            final_memory = process.memory_info().rss
            memory_growth = final_memory - initial_memory
            max_memory = max(self.memory_snapshots) if self.memory_snapshots else final_memory
            
            # Store results in instance for retrieval
            self.memory_metrics = {
                'initial_memory_mb': initial_memory // (1024 * 1024),
                'final_memory_mb': final_memory // (1024 * 1024),
                'max_memory_mb': max_memory // (1024 * 1024),
                'memory_growth_mb': memory_growth // (1024 * 1024),
                'memory_samples': len(self.memory_snapshots)
            }
    
    def get_memory_metrics(self):
        """Get the memory metrics from the last monitoring session."""
        return getattr(self, 'memory_metrics', {'memory_monitoring': 'not_run'})


class AsyncLoadTester:
    """
    Load tester specialized for async operations.
    """
    
    @staticmethod
    async def execute_async_load(
        async_function: Callable,
        test_data: List[Any],
        concurrency_level: int = 10,
        max_duration: int = 30
    ) -> Dict[str, Any]:
        """
        Execute async load test with proper resource management.
        
        Args:
            async_function: Async function to test
            test_data: Test data list
            concurrency_level: Number of concurrent async operations
            max_duration: Maximum test duration in seconds
            
        Returns:
            Load test results
        """
        start_time = time.time()
        results = []
        errors = []
        
        semaphore = asyncio.Semaphore(concurrency_level)
        
        async def execute_single_async(data):
            async with semaphore:
                execution_start = time.time()
                try:
                    result = await async_function(data)
                    execution_time = time.time() - execution_start
                    return {
                        'success': True,
                        'execution_time': execution_time,
                        'result': result
                    }
                except Exception as e:
                    execution_time = time.time() - execution_start
                    return {
                        'success': False,
                        'execution_time': execution_time,
                        'error': str(e)
                    }
        
        # Create tasks with timeout
        tasks = []
        for data_item in test_data:
            if time.time() - start_time > max_duration:
                break
            task = asyncio.create_task(execute_single_async(data_item))
            tasks.append(task)
        
        # Execute with timeout
        try:
            completed_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=max_duration
            )
            
            for result in completed_results:
                if isinstance(result, dict):
                    if result.get('success', False):
                        results.append(result)
                    else:
                        errors.append(result)
                else:
                    errors.append({'error': str(result), 'success': False})
        
        except asyncio.TimeoutError:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            errors.append({'error': 'Global timeout exceeded', 'success': False})
        
        total_duration = time.time() - start_time
        
        return {
            'total_duration': total_duration,
            'successful_operations': len(results),
            'failed_operations': len(errors),
            'avg_response_time': statistics.mean([r['execution_time'] for r in results]) if results else 0,
            'operations_per_second': len(results) / total_duration if total_duration > 0 else 0
        }


@pytest.fixture
def load_test_executor():
    """Fixture providing load test execution capabilities."""
    return LoadTestExecutor()


@pytest.fixture
def memory_load_tester():
    """Fixture providing memory load testing capabilities."""
    return MemoryLoadTester()


@pytest.fixture
def async_load_tester():
    """Fixture providing async load testing capabilities."""
    return AsyncLoadTester()