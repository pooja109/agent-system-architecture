"""
Scenario tracking integration service.
Coordinates storage of scenario processing data with minimal impact on email processing.
"""

import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
import uuid

import structlog
from pydantic import BaseModel

try:
    from services.scenario_tracking_client import ScenarioTrackingClient
    from services.circuit_breaker import CircuitBreaker, CircuitBreakerState
    from database.scenario_tracking_models import (
        ScenarioProcessingRecord,
        ScenarioTrackingConfiguration
    )
    from utils.data_transformation import ScenarioDataTransformer
    from services.scenario_tracking_exceptions import (
        ScenarioTrackingException,
        ServiceUnavailableError
    )
except ImportError:
    from .scenario_tracking_client import ScenarioTrackingClient
    from .circuit_breaker import CircuitBreaker, CircuitBreakerState
    from ..database.scenario_tracking_models import (
        ScenarioProcessingRecord,
        ScenarioTrackingConfiguration
    )
    from ..utils.data_transformation import ScenarioDataTransformer
    from .scenario_tracking_exceptions import (
        ScenarioTrackingException,
        ServiceUnavailableError
    )

logger = structlog.get_logger(__name__)


class TrackingIntegrationResult(BaseModel):
    """Result of tracking integration operation."""
    success: bool
    processing_duration_ms: float
    error_message: Optional[str] = None
    record_created: bool = False
    async_queued: bool = False
    retry_attempts: int = 0
    final_error: Optional[str] = None


class ScenarioTrackingIntegration:
    """
    Integration service for scenario tracking.
    Provides clean interface between email processing and data storage.
    """
    
    def __init__(self, config: ScenarioTrackingConfiguration = None):
        """Initialize integration service.
        
        Args:
            config: Tracking configuration, uses defaults if None
        """
        self.config = config or ScenarioTrackingConfiguration()
        self.tracking_client: Optional[ScenarioTrackingClient] = None
        self.data_transformer = ScenarioDataTransformer()
        self.logger = structlog.get_logger(__name__)
        self._initialization_lock = asyncio.Lock()
        self._initialized = False
        self._initialization_failed = False
        self._last_initialization_attempt = None
        
        # Batch processing components
        self._batch_queue: list = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        self._batch_flush_interval = 30.0  # seconds
        self._last_batch_flush = time.time()
        self._shutdown_event = asyncio.Event()
        
        # Retry configuration
        self._max_retry_attempts = getattr(config, 'max_retry_attempts', 3)
        self._base_retry_delay = getattr(config, 'base_retry_delay_seconds', 1.0)
        self._max_retry_delay = getattr(config, 'max_retry_delay_seconds', 30.0)
        self._retry_jitter = True  # Add randomness to prevent thundering herd
        
        # Circuit breaker for protecting email processing from tracking failures (Phase 3 requirement)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(config, 'circuit_breaker_failure_threshold', 5),
            recovery_timeout=getattr(config, 'circuit_breaker_recovery_timeout', 60.0),
            expected_exception=(ScenarioTrackingException, ServiceUnavailableError, ConnectionError, TimeoutError),
            success_threshold=getattr(config, 'circuit_breaker_success_threshold', 3)
        )
    
    async def _ensure_initialized(self) -> bool:
        """Ensure tracking client is initialized."""
        if self._initialized and self.tracking_client:
            return True
        
        if self._initialization_failed:
            # Don't retry failed initialization too frequently
            if (self._last_initialization_attempt and 
                time.time() - self._last_initialization_attempt < 60):  # 1 minute cooldown
                return False
        
        async with self._initialization_lock:
            if self._initialized:
                return True
            
            try:
                self._last_initialization_attempt = time.time()
                
                if not self.config.enabled:
                    self.logger.info("Scenario tracking disabled by configuration")
                    return False
                
                self.tracking_client = ScenarioTrackingClient(self.config)
                
                # CRITICAL FIX: Enter async context to initialize connection pool
                await self.tracking_client.__aenter__()
                
                # Test initialization with health check
                health_result = await self.tracking_client.health_check()
                if health_result.get("status") != "healthy":
                    raise ServiceUnavailableError("Tracking client health check failed")
                
                # Initialize table if needed
                table_initialized = await self.tracking_client.initialize_table()
                if not table_initialized:
                    raise ServiceUnavailableError("Failed to initialize tracking table")
                
                self._initialized = True
                self._initialization_failed = False
                
                self.logger.info(
                    "Scenario tracking integration initialized successfully",
                    extra={
                        "async_insert": self.config.async_insert,
                        "batch_size": self.config.batch_insert_size
                    }
                )
                return True
                
            except Exception as e:
                self._initialization_failed = True
                self.logger.error(
                    "Failed to initialize scenario tracking integration",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                return False
    
    async def _retry_with_exponential_backoff(self, operation, *args, **kwargs):
        """Retry an async operation with exponential backoff.
        
        Args:
            operation: Async function to retry
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Tuple of (success: bool, result: Any, attempts: int, final_error: str)
        """
        last_exception = None
        
        for attempt in range(self._max_retry_attempts + 1):  # +1 for initial attempt
            try:
                result = await operation(*args, **kwargs)
                return True, result, attempt, None
                
            except Exception as e:
                last_exception = e
                is_retryable = self._is_retryable_error(e)
                
                # Log the failure
                self.logger.warning(
                    "Storage operation failed, checking if retryable",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": self._max_retry_attempts + 1,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "is_retryable": is_retryable
                    }
                )
                
                # Don't retry if this is the last attempt or error is not retryable
                if attempt >= self._max_retry_attempts or not is_retryable:
                    break
                    
                # Calculate delay with exponential backoff and jitter
                delay = min(
                    self._base_retry_delay * (2 ** attempt),
                    self._max_retry_delay
                )
                
                if self._retry_jitter:
                    # Add ±25% jitter
                    jitter_range = delay * 0.25
                    delay += random.uniform(-jitter_range, jitter_range)
                    delay = max(0.1, delay)  # Ensure minimum delay
                
                self.logger.debug(
                    "Retrying storage operation after delay",
                    extra={
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                        "next_attempt": attempt + 2
                    }
                )
                
                await asyncio.sleep(delay)
        
        return False, None, self._max_retry_attempts + 1, str(last_exception) if last_exception else "Unknown error"
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.
        
        Args:
            error: Exception that occurred
            
        Returns:
            True if the error is likely transient and retryable
        """
        # Define retryable error types and patterns
        retryable_error_types = (
            # Network-related errors
            ConnectionError,
            TimeoutError,
            OSError,
            # Asyncio timeout
            asyncio.TimeoutError,
        )
        
        # Check error type
        if isinstance(error, retryable_error_types):
            return True
        
        # Check error message for retryable patterns
        error_message = str(error).lower()
        retryable_patterns = [
            'connection',
            'timeout',
            'network',
            'temporary',
            'transient',
            'unavailable',
            'busy',
            'throttle',
            'rate limit',
            'server error',
            '5xx',
            'internal server error',
            'bad gateway',
            'service unavailable',
            'gateway timeout'
        ]
        
        for pattern in retryable_patterns:
            if pattern in error_message:
                return True
        
        # Check for custom scenario tracking exceptions
        try:
            from .scenario_tracking_exceptions import ServiceUnavailableError
            if isinstance(error, ServiceUnavailableError):
                return True
        except ImportError:
            pass
        
        return False
    
    async def track_scenario_processing(
        self,
        email_data: Any,
        processing_result: Any,
        scenario_result: Any = None,
        intent_result: Any = None,
        original_subject_result: Any = None,
        correlation_id: str = None,
        **additional_context
    ) -> TrackingIntegrationResult:
        """
        Track scenario processing with optimized performance.
        
        Args:
            email_data: Email object from processing pipeline
            processing_result: ProcessingResult object
            scenario_result: ScenarioResult object (optional)
            intent_result: IntentClassificationResult object (optional)
            correlation_id: Correlation ID for tracing
            **additional_context: Additional context information
            
        Returns:
            TrackingIntegrationResult with operation status
        """
        start_time = time.time()
        
        # PERFORMANCE OPTIMIZATION: Early return if tracking is disabled (no overhead)
        if not self.config.enabled:
            return TrackingIntegrationResult(
                success=True,
                processing_duration_ms=0.0,
                error_message="Tracking disabled"
            )
        
        # PERFORMANCE OPTIMIZATION: Fast circuit breaker check
        if hasattr(self, '_circuit_breaker') and self._circuit_breaker.state == CircuitBreakerState.OPEN:
            return TrackingIntegrationResult(
                success=False,
                processing_duration_ms=(time.time() - start_time) * 1000,
                error_message="Circuit breaker is OPEN - tracking service unavailable"
            )
        
        # CRITICAL FIX: Check if connection pool is available for async operations
        from services.databricks_connection_pool import get_connection_pool
        pool_available = False
        try:
            await get_connection_pool()
            pool_available = True
        except Exception:
            pool_available = False
        
        # PERFORMANCE OPTIMIZATION: Use async mode only if connection pool isn't available
        # When pool is available, use sync mode to ensure storage works
        if self.config.async_insert and not pool_available:
            # Only use async mode when connection pool isn't available (mock mode)
            asyncio.create_task(
                self._async_track_processing(
                    email_data, processing_result, scenario_result, 
                    intent_result, original_subject_result, correlation_id, start_time, **additional_context
                )
            )
            
            # Return immediately with minimal overhead
            processing_duration_ms = (time.time() - start_time) * 1000
            return TrackingIntegrationResult(
                success=True,
                processing_duration_ms=processing_duration_ms,
                record_created=False,  # Will be created asynchronously
                async_queued=True
            )
        
        # Use synchronous processing when connection pool is available
        if pool_available:
            self.logger.debug("Using synchronous storage due to connection pool availability")
        
        # Synchronous processing (fallback)
        return await self._sync_track_processing(
            email_data, processing_result, scenario_result,
            intent_result, original_subject_result, correlation_id, start_time, **additional_context
        )
    
    async def _async_track_processing(
        self,
        email_data: Any,
        processing_result: Any,
        scenario_result: Any,
        intent_result: Any,
        original_subject_result: Any,
        correlation_id: str,
        start_time: float,
        **additional_context
    ):
        """Handle async tracking processing with error isolation."""
        try:
            # Ensure service is initialized (async)
            if not await self._ensure_initialized():
                self.logger.warning("Async tracking: service not available")
                return
            
            # PERFORMANCE OPTIMIZATION: Fast data transformation
            tracking_record = await self.data_transformer.create_tracking_record(
                email_data=email_data,
                processing_result=processing_result,
                scenario_result=scenario_result,
                intent_result=intent_result,
                original_subject_result=original_subject_result,
                correlation_id=correlation_id,
                **additional_context
            )
            
            # Store with minimal timeout for async operations
            await asyncio.wait_for(
                self.tracking_client.store_scenario_result(
                    record=tracking_record,
                    force_sync=False
                ),
                timeout=2.0  # Short timeout for async
            )
            
        except Exception as e:
            # Never fail email processing due to async tracking errors
            self.logger.error(
                "Async scenario tracking failed",
                extra={
                    "error": str(e),
                    "correlation_id": correlation_id
                }
            )
    
    async def _sync_track_processing(
        self,
        email_data: Any,
        processing_result: Any,
        scenario_result: Any,
        intent_result: Any,
        original_subject_result: Any,
        correlation_id: str,
        start_time: float,
        **additional_context
    ) -> TrackingIntegrationResult:
        """Handle synchronous tracking processing."""
        try:
            # Ensure service is initialized
            if not await self._ensure_initialized():
                return TrackingIntegrationResult(
                    success=False,
                    processing_duration_ms=(time.time() - start_time) * 1000,
                    error_message="Tracking service not available"
                )
            
            # PERFORMANCE OPTIMIZATION: Optimized data transformation
            tracking_record = await self.data_transformer.create_tracking_record(
                email_data=email_data,
                processing_result=processing_result,
                scenario_result=scenario_result,
                intent_result=intent_result,
                original_subject_result=original_subject_result,
                correlation_id=correlation_id,
                **additional_context
            )
            
            # Store record with minimal timeout for synchronous operations
            # CRITICAL FIX: Handle both old and new config attribute names
            if hasattr(self.config, 'connection_timeout_seconds'):
                timeout_value = self.config.connection_timeout_seconds
            elif hasattr(self.config, 'timeout_seconds'):
                timeout_value = self.config.timeout_seconds
            else:
                timeout_value = 30  # Default fallback
            storage_timeout = min(timeout_value, 5.0)  # Max 5 seconds
            
            try:
                storage_successful = await asyncio.wait_for(
                    self.tracking_client.store_scenario_result(
                        record=tracking_record,
                        force_sync=True
                    ),
                    timeout=storage_timeout
                )
                
                processing_duration_ms = (time.time() - start_time) * 1000
                
                return TrackingIntegrationResult(
                    success=storage_successful,
                    processing_duration_ms=processing_duration_ms,
                    record_created=storage_successful,
                    async_queued=False
                )
                
            except asyncio.TimeoutError:
                processing_duration_ms = (time.time() - start_time) * 1000
                self.logger.warning(
                    "Scenario tracking storage timed out",
                    extra={
                        "timeout_seconds": storage_timeout,
                        "processing_duration_ms": processing_duration_ms
                    }
                )
                return TrackingIntegrationResult(
                    success=False,
                    processing_duration_ms=processing_duration_ms,
                    error_message=f"Storage operation timed out after {storage_timeout}s"
                )
            
        except Exception as e:
            processing_duration_ms = (time.time() - start_time) * 1000
            
            # Log error but don't fail email processing
            self.logger.error(
                "Scenario tracking integration failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "processing_duration_ms": processing_duration_ms,
                    "correlation_id": correlation_id
                }
            )
            
            return TrackingIntegrationResult(
                success=False,
                processing_duration_ms=processing_duration_ms,
                error_message=str(e)
            )
    
    async def _add_to_batch(self, tracking_record: Any) -> bool:
        """Add tracking record to batch queue.
        
        Args:
            tracking_record: ScenarioProcessingRecord to add to batch
            
        Returns:
            True if successfully queued, False otherwise
        """
        try:
            async with self._batch_lock:
                self._batch_queue.append(tracking_record)
                
                # Start batch processing task if not already running
                if self._batch_task is None or self._batch_task.done():
                    self._batch_task = asyncio.create_task(self._batch_processor())
                
                # Check if we should flush immediately due to size
                if len(self._batch_queue) >= self.config.batch_insert_size:
                    await self._flush_batch_queue()
                    
                return True
                
        except Exception as e:
            self.logger.error("Failed to add record to batch queue", extra={"error": str(e)})
            return False
    
    async def _batch_processor(self):
        """Background task to process batches at regular intervals."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for flush interval or shutdown
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._batch_flush_interval
                    )
                    break  # Shutdown event was set
                except asyncio.TimeoutError:
                    # Regular flush interval - check if we need to flush
                    current_time = time.time()
                    if (current_time - self._last_batch_flush) >= self._batch_flush_interval:
                        async with self._batch_lock:
                            if self._batch_queue:
                                await self._flush_batch_queue()
                                
        except Exception as e:
            self.logger.error("Batch processor encountered error", extra={"error": str(e)})
    
    async def _flush_batch_queue(self):
        """Flush current batch queue to storage.
        
        Note: This method assumes it's called within a batch_lock context.
        """
        if not self._batch_queue:
            return
            
        batch_to_process = self._batch_queue.copy()
        self._batch_queue.clear()
        self._last_batch_flush = time.time()
        
        try:
            if self.tracking_client:
                async def _batch_storage_operation():
                    # Use bulk insert if available, otherwise insert individually
                    if hasattr(self.tracking_client, 'store_scenario_results_batch'):
                        return await self.tracking_client.store_scenario_results_batch(
                            records=batch_to_process,
                            force_sync=False  # Always async for batches
                        )
                    else:
                        # Fallback to individual inserts
                        success_count = 0
                        for record in batch_to_process:
                            try:
                                individual_success = await self.tracking_client.store_scenario_result(
                                    record=record,
                                    force_sync=False
                                )
                                if individual_success:
                                    success_count += 1
                            except Exception as e:
                                self.logger.warning(
                                    "Failed to store individual record in batch",
                                    extra={
                                        "error": str(e),
                                        "process_id": getattr(record, 'process_id', 'unknown')
                                    }
                                )
                        
                        return success_count == len(batch_to_process)
                
                # Use retry logic for batch operations
                success, _, retry_attempts, final_error = await self._retry_with_exponential_backoff(
                    _batch_storage_operation
                )
                
                self.logger.debug(
                    "Batch flush completed",
                    extra={
                        "batch_size": len(batch_to_process),
                        "success": success,
                        "retry_attempts": retry_attempts,
                        "final_error": final_error,
                        "batch_flush_interval": self._batch_flush_interval
                    }
                )
                
        except Exception as e:
            self.logger.error(
                "Failed to flush batch queue",
                extra={
                    "error": str(e),
                    "batch_size": len(batch_to_process)
                }
            )
    
    async def get_integration_health(self) -> Dict[str, Any]:
        """Get health status of integration service."""
        health_result = {
            "integration_service": "scenario_tracking_integration",
            "status": "healthy",
            "initialized": self._initialized,
            "initialization_failed": self._initialization_failed,
            "config_enabled": self.config.enabled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batch_processing": {
                "enabled": self.config.async_insert and self.config.batch_insert_size > 1,
                "batch_size": self.config.batch_insert_size,
                "queue_length": len(self._batch_queue),
                "batch_task_running": self._batch_task is not None and not self._batch_task.done(),
                "last_flush_time": self._last_batch_flush,
                "flush_interval": self._batch_flush_interval
            },
            "retry_configuration": {
                "max_attempts": self._max_retry_attempts,
                "base_delay_seconds": self._base_retry_delay,
                "max_delay_seconds": self._max_retry_delay,
                "jitter_enabled": self._retry_jitter
            }
        }
        
        if self._initialized and self.tracking_client:
            try:
                client_health = await self.tracking_client.health_check()
                health_result["tracking_client"] = client_health
                
                if client_health.get("status") != "healthy":
                    health_result["status"] = "degraded"
                    
            except Exception as e:
                health_result["status"] = "unhealthy"
                health_result["tracking_client_error"] = str(e)
        
        elif not self.config.enabled:
            health_result["status"] = "disabled"
        else:
            health_result["status"] = "not_initialized"
        
        return health_result
    
    async def flush_pending_operations(self):
        """Flush any pending async operations including batch queue."""
        # Flush batch queue first
        async with self._batch_lock:
            if self._batch_queue:
                await self._flush_batch_queue()
        
        # Flush underlying client operations
        if self._initialized and self.tracking_client:
            try:
                await self.tracking_client.flush_pending_inserts()
                self.logger.debug("Flushed pending tracking operations")
            except Exception as e:
                self.logger.warning("Failed to flush pending operations", extra={"error": str(e)})
    
    async def close(self):
        """Close integration service and cleanup resources."""
        # Signal shutdown to batch processor
        self._shutdown_event.set()
        
        # Wait for batch task to complete
        if self._batch_task and not self._batch_task.done():
            try:
                await asyncio.wait_for(self._batch_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("Batch processor did not shutdown cleanly")
                self._batch_task.cancel()
        
        # Flush any remaining batch items
        await self.flush_pending_operations()
        
        # Close tracking client
        if self.tracking_client:
            try:
                # Exit async context properly
                await self.tracking_client.__aexit__(None, None, None)
                # Close any remaining resources
                if hasattr(self.tracking_client, 'close'):
                    await self.tracking_client.close()
                self.logger.info("Scenario tracking integration closed")
            except Exception as e:
                self.logger.error("Error closing tracking integration", extra={"error": str(e)})
        
        self._initialized = False
        self.tracking_client = None


# Global integration instance for singleton usage
_integration_instance: Optional[ScenarioTrackingIntegration] = None
_integration_lock = asyncio.Lock()

async def get_tracking_integration(config: ScenarioTrackingConfiguration = None) -> ScenarioTrackingIntegration:
    """Get or create global tracking integration instance."""
    global _integration_instance
    
    async with _integration_lock:
        if _integration_instance is None:
            _integration_instance = ScenarioTrackingIntegration(config)
        return _integration_instance

async def close_tracking_integration():
    """Close global tracking integration instance."""
    global _integration_instance
    
    async with _integration_lock:
        if _integration_instance:
            await _integration_instance.close()
            _integration_instance = None