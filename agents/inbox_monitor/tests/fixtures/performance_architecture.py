"""
Dedicated performance testing architecture separate from unit tests.

This module provides a sophisticated performance testing framework that operates
independently from the standard unit test suite, with baseline tracking,
regression detection, and comprehensive performance reporting.
"""
import pytest
import time
import statistics
import json
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import contextmanager


@dataclass
class PerformanceBenchmark:
    """Performance benchmark definition."""
    name: str
    description: str
    target_function: Callable
    setup_function: Optional[Callable] = None
    teardown_function: Optional[Callable] = None
    iterations: int = 10
    warmup_iterations: int = 3
    max_execution_time: float = 300.0
    success_criteria: Dict[str, float] = field(default_factory=dict)


@dataclass  
class PerformanceResult:
    """Performance test result."""
    benchmark_name: str
    execution_times: List[float]
    mean_time: float
    median_time: float
    std_deviation: float
    min_time: float
    max_time: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceTestingFramework:
    """Dedicated framework for performance testing separate from unit tests."""
    
    def __init__(self):
        self.benchmarks: Dict[str, PerformanceBenchmark] = {}
        self.results: List[PerformanceResult] = []
        self.baseline_results: Dict[str, PerformanceResult] = {}
        self.performance_history: List[Dict[str, Any]] = []
        
        # Load baseline results if available
        self.load_baseline_results()
    
    def register_benchmark(self, benchmark: PerformanceBenchmark):
        """Register a performance benchmark."""
        self.benchmarks[benchmark.name] = benchmark
    
    def run_benchmark(self, benchmark_name: str) -> PerformanceResult:
        """Run a single performance benchmark."""
        if benchmark_name not in self.benchmarks:
            raise ValueError(f"Benchmark '{benchmark_name}' not found")
        
        benchmark = self.benchmarks[benchmark_name]
        execution_times = []
        error_message = None
        
        try:
            # Setup if required
            if benchmark.setup_function:
                setup_context = benchmark.setup_function()
            else:
                setup_context = None
            
            # Warmup iterations
            for _ in range(benchmark.warmup_iterations):
                try:
                    start_time = time.perf_counter()
                    if setup_context:
                        benchmark.target_function(setup_context)
                    else:
                        benchmark.target_function()
                    end_time = time.perf_counter()
                except Exception:
                    pass  # Ignore warmup errors
            
            # Actual benchmark iterations
            for i in range(benchmark.iterations):
                try:
                    start_time = time.perf_counter()
                    
                    if setup_context:
                        result = benchmark.target_function(setup_context)
                    else:
                        result = benchmark.target_function()
                    
                    end_time = time.perf_counter()
                    execution_time = end_time - start_time
                    
                    # Check for maximum execution time
                    if execution_time > benchmark.max_execution_time:
                        error_message = f"Execution time {execution_time:.3f}s exceeds maximum {benchmark.max_execution_time}s"
                        break
                    
                    execution_times.append(execution_time)
                    
                except Exception as e:
                    error_message = f"Benchmark iteration {i} failed: {str(e)}"
                    break
            
            # Teardown if required
            if benchmark.teardown_function:
                try:
                    benchmark.teardown_function(setup_context)
                except Exception:
                    pass  # Best effort cleanup
            
        except Exception as e:
            error_message = f"Benchmark setup failed: {str(e)}"
        
        # Calculate statistics
        if execution_times:
            mean_time = statistics.mean(execution_times)
            median_time = statistics.median(execution_times)
            std_deviation = statistics.stdev(execution_times) if len(execution_times) > 1 else 0.0
            min_time = min(execution_times)
            max_time = max(execution_times)
            
            # Check success criteria
            success = self.evaluate_success_criteria(benchmark, mean_time, std_deviation)
        else:
            mean_time = median_time = std_deviation = min_time = max_time = 0.0
            success = False
        
        result = PerformanceResult(
            benchmark_name=benchmark_name,
            execution_times=execution_times,
            mean_time=mean_time,
            median_time=median_time,
            std_deviation=std_deviation,
            min_time=min_time,
            max_time=max_time,
            success=success and error_message is None,
            error_message=error_message
        )
        
        self.results.append(result)
        return result
    
    def evaluate_success_criteria(self, benchmark: PerformanceBenchmark, 
                                mean_time: float, std_deviation: float) -> bool:
        """Evaluate if benchmark meets success criteria."""
        if not benchmark.success_criteria:
            return True  # No criteria means success
        
        for criterion, threshold in benchmark.success_criteria.items():
            if criterion == 'max_mean_time' and mean_time > threshold:
                return False
            elif criterion == 'max_std_deviation' and std_deviation > threshold:
                return False
            elif criterion == 'min_iterations' and len(self.results) > 0:
                if len(self.results[-1].execution_times) < threshold:
                    return False
        
        return True
    
    def run_all_benchmarks(self) -> List[PerformanceResult]:
        """Run all registered benchmarks."""
        results = []
        for benchmark_name in self.benchmarks:
            result = self.run_benchmark(benchmark_name)
            results.append(result)
        return results
    
    def compare_with_baseline(self, result: PerformanceResult) -> Dict[str, float]:
        """Compare result with baseline performance."""
        if result.benchmark_name not in self.baseline_results:
            return {'status': 'no_baseline'}
        
        baseline = self.baseline_results[result.benchmark_name]
        
        comparison = {
            'mean_time_ratio': result.mean_time / baseline.mean_time if baseline.mean_time > 0 else float('inf'),
            'median_time_ratio': result.median_time / baseline.median_time if baseline.median_time > 0 else float('inf'),
            'improvement_percent': ((baseline.mean_time - result.mean_time) / baseline.mean_time) * 100 if baseline.mean_time > 0 else 0.0
        }
        
        return comparison
    
    def save_baseline_results(self, results_file: Path = Path('performance_baselines.json')):
        """Save current results as baseline."""
        baseline_data = {}
        for result in self.results:
            baseline_data[result.benchmark_name] = {
                'mean_time': result.mean_time,
                'median_time': result.median_time,
                'std_deviation': result.std_deviation,
                'min_time': result.min_time,
                'max_time': result.max_time
            }
        
        with open(results_file, 'w') as f:
            json.dump(baseline_data, f, indent=2)
    
    def load_baseline_results(self, results_file: Path = Path('performance_baselines.json')):
        """Load baseline results for comparison."""
        try:
            if results_file.exists():
                with open(results_file) as f:
                    baseline_data = json.load(f)
                
                for name, data in baseline_data.items():
                    self.baseline_results[name] = PerformanceResult(
                        benchmark_name=name,
                        execution_times=[],  # Historical data not stored
                        **data,
                        success=True
                    )
        except Exception:
            pass  # Baseline loading is optional
    
    def initialize_default_baselines(self):
        """Initialize default performance baselines for common benchmarks."""
        default_baselines = {
            'import_performance': {
                'mean_time': 0.5,  # 500ms for module imports
                'median_time': 0.4,
                'std_deviation': 0.1,
                'min_time': 0.3,
                'max_time': 0.8
            },
            'prompt_manager_cold_start': {
                'mean_time': 0.08,  # 80ms for cold start
                'median_time': 0.075,
                'std_deviation': 0.015,
                'min_time': 0.060,
                'max_time': 0.100
            },
            'prompt_manager_cache_performance': {
                'mean_time': 0.0005,  # 0.5ms for cache hits
                'median_time': 0.0004,
                'std_deviation': 0.0001,
                'min_time': 0.0003,
                'max_time': 0.0010
            },
            'concurrent_prompt_operations': {
                'mean_time': 1.5,  # 1.5s for concurrent operations
                'median_time': 1.4,
                'std_deviation': 0.3,
                'min_time': 1.0,
                'max_time': 2.0
            },
            'memory_usage_scaling': {
                'mean_time': 15.0,  # 15s for memory scaling test
                'median_time': 14.0,
                'std_deviation': 3.0,
                'min_time': 10.0,
                'max_time': 30.0
            }
        }
        
        for name, data in default_baselines.items():
            if name not in self.baseline_results:
                self.baseline_results[name] = PerformanceResult(
                    benchmark_name=name,
                    execution_times=[],
                    success=True,
                    **data
                )
    
    def validate_baseline_consistency(self) -> Dict[str, Any]:
        """Validate baseline consistency for CI/CD environments."""
        validation_report = {
            'timestamp': time.time(),
            'baselines_count': len(self.baseline_results),
            'missing_baselines': [],
            'inconsistent_baselines': [],
            'validation_passed': True
        }
        
        # Check for expected baselines
        expected_baselines = [
            'import_performance',
            'prompt_manager_cold_start', 
            'prompt_manager_cache_performance',
            'concurrent_prompt_operations',
            'memory_usage_scaling'
        ]
        
        for expected in expected_baselines:
            if expected not in self.baseline_results:
                validation_report['missing_baselines'].append(expected)
                validation_report['validation_passed'] = False
        
        # Check for baseline reasonableness
        for name, baseline in self.baseline_results.items():
            issues = []
            
            # Check for reasonable values
            if baseline.mean_time <= 0:
                issues.append('mean_time <= 0')
            if baseline.mean_time > 60:  # 60 seconds seems too long
                issues.append('mean_time > 60s')
            if baseline.std_deviation < 0:
                issues.append('negative std_deviation')
            if baseline.min_time > baseline.max_time:
                issues.append('min_time > max_time')
            if baseline.min_time > baseline.mean_time:
                issues.append('min_time > mean_time')
            if baseline.max_time < baseline.mean_time:
                issues.append('max_time < mean_time')
            
            if issues:
                validation_report['inconsistent_baselines'].append({
                    'baseline': name,
                    'issues': issues
                })
                validation_report['validation_passed'] = False
        
        return validation_report
    
    def reset_baselines(self):
        """Reset all baselines - useful for baseline regeneration."""
        self.baseline_results.clear()
        
        # Remove baseline file if it exists
        baseline_file = Path('performance_baselines.json')
        if baseline_file.exists():
            baseline_file.unlink()
    
    def export_baseline_report(self, report_file: Path = Path('baseline_report.json')) -> Dict[str, Any]:
        """Export comprehensive baseline report."""
        report = {
            'generated_at': time.time(),
            'framework_version': '1.0.0',
            'baselines_count': len(self.baseline_results),
            'baselines': {},
            'validation': self.validate_baseline_consistency()
        }
        
        # Include baseline details
        for name, baseline in self.baseline_results.items():
            report['baselines'][name] = {
                'mean_time': baseline.mean_time,
                'median_time': baseline.median_time,
                'std_deviation': baseline.std_deviation,
                'min_time': baseline.min_time,
                'max_time': baseline.max_time,
                'success': baseline.success
            }
        
        # Save report
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def generate_performance_report(self) -> str:
        """Generate comprehensive performance report."""
        report = ["Performance Test Report", "=" * 50, ""]
        
        for result in self.results:
            report.append(f"Benchmark: {result.benchmark_name}")
            report.append(f"  Status: {'PASS' if result.success else 'FAIL'}")
            if result.error_message:
                report.append(f"  Error: {result.error_message}")
            report.append(f"  Mean Time: {result.mean_time:.6f}s")
            report.append(f"  Median Time: {result.median_time:.6f}s")
            report.append(f"  Std Deviation: {result.std_deviation:.6f}s")
            report.append(f"  Min Time: {result.min_time:.6f}s")
            report.append(f"  Max Time: {result.max_time:.6f}s")
            
            # Baseline comparison
            comparison = self.compare_with_baseline(result)
            if 'mean_time_ratio' in comparison:
                ratio = comparison['mean_time_ratio']
                improvement = comparison['improvement_percent']
                report.append(f"  Baseline Comparison: {ratio:.2f}x ({improvement:+.1f}%)")
            
            report.append("")
        
        return "\\n".join(report)


# Integration with existing test infrastructure
@pytest.fixture(scope="session")
def performance_framework():
    """Provide performance testing framework for session."""
    framework = PerformanceTestingFramework()
    
    # Initialize default baselines for consistent CI/CD behavior
    framework.initialize_default_baselines()
    
    # Load any existing baselines
    framework.load_baseline_results()
    
    # Register common benchmarks
    framework.register_benchmark(PerformanceBenchmark(
        name="import_performance",
        description="Module import performance",
        target_function=lambda: __import__('services.azure_ai_foundry_client'),
        iterations=5,
        success_criteria={'max_mean_time': 2.0}  # 2 second limit for imports
    ))
    
    yield framework
    
    # Save results as baseline after session
    framework.save_baseline_results()
    
    # Export baseline report for CI/CD tracking
    framework.export_baseline_report()


def performance_test(name: str, description: str = "", **kwargs):
    """Decorator for performance tests."""
    def decorator(func):
        func._performance_test = True
        func._performance_config = {
            'name': name,
            'description': description,
            **kwargs
        }
        return func
    return decorator


class PerformanceBenchmarkRunner:
    """Runner for executing performance benchmarks independently."""
    
    def __init__(self):
        self.framework = PerformanceTestingFramework()
        self.results: List[PerformanceResult] = []
    
    def run_import_benchmarks(self) -> Dict[str, PerformanceResult]:
        """Run module import performance benchmarks."""
        import_benchmarks = {
            'azure_client_import': lambda: __import__('services.azure_ai_foundry_client'),
            'graph_client_import': lambda: __import__('services.graph_api_client'),
            'email_processor_import': lambda: __import__('services.email_processor'),
            'monitor_import': lambda: __import__('services.monitor'),
        }
        
        results = {}
        for name, import_func in import_benchmarks.items():
            benchmark = PerformanceBenchmark(
                name=name,
                description=f"Import performance for {name}",
                target_function=import_func,
                iterations=5,
                success_criteria={'max_mean_time': 3.0}
            )
            
            self.framework.register_benchmark(benchmark)
            result = self.framework.run_benchmark(name)
            results[name] = result
        
        return results
    
    def run_async_operation_benchmarks(self) -> Dict[str, PerformanceResult]:
        """Run async operation performance benchmarks."""
        import asyncio
        from unittest import mock
        
        async def mock_azure_operation():
            client = mock.AsyncMock()
            client.get_completion = mock.AsyncMock(return_value="test completion")
            await client.get_completion("test prompt")
            return "completed"
        
        async def mock_graph_operation():
            client = mock.AsyncMock()
            client.get_inbox_messages = mock.AsyncMock(return_value=[])
            await client.get_inbox_messages()
            return "completed"
        
        def run_azure_benchmark():
            return asyncio.run(mock_azure_operation())
        
        def run_graph_benchmark():
            return asyncio.run(mock_graph_operation())
        
        async_benchmarks = {
            'azure_async_operation': run_azure_benchmark,
            'graph_async_operation': run_graph_benchmark,
        }
        
        results = {}
        for name, async_func in async_benchmarks.items():
            benchmark = PerformanceBenchmark(
                name=name,
                description=f"Async operation performance for {name}",
                target_function=async_func,
                iterations=10,
                success_criteria={'max_mean_time': 5.0}
            )
            
            self.framework.register_benchmark(benchmark)
            result = self.framework.run_benchmark(name)
            results[name] = result
        
        return results
    
    def generate_full_performance_report(self) -> str:
        """Generate comprehensive performance report."""
        return self.framework.generate_performance_report()


@contextmanager
def performance_testing_context():
    """Context manager for performance testing operations."""
    runner = PerformanceBenchmarkRunner()
    try:
        yield runner
    finally:
        # Clean up any resources
        pass