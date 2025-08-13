"""
Logger isolation fixtures for preventing singleton conflicts in tests.

This module provides fixtures and utilities to isolate logger instances between tests,
preventing the singleton conflicts that cause tests to hang for 30+ seconds.
"""
import pytest
import logging
import sys
import threading
from typing import Dict, List, Optional, Any
from unittest import mock
from contextlib import contextmanager


class LoggerIsolationManager:
    """Manages logger isolation for test execution."""
    
    def __init__(self):
        self.original_loggers: Dict[str, logging.Logger] = {}
        self.test_loggers: List[logging.Logger] = []
        self.handler_backups: Dict[str, List] = {}
        self.level_backups: Dict[str, int] = {}
        self.lock = threading.Lock()
    
    def isolate_loggers(self, test_name: str) -> None:
        """Create isolated logger environment for test."""
        with self.lock:
            # Backup existing loggers
            self.original_loggers = dict(logging.Logger.manager.loggerDict)
            
            # Backup root logger state
            root_logger = logging.getLogger()
            self.handler_backups['root'] = root_logger.handlers.copy()
            self.level_backups['root'] = root_logger.level
            
            # Clear existing handlers to prevent conflicts
            root_logger.handlers.clear()
            root_logger.setLevel(logging.WARNING)  # Reduce noise during testing
            
            # Create test-specific logger namespace
            test_logger_name = f"test_{test_name}_{id(self)}"
            test_logger = logging.getLogger(test_logger_name)
            test_logger.setLevel(logging.DEBUG)
            test_logger.propagate = False  # Prevent propagation to root
            
            # Add isolated handler that doesn't interfere with other tests
            handler = logging.StreamHandler()
            handler.setLevel(logging.WARNING)  # Only show warnings/errors during tests
            formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            test_logger.addHandler(handler)
            
            self.test_loggers.append(test_logger)
    
    def cleanup_loggers(self) -> None:
        """Clean up test logger environment."""
        with self.lock:
            # Remove test loggers and their handlers
            for logger in self.test_loggers:
                # Remove all handlers
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
                    handler.close()
            
            # Clear logger manager state
            logging.Logger.manager.loggerDict.clear()
            logging.Logger.manager.loggerDict.update(self.original_loggers)
            
            # Restore root logger state
            root_logger = logging.getLogger()
            root_logger.handlers.clear()
            root_logger.handlers.extend(self.handler_backups.get('root', []))
            root_logger.setLevel(self.level_backups.get('root', logging.WARNING))
            
            # Clear our tracking
            self.test_loggers.clear()
            self.handler_backups.clear()
            self.level_backups.clear()
            self.original_loggers.clear()
    
    def get_isolated_logger(self, name: str) -> logging.Logger:
        """Get an isolated logger for testing."""
        if not self.test_loggers:
            raise RuntimeError("Logger isolation not initialized. Call isolate_loggers() first.")
        
        # Create logger under the test namespace
        test_namespace = self.test_loggers[0].name
        logger_name = f"{test_namespace}.{name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        
        return logger


@pytest.fixture(scope="function")
def logger_isolation():
    """Provide isolated logger environment for each test."""
    manager = LoggerIsolationManager()
    
    # Get test name from pytest current test
    test_name = "unknown"
    if hasattr(pytest, 'current_test_name'):
        test_name = pytest.current_test_name
    elif hasattr(pytest, '_current_test'):
        test_name = pytest._current_test
    
    manager.isolate_loggers(test_name)
    
    try:
        yield manager
    finally:
        manager.cleanup_loggers()


@pytest.fixture(scope="function") 
def isolated_logger(logger_isolation):
    """Provide a clean logger instance for testing."""
    return logger_isolation.get_isolated_logger("test_logger")


@contextmanager
def mock_logger_factory():
    """Mock logger factory to prevent singleton conflicts."""
    original_getLogger = logging.getLogger
    created_loggers = []
    
    def mock_getLogger(name=None):
        """Mock getLogger that creates isolated instances."""
        if name is None:
            name = "root"
        
        # Create a unique logger name to avoid conflicts
        unique_name = f"mock_{name}_{id(mock_getLogger)}"
        logger = logging.Logger(unique_name)
        logger.setLevel(logging.DEBUG)
        created_loggers.append(logger)
        return logger
    
    # Patch logging.getLogger
    with mock.patch('logging.getLogger', side_effect=mock_getLogger):
        try:
            yield created_loggers
        finally:
            # Clean up created loggers
            for logger in created_loggers:
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
                    handler.close()


@pytest.fixture(scope="function")
def mock_logging_system():
    """Mock the entire logging system for tests that don't need real logging."""
    with mock_logger_factory() as loggers:
        yield loggers


class LoggerPerformanceMonitor:
    """Monitor logger performance to detect hangs and slowdowns."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.logger_creation_times: List[float] = []
        self.handler_operation_times: List[float] = []
    
    def start_monitoring(self):
        """Start monitoring logger performance."""
        import time
        self.start_time = time.perf_counter()
    
    def record_logger_creation(self, creation_time: float):
        """Record logger creation time."""
        self.logger_creation_times.append(creation_time)
    
    def record_handler_operation(self, operation_time: float):
        """Record handler operation time."""
        self.handler_operation_times.append(operation_time)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance monitoring report."""
        import time
        total_time = time.perf_counter() - (self.start_time or 0)
        
        return {
            'total_execution_time': total_time,
            'logger_creations': len(self.logger_creation_times),
            'avg_logger_creation_time': sum(self.logger_creation_times) / len(self.logger_creation_times) if self.logger_creation_times else 0,
            'max_logger_creation_time': max(self.logger_creation_times) if self.logger_creation_times else 0,
            'handler_operations': len(self.handler_operation_times),
            'avg_handler_operation_time': sum(self.handler_operation_times) / len(self.handler_operation_times) if self.handler_operation_times else 0,
            'max_handler_operation_time': max(self.handler_operation_times) if self.handler_operation_times else 0
        }


@pytest.fixture(scope="function")
def logger_performance_monitor():
    """Provide logger performance monitoring."""
    monitor = LoggerPerformanceMonitor()
    monitor.start_monitoring()
    return monitor


# Performance assertion helpers for logger tests
def assert_logger_performance_within_limits(performance_report: Dict[str, Any],
                                          max_total_time: float = 5.0,
                                          max_creation_time: float = 0.1,
                                          max_handler_time: float = 0.05):
    """Assert logger performance is within acceptable limits."""
    assert performance_report['total_execution_time'] < max_total_time, \
        f"Logger test execution time {performance_report['total_execution_time']:.2f}s exceeds limit {max_total_time}s"
    
    if performance_report['max_logger_creation_time'] > 0:
        assert performance_report['max_logger_creation_time'] < max_creation_time, \
            f"Logger creation time {performance_report['max_logger_creation_time']:.3f}s exceeds limit {max_creation_time}s"
    
    if performance_report['max_handler_operation_time'] > 0:
        assert performance_report['max_handler_operation_time'] < max_handler_time, \
            f"Handler operation time {performance_report['max_handler_operation_time']:.3f}s exceeds limit {max_handler_time}s"