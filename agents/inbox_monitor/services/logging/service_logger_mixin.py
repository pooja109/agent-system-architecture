# services/logging/service_logger_mixin.py
import logging
from typing import Optional, Dict, Any
from abc import ABC

from utils.custom_logging import get_logger, get_console_logger, get_structured_logger
from utils.custom_logging.correlation import get_correlation_id
from utils.custom_logging.sensitive_data_filter import SensitiveDataFilter


class ServiceLoggerMixin:
    """Mixin to add standardized logging to service classes."""
    
    def __init_logging__(self, service_name: Optional[str] = None):
        """Initialize logging for the service."""
        if service_name is None:
            service_name = self.__class__.__name__.lower()
        
        self.service_name = service_name
        self._logger = get_logger(f"services.{service_name}")
        self._console_logger = get_console_logger(f"user.{service_name}")
        self._diagnostic_logger = get_structured_logger(f"diagnostics.{service_name}")
        self._sensitive_filter = SensitiveDataFilter()
    
    @property
    def logger(self) -> logging.Logger:
        """Get the main service logger (both console and structured)."""
        if not hasattr(self, '_logger'):
            self.__init_logging__()
        return self._logger
    
    @logger.setter
    def logger(self, value: logging.Logger) -> None:
        """Allow setting logger for backward compatibility."""
        # If setting before mixin initialization, store as legacy logger
        if not hasattr(self, '_logger'):
            self._legacy_logger = value
        else:
            # If mixin already initialized, respect the existing logger
            pass
    
    @property
    def console_logger(self) -> logging.Logger:
        """Get console-only logger for user-facing messages."""
        if not hasattr(self, '_console_logger'):
            self.__init_logging__()
        return self._console_logger
    
    @property
    def diagnostic_logger(self) -> logging.Logger:
        """Get structured-only logger for diagnostic information."""
        if not hasattr(self, '_diagnostic_logger'):
            self.__init_logging__()
        return self._diagnostic_logger
    
    def log_operation_start(self, operation: str, **context) -> str:
        """Log the start of an operation and return correlation ID."""
        correlation_id = get_correlation_id()
        
        # Filter sensitive information from context
        safe_context = self._sensitive_filter.filter_dict(context)
        
        self.logger.info(
            f"Starting {operation}",
            extra={
                'operation': operation,
                'service': self.service_name,
                'correlation_id': correlation_id,
                'event_type': 'operation_start',
                **safe_context
            }
        )
        
        return correlation_id
    
    def log_operation_success(self, operation: str, 
                            correlation_id: str,
                            result_summary: Optional[str] = None,
                            **context) -> None:
        """Log successful completion of an operation."""
        log_data = {
            'operation': operation,
            'service': self.service_name,
            'correlation_id': correlation_id,
            'event_type': 'operation_success'
        }
        
        if result_summary:
            log_data['result_summary'] = result_summary
        
        # Filter sensitive information from context
        safe_context = self._sensitive_filter.filter_dict(context)
        log_data.update(safe_context)
        
        self.logger.info(f"Completed {operation}", extra=log_data)
    
    def log_operation_error(self, operation: str,
                          correlation_id: str, 
                          error: Exception,
                          **context) -> None:
        """Log operation failure with full error context."""
        # Filter sensitive information from context
        safe_context = self._sensitive_filter.filter_dict(context)
        
        self.logger.error(
            f"Failed {operation}: {error}",
            extra={
                'operation': operation,
                'service': self.service_name,
                'correlation_id': correlation_id,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'event_type': 'operation_error',
                **safe_context
            },
            exc_info=True
        )
    
    def log_user_message(self, message: str, level: str = 'info') -> None:
        """Log a message that should be visible to users."""
        log_method = getattr(self.console_logger, level.lower(), self.console_logger.info)
        log_method(message)
    
    def log_diagnostic(self, message: str, level: str = 'debug', **context) -> None:
        """Log diagnostic information (structured only)."""
        # Filter sensitive information from context
        safe_context = self._sensitive_filter.filter_dict(context)
        
        log_method = getattr(self.diagnostic_logger, level.lower(), self.diagnostic_logger.debug)
        log_method(
            message,
            extra={
                'service': self.service_name,
                'correlation_id': get_correlation_id(),
                'event_type': 'diagnostic',
                **safe_context
            }
        )
    
    def log_api_call(self, api_name: str, endpoint: str, method: str = 'GET') -> str:
        """Log an API call and return correlation ID."""
        correlation_id = get_correlation_id()
        
        self.diagnostic_logger.debug(
            f"API call: {method} {endpoint}",
            extra={
                'api_name': api_name,
                'endpoint': endpoint,
                'method': method,
                'service': self.service_name,
                'correlation_id': correlation_id,
                'event_type': 'api_call'
            }
        )
        
        return correlation_id
    
    def log_api_response(self, correlation_id: str, 
                        status_code: Optional[int] = None,
                        response_size: Optional[int] = None,
                        duration_ms: Optional[float] = None) -> None:
        """Log API response information."""
        log_data = {
            'service': self.service_name,
            'correlation_id': correlation_id,
            'event_type': 'api_response'
        }
        
        if status_code is not None:
            log_data['status_code'] = status_code
        if response_size is not None:
            log_data['response_size'] = response_size
        if duration_ms is not None:
            log_data['duration_ms'] = duration_ms
        
        self.diagnostic_logger.debug(
            f"API response: {status_code or 'unknown'}",
            extra=log_data
        )