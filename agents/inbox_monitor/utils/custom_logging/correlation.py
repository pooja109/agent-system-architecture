# utils/logging/correlation.py
"""Correlation ID system for request tracing and logging context."""

import uuid
import threading
from typing import Optional, Any, Dict
from contextlib import contextmanager


class CorrelationContext:
    """Thread-local storage for correlation context."""
    
    def __init__(self):
        self._local = threading.local()
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID for the current thread."""
        self._local.correlation_id = correlation_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get the correlation ID for the current thread."""
        return getattr(self._local, 'correlation_id', None)
    
    def set_context(self, **context) -> None:
        """Set additional context for the current thread."""
        if not hasattr(self._local, 'context'):
            self._local.context = {}
        self._local.context.update(context)
    
    def get_context(self) -> Dict[str, Any]:
        """Get the full context for the current thread."""
        context = getattr(self._local, 'context', {})
        correlation_id = self.get_correlation_id()
        if correlation_id:
            context['correlation_id'] = correlation_id
        return context
    
    def clear(self) -> None:
        """Clear all context for the current thread."""
        if hasattr(self._local, 'correlation_id'):
            delattr(self._local, 'correlation_id')
        if hasattr(self._local, 'context'):
            delattr(self._local, 'context')


# Global correlation context instance
_correlation_context = CorrelationContext()


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> str:
    """
    Get the current correlation ID, generating one if none exists.
    
    Returns:
        Current correlation ID for the thread
    """
    correlation_id = _correlation_context.get_correlation_id()
    if correlation_id is None:
        correlation_id = generate_correlation_id()
        _correlation_context.set_correlation_id(correlation_id)
    return correlation_id


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current thread.
    
    Args:
        correlation_id: The correlation ID to set
    """
    _correlation_context.set_correlation_id(correlation_id)


def get_correlation_context() -> Dict[str, Any]:
    """
    Get the full correlation context for logging.
    
    Returns:
        Dictionary with correlation ID and any additional context
    """
    return _correlation_context.get_context()


def set_correlation_context(**context) -> None:
    """
    Set additional context for correlation.
    
    Args:
        **context: Key-value pairs to add to correlation context
    """
    _correlation_context.set_context(**context)


def clear_correlation_context() -> None:
    """Clear all correlation context for the current thread."""
    _correlation_context.clear()


@contextmanager
def correlation_id_context(correlation_id: Optional[str] = None):
    """
    Context manager for correlation ID scope.
    
    Args:
        correlation_id: Optional correlation ID to use. If None, generates a new one.
        
    Example:
        with correlation_id_context("custom-id") as cid:
            logger.info("Processing request", extra={'correlation_id': cid})
    """
    if correlation_id is None:
        correlation_id = generate_correlation_id()
    
    # Save the current state
    original_id = _correlation_context.get_correlation_id()
    original_context = _correlation_context.get_context().copy()
    
    try:
        # Set new correlation ID
        set_correlation_id(correlation_id)
        yield correlation_id
    finally:
        # Restore original state
        if original_id is not None:
            _correlation_context.set_correlation_id(original_id)
        else:
            _correlation_context.clear()
        
        # Restore original context (excluding correlation_id which is handled above)
        if 'correlation_id' in original_context:
            del original_context['correlation_id']
        if original_context:
            _correlation_context.set_context(**original_context)


@contextmanager
def set_correlation_context(correlation_id: str, **additional_context):
    """
    Context manager for setting full correlation context.
    
    Args:
        correlation_id: The correlation ID to set
        **additional_context: Additional context to set
        
    Example:
        with set_correlation_context("req-123", user_id="user-456", operation="email_process"):
            # All logging will include this context
            logger.info("Processing started")
    """
    # Save current state
    original_id = _correlation_context.get_correlation_id()
    original_context = _correlation_context.get_context().copy()
    
    try:
        # Set new context
        set_correlation_id(correlation_id)
        if additional_context:
            set_correlation_context(**additional_context)
        yield
    finally:
        # Restore original state
        _correlation_context.clear()
        if original_id is not None:
            _correlation_context.set_correlation_id(original_id)
        if 'correlation_id' in original_context:
            del original_context['correlation_id']
        if original_context:
            _correlation_context.set_context(**original_context)


def create_correlation_aware_logger_extra(**extra_fields) -> Dict[str, Any]:
    """
    Create extra fields for logger that include correlation context.
    
    Args:
        **extra_fields: Additional fields to include
        
    Returns:
        Dictionary suitable for logger.info(..., extra=result)
    """
    context = get_correlation_context()
    context.update(extra_fields)
    return context


class CorrelationIDFilter:
    """Logging filter that adds correlation ID to all log records."""
    
    def filter(self, record):
        """Add correlation ID to log record."""
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = get_correlation_id()
        return True


def add_correlation_to_logger(logger):
    """
    Add correlation ID filter to a logger.
    
    Args:
        logger: Logger instance to enhance
        
    Example:
        import logging
        logger = logging.getLogger('my_service')
        add_correlation_to_logger(logger)
    """
    correlation_filter = CorrelationIDFilter()
    logger.addFilter(correlation_filter)