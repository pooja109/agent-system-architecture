# services/logging/business_logic_logger.py
"""Specialized logging mixin for business logic services."""

from typing import Dict, Any, Optional
from .service_logger_mixin import ServiceLoggerMixin
from utils.custom_logging.correlation import get_correlation_id


class BusinessLogicLoggerMixin(ServiceLoggerMixin):
    """Specialized mixin for business logic services."""
    
    def log_processing_start(self, item_type: str, item_id: Optional[str] = None) -> str:
        """Log start of processing an item."""
        correlation_id = get_correlation_id()
        
        log_data = {
            'item_type': item_type,
            'service': self.service_name,
            'correlation_id': correlation_id,
            'event_type': 'processing_start'
        }
        
        if item_id:
            log_data['item_id'] = item_id
        
        self.logger.info(f"Processing {item_type}", extra=log_data)
        
        return correlation_id
    
    def log_processing_result(self, correlation_id: str,
                            item_type: str,
                            result: str,
                            metrics: Optional[Dict[str, Any]] = None) -> None:
        """Log processing result."""
        log_data = {
            'item_type': item_type,
            'result': result,
            'service': self.service_name,
            'correlation_id': correlation_id,
            'event_type': 'processing_result'
        }
        
        if metrics:
            # Filter sensitive information from metrics
            safe_metrics = self._sensitive_filter.filter_dict(metrics)
            log_data['metrics'] = safe_metrics
        
        self.logger.info(f"Processing result: {result}", extra=log_data)