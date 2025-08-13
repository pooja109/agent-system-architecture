"""
Performance Benchmarking Tool for External Prompt System
========================================================

Comprehensive benchmarking tool to measure and validate performance
characteristics of the external prompt system.
"""

import asyncio
import time
import statistics
import json
import psutil
import os
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# Add the parent directory to sys.path to import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.prompt_manager import PromptManager
from services.template_renderer import TemplateRenderer
from services.email_forwarding_manager import EmailForwardingManager


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    operation: str
    total_operations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    p95_time: float
    p99_time: float
    memory_usage_mb: float
    cache_hit_rate: float = 0.0


class PromptPerformanceBenchmark:
    """Comprehensive performance benchmarking for prompt operations."""
    
    def __init__(self, prompts_base_path: Path):
        """Initialize benchmark with prompts directory."""
        self.prompts_base_path = prompts_base_path
        self.prompt_manager = PromptManager(prompts_base_path=prompts_base_path)
        self.template_renderer = TemplateRenderer()
        self.email_forwarding_manager = EmailForwardingManager(self.prompt_manager)
        self.results: List[PerformanceMetrics] = []
        self.process = psutil.Process(os.getpid())
    
    async def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive performance benchmark suite."""
        print("Starting comprehensive prompt performance benchmark...")
        
        # Benchmark individual operations
        await self._benchmark_prompt_loading()
        await self._benchmark_template_rendering()
        await self._benchmark_email_forwarding()
        await self._benchmark_concurrent_operations()
        await self._benchmark_memory_usage()
        
        # Generate summary report
        report = self._generate_performance_report()
        
        print("\nBenchmark completed successfully!")
        return report
    
    async def _benchmark_prompt_loading(self):
        """Benchmark prompt loading operations."""
        print("\nBenchmarking prompt loading...")
        
        # Cold start benchmark
        times = []
        memory_before = self._get_memory_usage()
        
        for i in range(10):
            # Clear cache to simulate cold start
            self.prompt_manager.clear_cache()
            
            start_time = time.time()
            await self.prompt_manager.get_system_instructions("email_classification")
            end_time = time.time()
            
            times.append(end_time - start_time)
        
        memory_after = self._get_memory_usage()
        
        metrics = PerformanceMetrics(
            operation="prompt_loading_cold_start",
            total_operations=len(times),
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            p95_time=self._percentile(times, 95),
            p99_time=self._percentile(times, 99),
            memory_usage_mb=memory_after - memory_before
        )
        
        self.results.append(metrics)
        print(f"  Cold start avg: {metrics.avg_time:.3f}s, max: {metrics.max_time:.3f}s")
        
        # Cache hit benchmark
        times = []
        for i in range(100):
            start_time = time.time()
            await self.prompt_manager.get_system_instructions("email_classification")
            end_time = time.time()
            times.append(end_time - start_time)
        
        cache_stats = self.prompt_manager.get_cache_statistics()
        
        metrics = PerformanceMetrics(
            operation="prompt_loading_cache_hit",
            total_operations=len(times),
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            p95_time=self._percentile(times, 95),
            p99_time=self._percentile(times, 99),
            memory_usage_mb=0,  # No additional memory for cache hits
            cache_hit_rate=cache_stats["hit_rate_percent"]
        )
        
        self.results.append(metrics)
        print(f"  Cache hit avg: {metrics.avg_time:.6f}s, hit rate: {metrics.cache_hit_rate:.1f}%")
    
    async def _benchmark_template_rendering(self):
        """Benchmark template rendering operations."""
        print("\nBenchmarking template rendering...")
        
        # Load template once
        template_config = await self.prompt_manager.load_template(
            "email_classification", 
            "classification_template"
        )
        
        # Prepare test variables
        test_variables = {
            "sender_email": "test@example.com",
            "subject": "Test Subject",
            "body": "This is a test email body with some content to render.",
            "sender_domain": "example.com",
            "domain_type": "Corporate/Legitimate",
            "content_length": 50,
            "sender_format": "Standard format",
            "domain_classification": "corporate domain",
            "length_classification": "minimal"
        }
        
        times = []
        memory_before = self._get_memory_usage()
        
        for i in range(100):
            start_time = time.time()
            self.template_renderer.render_template(template_config, test_variables)
            end_time = time.time()
            times.append(end_time - start_time)
        
        memory_after = self._get_memory_usage()
        render_stats = self.template_renderer.get_rendering_statistics()
        
        metrics = PerformanceMetrics(
            operation="template_rendering",
            total_operations=len(times),
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            p95_time=self._percentile(times, 95),
            p99_time=self._percentile(times, 99),
            memory_usage_mb=memory_after - memory_before,
            cache_hit_rate=100 - render_stats["error_rate_percent"]
        )
        
        self.results.append(metrics)
        print(f"  Template rendering avg: {metrics.avg_time:.6f}s, max: {metrics.max_time:.6f}s")
    
    async def _benchmark_email_forwarding(self):
        """Benchmark email forwarding operations."""
        print("\nBenchmarking email forwarding...")
        
        from models.email import Email, EmailSender, EmailBody
        from datetime import datetime, timezone
        
        # Create test email
        test_email = Email(
            id="benchmark-email",
            subject="Benchmark Test Email",
            sender=EmailSender(email="test@example.com", name="Test User"),
            body=EmailBody(content="This is a benchmark test email content."),
            received_datetime=datetime.now(timezone.utc)
        )
        
        times = []
        memory_before = self._get_memory_usage()
        
        for i in range(50):
            start_time = time.time()
            await self.email_forwarding_manager.generate_forwarding_email_content(
                original_email=test_email,
                recipient_email="recipient@example.com",
                recipient_name="Test Recipient",
                scenario_type="service_inquiry"
            )
            end_time = time.time()
            times.append(end_time - start_time)
        
        memory_after = self._get_memory_usage()
        forwarding_stats = self.email_forwarding_manager.get_forwarding_statistics()
        
        metrics = PerformanceMetrics(
            operation="email_forwarding_content_generation",
            total_operations=len(times),
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            p95_time=self._percentile(times, 95),
            p99_time=self._percentile(times, 99),
            memory_usage_mb=memory_after - memory_before,
            cache_hit_rate=100 - forwarding_stats["error_rate_percent"]
        )
        
        self.results.append(metrics)
        print(f"  Email forwarding avg: {metrics.avg_time:.3f}s, max: {metrics.max_time:.3f}s")
    
    async def _benchmark_concurrent_operations(self):
        """Benchmark concurrent prompt operations."""
        print("\nBenchmarking concurrent operations...")
        
        async def concurrent_load():
            start_time = time.time()
            await self.prompt_manager.get_system_instructions("email_classification")
            return time.time() - start_time
        
        # Test different concurrency levels
        for concurrency in [10, 50, 100]:
            print(f"  Testing {concurrency} concurrent operations...")
            
            start_time = time.time()
            tasks = [concurrent_load() for _ in range(concurrency)]
            individual_times = await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            metrics = PerformanceMetrics(
                operation=f"concurrent_operations_{concurrency}",
                total_operations=concurrency,
                total_time=total_time,
                avg_time=statistics.mean(individual_times),
                min_time=min(individual_times),
                max_time=max(individual_times),
                p95_time=self._percentile(individual_times, 95),
                p99_time=self._percentile(individual_times, 99),
                memory_usage_mb=0  # Measured separately
            )
            
            self.results.append(metrics)
            print(f"    Throughput: {concurrency/total_time:.1f} ops/sec")
    
    async def _benchmark_memory_usage(self):
        """Benchmark memory usage patterns."""
        print("\nBenchmarking memory usage...")
        
        initial_memory = self._get_memory_usage()
        
        # Load many prompts to test memory scaling
        for i in range(100):
            await self.prompt_manager.get_system_instructions("email_classification")
            
            if i % 20 == 0:
                current_memory = self._get_memory_usage()
                memory_increase = current_memory - initial_memory
                print(f"  After {i+1} operations: {memory_increase:.1f}MB increase")
        
        final_memory = self._get_memory_usage()
        total_increase = final_memory - initial_memory
        
        metrics = PerformanceMetrics(
            operation="memory_usage_scaling",
            total_operations=100,
            total_time=0,
            avg_time=0,
            min_time=0,
            max_time=0,
            p95_time=0,
            p99_time=0,
            memory_usage_mb=total_increase
        )
        
        self.results.append(metrics)
        print(f"  Total memory increase: {total_increase:.1f}MB")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        return statistics.quantiles(data, n=100)[percentile - 1] if len(data) > 1 else data[0]
    
    def _generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "benchmark_summary": {
                "total_operations": sum(m.total_operations for m in self.results),
                "total_benchmarks": len(self.results),
                "timestamp": time.time()
            },
            "performance_metrics": [asdict(metric) for metric in self.results],
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations based on benchmark results."""
        recommendations = []
        
        # Check cold start performance
        cold_start_metrics = [m for m in self.results if "cold_start" in m.operation]
        if cold_start_metrics and cold_start_metrics[0].avg_time > 0.1:
            recommendations.append(
                f"Cold start performance ({cold_start_metrics[0].avg_time:.3f}s) exceeds 100ms target. "
                "Consider prompt preloading or caching optimization."
            )
        
        # Check cache hit performance
        cache_hit_metrics = [m for m in self.results if "cache_hit" in m.operation]
        if cache_hit_metrics and cache_hit_metrics[0].avg_time > 0.001:
            recommendations.append(
                f"Cache hit performance ({cache_hit_metrics[0].avg_time:.6f}s) exceeds 1ms target. "
                "Consider cache optimization."
            )
        
        # Check memory usage
        memory_metrics = [m for m in self.results if "memory" in m.operation]
        if memory_metrics and memory_metrics[0].memory_usage_mb > 50:
            recommendations.append(
                f"Memory usage ({memory_metrics[0].memory_usage_mb:.1f}MB) is high. "
                "Consider implementing memory limits or cache eviction."
            )
        
        if not recommendations:
            recommendations.append("Performance is within acceptable limits. No optimizations required.")
        
        return recommendations


async def main():
    """Run the performance benchmark."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark external prompt system performance")
    parser.add_argument("--prompts-dir", type=Path, 
                       default=Path(__file__).parent.parent / "prompts",
                       help="Path to prompts directory")
    parser.add_argument("--output", type=Path,
                       default=Path("benchmark_results.json"),
                       help="Output file for benchmark results")
    
    args = parser.parse_args()
    
    if not args.prompts_dir.exists():
        print(f"Error: Prompts directory not found: {args.prompts_dir}")
        return 1
    
    try:
        benchmark = PromptPerformanceBenchmark(args.prompts_dir)
        results = await benchmark.run_comprehensive_benchmark()
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nBenchmark results saved to: {args.output}")
        
        # Print summary
        print("\nPerformance Summary:")
        for metric in benchmark.results:
            print(f"  {metric.operation}: {metric.avg_time:.6f}s avg, {metric.max_time:.6f}s max")
        
        print("\nRecommendations:")
        for rec in results["recommendations"]:
            print(f"  - {rec}")
        
        return 0
        
    except Exception as e:
        print(f"Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))