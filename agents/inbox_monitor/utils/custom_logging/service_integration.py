# utils/logging/service_integration.py
from typing import Dict, Any, Optional, Callable, Type
import logging
import functools
import inspect
from contextlib import contextmanager

from .logger_factory import LoggerFactory
from .config import LoggingConfig
from .correlation import get_correlation_id, set_correlation_context
from .sensitive_data_filter import SensitiveDataFilter


class ServiceLoggingIntegration:
    """Utilities for integrating logging into existing services."""
    
    def __init__(self, logger_factory: LoggerFactory):
        self.logger_factory = logger_factory
        self.sensitive_filter = SensitiveDataFilter()
    
    def create_service_logger(self, service_class: Type) -> logging.Logger:
        """Create a logger specifically for a service class."""
        service_name = self._get_service_name(service_class)
        logger = self.logger_factory.get_logger(f"services.{service_name}")
        return logger
    
    def create_console_logger(self, service_class: Type) -> logging.Logger:
        """Create a console-only logger for user-facing messages."""
        service_name = self._get_service_name(service_class)
        logger = self.logger_factory.get_console_logger(f"user.{service_name}")
        return logger
    
    def create_structured_logger(self, service_class: Type) -> logging.Logger:
        """Create a structured-only logger for diagnostic information."""
        service_name = self._get_service_name(service_class)
        logger = self.logger_factory.get_structured_logger(f"diagnostics.{service_name}")
        return logger
    
    def _get_service_name(self, service_class: Type) -> str:
        """Extract service name from class."""
        name = service_class.__name__
        # Convert CamelCase to snake_case
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    
    def retrofit_service_methods(self, service_instance: Any, 
                                logger: logging.Logger,
                                methods_to_log: Optional[list] = None) -> Any:
        """Retrofit existing service methods with logging."""
        if methods_to_log is None:
            # Default to public methods that aren't special methods
            methods_to_log = [
                name for name, method in inspect.getmembers(service_instance, inspect.ismethod)
                if not name.startswith('_') and callable(method)
            ]
        
        for method_name in methods_to_log:
            if hasattr(service_instance, method_name):
                original_method = getattr(service_instance, method_name)
                wrapped_method = self._create_logged_method(original_method, logger, method_name)
                setattr(service_instance, method_name, wrapped_method)
        
        return service_instance
    
    def _create_logged_method(self, original_method: Callable, 
                            logger: logging.Logger, 
                            method_name: str) -> Callable:
        """Create a wrapped version of a method with logging."""
        @functools.wraps(original_method)
        def logged_method(*args, **kwargs):
            correlation_id = get_correlation_id()
            
            # Filter sensitive information from arguments
            safe_kwargs = self.sensitive_filter.filter_dict(kwargs)
            
            # Log method entry
            logger.debug(
                f"{method_name} called",
                extra={
                    'method': method_name,
                    'correlation_id': correlation_id,
                    'args_count': len(args),
                    'kwargs': safe_kwargs,
                    'event_type': 'method_entry'
                }
            )
            
            try:
                # Execute the original method
                with set_correlation_context(correlation_id):
                    result = original_method(*args, **kwargs)
                
                # Log successful completion
                logger.debug(
                    f"{method_name} completed successfully",
                    extra={
                        'method': method_name,
                        'correlation_id': correlation_id,
                        'event_type': 'method_success'
                    }
                )
                
                return result
                
            except Exception as e:
                # Log error with full context
                logger.error(
                    f"{method_name} failed: {e}",
                    extra={
                        'method': method_name,
                        'correlation_id': correlation_id,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'event_type': 'method_error'
                    },
                    exc_info=True
                )
                # Re-raise the exception
                raise
        
        return logged_method


def log_api_call(logger: logging.Logger, 
                operation: str,
                service_name: str = None):
    """Decorator for API call logging."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            correlation_id = get_correlation_id()
            
            # Extract service name from function if not provided
            if service_name is None:
                extracted_service = func.__qualname__.split('.')[0] if '.' in func.__qualname__ else 'unknown'
            else:
                extracted_service = service_name
            
            logger.info(
                f"Starting {operation}",
                extra={
                    'operation': operation,
                    'service': extracted_service,
                    'correlation_id': correlation_id,
                    'event_type': 'api_call_start'
                }
            )
            
            try:
                result = func(*args, **kwargs)
                
                logger.info(
                    f"Completed {operation}",
                    extra={
                        'operation': operation,
                        'service': extracted_service,
                        'correlation_id': correlation_id,
                        'event_type': 'api_call_success'
                    }
                )
                
                return result
                
            except Exception as e:
                logger.error(
                    f"Failed {operation}: {e}",
                    extra={
                        'operation': operation,
                        'service': extracted_service,
                        'correlation_id': correlation_id,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'event_type': 'api_call_error'
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def log_business_operation(logger: logging.Logger, 
                         operation: str,
                         include_result: bool = False):
    """Decorator for business logic operation logging."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            correlation_id = get_correlation_id()
            
            logger.info(
                f"Processing {operation}",
                extra={
                    'operation': operation,
                    'correlation_id': correlation_id,
                    'event_type': 'business_operation_start'
                }
            )
            
            try:
                result = func(*args, **kwargs)
                
                log_data = {
                    'operation': operation,
                    'correlation_id': correlation_id,
                    'event_type': 'business_operation_success'
                }
                
                if include_result and result is not None:
                    # Only include safe result information
                    if isinstance(result, (str, int, float, bool)):
                        log_data['result'] = result
                    elif hasattr(result, '__len__'):
                        log_data['result_count'] = len(result)
                
                logger.info(f"Completed {operation}", extra=log_data)
                
                return result
                
            except Exception as e:
                logger.error(
                    f"Failed {operation}: {e}",
                    extra={
                        'operation': operation,
                        'correlation_id': correlation_id,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'event_type': 'business_operation_error'
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator