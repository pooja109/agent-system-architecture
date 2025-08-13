# services/logging/api_client_logger.py
"""Specialized logging mixin for API client services."""

from .service_logger_mixin import ServiceLoggerMixin
from utils.custom_logging.correlation import get_correlation_id


class APIClientLoggerMixin(ServiceLoggerMixin):
    """Specialized mixin for API client services."""
    
    def log_authentication_start(self, auth_type: str) -> str:
        """Log authentication start."""
        correlation_id = get_correlation_id()
        
        self.diagnostic_logger.info(
            f"Starting {auth_type} authentication",
            extra={
                'auth_type': auth_type,
                'service': self.service_name,
                'correlation_id': correlation_id,
                'event_type': 'auth_start'
            }
        )
        
        return correlation_id
    
    def log_authentication_success(self, correlation_id: str, auth_type: str) -> None:
        """Log successful authentication."""
        self.logger.info(
            f"{auth_type} authentication successful",
            extra={
                'auth_type': auth_type,
                'service': self.service_name,
                'correlation_id': correlation_id,
                'event_type': 'auth_success'
            }
        )
    
    def log_authentication_failure(self, correlation_id: str, 
                                 auth_type: str, 
                                 error: Exception) -> None:
        """Log authentication failure."""
        self.logger.error(
            f"{auth_type} authentication failed: {error}",
            extra={
                'auth_type': auth_type,
                'service': self.service_name,
                'correlation_id': correlation_id,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'event_type': 'auth_error'
            },
            exc_info=True
        )