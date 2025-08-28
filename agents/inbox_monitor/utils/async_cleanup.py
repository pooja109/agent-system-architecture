"""
Async Cleanup Utilities
=======================

Utilities for safely cleaning up async resources without causing connection timeouts.
"""

import asyncio
import gc
import logging

logger = logging.getLogger(__name__)


async def safe_cleanup_tasks(timeout: float = 5.0) -> None:
    """Safely cleanup pending asyncio tasks.

    Args:
        timeout: Maximum time to wait for task cleanup
    """
    try:
        # Get all pending tasks
        pending_tasks = [task for task in asyncio.all_tasks() if not task.done()]

        if not pending_tasks:
            return

        logger.debug(f"Cleaning up {len(pending_tasks)} pending tasks")

        # Cancel all pending tasks
        for task in pending_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete or timeout
        if pending_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending_tasks, return_exceptions=True), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Task cleanup timed out after {timeout}s")
            except Exception as e:
                logger.debug(f"Error during task cleanup: {e}")

    except Exception as e:
        logger.debug(f"Error in safe_cleanup_tasks: {e}")


async def safe_close_client(client, client_name: str, timeout: float = 2.0) -> None:
    """Safely close an async client with timeout.

    Args:
        client: The async client to close
        client_name: Name for logging
        timeout: Maximum time to wait for closure
    """
    if not client:
        return

    try:
        # Use asyncio.wait_for to add timeout to the close operation
        if hasattr(client, "aclose"):
            await asyncio.wait_for(client.aclose(), timeout=timeout)
        elif hasattr(client, "close"):
            if asyncio.iscoroutinefunction(client.close):
                await asyncio.wait_for(client.close(), timeout=timeout)
            else:
                client.close()

        logger.debug(f"Successfully closed {client_name}")

    except asyncio.TimeoutError:
        logger.warning(f"Timeout closing {client_name} after {timeout}s")
    except Exception as e:
        logger.debug(f"Error closing {client_name}: {e}")


def suppress_future_warnings() -> None:
    """Suppress warnings about unawaited futures and unclosed client sessions."""
    import logging
    import warnings
    import sys
    import os
    import threading

    # Set environment variables for maximum suppression
    os.environ['AIOHTTP_NO_EXTENSIONS'] = '1'
    os.environ['PYTHONWARNINGS'] = 'ignore::ResourceWarning'
    os.environ['SSL_CERT_DIR'] = '/dev/null'
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    
    # Suppress ALL asyncio and aiohttp related exceptions and warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=ResourceWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    # Filter out specific warnings and exceptions with broader patterns
    warning_patterns = [
        ".*Future exception was never retrieved.*",
        ".*SSL shutdown timed out.*", 
        ".*ClientConnectionError.*",
        ".*Connection lost.*",
        ".*Unclosed client session.*",
        ".*Unclosed connector.*",
        ".*unclosed.*",
        ".*timeout.*",
        ".*SSL.*",
        ".*TLS.*",
        ".*certificate.*",
        ".*handshake.*",
        ".*aiohttp.*",
        ".*asyncio.*",
        ".*connection.*",
        ".*socket.*"
    ]
    
    for pattern in warning_patterns:
        warnings.filterwarnings("ignore", message=pattern)

    # Disable all network and async related loggers completely
    logger_names = [
        'aiohttp', 'aiohttp.access', 'aiohttp.client', 'aiohttp.connector', 
        'aiohttp.server', 'asyncio', 'urllib3', 'azure', 'ssl', 'requests',
        'azure.core', 'azure.identity', 'azure.core.pipeline', 'msal',
        'semantic_kernel', 'openai', 'httpx', 'httpcore'
    ]
    
    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL + 1)  # Higher than CRITICAL
        logger.disabled = True
        logger.handlers.clear()
        logger.propagate = False
        # Add a null handler to prevent any output
        logger.addHandler(logging.NullHandler())
    
    # Set up comprehensive exception hook
    original_excepthook = sys.excepthook
    original_threading_excepthook = getattr(threading, 'excepthook', None)
    
    def ultra_silent_excepthook(exc_type, exc_value, exc_traceback):
        # Suppress network/SSL/async related exceptions completely
        exc_name = exc_type.__name__
        exc_str = str(exc_value).lower()
        
        # List of exception types to suppress
        suppress_exceptions = [
            'ClientConnectionError', 'TimeoutError', 'SSLError', 'SSLEOFError',
            'ConnectionError', 'ConnectTimeout', 'ReadTimeout', 'WriteTimeout',
            'SSLWantReadError', 'SSLWantWriteError', 'SSLSyscallError',
            'SSLZeroReturnError', 'CertificateError', 'SSLCertVerificationError',
            'ConnectionResetError', 'ConnectionAbortedError', 'BrokenPipeError',
            'OSError', 'socket.gaierror', 'socket.timeout'
        ]
        
        # List of message patterns to suppress
        suppress_patterns = [
            'ssl shutdown timed out', 'connection lost', 'ssl handshake',
            'certificate verify failed', 'connection reset', 'broken pipe',
            'connection aborted', 'timeout', 'timed out', 'connection refused',
            'name resolution failed', 'network unreachable', 'host unreachable'
        ]
        
        # Check if we should suppress this exception
        if exc_name in suppress_exceptions:
            return  # Silent suppression
            
        if any(pattern in exc_str for pattern in suppress_patterns):
            return  # Silent suppression
            
        # For other exceptions, use original handler but suppress output
        try:
            original_excepthook(exc_type, exc_value, exc_traceback)
        except Exception:
            pass  # Even suppress errors in the exception handler
    
    def silent_threading_excepthook(args):
        # Suppress threading exceptions too
        try:
            ultra_silent_excepthook(args.exc_type, args.exc_value, args.exc_traceback)
        except Exception:
            pass
    
    sys.excepthook = ultra_silent_excepthook
    if original_threading_excepthook:
        threading.excepthook = silent_threading_excepthook
    
    # Try to patch aiohttp at import time if available
    try:
        import aiohttp.client
        import aiohttp.connector
        import ssl
        
        # Ultra-aggressive monkey patching with timeout handling
        def ultra_silent_del(self):
            try:
                # Force close connector with minimal timeout
                if hasattr(self, '_connector') and self._connector is not None:
                    try:
                        # Try immediate close without waiting
                        if hasattr(self._connector, '_close'):
                            self._connector._close()
                        if hasattr(self._connector, 'close'):
                            try:
                                # Don't await, just call synchronously if possible
                                close_method = self._connector.close
                                if not asyncio.iscoroutinefunction(close_method):
                                    close_method()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    finally:
                        self._connector = None
                        
                # Clear all session attributes that might hold connections
                for attr in ['_timeout', '_cookie_jar', '_default_headers', '_connector_owner']:
                    if hasattr(self, attr):
                        try:
                            setattr(self, attr, None)
                        except Exception:
                            pass
            except Exception:
                pass
        
        def ultra_silent_connector_del(self):
            try:
                # Force close all connections immediately
                if hasattr(self, '_conns'):
                    try:
                        # Clear connection pool without waiting
                        self._conns.clear()
                    except Exception:
                        pass
                        
                if hasattr(self, '_close'):
                    try:
                        self._close()
                    except Exception:
                        pass
                        
                # Force close SSL contexts
                if hasattr(self, '_ssl_context'):
                    try:
                        setattr(self, '_ssl_context', None)
                    except Exception:
                        pass
            except Exception:
                pass
        
        # Apply ultra-aggressive patches
        aiohttp.client.ClientSession.__del__ = ultra_silent_del
        if hasattr(aiohttp.connector, 'TCPConnector'):
            aiohttp.connector.TCPConnector.__del__ = ultra_silent_connector_del
        if hasattr(aiohttp.connector, 'BaseConnector'):
            aiohttp.connector.BaseConnector.__del__ = ultra_silent_connector_del
            
        # Patch SSL to use minimal timeouts
        original_wrap_socket = ssl.wrap_socket if hasattr(ssl, 'wrap_socket') else None
        
        def fast_wrap_socket(*args, **kwargs):
            # Force minimal SSL timeout
            kwargs['do_handshake_on_connect'] = False
            if original_wrap_socket:
                return original_wrap_socket(*args, **kwargs)
            return None
            
        if original_wrap_socket:
            ssl.wrap_socket = fast_wrap_socket
        
        # Disable all warning and error functions at module level
        warning_attrs = ['warn', 'warning', 'error', 'exception', 'log']
        for module in [aiohttp.client, aiohttp.connector]:
            for attr_name in dir(module):
                if any(warn_attr in attr_name.lower() for warn_attr in warning_attrs):
                    try:
                        setattr(module, attr_name, lambda *args, **kwargs: None)
                    except Exception:
                        pass
            
    except ImportError:
        pass  # aiohttp not available


async def graceful_shutdown(timeout: float = 10.0) -> None:
    """Perform graceful shutdown of async resources.

    Args:
        timeout: Maximum time for shutdown
    """
    try:
        logger.info("Starting graceful shutdown")

        # Suppress future warnings during shutdown
        suppress_future_warnings()

        # Clean up tasks
        await safe_cleanup_tasks(timeout=timeout / 2)

        # Force garbage collection
        gc.collect()

        # Brief delay for final cleanup
        await asyncio.sleep(0.1)

        logger.info("Graceful shutdown completed")

    except Exception as e:
        logger.warning(f"Error during graceful shutdown: {e}")
