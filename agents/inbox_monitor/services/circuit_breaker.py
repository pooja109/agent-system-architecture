"""
Production Circuit Breaker Implementation
Provides circuit breaker pattern for external service resilience.
"""
import asyncio
import time
from typing import Any, Callable, Optional, Type, Union, Tuple
from enum import Enum
import structlog

logger = structlog.get_logger()

class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Production circuit breaker implementation.
    
    Provides automatic failure detection and recovery for external services.
    """
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
                 success_threshold: int = 3):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception types that trigger circuit breaker
            success_threshold: Number of successes needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        # State
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._lock = asyncio.Lock()
        
        # Metrics
        self.metrics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'circuit_opens': 0,
            'circuit_closes': 0
        }
    
    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state.value
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            Original exception: When function fails and circuit remains closed
        """
        async with self._lock:
            self.metrics['total_calls'] += 1
            
            # Check if circuit should transition to half-open
            if (self._state == CircuitBreakerState.OPEN and 
                self._last_failure_time and
                time.time() - self._last_failure_time >= self.recovery_timeout):
                
                self._state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit breaker transitioning to half-open state")
            
            # Block calls when circuit is open
            if self._state == CircuitBreakerState.OPEN:
                logger.warning("Circuit breaker is open, blocking call")
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        # Execute the function
        start_time = time.time()
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Handle success
            async with self._lock:
                await self._on_success()
            
            execution_time = time.time() - start_time
            logger.debug(f"Circuit breaker call successful in {execution_time:.2f}s")
            return result
            
        except self.expected_exception as e:
            # Handle expected failure
            async with self._lock:
                await self._on_failure()
            
            execution_time = time.time() - start_time
            logger.warning(f"Circuit breaker call failed in {execution_time:.2f}s: {e}")
            raise
        except Exception as e:
            # Handle unexpected exception (don't count as failure)
            execution_time = time.time() - start_time
            logger.error(f"Circuit breaker call had unexpected error in {execution_time:.2f}s: {e}")
            raise
    
    async def _on_success(self):
        """Handle successful function execution."""
        self.metrics['successful_calls'] += 1
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            
            if self._success_count >= self.success_threshold:
                # Close the circuit
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self.metrics['circuit_closes'] += 1
                logger.info("Circuit breaker closed after successful recovery")
        
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    async def _on_failure(self):
        """Handle failed function execution."""
        self.metrics['failed_calls'] += 1
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            # Return to open state
            self._state = CircuitBreakerState.OPEN
            self._success_count = 0
            logger.warning("Circuit breaker returning to open state after failure during recovery")
        
        elif (self._state == CircuitBreakerState.CLOSED and 
              self._failure_count >= self.failure_threshold):
            # Open the circuit
            self._state = CircuitBreakerState.OPEN
            self.metrics['circuit_opens'] += 1
            logger.warning(f"Circuit breaker opened after {self._failure_count} failures")
    
    def get_metrics(self) -> dict:
        """Get circuit breaker metrics."""
        return {
            **self.metrics,
            'state': self.state,
            'failure_count': self._failure_count,
            'success_count': self._success_count,
            'failure_rate': (
                self.metrics['failed_calls'] / max(self.metrics['total_calls'], 1)
            ),
            'last_failure_time': self._last_failure_time
        }
    
    def reset(self):
        """Reset circuit breaker to initial state."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        
        # Reset metrics
        for key in self.metrics:
            self.metrics[key] = 0
        
        logger.info("Circuit breaker reset to initial state")

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass