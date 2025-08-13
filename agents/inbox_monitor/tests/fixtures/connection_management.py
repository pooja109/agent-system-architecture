"""
Connection pool management and monitoring for test execution.

This module provides comprehensive connection pool management to prevent connection 
exhaustion, leaks, and deadlocks during test execution.
"""
import pytest
import asyncio
import weakref
import threading
import time
from typing import Dict, List, Optional, Any, AsyncContextManager, ContextManager, Set
from dataclasses import dataclass, field
from contextlib import asynccontextmanager, contextmanager
from unittest import mock


@dataclass
class ConnectionBudget:
    """Connection resource budget for test execution."""
    max_connections: int
    max_concurrent_operations: int
    connection_timeout: float
    idle_timeout: float
    cleanup_interval: float = 30.0


class ConnectionPoolManager:
    """Manages connection pools and prevents resource exhaustion."""
    
    def __init__(self):
        self.active_connections: Set[Any] = set()
        self.connection_pools: Dict[str, Any] = {}
        self.connection_budgets: Dict[str, ConnectionBudget] = {}
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.connection_stats: Dict[str, int] = {}
        
        # Default budgets by service type
        self.default_budgets = {
            'azure': ConnectionBudget(5, 3, 30.0, 300.0),
            'graph_api': ConnectionBudget(3, 2, 20.0, 180.0),
            'salesforce': ConnectionBudget(4, 2, 25.0, 240.0),
            'database': ConnectionBudget(8, 4, 15.0, 600.0),
            'generic': ConnectionBudget(10, 5, 30.0, 300.0)
        }
    
    def set_connection_budget(self, service_type: str, budget: ConnectionBudget):
        """Set connection budget for service type."""
        self.connection_budgets[service_type] = budget
    
    def get_connection_budget(self, service_type: str) -> ConnectionBudget:
        """Get connection budget for service type."""
        return self.connection_budgets.get(service_type, self.default_budgets.get(service_type, self.default_budgets['generic']))
    
    def register_connection(self, connection: Any, service_type: str = 'generic'):
        """Register a connection for tracking."""
        self.active_connections.add(connection)
        self.connection_stats[service_type] = self.connection_stats.get(service_type, 0) + 1
        
        # Add weak reference for automatic cleanup
        def cleanup_callback():
            if connection in self.active_connections:
                self.active_connections.remove(connection)
                self.connection_stats[service_type] = max(0, self.connection_stats.get(service_type, 0) - 1)
        
        try:
            weakref.finalize(connection, cleanup_callback)
        except TypeError:
            # Object doesn't support weak references
            pass
    
    def unregister_connection(self, connection: Any, service_type: str = 'generic'):
        """Unregister a connection."""
        if connection in self.active_connections:
            self.active_connections.remove(connection)
            self.connection_stats[service_type] = max(0, self.connection_stats.get(service_type, 0) - 1)
    
    def get_connection_count(self, service_type: Optional[str] = None) -> int:
        """Get current connection count."""
        if service_type:
            return self.connection_stats.get(service_type, 0)
        return len(self.active_connections)
    
    def check_connection_limits(self, service_type: str) -> bool:
        """Check if creating new connection would exceed limits."""
        budget = self.get_connection_budget(service_type)
        current_count = self.connection_stats.get(service_type, 0)
        return current_count < budget.max_connections
    
    @asynccontextmanager
    async def managed_connection(self, connection_factory: Any, service_type: str = 'generic', **kwargs):
        """Context manager for managed connection lifecycle."""
        budget = self.get_connection_budget(service_type)
        
        if not self.check_connection_limits(service_type):
            raise RuntimeError(f"Connection limit exceeded for {service_type}: {budget.max_connections}")
        
        connection = None
        try:
            # Create connection with timeout
            connection = await asyncio.wait_for(
                connection_factory(**kwargs),
                timeout=budget.connection_timeout
            )
            
            self.register_connection(connection, service_type)
            yield connection
            
        finally:
            if connection:
                try:
                    if hasattr(connection, 'close'):
                        if asyncio.iscoroutinefunction(connection.close):
                            await asyncio.wait_for(connection.close(), timeout=5.0)
                        else:
                            connection.close()
                    elif hasattr(connection, 'disconnect'):
                        if asyncio.iscoroutinefunction(connection.disconnect):
                            await asyncio.wait_for(connection.disconnect(), timeout=5.0)
                        else:
                            connection.disconnect()
                except Exception:
                    pass  # Best effort cleanup
                
                self.unregister_connection(connection, service_type)
    
    @contextmanager
    def connection_pool(self, service_type: str = 'generic'):
        """Context manager for connection pool management."""
        pool_key = f"pool_{service_type}_{id(self)}"
        
        try:
            yield self
        finally:
            # Cleanup any pools created during test
            if pool_key in self.connection_pools:
                pool = self.connection_pools.pop(pool_key)
                if hasattr(pool, 'close'):
                    try:
                        if asyncio.iscoroutinefunction(pool.close):
                            asyncio.create_task(pool.close())
                        else:
                            pool.close()
                    except Exception:
                        pass
    
    async def cleanup_all_connections(self):
        """Clean up all tracked connections."""
        cleanup_tasks = []
        
        for connection in list(self.active_connections):
            try:
                if hasattr(connection, 'close'):
                    if asyncio.iscoroutinefunction(connection.close):
                        cleanup_tasks.append(asyncio.create_task(connection.close()))
                    else:
                        connection.close()
                elif hasattr(connection, 'disconnect'):
                    if asyncio.iscoroutinefunction(connection.disconnect):
                        cleanup_tasks.append(asyncio.create_task(connection.disconnect()))
                    else:
                        connection.disconnect()
            except Exception:
                pass
        
        # Wait for async cleanup to complete
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Clear tracking
        self.active_connections.clear()
        self.connection_stats.clear()


# Mock connection factories for testing
class MockConnectionFactory:
    """Factory for creating mock connections with resource tracking."""
    
    def __init__(self, connection_manager: ConnectionPoolManager):
        self.connection_manager = connection_manager
        self.connection_counter = 0
    
    async def create_azure_client(self, **kwargs):
        """Create mock Azure client."""
        self.connection_counter += 1
        client = mock.AsyncMock()
        client.connection_id = f"azure_{self.connection_counter}"
        client.close = mock.AsyncMock()
        return client
    
    async def create_graph_client(self, **kwargs):
        """Create mock Graph API client."""
        self.connection_counter += 1
        client = mock.AsyncMock()
        client.connection_id = f"graph_{self.connection_counter}"
        client.close = mock.AsyncMock()
        return client
    
    async def create_salesforce_client(self, **kwargs):
        """Create mock Salesforce client."""
        self.connection_counter += 1
        client = mock.AsyncMock()
        client.connection_id = f"salesforce_{self.connection_counter}"
        client.close = mock.AsyncMock()
        return client
    
    async def create_database_connection(self, **kwargs):
        """Create mock database connection."""
        self.connection_counter += 1
        connection = mock.AsyncMock()
        connection.connection_id = f"db_{self.connection_counter}"
        connection.close = mock.AsyncMock()
        return connection


class ConnectionLeakDetector:
    """Detects and reports connection leaks during test execution."""
    
    def __init__(self):
        self.baseline_connections = {}
        self.leak_threshold = 5  # Number of leaked connections that trigger warnings
        
    def capture_baseline(self, connection_manager: ConnectionPoolManager):
        """Capture baseline connection counts."""
        self.baseline_connections = connection_manager.connection_stats.copy()
    
    def detect_leaks(self, connection_manager: ConnectionPoolManager) -> Dict[str, Any]:
        """Detect connection leaks compared to baseline."""
        current_connections = connection_manager.connection_stats
        leaks = {}
        
        for service_type, current_count in current_connections.items():
            baseline_count = self.baseline_connections.get(service_type, 0)
            leak_count = current_count - baseline_count
            
            if leak_count > 0:
                leaks[service_type] = leak_count
        
        # Check for completely new service types
        for service_type in current_connections:
            if service_type not in self.baseline_connections:
                leaks[f"new_service_{service_type}"] = current_connections[service_type]
        
        total_leaks = sum(leaks.values())
        
        return {
            'has_leaks': total_leaks > 0,
            'total_leaked_connections': total_leaks,
            'leaks_by_service': leaks,
            'leak_warning': total_leaks >= self.leak_threshold
        }


class ConnectionPoolValidator:
    """Validates connection pool behavior and limits."""
    
    def __init__(self):
        self.validation_errors = []
    
    def validate_connection_limits(self, manager: ConnectionPoolManager, service_type: str) -> bool:
        """Validate connection limits are enforced."""
        budget = manager.get_connection_budget(service_type)
        current_count = manager.get_connection_count(service_type)
        
        if current_count > budget.max_connections:
            self.validation_errors.append(
                f"Connection limit exceeded for {service_type}: {current_count} > {budget.max_connections}"
            )
            return False
        
        return True
    
    def validate_connection_cleanup(self, initial_connections: Dict[str, int], 
                                  final_connections: Dict[str, int]) -> bool:
        """Validate connections were properly cleaned up."""
        cleanup_success = True
        
        for service_type, final_count in final_connections.items():
            initial_count = initial_connections.get(service_type, 0)
            if final_count > initial_count:
                self.validation_errors.append(
                    f"Connection cleanup failed for {service_type}: {final_count} > {initial_count}"
                )
                cleanup_success = False
        
        return cleanup_success
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get validation report."""
        return {
            'validation_passed': len(self.validation_errors) == 0,
            'error_count': len(self.validation_errors),
            'errors': self.validation_errors.copy()
        }


@pytest.fixture(scope="function")
def connection_manager():
    """Provide connection pool management for each test."""
    manager = ConnectionPoolManager()
    try:
        yield manager
    finally:
        # Cleanup connections
        loop = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(manager.cleanup_all_connections())
            else:
                loop.run_until_complete(manager.cleanup_all_connections())
        except RuntimeError:
            # Create new event loop for cleanup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.cleanup_all_connections())
            finally:
                loop.close()


@pytest.fixture(scope="function")
def mock_connection_factory(connection_manager):
    """Provide mock connection factory with resource tracking."""
    return MockConnectionFactory(connection_manager)


@pytest.fixture(scope="function")
def connection_leak_detector():
    """Provide connection leak detection."""
    return ConnectionLeakDetector()


@pytest.fixture(scope="function")
def connection_validator():
    """Provide connection pool validation."""
    return ConnectionPoolValidator()


# Connection pool testing utilities
class ConnectionPoolTester:
    """Utilities for testing connection pool behavior."""
    
    def __init__(self, manager: ConnectionPoolManager, factory: MockConnectionFactory):
        self.manager = manager
        self.factory = factory
    
    async def test_connection_limits(self, service_type: str = 'generic') -> Dict[str, Any]:
        """Test connection limit enforcement."""
        budget = self.manager.get_connection_budget(service_type)
        connections = []
        limit_enforced = False
        
        try:
            # Try to create more connections than the limit
            for i in range(budget.max_connections + 2):
                async with self.manager.managed_connection(
                    self.factory.create_azure_client, service_type
                ) as conn:
                    connections.append(conn)
        except RuntimeError as e:
            limit_enforced = "Connection limit exceeded" in str(e)
        
        return {
            'limit_enforced': limit_enforced,
            'connections_created': len(connections),
            'max_allowed': budget.max_connections
        }
    
    async def test_connection_cleanup(self, service_type: str = 'generic') -> Dict[str, Any]:
        """Test connection cleanup behavior."""
        initial_count = self.manager.get_connection_count(service_type)
        
        # Create and release connections
        async with self.manager.managed_connection(
            self.factory.create_azure_client, service_type
        ) as conn:
            during_count = self.manager.get_connection_count(service_type)
        
        final_count = self.manager.get_connection_count(service_type)
        
        return {
            'initial_count': initial_count,
            'during_count': during_count,
            'final_count': final_count,
            'cleanup_successful': final_count == initial_count
        }
    
    async def stress_test_connections(self, concurrent_count: int = 5, 
                                    service_type: str = 'generic') -> Dict[str, Any]:
        """Stress test connection pool with concurrent operations."""
        budget = self.manager.get_connection_budget(service_type)
        actual_concurrent = min(concurrent_count, budget.max_concurrent_operations)
        
        async def create_connection(conn_id: int):
            async with self.manager.managed_connection(
                self.factory.create_azure_client, service_type
            ) as conn:
                # Simulate work
                await asyncio.sleep(0.1)
                return f"conn_{conn_id}_completed"
        
        # Run concurrent connections
        tasks = [create_connection(i) for i in range(actual_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_results = [r for r in results if isinstance(r, str)]
        error_results = [r for r in results if isinstance(r, Exception)]
        
        return {
            'concurrent_operations': actual_concurrent,
            'successful_connections': len(successful_results),
            'failed_connections': len(error_results),
            'final_connection_count': self.manager.get_connection_count(service_type),
            'errors': [str(e) for e in error_results]
        }


@pytest.fixture(scope="function")
def connection_pool_tester(connection_manager, mock_connection_factory):
    """Provide connection pool testing utilities."""
    return ConnectionPoolTester(connection_manager, mock_connection_factory)


# Connection management decorators
def connection_limit(service_type: str, max_connections: int):
    """Decorator to enforce connection limits on test functions."""
    def decorator(test_func):
        async def wrapper(*args, **kwargs):
            # Find connection_manager in args/kwargs
            manager = None
            for arg in args:
                if isinstance(arg, ConnectionPoolManager):
                    manager = arg
                    break
            
            if not manager and 'connection_manager' in kwargs:
                manager = kwargs['connection_manager']
            
            if manager:
                budget = manager.get_connection_budget(service_type)
                budget.max_connections = max_connections
                manager.set_connection_budget(service_type, budget)
            
            return await test_func(*args, **kwargs)
        
        wrapper.__name__ = test_func.__name__
        wrapper.__doc__ = test_func.__doc__
        return wrapper
    return decorator


# Export commonly used components
__all__ = [
    'ConnectionPoolManager', 'ConnectionBudget', 'MockConnectionFactory',
    'ConnectionLeakDetector', 'ConnectionPoolValidator', 'ConnectionPoolTester',
    'connection_manager', 'mock_connection_factory', 'connection_leak_detector',
    'connection_validator', 'connection_pool_tester', 'connection_limit'
]