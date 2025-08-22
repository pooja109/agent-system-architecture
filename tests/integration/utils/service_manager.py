#!/usr/bin/env python3
"""
Service Management Utilities
============================

Utilities for managing live services during integration testing.
"""

import subprocess
import time
import requests
import psutil
import signal
import os
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import tempfile
import shutil
import json


class ServiceManager:
    """Manages live service instances for testing."""
    
    def __init__(self, base_dir: Path = None):
        """Initialize service manager."""
        self.base_dir = base_dir or Path(__file__).parent.parent.parent.parent
        self.services = {}
        self.processes = {}
        self.temp_dirs = {}
        
    def create_test_environment(self, service_name: str) -> Path:
        """Create isolated test environment for a service."""
        # Create temporary directory for service
        temp_dir = Path(tempfile.mkdtemp(prefix=f"test-{service_name}-"))
        self.temp_dirs[service_name] = temp_dir
        
        # Copy service files
        if service_name == "inbox_monitor":
            source_dir = self.base_dir / "agents" / "inbox_monitor"
        else:  # email_agent
            source_dir = self.base_dir / "agents" / "email"
        
        if source_dir.exists():
            # Copy service directory
            service_dir = temp_dir / service_name
            shutil.copytree(source_dir, service_dir, 
                          ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.env*'))
            
            # Create test environment file
            env_content = self._create_test_env_content(service_name)
            env_file = service_dir / ".env"
            env_file.write_text(env_content)
            
            return service_dir
        else:
            raise RuntimeError(f"Source directory not found: {source_dir}")
    
    def _create_test_env_content(self, service_name: str) -> str:
        """Create secure test environment content."""
        base_env = {
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "DEBUG",
            "TEST_MODE": "true",
            "SKIP_ENV_VALIDATION": "true",
            "DISABLE_EXTERNAL_CALLS": "true",
            "USE_MOCK_DATABASE": "true",
            "MOCK_AZURE_SERVICES": "true"
        }
        
        if service_name == "inbox_monitor":
            base_env.update({
                "SERVICE_NAME": "inbox-monitor-test",
                "HEALTH_CHECK_PORT": "8080",
                "GRAPH_API_MONITORED_EMAIL": "test@example.com",
                "AZURE_KEY_VAULT_URL": "https://mock-vault.vault.azure.net",
                "DATABRICKS_SERVER_HOSTNAME": "mock.azuredatabricks.net",
                "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/mock"
            })
        else:  # email_agent
            base_env.update({
                "SERVICE_NAME": "email-agent-test",
                "HEALTH_CHECK_PORT": "8081",
                "AZURE_KEY_VAULT_URL": "https://mock-vault.vault.azure.net",
                "DATABRICKS_SERVER_HOSTNAME": "mock.azuredatabricks.net",
                "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/mock"
            })
        
        # Generate secure test credentials (clearly marked as test and non-functional)
        import uuid
        import hashlib
        import time
        
        # Generate unique test identifiers based on timestamp and service
        timestamp = str(int(time.time()))
        service_hash = hashlib.md5(f"{service_name}-{timestamp}".encode()).hexdigest()[:8]
        
        base_env.update({
            "AZURE_TENANT_ID": f"test-tenant-{service_hash}-0000-0000-000000000000",
            "AZURE_CLIENT_ID": f"test-client-{service_hash}-0000-0000-000000000000",
            "AZURE_CLIENT_SECRET": f"MOCK_SECRET_FOR_TESTING_ONLY_{service_hash.upper()}_NOT_PRODUCTION",
            "MOCK_CREDENTIALS": "true",
            "SECURITY_VALIDATION_DISABLED": "true"
        })
        
        return "\n".join(f"{key}={value}" for key, value in base_env.items())
    
    def start_service(self, service_name: str, timeout: int = 30) -> bool:
        """Start a service for testing."""
        try:
            # Create test environment
            service_dir = self.create_test_environment(service_name)
            
            # Start service process
            cmd = ["python", "main.py", "--test-mode", "--health-check-only"]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = str(service_dir)
            
            process = subprocess.Popen(
                cmd,
                cwd=service_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes[service_name] = process
            
            # Wait for service to be ready
            port = 8080 if service_name == "inbox_monitor" else 8081
            if self._wait_for_service_ready(port, timeout):
                self.services[service_name] = {
                    "process": process,
                    "port": port,
                    "service_dir": service_dir,
                    "status": "running"
                }
                return True
            else:
                self.stop_service(service_name)
                return False
                
        except Exception as e:
            print(f"Failed to start {service_name}: {e}")
            return False
    
    def _wait_for_service_ready(self, port: int, timeout: int) -> bool:
        """Wait for service to be ready on specified port."""
        import socket
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if port is listening
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    if s.connect_ex(('localhost', port)) == 0:
                        # Port is open, try health check
                        try:
                            response = requests.get(f"http://localhost:{port}/health", timeout=2)
                            if response.status_code == 200:
                                return True
                        except requests.RequestException:
                            pass
            except Exception:
                pass
            
            time.sleep(1)
        
        return False
    
    def stop_service(self, service_name: str):
        """Stop a service."""
        if service_name in self.services:
            try:
                process = self.services[service_name]["process"]
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                del self.services[service_name]
                
            except Exception as e:
                print(f"Error stopping {service_name}: {e}")
        
        # Clean up process reference
        if service_name in self.processes:
            del self.processes[service_name]
        
        # Clean up temporary directory
        if service_name in self.temp_dirs:
            try:
                shutil.rmtree(self.temp_dirs[service_name])
                del self.temp_dirs[service_name]
            except Exception as e:
                print(f"Error cleaning up temp dir for {service_name}: {e}")
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get status of a service."""
        if service_name not in self.services:
            return {"status": "not_running", "error": "Service not started"}
        
        service = self.services[service_name]
        process = service["process"]
        
        if process.poll() is None:
            # Process is still running, check health
            try:
                response = requests.get(
                    f"http://localhost:{service['port']}/health", 
                    timeout=5
                )
                return {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "port": service["port"],
                    "response_code": response.status_code,
                    "response_data": response.json() if response.status_code == 200 else None
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "port": service["port"],
                    "error": str(e)
                }
        else:
            return {
                "status": "crashed",
                "exit_code": process.poll(),
                "error": "Process exited"
            }
    
    def cleanup_all(self):
        """Clean up all services and resources."""
        for service_name in list(self.services.keys()):
            self.stop_service(service_name)
        
        # Clean up any remaining temp directories
        for service_name, temp_dir in list(self.temp_dirs.items()):
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                del self.temp_dirs[service_name]
            except Exception as e:
                print(f"Error cleaning up temp dir for {service_name}: {e}")


class DatabaseMockManager:
    """Mock database manager for testing."""
    
    def __init__(self):
        self.mock_data = {}
        self.connection_count = 0
    
    def create_mock_connection(self, service_name: str) -> Dict[str, Any]:
        """Create mock database connection."""
        self.connection_count += 1
        connection_id = f"mock-conn-{self.connection_count}"
        
        connection_info = {
            "connection_id": connection_id,
            "service": service_name,
            "status": "connected",
            "mock": True,
            "created_at": time.time()
        }
        
        self.mock_data[connection_id] = connection_info
        return connection_info
    
    def test_connection(self, connection_id: str) -> bool:
        """Test a mock database connection."""
        return connection_id in self.mock_data
    
    def close_connection(self, connection_id: str):
        """Close a mock database connection."""
        if connection_id in self.mock_data:
            del self.mock_data[connection_id]
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.mock_data),
            "active_connections": list(self.mock_data.keys())
        }


def create_service_fixtures():
    """Create service fixtures for pytest."""
    import pytest
    
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
    def service_endpoints(live_service_manager):
        """Service endpoints fixture with live service support."""
        # Try to start services if not running
        endpoints = {
            "inbox_monitor": {
                "base_url": "http://localhost:8080",
                "health_endpoint": "/health",
                "status_endpoint": "/status",
                "metrics_endpoint": "/metrics",
                "service_manager": live_service_manager
            },
            "email_agent": {
                "base_url": "http://localhost:8081",
                "health_endpoint": "/health", 
                "status_endpoint": "/status",
                "metrics_endpoint": "/metrics",
                "service_manager": live_service_manager
            }
        }
        
        # Attempt to start services for testing
        for service_name in endpoints.keys():
            try:
                live_service_manager.start_service(service_name, timeout=30)
            except Exception as e:
                print(f"Could not start {service_name} for testing: {e}")
        
        return endpoints
    
    return {
        "live_service_manager": live_service_manager,
        "database_mock": database_mock,
        "service_endpoints": service_endpoints
    }


if __name__ == "__main__":
    # Test service manager
    manager = ServiceManager()
    
    try:
        print("Testing service manager...")
        
        # Test inbox monitor
        print("Starting inbox monitor...")
        if manager.start_service("inbox_monitor"):
            print("✅ Inbox monitor started successfully")
            status = manager.get_service_status("inbox_monitor")
            print(f"Status: {status}")
        else:
            print("❌ Failed to start inbox monitor")
        
        # Test email agent
        print("Starting email agent...")
        if manager.start_service("email_agent"):
            print("✅ Email agent started successfully")
            status = manager.get_service_status("email_agent")
            print(f"Status: {status}")
        else:
            print("❌ Failed to start email agent")
        
        # Keep services running briefly
        print("Services running for 10 seconds...")
        time.sleep(10)
        
    finally:
        print("Cleaning up...")
        manager.cleanup_all()
        print("✅ Cleanup complete")