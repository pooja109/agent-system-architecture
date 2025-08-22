"""
Storage Load Tests for Scenario Tracking System
===============================================

High-volume load testing to validate storage system performance under
extreme conditions and concurrent access patterns.
"""

import pytest
import asyncio
import time
import random
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor
import structlog

# System under test imports
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

logger = structlog.get_logger(__name__)


class TestStorageLoadTesting:
    """High-volume load testing for storage operations."""
    
    @pytest.fixture(autouse=True)
    async def setup_load_test_environment(self):
        """Setup load test environment."""
        self.table_suffix = "_load_test"
        self.load_test_results = {}
        self.max_test_duration = 300  # 5 minutes max per test
    
    def generate_realistic_test_records(self, count: int, prefix: str = "load_test") -> List[ScenarioProcessingRecord]:
        """Generate realistic test records with varied characteristics."""
        records = []
        base_time = datetime.now(timezone.utc)
        
        # Realistic scenario distribution
        scenario_weights = {
            ScenarioType.SCENARIO_5: 0.3,  # Most common - positive feedback
            ScenarioType.SCENARIO_6: 0.2,  # Negative feedback
            ScenarioType.SCENARIO_7: 0.15, # Service inquiries
            ScenarioType.SCENARIO_8: 0.1,  # Out of office
            ScenarioType.SCENARIO_9: 0.1,  # Invalid email
            ScenarioType.SCENARIO_10: 0.1, # No longer works
            ScenarioType.SCENARIO_11: 0.05 # Unknown
        }
        
        for i in range(count):
            # Select scenario type based on realistic weights
            scenario_type = random.choices(
                list(scenario_weights.keys()),
                weights=list(scenario_weights.values())
            )[0]
            
            # Generate realistic field values
            ai_confidence = random.uniform(0.6, 0.95)
            processing_time = random.randint(100, 5000)  # 0.1s to 5s
            
            record = ScenarioProcessingRecord(
                process_id=f"{prefix}_{i}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                email_id=f"{prefix}_email_{i}_{random.randint(100, 999)}",
                sender_email=f"{prefix}_{i}@load-test-{random.randint(1, 100)}.com",
                sender_name=f"Load Test User {i}",
                recipient_emails=[f"recipient_{j}@company.com" for j in range(random.randint(1, 3))],
                subject=f"Load test email {i} - {random.choice(['Feedback', 'Question', 'Issue', 'Request'])}",
                received_datetime=base_time - timedelta(
                    minutes=random.randint(0, 1440),  # Last 24 hours
                    seconds=random.randint(0, 59)
                ),
                process_success=random.choice([True] * 9 + [False]),  # 90% success rate
                processing_duration_ms=processing_time,
                scenario_type=scenario_type,
                ai_confidence=ai_confidence,
                ai_intent=random.choice(["POSITIVE", "NEGATIVE", "SERVICE_INQUIRY", "UNKNOWN"]),
                ai_reasoning=f"AI analysis for record {i}" if ai_confidence > 0.8 else None,
                expert_assigned=f"Expert_{random.randint(1, 10)}" if scenario_type == ScenarioType.SCENARIO_5 else None,
                case_created=f"CASE_{random.randint(10000, 99999)}" if scenario_type == ScenarioType.SCENARIO_5 else None,
                emails_forwarded=[f"forward_{j}@company.com" for j in range(random.randint(0, 2))],
                test_mode=True,
                environment="load_test"
            )
            records.append(record)
        
        return records
    
    @pytest.mark.load
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_volume_sequential_load(self):
        """Test sequential processing of high volume data."""
        
        total_records = 1000
        batch_size = 50
        
        test_records = self.generate_realistic_test_records(total_records, "sequential_load")
        
        start_time = time.time()
        total_successful = 0
        total_failed = 0
        batch_timings = []
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            for i in range(0, total_records, batch_size):
                batch = test_records[i:i + batch_size]
                
                batch_start = time.time()
                result = await db_client.store_scenario_processing_records_batch(batch)
                batch_end = time.time()
                
                batch_duration = batch_end - batch_start
                batch_timings.append(batch_duration)
                
                total_successful += result["successful_records"]
                total_failed += result["failed_records"]
                
                # Check if we're taking too long
                if time.time() - start_time > self.max_test_duration:
                    logger.warning("High volume sequential test timed out")
                    break
                
                # Brief pause to prevent overwhelming the system
                await asyncio.sleep(0.1)
        
        total_duration = time.time() - start_time
        overall_throughput = total_successful / total_duration if total_duration > 0 else 0
        avg_batch_time = statistics.mean(batch_timings)
        success_rate = total_successful / (total_successful + total_failed) if (total_successful + total_failed) > 0 else 0
        
        logger.info("High volume sequential load test results",
                   total_records=total_records,
                   total_successful=total_successful,
                   total_failed=total_failed,
                   total_duration=total_duration,
                   overall_throughput=overall_throughput,
                   avg_batch_time=avg_batch_time,
                   success_rate=success_rate)
        
        # Load test requirements
        assert success_rate >= 0.85, f"Success rate too low under load: {success_rate:.2%}"
        assert overall_throughput >= 10, f"Throughput too low: {overall_throughput:.2f}/s"
        assert avg_batch_time < 10, f"Average batch time too high: {avg_batch_time:.2f}s"
        
        self.load_test_results["high_volume_sequential"] = {
            "total_records": total_records,
            "total_successful": total_successful,
            "success_rate": success_rate,
            "overall_throughput": overall_throughput,
            "avg_batch_time": avg_batch_time
        }
    
    @pytest.mark.load
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_concurrency_load(self):
        """Test high concurrency with many simultaneous operations."""
        
        num_concurrent_tasks = 20
        records_per_task = 25
        
        start_time = time.time()
        
        # Create concurrent tasks
        tasks = []
        for i in range(num_concurrent_tasks):
            task_records = self.generate_realistic_test_records(
                records_per_task, 
                f"concurrent_{i}"
            )
            task = self._concurrent_load_task(task_records, f"load_task_{i}")
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        # Analyze results
        successful_tasks = [r for r in results if not isinstance(r, Exception)]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        total_successful = sum(r["successful"] for r in successful_tasks)
        total_failed = sum(r["failed"] for r in successful_tasks)
        exception_count = len(exceptions)
        
        overall_throughput = total_successful / total_duration if total_duration > 0 else 0
        success_rate = total_successful / (total_successful + total_failed) if (total_successful + total_failed) > 0 else 0
        task_success_rate = len(successful_tasks) / num_concurrent_tasks
        
        logger.info("High concurrency load test results",
                   concurrent_tasks=num_concurrent_tasks,
                   records_per_task=records_per_task,
                   total_successful=total_successful,
                   total_failed=total_failed,
                   exception_count=exception_count,
                   total_duration=total_duration,
                   overall_throughput=overall_throughput,
                   success_rate=success_rate,
                   task_success_rate=task_success_rate)
        
        # High concurrency requirements
        assert task_success_rate >= 0.8, f"Too many tasks failed: {task_success_rate:.2%}"
        assert success_rate >= 0.75, f"Success rate too low under concurrency: {success_rate:.2%}"
        assert overall_throughput >= 15, f"Concurrent throughput too low: {overall_throughput:.2f}/s"
        assert exception_count <= num_concurrent_tasks * 0.2, f"Too many exceptions: {exception_count}"
        
        self.load_test_results["high_concurrency"] = {
            "concurrent_tasks": num_concurrent_tasks,
            "total_successful": total_successful,
            "success_rate": success_rate,
            "task_success_rate": task_success_rate,
            "overall_throughput": overall_throughput,
            "exception_count": exception_count
        }
    
    async def _concurrent_load_task(self, records: List[ScenarioProcessingRecord], task_id: str) -> Dict[str, Any]:
        """Execute a concurrent load testing task."""
        try:
            # Add some random delay to simulate realistic timing
            await asyncio.sleep(random.uniform(0, 0.5))
            
            async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
                result = await db_client.store_scenario_processing_records_batch(records)
                
                return {
                    "task_id": task_id,
                    "successful": result["successful_records"],
                    "failed": result["failed_records"],
                    "duration": result.get("processing_duration_ms", 0) / 1000
                }
                
        except Exception as e:
            logger.error("Concurrent load task failed", task_id=task_id, error=str(e))
            return {
                "task_id": task_id, 
                "successful": 0, 
                "failed": len(records),
                "error": str(e)
            }
    
    @pytest.mark.load
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_burst_load_patterns(self):
        """Test handling of burst traffic patterns."""
        
        # Simulate burst patterns: high load periods followed by low load
        burst_cycles = 5
        records_per_burst = 100
        quiet_period_seconds = 2
        
        burst_results = []
        start_time = time.time()
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            for cycle in range(burst_cycles):
                logger.info(f"Starting burst cycle {cycle + 1}/{burst_cycles}")
                
                # Generate burst records
                burst_records = self.generate_realistic_test_records(
                    records_per_burst,
                    f"burst_{cycle}"
                )
                
                # Process burst as quickly as possible
                burst_start = time.time()
                
                # Split into smaller concurrent batches for maximum load
                batch_size = 20
                burst_tasks = []
                
                for i in range(0, len(burst_records), batch_size):
                    batch = burst_records[i:i + batch_size]
                    task = self._burst_batch_task(db_client, batch, f"burst_{cycle}_batch_{i // batch_size}")
                    burst_tasks.append(task)
                
                batch_results = await asyncio.gather(*burst_tasks, return_exceptions=True)
                burst_end = time.time()
                
                burst_duration = burst_end - burst_start
                successful_batches = [r for r in batch_results if not isinstance(r, Exception)]
                burst_successful = sum(r["successful"] for r in successful_batches)
                burst_failed = sum(r["failed"] for r in successful_batches)
                
                burst_throughput = burst_successful / burst_duration if burst_duration > 0 else 0
                burst_success_rate = burst_successful / (burst_successful + burst_failed) if (burst_successful + burst_failed) > 0 else 0
                
                burst_results.append({
                    "cycle": cycle,
                    "duration": burst_duration,
                    "successful": burst_successful,
                    "failed": burst_failed,
                    "throughput": burst_throughput,
                    "success_rate": burst_success_rate
                })
                
                logger.info(f"Burst cycle {cycle + 1} completed",
                           duration=burst_duration,
                           throughput=burst_throughput,
                           success_rate=burst_success_rate)
                
                # Quiet period between bursts
                if cycle < burst_cycles - 1:
                    await asyncio.sleep(quiet_period_seconds)
        
        total_duration = time.time() - start_time
        
        # Analyze burst performance
        avg_burst_throughput = statistics.mean(r["throughput"] for r in burst_results)
        avg_burst_success_rate = statistics.mean(r["success_rate"] for r in burst_results)
        min_success_rate = min(r["success_rate"] for r in burst_results)
        max_throughput = max(r["throughput"] for r in burst_results)
        
        logger.info("Burst load pattern test results",
                   total_cycles=burst_cycles,
                   total_duration=total_duration,
                   avg_burst_throughput=avg_burst_throughput,
                   avg_burst_success_rate=avg_burst_success_rate,
                   min_success_rate=min_success_rate,
                   max_throughput=max_throughput)
        
        # Burst load requirements
        assert avg_burst_success_rate >= 0.8, f"Average burst success rate too low: {avg_burst_success_rate:.2%}"
        assert min_success_rate >= 0.7, f"Minimum burst success rate too low: {min_success_rate:.2%}"
        assert avg_burst_throughput >= 20, f"Average burst throughput too low: {avg_burst_throughput:.2f}/s"
        
        self.load_test_results["burst_patterns"] = {
            "burst_cycles": burst_cycles,
            "avg_burst_throughput": avg_burst_throughput,
            "avg_burst_success_rate": avg_burst_success_rate,
            "min_success_rate": min_success_rate,
            "max_throughput": max_throughput
        }
    
    async def _burst_batch_task(self, db_client: InboxMonitorDatabricksClient, 
                               records: List[ScenarioProcessingRecord], 
                               batch_id: str) -> Dict[str, Any]:
        """Execute a batch task within a burst test."""
        try:
            result = await db_client.store_scenario_processing_records_batch(records)
            return {
                "batch_id": batch_id,
                "successful": result["successful_records"],
                "failed": result["failed_records"]
            }
        except Exception as e:
            logger.error("Burst batch task failed", batch_id=batch_id, error=str(e))
            return {"batch_id": batch_id, "successful": 0, "failed": len(records)}
    
    @pytest.mark.load
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_sustained_high_load_endurance(self):
        """Test sustained high load over extended period."""
        
        # Run for 2 minutes with continuous load
        test_duration_seconds = 120
        batch_interval_seconds = 1  # High frequency
        records_per_batch = 20
        
        start_time = time.time()
        batch_results = []
        batch_number = 0
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            while (time.time() - start_time) < test_duration_seconds:
                batch_number += 1
                
                # Generate batch with realistic distribution
                batch_records = self.generate_realistic_test_records(
                    records_per_batch,
                    f"sustained_{batch_number}"
                )
                
                batch_start = time.time()
                
                try:
                    result = await db_client.store_scenario_processing_records_batch(batch_records)
                    
                    batch_duration = time.time() - batch_start
                    
                    batch_results.append({
                        "batch_number": batch_number,
                        "batch_duration": batch_duration,
                        "successful_records": result["successful_records"],
                        "failed_records": result["failed_records"],
                        "success_rate": result["success_rate"],
                        "elapsed_time": time.time() - start_time
                    })
                    
                except Exception as e:
                    logger.error(f"Sustained load batch {batch_number} failed", error=str(e))
                    batch_results.append({
                        "batch_number": batch_number,
                        "batch_duration": time.time() - batch_start,
                        "successful_records": 0,
                        "failed_records": records_per_batch,
                        "success_rate": 0.0,
                        "error": str(e),
                        "elapsed_time": time.time() - start_time
                    })
                
                # Maintain high load frequency
                await asyncio.sleep(max(0, batch_interval_seconds - (time.time() - batch_start)))
        
        total_duration = time.time() - start_time
        total_batches = len(batch_results)
        total_successful = sum(r["successful_records"] for r in batch_results)
        total_failed = sum(r["failed_records"] for r in batch_results)
        
        # Performance analysis over time
        avg_success_rate = statistics.mean(r["success_rate"] for r in batch_results)
        avg_batch_duration = statistics.mean(r["batch_duration"] for r in batch_results)
        overall_throughput = total_successful / total_duration if total_duration > 0 else 0
        
        # Check for performance degradation over time
        first_third = batch_results[:len(batch_results)//3]
        last_third = batch_results[-len(batch_results)//3:]
        
        first_third_avg_duration = statistics.mean(r["batch_duration"] for r in first_third)
        last_third_avg_duration = statistics.mean(r["batch_duration"] for r in last_third)
        
        first_third_avg_success = statistics.mean(r["success_rate"] for r in first_third)
        last_third_avg_success = statistics.mean(r["success_rate"] for r in last_third)
        
        duration_degradation = last_third_avg_duration / first_third_avg_duration if first_third_avg_duration > 0 else 1
        success_degradation = first_third_avg_success / last_third_avg_success if last_third_avg_success > 0 else 1
        
        logger.info("Sustained high load endurance test results",
                   total_duration=total_duration,
                   total_batches=total_batches,
                   total_successful=total_successful,
                   total_failed=total_failed,
                   avg_success_rate=avg_success_rate,
                   avg_batch_duration=avg_batch_duration,
                   overall_throughput=overall_throughput,
                   duration_degradation=duration_degradation,
                   success_degradation=success_degradation)
        
        # Sustained load requirements
        assert avg_success_rate >= 0.85, f"Average success rate too low: {avg_success_rate:.2%}"
        assert overall_throughput >= 12, f"Overall throughput too low: {overall_throughput:.2f}/s"
        assert duration_degradation < 2.0, f"Performance degraded too much over time: {duration_degradation:.2f}x"
        assert success_degradation < 1.3, f"Success rate degraded too much: {success_degradation:.2f}x"
        
        self.load_test_results["sustained_high_load"] = {
            "total_duration": total_duration,
            "total_batches": total_batches,
            "avg_success_rate": avg_success_rate,
            "overall_throughput": overall_throughput,
            "duration_degradation": duration_degradation,
            "success_degradation": success_degradation
        }
    
    @pytest.mark.load
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_pressure_under_load(self):
        """Test system behavior under memory pressure during load."""
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate increasingly large batches to create memory pressure
        batch_sizes = [50, 100, 200, 300, 400, 500]
        memory_results = []
        
        async with InboxMonitorDatabricksClient(table_suffix=self.table_suffix) as db_client:
            for batch_size in batch_sizes:
                # Generate large batch
                large_batch = self.generate_realistic_test_records(
                    batch_size,
                    f"memory_pressure_{batch_size}"
                )
                
                # Measure memory before
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Process batch
                batch_start = time.time()
                try:
                    result = await db_client.store_scenario_processing_records_batch(large_batch)
                    batch_success = True
                except Exception as e:
                    logger.error(f"Memory pressure batch {batch_size} failed", error=str(e))
                    result = {"successful_records": 0, "failed_records": batch_size, "success_rate": 0.0}
                    batch_success = False
                
                batch_duration = time.time() - batch_start
                
                # Measure memory after
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = memory_after - memory_before
                
                memory_results.append({
                    "batch_size": batch_size,
                    "batch_success": batch_success,
                    "batch_duration": batch_duration,
                    "success_rate": result["success_rate"],
                    "memory_before_mb": memory_before,
                    "memory_after_mb": memory_after,
                    "memory_increase_mb": memory_increase
                })
                
                logger.info(f"Memory pressure test batch {batch_size}",
                           batch_success=batch_success,
                           memory_increase=memory_increase,
                           success_rate=result["success_rate"])
                
                # Brief pause for garbage collection
                await asyncio.sleep(1)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        # Analysis
        successful_batches = [r for r in memory_results if r["batch_success"]]
        max_memory_increase = max(r["memory_increase_mb"] for r in memory_results)
        avg_success_rate = statistics.mean(r["success_rate"] for r in successful_batches) if successful_batches else 0
        
        logger.info("Memory pressure load test results",
                   initial_memory_mb=initial_memory,
                   final_memory_mb=final_memory,
                   total_memory_increase_mb=total_memory_increase,
                   max_memory_increase_mb=max_memory_increase,
                   successful_batches=len(successful_batches),
                   avg_success_rate=avg_success_rate)
        
        # Memory pressure requirements
        assert len(successful_batches) >= len(batch_sizes) * 0.7, "Too many batches failed under memory pressure"
        assert max_memory_increase < 50, f"Memory increase per batch too high: {max_memory_increase:.2f}MB"
        assert total_memory_increase < 150, f"Total memory increase too high: {total_memory_increase:.2f}MB"
        
        self.load_test_results["memory_pressure"] = {
            "successful_batches": len(successful_batches),
            "total_batches": len(batch_sizes),
            "max_memory_increase_mb": max_memory_increase,
            "total_memory_increase_mb": total_memory_increase,
            "avg_success_rate": avg_success_rate
        }
    
    def teardown_method(self):
        """Log load test results summary after each test method."""
        if self.load_test_results:
            logger.info("Load test completed", 
                       load_test_results=self.load_test_results)


@pytest.mark.load
class TestExtremeLoadConditions:
    """Test system behavior under extreme load conditions."""
    
    @pytest.mark.asyncio
    async def test_extreme_concurrency_stress(self):
        """Test with extreme concurrency levels."""
        
        # Test with very high concurrency
        extreme_concurrency = 50
        records_per_task = 10
        
        start_time = time.time()
        
        # Create extreme concurrent load
        tasks = []
        for i in range(extreme_concurrency):
            task_records = TestStorageLoadTesting().generate_realistic_test_records(
                records_per_task, f"extreme_{i}"
            )
            task = self._extreme_concurrent_task(task_records, f"extreme_task_{i}")
            tasks.append(task)
        
        # Execute with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=180  # 3 minutes max
            )
        except asyncio.TimeoutError:
            logger.error("Extreme concurrency test timed out")
            results = [Exception("Timeout")] * extreme_concurrency
        
        total_duration = time.time() - start_time
        
        # Analyze extreme load results
        successful_tasks = [r for r in results if not isinstance(r, Exception) and r.get("successful", 0) > 0]
        failed_tasks = [r for r in results if isinstance(r, Exception) or r.get("successful", 0) == 0]
        
        task_success_rate = len(successful_tasks) / extreme_concurrency if extreme_concurrency > 0 else 0
        total_successful = sum(r.get("successful", 0) for r in successful_tasks)
        
        logger.info("Extreme concurrency stress test results",
                   extreme_concurrency=extreme_concurrency,
                   task_success_rate=task_success_rate,
                   total_successful=total_successful,
                   failed_tasks=len(failed_tasks),
                   total_duration=total_duration)
        
        # Under extreme load, we accept degraded performance but system should not crash
        assert task_success_rate >= 0.5, f"Too many tasks failed under extreme load: {task_success_rate:.2%}"
        assert total_successful > 0, "No records processed successfully under extreme load"
        
    async def _extreme_concurrent_task(self, records: List[ScenarioProcessingRecord], task_id: str) -> Dict[str, Any]:
        """Execute an extreme concurrency task with error handling."""
        try:
            # Add random delay to spread load
            await asyncio.sleep(random.uniform(0, 1.0))
            
            async with InboxMonitorDatabricksClient(table_suffix="_extreme_test") as db_client:
                result = await db_client.store_scenario_processing_records_batch(records)
                return {
                    "task_id": task_id,
                    "successful": result["successful_records"],
                    "failed": result["failed_records"]
                }
        except Exception as e:
            logger.error("Extreme concurrent task failed", task_id=task_id, error=str(e))
            return {"task_id": task_id, "successful": 0, "failed": len(records), "error": str(e)}


if __name__ == "__main__":
    # Run load tests
    pytest.main([
        __file__,
        "-v", 
        "--tb=short",
        "-m", "load",
        "--asyncio-mode=auto"
    ])