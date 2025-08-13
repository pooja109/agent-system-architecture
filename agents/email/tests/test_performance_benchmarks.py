"""
Performance Benchmark Tests for OAuth Migration
===============================================

Comprehensive performance benchmarking comparing PAT vs OAuth performance
and validating production performance requirements.
"""

import asyncio
import pytest
import time
import statistics
from datetime import datetime
from typing import Dict, List, Any, Tuple
import structlog
import os

from services.databricks_connection_pool import (
    ConnectionPoolConfig,
    initialize_connection_pool,
    shutdown_connection_pool,
    get_connection_pool
)
from services.azure_key_vault_client import AzureKeyVaultClient
from database.databricks_client import DatabricksClient
from config.settings import get_settings


class PerformanceBenchmarkSuite:
    """Comprehensive performance benchmarking for OAuth migration."""
    
    def __init__(self):
        """Initialize performance benchmark suite."""
        self.logger = structlog.get_logger(__name__)
        self.settings = get_settings()
        self.benchmark_results: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, List[float]] = {}
    
    async def run_complete_benchmark_suite(self) -> Dict[str, Any]:
        """Run complete performance benchmark suite.
        
        Returns:
            Dictionary with comprehensive benchmark results
        """
        self.logger.info("Starting comprehensive OAuth performance benchmark suite")
        start_time = time.time()
        
        try:
            # Benchmark 1: Connection Establishment Performance
            await self._benchmark_connection_establishment()
            
            # Benchmark 2: Query Execution Performance
            await self._benchmark_query_execution()
            
            # Benchmark 3: Concurrent Operations Performance
            await self._benchmark_concurrent_operations()
            
            # Benchmark 4: Connection Pool Efficiency
            await self._benchmark_connection_pool_efficiency()
            
            # Benchmark 5: Resource Utilization Patterns
            await self._benchmark_resource_utilization()
            
            # Generate comprehensive performance summary
            performance_summary = self._generate_performance_summary()
            
            total_time = time.time() - start_time
            
            self.benchmark_results.update({
                "overall_status": "COMPLETED",
                "total_benchmark_time_seconds": round(total_time, 2),
                "benchmarks_completed": 5,
                "timestamp": datetime.utcnow().isoformat(),
                "performance_summary": performance_summary
            })
            
            self.logger.info(
                "OAuth performance benchmark suite completed",
                total_time=total_time,
                benchmarks_completed=5
            )
            
            return self.benchmark_results
            
        except Exception as e:
            self.benchmark_results.update({
                "overall_status": "FAILED",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            self.logger.error("OAuth performance benchmark suite failed", error=str(e))
            raise
    
    async def _benchmark_connection_establishment(self) -> None:
        """Benchmark connection establishment performance."""
        self.logger.info("Benchmarking connection establishment performance")
        benchmark_start = time.time()
        
        try:
            # Test different pool configurations
            pool_configs = [
                ConnectionPoolConfig(min_connections=1, max_connections=2),
                ConnectionPoolConfig(min_connections=2, max_connections=4),
                ConnectionPoolConfig(min_connections=3, max_connections=6)
            ]
            
            establishment_results = {}
            
            for i, config in enumerate(pool_configs):
                config_name = f"config_{i+1}_min{config.min_connections}_max{config.max_connections}"
                
                # Measure pool initialization time
                init_start = time.time()
                pool = await initialize_connection_pool(
                    self.settings.databricks,
                    self.settings.key_vault,
                    config
                )
                init_time = time.time() - init_start
                
                # Measure first connection acquisition
                first_conn_start = time.time()
                async with pool.get_connection() as conn:
                    await conn.test_connection()
                first_conn_time = time.time() - first_conn_start
                
                # Measure subsequent connection acquisitions
                subsequent_times = []
                for _ in range(10):
                    acq_start = time.time()
                    async with pool.get_connection() as conn:
                        await conn.test_connection()
                    subsequent_times.append(time.time() - acq_start)
                
                await pool.shutdown()
                
                establishment_results[config_name] = {
                    "pool_init_time_ms": round(init_time * 1000, 2),
                    "first_connection_time_ms": round(first_conn_time * 1000, 2),
                    "avg_subsequent_connection_time_ms": round(statistics.mean(subsequent_times) * 1000, 2),
                    "min_subsequent_connection_time_ms": round(min(subsequent_times) * 1000, 2),
                    "max_subsequent_connection_time_ms": round(max(subsequent_times) * 1000, 2),
                    "p95_subsequent_connection_time_ms": round(
                        sorted(subsequent_times)[int(0.95 * len(subsequent_times))] * 1000, 2
                    )
                }
                
                self.performance_metrics[f"connection_establishment_{config_name}"] = subsequent_times
            
            benchmark_time = time.time() - benchmark_start
            self.benchmark_results["connection_establishment"] = {
                "status": "COMPLETED",
                "benchmark_time_seconds": round(benchmark_time, 2),
                "configurations_tested": len(pool_configs),
                "results": establishment_results
            }
            
        except Exception as e:
            self.benchmark_results["connection_establishment"] = {
                "status": "FAILED",
                "error": str(e),
                "benchmark_time_seconds": round(time.time() - benchmark_start, 2)
            }
            raise
    
    async def _benchmark_query_execution(self) -> None:
        """Benchmark query execution performance."""
        self.logger.info("Benchmarking query execution performance")
        benchmark_start = time.time()
        
        try:
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                ConnectionPoolConfig(min_connections=3, max_connections=6)
            )
            
            # Test different query types
            query_tests = [
                ("simple_select", "SELECT 'email_performance_test' as message"),
                ("numeric_calculation", "SELECT 1 + 1 as result, CURRENT_TIMESTAMP() as timestamp"),
                ("multi_row_result", "SELECT value FROM VALUES (1), (2), (3), (4), (5) AS t(value)"),
                ("complex_calculation", "SELECT POW(2, 10) as power_result, SQRT(16) as sqrt_result, PI() as pi_value"),
                ("email_specific_query", "SELECT 'email_agent' as agent_type, CURRENT_DATE() as process_date")
            ]
            
            query_results = {}
            
            for query_name, query_sql in query_tests:
                query_times = []
                
                # Perform 20 iterations for statistical significance
                for _ in range(20):
                    query_start = time.time()
                    
                    async with DatabricksClient() as client:
                        result = await client.execute_sql(query_sql)
                        
                    query_time = time.time() - query_start
                    query_times.append(query_time)
                
                query_results[query_name] = {
                    "avg_execution_time_ms": round(statistics.mean(query_times) * 1000, 2),
                    "min_execution_time_ms": round(min(query_times) * 1000, 2),
                    "max_execution_time_ms": round(max(query_times) * 1000, 2),
                    "p95_execution_time_ms": round(
                        sorted(query_times)[int(0.95 * len(query_times))] * 1000, 2
                    ),
                    "std_dev_ms": round(statistics.stdev(query_times) * 1000, 2),
                    "iterations": len(query_times)
                }
                
                self.performance_metrics[f"query_execution_{query_name}"] = query_times
            
            await shutdown_connection_pool()
            
            benchmark_time = time.time() - benchmark_start
            self.benchmark_results["query_execution"] = {
                "status": "COMPLETED",
                "benchmark_time_seconds": round(benchmark_time, 2),
                "query_types_tested": len(query_tests),
                "results": query_results
            }
            
        except Exception as e:
            self.benchmark_results["query_execution"] = {
                "status": "FAILED",
                "error": str(e),
                "benchmark_time_seconds": round(time.time() - benchmark_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _benchmark_concurrent_operations(self) -> None:
        """Benchmark concurrent operations performance."""
        self.logger.info("Benchmarking concurrent operations performance")
        benchmark_start = time.time()
        
        try:
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                ConnectionPoolConfig(min_connections=4, max_connections=8)
            )
            
            # Test different concurrency levels
            concurrency_levels = [1, 5, 10, 15, 20]
            concurrency_results = {}
            
            for concurrency in concurrency_levels:
                level_name = f"concurrency_{concurrency}"
                
                async def concurrent_operation(op_id: int):
                    start_time = time.time()
                    async with DatabricksClient() as client:
                        await client.test_connection()
                        # Simulate email-specific work
                        await client.execute_sql("SELECT 'email_concurrent_test' as message")
                    return time.time() - start_time
                
                # Run concurrent operations
                concurrent_start = time.time()
                tasks = [concurrent_operation(i) for i in range(concurrency)]
                operation_times = await asyncio.gather(*tasks)
                total_concurrent_time = time.time() - concurrent_start
                
                # Calculate metrics
                throughput = concurrency / total_concurrent_time
                avg_operation_time = statistics.mean(operation_times)
                
                concurrency_results[level_name] = {
                    "concurrency_level": concurrency,
                    "total_time_seconds": round(total_concurrent_time, 3),
                    "throughput_ops_per_sec": round(throughput, 2),
                    "avg_operation_time_ms": round(avg_operation_time * 1000, 2),
                    "min_operation_time_ms": round(min(operation_times) * 1000, 2),
                    "max_operation_time_ms": round(max(operation_times) * 1000, 2),
                    "p95_operation_time_ms": round(
                        sorted(operation_times)[int(0.95 * len(operation_times))] * 1000, 2
                    )
                }
                
                self.performance_metrics[f"concurrent_operations_{level_name}"] = operation_times
            
            await shutdown_connection_pool()
            
            benchmark_time = time.time() - benchmark_start
            self.benchmark_results["concurrent_operations"] = {
                "status": "COMPLETED",
                "benchmark_time_seconds": round(benchmark_time, 2),
                "concurrency_levels_tested": len(concurrency_levels),
                "results": concurrency_results
            }
            
        except Exception as e:
            self.benchmark_results["concurrent_operations"] = {
                "status": "FAILED",
                "error": str(e),
                "benchmark_time_seconds": round(time.time() - benchmark_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _benchmark_connection_pool_efficiency(self) -> None:
        """Benchmark connection pool efficiency and utilization."""
        self.logger.info("Benchmarking connection pool efficiency")
        benchmark_start = time.time()
        
        try:
            # Test pool efficiency with different configurations
            pool_config = ConnectionPoolConfig(min_connections=3, max_connections=6)
            pool = await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                pool_config
            )
            
            efficiency_metrics = {}
            
            # Test 1: Pool utilization over time
            utilization_samples = []
            
            async def sample_utilization():
                for _ in range(100):  # Sample 100 times
                    metrics = pool.get_metrics()
                    utilization = (metrics.active_connections / metrics.total_connections) * 100
                    utilization_samples.append(utilization)
                    await asyncio.sleep(0.01)  # 10ms intervals
            
            async def generate_load():
                async def load_operation():
                    async with pool.get_connection() as conn:
                        await conn.test_connection()
                        await asyncio.sleep(0.05)  # Hold connection for 50ms
                
                # Generate load with 10 concurrent operations
                tasks = [load_operation() for _ in range(10)]
                await asyncio.gather(*tasks)
            
            # Run utilization sampling concurrent with load generation
            await asyncio.gather(
                sample_utilization(),
                generate_load()
            )
            
            efficiency_metrics["pool_utilization"] = {
                "avg_utilization_percent": round(statistics.mean(utilization_samples), 2),
                "max_utilization_percent": round(max(utilization_samples), 2),
                "min_utilization_percent": round(min(utilization_samples), 2),
                "samples_collected": len(utilization_samples)
            }
            
            # Test 2: Connection reuse efficiency
            reuse_start = time.time()
            operations_completed = 0
            
            # Perform 50 operations and measure connection reuse
            for _ in range(50):
                async with pool.get_connection() as conn:
                    await conn.test_connection()
                    operations_completed += 1
            
            reuse_time = time.time() - reuse_start
            final_metrics = pool.get_metrics()
            
            efficiency_metrics["connection_reuse"] = {
                "operations_completed": operations_completed,
                "total_time_seconds": round(reuse_time, 3),
                "operations_per_second": round(operations_completed / reuse_time, 2),
                "final_total_connections": final_metrics.total_connections,
                "final_total_checkouts": final_metrics.total_checkouts,
                "avg_checkouts_per_connection": round(
                    final_metrics.total_checkouts / final_metrics.total_connections, 2
                )
            }
            
            # Test 3: Pool scaling behavior
            scaling_metrics = []
            
            # Gradually increase load and measure pool response
            for load_level in [2, 4, 6, 8, 10]:
                scaling_start = time.time()
                
                async def scaling_operation():
                    async with pool.get_connection() as conn:
                        await conn.test_connection()
                
                tasks = [scaling_operation() for _ in range(load_level)]
                await asyncio.gather(*tasks)
                
                scaling_time = time.time() - scaling_start
                metrics = pool.get_metrics()
                
                scaling_metrics.append({
                    "load_level": load_level,
                    "completion_time_ms": round(scaling_time * 1000, 2),
                    "active_connections": metrics.active_connections,
                    "total_connections": metrics.total_connections
                })
            
            efficiency_metrics["pool_scaling"] = scaling_metrics
            
            await pool.shutdown()
            
            benchmark_time = time.time() - benchmark_start
            self.benchmark_results["connection_pool_efficiency"] = {
                "status": "COMPLETED",
                "benchmark_time_seconds": round(benchmark_time, 2),
                "efficiency_metrics": efficiency_metrics
            }
            
        except Exception as e:
            self.benchmark_results["connection_pool_efficiency"] = {
                "status": "FAILED",
                "error": str(e),
                "benchmark_time_seconds": round(time.time() - benchmark_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    async def _benchmark_resource_utilization(self) -> None:
        """Benchmark resource utilization patterns."""
        self.logger.info("Benchmarking resource utilization patterns")
        benchmark_start = time.time()
        
        try:
            await initialize_connection_pool(
                self.settings.databricks,
                self.settings.key_vault,
                ConnectionPoolConfig(min_connections=2, max_connections=4)
            )
            
            resource_metrics = {}
            
            # Test 1: Memory usage patterns (approximate)
            import psutil
            process = psutil.Process()
            
            memory_before = process.memory_info().rss
            
            # Perform sustained operations
            sustained_start = time.time()
            for i in range(100):
                async with DatabricksClient() as client:
                    await client.test_connection()
                    if i % 20 == 0:  # Sample every 20 operations
                        current_memory = process.memory_info().rss
                        memory_delta = current_memory - memory_before
            
            sustained_time = time.time() - sustained_start
            memory_after = process.memory_info().rss
            memory_increase = memory_after - memory_before
            
            resource_metrics["memory_utilization"] = {
                "memory_before_mb": round(memory_before / 1024 / 1024, 2),
                "memory_after_mb": round(memory_after / 1024 / 1024, 2),
                "memory_increase_mb": round(memory_increase / 1024 / 1024, 2),
                "operations_completed": 100,
                "sustained_operations_time_seconds": round(sustained_time, 2)
            }
            
            # Test 2: Service cleanup efficiency
            cleanup_times = []
            
            for _ in range(10):
                cleanup_start = time.time()
                
                async with DatabricksClient() as client:
                    await client.test_connection()
                # Service cleanup happens here
                
                cleanup_time = time.time() - cleanup_start
                cleanup_times.append(cleanup_time)
            
            resource_metrics["service_cleanup"] = {
                "avg_cleanup_time_ms": round(statistics.mean(cleanup_times) * 1000, 2),
                "max_cleanup_time_ms": round(max(cleanup_times) * 1000, 2),
                "min_cleanup_time_ms": round(min(cleanup_times) * 1000, 2),
                "cleanup_operations": len(cleanup_times)
            }
            
            # Test 3: Connection pool resource management
            pool = get_connection_pool()
            pool_status = pool.get_pool_status()
            
            resource_metrics["pool_resource_management"] = {
                "total_connections": pool_status["total_connections"],
                "active_connections": pool_status["active_connections"],
                "connection_details": len(pool_status["connection_details"]),
                "is_initialized": pool_status["is_initialized"]
            }
            
            await shutdown_connection_pool()
            
            benchmark_time = time.time() - benchmark_start
            self.benchmark_results["resource_utilization"] = {
                "status": "COMPLETED",
                "benchmark_time_seconds": round(benchmark_time, 2),
                "resource_metrics": resource_metrics
            }
            
        except Exception as e:
            self.benchmark_results["resource_utilization"] = {
                "status": "FAILED",
                "error": str(e),
                "benchmark_time_seconds": round(time.time() - benchmark_start, 2)
            }
            try:
                await shutdown_connection_pool()
            except:
                pass
            raise
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate comprehensive performance summary."""
        summary = {
            "performance_requirements_validation": {},
            "key_metrics": {},
            "recommendations": []
        }
        
        # Validate performance requirements
        requirements_met = True
        
        # Check connection establishment requirements
        if "connection_establishment" in self.benchmark_results:
            conn_results = self.benchmark_results["connection_establishment"]["results"]
            best_config = min(conn_results.keys(), 
                            key=lambda k: conn_results[k]["p95_subsequent_connection_time_ms"])
            best_p95 = conn_results[best_config]["p95_subsequent_connection_time_ms"]
            
            summary["performance_requirements_validation"]["connection_acquisition_p95"] = {
                "requirement_ms": 500,
                "actual_ms": best_p95,
                "met": best_p95 < 500,
                "best_configuration": best_config
            }
            
            if best_p95 >= 500:
                requirements_met = False
                summary["recommendations"].append(
                    f"Connection acquisition P95 ({best_p95}ms) exceeds 500ms requirement. "
                    f"Consider optimizing pool configuration."
                )
        
        # Check throughput requirements
        if "concurrent_operations" in self.benchmark_results:
            concurrent_results = self.benchmark_results["concurrent_operations"]["results"]
            max_throughput = max(
                result["throughput_ops_per_sec"] 
                for result in concurrent_results.values()
            )
            
            summary["performance_requirements_validation"]["throughput"] = {
                "requirement_ops_per_sec": 20,
                "actual_ops_per_sec": max_throughput,
                "met": max_throughput > 20
            }
            
            if max_throughput <= 20:
                requirements_met = False
                summary["recommendations"].append(
                    f"Maximum throughput ({max_throughput} ops/sec) does not exceed 20 ops/sec requirement."
                )
        
        # Extract key metrics
        if "query_execution" in self.benchmark_results:
            query_results = self.benchmark_results["query_execution"]["results"]
            simple_select = query_results.get("simple_select", {})
            summary["key_metrics"]["simple_query_avg_ms"] = simple_select.get("avg_execution_time_ms")
        
        if "connection_pool_efficiency" in self.benchmark_results:
            efficiency = self.benchmark_results["connection_pool_efficiency"]["efficiency_metrics"]
            pool_util = efficiency.get("pool_utilization", {})
            summary["key_metrics"]["avg_pool_utilization_percent"] = pool_util.get("avg_utilization_percent")
        
        # Email agent specific recommendations
        if requirements_met:
            summary["recommendations"].append("All performance requirements met successfully for email agent.")
        
        summary["recommendations"].extend([
            "Monitor email processing throughput in production to optimize batch sizes.",
            "Implement connection pool pre-warming for email batch processing workflows.",
            "Consider implementing query result caching for frequently accessed email metadata.",
            "Monitor database connection utilization during peak email processing periods."
        ])
        
        summary["overall_performance_assessment"] = {
            "requirements_met": requirements_met,
            "production_ready": requirements_met,
            "agent_type": "email"
        }
        
        return summary


# Pytest integration
@pytest.mark.skipif(
    os.getenv("RUN_PERFORMANCE_TESTS") != "true",
    reason="Performance tests require RUN_PERFORMANCE_TESTS=true"
)
class TestPerformanceBenchmarks:
    """Pytest wrapper for performance benchmark tests."""
    
    @pytest.mark.asyncio
    async def test_complete_performance_benchmark_suite(self):
        """Test complete performance benchmark suite."""
        benchmark_suite = PerformanceBenchmarkSuite()
        results = await benchmark_suite.run_complete_benchmark_suite()
        
        assert results["overall_status"] == "COMPLETED", f"Benchmark suite failed: {results.get('error', 'Unknown error')}"
        assert results["benchmarks_completed"] == 5, f"Expected 5 benchmarks, got {results['benchmarks_completed']}"
        
        # Validate performance requirements
        performance_summary = results["performance_summary"]
        assert performance_summary["overall_performance_assessment"]["production_ready"], \
            "Performance benchmarks indicate system not production ready"
        
        # Log performance summary
        print(f"\nPerformance Requirements Validation:")
        for req, details in performance_summary["performance_requirements_validation"].items():
            print(f"  {req}: {'PASS' if details['met'] else 'FAIL'} - {details}")
    
    @pytest.mark.asyncio
    async def test_connection_establishment_benchmark(self):
        """Test connection establishment benchmark only."""
        benchmark_suite = PerformanceBenchmarkSuite()
        await benchmark_suite._benchmark_connection_establishment()
        
        assert benchmark_suite.benchmark_results["connection_establishment"]["status"] == "COMPLETED"
    
    @pytest.mark.asyncio
    async def test_query_execution_benchmark(self):
        """Test query execution benchmark only."""
        benchmark_suite = PerformanceBenchmarkSuite()
        await benchmark_suite._benchmark_query_execution()
        
        assert benchmark_suite.benchmark_results["query_execution"]["status"] == "COMPLETED"
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_benchmark(self):
        """Test concurrent operations benchmark only."""
        benchmark_suite = PerformanceBenchmarkSuite()
        await benchmark_suite._benchmark_concurrent_operations()
        
        assert benchmark_suite.benchmark_results["concurrent_operations"]["status"] == "COMPLETED"


if __name__ == "__main__":
    async def main():
        """Run the complete benchmark suite when executed directly."""
        benchmark_suite = PerformanceBenchmarkSuite()
        try:
            results = await benchmark_suite.run_complete_benchmark_suite()
            print(f"\nBenchmark Results:")
            print(f"Overall Status: {results['overall_status']}")
            print(f"Benchmarks Completed: {results['benchmarks_completed']}")
            print(f"Total Time: {results['total_benchmark_time_seconds']}s")
            
            performance_summary = results["performance_summary"]
            print(f"\nPerformance Assessment:")
            print(f"Production Ready: {performance_summary['overall_performance_assessment']['production_ready']}")
            print(f"Requirements Met: {performance_summary['overall_performance_assessment']['requirements_met']}")
            print(f"Agent Type: {performance_summary['overall_performance_assessment']['agent_type']}")
            
            print(f"\nKey Metrics:")
            for metric, value in performance_summary["key_metrics"].items():
                print(f"  {metric}: {value}")
            
            print(f"\nRecommendations:")
            for recommendation in performance_summary["recommendations"]:
                print(f"  - {recommendation}")
                
        except Exception as e:
            print(f"Benchmark suite failed: {e}")
            return 1
        
        return 0
    
    import sys
    sys.exit(asyncio.run(main()))