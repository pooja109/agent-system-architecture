"""
Comprehensive logging isolation for ResponseHandler tests.
Resolves structured logging incompatibility within test-only constraints.
"""
import logging
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import pytest


class MockStructLogger:
    """Mock logger that accepts structured logging calls."""
    
    def __init__(self):
        self.calls = []
        
    def info(self, message, **kwargs):
        self.calls.append(('info', message, kwargs))
        
    def error(self, message, **kwargs):
        self.calls.append(('error', message, kwargs))
        
    def warning(self, message, **kwargs):
        self.calls.append(('warning', message, kwargs))
        
    def debug(self, message, **kwargs):
        self.calls.append(('debug', message, kwargs))


@contextmanager
def isolated_logging():
    """
    Context manager that completely isolates tests from ResponseHandler's logging system.
    
    This resolves the critical audit finding where structured logging calls
    fail within test-only constraints.
    """
    mock_logger = MockStructLogger()
    
    # Patch all logging-related imports and calls that ResponseHandler uses
    patches = [
        # Patch structlog
        patch('structlog.get_logger', return_value=mock_logger),
        
        # Patch the logging mixin initialization
        patch('services.logging.business_logic_logger.BusinessLogicLoggerMixin.__init_logging__'),
        
        # Patch all logger factory functions
        patch('utils.custom_logging.get_logger', return_value=mock_logger),
        patch('utils.custom_logging.get_console_logger', return_value=mock_logger),
        patch('utils.custom_logging.get_structured_logger', return_value=mock_logger),
        
        # Patch logger factory methods if they exist
        patch('utils.custom_logging.logger_factory.get_logger', return_value=mock_logger, create=True),
        patch('utils.custom_logging.logger_factory.get_console_logger', return_value=mock_logger, create=True),
        patch('utils.custom_logging.logger_factory.get_structured_logger', return_value=mock_logger, create=True),
        
        # Patch the service logger mixin properties
        patch('services.logging.service_logger_mixin.ServiceLoggerMixin.logger', mock_logger, create=True),
        patch('services.logging.service_logger_mixin.ServiceLoggerMixin.console_logger', mock_logger, create=True),
        patch('services.logging.service_logger_mixin.ServiceLoggerMixin.diagnostic_logger', mock_logger, create=True),
    ]
    
    # Start all patches
    started_patches = []
    try:
        for p in patches:
            started_patches.append(p.__enter__())
        
        yield mock_logger
        
    finally:
        # Clean up all patches in reverse order
        for p in reversed(patches):
            try:
                p.__exit__(None, None, None)
            except:
                pass  # Ignore cleanup errors


@pytest.fixture
def logging_isolated_response_handler():
    """
    Fixture that provides a ResponseHandler with completely isolated logging.
    
    This resolves the audit finding that ResponseHandler tests cannot pass
    due to structured logging incompatibility.
    """
    def create_handler(settings, scenario_processor):
        with isolated_logging() as mock_logger:
            # Import ResponseHandler WITHIN the logging isolation context
            from services.response_handler import ResponseHandler
            
            # Create instance with mocked logging
            handler = ResponseHandler(settings=settings, scenario_processor=scenario_processor)
            
            # Replace the logger with our mock to ensure all calls work
            handler.logger = mock_logger
            
            return handler, mock_logger
    
    return create_handler


@pytest.fixture
def mock_response_handler_factory(mock_settings, mock_scenario_processor):
    """
    Factory fixture for creating ResponseHandler instances with isolated logging.
    
    Usage: 
        handler, logger_mock = mock_response_handler_factory()
    """
    def factory():
        with isolated_logging() as mock_logger:
            # Import within isolation context
            from services.response_handler import ResponseHandler
            
            # Create the handler
            handler = ResponseHandler(
                settings=mock_settings,
                scenario_processor=mock_scenario_processor
            )
            
            # Ensure the logger is our mock
            handler.logger = mock_logger
            
            return handler, mock_logger
    
    return factory