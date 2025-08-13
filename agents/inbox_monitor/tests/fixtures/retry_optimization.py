# TEMPLATE: Optimized Retry Logic for Test Environments

import asyncio
import functools
from typing import Optional

class TestOptimizedRetry:
    """Template for retry logic optimized for test performance."""
    
    @staticmethod
    def get_test_retry_config():
        """Get retry configuration optimized for test environments."""
        return {
            'max_attempts': 2,  # Reduced from production values
            'delay_seconds': 0.01,  # Minimal delay for tests
            'backoff_factor': 1.1,  # Minimal backoff
            'timeout_seconds': 5.0  # Quick timeout for tests
        }
    
    @staticmethod
    async def fast_retry_operation(operation, operation_name: str, **kwargs):
        """Retry operation with test-optimized settings."""
        config = TestOptimizedRetry.get_test_retry_config()
        
        max_attempts = kwargs.get('max_attempts', config['max_attempts'])
        delay_seconds = kwargs.get('delay_seconds', config['delay_seconds'])
        
        for attempt in range(max_attempts):
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    result = operation()
                return True, result, None
            except Exception as e:
                if attempt == max_attempts - 1:
                    return False, None, str(e)
                
                # Minimal delay for tests
                await asyncio.sleep(delay_seconds)
        
        return False, None, "Max attempts exceeded"

# Test-specific retry decorator
def test_retry(max_attempts=2, delay_seconds=0.01):
    """Decorator for retry logic optimized for testing."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise e
                    await asyncio.sleep(delay_seconds)
        return wrapper
    return decorator