"""
Optimized mock management for improved test performance.

This module provides reusable mock objects and optimized mock setups to reduce
test execution time by minimizing mock creation overhead.
"""
import pytest
from unittest import mock
from typing import Dict, Any, Optional, Type, Set, Callable
from contextlib import contextmanager
import weakref


class MockPool:
    """Reusable mock object pool for performance optimization."""
    
    def __init__(self):
        self._mock_cache: Dict[str, mock.Mock] = {}
        self._spec_cache: Dict[Type, mock.Mock] = {}
        self._created_mocks: Set[mock.Mock] = set()
        self._cleanup_callbacks: List[Callable] = []
    
    def get_mock(self, name: str, spec: Optional[Type] = None, **kwargs) -> mock.Mock:
        """Get or create a mock with caching for performance."""
        # Create cache key from parameters
        cache_key = f"{name}_{id(spec)}_{hash(frozenset(kwargs.items()) if kwargs else frozenset())}"
        
        if cache_key not in self._mock_cache:
            if spec:
                mock_obj = mock.Mock(spec=spec, **kwargs)
            else:
                mock_obj = mock.Mock(**kwargs)
            
            self._mock_cache[cache_key] = mock_obj
            self._created_mocks.add(mock_obj)
        
        # Reset mock state while preserving spec and configuration
        mock_obj = self._mock_cache[cache_key]
        mock_obj.reset_mock(return_value=True, side_effect=True)
        
        return mock_obj
    
    def get_async_mock(self, name: str, spec: Optional[Type] = None, **kwargs) -> mock.AsyncMock:
        """Get or create an async mock with caching."""
        cache_key = f"async_{name}_{id(spec)}_{hash(frozenset(kwargs.items()) if kwargs else frozenset())}"
        
        if cache_key not in self._mock_cache:
            if spec:
                mock_obj = mock.AsyncMock(spec=spec, **kwargs)
            else:
                mock_obj = mock.AsyncMock(**kwargs)
            
            self._mock_cache[cache_key] = mock_obj
            self._created_mocks.add(mock_obj)
        
        mock_obj = self._mock_cache[cache_key]
        mock_obj.reset_mock(return_value=True, side_effect=True)
        
        return mock_obj
    
    def create_mock_manager(self) -> mock.MagicMock:
        """Create a mock manager for complex mock scenarios."""
        manager = mock.MagicMock()
        self._created_mocks.add(manager)
        return manager
    
    def register_cleanup_callback(self, callback: Callable):
        """Register a cleanup callback for test teardown."""
        self._cleanup_callbacks.append(callback)
    
    def clear_cache(self):
        """Clear mock cache to free memory."""
        # Call cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clear all mocks
        for mock_obj in self._created_mocks:
            try:
                if hasattr(mock_obj, 'stop'):
                    mock_obj.stop()
            except Exception:
                pass  # Ignore stop errors
        
        self._mock_cache.clear()
        self._spec_cache.clear()
        self._created_mocks.clear()
        self._cleanup_callbacks.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get mock pool statistics."""
        return {
            'cached_mocks': len(self._mock_cache),
            'created_mocks': len(self._created_mocks),
            'cleanup_callbacks': len(self._cleanup_callbacks)
        }


# Global mock pool for session-level caching
_global_mock_pool = MockPool()


# High-performance mock factory functions
def fast_mock_settings(mock_pool: MockPool = None) -> mock.Mock:
    """Create optimized settings mock."""
    if mock_pool is None:
        mock_pool = _global_mock_pool
    
    settings_mock = mock_pool.get_mock(
        "settings",
        azure_openai_api_key="test_key",
        azure_openai_endpoint="https://test.openai.azure.com/",
        azure_openai_api_version="2023-12-01-preview",
        azure_openai_chat_deployment_name="test-deployment",
        graph_client_id="test_client_id",
        graph_client_secret="test_client_secret",
        graph_tenant_id="test_tenant_id",
        salesforce_username="test@salesforce.com",
        salesforce_password="test_password",
        salesforce_security_token="test_token",
        salesforce_domain="test"
    )
    
    return settings_mock


def fast_mock_azure_client(mock_pool: MockPool = None) -> mock.AsyncMock:
    """Create optimized Azure AI Foundry client mock."""
    if mock_pool is None:
        mock_pool = _global_mock_pool
    
    azure_mock = mock_pool.get_async_mock(
        "azure_client",
        get_completion=mock.AsyncMock(return_value="mocked response"),
        close=mock.AsyncMock(),
        is_closed=False
    )
    
    return azure_mock


def fast_mock_graph_api(mock_pool: MockPool = None) -> mock.AsyncMock:
    """Create optimized Graph API client mock."""
    if mock_pool is None:
        mock_pool = _global_mock_pool
    
    graph_mock = mock_pool.get_async_mock(
        "graph_api",
        get_inbox_messages=mock.AsyncMock(return_value=[]),
        authenticate=mock.AsyncMock(return_value=True),
        get_folder_by_name=mock.AsyncMock(return_value={"id": "test_folder"}),
        move_message=mock.AsyncMock(return_value=True),
        convert_to_email_model=mock.Mock(return_value=mock.Mock(
            id="test_email",
            subject="Test Email",
            to_ai_format=mock.Mock(return_value={"id": "test_email"})
        ))
    )
    
    return graph_mock


def fast_mock_salesforce(mock_pool: MockPool = None) -> mock.AsyncMock:
    """Create optimized Salesforce client mock."""
    if mock_pool is None:
        mock_pool = _global_mock_pool
    
    salesforce_mock = mock_pool.get_async_mock(
        "salesforce",
        create_case=mock.AsyncMock(return_value={"id": "test_case", "number": "12345"}),
        update_case=mock.AsyncMock(return_value=True),
        authenticate=mock.AsyncMock(return_value=True),
        query=mock.AsyncMock(return_value={"records": []})
    )
    
    return salesforce_mock


def fast_mock_email_processor(mock_pool: MockPool = None) -> mock.AsyncMock:
    """Create optimized email processor mock."""
    if mock_pool is None:
        mock_pool = _global_mock_pool
    
    processor_mock = mock_pool.get_async_mock(
        "email_processor",
        process_inbox=mock.AsyncMock(return_value={
            "success": True,
            "processed_count": 0,
            "failed_count": 0,
            "processing_results": []
        }),
        process_single_email=mock.AsyncMock(return_value={
            "success": True,
            "email_id": "test_email",
            "action": "no_action"
        })
    )
    
    return processor_mock


def fast_mock_monitor(mock_pool: MockPool = None) -> mock.Mock:
    """Create optimized inbox monitor mock."""
    if mock_pool is None:
        mock_pool = _global_mock_pool
    
    monitor_mock = mock_pool.get_mock(
        "monitor",
        start=mock.Mock(),
        stop=mock.Mock(),
        is_running=False,
        _running=False
    )
    
    return monitor_mock


class MockContextManager:
    """Context manager for complex mock scenarios with automatic cleanup."""
    
    def __init__(self, mock_pool: MockPool):
        self.mock_pool = mock_pool
        self.active_patches: List[mock._patch] = []
        self.context_mocks: Dict[str, mock.Mock] = {}
    
    def patch(self, target: str, new: Any = None, **kwargs) -> mock.Mock:
        """Create a patch and track it for cleanup."""
        patcher = mock.patch(target, new=new, **kwargs)
        mock_obj = patcher.start()
        self.active_patches.append(patcher)
        return mock_obj
    
    def patch_object(self, obj: Any, attribute: str, new: Any = None, **kwargs) -> mock.Mock:
        """Create an object patch and track it for cleanup."""
        patcher = mock.patch.object(obj, attribute, new=new, **kwargs)
        mock_obj = patcher.start()
        self.active_patches.append(patcher)
        return mock_obj
    
    def add_mock(self, name: str, mock_obj: mock.Mock):
        """Add a mock to the context for tracking."""
        self.context_mocks[name] = mock_obj
    
    def get_mock(self, name: str) -> Optional[mock.Mock]:
        """Get a mock from the context."""
        return self.context_mocks.get(name)
    
    def cleanup(self):
        """Clean up all patches and mocks."""
        # Stop all patches
        for patcher in reversed(self.active_patches):
            try:
                patcher.stop()
            except Exception:
                pass  # Ignore stop errors
        
        # Clear tracking
        self.active_patches.clear()
        self.context_mocks.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


@pytest.fixture(scope="function")
def mock_pool():
    """Provide optimized mock pool for test."""
    return _global_mock_pool


@pytest.fixture(scope="function")
def mock_context(mock_pool):
    """Provide mock context manager for complex scenarios."""
    context = MockContextManager(mock_pool)
    try:
        yield context
    finally:
        context.cleanup()


@pytest.fixture(scope="session", autouse=True)
def cleanup_mock_pool():
    """Clean up mock pool at end of test session."""
    yield
    _global_mock_pool.clear_cache()


# Pre-configured mock combinations for common scenarios
@pytest.fixture(scope="function")
def mock_email_system(mock_pool):
    """Provide complete mocked email system for integration tests."""
    return {
        'settings': fast_mock_settings(mock_pool),
        'azure_client': fast_mock_azure_client(mock_pool),
        'graph_client': fast_mock_graph_api(mock_pool),
        'email_processor': fast_mock_email_processor(mock_pool),
        'monitor': fast_mock_monitor(mock_pool)
    }


@pytest.fixture(scope="function")
def mock_external_services(mock_pool):
    """Provide mocked external services for testing."""
    return {
        'azure_client': fast_mock_azure_client(mock_pool),
        'graph_api': fast_mock_graph_api(mock_pool),
        'salesforce': fast_mock_salesforce(mock_pool)
    }


# Performance optimized mock decorators
def with_fast_mocks(*mock_names):
    """Decorator to automatically provide fast mocks for test methods."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            mock_pool = _global_mock_pool
            
            # Add mocks to kwargs
            for name in mock_names:
                if name == 'settings':
                    kwargs['mock_settings'] = fast_mock_settings(mock_pool)
                elif name == 'azure_client':
                    kwargs['mock_azure_client'] = fast_mock_azure_client(mock_pool)
                elif name == 'graph_api':
                    kwargs['mock_graph_client'] = fast_mock_graph_api(mock_pool)
                elif name == 'salesforce':
                    kwargs['mock_salesforce'] = fast_mock_salesforce(mock_pool)
                elif name == 'email_processor':
                    kwargs['mock_email_processor'] = fast_mock_email_processor(mock_pool)
                elif name == 'monitor':
                    kwargs['mock_monitor'] = fast_mock_monitor(mock_pool)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator