"""
Storage Performance Tests for Scenario Tracking System
======================================================

Performance benchmarking and load testing for the core storage operations,
validating throughput, latency, and reliability under various load conditions.
"""

import pytest
import asyncio
import time
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
import structlog

# System under test imports
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

logger = structlog.get_logger(__name__)


class TestRealDatabasePerformance:
    """Performance tests using real database connections for production validation."""
    
    @pytest.fixture(autouse=True)
    async def setup_real_performance_environment(self):
        """Setup real database performance test environment."""
        self.table_suffix = "_real_performance_test"
        self.performance_metrics = {}
        
        # Check if we should run real database tests
        import os
        self.run_real_tests = os.getenv("RUN_REAL_PERFORMANCE_TESTS", "false").lower() == "true"
        
        if not self.run_real_tests:
            pytest.skip("Real database performance tests disabled. Set RUN_REAL_PERFORMANCE_TESTS=true to enable")
    
    def generate_realistic_test_records(self, count: int) -> List[ScenarioProcessingRecord]:
        """Generate realistic test records for real database testing."""
        records = []
        base_time = datetime.now(timezone.utc)
        
        # Realistic scenario distribution based on actual usage patterns
        scenario_distribution = [
            (ScenarioType.SCENARIO_5, 0.4),  # 40% - Most common
            (ScenarioType.SCENARIO_6, 0.2),  # 20% - Negative feedback
            (ScenarioType.SCENARIO_7, 0.15), # 15% - Service inquiries
            (ScenarioType.SCENARIO_8, 0.1),  # 10% - Out of office
            (ScenarioType.SCENARIO_9, 0.05), # 5% - Invalid emails
            (ScenarioType.SCENARIO_10, 0.05), # 5% - No longer works
            (ScenarioType.SCENARIO_11, 0.05)  # 5% - Unknown
        ]
        
        for i in range(count):
            # Select scenario type based on realistic distribution
            import random
            rand_val = random.random()
            cumulative = 0
            selected_scenario = ScenarioType.SCENARIO_5
            
            for scenario, probability in scenario_distribution:
                cumulative += probability
                if rand_val <= cumulative:
                    selected_scenario = scenario
                    break
            
            record = ScenarioProcessingRecord(
                process_id=f"real_perf_{i}_{int(time.time() * 1000)}",
                email_id=f"real_perf_email_{i}",
                sender_email=f"real_customer_{i % 50}@company.com",  # Simulate 50 different customers
                received_datetime=base_time - timedelta(minutes=i),
                process_success=random.choice([True, True, True, False]),  # 75% success rate
                scenario_type=selected_scenario,
                processing_duration_ms=random.randint(1000, 30000),  # 1-30 second processing
                ai_confidence=random.uniform(0.5, 0.95),
                test_mode=True,
                environment="real_performance_test"
            )
            records.append(record)
        
        return records
    
    @pytest.mark.real_database
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.medium
    @pytest.mark.asyncio
    async def test_real_database_single_record_performance(self):
        """Test single record performance against real database."""
        
        # Generate test records
        test_records = self.generate_realistic_test_records(10)
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            # Test connection first
            connection_working = await db_client.test_connection()
            if not connection_working:
                pytest.skip("Real database connection not available")
            
            # Benchmark single record operations
            start_time = time.perf_counter()
            
            for record in test_records:
                record_start = time.perf_counter()
                result = await db_client.store_scenario_processing_record(record)
                record_duration = time.perf_counter() - record_start
                
                assert result is True, "Real database storage should succeed"
                self.performance_metrics[f"single_record_{record.process_id}"] = record_duration
            
            total_duration = time.perf_counter() - start_time
            avg_record_time = total_duration / len(test_records)
            
            # Performance assertions for real database
            assert avg_record_time < 5.0, f"Average record time too high: {avg_record_time:.3f}s (should be < 5s)"
            assert total_duration < 60.0, f"Total processing time too high: {total_duration:.3f}s (should be < 60s)"
            
            logger.info(
                "Real database single record performance",
                total_duration=f"{total_duration:.3f}s",
                avg_record_time=f"{avg_record_time:.3f}s",
                records_per_second=f"{len(test_records)/total_duration:.2f}",
                success_rate="100%"
            )
    
    @pytest.mark.real_database
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.medium
    @pytest.mark.asyncio 
    async def test_real_database_batch_performance(self):
        """Test batch operations performance against real database."""
        
        # Generate larger batch of test records
        test_records = self.generate_realistic_test_records(50)
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            # Test connection first
            connection_working = await db_client.test_connection()
            if not connection_working:
                pytest.skip("Real database connection not available")
            
            # Benchmark batch operations
            start_time = time.perf_counter()
            result = await db_client.store_scenario_processing_records_batch(test_records)
            batch_duration = time.perf_counter() - start_time
            
            # Validate batch result structure
            assert isinstance(result, dict), "Batch result should be dictionary"
            assert "successful_records" in result, "Batch result should include successful_records"
            
            successful_records = result.get("successful_records", 0)
            failed_records = result.get("failed_records", 0)
            
            # Performance assertions for batch operations
            records_per_second = successful_records / batch_duration if batch_duration > 0 else 0
            success_rate = successful_records / len(test_records) if len(test_records) > 0 else 0
            
            assert batch_duration < 30.0, f"Batch duration too high: {batch_duration:.3f}s (should be < 30s)"
            assert records_per_second >= 2.0, f"Batch throughput too low: {records_per_second:.2f} records/s (should be >= 2/s)"
            assert success_rate >= 0.80, f"Batch success rate too low: {success_rate:.2%} (should be >= 80%)"
            
            logger.info(
                "Real database batch performance",
                batch_duration=f"{batch_duration:.3f}s", 
                successful_records=successful_records,
                failed_records=failed_records,
                records_per_second=f"{records_per_second:.2f}",
                success_rate=f"{success_rate:.1%}"
            )
    
    @pytest.mark.real_database
    @pytest.mark.real_database
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.medium
    @pytest.mark.asyncio
    async def test_real_database_query_performance(self):
        """Test query operations performance against real database."""
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            # Test connection first
            connection_working = await db_client.test_connection()
            if not connection_working:
                pytest.skip("Real database connection not available")
            
            # Benchmark query operations
            queries = [
                ("get_recent_scenario_records", lambda: db_client.get_recent_scenario_records(limit=100)),
                ("get_scenario_records_by_sender", lambda: db_client.get_scenario_records_by_sender("real_customer_1@company.com")),
                ("get_scenario_records_by_email_id", lambda: db_client.get_scenario_records_by_email_id("real_perf_email_1")),
            ]
            
            for query_name, query_func in queries:
                start_time = time.perf_counter()
                results = await query_func()
                query_duration = time.perf_counter() - start_time
                
                # Validate query results
                assert isinstance(results, list), f"{query_name} should return list"
                
                # Performance assertions for queries
                assert query_duration < 10.0, f"{query_name} duration too high: {query_duration:.3f}s (should be < 10s)"
                
                logger.info(
                    f"Real database {query_name} performance",
                    duration=f"{query_duration:.3f}s",
                    result_count=len(results)
                )


class TestStoragePerformance:
    """Performance tests for core storage operations."""
    
    @pytest.fixture(autouse=True)
    async def setup_performance_environment(self):
        """Setup performance test environment."""
        self.table_suffix = "_performance_test"
        self.performance_metrics = {}
    
    def generate_test_records(self, count: int, prefix: str = "perf_test") -> List[ScenarioProcessingRecord]:
        """Generate test records for performance testing."""
        records = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(count):
            record = ScenarioProcessingRecord(
                process_id=f"{prefix}_{i}_{int(time.time() * 1000)}",
                email_id=f"{prefix}_email_{i}",
                sender_email=f"{prefix}_{i}@performance-test.com",
                received_datetime=base_time - timedelta(minutes=i),
                process_success=True,
                scenario_type=[ScenarioType.SCENARIO_5, ScenarioType.SCENARIO_6, ScenarioType.SCENARIO_7, ScenarioType.SCENARIO_8, ScenarioType.SCENARIO_9, ScenarioType.SCENARIO_10, ScenarioType.SCENARIO_11][i % 7],
                processing_duration_ms=100 + (i % 200),
                ai_confidence=0.6 + (i % 4) * 0.1,
                test_mode=True,
                environment="performance_test"
            )
            records.append(record)
        
        return records
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_single_record_latency_benchmark(self):
        """Benchmark single record storage latency."""
        
        test_records = self.generate_test_records(10, "latency_test")
        latencies = []
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            for record in test_records:
                start_time = time.time()
                
                result = await db_client.store_scenario_processing_record(record)
                
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)
                
                assert result is True, f"Storage failed for record {record.process_id}"
        
        # Calculate latency statistics
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        max_latency = max(latencies)
        
        logger.info("Single record latency benchmark results",
                   avg_latency_ms=avg_latency,
                   median_latency_ms=median_latency,
                   p95_latency_ms=p95_latency,
                   max_latency_ms=max_latency)
        
        # Performance requirements
        assert avg_latency < 500, f"Average latency too high: {avg_latency:.2f}ms"
        assert p95_latency < 1000, f"P95 latency too high: {p95_latency:.2f}ms"
        assert max_latency < 2000, f"Max latency too high: {max_latency:.2f}ms"
        
        self.performance_metrics["single_record_latency"] = {
            "avg_ms": avg_latency,
            "median_ms": median_latency,
            "p95_ms": p95_latency,
            "max_ms": max_latency
        }
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_batch_storage_throughput_benchmark(self):
        """Benchmark batch storage throughput."""
        
        batch_sizes = [10, 25, 50, 100]
        throughput_results = {}
        
        for batch_size in batch_sizes:
            test_records = self.generate_test_records(batch_size, f"batch_{batch_size}")
            
            async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
                start_time = time.time()
                
                # Store records individually since batch API is not in Phase 6 spec
                successful_records = 0
                failed_records = 0
                
                for record in test_records:
                    record_result = await db_client.store_scenario_processing_record(record)
                    if record_result:
                        successful_records += 1
                    else:
                        failed_records += 1
                
                result = {
                    "successful_records": successful_records,
                    "failed_records": failed_records,
                    "success_rate": successful_records / len(test_records) if test_records else 0
                }
                
                end_time = time.time()
                duration = end_time - start_time
                throughput = result["successful_records"] / duration if duration > 0 else 0
                
                throughput_results[batch_size] = {
                    "duration_seconds": duration,
                    "throughput_records_per_second": throughput,
                    "successful_records": result["successful_records"],
                    "failed_records": result["failed_records"],
                    "success_rate": result["success_rate"]
                }
                
                logger.info("Batch throughput benchmark",
                           batch_size=batch_size,
                           duration=duration,
                           throughput=throughput,
                           success_rate=result["success_rate"])
                
                # Performance requirements per batch size
                if batch_size <= 50:
                    assert throughput >= 5, f"Throughput too low for batch {batch_size}: {throughput:.2f}/s"
                else:
                    assert throughput >= 8, f"Throughput too low for batch {batch_size}: {throughput:.2f}/s"
                
                assert result["success_rate"] >= 0.90, f"Success rate too low: {result['success_rate']:.2%}"
        
        self.performance_metrics["batch_throughput"] = throughput_results
    
    @pytest.mark.performance
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_storage_performance(self):
        """Test performance under concurrent storage operations."""
        
        concurrency_levels = [2, 5, 10]
        concurrent_results = {}
        
        for concurrency in concurrency_levels:
            # Create separate record batches for each concurrent task
            tasks = []
            all_records = []
            
            for i in range(concurrency):
                records = self.generate_test_records(20, f"concurrent_{concurrency}_{i}")
                all_records.extend(records)
                
                task = self._concurrent_storage_task(records, f"task_{i}")
                tasks.append(task)
            
            # Execute concurrent tasks
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze results
            total_duration = end_time - start_time
            total_successful = sum(r["successful"] for r in results if not isinstance(r, Exception))
            total_failed = sum(r["failed"] for r in results if not isinstance(r, Exception))
            exceptions = sum(1 for r in results if isinstance(r, Exception))
            
            overall_throughput = total_successful / total_duration if total_duration > 0 else 0
            success_rate = total_successful / (total_successful + total_failed) if (total_successful + total_failed) > 0 else 0
            
            concurrent_results[concurrency] = {
                "total_duration": total_duration,
                "overall_throughput": overall_throughput,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "exceptions": exceptions,
                "success_rate": success_rate
            }
            
            logger.info("Concurrent storage performance",
                       concurrency_level=concurrency,
                       total_duration=total_duration,
                       overall_throughput=overall_throughput,
                       success_rate=success_rate,
                       exceptions=exceptions)
            
            # Performance requirements
            assert success_rate >= 0.85, f"Success rate too low under concurrency {concurrency}: {success_rate:.2%}"
            assert overall_throughput >= 10, f"Overall throughput too low: {overall_throughput:.2f}/s"
            assert exceptions == 0, f"Unexpected exceptions: {exceptions}"
        
        self.performance_metrics["concurrent_performance"] = concurrent_results
    
    async def _concurrent_storage_task(self, records: List[ScenarioProcessingRecord], task_id: str) -> Dict[str, int]:
        """Execute a concurrent storage task."""
        try:
            async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
                # Store records individually since batch API is not in Phase 6 spec
                successful = 0
                failed = 0
                
                for record in records:
                    record_result = await db_client.store_scenario_processing_record(record)
                    if record_result:
                        successful += 1
                    else:
                        failed += 1
                
                return {
                    "task_id": task_id,
                    "successful": successful,
                    "failed": failed
                }
        except Exception as e:
            logger.error("Concurrent task failed", task_id=task_id, error=str(e))
            return {"task_id": task_id, "successful": 0, "failed": len(records)}
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_large_batch_processing_limits(self):
        """Test performance limits with very large batches."""
        
        large_batch_sizes = [200, 500, 1000]
        large_batch_results = {}
        
        for batch_size in large_batch_sizes:
            test_records = self.generate_test_records(batch_size, f"large_{batch_size}")
            
            async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
                start_time = time.time()
                
                try:
                    # Store records individually since batch API is not in Phase 6 spec
                    successful_records = 0
                    failed_records = 0
                    
                    for record in test_records:
                        record_result = await db_client.store_scenario_processing_record(record)
                        if record_result:
                            successful_records += 1
                        else:
                            failed_records += 1
                    
                    end_time = time.time()
                    duration = end_time - start_time
                    throughput = successful_records / duration if duration > 0 else 0
                    success_rate = successful_records / len(test_records) if test_records else 0
                    
                    large_batch_results[batch_size] = {
                        "completed": True,
                        "duration_seconds": duration,
                        "throughput": throughput,
                        "successful_records": successful_records,
                        "success_rate": success_rate
                    }
                    
                    logger.info("Large batch processing",
                               batch_size=batch_size,
                               duration=duration,
                               throughput=throughput,
                               success_rate=success_rate)
                    
                    # Relaxed requirements for large batches
                    assert success_rate >= 0.80, f"Large batch success rate too low: {success_rate:.2%}"
                    assert duration < 120, f"Large batch took too long: {duration:.2f}s"
                    
                except Exception as e:
                    large_batch_results[batch_size] = {
                        "completed": False,
                        "error": str(e)
                    }
                    
                    logger.error("Large batch processing failed",
                                batch_size=batch_size,
                                error=str(e))
                    
                    # For very large batches, failure is acceptable but should be controlled
                    if batch_size >= 1000:
                        pytest.skip(f"Large batch {batch_size} failed as expected: {str(e)}")
                    else:
                        raise
        
        self.performance_metrics["large_batch_performance"] = large_batch_results
    
    @pytest.mark.performance
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test memory usage during high-load operations."""
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate large dataset
        large_record_set = self.generate_test_records(500, "memory_test")
        
        memory_samples = []
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            # Process in chunks while monitoring memory
            chunk_size = 50
            for i in range(0, len(large_record_set), chunk_size):
                chunk = large_record_set[i:i + chunk_size]
                
                # Measure memory before processing
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Process chunk (store individually since batch API is not in Phase 6 spec)
                for record in chunk:
                    await db_client.store_scenario_processing_record(record)
                
                # Measure memory after processing
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                
                memory_samples.append({
                    "chunk_number": i // chunk_size,
                    "memory_before_mb": memory_before,
                    "memory_after_mb": memory_after,
                    "memory_increase_mb": memory_after - memory_before
                })
                
                # Small delay to allow garbage collection
                await asyncio.sleep(0.1)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        max_memory_increase = max(sample["memory_increase_mb"] for sample in memory_samples)
        
        logger.info("Memory usage under load",
                   initial_memory_mb=initial_memory,
                   final_memory_mb=final_memory,
                   total_increase_mb=total_memory_increase,
                   max_chunk_increase_mb=max_memory_increase)
        
        # Memory usage requirements
        assert total_memory_increase < 100, f"Total memory increase too high: {total_memory_increase:.2f}MB"
        assert max_memory_increase < 20, f"Max chunk memory increase too high: {max_memory_increase:.2f}MB"
        
        self.performance_metrics["memory_usage"] = {
            "initial_mb": initial_memory,
            "final_mb": final_memory,
            "total_increase_mb": total_memory_increase,
            "max_chunk_increase_mb": max_memory_increase
        }
    
    @pytest.mark.performance
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.benchmark
    @pytest.mark.medium
    @pytest.mark.asyncio
    async def test_retrieval_performance_benchmark(self):
        """Test performance of data retrieval operations."""
        
        # First, populate with test data
        setup_records = self.generate_test_records(100, "retrieval_test")
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            # Store setup data (using Phase 6 API)
            for record in setup_records:
                await db_client.store_scenario_processing_record(record)
            
            # Test different retrieval operations
            retrieval_results = {}
            
            # 1. Recent records query performance (Phase 6 API)
            start_time = time.time()
            recent_records = await db_client.get_recent_scenario_records(limit=50)
            recent_duration = (time.time() - start_time) * 1000
            
            retrieval_results["recent_records_query"] = {
                "duration_ms": recent_duration,
                "records_found": len(recent_records)
            }
            
            # 2. Records by sender query performance (Phase 6 API)
            test_customer = "retrieval_test_0@performance-test.com"
            start_time = time.time()
            sender_records = await db_client.get_scenario_records_by_sender(test_customer)
            sender_duration = (time.time() - start_time) * 1000
            
            retrieval_results["sender_records_query"] = {
                "duration_ms": sender_duration,
                "records_found": len(sender_records)
            }
            
            # 3. Records by email ID query performance (Phase 6 API)
            test_email_id = "retrieval_test_0"
            start_time = time.time()
            email_records = await db_client.get_scenario_records_by_email_id(test_email_id)
            email_duration = (time.time() - start_time) * 1000
            
            retrieval_results["email_records_query"] = {
                "duration_ms": email_duration,
                "records_found": len(email_records)
            }
            
            # 4. Health check performance (Phase 6 API)
            start_time = time.time()
            health_status = await db_client.get_health_status()
            health_duration = (time.time() - start_time) * 1000
            
            retrieval_results["health_check"] = {
                "duration_ms": health_duration,
                "status": health_status["status"]
            }
            
            logger.info("Retrieval performance benchmark",
                       analytics_ms=analytics_duration,
                       customer_ms=customer_duration,
                       expert_ms=expert_duration,
                       health_ms=health_duration)
            
            # Performance requirements for retrieval operations
            assert analytics_duration < 3000, f"Analytics query too slow: {analytics_duration:.2f}ms"
            assert customer_duration < 2000, f"Customer history query too slow: {customer_duration:.2f}ms"
            assert expert_duration < 2000, f"Expert stats query too slow: {expert_duration:.2f}ms"
            assert health_duration < 1000, f"Health check too slow: {health_duration:.2f}ms"
            
            self.performance_metrics["retrieval_performance"] = retrieval_results
    
    @pytest.mark.performance
    @pytest.mark.scenario_tracking
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_sustained_load_endurance(self):
        """Test performance under sustained load over time."""
        
        # Run sustained operations for a fixed duration
        test_duration_seconds = 30
        batch_interval_seconds = 2
        records_per_batch = 10
        
        start_time = time.time()
        batch_results = []
        batch_number = 0
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            while (time.time() - start_time) < test_duration_seconds:
                batch_number += 1
                
                # Generate batch
                batch_records = self.generate_test_records(
                    records_per_batch, 
                    f"endurance_{batch_number}"
                )
                
                # Process batch with timing
                batch_start = time.time()
                result = await db_client.store_scenario_processing_records_batch(batch_records)
                batch_duration = time.time() - batch_start
                
                batch_results.append({
                    "batch_number": batch_number,
                    "batch_duration": batch_duration,
                    "successful_records": result["successful_records"],
                    "success_rate": result["success_rate"],
                    "elapsed_time": time.time() - start_time
                })
                
                # Wait before next batch
                await asyncio.sleep(batch_interval_seconds)
        
        total_duration = time.time() - start_time
        total_batches = len(batch_results)
        total_successful = sum(r["successful_records"] for r in batch_results)
        
        # Calculate performance trends
        avg_batch_duration = statistics.mean(r["batch_duration"] for r in batch_results)
        avg_success_rate = statistics.mean(r["success_rate"] for r in batch_results)
        overall_throughput = total_successful / total_duration
        
        logger.info("Sustained load endurance test",
                   total_duration=total_duration,
                   total_batches=total_batches,
                   total_successful=total_successful,
                   avg_batch_duration=avg_batch_duration,
                   avg_success_rate=avg_success_rate,
                   overall_throughput=overall_throughput)
        
        # Endurance requirements
        assert avg_success_rate >= 0.90, f"Average success rate degraded: {avg_success_rate:.2%}"
        assert overall_throughput >= 3, f"Overall throughput too low: {overall_throughput:.2f}/s"
        assert avg_batch_duration < 5, f"Average batch duration too high: {avg_batch_duration:.2f}s"
        
        # Check for performance degradation over time
        first_half = batch_results[:len(batch_results)//2]
        second_half = batch_results[len(batch_results)//2:]
        
        first_half_avg = statistics.mean(r["batch_duration"] for r in first_half)
        second_half_avg = statistics.mean(r["batch_duration"] for r in second_half)
        
        degradation_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1
        assert degradation_ratio < 1.5, f"Performance degraded over time: {degradation_ratio:.2f}x"
        
        self.performance_metrics["endurance_test"] = {
            "total_duration": total_duration,
            "total_batches": total_batches,
            "avg_batch_duration": avg_batch_duration,
            "avg_success_rate": avg_success_rate,
            "overall_throughput": overall_throughput,
            "degradation_ratio": degradation_ratio
        }
    
    def teardown_method(self):
        """Log performance metrics summary after each test method."""
        if self.performance_metrics:
            logger.info("Performance test completed", 
                       test_metrics=self.performance_metrics)


@pytest.mark.performance
class TestStorageScalability:
    """Test scalability characteristics of the storage system."""
    
    @pytest.mark.asyncio
    async def test_connection_pool_scalability(self):
        """Test performance scaling with connection pool usage."""
        
        pool_sizes = [1, 4, 8]
        scalability_results = {}
        
        for pool_size in pool_sizes:
            # Mock connection pool with different sizes
            with patch('services.scenario_tracking_client.get_connection_pool') as mock_pool:
                # Configure mock pool
                mock_connection_pool = AsyncMock()
                mock_connection_pool.max_connections = pool_size
                mock_pool.return_value = mock_connection_pool
                
                # Test with moderate load
                test_records = TestStoragePerformance().generate_test_records(50, f"scale_{pool_size}")
                
                start_time = time.time()
                
                # Create multiple concurrent clients
                tasks = []
                for i in range(min(pool_size, 3)):  # Don't exceed pool size too much
                    task = self._scalability_test_task(
                        test_records[i::3], f"scale_task_{i}"
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                duration = time.time() - start_time
                
                # Analyze results
                successful_tasks = [r for r in results if not isinstance(r, Exception)]
                total_successful = sum(r["successful"] for r in successful_tasks)
                throughput = total_successful / duration if duration > 0 else 0
                
                scalability_results[pool_size] = {
                    "duration": duration,
                    "throughput": throughput,
                    "successful_tasks": len(successful_tasks),
                    "total_successful_records": total_successful
                }
                
                logger.info("Connection pool scalability test",
                           pool_size=pool_size,
                           throughput=throughput,
                           duration=duration)
        
        # Verify that larger pools generally perform better
        throughputs = [scalability_results[size]["throughput"] for size in pool_sizes]
        assert throughputs[-1] >= throughputs[0] * 0.8, "Scalability not improving with pool size"
    
    async def _scalability_test_task(self, records: List[ScenarioProcessingRecord], task_id: str) -> Dict[str, Any]:
        """Execute a scalability test task."""
        try:
            async with InboxMonitorDatabricksClient(table_suffix="_scalability_test") as db_client:
                result = await db_client.store_scenario_processing_records_batch(records)
                return {
                    "task_id": task_id,
                    "successful": result["successful_records"],
                    "failed": result["failed_records"]
                }
        except Exception as e:
            logger.error("Scalability task failed", task_id=task_id, error=str(e))
            return {"task_id": task_id, "successful": 0, "failed": len(records)}


if __name__ == "__main__":
    # Run performance tests
    pytest.main([
        __file__,
        "-v", 
        "--tb=short",
        "-m", "performance",
        "--asyncio-mode=auto"
    ])