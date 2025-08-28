# TEMPLATE: Comprehensive Resource Management for Test Performance

import asyncio
import tempfile
import shutil
import functools
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
import pytest

class ResourceManager:
    """Template for managing test resources and ensuring proper cleanup."""
    
    def __init__(self):
        self.active_resources = []
        self.cleanup_callbacks = []
    
    @asynccontextmanager
    async def managed_temp_directory(self, prefix='test_'):
        """Context manager for temporary directories with guaranteed cleanup."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        temp_path = Path(temp_dir)
        self.active_resources.append(temp_path)
        
        try:
            yield temp_path
        finally:
            # Ensure cleanup even if test fails
            try:
                shutil.rmtree(temp_path, ignore_errors=True)
                self.active_resources.remove(temp_path)
            except Exception as e:
                print(f"Warning: Failed to cleanup {temp_path}: {e}")
    
    @asynccontextmanager
    async def managed_async_client(self, client_class, *args, **kwargs):
        """Context manager for async clients with guaranteed cleanup."""
        client = None
        try:
            client = client_class(*args, **kwargs)
            if hasattr(client, '__aenter__'):
                client = await client.__aenter__()
            self.active_resources.append(client)
            yield client
        finally:
            if client:
                try:
                    if hasattr(client, '__aexit__'):
                        await client.__aexit__(None, None, None)
                    elif hasattr(client, 'close'):
                        if asyncio.iscoroutinefunction(client.close):
                            await client.close()
                        else:
                            client.close()
                    if client in self.active_resources:
                        self.active_resources.remove(client)
                except Exception as e:
                    print(f"Warning: Failed to cleanup client {client}: {e}")
    
    async def cleanup_all(self):
        """Force cleanup of all active resources."""
        errors = []
        for resource in self.active_resources[:]:  # Copy list to avoid modification during iteration
            try:
                if hasattr(resource, '__aexit__'):
                    await resource.__aexit__(None, None, None)
                elif hasattr(resource, 'close'):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()
                elif isinstance(resource, Path) and resource.exists():
                    shutil.rmtree(resource, ignore_errors=True)
            except Exception as e:
                errors.append(f"Cleanup error for {resource}: {e}")
        
        self.active_resources.clear()
        if errors:
            print("Resource cleanup warnings:", errors)

@pytest.fixture
async def resource_manager():
    """Fixture providing resource management with automatic cleanup."""
    manager = ResourceManager()
    yield manager
    await manager.cleanup_all()

# Decorator for automatic resource cleanup
def with_resource_cleanup(test_func):
    """Decorator to ensure resource cleanup after test execution."""
    @functools.wraps(test_func)
    async def wrapper(*args, **kwargs):
        manager = ResourceManager()
        try:
            # Inject resource manager into test
            if 'resource_manager' in test_func.__code__.co_varnames:
                kwargs['resource_manager'] = manager
            return await test_func(*args, **kwargs)
        finally:
            await manager.cleanup_all()
    
    return wrapper