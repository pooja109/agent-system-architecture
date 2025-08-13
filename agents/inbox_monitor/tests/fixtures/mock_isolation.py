"""
Mock state isolation and management for reliable test execution.

This module provides comprehensive mock isolation to prevent mock state leakage
between tests and ensure clean, predictable mock behavior.
"""
import pytest
from unittest import mock
from typing import Dict, List, Any, Optional, Callable, Set, Type
from contextlib import contextmanager, ExitStack
import weakref
import asyncio


class MockStateManager:
    """Manages mock state to prevent leakage between tests."""
    
    def __init__(self):
        self.active_patches: List[mock._patch] = []
        self.mock_registry: Dict[str, mock.Mock] = {}
        self.patch_stack: ExitStack = ExitStack()
        self.original_values: Dict[str, Any] = {}
        self.async_mocks: Set[mock.AsyncMock] = set()
        self.mock_call_history: Dict[str, List] = {}
        self.weak_references: List[weakref.ref] = []
    
    def create_isolated_mock(self, target: str, spec: Optional[Type] = None, **kwargs) -> mock.Mock:
        """Create an isolated mock that will be automatically cleaned up."""
        mock_obj = mock.Mock(spec=spec, **kwargs) if spec else mock.Mock(**kwargs)
        self.mock_registry[target] = mock_obj
        
        # Track weak reference for cleanup validation
        try:
            self.weak_references.append(weakref.ref(mock_obj))
        except TypeError:
            pass  # Some objects don't support weak references
        
        return mock_obj
    
    def create_isolated_async_mock(self, target: str, spec: Optional[Type] = None, **kwargs) -> mock.AsyncMock:
        """Create an isolated async mock with automatic cleanup."""
        async_mock = mock.AsyncMock(spec=spec, **kwargs)
        self.mock_registry[target] = async_mock
        self.async_mocks.add(async_mock)
        
        # Track weak reference
        try:
            self.weak_references.append(weakref.ref(async_mock))
        except TypeError:
            pass
        
        return async_mock
    
    def patch_with_isolation(self, target: str, new: Any = mock.DEFAULT, **kwargs):
        """Create a patch with automatic cleanup and state isolation."""
        # Auto-detect if we need an async mock
        if new is mock.DEFAULT:
            if self._should_use_async_mock(target):
                new = self.create_isolated_async_mock(target)
            else:
                new = self.create_isolated_mock(target)
        
        patcher = mock.patch(target, new, **kwargs)
        patched_mock = self.patch_stack.enter_context(patcher)
        
        # Register the actual patched object
        self.mock_registry[target] = patched_mock
        
        # Track call history for debugging
        self.mock_call_history[target] = []
        
        return patched_mock
    
    def patch_object_with_isolation(self, obj: Any, attribute: str, new: Any = mock.DEFAULT, **kwargs):
        """Create an object patch with isolation."""
        if new is mock.DEFAULT:
            if self._should_use_async_mock(f"{obj.__class__.__module__}.{obj.__class__.__name__}.{attribute}"):
                new = self.create_isolated_async_mock(f"{obj.__class__.__name__}.{attribute}")
            else:
                new = self.create_isolated_mock(f"{obj.__class__.__name__}.{attribute}")
        
        patcher = mock.patch.object(obj, attribute, new, **kwargs)
        patched_mock = self.patch_stack.enter_context(patcher)
        
        target_name = f"{obj.__class__.__name__}.{attribute}"
        self.mock_registry[target_name] = patched_mock
        self.mock_call_history[target_name] = []
        
        return patched_mock
    
    def _should_use_async_mock(self, target: str) -> bool:
        """Determine if target should use AsyncMock based on common patterns."""
        async_indicators = [
            'client', 'Client', 'async', 'Async',
            'connect', 'disconnect', 'close',
            'get_completion', 'authenticate',
            'create_case', 'update_case'
        ]
        
        return any(indicator in target for indicator in async_indicators)
    
    def get_mock(self, target: str) -> Optional[mock.Mock]:
        """Get a registered mock by target name."""
        return self.mock_registry.get(target)
    
    def reset_mock_state(self, target: str):
        """Reset the state of a specific mock."""
        if target in self.mock_registry:
            mock_obj = self.mock_registry[target]
            mock_obj.reset_mock()
            if target in self.mock_call_history:
                self.mock_call_history[target].clear()
    
    def reset_all_mocks(self):
        """Reset state of all registered mocks without cleanup."""
        for mock_obj in self.mock_registry.values():
            if hasattr(mock_obj, 'reset_mock'):
                mock_obj.reset_mock()
        
        # Clear call history
        for target in self.mock_call_history:
            self.mock_call_history[target].clear()
    
    def cleanup_all_mocks(self):
        """Clean up all mocks and restore original state."""
        # Close patch stack (this restores original implementations)
        try:
            self.patch_stack.close()
        except Exception:
            pass  # Ignore cleanup errors
        
        self.patch_stack = ExitStack()
        
        # Reset all registered mocks
        for mock_obj in self.mock_registry.values():
            if hasattr(mock_obj, 'reset_mock'):
                try:
                    mock_obj.reset_mock()
                except Exception:
                    pass  # Ignore reset errors
        
        # Clean up async mocks specifically
        for async_mock in list(self.async_mocks):
            try:
                if hasattr(async_mock, 'reset_mock'):
                    async_mock.reset_mock()
            except Exception:
                pass
        
        # Clear all tracking
        self.mock_registry.clear()
        self.active_patches.clear()
        self.original_values.clear()
        self.async_mocks.clear()
        self.mock_call_history.clear()
        self.weak_references.clear()
    
    def get_mock_statistics(self) -> Dict[str, Any]:
        """Get statistics about current mock state."""
        active_refs = sum(1 for ref in self.weak_references if ref() is not None)
        
        return {
            'registered_mocks': len(self.mock_registry),
            'active_patches': len(self.active_patches),
            'async_mocks': len(self.async_mocks),
            'active_references': active_refs,
            'call_history_entries': sum(len(calls) for calls in self.mock_call_history.values()),
            'mock_targets': list(self.mock_registry.keys())
        }


@pytest.fixture(scope="function")
def isolated_mocks():
    """Provide isolated mock management for each test."""
    manager = MockStateManager()
    
    try:
        yield manager
    finally:
        manager.cleanup_all_mocks()


# High-level service mock fixtures
@pytest.fixture(scope="function")
def mock_azure_client_isolated(isolated_mocks):
    """Provide isolated Azure AI Foundry client mock."""
    mock_client = isolated_mocks.patch_with_isolation(
        'services.azure_ai_foundry_client.AzureAIFoundryClient'
    )
    
    # Configure common methods
    mock_client.get_completion = mock.AsyncMock(return_value="mocked completion")
    mock_client.close = mock.AsyncMock()
    mock_client.is_closed = False
    
    return mock_client


@pytest.fixture(scope="function") 
def mock_graph_api_isolated(isolated_mocks):
    """Provide isolated Graph API client mock."""
    mock_client = isolated_mocks.patch_with_isolation(
        'services.graph_api_client.GraphAPIClient'
    )
    
    # Configure common methods
    mock_client.get_inbox_messages = mock.AsyncMock(return_value=[])
    mock_client.authenticate = mock.AsyncMock(return_value=True)
    mock_client.get_folder_by_name = mock.AsyncMock(return_value={"id": "test_folder"})
    mock_client.move_message = mock.AsyncMock(return_value=True)
    
    return mock_client


@pytest.fixture(scope="function")
def mock_salesforce_client_isolated(isolated_mocks):
    """Provide isolated Salesforce client mock."""
    mock_client = isolated_mocks.patch_with_isolation(
        'services.salesforce_client.SalesforceClient'
    )
    
    # Configure common methods
    mock_client.create_case = mock.AsyncMock(return_value={"id": "test_case", "number": "12345"})
    mock_client.update_case = mock.AsyncMock(return_value=True)
    mock_client.get_case = mock.AsyncMock(return_value={"id": "test_case", "status": "open"})
    mock_client.authenticate = mock.AsyncMock(return_value=True)
    
    return mock_client


@pytest.fixture(scope="function")
def mock_email_processor_isolated(isolated_mocks):
    """Provide isolated email processor mock."""
    mock_processor = isolated_mocks.patch_with_isolation(
        'services.email_processor.EmailProcessor'
    )
    
    # Configure common methods
    mock_processor.process_inbox = mock.AsyncMock(return_value={
        "success": True,
        "processed_count": 0,
        "failed_count": 0,
        "processing_results": []
    })
    mock_processor.process_single_email = mock.AsyncMock(return_value={
        "success": True,
        "email_id": "test_email",
        "action": "no_action"
    })
    
    return mock_processor


@pytest.fixture(scope="function")
def mock_monitor_isolated(isolated_mocks):
    """Provide isolated inbox monitor mock."""
    mock_monitor = isolated_mocks.patch_with_isolation(
        'services.monitor.InboxMonitor'
    )
    
    # Configure common methods and attributes
    mock_monitor.start = mock.AsyncMock()
    mock_monitor.stop = mock.AsyncMock()
    mock_monitor.is_running = False
    mock_monitor._running = False
    mock_monitor.check_inbox = mock.AsyncMock(return_value=True)
    
    return mock_monitor


@contextmanager
def temporary_mock_state(mock_obj: mock.Mock, **method_configs):
    """Temporarily apply mock state without affecting other tests."""
    if not isinstance(mock_obj, (mock.Mock, mock.AsyncMock)):
        raise ValueError("Object must be a Mock or AsyncMock instance")
    
    # Backup original state
    original_return_values = {}
    original_side_effects = {}
    
    for method_name, config in method_configs.items():
        if hasattr(mock_obj, method_name):
            method_mock = getattr(mock_obj, method_name)
            if hasattr(method_mock, 'return_value'):
                original_return_values[method_name] = method_mock.return_value
            if hasattr(method_mock, 'side_effect'):
                original_side_effects[method_name] = method_mock.side_effect
            
            # Apply new configuration
            if isinstance(config, dict):
                if 'return_value' in config:
                    method_mock.return_value = config['return_value']
                if 'side_effect' in config:
                    method_mock.side_effect = config['side_effect']
            else:
                # Direct return value
                method_mock.return_value = config
    
    try:
        yield mock_obj
    finally:
        # Restore original state
        for method_name in method_configs:
            if hasattr(mock_obj, method_name):
                method_mock = getattr(mock_obj, method_name)
                
                if method_name in original_return_values:
                    method_mock.return_value = original_return_values[method_name]
                if method_name in original_side_effects:
                    method_mock.side_effect = original_side_effects[method_name]


class MockValidationManager:
    """Validates mock isolation and prevents state leakage."""
    
    def __init__(self):
        self.pre_test_state: Dict[str, Any] = {}
        self.post_test_state: Dict[str, Any] = {}
    
    def capture_pre_test_state(self, manager: MockStateManager):
        """Capture mock state before test execution."""
        self.pre_test_state = manager.get_mock_statistics()
    
    def validate_post_test_isolation(self, manager: MockStateManager) -> Dict[str, Any]:
        """Validate mock isolation after test execution."""
        self.post_test_state = manager.get_mock_statistics()
        
        # Check for state leakage
        validation_results = {
            'isolation_success': True,
            'issues': [],
            'statistics': self.post_test_state
        }
        
        # Validate no excessive mock accumulation
        if self.post_test_state['registered_mocks'] > 50:
            validation_results['isolation_success'] = False
            validation_results['issues'].append(f"Too many registered mocks: {self.post_test_state['registered_mocks']}")
        
        return validation_results


@pytest.fixture(scope="function")
def mock_validation():
    """Provide mock validation for test isolation verification."""
    return MockValidationManager()


# Specialized context managers for common mock scenarios
@contextmanager
def mock_external_services(isolated_mocks):
    """Context manager that mocks all external services at once."""
    mocks = {}
    
    try:
        # Mock all major external services
        mocks['azure'] = isolated_mocks.patch_with_isolation('services.azure_ai_foundry_client.AzureAIFoundryClient')
        mocks['graph'] = isolated_mocks.patch_with_isolation('services.graph_api_client.GraphAPIClient')
        mocks['salesforce'] = isolated_mocks.patch_with_isolation('services.salesforce_client.SalesforceClient')
        
        # Configure basic behaviors
        mocks['azure'].get_completion = mock.AsyncMock(return_value="test completion")
        mocks['graph'].get_inbox_messages = mock.AsyncMock(return_value=[])
        mocks['salesforce'].create_case = mock.AsyncMock(return_value={"id": "test_case"})
        
        yield mocks
    finally:
        # Cleanup is handled by isolated_mocks fixture
        pass


# Debug and troubleshooting utilities
def debug_mock_state(manager: MockStateManager):
    """Debug current mock state for troubleshooting."""
    stats = manager.get_mock_statistics()
    
    print(f"\n🔍 MOCK STATE DEBUG:")
    print(f"   Registered mocks: {stats['registered_mocks']}")
    print(f"   Active patches: {stats['active_patches']}")
    print(f"   Async mocks: {stats['async_mocks']}")
    print(f"   Active references: {stats['active_references']}")
    
    if stats['mock_targets']:
        print(f"   Mock targets: {', '.join(stats['mock_targets'][:5])}{'...' if len(stats['mock_targets']) > 5 else ''}")


# Export commonly used fixtures and utilities
__all__ = [
    'MockStateManager', 'MockValidationManager',
    'isolated_mocks', 
    'mock_azure_client_isolated', 'mock_graph_api_isolated', 'mock_salesforce_client_isolated',
    'mock_email_processor_isolated', 'mock_monitor_isolated',
    'temporary_mock_state', 'mock_external_services', 'debug_mock_state'
]