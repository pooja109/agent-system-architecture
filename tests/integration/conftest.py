#!/usr/bin/env python3
"""
Integration Test Configuration
=============================

Pytest configuration for integration tests.
"""

import pytest
import subprocess
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

# Import service management utilities
from .utils.service_manager import ServiceManager, DatabaseMockManager
from .utils.security_validator import SecurityValidator
from .utils.performance_tester import PerformanceTester


def pytest_configure(config):
    """Configure pytest for integration tests."""
    # Add custom markers
    config.addinivalue_line("markers", "docker: mark test to run with Docker")
    config.addinivalue_line("markers", "kubernetes: mark test to run with Kubernetes") 
    config.addinivalue_line("markers", "live: mark test to run against live services")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers and options."""
    
    # Skip Docker tests if Docker is not available
    docker_available = False
    if DOCKER_AVAILABLE:
        try:
            client = docker.from_env()
            client.ping()
            docker_available = True
        except Exception:
            docker_available = False
    
    # Skip Kubernetes tests if kubectl is not available
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True, text=True, timeout=5
        )
        kubectl_available = (result.returncode == 0)
    except Exception:
        kubectl_available = False
    
    # Apply skips based on availability
    for item in items:
        if "docker" in item.keywords and not docker_available:
            item.add_marker(pytest.mark.skip(reason="Docker not available"))
        
        if "kubernetes" in item.keywords and not kubectl_available:
            item.add_marker(pytest.mark.skip(reason="kubectl not available"))


@pytest.fixture(scope="session")
def integration_config():
    """Integration test configuration."""
    return {
        "services": {
            "inbox_monitor": {
                "name": "inbox-monitor",
                "port": 8080,
                "health_endpoint": "/health",
                "container_image": "inbox-monitor:latest",
                "k8s_namespace": "email-agents"
            },
            "email_agent": {
                "name": "email-agent", 
                "port": 8081,
                "health_endpoint": "/health",
                "container_image": "email-agent:latest",
                "k8s_namespace": "email-agents"
            }
        },
        "timeouts": {
            "health_check": 10,
            "container_startup": 30,
            "service_startup": 60,
            "test_timeout": 120
        },
        "retry": {
            "max_attempts": 3,
            "delay": 2,
            "backoff": 1.5
        }
    }


@pytest.fixture(scope="session")
def docker_client():
    """Docker client for container tests."""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker library not available")
    
    try:
        client = docker.from_env()
        client.ping()
        yield client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture(scope="session")
def kubectl_available():
    """Check if kubectl is available."""
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            pytest.skip("kubectl not available")
        return True
    except Exception:
        pytest.skip("kubectl not available")


@pytest.fixture(scope="session")
def kubernetes_cluster(kubectl_available):
    """Check if Kubernetes cluster is available."""
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            pytest.skip("Kubernetes cluster not available")
        return True
    except Exception:
        pytest.skip("Kubernetes cluster not available")


@pytest.fixture
def service_health_checker(integration_config):
    """Health checker utility for services."""
    
    def check_service_health(service_name: str, timeout: int = None) -> Dict[str, Any]:
        """Check health of a specific service."""
        if timeout is None:
            timeout = integration_config["timeouts"]["health_check"]
        
        service_config = integration_config["services"].get(service_name)
        if not service_config:
            return {"error": f"Unknown service: {service_name}"}
        
        url = f"http://localhost:{service_config['port']}{service_config['health_endpoint']}"
        
        try:
            response = requests.get(url, timeout=timeout)
            return {
                "service": service_name,
                "status_code": response.status_code,
                "healthy": response.status_code == 200,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code == 200 else None
            }
        except requests.exceptions.RequestException as e:
            return {
                "service": service_name,
                "healthy": False,
                "error": str(e)
            }
    
    return check_service_health


@pytest.fixture
def container_manager(docker_client, integration_config):
    """Container management utility."""
    
    class ContainerManager:
        def __init__(self):
            self.client = docker_client
            self.config = integration_config
            self.containers = {}
        
        def start_service_container(self, service_name: str, **kwargs) -> str:
            """Start a container for a service."""
            service_config = self.config["services"][service_name]
            
            container_config = {
                "image": service_config["container_image"],
                "name": f"test-{service_name}",
                "ports": {f"{service_config['port']}/tcp": service_config['port']},
                "environment": {
                    "TEST_MODE": "true",
                    "SKIP_ENV_VALIDATION": "true",
                    "LOG_LEVEL": "INFO"
                },
                "detach": True,
                "remove": True
            }
            
            # Override with custom config
            container_config.update(kwargs)
            
            try:
                # Remove existing container if any
                try:
                    old_container = self.client.containers.get(container_config["name"])
                    old_container.remove(force=True)
                except docker.errors.NotFound:
                    pass
                
                # Start new container
                container = self.client.containers.run(**container_config)
                self.containers[service_name] = container
                
                # Wait for startup
                time.sleep(self.config["timeouts"]["container_startup"])
                
                return container.id
                
            except docker.errors.ImageNotFound:
                pytest.skip(f"Container image {container_config['image']} not found")
            except Exception as e:
                pytest.fail(f"Failed to start container for {service_name}: {e}")
        
        def stop_service_container(self, service_name: str):
            """Stop a container for a service."""
            if service_name in self.containers:
                try:
                    self.containers[service_name].stop(timeout=5)
                    del self.containers[service_name]
                except Exception:
                    pass
        
        def cleanup_all(self):
            """Clean up all managed containers."""
            for service_name in list(self.containers.keys()):
                self.stop_service_container(service_name)
    
    manager = ContainerManager()
    yield manager
    manager.cleanup_all()


@pytest.fixture
def kubernetes_manager(kubectl_available, integration_config):
    """Kubernetes management utility."""
    
    class KubernetesManager:
        def __init__(self):
            self.config = integration_config
            self.test_namespace = "integration-test"
            self.created_resources = []
        
        def apply_manifest(self, manifest_content: str, namespace: str = None) -> bool:
            """Apply a Kubernetes manifest."""
            if namespace is None:
                namespace = self.test_namespace
            
            try:
                result = subprocess.run([
                    "kubectl", "apply", 
                    "--dry-run=server",
                    "--validate=true",
                    "-f", "-",
                    "-n", namespace
                ], input=manifest_content, text=True, capture_output=True)
                
                return result.returncode == 0
                
            except Exception:
                return False
        
        def delete_resource(self, resource_type: str, resource_name: str, namespace: str = None):
            """Delete a Kubernetes resource."""
            if namespace is None:
                namespace = self.test_namespace
            
            try:
                subprocess.run([
                    "kubectl", "delete", resource_type, resource_name,
                    "-n", namespace, "--ignore-not-found=true"
                ], capture_output=True)
            except Exception:
                pass
        
        def cleanup_all(self):
            """Clean up all created resources."""
            for resource_type, resource_name in self.created_resources:
                self.delete_resource(resource_type, resource_name)
    
    manager = KubernetesManager()
    yield manager
    manager.cleanup_all()


@pytest.fixture
def test_data_factory():
    """Factory for creating test data."""
    
    def create_test_environment_config(service_name: str) -> Dict[str, str]:
        """Create test environment configuration."""
        base_config = {
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "INFO",
            "TEST_MODE": "true",
            "SKIP_ENV_VALIDATION": "true"
        }
        
        if service_name == "inbox_monitor":
            base_config.update({
                "SERVICE_NAME": "inbox-monitor-test",
                "HEALTH_CHECK_PORT": "8080",
                "GRAPH_API_MONITORED_EMAIL": "test@example.com"
            })
        elif service_name == "email_agent":
            base_config.update({
                "SERVICE_NAME": "email-agent-test",
                "HEALTH_CHECK_PORT": "8081"
            })
        
        return base_config
    
    def create_test_manifest(service_name: str, resource_type: str) -> str:
        """Create test Kubernetes manifest."""
        if resource_type == "pod":
            return f"""
apiVersion: v1
kind: Pod
metadata:
  name: test-{service_name}
  labels:
    app: {service_name}
    test: integration
spec:
  containers:
  - name: {service_name}
    image: python:3.11-slim
    command: ["sleep", "300"]
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
"""
        elif resource_type == "service":
            port = 8080 if service_name == "inbox-monitor" else 8081
            return f"""
apiVersion: v1
kind: Service
metadata:
  name: test-{service_name}
spec:
  selector:
    app: {service_name}
  ports:
  - port: 80
    targetPort: {port}
  type: ClusterIP
"""
        
        return ""
    
    return {
        "environment_config": create_test_environment_config,
        "manifest": create_test_manifest
    }


@pytest.fixture
def retry_helper(integration_config):
    """Retry helper utility."""
    
    def retry_operation(operation, max_attempts: int = None, delay: float = None, backoff: float = None):
        """Retry an operation with exponential backoff."""
        if max_attempts is None:
            max_attempts = integration_config["retry"]["max_attempts"]
        if delay is None:
            delay = integration_config["retry"]["delay"]
        if backoff is None:
            backoff = integration_config["retry"]["backoff"]
        
        last_exception = None
        current_delay = delay
        
        for attempt in range(max_attempts):
            try:
                return operation()
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        raise last_exception
    
    return retry_operation


# Live service management fixtures
@pytest.fixture(scope="class")
def live_service_manager():
    """Live service manager fixture."""
    manager = ServiceManager()
    yield manager
    manager.cleanup_all()


@pytest.fixture
def database_mock():
    """Database mock fixture."""
    return DatabaseMockManager()


@pytest.fixture
def security_validator():
    """Security validator fixture."""
    return SecurityValidator()


@pytest.fixture(scope="class")
def performance_tester():
    """Performance tester fixture."""
    return PerformanceTester()


@pytest.fixture
def service_endpoints(live_service_manager):
    """Service endpoints fixture with live service support."""
    # Define service endpoint configurations
    endpoints = {
        "inbox_monitor": {
            "base_url": "http://localhost:8080",
            "health_endpoint": "/health",
            "status_endpoint": "/status", 
            "metrics_endpoint": "/metrics",
            "service_manager": live_service_manager,
            "port": 8080
        },
        "email_agent": {
            "base_url": "http://localhost:8081",
            "health_endpoint": "/health",
            "status_endpoint": "/status",
            "metrics_endpoint": "/metrics", 
            "service_manager": live_service_manager,
            "port": 8081
        }
    }
    
    # Attempt to start services for testing (optional)
    started_services = []
    for service_name in endpoints.keys():
        try:
            if live_service_manager.start_service(service_name, timeout=15):
                started_services.append(service_name)
                print(f"✅ Started {service_name} for testing")
        except Exception as e:
            print(f"⚠️  Could not start {service_name} for testing: {e}")
    
    # Add metadata about which services are running
    for service_name, config in endpoints.items():
        config["is_live"] = service_name in started_services
        if service_name in started_services:
            status = live_service_manager.get_service_status(service_name)
            config["live_status"] = status
    
    return endpoints


# Test result collection and reporting
@pytest.fixture(scope="session") 
def test_results_collector():
    """Collect test results for reporting."""
    results = {
        "isolation_tests": [],
        "container_tests": [],
        "kubernetes_tests": [],
        "communication_tests": [],
        "scaling_tests": [],
        "resilience_tests": []
    }
    
    yield results
    
    # Could add summary reporting here
    total_tests = sum(len(tests) for tests in results.values())
    if total_tests > 0:
        print(f"\n📊 Integration Test Summary: {total_tests} tests collected")


def pytest_runtest_teardown(item, nextitem):
    """Clean up after each test."""
    # Add any global cleanup if needed
    pass


def pytest_sessionfinish(session, exitstatus):
    """Session cleanup."""
    print("\n🧹 Integration test session finished - cleaning up...")
    
    # Clean up any leftover containers
    if DOCKER_AVAILABLE:
        try:
            client = docker.from_env()
            test_containers = client.containers.list(filters={"name": "test-"})
            for container in test_containers:
                try:
                    container.stop(timeout=2)
                except Exception:
                    pass
        except Exception:
            pass