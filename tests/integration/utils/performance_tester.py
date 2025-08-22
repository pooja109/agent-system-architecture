#!/usr/bin/env python3
"""
Performance Testing Utilities
=============================

Utilities for performance testing with baseline establishment and validation.
"""

import time
import statistics
import json
import requests
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import threading


class PerformanceTester:
    """Performance testing utility with baseline establishment."""
    
    def __init__(self, results_dir: Path = None):
        """Initialize performance tester."""
        self.results_dir = results_dir or Path(__file__).parent.parent.parent / "performance-results"
        self.results_dir.mkdir(exist_ok=True)
        self.baselines = {}
        self.load_baselines()
    
    def load_baselines(self):
        """Load existing performance baselines."""
        baseline_file = self.results_dir / "baselines.json"
        if baseline_file.exists():
            try:
                self.baselines = json.loads(baseline_file.read_text())
            except Exception as e:
                print(f"Warning: Could not load baselines: {e}")
                self.baselines = {}
    
    def save_baselines(self):
        """Save performance baselines."""
        baseline_file = self.results_dir / "baselines.json"
        try:
            baseline_file.write_text(json.dumps(self.baselines, indent=2))
        except Exception as e:
            print(f"Warning: Could not save baselines: {e}")
    
    def establish_baseline(self, service_name: str, service_url: str, 
                          duration: int = 30, concurrent_requests: int = 5) -> Dict[str, Any]:
        """Establish performance baseline for a service."""
        print(f"🎯 Establishing baseline for {service_name}...")
        
        # Run baseline performance test
        results = self.run_load_test(
            service_url=service_url,
            endpoint="/health",
            duration=duration,
            concurrent_requests=concurrent_requests,
            test_type="baseline"
        )
        
        if results["success"]:
            # Store baseline metrics
            baseline = {
                "service_name": service_name,
                "service_url": service_url,
                "established_at": time.time(),
                "test_duration": duration,
                "concurrent_requests": concurrent_requests,
                "metrics": {
                    "avg_response_time": results["metrics"]["avg_response_time"],
                    "p95_response_time": results["metrics"]["p95_response_time"],
                    "p99_response_time": results["metrics"]["p99_response_time"],
                    "success_rate": results["metrics"]["success_rate"],
                    "requests_per_second": results["metrics"]["requests_per_second"],
                    "error_rate": results["metrics"]["error_rate"]
                },
                "thresholds": {
                    # Set thresholds as 150% of baseline for warnings
                    "max_avg_response_time": results["metrics"]["avg_response_time"] * 1.5,
                    "max_p95_response_time": results["metrics"]["p95_response_time"] * 1.5,
                    "min_success_rate": max(95.0, results["metrics"]["success_rate"] * 0.95),
                    "min_requests_per_second": results["metrics"]["requests_per_second"] * 0.8,
                    "max_error_rate": min(5.0, results["metrics"]["error_rate"] * 2.0)
                }
            }
            
            self.baselines[service_name] = baseline
            self.save_baselines()
            
            print(f"✅ Baseline established for {service_name}")
            print(f"   Avg Response Time: {baseline['metrics']['avg_response_time']:.3f}s")
            print(f"   Success Rate: {baseline['metrics']['success_rate']:.1f}%")
            print(f"   Requests/sec: {baseline['metrics']['requests_per_second']:.1f}")
            
            return baseline
        else:
            print(f"❌ Failed to establish baseline for {service_name}: {results.get('error', 'Unknown error')}")
            return None
    
    def run_load_test(self, service_url: str, endpoint: str = "/health", 
                     duration: int = 30, concurrent_requests: int = 10,
                     test_type: str = "load") -> Dict[str, Any]:
        """Run load test against a service."""
        
        results = {
            "test_type": test_type,
            "service_url": service_url,
            "endpoint": endpoint,
            "duration": duration,
            "concurrent_requests": concurrent_requests,
            "start_time": time.time(),
            "success": False,
            "metrics": {},
            "raw_results": []
        }
        
        def make_request() -> Dict[str, Any]:
            """Make a single request and measure performance."""
            start_time = time.time()
            try:
                response = requests.get(f"{service_url}{endpoint}", timeout=10)
                end_time = time.time()
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "response_size": len(response.content),
                    "timestamp": start_time
                }
            except Exception as e:
                end_time = time.time()
                return {
                    "success": False,
                    "error": str(e),
                    "response_time": end_time - start_time,
                    "timestamp": start_time
                }
        
        # Run concurrent requests for specified duration
        end_time = time.time() + duration
        all_results = []
        
        with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = []
            
            while time.time() < end_time:
                # Submit concurrent requests
                for _ in range(concurrent_requests):
                    if time.time() >= end_time:
                        break
                    future = executor.submit(make_request)
                    futures.append(future)
                
                # Collect completed results
                completed_futures = []
                for future in futures:
                    if future.done():
                        try:
                            result = future.result()
                            all_results.append(result)
                            completed_futures.append(future)
                        except Exception as e:
                            print(f"Error in request: {e}")
                            completed_futures.append(future)
                
                # Remove completed futures
                for future in completed_futures:
                    futures.remove(future)
                
                # Small delay to prevent overwhelming
                time.sleep(0.01)
            
            # Wait for remaining futures
            for future in as_completed(futures, timeout=30):
                try:
                    result = future.result()
                    all_results.append(result)
                except Exception as e:
                    print(f"Error in request: {e}")
        
        # Analyze results
        if all_results:
            successful_results = [r for r in all_results if r.get("success", False)]
            failed_results = [r for r in all_results if not r.get("success", False)]
            
            if successful_results:
                response_times = [r["response_time"] for r in successful_results]
                
                results["metrics"] = {
                    "total_requests": len(all_results),
                    "successful_requests": len(successful_results),
                    "failed_requests": len(failed_results),
                    "success_rate": (len(successful_results) / len(all_results)) * 100,
                    "error_rate": (len(failed_results) / len(all_results)) * 100,
                    "avg_response_time": statistics.mean(response_times),
                    "median_response_time": statistics.median(response_times),
                    "min_response_time": min(response_times),
                    "max_response_time": max(response_times),
                    "p95_response_time": self._percentile(response_times, 95),
                    "p99_response_time": self._percentile(response_times, 99),
                    "requests_per_second": len(successful_results) / duration,
                    "test_duration": duration
                }
                results["success"] = True
            else:
                results["error"] = "No successful requests"
                results["metrics"] = {
                    "total_requests": len(all_results),
                    "successful_requests": 0,
                    "failed_requests": len(failed_results),
                    "success_rate": 0,
                    "error_rate": 100
                }
        else:
            results["error"] = "No requests completed"
        
        results["end_time"] = time.time()
        results["raw_results"] = all_results
        
        return results
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_data) - 1)
            weight = index - lower_index
            return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
    
    def validate_against_baseline(self, service_name: str, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate performance test results against baseline."""
        if service_name not in self.baselines:
            return {
                "baseline_exists": False,
                "message": f"No baseline exists for {service_name}. Run establish_baseline() first."
            }
        
        baseline = self.baselines[service_name]
        thresholds = baseline["thresholds"]
        metrics = test_results.get("metrics", {})
        
        validation_results = {
            "baseline_exists": True,
            "service_name": service_name,
            "test_passed": True,
            "violations": [],
            "comparisons": {}
        }
        
        # Check each threshold
        checks = [
            ("avg_response_time", "max_avg_response_time", "<="),
            ("p95_response_time", "max_p95_response_time", "<="),
            ("success_rate", "min_success_rate", ">="),
            ("requests_per_second", "min_requests_per_second", ">="),
            ("error_rate", "max_error_rate", "<=")
        ]
        
        for metric_name, threshold_name, operator in checks:
            metric_value = metrics.get(metric_name, 0)
            threshold_value = thresholds.get(threshold_name, 0)
            baseline_value = baseline["metrics"].get(metric_name, 0)
            
            if operator == "<=" and metric_value > threshold_value:
                validation_results["violations"].append({
                    "metric": metric_name,
                    "actual": metric_value,
                    "threshold": threshold_value,
                    "baseline": baseline_value,
                    "message": f"{metric_name} ({metric_value:.3f}) exceeds threshold ({threshold_value:.3f})"
                })
                validation_results["test_passed"] = False
            elif operator == ">=" and metric_value < threshold_value:
                validation_results["violations"].append({
                    "metric": metric_name,
                    "actual": metric_value,
                    "threshold": threshold_value,
                    "baseline": baseline_value,
                    "message": f"{metric_name} ({metric_value:.3f}) below threshold ({threshold_value:.3f})"
                })
                validation_results["test_passed"] = False
            
            # Store comparison data
            validation_results["comparisons"][metric_name] = {
                "actual": metric_value,
                "baseline": baseline_value,
                "threshold": threshold_value,
                "percentage_change": ((metric_value - baseline_value) / baseline_value * 100) if baseline_value > 0 else 0,
                "within_threshold": (
                    (operator == "<=" and metric_value <= threshold_value) or
                    (operator == ">=" and metric_value >= threshold_value)
                )
            }
        
        return validation_results
    
    def run_stress_test(self, service_name: str, service_url: str) -> Dict[str, Any]:
        """Run stress test to find breaking points."""
        print(f"🔥 Running stress test for {service_name}...")
        
        # Gradually increase load until service degrades
        concurrent_levels = [1, 5, 10, 20, 50, 100]
        stress_results = []
        
        for concurrent_requests in concurrent_levels:
            print(f"   Testing with {concurrent_requests} concurrent requests...")
            
            result = self.run_load_test(
                service_url=service_url,
                endpoint="/health",
                duration=30,
                concurrent_requests=concurrent_requests,
                test_type="stress"
            )
            
            if result["success"]:
                metrics = result["metrics"]
                stress_results.append({
                    "concurrent_requests": concurrent_requests,
                    "avg_response_time": metrics["avg_response_time"],
                    "success_rate": metrics["success_rate"],
                    "requests_per_second": metrics["requests_per_second"],
                    "error_rate": metrics["error_rate"]
                })
                
                # Stop if performance degrades significantly
                if (metrics["success_rate"] < 95 or 
                    metrics["avg_response_time"] > 5.0 or
                    metrics["error_rate"] > 10):
                    print(f"   Performance degradation detected at {concurrent_requests} concurrent requests")
                    break
            else:
                print(f"   Test failed at {concurrent_requests} concurrent requests")
                break
        
        return {
            "service_name": service_name,
            "stress_test_results": stress_results,
            "max_concurrent_requests": max([r["concurrent_requests"] for r in stress_results]) if stress_results else 0,
            "recommendations": self._generate_stress_recommendations(stress_results)
        }
    
    def _generate_stress_recommendations(self, stress_results: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on stress test results."""
        recommendations = []
        
        if not stress_results:
            recommendations.append("Service failed under minimal load - investigate immediately")
            return recommendations
        
        max_concurrent = max([r["concurrent_requests"] for r in stress_results])
        
        if max_concurrent < 10:
            recommendations.append("Service cannot handle moderate load - consider performance optimization")
        elif max_concurrent < 50:
            recommendations.append("Service handles light load well - monitor under production load")
        else:
            recommendations.append("Service demonstrates good performance under stress")
        
        # Check response time degradation
        if len(stress_results) > 1:
            response_time_increase = (
                stress_results[-1]["avg_response_time"] / stress_results[0]["avg_response_time"]
            )
            if response_time_increase > 3:
                recommendations.append("Response time increases significantly under load")
        
        return recommendations
    
    def run_comprehensive_performance_test(self, service_endpoints: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive performance test suite."""
        results = {
            "test_suite": "comprehensive_performance",
            "start_time": time.time(),
            "services": {},
            "summary": {
                "services_tested": 0,
                "baselines_established": 0,
                "performance_regressions": 0,
                "stress_test_passes": 0
            }
        }
        
        for service_name, config in service_endpoints.items():
            service_url = config["base_url"]
            print(f"\n🚀 Testing performance for {service_name}...")
            
            service_results = {
                "service_name": service_name,
                "service_url": service_url,
                "baseline_test": None,
                "load_test": None,
                "stress_test": None,
                "validation": None
            }
            
            # Establish baseline if none exists or service is live
            if service_name not in self.baselines or config.get("is_live", False):
                try:
                    baseline = self.establish_baseline(service_name, service_url)
                    service_results["baseline_test"] = baseline
                    if baseline:
                        results["summary"]["baselines_established"] += 1
                except Exception as e:
                    print(f"   ⚠️  Could not establish baseline: {e}")
                    service_results["baseline_test"] = {"error": str(e)}
            
            # Run load test if service is available
            if config.get("is_live", False) or service_name in self.baselines:
                try:
                    load_result = self.run_load_test(
                        service_url=service_url,
                        duration=60,
                        concurrent_requests=10,
                        test_type="load"
                    )
                    service_results["load_test"] = load_result
                    
                    # Validate against baseline
                    if service_name in self.baselines:
                        validation = self.validate_against_baseline(service_name, load_result)
                        service_results["validation"] = validation
                        
                        if not validation.get("test_passed", False):
                            results["summary"]["performance_regressions"] += 1
                
                except Exception as e:
                    print(f"   ⚠️  Load test failed: {e}")
                    service_results["load_test"] = {"error": str(e)}
            
            # Run stress test if service is live
            if config.get("is_live", False):
                try:
                    stress_result = self.run_stress_test(service_name, service_url)
                    service_results["stress_test"] = stress_result
                    
                    if stress_result.get("max_concurrent_requests", 0) >= 10:
                        results["summary"]["stress_test_passes"] += 1
                
                except Exception as e:
                    print(f"   ⚠️  Stress test failed: {e}")
                    service_results["stress_test"] = {"error": str(e)}
            
            results["services"][service_name] = service_results
            results["summary"]["services_tested"] += 1
        
        results["end_time"] = time.time()
        
        # Save comprehensive results
        results_file = self.results_dir / f"performance_test_{int(time.time())}.json"
        try:
            results_file.write_text(json.dumps(results, indent=2))
            print(f"\n📊 Results saved to {results_file}")
        except Exception as e:
            print(f"Warning: Could not save results: {e}")
        
        return results


def create_performance_test_fixtures():
    """Create performance test fixtures for pytest."""
    import pytest
    
    @pytest.fixture(scope="class")
    def performance_tester():
        """Performance tester fixture."""
        return PerformanceTester()
    
    return {"performance_tester": performance_tester}


if __name__ == "__main__":
    # Test performance tester
    tester = PerformanceTester()
    
    # Test with a mock service (will fail, but demonstrates functionality)
    print("Testing PerformanceTester...")
    
    # This would establish baseline if service was running
    # baseline = tester.establish_baseline("test_service", "http://localhost:8080")
    
    print("✅ PerformanceTester initialized successfully")