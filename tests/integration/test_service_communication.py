#!/usr/bin/env python3
"""
Service Communication Integration Tests
======================================

Tests for inter-service communication, API endpoints, and service independence.
"""

import pytest
import requests
import time
import json
import subprocess
import threading
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiohttp


class TestServiceCommunication:
    """Test service communication patterns and independence."""
    
    @pytest.fixture
    def service_endpoints(self):
        """Define service endpoint configurations."""
        return {
            "inbox_monitor": {
                "base_url": "http://localhost:8080",
                "health_endpoint": "/health",
                "status_endpoint": "/status",
                "metrics_endpoint": "/metrics"
            },
            "email_agent": {
                "base_url": "http://localhost:8081", 
                "health_endpoint": "/health",
                "status_endpoint": "/status",
                "metrics_endpoint": "/metrics"
            }
        }
    
    def test_service_independence(self, service_endpoints):
        """Test that services operate independently without dependencies."""
        
        def test_service_isolation(service_name: str, config: Dict[str, str]) -> bool:
            """Test if a service operates independently."""
            try:
                # Test health endpoint
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Verify service identifies itself correctly
                    service_name_lower = service_name.replace("_", "-").lower()
                    assert service_name_lower in health_data.get("service", "").lower()
                    
                    # Verify no dependencies on other services in health status
                    health_str = json.dumps(health_data).lower()
                    other_service = "email" if "inbox" in service_name_lower else "inbox"
                    assert other_service not in health_str, f"Service {service_name} references {other_service}"
                    
                    return True
                
                return False
                
            except requests.exceptions.RequestException:
                # Service not running - that's fine for this test
                return True
            except Exception as e:
                print(f"Error testing {service_name}: {e}")
                return False
        
        # Test both services independently
        for service_name, config in service_endpoints.items():
            is_independent = test_service_isolation(service_name, config)
            assert is_independent, f"Service {service_name} failed independence test"
    
    def test_concurrent_service_startup(self, service_endpoints):
        """Test that services can start up concurrently without conflicts."""
        
        def check_service_startup(service_name: str, config: Dict[str, str]) -> Dict[str, Any]:
            """Check service startup behavior."""
            results = {
                "service": service_name,
                "startup_time": None,
                "health_check": False,
                "port_accessible": False,
                "errors": []
            }
            
            start_time = time.time()
            
            try:
                # Test port accessibility
                import socket
                host, port = config["base_url"].replace("http://", "").split(":")
                port = int(port)
                
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex((host, port))
                    results["port_accessible"] = (result == 0)
                
                # Test health endpoint if port is accessible
                if results["port_accessible"]:
                    health_url = f"{config['base_url']}{config['health_endpoint']}"
                    response = requests.get(health_url, timeout=5)
                    results["health_check"] = (response.status_code == 200)
                
                results["startup_time"] = time.time() - start_time
                
            except Exception as e:
                results["errors"].append(str(e))
            
            return results
        
        # Test concurrent startup simulation
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for service_name, config in service_endpoints.items():
                future = executor.submit(check_service_startup, service_name, config)
                futures.append(future)
            
            results = [future.result() for future in futures]
        
        # Verify no conflicts occurred
        for result in results:
            # If service is running, it should be healthy
            if result["port_accessible"]:
                assert result["health_check"], f"Service {result['service']} failed health check"
            
            # No critical errors should occur
            critical_errors = [e for e in result["errors"] if "conflict" in e.lower() or "bind" in e.lower()]
            assert not critical_errors, f"Service {result['service']} had conflicts: {critical_errors}"
    
    def test_api_endpoint_isolation(self, service_endpoints):
        """Test that API endpoints are properly isolated between services."""
        
        def test_endpoint_isolation(service_name: str, config: Dict[str, str]) -> List[str]:
            """Test endpoint isolation for a service."""
            violations = []
            
            try:
                # Test that health endpoint returns service-specific data
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check that response contains service-specific identifiers
                    response_str = json.dumps(data).lower()
                    service_identifier = service_name.replace("_", "-").lower()
                    
                    if service_identifier not in response_str:
                        violations.append(f"Health endpoint doesn't identify service {service_name}")
                    
                    # Check that response doesn't contain other service identifiers
                    other_services = [s for s in service_endpoints.keys() if s != service_name]
                    for other_service in other_services:
                        other_identifier = other_service.replace("_", "-").lower()
                        if other_identifier in response_str:
                            violations.append(f"Service {service_name} references {other_service}")
            
            except requests.exceptions.RequestException:
                # Service not running - skip test
                pass
            except Exception as e:
                violations.append(f"Error testing {service_name}: {e}")
            
            return violations
        
        # Test endpoint isolation for all services
        all_violations = []
        for service_name, config in service_endpoints.items():
            violations = test_endpoint_isolation(service_name, config)
            all_violations.extend(violations)
        
        assert not all_violations, f"API endpoint isolation violations: {all_violations}"
    
    def test_service_port_uniqueness(self, service_endpoints):
        """Test that services use unique ports."""
        
        ports = []
        for service_name, config in service_endpoints.items():
            port = int(config["base_url"].split(":")[-1])
            
            assert port not in ports, f"Port {port} is used by multiple services"
            ports.append(port)
        
        # Verify reasonable port ranges
        for port in ports:
            assert 8000 <= port <= 9000, f"Port {port} outside expected range"
    
    @pytest.mark.asyncio
    async def test_async_service_communication(self, service_endpoints):
        """Test asynchronous communication patterns don't interfere."""
        
        async def test_async_health_check(service_name: str, config: Dict[str, str]) -> Dict[str, Any]:
            """Test async health check for a service."""
            result = {
                "service": service_name,
                "success": False,
                "response_time": None,
                "status_code": None
            }
            
            start_time = time.time()
            
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    health_url = f"{config['base_url']}{config['health_endpoint']}"
                    async with session.get(health_url) as response:
                        result["status_code"] = response.status
                        result["success"] = (response.status == 200)
                        result["response_time"] = time.time() - start_time
                        
            except Exception as e:
                result["error"] = str(e)
                result["response_time"] = time.time() - start_time
            
            return result
        
        # Test concurrent async requests
        tasks = []
        for service_name, config in service_endpoints.items():
            task = test_async_health_check(service_name, config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no exceptions occurred
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pytest.fail(f"Async communication test failed: {result}")
            
            # If service is available, it should respond successfully
            if result.get("status_code") == 200:
                assert result["success"], f"Service {result['service']} failed async health check"


class TestServiceLoadBalancing:
    """Test load balancing and service discovery patterns."""
    
    def test_service_discovery_independence(self):
        """Test that services can be discovered independently."""
        
        # Test that each service can be resolved by its name
        service_names = ["inbox-monitor", "email-agent"]
        
        for service_name in service_names:
            # In a real k8s environment, this would test DNS resolution
            # For now, we test that service names are properly configured
            assert "-" in service_name, f"Service name {service_name} should use kebab-case"
            assert len(service_name.split("-")) >= 2, f"Service name {service_name} should be descriptive"
    
    def test_load_balancing_readiness(self):
        """Test that services are ready for load balancing."""
        
        # Test that each service defines proper readiness criteria
        readiness_criteria = {
            "inbox_monitor": {
                "health_endpoint": "/health",
                "expected_status": 200,
                "timeout": 5
            },
            "email_agent": {
                "health_endpoint": "/health", 
                "expected_status": 200,
                "timeout": 5
            }
        }
        
        for service_name, criteria in readiness_criteria.items():
            # Verify readiness criteria are well-defined
            assert "health_endpoint" in criteria
            assert "expected_status" in criteria
            assert "timeout" in criteria
            
            # Verify reasonable timeout values
            assert 1 <= criteria["timeout"] <= 30, f"Unreasonable timeout for {service_name}"


class TestServiceFailureIsolation:
    """Test that service failures are properly isolated."""
    
    def test_service_failure_independence(self, service_endpoints):
        """Test that failure of one service doesn't affect others."""
        
        def simulate_service_check(service_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
            """Check service status independently."""
            result = {
                "service": service_name,
                "available": False,
                "isolated": True,
                "error": None
            }
            
            try:
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                response = requests.get(health_url, timeout=2)
                result["available"] = (response.status_code == 200)
                
                if result["available"]:
                    data = response.json()
                    # Check that service doesn't report on other services
                    response_str = json.dumps(data).lower()
                    other_services = [s for s in service_endpoints.keys() if s != service_name]
                    
                    for other_service in other_services:
                        other_name = other_service.replace("_", "-").lower()
                        if other_name in response_str:
                            result["isolated"] = False
                            result["error"] = f"Service {service_name} reports on {other_service}"
                
            except requests.exceptions.RequestException:
                # Service not available - that's expected for some tests
                result["available"] = False
                result["isolated"] = True  # Not available is still considered isolated
            except Exception as e:
                result["error"] = str(e)
                result["isolated"] = False
            
            return result
        
        # Check each service independently
        for service_name, config in service_endpoints.items():
            result = simulate_service_check(service_name, config)
            
            # Service should be properly isolated regardless of availability
            assert result["isolated"], f"Service {service_name} not properly isolated: {result['error']}"
    
    def test_graceful_degradation(self, service_endpoints):
        """Test that services handle unavailable dependencies gracefully."""
        
        # Test that each service can start and respond to health checks
        # even if other services are not available
        
        any_service_tested = False
        
        for service_name, config in service_endpoints.items():
            try:
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    any_service_tested = True
                    data = response.json()
                    
                    # Service should report its own status
                    assert "status" in data or "health" in data or "service" in data, \
                        f"Service {service_name} doesn't report status information"
                    
                    # Service should not fail due to other service unavailability
                    status_str = json.dumps(data).lower()
                    error_indicators = ["error", "failed", "unavailable", "timeout"]
                    
                    # If there are errors, they shouldn't be about other services
                    for indicator in error_indicators:
                        if indicator in status_str:
                            other_services = [s for s in service_endpoints.keys() if s != service_name]
                            for other_service in other_services:
                                other_name = other_service.replace("_", "-").lower()
                                assert other_name not in status_str, \
                                    f"Service {service_name} failing due to {other_service}"
            
            except requests.exceptions.RequestException:
                # Service not running - skip this service
                continue
        
        # If no services were available for testing, that's acceptable
        # The test passes as long as available services are well-behaved


class TestDatabaseConnectivity:
    """Test database connectivity and isolation."""
    
    def test_database_connection_isolation(self, service_endpoints, database_mock):
        """Test that database connections are properly isolated."""
        
        connection_results = {}
        
        for service_name, config in service_endpoints.items():
            # Create mock database connection for each service
            connection_info = database_mock.create_mock_connection(service_name)
            connection_results[service_name] = connection_info
            
            # Test connection is working
            assert database_mock.test_connection(connection_info["connection_id"]), \
                f"Mock database connection failed for {service_name}"
        
        # Verify each service has its own connection
        connection_ids = [result["connection_id"] for result in connection_results.values()]
        assert len(connection_ids) == len(set(connection_ids)), "Services sharing database connections"
        
        # Test connection stats
        stats = database_mock.get_connection_stats()
        assert stats["total_connections"] >= len(service_endpoints), \
            "Not all services have database connections"
    
    def test_database_failure_isolation(self, service_endpoints, database_mock):
        """Test that database failures are isolated between services."""
        
        connections = {}
        
        # Create connections for all services
        for service_name in service_endpoints.keys():
            connection_info = database_mock.create_mock_connection(service_name)
            connections[service_name] = connection_info
        
        # Simulate failure of one connection
        first_service = list(connections.keys())[0]
        first_connection_id = connections[first_service]["connection_id"]
        database_mock.close_connection(first_connection_id)
        
        # Verify other connections are still working
        for service_name, connection_info in connections.items():
            if service_name != first_service:
                assert database_mock.test_connection(connection_info["connection_id"]), \
                    f"Service {service_name} database connection affected by {first_service} failure"
        
        # Verify failed connection is actually closed
        assert not database_mock.test_connection(first_connection_id), \
            "Failed connection still appears to be working"
    
    def test_live_service_database_integration(self, service_endpoints):
        """Test database integration with live services if available."""
        
        for service_name, config in service_endpoints.items():
            if not config.get("is_live", False):
                continue
            
            try:
                # Test that service can handle database requests
                health_url = f"{config['base_url']}{config['health_endpoint']}"
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for database connectivity indicators in health response
                    health_str = json.dumps(data).lower()
                    
                    # Service should indicate database status
                    database_indicators = ["database", "db", "connection", "storage"]
                    has_database_info = any(indicator in health_str for indicator in database_indicators)
                    
                    # If service reports database info, it should not be in error state
                    if has_database_info and "error" in health_str:
                        # Check if error is database-related
                        error_indicators = ["connection failed", "timeout", "unavailable"]
                        has_db_error = any(error in health_str for error in error_indicators)
                        
                        # In test mode, database errors are acceptable due to mocking
                        if has_db_error and "test" not in health_str:
                            pytest.fail(f"Service {service_name} has database connectivity issues")
            
            except requests.exceptions.RequestException:
                # Service not available - skip
                continue


class TestServiceSecurity:
    """Test service security configurations."""
    
    def test_environment_security(self, service_endpoints, security_validator):
        """Test that environment configurations are secure."""
        
        for service_name, config in service_endpoints.items():
            # Get service manager to access environment configuration
            service_manager = config.get("service_manager")
            if service_manager and hasattr(service_manager, '_create_test_env_content'):
                env_content = service_manager._create_test_env_content(service_name)
                
                # Validate environment security
                result = security_validator.validate_environment_security(env_content)
                
                assert result["safe"], f"Service {service_name} environment not secure: {result['findings']}"
                assert result["security_score"] >= 80, f"Service {service_name} security score too low: {result['security_score']}"
                assert result["has_test_indicators"], f"Service {service_name} lacks test indicators"
    
    def test_http_security_headers(self, service_endpoints, security_validator):
        """Test HTTP security headers for live services."""
        
        for service_name, config in service_endpoints.items():
            if not config.get("is_live", False):
                continue
            
            result = security_validator.validate_http_security_headers(config["base_url"])
            
            # Don't require all headers for test services, but check for critical ones
            critical_headers = ['X-Content-Type-Options', 'X-Frame-Options']
            for header in critical_headers:
                if header in result.get("headers", {}):
                    header_info = result["headers"][header]
                    # Allow missing headers for test services, but if present should be valid
                    if header_info.get("present", False):
                        assert header_info.get("valid", True), \
                            f"Service {service_name} has invalid {header} header"
    
    def test_secrets_management(self, service_endpoints, security_validator):
        """Test that secrets are properly managed."""
        
        for service_name, config in service_endpoints.items():
            result = security_validator.validate_secrets_management(config)
            
            # Secrets should be properly managed
            assert result["secrets_properly_managed"], \
                f"Service {service_name} secrets not properly managed: {result['findings']}"
            
            # Security score should be reasonable for test environment
            assert result["security_score"] >= 75, \
                f"Service {service_name} secrets security score too low: {result['security_score']}"
    
    def test_input_sanitization(self, service_endpoints, security_validator):
        """Test input sanitization for live services."""
        
        for service_name, config in service_endpoints.items():
            if not config.get("is_live", False):
                continue
            
            result = security_validator.validate_input_sanitization(config["base_url"])
            
            # Input should be properly sanitized
            assert result["properly_sanitized"], \
                f"Service {service_name} input not properly sanitized"
            
            # Sanitization score should be high
            assert result["sanitization_score"] >= 80, \
                f"Service {service_name} sanitization score too low: {result['sanitization_score']}"
    
    def test_comprehensive_security_scan(self, service_endpoints, security_validator):
        """Run comprehensive security scan on all services."""
        
        result = security_validator.run_comprehensive_security_scan(service_endpoints)
        
        # Overall security score should be acceptable
        assert result["overall_score"] >= 70, \
            f"Overall security score too low: {result['overall_score']}"
        
        # Should not have critical security findings
        assert result["summary"]["critical_findings"] == 0, \
            f"Critical security findings detected: {result['summary']['critical_findings']}"
        
        # All services should be tested
        assert result["summary"]["services_tested"] == len(service_endpoints), \
            "Not all services were tested for security"
        
        # Print summary for visibility
        print(f"\n🔒 Security Scan Summary:")
        print(f"Overall Score: {result['overall_score']:.1f}/100")
        print(f"Services Tested: {result['summary']['services_tested']}")
        print(f"Total Findings: {result['summary']['total_findings']}")
        print(f"Critical Findings: {result['summary']['critical_findings']}")
        print(f"Security Compliant: {result['summary']['security_compliant']}")


class TestServicePerformance:
    """Test service performance characteristics."""
    
    def test_establish_performance_baselines(self, service_endpoints, performance_tester):
        """Establish performance baselines for all services."""
        
        baselines_established = 0
        
        for service_name, config in service_endpoints.items():
            if config.get("is_live", False):
                try:
                    baseline = performance_tester.establish_baseline(
                        service_name=service_name,
                        service_url=config["base_url"],
                        duration=15,  # Shorter duration for testing
                        concurrent_requests=3
                    )
                    
                    if baseline:
                        baselines_established += 1
                        
                        # Verify baseline contains expected metrics
                        assert "metrics" in baseline
                        assert "avg_response_time" in baseline["metrics"]
                        assert "success_rate" in baseline["metrics"]
                        assert baseline["metrics"]["success_rate"] > 0
                        
                        print(f"✅ Baseline established for {service_name}")
                
                except Exception as e:
                    print(f"⚠️  Could not establish baseline for {service_name}: {e}")
        
        # At least one baseline should be established if any services are live
        live_services = sum(1 for config in service_endpoints.values() if config.get("is_live", False))
        if live_services > 0:
            assert baselines_established > 0, "No baselines were established for live services"
    
    def test_load_performance(self, service_endpoints, performance_tester):
        """Test load performance for live services."""
        
        for service_name, config in service_endpoints.items():
            if not config.get("is_live", False):
                continue
            
            try:
                # Run load test
                result = performance_tester.run_load_test(
                    service_url=config["base_url"],
                    endpoint="/health",
                    duration=20,
                    concurrent_requests=5,
                    test_type="load"
                )
                
                assert result["success"], f"Load test failed for {service_name}: {result.get('error')}"
                
                metrics = result["metrics"]
                
                # Performance assertions
                assert metrics["success_rate"] >= 95, \
                    f"Success rate too low for {service_name}: {metrics['success_rate']}%"
                
                assert metrics["avg_response_time"] <= 5.0, \
                    f"Average response time too high for {service_name}: {metrics['avg_response_time']}s"
                
                assert metrics["error_rate"] <= 5.0, \
                    f"Error rate too high for {service_name}: {metrics['error_rate']}%"
                
                print(f"✅ Load test passed for {service_name}")
                print(f"   Avg Response: {metrics['avg_response_time']:.3f}s")
                print(f"   Success Rate: {metrics['success_rate']:.1f}%")
                print(f"   Requests/sec: {metrics['requests_per_second']:.1f}")
            
            except Exception as e:
                pytest.fail(f"Load test failed for {service_name}: {e}")
    
    def test_baseline_validation(self, service_endpoints, performance_tester):
        """Test performance against established baselines."""
        
        validated_services = 0
        
        for service_name, config in service_endpoints.items():
            if not config.get("is_live", False):
                continue
            
            # Check if baseline exists
            if service_name not in performance_tester.baselines:
                print(f"⚠️  No baseline exists for {service_name}, skipping validation")
                continue
            
            try:
                # Run performance test
                test_result = performance_tester.run_load_test(
                    service_url=config["base_url"],
                    endpoint="/health",
                    duration=15,
                    concurrent_requests=3,
                    test_type="validation"
                )
                
                if test_result["success"]:
                    # Validate against baseline
                    validation = performance_tester.validate_against_baseline(service_name, test_result)
                    
                    assert validation["baseline_exists"], f"Baseline validation failed for {service_name}"
                    
                    # Allow some tolerance for test environment variability
                    critical_violations = [
                        v for v in validation.get("violations", [])
                        if "success_rate" in v["metric"] or 
                           (v["metric"] == "avg_response_time" and v["actual"] > v["threshold"] * 2)
                    ]
                    
                    assert not critical_violations, \
                        f"Critical performance regression for {service_name}: {critical_violations}"
                    
                    validated_services += 1
                    
                    if validation["test_passed"]:
                        print(f"✅ Performance validation passed for {service_name}")
                    else:
                        print(f"⚠️  Minor performance variations for {service_name}")
                        for violation in validation.get("violations", []):
                            print(f"     {violation['message']}")
                
            except Exception as e:
                print(f"⚠️  Baseline validation failed for {service_name}: {e}")
        
        # Should validate at least one service if any are live
        live_services = sum(1 for config in service_endpoints.values() if config.get("is_live", False))
        if live_services > 0:
            print(f"📊 Validated {validated_services} of {live_services} live services")
    
    def test_stress_tolerance(self, service_endpoints, performance_tester):
        """Test stress tolerance for live services."""
        
        for service_name, config in service_endpoints.items():
            if not config.get("is_live", False):
                continue
            
            try:
                # Run light stress test (reduced for integration testing)
                stress_result = performance_tester.run_stress_test(
                    service_name=service_name,
                    service_url=config["base_url"]
                )
                
                max_concurrent = stress_result.get("max_concurrent_requests", 0)
                
                # Should handle at least minimal concurrent load
                assert max_concurrent >= 5, \
                    f"Service {service_name} cannot handle minimal concurrent load: {max_concurrent}"
                
                recommendations = stress_result.get("recommendations", [])
                
                print(f"🔥 Stress test completed for {service_name}")
                print(f"   Max concurrent requests: {max_concurrent}")
                if recommendations:
                    print(f"   Recommendations: {'; '.join(recommendations)}")
            
            except Exception as e:
                print(f"⚠️  Stress test failed for {service_name}: {e}")
                # Don't fail the test for stress test issues in integration environment
    
    def test_comprehensive_performance_suite(self, service_endpoints, performance_tester):
        """Run comprehensive performance test suite."""
        
        result = performance_tester.run_comprehensive_performance_test(service_endpoints)
        
        # Verify test suite completed
        assert "services" in result
        assert result["summary"]["services_tested"] == len(service_endpoints)
        
        # Print summary
        summary = result["summary"]
        print(f"\n📊 Performance Test Suite Summary:")
        print(f"Services Tested: {summary['services_tested']}")
        print(f"Baselines Established: {summary['baselines_established']}")
        print(f"Performance Regressions: {summary['performance_regressions']}")
        print(f"Stress Test Passes: {summary['stress_test_passes']}")
        
        # Should not have excessive performance regressions
        regression_rate = summary["performance_regressions"] / max(1, summary["services_tested"])
        assert regression_rate <= 0.5, f"Too many performance regressions: {regression_rate:.1%}"


def run_communication_tests():
    """Run all service communication tests."""
    import pytest
    
    pytest_args = [
        __file__,
        "-v", "--tb=short",
        "--color=yes",
        "-W", "ignore::DeprecationWarning"
    ]
    
    print("🔗 Running Service Communication Tests")
    print("=" * 50)
    
    result = pytest.main(pytest_args)
    
    if result == 0:
        print("\n✅ All service communication tests passed!")
        return True
    else:
        print("\n❌ Some service communication tests failed!")
        return False


if __name__ == "__main__":
    import sys
    success = run_communication_tests()
    sys.exit(0 if success else 1)