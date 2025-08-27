# utils/logging/__init__.py
"""Logging utilities for clean console output and structured production logging."""

from .config import LoggingConfig, ConsoleConfig, StructuredConfig, FileConfig, LogLevel, OutputFormat
from .console_handler import ConsoleHandler, ConsoleFormatter
from .structured_handler import StructuredHandler, StructuredFormatter
from .logger_factory import LoggerFactory
from .message_formatter import (
    MessageFormatter, ConsoleMessageFormatter, StructuredMessageFormatter,
    MessageFormatterFactory, SensitiveDataRedactor, MessageStyler,
    MessageSensitivity, create_console_formatter, create_structured_formatter, create_redactor
)
from .exceptions import (
    LoggingException,
    LoggingConfigurationError,
    LogHandlerError,
    LogFormatterError,
    LoggerInitializationError
)
from .correlation import (
    generate_correlation_id, get_correlation_id, set_correlation_id,
    get_correlation_context, set_correlation_context, clear_correlation_context,
    correlation_id_context, set_correlation_context as correlation_context_manager,
    create_correlation_aware_logger_extra, CorrelationIDFilter, add_correlation_to_logger
)
from .sensitive_data_filter import (
    SensitiveDataFilter, LogMessageFilter, get_global_filter,
    filter_sensitive_data, add_sensitive_pattern, create_log_message_filter
)
from .service_integration import (
    ServiceLoggingIntegration, log_api_call, log_business_operation
)
from .http_client_config import (
    HTTPClientLogSuppressor, configure_azure_sdk_logging, 
    configure_graph_api_logging, quick_suppress_http_logging
)

# Convenience functions for common usage patterns
import logging
from typing import Any

def get_logger(name: str) -> logging.Logger:
    """Get a logger with both console and structured output."""
    factory = LoggerFactory()
    return factory.get_logger(name)

def get_console_logger(name: str) -> logging.Logger:
    """Get a logger that only outputs to console (user-facing)."""
    factory = LoggerFactory()
    return factory.get_console_logger(name)

def get_structured_logger(name: str) -> logging.Logger:
    """Get a logger that only outputs structured logs (production)."""
    factory = LoggerFactory()
    return factory.get_structured_logger(name)

def initialize_logging(config: LoggingConfig) -> None:
    """Initialize the logging system with the provided configuration."""
    factory = LoggerFactory()
    factory.initialize(config)


def initialize_logging_from_settings(existing_config: Any) -> LoggerFactory:
    """
    Initialize logging from existing settings/configuration.
    
    This function provides seamless integration with the existing config/settings.py
    system by automatically converting existing configuration to LoggingConfig format.
    
    Args:
        existing_config: Existing configuration object (e.g., from config/settings.py)
        
    Returns:
        Initialized LoggerFactory instance
        
    Example:
        from config.settings import get_settings
        from utils.custom_logging import initialize_logging_from_settings, get_logger
        
        settings = get_settings()
        initialize_logging_from_settings(settings)
        logger = get_logger('my_service')
    """
    return LoggerFactory.from_existing_config(existing_config)

def cleanup_logging() -> None:
    """Clean up logging resources."""
    factory = LoggerFactory()
    factory.cleanup()

def reset_logging_for_testing() -> None:
    """
    Reset logging system for testing purposes.
    
    This function provides a clean reset that allows the logging system
    to be re-initialized after cleanup, which is useful for testing scenarios.
    """
    LoggerFactory.reset_for_testing()


# Service Integration Helper Functions
def integrate_service_logging(service_class: type, logger_name: str = None) -> type:
    """
    Integrate logging into an existing service class.
    
    This helper function adds logging capabilities to existing service classes
    by injecting logger instances and providing convenient logging methods.
    
    Args:
        service_class: The service class to enhance with logging
        logger_name: Optional logger name (defaults to class name)
        
    Returns:
        Enhanced service class with logging capabilities
        
    Example:
        @integrate_service_logging
        class EmailService:
            def process_email(self, email):
                self.log.info("Processing email", extra={"email_id": email.id})
                # ... processing logic
    """
    import functools
    from typing import Any, Optional
    from datetime import datetime
    
    original_init = service_class.__init__
    
    @functools.wraps(original_init)
    def enhanced_init(self, *args, **kwargs):
        # Call original init
        original_init(self, *args, **kwargs)
        
        # Add logging capabilities
        logger_name_to_use = logger_name or service_class.__name__.lower()
        self.log = get_logger(logger_name_to_use)
        self.console_log = get_console_logger(logger_name_to_use)
        self.structured_log = get_structured_logger(logger_name_to_use)
        
        # Add convenience methods
        self.log_info = lambda msg, **kw: self.log.info(msg, **kw)
        self.log_error = lambda msg, **kw: self.log.error(msg, **kw)
        self.log_warning = lambda msg, **kw: self.log.warning(msg, **kw)
        self.log_debug = lambda msg, **kw: self.log.debug(msg, **kw)
        
        # Console-specific logging for user messages
        self.user_info = lambda msg: self.console_log.info(msg)
        self.user_error = lambda msg: self.console_log.error(msg)
        self.user_warning = lambda msg: self.console_log.warning(msg)
    
    service_class.__init__ = enhanced_init
    return service_class


def setup_service_logging(service_instance, logger_name: str = None) -> None:
    """
    Set up logging for an existing service instance.
    
    This function adds logging capabilities to an already instantiated service.
    
    Args:
        service_instance: The service instance to enhance
        logger_name: Optional logger name (defaults to class name)
    """
    from typing import Any, Optional
    from datetime import datetime
    
    logger_name_to_use = logger_name or service_instance.__class__.__name__.lower()
    
    # Add logger instances
    service_instance.log = get_logger(logger_name_to_use)
    service_instance.console_log = get_console_logger(logger_name_to_use)
    service_instance.structured_log = get_structured_logger(logger_name_to_use)
    
    # Add convenience methods
    service_instance.log_info = lambda msg, **kw: service_instance.log.info(msg, **kw)
    service_instance.log_error = lambda msg, **kw: service_instance.log.error(msg, **kw)
    service_instance.log_warning = lambda msg, **kw: service_instance.log.warning(msg, **kw)
    service_instance.log_debug = lambda msg, **kw: service_instance.log.debug(msg, **kw)
    
    # Console-specific logging for user messages
    service_instance.user_info = lambda msg: service_instance.console_log.info(msg)
    service_instance.user_error = lambda msg: service_instance.console_log.error(msg)
    service_instance.user_warning = lambda msg: service_instance.console_log.warning(msg)


def create_service_logger_context(service_name: str, operation: str = None) -> dict:
    """
    Create a logging context for service operations.
    
    Args:
        service_name: Name of the service
        operation: Current operation being performed
        
    Returns:
        Context dictionary for structured logging
    """
    from datetime import datetime
    
    context = {
        "service": service_name,
        "timestamp": datetime.now().isoformat()
    }
    
    if operation:
        context["operation"] = operation
    
    return context


def log_service_error(logger, 
                     service_name: str, 
                     error: Exception, 
                     operation: str = None,
                     extra_context: dict = None) -> None:
    """
    Log service errors with consistent formatting.
    
    Args:
        logger: Logger instance to use
        service_name: Name of the service where error occurred
        error: The exception that occurred
        operation: Operation that was being performed
        extra_context: Additional context information
    """
    context = create_service_logger_context(service_name, operation)
    
    if extra_context:
        context.update(extra_context)
    
    logger.error(
        f"Service error in {service_name}: {str(error)}",
        exc_info=True,
        extra=context
    )


def migrate_print_statements(service_instance, 
                           default_level: str = "info",
                           setup_logging_first: bool = True) -> None:
    """
    Helper to migrate from print statements to proper logging.
    
    This function replaces print with logging calls and can be used
    during the migration process.
    
    Args:
        service_instance: Service instance to modify
        default_level: Default logging level for print replacement
        setup_logging_first: Whether to set up logging if not present
    """
    if setup_logging_first and not hasattr(service_instance, 'log'):
        setup_service_logging(service_instance)
    
    # Store original print function
    original_print = print
    
    def logging_print(*args, **kwargs):
        # Convert print arguments to string
        message = ' '.join(str(arg) for arg in args)
        
        # Use appropriate logging level
        if hasattr(service_instance, 'log'):
            getattr(service_instance.log, default_level)(message)
        else:
            # Fallback to original print if logging not available
            original_print(*args, **kwargs)
    
    # Replace print in the service instance's namespace if it's a module
    if hasattr(service_instance, '__dict__'):
        service_instance.print = logging_print


# Make commonly used items available at package level
__all__ = [
    # Core logging components
    'LoggingConfig',
    'ConsoleConfig', 
    'StructuredConfig',
    'FileConfig',
    'LogLevel',
    'OutputFormat',
    'ConsoleHandler',
    'StructuredHandler',
    'LoggerFactory',
    'MessageFormatter',
    'ConsoleMessageFormatter',
    'StructuredMessageFormatter', 
    'MessageFormatterFactory',
    'SensitiveDataRedactor',
    'MessageStyler',
    'MessageSensitivity',
    'create_console_formatter',
    'create_structured_formatter',
    'create_redactor',
    
    # Convenience functions
    'get_logger',
    'get_console_logger',
    'get_structured_logger',
    'initialize_logging',
    'initialize_logging_from_settings',
    'cleanup_logging',
    'reset_logging_for_testing',
    'integrate_service_logging',
    'setup_service_logging',
    'create_service_logger_context',
    'log_service_error',
    'migrate_print_statements',
    
    # Correlation system
    'generate_correlation_id',
    'get_correlation_id',
    'set_correlation_id',
    'get_correlation_context',
    'set_correlation_context',
    'clear_correlation_context',
    'correlation_id_context',
    'correlation_context_manager',
    'create_correlation_aware_logger_extra',
    'CorrelationIDFilter',
    'add_correlation_to_logger',
    
    # Sensitive data filtering
    'SensitiveDataFilter',
    'LogMessageFilter',
    'get_global_filter',
    'filter_sensitive_data',
    'add_sensitive_pattern',
    'create_log_message_filter',
    
    # Service integration
    'ServiceLoggingIntegration',
    'log_api_call',
    'log_business_operation',
    
    # HTTP client configuration
    'HTTPClientLogSuppressor',
    'configure_azure_sdk_logging',
    'configure_graph_api_logging',
    'quick_suppress_http_logging',
    
    # Exceptions
    'LoggingException',
    'LoggingConfigurationError',
    'LogHandlerError',
    'LogFormatterError',
    'LoggerInitializationError'
]