"""
Async resource isolation and cleanup for test execution.

This module provides comprehensive async resource management to prevent connection leaks,
hanging tasks, and event loop conflicts between tests.
"""
import pytest
import asyncio
import weakref
import threading
import time
from typing import Set, List, Optional, Any, Callable, Dict, Coroutine
from contextlib import asynccontextmanager
from unittest import mock
import logging


class AsyncResourceManager:
    """Manages async resources to prevent leakage between tests."""
    
    def __init__(self):
        self.active_clients: Set[Any] = set()
        self.active_tasks: List[asyncio.Task] = []
        self.event_loops: List[asyncio.AbstractEventLoop] = []
        self.cleanup_callbacks: List[Callable] = []
        self.connection_pools: Set[Any] = set()
        self.weak_references: List[weakref.ref] = []
        self.resource_stats: Dict[str, int] = {}
        self.cleanup_timeout: float = 5.0
        self.lock = threading.Lock()
    
    def register_client(self, client: Any, client_type: str = "unknown"):
        """Register an async client for cleanup tracking."""
        with self.lock:
            self.active_clients.add(client)
            self.resource_stats[client_type] = self.resource_stats.get(client_type, 0) + 1
        
        # Use weak reference to avoid keeping objects alive
        def cleanup_callback():
            with self.lock:
                if client in self.active_clients:
                    self.active_clients.remove(client)
                if client_type in self.resource_stats:
                    self.resource_stats[client_type] = max(0, self.resource_stats[client_type] - 1)
        
        try:
            ref = weakref.finalize(client, cleanup_callback)
            self.weak_references.append(ref)
        except TypeError:
            # Object doesn't support weak references
            pass
    
    def register_task(self, task: asyncio.Task, task_name: str = "unknown"):
        """Register a task for cleanup."""
        if not task.done():
            with self.lock:
                self.active_tasks.append(task)
                task_type = f"task_{task_name}"
                self.resource_stats[task_type] = self.resource_stats.get(task_type, 0) + 1
    
    def register_connection_pool(self, pool: Any, pool_type: str = "connection_pool"):
        """Register a connection pool for cleanup."""
        with self.lock:
            self.connection_pools.add(pool)
            self.resource_stats[pool_type] = self.resource_stats.get(pool_type, 0) + 1
    
    def register_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Register an event loop for tracking."""
        with self.lock:
            self.event_loops.append(loop)
            self.resource_stats["event_loops"] = len(self.event_loops)
    
    def register_cleanup_callback(self, callback: Callable, callback_name: str = "custom"):
        """Register a custom cleanup callback."""
        with self.lock:
            self.cleanup_callbacks.append(callback)
            callback_type = f"callback_{callback_name}"
            self.resource_stats[callback_type] = self.resource_stats.get(callback_type, 0) + 1
    
    async def cleanup_active_tasks(self):
        """Clean up active async tasks."""
        cleanup_errors = []
        tasks_to_cancel = []
        
        with self.lock:
            tasks_to_cancel = [task for task in self.active_tasks if not task.done()]
        
        if not tasks_to_cancel:
            return cleanup_errors
        
        # Cancel all active tasks
        for task in tasks_to_cancel:
            try:
                task.cancel()
            except Exception as e:
                cleanup_errors.append(f"Task cancel error: {e}")
        
        # Wait for tasks to complete or timeout
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=self.cleanup_timeout
                )
            except asyncio.TimeoutError:
                cleanup_errors.append(f"Task cleanup timeout after {self.cleanup_timeout}s")
            except Exception as e:
                cleanup_errors.append(f"Task cleanup error: {e}")
        
        with self.lock:
            self.active_tasks.clear()
        
        return cleanup_errors
    
    async def cleanup_active_clients(self):
        """Clean up active async clients."""
        cleanup_errors = []
        clients_to_close = []
        
        with self.lock:
            clients_to_close = list(self.active_clients)
        
        for client in clients_to_close:
            try:
                # Try various close methods
                if hasattr(client, 'aclose'):
                    await asyncio.wait_for(client.aclose(), timeout=2.0)
                elif hasattr(client, 'close'):
                    close_result = client.close()
                    if asyncio.iscoroutine(close_result):
                        await asyncio.wait_for(close_result, timeout=2.0)
                elif hasattr(client, 'disconnect'):
                    disconnect_result = client.disconnect()
                    if asyncio.iscoroutine(disconnect_result):
                        await asyncio.wait_for(disconnect_result, timeout=2.0)
                elif hasattr(client, '__aexit__'):
                    await asyncio.wait_for(client.__aexit__(None, None, None), timeout=2.0)
            except asyncio.TimeoutError:
                cleanup_errors.append(f"Client close timeout: {type(client).__name__}")
            except Exception as e:
                cleanup_errors.append(f"Client cleanup error: {e}")
        
        with self.lock:
            self.active_clients.clear()
        
        return cleanup_errors
    
    async def cleanup_connection_pools(self):
        """Clean up connection pools."""
        cleanup_errors = []
        pools_to_close = []
        
        with self.lock:
            pools_to_close = list(self.connection_pools)
        
        for pool in pools_to_close:
            try:
                if hasattr(pool, 'close'):
                    close_result = pool.close()
                    if asyncio.iscoroutine(close_result):
                        await asyncio.wait_for(close_result, timeout=3.0)
                elif hasattr(pool, 'disconnect'):
                    disconnect_result = pool.disconnect()
                    if asyncio.iscoroutine(disconnect_result):
                        await asyncio.wait_for(disconnect_result, timeout=3.0)
                elif hasattr(pool, 'terminate'):
                    terminate_result = pool.terminate()
                    if asyncio.iscoroutine(terminate_result):
                        await asyncio.wait_for(terminate_result, timeout=3.0)
            except asyncio.TimeoutError:
                cleanup_errors.append(f"Pool close timeout: {type(pool).__name__}")
            except Exception as e:
                cleanup_errors.append(f"Pool cleanup error: {e}")
        
        with self.lock:
            self.connection_pools.clear()
        
        return cleanup_errors
    
    async def run_cleanup_callbacks(self):
        """Run custom cleanup callbacks."""
        cleanup_errors = []
        callbacks_to_run = []
        
        with self.lock:
            callbacks_to_run = list(self.cleanup_callbacks)
        
        for callback in callbacks_to_run:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=2.0)
            except asyncio.TimeoutError:
                cleanup_errors.append(f"Callback timeout: {callback.__name__ if hasattr(callback, '__name__') else 'unknown'}")
            except Exception as e:
                cleanup_errors.append(f"Callback cleanup error: {e}")
        
        with self.lock:
            self.cleanup_callbacks.clear()
        
        return cleanup_errors
    
    async def cleanup_async_resources(self):
        """Clean up all async resources."""
        all_cleanup_errors = []
        
        # Clean up in order: tasks, clients, pools, callbacks
        all_cleanup_errors.extend(await self.cleanup_active_tasks())
        all_cleanup_errors.extend(await self.cleanup_active_clients())
        all_cleanup_errors.extend(await self.cleanup_connection_pools())
        all_cleanup_errors.extend(await self.run_cleanup_callbacks())
        
        # Clear resource statistics
        with self.lock:
            self.resource_stats.clear()
            self.weak_references.clear()
            # Keep event_loops for proper lifecycle management
        
        # Log cleanup errors for debugging
        if all_cleanup_errors:
            logger = logging.getLogger(__name__)
            for error in all_cleanup_errors:
                logger.warning(f"Async cleanup error: {error}")
        
        return all_cleanup_errors
    
    def get_resource_statistics(self) -> Dict[str, Any]:
        """Get statistics about current async resource usage."""
        with self.lock:
            active_refs = sum(1 for ref in self.weak_references if ref() is not None)
            
            return {
                'active_clients': len(self.active_clients),
                'active_tasks': len([t for t in self.active_tasks if not t.done()]),
                'connection_pools': len(self.connection_pools),
                'cleanup_callbacks': len(self.cleanup_callbacks),
                'event_loops': len(self.event_loops),
                'active_references': active_refs,
                'resource_breakdown': self.resource_stats.copy(),
                'cleanup_timeout': self.cleanup_timeout
            }


@pytest.fixture(scope="function")
def async_resource_manager():
    """Provide async resource management for each test."""
    manager = AsyncResourceManager()
    
    try:
        yield manager
    finally:
        # Run cleanup in appropriate event loop context
        try:
            loop = asyncio.get_running_loop()
            # If we have a running loop, create a task
            cleanup_task = asyncio.create_task(manager.cleanup_async_resources())
            # The task will be awaited by the test framework
        except RuntimeError:
            # No running loop, try to get or create one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Loop is running but not current, skip cleanup
                    pass
                else:
                    loop.run_until_complete(manager.cleanup_async_resources())
            except RuntimeError:
                # Create new event loop for cleanup
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(manager.cleanup_async_resources())
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)


@pytest.fixture(scope="function")
def isolated_event_loop(async_resource_manager):
    """Provide an isolated event loop for each test."""
    # Store current loop if any
    current_loop = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    
    # Create new isolated loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async_resource_manager.register_event_loop(loop)
    
    try:
        yield loop
    finally:
        # Clean up loop
        try:
            # Cancel all tasks in the loop
            pending_tasks = asyncio.all_tasks(loop)
            for task in pending_tasks:
                task.cancel()
            
            # Wait for tasks to complete with timeout
            if pending_tasks:
                loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*pending_tasks, return_exceptions=True),
                        timeout=3.0
                    )
                )
        except (asyncio.TimeoutError, RuntimeError):
            pass  # Ignore cleanup timeouts
        finally:
            # Close the loop
            try:
                loop.close()
            except RuntimeError:
                pass
            
            # Restore previous loop if any
            if current_loop:
                try:
                    asyncio.set_event_loop(current_loop)
                except RuntimeError:
                    pass
            else:
                asyncio.set_event_loop(None)


@pytest.fixture(scope="function")
def async_timeout_manager():
    """Provide timeout management for async operations."""
    default_timeout = 30.0
    operation_timeouts = {
        'client_connect': 10.0,
        'client_disconnect': 5.0,
        'api_call': 15.0,
        'cleanup': 5.0
    }
    
    class TimeoutManager:
        def get_timeout(self, operation: str) -> float:
            return operation_timeouts.get(operation, default_timeout)
        
        def set_timeout(self, operation: str, timeout: float):
            operation_timeouts[operation] = timeout
        
        async def with_timeout(self, coro: Coroutine, operation: str = 'default'):
            timeout = self.get_timeout(operation)
            return await asyncio.wait_for(coro, timeout=timeout)
    
    return TimeoutManager()


@asynccontextmanager
async def isolated_async_client(client_class, *args, async_resource_manager=None, **kwargs):
    """Context manager for isolated async client usage."""
    client = None
    client_type = client_class.__name__ if hasattr(client_class, '__name__') else "unknown_client"
    
    try:
        # Create and initialize client
        client = client_class(*args, **kwargs)
        
        # Register with resource manager if provided
        if async_resource_manager:
            async_resource_manager.register_client(client, client_type)
        
        # Initialize client connection if needed
        if hasattr(client, 'connect'):
            await asyncio.wait_for(client.connect(), timeout=10.0)
        elif hasattr(client, '__aenter__'):
            await asyncio.wait_for(client.__aenter__(), timeout=10.0)
        elif hasattr(client, 'initialize'):
            init_result = client.initialize()
            if asyncio.iscoroutine(init_result):
                await asyncio.wait_for(init_result, timeout=10.0)
        
        yield client
        
    finally:
        if client is not None:
            try:
                # Clean up client connection
                if hasattr(client, 'aclose'):
                    await asyncio.wait_for(client.aclose(), timeout=5.0)
                elif hasattr(client, 'close'):
                    close_result = client.close()
                    if asyncio.iscoroutine(close_result):
                        await asyncio.wait_for(close_result, timeout=5.0)
                elif hasattr(client, 'disconnect'):
                    disconnect_result = client.disconnect()
                    if asyncio.iscoroutine(disconnect_result):
                        await asyncio.wait_for(disconnect_result, timeout=5.0)
                elif hasattr(client, '__aexit__'):
                    await asyncio.wait_for(client.__aexit__(None, None, None), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                pass  # Ignore cleanup errors in isolated context


@asynccontextmanager
async def managed_async_task(coro, task_name: str = "managed_task", async_resource_manager=None):
    """Context manager for managed async task execution."""
    task = None
    
    try:
        # Create and start task
        task = asyncio.create_task(coro, name=task_name)
        
        # Register with resource manager if provided
        if async_resource_manager:
            async_resource_manager.register_task(task, task_name)
        
        yield task
        
        # Wait for task completion
        await task
        
    except asyncio.CancelledError:
        # Task was cancelled, which is expected in cleanup
        pass
    finally:
        if task and not task.done():
            try:
                task.cancel()
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass  # Expected during cleanup


class AsyncResourceValidator:
    """Validates async resource isolation and cleanup."""
    
    def __init__(self):
        self.initial_tasks: Set[asyncio.Task] = set()
        self.initial_loop_state: Dict[str, Any] = {}
    
    def capture_initial_state(self):
        """Capture initial async resource state."""
        try:
            loop = asyncio.get_running_loop()
            self.initial_tasks = set(asyncio.all_tasks(loop))
            self.initial_loop_state = {
                'is_running': loop.is_running(),
                'is_closed': loop.is_closed(),
                'task_count': len(self.initial_tasks)
            }
        except RuntimeError:
            # No running loop
            self.initial_tasks = set()
            self.initial_loop_state = {'task_count': 0}
    
    def validate_cleanup(self) -> Dict[str, Any]:
        """Validate async resource cleanup after test."""
        validation_results = {
            'cleanup_success': True,
            'issues': [],
            'statistics': {}
        }
        
        try:
            loop = asyncio.get_running_loop()
            current_tasks = set(asyncio.all_tasks(loop))
            
            # Check for task leaks
            new_tasks = current_tasks - self.initial_tasks
            if new_tasks:
                validation_results['cleanup_success'] = False
                validation_results['issues'].append(f"Task leak detected: {len(new_tasks)} new tasks")
            
            validation_results['statistics'] = {
                'initial_tasks': len(self.initial_tasks),
                'current_tasks': len(current_tasks),
                'new_tasks': len(new_tasks),
                'loop_running': loop.is_running(),
                'loop_closed': loop.is_closed()
            }
            
        except RuntimeError:
            # No running loop - this might be expected after cleanup
            validation_results['statistics'] = {
                'no_running_loop': True
            }
        
        return validation_results


@pytest.fixture(scope="function")
def async_resource_validator():
    """Provide async resource validation."""
    validator = AsyncResourceValidator()
    validator.capture_initial_state()
    
    yield validator
    
    # Validate at end of test
    results = validator.validate_cleanup()
    if not results['cleanup_success']:
        print(f"\n⚠️  Async resource issues detected:")
        for issue in results['issues']:
            print(f"   {issue}")


# Debug and troubleshooting utilities
def debug_async_state(manager: AsyncResourceManager):
    """Debug current async resource state."""
    stats = manager.get_resource_statistics()
    
    print(f"\n🔍 ASYNC RESOURCE STATE DEBUG:")
    print(f"   Active clients: {stats['active_clients']}")
    print(f"   Active tasks: {stats['active_tasks']}")
    print(f"   Connection pools: {stats['connection_pools']}")
    print(f"   Cleanup callbacks: {stats['cleanup_callbacks']}")
    print(f"   Event loops: {stats['event_loops']}")
    print(f"   Active references: {stats['active_references']}")
    print(f"   Cleanup timeout: {stats['cleanup_timeout']}s")
    
    if stats['resource_breakdown']:
        print(f"   Resource breakdown:")
        for resource_type, count in stats['resource_breakdown'].items():
            print(f"     {resource_type}: {count}")


# Export commonly used fixtures and utilities
__all__ = [
    'AsyncResourceManager', 'AsyncResourceValidator',
    'async_resource_manager', 'isolated_event_loop', 'async_timeout_manager', 
    'async_resource_validator',
    'isolated_async_client', 'managed_async_task',
    'debug_async_state'
]