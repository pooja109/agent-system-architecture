"""
Error Recovery Manager - Robust Error Handling and Recovery
"""

import asyncio
import logging
from typing import Any, Callable, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import traceback


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    error_type: type
    error_message: str
    traceback: str
    timestamp: datetime
    scenario_id: Optional[int] = None
    service: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class ErrorRecoveryManager:
    """Manages error recovery and resilience."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.error_log = []
        self.recovery_strategies = self._setup_strategies()
        self.fallback_handlers = self._setup_fallbacks()
        
        # Configure retry settings
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        self.exponential_backoff = self.config.get('exponential_backoff', True)
    
    def _setup_strategies(self) -> Dict[type, RecoveryStrategy]:
        """Set up recovery strategies for different error types."""
        return {
            ConnectionError: RecoveryStrategy.RETRY,
            TimeoutError: RecoveryStrategy.RETRY,
            ValueError: RecoveryStrategy.SKIP,
            KeyError: RecoveryStrategy.FALLBACK,
            PermissionError: RecoveryStrategy.ABORT,
            Exception: RecoveryStrategy.SKIP  # Default strategy
        }
    
    def _setup_fallbacks(self) -> Dict[str, Callable]:
        """Set up fallback handlers for services."""
        return {
            'graph_api': self._fallback_mock_email,
            'azure_ai': self._fallback_simple_classification,
            'salesforce': self._fallback_local_case
        }
    
    async def execute_with_recovery(self, 
                                   func: Callable,
                                   *args,
                                   context: Optional[Dict[str, Any]] = None,
                                   **kwargs) -> Any:
        """Execute function with error recovery."""
        context = context or {}
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                # Attempt execution
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - log if this was a retry
                if retry_count > 0:
                    self._log_recovery_success(func.__name__, retry_count)
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Create error context
                error_context = ErrorContext(
                    error_type=type(e),
                    error_message=str(e),
                    traceback=traceback.format_exc(),
                    timestamp=datetime.now(),
                    scenario_id=context.get('scenario_id'),
                    service=context.get('service'),
                    retry_count=retry_count,
                    max_retries=self.max_retries
                )
                
                # Log error
                self.error_log.append(error_context)
                
                # Determine recovery strategy
                strategy = self._get_recovery_strategy(error_context)
                
                if strategy == RecoveryStrategy.RETRY and retry_count < self.max_retries:
                    # Retry with backoff
                    delay = self._calculate_backoff(retry_count)
                    await asyncio.sleep(delay)
                    retry_count += 1
                    continue
                    
                elif strategy == RecoveryStrategy.FALLBACK:
                    # Use fallback handler
                    fallback = self._get_fallback_handler(context.get('service'))
                    if fallback:
                        if asyncio.iscoroutinefunction(fallback):
                            return await fallback(*args, **kwargs)
                        else:
                            return fallback(*args, **kwargs)
                    break
                    
                elif strategy == RecoveryStrategy.SKIP:
                    # Skip and return None
                    return None
                    
                elif strategy == RecoveryStrategy.ABORT:
                    # Re-raise the error
                    raise
                    
                else:
                    break
        
        # Max retries exceeded or no recovery possible
        self._log_recovery_failure(func.__name__, last_error)
        raise last_error
    
    def _get_recovery_strategy(self, context: ErrorContext) -> RecoveryStrategy:
        """Determine recovery strategy for error."""
        # Check specific error type strategies
        for error_type, strategy in self.recovery_strategies.items():
            if issubclass(context.error_type, error_type):
                return strategy
        
        # Default strategy
        return RecoveryStrategy.SKIP
    
    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate backoff delay for retry."""
        if self.exponential_backoff:
            return self.retry_delay * (2 ** retry_count)
        else:
            return self.retry_delay
    
    def _get_fallback_handler(self, service: Optional[str]) -> Optional[Callable]:
        """Get fallback handler for service."""
        if service:
            return self.fallback_handlers.get(service)
        return None
    
    def _fallback_mock_email(self, *args, **kwargs) -> Dict[str, Any]:
        """Fallback: Return mock email data."""
        return {
            'id': 'mock-email-001',
            'from': 'fallback@example.com',
            'subject': 'Fallback Email',
            'body': 'This is a fallback email for testing.',
            'received': datetime.now().isoformat()
        }
    
    def _fallback_simple_classification(self, *args, **kwargs) -> Dict[str, Any]:
        """Fallback: Simple rule-based classification."""
        email = args[0] if args else kwargs.get('email', {})
        subject = email.get('subject', '').lower()
        
        # Simple classification rules
        if 'support' in subject or 'help' in subject:
            intent = 'support_request'
        elif 'cancel' in subject or 'stop' in subject:
            intent = 'no_longer_works'
        elif 'question' in subject or 'inquiry' in subject:
            intent = 'inquiry'
        else:
            intent = 'inquiry'
        
        return {
            'classification': intent,
            'confidence': 0.7,
            'tokens_used': 0,
            'fallback': True
        }
    
    def _fallback_local_case(self, *args, **kwargs) -> str:
        """Fallback: Create local case ID."""
        import uuid
        return f"LOCAL-{uuid.uuid4().hex[:8].upper()}"
    
    def _log_recovery_success(self, func_name: str, retry_count: int):
        """Log successful recovery."""
        logging.info(f"Recovery successful for {func_name} after {retry_count} retries")
    
    def _log_recovery_failure(self, func_name: str, error: Exception):
        """Log recovery failure."""
        logging.error(f"Recovery failed for {func_name}: {error}")
    
    def get_error_report(self) -> Dict[str, Any]:
        """Get error report summary."""
        if not self.error_log:
            return {
                'total_errors': 0,
                'recovered': 0,
                'failed': 0,
                'errors_by_type': {},
                'errors_by_service': {}
            }
        
        errors_by_type = {}
        errors_by_service = {}
        
        for error in self.error_log:
            # Count by type
            error_type_name = error.error_type.__name__
            errors_by_type[error_type_name] = errors_by_type.get(error_type_name, 0) + 1
            
            # Count by service
            if error.service:
                errors_by_service[error.service] = errors_by_service.get(error.service, 0) + 1
        
        return {
            'total_errors': len(self.error_log),
            'recovered': sum(1 for e in self.error_log if e.retry_count > 0),
            'failed': sum(1 for e in self.error_log if e.retry_count >= e.max_retries),
            'errors_by_type': errors_by_type,
            'errors_by_service': errors_by_service,
            'recent_errors': [
                {
                    'timestamp': e.timestamp.isoformat(),
                    'type': e.error_type.__name__,
                    'message': e.error_message,
                    'service': e.service
                }
                for e in self.error_log[-5:]  # Last 5 errors
            ]
        }
    
    def clear_error_log(self):
        """Clear error log."""
        self.error_log = []