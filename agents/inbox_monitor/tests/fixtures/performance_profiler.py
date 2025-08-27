# TEMPLATE: Comprehensive Performance Measurement

import time
import asyncio
import functools
from typing import Dict, List, Tuple
import pytest

class PerformanceProfiler:
    """Template for detailed test performance profiling."""
    
    def __init__(self):
        self.measurements = {}
        self.benchmarks = {
            'fast': 5.0,    # 5 seconds max for fast tests
            'medium': 30.0, # 30 seconds max for medium tests  
            'slow': 300.0   # 300 seconds max for slow tests
        }
    
    def measure_test(self, test_category: str = 'fast'):
        """Decorator to measure test performance and validate against benchmarks."""
        def decorator(test_func):
            @functools.wraps(test_func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await test_func(*args, **kwargs)
                except Exception as e:
                    # Still record timing even for failed tests
                    execution_time = time.time() - start_time
                    self.measurements[test_func.__name__] = {
                        'time': execution_time,
                        'status': 'failed',
                        'category': test_category
                    }
                    raise e
                
                execution_time = time.time() - start_time
                self.measurements[test_func.__name__] = {
                    'time': execution_time,
                    'status': 'passed',
                    'category': test_category
                }
                
                # Validate against benchmark
                benchmark = self.benchmarks.get(test_category, 5.0)
                if execution_time > benchmark:
                    pytest.fail(f"Performance regression: {test_func.__name__} took {execution_time:.2f}s "
                              f"(benchmark: {benchmark}s for {test_category} tests)")
                
                return result
            
            @functools.wraps(test_func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = test_func(*args, **kwargs)
                except Exception as e:
                    execution_time = time.time() - start_time
                    self.measurements[test_func.__name__] = {
                        'time': execution_time,
                        'status': 'failed',
                        'category': test_category
                    }
                    raise e
                
                execution_time = time.time() - start_time
                self.measurements[test_func.__name__] = {
                    'time': execution_time,
                    'status': 'passed',
                    'category': test_category
                }
                
                benchmark = self.benchmarks.get(test_category, 5.0)
                if execution_time > benchmark:
                    pytest.fail(f"Performance regression: {test_func.__name__} took {execution_time:.2f}s "
                              f"(benchmark: {benchmark}s for {test_category} tests)")
                
                return result
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(test_func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def generate_performance_report(self) -> str:
        """Generate detailed performance analysis report."""
        if not self.measurements:
            return "No performance measurements recorded"
        
        report = ["Performance Analysis Report", "=" * 30]
        
        by_category = {}
        for test_name, data in self.measurements.items():
            category = data['category']
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((test_name, data))
        
        for category, tests in by_category.items():
            report.append(f"\n{category.upper()} Tests:")
            report.append(f"Benchmark: {self.benchmarks.get(category, 5.0)}s")
            
            times = [data['time'] for _, data in tests]
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)
            
            report.append(f"Average: {avg_time:.2f}s, Min: {min_time:.2f}s, Max: {max_time:.2f}s")
            
            # Show slowest tests
            sorted_tests = sorted(tests, key=lambda x: x[1]['time'], reverse=True)[:5]
            for test_name, data in sorted_tests:
                status_icon = "✅" if data['status'] == 'passed' else "❌"
                report.append(f"  {status_icon} {test_name}: {data['time']:.2f}s")
        
        return "\n".join(report)

# Global profiler instance for test measurement
profiler = PerformanceProfiler()