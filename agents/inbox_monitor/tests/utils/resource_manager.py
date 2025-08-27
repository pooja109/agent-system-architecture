"""
Resource management utilities for test cleanup and optimization.
"""
import asyncio
import gc
import os
import tempfile
import threading
from pathlib import Path
from typing import List, Set, Any
from unittest.mock import patch
import pytest


class ResourceManager:
    """
    Manage test resources and cleanup to prevent leaks.
    """
    
    def __init__(self):
        self.temp_files: Set[Path] = set()
        self.temp_dirs: Set[Path] = set()
        self.open_files: List[Any] = []
        self.active_patches: List[Any] = []
        self.background_tasks: Set[asyncio.Task] = set()
    
    def register_temp_file(self, file_path: Path):
        """Register a temporary file for cleanup."""
        self.temp_files.add(file_path)
    
    def register_temp_dir(self, dir_path: Path):
        """Register a temporary directory for cleanup."""
        self.temp_dirs.add(dir_path)
    
    def register_open_file(self, file_handle: Any):
        """Register an open file handle for cleanup."""
        self.open_files.append(file_handle)
    
    def register_patch(self, patch_obj: Any):
        """Register a mock patch for cleanup."""
        self.active_patches.append(patch_obj)
    
    def register_background_task(self, task: asyncio.Task):
        """Register an async background task for cleanup."""
        self.background_tasks.add(task)
    
    def cleanup_all(self):
        """Clean up all registered resources."""
        # Clean up patches
        for patch_obj in self.active_patches:
            try:
                if hasattr(patch_obj, 'stop'):
                    patch_obj.stop()
            except Exception:
                pass
        self.active_patches.clear()
        
        # Close open files
        for file_handle in self.open_files:
            try:
                if hasattr(file_handle, 'close'):
                    file_handle.close()
            except Exception:
                pass
        self.open_files.clear()
        
        # Clean up background tasks
        for task in self.background_tasks:
            try:
                if not task.done():
                    task.cancel()
            except Exception:
                pass
        self.background_tasks.clear()
        
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
        self.temp_files.clear()
        
        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            try:
                if temp_dir.exists():
                    import shutil
                    shutil.rmtree(temp_dir)
            except Exception:
                pass
        self.temp_dirs.clear()
        
        # Force garbage collection
        gc.collect()


class AsyncResourceManager:
    """
    Specialized resource manager for async operations.
    """
    
    @staticmethod
    async def cleanup_event_loop():
        """Clean up current event loop resources."""
        try:
            # Cancel all pending tasks
            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            if tasks:
                for task in tasks:
                    task.cancel()
                
                # Wait for tasks to complete cancellation
                await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception:
            pass
    
    @staticmethod
    def cleanup_event_loop_sync():
        """Clean up event loop resources synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                # Cancel pending tasks
                tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in tasks:
                    task.cancel()
                
                # Run until tasks are cancelled
                if tasks:
                    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        
        except Exception:
            pass


class OptimizedMockManager:
    """
    Manager for optimized mock objects with caching.
    """
    
    def __init__(self):
        self._mock_cache = {}
        self._response_cache = {}
    
    def get_cached_mock(self, mock_key: str, factory_func):
        """
        Get a cached mock object or create it if not exists.
        
        Args:
            mock_key: Unique key for the mock
            factory_func: Function to create the mock if not cached
            
        Returns:
            Cached or newly created mock object
        """
        if mock_key not in self._mock_cache:
            self._mock_cache[mock_key] = factory_func()
        
        return self._mock_cache[mock_key]
    
    def cache_mock_response(self, response_key: str, response_data: Any):
        """Cache a mock response for reuse."""
        self._response_cache[response_key] = response_data
    
    def get_cached_response(self, response_key: str, default=None):
        """Get a cached mock response."""
        return self._response_cache.get(response_key, default)
    
    def clear_cache(self):
        """Clear all cached mocks and responses."""
        self._mock_cache.clear()
        self._response_cache.clear()


# Global resource manager instances
resource_manager = ResourceManager()
async_resource_manager = AsyncResourceManager()
mock_manager = OptimizedMockManager()


@pytest.fixture(scope="function", autouse=True)
def auto_resource_cleanup():
    """Automatically clean up resources after each test."""
    yield
    resource_manager.cleanup_all()
    async_resource_manager.cleanup_event_loop_sync()


@pytest.fixture
def managed_resources():
    """Fixture providing managed resource utilities."""
    return resource_manager


@pytest.fixture
def async_resources():
    """Fixture providing async resource management."""
    return async_resource_manager


@pytest.fixture  
def optimized_mocks():
    """Fixture providing optimized mock management."""
    return mock_manager