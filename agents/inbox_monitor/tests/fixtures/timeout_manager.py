# TEMPLATE: Optimized Timeout Configuration for Tests

import asyncio
import functools
from contextlib import asynccontextmanager
from typing import Optional

class TestTimeoutManager:
    """Template for managing timeouts in test environments."""
    
    # Test-optimized timeout configurations
    TIMEOUT_CONFIGS = {
        'fast_test': 5.0,      # 5 seconds max for fast tests
        'medium_test': 30.0,   # 30 seconds max for medium tests
        'slow_test': 300.0,    # 5 minutes max for slow tests
        'http_request': 2.0,   # 2 seconds for HTTP requests in tests
        'database_query': 5.0, # 5 seconds for database operations
        'service_call': 3.0    # 3 seconds for service calls
    }
    
    @classmethod
    @asynccontextmanager
    async def timeout_context(cls, timeout_type: str, custom_timeout: Optional[float] = None):
        """Context manager for timeout enforcement."""
        timeout = custom_timeout or cls.TIMEOUT_CONFIGS.get(timeout_type, 5.0)
        
        try:
            async with asyncio.timeout(timeout):
                yield
        except asyncio.TimeoutError:
            raise AssertionError(f"Test timed out after {timeout}s (type: {timeout_type})")
    
    @classmethod
    def timeout_decorator(cls, timeout_type: str, custom_timeout: Optional[float] = None):
        """Decorator for timeout enforcement."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                async with cls.timeout_context(timeout_type, custom_timeout):
                    return await func(*args, **kwargs)
            return wrapper
        return decorator

# Usage examples:
@TestTimeoutManager.timeout_decorator('fast_test')
async def test_fast_operation():
    """Test with 5-second timeout."""
    pass

async def test_with_context_timeout():
    """Test using context manager for timeout."""
    async with TestTimeoutManager.timeout_context('medium_test'):
        # Test implementation
        pass