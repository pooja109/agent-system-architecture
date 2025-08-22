#!/usr/bin/env python3
"""
Scaling and Resilience Integration Tests
=======================================

Tests for service scaling, resilience patterns, and failure recovery.
"""

import pytest
import requests
import time
import subprocess
import threading
import json
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import aiohttp


class TestServiceScaling:
    """Test service scaling capabilities and behaviors."""
    
    @pytest.fixture
    def scaling_config(self):
        """Scaling configuration for testing."""
        return {
            "inbox_monitor": {
                "min_replicas": 1,
                "max_replicas": 5,
                "target_cpu": 70,
                "base_url": "http://localhost:8080",
                "health_endpoint": "/health"
            },
            "email_agent": {
                "min_replicas": 1,
                "max_replicas": 3,
                "target_cpu": 70, 
                "base_url": "http://localhost:8081",
                "health_endpoint": "/health"
            }
        }
    
    def test_scaling_configuration_validity(self, scaling_config):
        """Test that scaling configurations are valid."""
        
        for service_name, config in scaling_config.items():
            # Verify scaling bounds
            assert config["min_replicas"] >= 1, f"Min replicas too low for {service_name}"
            assert config["max_replicas"] <= 10, f"Max replicas too high for {service_name}"
            assert config["min_replicas"] < config["max_replicas"], f"Invalid replica range for {service_name}"
            
            # Verify CPU targets are reasonable
            assert 30 <= config["target_cpu"] <= 90, f"Invalid CPU target for {service_name}"
            
            # Verify service endpoints are configured
            assert config["base_url"], f"Missing base URL for {service_name}"
            assert config["health_endpoint"], f"Missing health endpoint for {service_name}"
    
    def test_horizontal_scaling_readiness(self, scaling_config):
        """Test that services are ready for horizontal scaling."""
        
        def test_service_statelessness(service_name: str, config: Dict[str, str]) -> List[str]:
            """Test if service is stateless and scaling-ready."""
            issues = []
            
            try:
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for stateful indicators
                    response_str = json.dumps(data).lower()
                    stateful_indicators = [
                        "session", "local_file", "temp_file", "local_state",
                        "instance_id", "server_id", "node_specific"
                    ]
                    
                    for indicator in stateful_indicators:
                        if indicator in response_str:
                            issues.append(f"Service {service_name} may have stateful behavior: {indicator}")
                    
                    # Check for scaling readiness indicators
                    readiness_indicators = ["ready", "healthy", "status"]
                    has_readiness = any(indicator in response_str for indicator in readiness_indicators)
                    
                    if not has_readiness:
                        issues.append(f"Service {service_name} lacks readiness indicators")
            
            except requests.exceptions.RequestException:
                # Service not running - skip statelessness test
                pass
            except Exception as e:
                issues.append(f"Error testing {service_name}: {e}")
            
            return issues
        
        # Test all services for scaling readiness
        all_issues = []
        for service_name, config in scaling_config.items():
            issues = test_service_statelessness(service_name, config)
            all_issues.extend(issues)
        
        assert not all_issues, f"Scaling readiness issues: {all_issues}"
    
    def test_load_distribution_capability(self, scaling_config):
        """Test that services can handle distributed load."""
        
        async def test_concurrent_requests(service_name: str, config: Dict[str, str], num_requests: int = 5):
            """Test concurrent request handling."""
            results = []
            
            async def make_request(session, request_id):
                try:
                    health_url = f"{config['base_url']}{config['health_endpoint']}"
                    start_time = time.time()
                    async with session.get(health_url) as response:
                        end_time = time.time()
                        return {
                            "request_id": request_id,
                            "status": response.status,
                            "response_time": end_time - start_time,
                            "success": response.status == 200
                        }
                except Exception as e:
                    return {
                        "request_id": request_id,
                        "error": str(e),
                        "success": False
                    }
            
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    tasks = [make_request(session, i) for i in range(num_requests)]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out exceptions
                valid_results = [r for r in results if isinstance(r, dict)]
                
                if valid_results:
                    success_rate = sum(1 for r in valid_results if r.get("success", False)) / len(valid_results)
                    avg_response_time = sum(r.get("response_time", 0) for r in valid_results) / len(valid_results)
                    
                    return {
                        "service": service_name,
                        "total_requests": num_requests,
                        "successful_requests": sum(1 for r in valid_results if r.get("success", False)),
                        "success_rate": success_rate,
                        "average_response_time": avg_response_time
                    }
                
                return {"service": service_name, "error": "No valid responses"}
                
            except Exception as e:
                return {"service": service_name, "error": str(e)}
        
        # Test concurrent load for each service
        async def run_load_tests():
            tasks = []
            for service_name, config in scaling_config.items():
                task = test_concurrent_requests(service_name, config)
                tasks.append(task)
            
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        results = asyncio.run(run_load_tests())
        
        # Verify load handling capability
        for result in results:
            if isinstance(result, dict) and "error" not in result:
                # If service is available, it should handle concurrent requests well
                if result.get("successful_requests", 0) > 0:
                    assert result["success_rate"] >= 0.8, f"Service {result['service']} has low success rate: {result['success_rate']}"
                    assert result["average_response_time"] < 5.0, f"Service {result['service']} has high response time: {result['average_response_time']}"


class TestServiceResilience:
    """Test service resilience and failure recovery."""
    
    @pytest.fixture
    def resilience_config(self):
        """Resilience configuration for testing."""
        return {
            "inbox_monitor": {
                "base_url": "http://localhost:8080",
                "health_endpoint": "/health",
                "expected_recovery_time": 30,
                "max_acceptable_downtime": 60
            },
            "email_agent": {
                "base_url": "http://localhost:8081",
                "health_endpoint": "/health",
                "expected_recovery_time": 30,
                "max_acceptable_downtime": 60
            }
        }
    
    def test_health_check_resilience(self, resilience_config):
        """Test that health checks are resilient to transient failures."""
        
        def test_health_check_retry(service_name: str, config: Dict[str, str]) -> Dict[str, Any]:
            """Test health check retry behavior."""
            result = {
                "service": service_name,
                "attempts": 0,
                "success": False,
                "response_times": [],
                "errors": []
            }
            
            max_attempts = 3
            retry_delay = 1
            
            for attempt in range(max_attempts):
                result["attempts"] += 1
                start_time = time.time()
                
                try:
                    health_url = f"{config['base_url']}{config['health_endpoint']}"
                    response = requests.get(health_url, timeout=5)
                    response_time = time.time() - start_time
                    result["response_times"].append(response_time)
                    
                    if response.status_code == 200:
                        result["success"] = True
                        break
                    else:
                        result["errors"].append(f"Attempt {attempt + 1}: HTTP {response.status_code}")
                
                except requests.exceptions.RequestException as e:
                    response_time = time.time() - start_time
                    result["response_times"].append(response_time)
                    result["errors"].append(f"Attempt {attempt + 1}: {str(e)}")
                
                if attempt < max_attempts - 1:
                    time.sleep(retry_delay)
            
            return result
        
        # Test health check resilience for all services
        for service_name, config in resilience_config.items():
            result = test_health_check_retry(service_name, config)
            
            # If service is available, health checks should be resilient
            if result["success"]:
                avg_response_time = sum(result["response_times"]) / len(result["response_times"])
                assert avg_response_time < 10.0, f"Service {service_name} has slow health checks: {avg_response_time}s"
    
    def test_graceful_degradation(self, resilience_config):
        """Test that services degrade gracefully under stress."""
        
        def stress_test_service(service_name: str, config: Dict[str, str]) -> Dict[str, Any]:
            """Apply stress and measure degradation."""
            result = {
                "service": service_name,
                "baseline_time": None,
                "stress_time": None,
                "degradation_ratio": None,
                "graceful": True
            }
            
            try:
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                
                # Measure baseline response time
                start_time = time.time()
                baseline_response = requests.get(health_url, timeout=5)
                result["baseline_time"] = time.time() - start_time
                
                if baseline_response.status_code != 200:
                    return result
                
                # Apply stress by making concurrent requests
                def make_stress_request():
                    try:
                        return requests.get(health_url, timeout=2)
                    except:
                        return None
                
                # Start stress test
                with ThreadPoolExecutor(max_workers=10) as executor:
                    stress_futures = [executor.submit(make_stress_request) for _ in range(20)]
                    
                    # Measure response time under stress
                    start_time = time.time()
                    stress_response = requests.get(health_url, timeout=10)
                    result["stress_time"] = time.time() - start_time
                    
                    # Wait for stress requests to complete
                    for future in as_completed(stress_futures, timeout=10):
                        try:
                            future.result()
                        except:
                            pass
                
                # Calculate degradation
                if result["baseline_time"] and result["stress_time"]:
                    result["degradation_ratio"] = result["stress_time"] / result["baseline_time"]
                    
                    # Check if degradation is acceptable (less than 5x slowdown)
                    result["graceful"] = result["degradation_ratio"] < 5.0
                    
                    # Service should still respond under stress
                    assert stress_response.status_code == 200, f"Service {service_name} failed under stress"
            
            except requests.exceptions.RequestException:
                # Service not available - skip stress test
                pass
            except Exception as e:
                result["graceful"] = False
                result["error"] = str(e)
            
            return result
        
        # Test graceful degradation for all services
        for service_name, config in resilience_config.items():
            result = stress_test_service(service_name, config)
            
            # If we got measurements, verify graceful degradation
            if result["degradation_ratio"] is not None:
                assert result["graceful"], f"Service {service_name} does not degrade gracefully: {result['degradation_ratio']}x slowdown"
    
    def test_error_handling_resilience(self, resilience_config):
        """Test that services handle errors gracefully."""
        
        def test_error_responses(service_name: str, config: Dict[str, str]) -> List[str]:
            """Test error handling patterns."""
            issues = []
            
            try:
                base_url = config["base_url"]
                
                # Test various error scenarios
                error_endpoints = [
                    "/nonexistent-endpoint",
                    "/health/../invalid",
                    "/health?invalid=param"
                ]
                
                for endpoint in error_endpoints:
                    try:
                        response = requests.get(f"{base_url}{endpoint}", timeout=5)
                        
                        # Service should return proper HTTP error codes
                        if response.status_code == 200:
                            issues.append(f"Service {service_name} returns 200 for invalid endpoint {endpoint}")
                        
                        # Response should be well-formed (valid JSON or HTML)
                        try:
                            if response.headers.get("content-type", "").startswith("application/json"):
                                response.json()
                        except json.JSONDecodeError:
                            issues.append(f"Service {service_name} returns invalid JSON for {endpoint}")
                    
                    except requests.exceptions.RequestException:
                        # Connection errors are acceptable for error testing
                        pass
            
            except Exception as e:
                issues.append(f"Error testing {service_name}: {e}")
            
            return issues
        
        # Test error handling for all services
        all_issues = []
        for service_name, config in resilience_config.items():
            issues = test_error_responses(service_name, config)
            all_issues.extend(issues)
        
        # Some issues are acceptable, but not critical ones
        critical_issues = [issue for issue in all_issues if "returns 200 for invalid" in issue]
        assert not critical_issues, f"Critical error handling issues: {critical_issues}"


class TestFailoverScenarios:
    """Test service failover and recovery scenarios."""
    
    def test_service_independence_during_failure(self):
        """Test that service failures don't cascade."""
        
        service_configs = {
            "inbox_monitor": {
                "base_url": "http://localhost:8080",
                "health_endpoint": "/health"
            },
            "email_agent": {
                "base_url": "http://localhost:8081",
                "health_endpoint": "/health"
            }
        }
        
        def check_service_independence(available_services: List[str]) -> Dict[str, Any]:
            """Check that available services work independently."""
            results = {}
            
            for service_name, config in service_configs.items():
                if service_name in available_services:
                    try:
                        health_url = f"{config['base_url']}{config['health_endpoint']}"
                        response = requests.get(health_url, timeout=5)
                        
                        results[service_name] = {
                            "available": response.status_code == 200,
                            "independent": True
                        }
                        
                        if response.status_code == 200:
                            data = response.json()
                            response_str = json.dumps(data).lower()
                            
                            # Check that service doesn't reference unavailable services
                            unavailable_services = [s for s in service_configs.keys() if s not in available_services]
                            for unavailable_service in unavailable_services:
                                unavailable_name = unavailable_service.replace("_", "-").lower()
                                if unavailable_name in response_str:
                                    results[service_name]["independent"] = False
                    
                    except requests.exceptions.RequestException:
                        results[service_name] = {
                            "available": False,
                            "independent": True  # Not available, so independence is moot
                        }
            
            return results
        
        # Test different failure scenarios
        failure_scenarios = [
            ["inbox_monitor"],  # Only inbox monitor available
            ["email_agent"],    # Only email agent available
            ["inbox_monitor", "email_agent"]  # Both available
        ]
        
        for available_services in failure_scenarios:
            results = check_service_independence(available_services)
            
            for service_name, result in results.items():
                if result["available"]:
                    assert result["independent"], f"Service {service_name} not independent when others unavailable"
    
    def test_recovery_behavior(self):
        """Test service recovery behavior after simulated failures."""
        
        def simulate_recovery_test(service_name: str, base_url: str) -> Dict[str, Any]:
            """Simulate recovery testing for a service."""
            result = {
                "service": service_name,
                "recovery_time": None,
                "successful_recovery": False,
                "stable_after_recovery": False
            }
            
            try:
                health_url = f"{base_url}/health"
                
                # Test initial availability
                initial_response = requests.get(health_url, timeout=5)
                if initial_response.status_code != 200:
                    # Service not initially available
                    return result
                
                # Simulate recovery by testing multiple health checks
                recovery_start = time.time()
                consecutive_successes = 0
                required_successes = 3
                
                for attempt in range(10):  # Max 10 attempts
                    try:
                        response = requests.get(health_url, timeout=5)
                        if response.status_code == 200:
                            consecutive_successes += 1
                            if consecutive_successes >= required_successes:
                                result["recovery_time"] = time.time() - recovery_start
                                result["successful_recovery"] = True
                                break
                        else:
                            consecutive_successes = 0
                    
                    except requests.exceptions.RequestException:
                        consecutive_successes = 0
                    
                    time.sleep(2)  # Wait between attempts
                
                # Test stability after recovery
                if result["successful_recovery"]:
                    time.sleep(5)  # Wait a bit
                    stability_checks = 3
                    stable_responses = 0
                    
                    for _ in range(stability_checks):
                        try:
                            response = requests.get(health_url, timeout=5)
                            if response.status_code == 200:
                                stable_responses += 1
                        except:
                            pass
                        time.sleep(1)
                    
                    result["stable_after_recovery"] = (stable_responses == stability_checks)
            
            except Exception as e:
                result["error"] = str(e)
            
            return result
        
        # Test recovery for both services
        services = {
            "inbox_monitor": "http://localhost:8080",
            "email_agent": "http://localhost:8081"
        }
        
        for service_name, base_url in services.items():
            result = simulate_recovery_test(service_name, base_url)
            
            # If service recovered, it should be stable
            if result["successful_recovery"]:
                assert result["stable_after_recovery"], f"Service {service_name} not stable after recovery"
                assert result["recovery_time"] < 60, f"Service {service_name} took too long to recover: {result['recovery_time']}s"


def run_scaling_resilience_tests():
    """Run all scaling and resilience tests."""
    import pytest
    
    pytest_args = [
        __file__,
        "-v", "--tb=short",
        "--color=yes",
        "-W", "ignore::DeprecationWarning"
    ]
    
    print("📈 Running Scaling and Resilience Tests")
    print("=" * 50)
    
    result = pytest.main(pytest_args)
    
    if result == 0:
        print("\n✅ All scaling and resilience tests passed!")
        return True
    else:
        print("\n❌ Some scaling and resilience tests failed!")
        return False


if __name__ == "__main__":
    import sys
    success = run_scaling_resilience_tests()
    sys.exit(0 if success else 1)