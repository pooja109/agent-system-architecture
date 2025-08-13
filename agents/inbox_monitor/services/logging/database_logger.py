# services/logging/database_logger.py
"""Specialized logging mixin for database operation services."""

from typing import Dict, Any, Optional
from .service_logger_mixin import ServiceLoggerMixin
from utils.custom_logging.correlation import get_correlation_id


class DatabaseLoggerMixin(ServiceLoggerMixin):
    """Specialized mixin for database operations."""
    
    def log_query_start(self, query_type: str, table: Optional[str] = None) -> str:
        """Log start of database query."""
        correlation_id = get_correlation_id()
        
        log_data = {
            'query_type': query_type,
            'service': self.service_name,
            'correlation_id': correlation_id,
            'event_type': 'query_start'
        }
        
        if table:
            log_data['table'] = table
        
        self.diagnostic_logger.debug(f"Database query: {query_type}", extra=log_data)
        
        return correlation_id
    
    def log_query_result(self, correlation_id: str,
                        query_type: str,
                        row_count: Optional[int] = None,
                        duration_ms: Optional[float] = None) -> None:
        """Log database query result."""
        log_data = {
            'query_type': query_type,
            'service': self.service_name,
            'correlation_id': correlation_id,
            'event_type': 'query_result'
        }
        
        if row_count is not None:
            log_data['row_count'] = row_count
        if duration_ms is not None:
            log_data['duration_ms'] = duration_ms
        
        self.diagnostic_logger.debug(
            f"Query completed: {row_count or 'unknown'} rows",
            extra=log_data
        )
    
    def log_connection_event(self, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log database connection events."""
        log_data = {
            'event_type': f'connection_{event_type}',
            'service': self.service_name,
            'correlation_id': get_correlation_id()
        }
        
        if details:
            safe_details = self._sensitive_filter.filter_dict(details)
            log_data.update(safe_details)
        
        self.diagnostic_logger.info(f"Database connection: {event_type}", extra=log_data)