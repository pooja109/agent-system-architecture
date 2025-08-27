"""
Async test utilities and patterns for handling coroutines in tests.
Works with existing source code async patterns without modification.
"""
import asyncio
import inspect
from typing import Any, Callable, Coroutine, Union
from unittest.mock import AsyncMock, MagicMock
import pytest


class AsyncTestHelper:
    """
    Utility class for handling async/sync boundaries in tests.
    """
    
    @staticmethod
    def is_coroutine_function(obj: Any) -> bool:
        """Check if an object is a coroutine function."""
        return inspect.iscoroutinefunction(obj)
    
    @staticmethod  
    def is_coroutine(obj: Any) -> bool:
        """Check if an object is a coroutine."""
        return inspect.iscoroutine(obj)
    
    @staticmethod
    async def safe_await(obj: Any) -> Any:
        """
        Safely await an object if it's a coroutine, otherwise return it directly.
        
        This handles the common pattern where methods may or may not be async
        depending on implementation.
        """
        if AsyncTestHelper.is_coroutine(obj):
            return await obj
        return obj
    
    @staticmethod
    def run_sync(coro: Coroutine) -> Any:
        """
        Run a coroutine synchronously in tests.
        Handles event loop management properly.
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create new event loop for nested async calls
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(coro)


class AsyncMockManager:
    """
    Manager for creating async-compatible mocks for source code methods.
    """
    
    @staticmethod
    def create_async_mock(return_value: Any = None, side_effect: Any = None) -> AsyncMock:
        """Create an AsyncMock with proper configuration."""
        mock = AsyncMock()
        if return_value is not None:
            mock.return_value = return_value
        if side_effect is not None:
            mock.side_effect = side_effect
        return mock
    
    @staticmethod
    def create_hybrid_mock(sync_return: Any = None, async_return: Any = None) -> MagicMock:
        """
        Create a mock that can handle both sync and async calls.
        Useful for methods that may be called either way in tests.
        """
        mock = MagicMock()
        
        if async_return is not None:
            async_method = AsyncMock(return_value=async_return)
            mock.return_value = async_method
        elif sync_return is not None:
            mock.return_value = sync_return
            
        return mock


@pytest.fixture
def async_test_helper():
    """Fixture providing async test utilities."""
    return AsyncTestHelper()


@pytest.fixture
def async_mock_manager():
    """Fixture providing async mock management."""
    return AsyncMockManager()


@pytest.fixture
async def async_scenario_processing_record():
    """
    Async fixture for ScenarioProcessingRecord that handles the coroutine issue.
    
    This provides a properly awaited instance for tests that need it.
    """
    # Mock the async factory method properly
    from database.scenario_tracking_models import ScenarioProcessingRecord
    
    # Create a mock that simulates the async factory behavior
    mock_record = MagicMock()
    mock_record.scenario_id = "test-scenario-123"
    mock_record.processing_status = "completed"
    mock_record.created_at = "2024-01-15T10:30:00Z"
    
    return mock_record


@pytest.fixture(scope="function")
def async_event_loop():
    """
    Fixture providing a clean event loop for async tests.
    Ensures proper cleanup to prevent resource leaks.
    Uses function scope to avoid conflicts with pytest-asyncio.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    policy.set_event_loop(loop)
    yield loop
    
    # Comprehensive cleanup
    try:
        # Cancel all remaining tasks
        tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if tasks:
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        
        # Run any pending callbacks
        loop.run_until_complete(asyncio.sleep(0))
        
        # Close the loop
        loop.close()
    except Exception:
        # Force close if cleanup fails
        try:
            loop.close()
        except:
            pass


async def await_all_coroutines(obj: Any) -> Any:
    """
    Recursively await all coroutines in a data structure.
    Handles the case where factory methods return nested coroutines.
    """
    if inspect.iscoroutine(obj):
        return await obj
    elif isinstance(obj, (list, tuple)):
        results = []
        for item in obj:
            results.append(await await_all_coroutines(item))
        return type(obj)(results)
    elif isinstance(obj, dict):
        results = {}
        for key, value in obj.items():
            results[key] = await await_all_coroutines(value)
        return results
    else:
        return obj


@pytest.fixture
def mock_async_from_processing_results():
    """
    Mock fixture for the async from_processing_results method.
    
    Provides a properly configured AsyncMock that returns realistic test data
    instead of a coroutine that needs to be awaited.
    """
    async def mock_factory(email_data=None, processing_result=None, **kwargs):
        """Mock implementation that returns test data."""
        await asyncio.sleep(0.01)  # Simulate async processing
        
        # Create mock record data based on input
        mock_data = {
            "processing_id": "test-processing-123",
            "email_id": getattr(email_data, 'id', 'test-email-123'),
            "sender_email": "test@example.com",
            "scenario_type": "scenario_5",
            "process_success": True,
            "received_datetime": "2024-01-15T10:30:00Z",
            "processed_at": "2024-01-15T10:30:00Z"
        }
        
        # Create a MagicMock that acts like a ScenarioProcessingRecord
        from unittest.mock import MagicMock
        mock_record = MagicMock()
        for key, value in mock_data.items():
            setattr(mock_record, key, value)
        
        return mock_record
    
    return AsyncMock(side_effect=mock_factory)


@pytest.fixture
async def mock_async_scenario_builder():
    """
    Async mock for ScenarioProcessingRecordBuilder.build_async.
    
    This handles the async builder pattern used in the source code.
    """
    async def mock_build_async(processing_result=None, email_data=None, **kwargs):
        """Mock the async builder method."""
        await asyncio.sleep(0.01)  # Simulate async processing
        
        return {
            "processing_id": "test-processing-456",
            "email_id": getattr(email_data, 'id', 'test-email-456'),
            "sender_email": getattr(email_data, 'sender', {}).get('email', 'test@example.com'),
            "scenario_type": "scenario_6",
            "process_success": True,
            "received_datetime": "2024-01-15T10:30:00Z",
            "processed_at": "2024-01-15T10:30:00Z",
            "scenario_result": kwargs.get('scenario_result', {'classification': 'positive'})
        }
    
    return AsyncMock(side_effect=mock_build_async)