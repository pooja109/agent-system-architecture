"""
Integration Testing Architecture for robust patterns for external service integration.

This framework provides comprehensive integration testing solutions for external service
interactions, service integration redesign patterns, and architectural solutions for
integration test challenges.
"""
import pytest
import asyncio
import time
import json
import uuid
from typing import Dict, List, Optional, Any, Callable, Union, Type
from dataclasses import dataclass, field
from contextlib import asynccontextmanager, contextmanager
from unittest import mock
from abc import ABC, abstractmethod
import threading
from collections import defaultdict
import logging


@dataclass
class IntegrationConfig:
    """Configuration for integration testing scenarios."""
    service_name: str
    timeout: float
    retry_attempts: int
    retry_delay: float
    circuit_breaker_threshold: int
    mock_mode: bool = False
    rate_limit_per_second: Optional[float] = None
    authentication_required: bool = True
    connection_pool_size: int = 5


@dataclass
class ServiceEndpoint:
    """Represents an external service endpoint for testing."""
    name: str
    url: str
    method: str
    expected_response_time: float
    expected_status_codes: List[int]
    authentication_type: str  # 'oauth', 'api_key', 'bearer', 'none'
    rate_limits: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class IntegrationTestResult:
    """Result of an integration test execution."""
    test_name: str
    service_name: str
    endpoint_name: str
    success: bool
    execution_time: float
    response_data: Optional[Any] = None
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class ServiceMockManager:
    """Manages sophisticated mocks for external services."""
    
    def __init__(self):
        self.mock_services: Dict[str, mock.AsyncMock] = {}
        self.mock_behaviors: Dict[str, Dict[str, Any]] = {}
        self.call_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.failure_scenarios: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    def create_service_mock(self, service_name: str, config: IntegrationConfig) -> mock.AsyncMock:
        """Create a sophisticated mock for an external service."""
        service_mock = mock.AsyncMock()
        
        # Configure mock behavior based on service type
        if service_name == 'azure_ai_foundry':
            service_mock.get_completion = mock.AsyncMock(
                side_effect=self._azure_completion_mock
            )
            service_mock.authenticate = mock.AsyncMock(return_value=True)
            service_mock.close = mock.AsyncMock()
            
        elif service_name == 'microsoft_graph':
            service_mock.get_inbox_messages = mock.AsyncMock(
                side_effect=self._graph_messages_mock
            )
            service_mock.authenticate = mock.AsyncMock(return_value=True)
            service_mock.close = mock.AsyncMock()
            
        elif service_name == 'salesforce':
            service_mock.create_case = mock.AsyncMock(
                side_effect=self._salesforce_case_mock
            )
            service_mock.authenticate = mock.AsyncMock(return_value=True)
            service_mock.close = mock.AsyncMock()
        
        # Add common mock patterns
        service_mock.connect = mock.AsyncMock(return_value=True)
        service_mock.disconnect = mock.AsyncMock(return_value=True)
        service_mock.health_check = mock.AsyncMock(return_value={'status': 'healthy'})
        
        # Configure mock behavior tracking
        service_mock.side_effect = self._track_service_calls(service_name)
        
        self.mock_services[service_name] = service_mock
        return service_mock
    
    def set_mock_behavior(self, service_name: str, behavior_config: Dict[str, Any]):
        """Set specific behavior for a mocked service."""
        self.mock_behaviors[service_name] = behavior_config
    
    def add_failure_scenario(self, service_name: str, failure_config: Dict[str, Any]):
        """Add a failure scenario for testing error handling."""
        self.failure_scenarios[service_name].append(failure_config)
    
    def _track_service_calls(self, service_name: str):
        """Track calls made to service mocks."""
        def tracker(*args, **kwargs):
            call_record = {
                'timestamp': time.time(),
                'args': args,
                'kwargs': kwargs,
                'thread_id': threading.current_thread().ident
            }
            self.call_history[service_name].append(call_record)
            return None  # Let mock handle the actual response
        return tracker
    
    async def _azure_completion_mock(self, prompt: str, **kwargs):
        """Mock Azure AI Foundry completion response."""
        service_name = 'azure_ai_foundry'
        
        # Check for configured behaviors
        if service_name in self.mock_behaviors:
            behavior = self.mock_behaviors[service_name]
            if behavior.get('simulate_delay'):
                await asyncio.sleep(behavior['simulate_delay'])
            if behavior.get('raise_exception'):
                raise Exception(behavior['raise_exception'])
        
        # Check for failure scenarios
        for failure in self.failure_scenarios.get(service_name, []):
            if failure.get('condition', lambda: True)():
                if failure.get('exception'):
                    raise Exception(failure['exception'])
                if failure.get('timeout'):
                    await asyncio.sleep(failure['timeout'])
                    raise asyncio.TimeoutError("Simulated timeout")
        
        # Return mock completion
        return f"Mock completion for: {prompt[:50]}..."
    
    async def _graph_messages_mock(self, **kwargs):
        """Mock Microsoft Graph messages response."""
        service_name = 'microsoft_graph'
        
        # Apply behaviors and failures similar to Azure mock
        if service_name in self.mock_behaviors:
            behavior = self.mock_behaviors[service_name]
            if behavior.get('simulate_delay'):
                await asyncio.sleep(behavior['simulate_delay'])
        
        # Return mock messages
        return [
            {
                'id': f'msg_{uuid.uuid4().hex[:8]}',
                'subject': 'Mock Email Subject',
                'from': {'emailAddress': {'address': 'test@example.com'}},
                'receivedDateTime': '2025-01-09T00:00:00Z',
                'body': {'content': 'Mock email content'}
            }
        ]
    
    async def _salesforce_case_mock(self, case_data: Dict[str, Any]):
        """Mock Salesforce case creation response."""
        service_name = 'salesforce'
        
        # Apply behaviors and failures
        if service_name in self.mock_behaviors:
            behavior = self.mock_behaviors[service_name]
            if behavior.get('simulate_delay'):
                await asyncio.sleep(behavior['simulate_delay'])
        
        # Return mock case ID
        return {'id': f'case_{uuid.uuid4().hex[:8]}', 'success': True}


class IntegrationTestFramework:
    """
    Comprehensive framework for integration testing with external services.
    
    This framework provides:
    - Robust external service integration patterns
    - Service interaction redesign patterns  
    - Integration test architectural solutions
    - Sophisticated mock orchestration for integration scenarios
    - Performance monitoring for integration points
    """
    
    def __init__(self):
        self.service_configs: Dict[str, IntegrationConfig] = {}
        self.service_endpoints: Dict[str, List[ServiceEndpoint]] = {}
        self.mock_manager = ServiceMockManager()
        self.integration_results: List[IntegrationTestResult] = []
        self.service_health_cache: Dict[str, Dict[str, Any]] = {}
        self.circuit_breakers: Dict[str, int] = {}  # Failure counts
        self.rate_limiters: Dict[str, List[float]] = defaultdict(list)  # Timestamps
        
        # Default service configurations
        self._setup_default_configurations()
    
    def _setup_default_configurations(self):
        """Set up default configurations for common services."""
        self.service_configs.update({
            'azure_ai_foundry': IntegrationConfig(
                service_name='azure_ai_foundry',
                timeout=30.0,
                retry_attempts=2,
                retry_delay=1.0,
                circuit_breaker_threshold=5,
                mock_mode=True,  # Default to mock for testing
                rate_limit_per_second=10.0,
                authentication_required=True
            ),
            'microsoft_graph': IntegrationConfig(
                service_name='microsoft_graph',
                timeout=20.0,
                retry_attempts=3,
                retry_delay=2.0,
                circuit_breaker_threshold=3,
                mock_mode=True,
                rate_limit_per_second=5.0,
                authentication_required=True
            ),
            'salesforce': IntegrationConfig(
                service_name='salesforce',
                timeout=15.0,
                retry_attempts=2,
                retry_delay=1.5,
                circuit_breaker_threshold=4,
                mock_mode=True,
                rate_limit_per_second=20.0,
                authentication_required=True
            )
        })
        
        # Set up service endpoints
        self.service_endpoints.update({
            'azure_ai_foundry': [
                ServiceEndpoint(
                    name='get_completion',
                    url='/completions',
                    method='POST',
                    expected_response_time=2.0,
                    expected_status_codes=[200, 201],
                    authentication_type='oauth',
                    dependencies=['authentication']
                )
            ],
            'microsoft_graph': [
                ServiceEndpoint(
                    name='get_messages',
                    url='/me/messages',
                    method='GET',
                    expected_response_time=1.5,
                    expected_status_codes=[200],
                    authentication_type='oauth',
                    dependencies=['authentication']
                )
            ],
            'salesforce': [
                ServiceEndpoint(
                    name='create_case',
                    url='/services/data/v55.0/sobjects/Case',
                    method='POST',
                    expected_response_time=1.0,
                    expected_status_codes=[201],
                    authentication_type='oauth',
                    dependencies=['authentication']
                )
            ]
        })
    
    def register_service_config(self, service_name: str, config: IntegrationConfig):
        """Register configuration for a service."""
        self.service_configs[service_name] = config
    
    def register_service_endpoint(self, service_name: str, endpoint: ServiceEndpoint):
        """Register an endpoint for a service."""
        if service_name not in self.service_endpoints:
            self.service_endpoints[service_name] = []
        self.service_endpoints[service_name].append(endpoint)
    
    def configure_mock_behavior(self, service_name: str, behavior_config: Dict[str, Any]):
        """Configure mock behavior for a service."""
        self.mock_manager.set_mock_behavior(service_name, behavior_config)
    
    def add_failure_scenario(self, service_name: str, failure_config: Dict[str, Any]):
        """Add failure scenario for testing error handling."""
        self.mock_manager.add_failure_scenario(service_name, failure_config)
    
    @asynccontextmanager
    async def integration_test_context(self, service_names: List[str], 
                                     test_mode: str = 'mock'):
        """
        Context manager for integration test execution.
        
        Args:
            service_names: List of services to set up for testing
            test_mode: 'mock', 'live', or 'hybrid'
        """
        service_clients = {}
        
        try:
            # Set up service clients
            for service_name in service_names:
                if service_name not in self.service_configs:
                    raise ValueError(f"Service '{service_name}' not configured")
                
                config = self.service_configs[service_name]
                
                if test_mode == 'mock' or config.mock_mode:
                    # Create mock client
                    client = self.mock_manager.create_service_mock(service_name, config)
                else:
                    # Create real client (would need actual implementation)
                    client = await self._create_real_service_client(service_name, config)
                
                service_clients[service_name] = client
            
            # Yield context with clients
            yield {
                'clients': service_clients,
                'framework': self,
                'mock_manager': self.mock_manager
            }
            
        finally:
            # Cleanup service clients
            for service_name, client in service_clients.items():
                try:
                    if hasattr(client, 'close'):
                        if asyncio.iscoroutinefunction(client.close):
                            await client.close()
                        else:
                            client.close()
                except Exception:
                    pass  # Best effort cleanup
    
    async def _create_real_service_client(self, service_name: str, config: IntegrationConfig):
        """Create real service client (placeholder - would need actual implementation)."""
        # This would create actual service clients for live testing
        # For now, return a mock to avoid actual service calls
        return self.mock_manager.create_service_mock(service_name, config)
    
    async def execute_integration_test(self, service_name: str, endpoint_name: str, 
                                     test_data: Dict[str, Any] = None) -> IntegrationTestResult:
        """Execute an integration test for a specific service endpoint."""
        if service_name not in self.service_configs:
            raise ValueError(f"Service '{service_name}' not configured")
        
        config = self.service_configs[service_name]
        endpoints = self.service_endpoints.get(service_name, [])
        endpoint = next((ep for ep in endpoints if ep.name == endpoint_name), None)
        
        if not endpoint:
            raise ValueError(f"Endpoint '{endpoint_name}' not found for service '{service_name}'")
        
        # Check circuit breaker
        if self.circuit_breakers.get(service_name, 0) >= config.circuit_breaker_threshold:
            return IntegrationTestResult(
                test_name=f"{service_name}.{endpoint_name}",
                service_name=service_name,
                endpoint_name=endpoint_name,
                success=False,
                execution_time=0.0,
                error_message="Circuit breaker open"
            )
        
        # Check rate limiting
        if not self._check_rate_limit(service_name, config):
            return IntegrationTestResult(
                test_name=f"{service_name}.{endpoint_name}",
                service_name=service_name,
                endpoint_name=endpoint_name,
                success=False,
                execution_time=0.0,
                error_message="Rate limit exceeded"
            )
        
        start_time = time.perf_counter()
        
        try:
            # Execute the integration test
            async with self.integration_test_context([service_name]) as context:
                client = context['clients'][service_name]
                
                # Execute endpoint call based on endpoint configuration
                if endpoint_name == 'get_completion':
                    result = await client.get_completion(
                        test_data.get('prompt', 'Test prompt') if test_data else 'Test prompt'
                    )
                elif endpoint_name == 'get_messages':
                    result = await client.get_inbox_messages()
                elif endpoint_name == 'create_case':
                    result = await client.create_case(
                        test_data if test_data else {'subject': 'Test Case'}
                    )
                else:
                    # Generic endpoint call
                    method = getattr(client, endpoint_name, None)
                    if method:
                        if test_data:
                            result = await method(**test_data)
                        else:
                            result = await method()
                    else:
                        raise AttributeError(f"Method '{endpoint_name}' not found on client")
            
            execution_time = time.perf_counter() - start_time
            
            # Validate response time
            if execution_time > endpoint.expected_response_time:
                logging.warning(
                    f"Slow response from {service_name}.{endpoint_name}: "
                    f"{execution_time:.3f}s > {endpoint.expected_response_time}s"
                )
            
            # Reset circuit breaker on success
            self.circuit_breakers[service_name] = 0
            
            test_result = IntegrationTestResult(
                test_name=f"{service_name}.{endpoint_name}",
                service_name=service_name,
                endpoint_name=endpoint_name,
                success=True,
                execution_time=execution_time,
                response_data=result,
                metrics={
                    'expected_response_time': endpoint.expected_response_time,
                    'actual_response_time': execution_time,
                    'performance_ratio': execution_time / endpoint.expected_response_time
                }
            )
            
        except Exception as e:
            execution_time = time.perf_counter() - start_time
            
            # Increment circuit breaker
            self.circuit_breakers[service_name] = self.circuit_breakers.get(service_name, 0) + 1
            
            test_result = IntegrationTestResult(
                test_name=f"{service_name}.{endpoint_name}",
                service_name=service_name,
                endpoint_name=endpoint_name,
                success=False,
                execution_time=execution_time,
                error_message=str(e),
                metrics={
                    'expected_response_time': endpoint.expected_response_time,
                    'actual_response_time': execution_time,
                    'error_type': type(e).__name__
                }
            )
        
        self.integration_results.append(test_result)
        return test_result
    
    def _check_rate_limit(self, service_name: str, config: IntegrationConfig) -> bool:
        """Check if rate limit allows the request."""
        if not config.rate_limit_per_second:
            return True
        
        current_time = time.time()
        service_calls = self.rate_limiters[service_name]
        
        # Remove calls older than 1 second
        service_calls[:] = [call_time for call_time in service_calls if current_time - call_time < 1.0]
        
        # Check if under rate limit
        if len(service_calls) >= config.rate_limit_per_second:
            return False
        
        # Record this call
        service_calls.append(current_time)
        return True
    
    async def run_integration_test_suite(self, service_names: List[str] = None) -> List[IntegrationTestResult]:
        """Run comprehensive integration test suite."""
        if not service_names:
            service_names = list(self.service_configs.keys())
        
        results = []
        
        for service_name in service_names:
            endpoints = self.service_endpoints.get(service_name, [])
            
            for endpoint in endpoints:
                result = await self.execute_integration_test(service_name, endpoint.name)
                results.append(result)
        
        return results
    
    def generate_integration_report(self) -> str:
        """Generate comprehensive integration test report."""
        if not self.integration_results:
            return "No integration tests executed."
        
        report = ["Integration Test Report", "=" * 50, ""]
        
        # Summary statistics
        total_tests = len(self.integration_results)
        successful_tests = sum(1 for r in self.integration_results if r.success)
        failed_tests = total_tests - successful_tests
        
        report.extend([
            f"Total Tests: {total_tests}",
            f"Successful: {successful_tests}",
            f"Failed: {failed_tests}",
            f"Success Rate: {(successful_tests/total_tests)*100:.1f}%",
            ""
        ])
        
        # Service breakdown
        service_stats = defaultdict(lambda: {'total': 0, 'success': 0})
        for result in self.integration_results:
            service_stats[result.service_name]['total'] += 1
            if result.success:
                service_stats[result.service_name]['success'] += 1
        
        report.append("Service Breakdown:")
        for service, stats in service_stats.items():
            success_rate = (stats['success'] / stats['total']) * 100
            report.append(f"  {service}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        
        report.append("")
        
        # Performance statistics
        successful_results = [r for r in self.integration_results if r.success]
        if successful_results:
            avg_response_time = sum(r.execution_time for r in successful_results) / len(successful_results)
            max_response_time = max(r.execution_time for r in successful_results)
            min_response_time = min(r.execution_time for r in successful_results)
            
            report.extend([
                "Performance Statistics:",
                f"  Average Response Time: {avg_response_time:.3f}s",
                f"  Max Response Time: {max_response_time:.3f}s",
                f"  Min Response Time: {min_response_time:.3f}s",
                ""
            ])
        
        # Failed tests details
        failed_results = [r for r in self.integration_results if not r.success]
        if failed_results:
            report.append("Failed Tests:")
            for result in failed_results:
                report.append(f"  {result.test_name}: {result.error_message}")
            report.append("")
        
        return "\n".join(report)


# Integration fixtures for use in tests
@pytest.fixture(scope="session")
def integration_framework():
    """Provide integration testing framework for session."""
    return IntegrationTestFramework()


@pytest.fixture(scope="function")
async def azure_integration_client(integration_framework):
    """Provide Azure AI Foundry integration client."""
    async with integration_framework.integration_test_context(['azure_ai_foundry']) as context:
        yield context['clients']['azure_ai_foundry']


@pytest.fixture(scope="function") 
async def graph_integration_client(integration_framework):
    """Provide Microsoft Graph integration client."""
    async with integration_framework.integration_test_context(['microsoft_graph']) as context:
        yield context['clients']['microsoft_graph']


@pytest.fixture(scope="function")
async def salesforce_integration_client(integration_framework):
    """Provide Salesforce integration client."""
    async with integration_framework.integration_test_context(['salesforce']) as context:
        yield context['clients']['salesforce']


@pytest.fixture(scope="function")
async def multi_service_integration(integration_framework):
    """Provide multi-service integration context."""
    async with integration_framework.integration_test_context([
        'azure_ai_foundry', 'microsoft_graph', 'salesforce'
    ]) as context:
        yield context


# Utility decorators and context managers
def integration_test_pattern(service_name: str, endpoint_name: str, 
                           failure_scenarios: List[Dict[str, Any]] = None):
    """Decorator for integration test patterns."""
    def decorator(test_func):
        async def wrapper(*args, **kwargs):
            # Set up integration context
            framework = IntegrationTestFramework()
            
            # Add failure scenarios if specified
            if failure_scenarios:
                for scenario in failure_scenarios:
                    framework.add_failure_scenario(service_name, scenario)
            
            # Execute test with integration context
            async with framework.integration_test_context([service_name]) as context:
                return await test_func(context, *args, **kwargs)
        
        wrapper._integration_test = True
        wrapper._service_name = service_name
        wrapper._endpoint_name = endpoint_name
        
        return wrapper
    return decorator


@contextmanager
def robust_service_integration(services: List[str], 
                              failure_tolerance: int = 1,
                              retry_on_failure: bool = True):
    """
    Context manager for robust service integration testing.
    
    Args:
        services: List of service names to integrate
        failure_tolerance: Number of failures to tolerate before giving up
        retry_on_failure: Whether to retry failed operations
    """
    framework = IntegrationTestFramework()
    
    # Configure failure tolerance
    for service in services:
        config = framework.service_configs.get(service)
        if config:
            config.circuit_breaker_threshold = failure_tolerance
            if retry_on_failure:
                config.retry_attempts = max(config.retry_attempts, 2)
    
    yield framework