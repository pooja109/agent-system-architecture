"""
Configuration settings for scenario tracking integration.
Manages integration-specific settings for email processing pipeline integration.
"""

from datetime import timedelta
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
import os


class TrackingIntegrationSettings(BaseModel):
    """Settings for scenario tracking integration with email processing pipeline."""
    
    # Integration Control
    enabled: bool = Field(
        default=True,
        description="Enable/disable scenario tracking integration"
    )
    
    fail_fast: bool = Field(
        default=False,
        description="Fail email processing if tracking fails (NOT RECOMMENDED)"
    )
    
    # PERFORMANCE OPTIMIZED: Settings for <5% overhead requirement
    async_storage: bool = Field(
        default=True,
        description="Use asynchronous storage operations (REQUIRED for performance)"
    )
    
    storage_timeout_seconds: int = Field(
        default=2,  # PERFORMANCE OPTIMIZATION: Reduced from 10s to 2s
        ge=1,
        le=60,
        description="Timeout for storage operations in seconds (optimized for minimal blocking)"
    )
    
    # PERFORMANCE OPTIMIZATION: Fast-fail mode for overhead reduction
    fast_fail_mode: bool = Field(
        default=True,
        description="Enable fast-fail mode to minimize processing overhead"
    )
    
    # PERFORMANCE OPTIMIZATION: Minimal data extraction
    minimal_extraction: bool = Field(
        default=True,
        description="Use minimal data extraction for performance (extract only required fields)"
    )
    
    # Performance Monitoring Thresholds (Phase 3 audit requirement)
    performance_threshold_ms: int = Field(
        default=50,  # 5% of 1000ms email processing time
        ge=10,
        le=500,
        description="Performance overhead threshold in milliseconds (5% of typical email processing)"
    )
    
    performance_monitoring_enabled: bool = Field(
        default=True,
        description="Enable performance impact monitoring and alerting"
    )
    
    # PERFORMANCE OPTIMIZATION: Circuit breaker for overhead protection
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker to protect against performance degradation"
    )
    
    circuit_breaker_failure_threshold: int = Field(
        default=3,
        description="Number of failures before circuit breaker opens"
    )
    
    circuit_breaker_recovery_timeout: int = Field(
        default=30,
        description="Seconds before attempting recovery"
    )
    
    memory_usage_threshold_mb: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Memory usage threshold for alerting in megabytes"
    )
    
    connection_pool_wait_threshold_ms: int = Field(
        default=5000,
        ge=100,
        le=30000,
        description="Connection pool wait time threshold in milliseconds"
    )
    
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed storage operations"
    )
    
    retry_delay_ms: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Base delay between retry attempts in milliseconds"
    )
    
    # Batch Processing Settings
    batch_enabled: bool = Field(
        default=True,
        description="Enable batch processing for high-volume scenarios"
    )
    
    batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of records to process in a single batch"
    )
    
    batch_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Maximum time to wait for batch completion"
    )
    
    # Circuit Breaker Settings
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker for tracking service failures"
    )
    
    failure_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of consecutive failures before circuit breaker opens"
    )
    
    recovery_timeout_seconds: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Time before attempting to close circuit breaker"
    )
    
    # Health Check Settings
    health_check_enabled: bool = Field(
        default=True,
        description="Enable health checks for tracking integration"
    )
    
    health_check_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Interval between health checks"
    )
    
    # Data Quality Settings
    data_validation_enabled: bool = Field(
        default=True,
        description="Enable data validation before storage"
    )
    
    fallback_record_creation: bool = Field(
        default=True,
        description="Create fallback records when transformation fails"
    )
    
    max_subject_length: int = Field(
        default=500,
        ge=50,
        le=1000,
        description="Maximum length for email subject field"
    )
    
    max_email_body_length: int = Field(
        default=255,
        ge=50,
        le=500,
        description="Maximum length for email body field"
    )
    
    # Monitoring Settings
    metrics_enabled: bool = Field(
        default=True,
        description="Enable performance metrics collection"
    )
    
    detailed_logging: bool = Field(
        default=False,
        description="Enable detailed logging for debugging"
    )
    
    performance_tracking: bool = Field(
        default=True,
        description="Track performance metrics for integration operations"
    )
    
    # Environment-Specific Settings
    environment: str = Field(
        default="development",
        description="Current environment (development, staging, production)"
    )
    
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode for additional logging and validation"
    )
    
    # Test Mode Settings
    test_mode: bool = Field(
        default=False,
        description="Enable test mode for safe testing"
    )
    
    test_storage_prefix: str = Field(
        default="test_",
        description="Prefix for test data to avoid production conflicts"
    )
    
    @field_validator('environment')
    def validate_environment(cls, v):
        """Validate environment setting."""
        allowed_environments = ['development', 'staging', 'production', 'test']
        if v.lower() not in allowed_environments:
            raise ValueError(f"Environment must be one of {allowed_environments}")
        return v.lower()
    
    @field_validator('storage_timeout_seconds')
    def validate_storage_timeout(cls, v):
        """Ensure storage timeout is reasonable for async operations."""
        if v > 30:
            raise ValueError("Storage timeout should not exceed 30 seconds")
        return v
    
    @field_validator('batch_size')
    def validate_batch_size(cls, v):
        """Validate batch size based on enabled features."""
        if v < 10:
            raise ValueError("Batch size should be at least 10 for efficiency")
        return v
    
    @classmethod
    def from_environment(cls) -> "TrackingIntegrationSettings":
        """Create settings from environment variables."""
        return cls(
            enabled=os.getenv('TRACKING_INTEGRATION_ENABLED', 'true').lower() == 'true',
            async_storage=os.getenv('TRACKING_ASYNC_STORAGE', 'true').lower() == 'true',
            storage_timeout_seconds=int(os.getenv('TRACKING_STORAGE_TIMEOUT', '10')),
            batch_enabled=os.getenv('TRACKING_BATCH_ENABLED', 'true').lower() == 'true',
            batch_size=int(os.getenv('TRACKING_BATCH_SIZE', '50')),
            circuit_breaker_enabled=os.getenv('TRACKING_CIRCUIT_BREAKER', 'true').lower() == 'true',
            environment=os.getenv('ENVIRONMENT', 'development'),
            debug_mode=os.getenv('DEBUG_MODE', 'false').lower() == 'true',
            test_mode=os.getenv('TEST_MODE_ENABLED', 'false').lower() == 'true'
        )
    
    def to_tracking_config(self) -> Dict[str, Any]:
        """Convert to configuration dict for ScenarioTrackingConfiguration."""
        return {
            'enabled': self.enabled,
            'async_insert': self.async_storage,
            'batch_insert_size': self.batch_size if self.batch_enabled else 1,
            'connection_timeout_seconds': self.storage_timeout_seconds,
            'max_retries': self.max_retries,
            'retry_delay_ms': self.retry_delay_ms,
            'enable_circuit_breaker': self.circuit_breaker_enabled,
            'circuit_breaker_failure_threshold': self.failure_threshold,
            'circuit_breaker_recovery_timeout_seconds': self.recovery_timeout_seconds,
            'enable_performance_tracking': self.performance_tracking,
            'environment': self.environment,
            'test_mode': self.test_mode
        }
    
    def get_performance_thresholds(self) -> Dict[str, float]:
        """Get performance thresholds for monitoring."""
        base_thresholds = {
            'storage_latency_ms': 5000.0,  # 5 seconds
            'transformation_latency_ms': 100.0,  # 100ms
            'integration_overhead_percent': 5.0,  # 5% overhead
            'error_rate_percent': 1.0,  # 1% error rate
            'circuit_breaker_trigger_rate': 10.0  # 10% failure rate
        }
        
        # Adjust thresholds based on environment
        if self.environment == 'production':
            base_thresholds['storage_latency_ms'] = 3000.0
            base_thresholds['integration_overhead_percent'] = 3.0
            base_thresholds['error_rate_percent'] = 0.5
        elif self.environment == 'development':
            base_thresholds['storage_latency_ms'] = 10000.0
            base_thresholds['integration_overhead_percent'] = 10.0
        
        return base_thresholds
    
    def get_alerting_config(self) -> Dict[str, Any]:
        """Get alerting configuration for monitoring systems."""
        return {
            'enabled': self.metrics_enabled,
            'integration_health_alerts': self.health_check_enabled,
            'performance_alerts': self.performance_tracking,
            'error_rate_threshold': 5.0,  # Alert if error rate exceeds 5%
            'latency_threshold_ms': self.storage_timeout_seconds * 1000 * 0.8,  # 80% of timeout
            'circuit_breaker_alerts': self.circuit_breaker_enabled,
            'batch_processing_alerts': self.batch_enabled
        }


class EmailProcessorIntegrationSettings(BaseModel):
    """Settings specific to EmailProcessor integration points."""
    
    # Integration Points
    integrate_after_scenario_processing: bool = Field(
        default=True,
        description="Integrate tracking after scenario processing completes"
    )
    
    integrate_on_processing_failure: bool = Field(
        default=True,
        description="Track data even when email processing fails"
    )
    
    # Error Handling
    continue_on_tracking_failure: bool = Field(
        default=True,
        description="Continue email processing if tracking fails"
    )
    
    log_tracking_failures: bool = Field(
        default=True,
        description="Log tracking failures for debugging"
    )
    
    # Data Capture
    capture_scenario_results: bool = Field(
        default=True,
        description="Capture scenario processing results"
    )
    
    capture_intent_classification: bool = Field(
        default=True,
        description="Capture AI intent classification results"
    )
    
    capture_performance_metrics: bool = Field(
        default=True,
        description="Capture processing performance metrics"
    )
    
    # Correlation and Tracing
    use_correlation_ids: bool = Field(
        default=True,
        description="Use correlation IDs for request tracing"
    )
    
    correlation_id_header: str = Field(
        default="X-Correlation-ID",
        description="Header name for correlation ID"
    )


# Default configuration instances
DEFAULT_TRACKING_INTEGRATION_SETTINGS = TrackingIntegrationSettings()
DEFAULT_EMAIL_PROCESSOR_INTEGRATION_SETTINGS = EmailProcessorIntegrationSettings()


def get_integration_settings(
    environment: Optional[str] = None,
    override_settings: Optional[Dict[str, Any]] = None
) -> TrackingIntegrationSettings:
    """
    Get integration settings with environment and override support.
    
    Args:
        environment: Environment to load settings for
        override_settings: Dictionary of settings to override
        
    Returns:
        Configured TrackingIntegrationSettings instance
    """
    # Start with environment-based settings
    if environment:
        settings = TrackingIntegrationSettings.from_environment()
        settings.environment = environment
    else:
        settings = TrackingIntegrationSettings.from_environment()
    
    # Apply overrides if provided
    if override_settings:
        settings_dict = settings.dict()
        settings_dict.update(override_settings)
        settings = TrackingIntegrationSettings(**settings_dict)
    
    return settings


def get_email_processor_integration_settings() -> EmailProcessorIntegrationSettings:
    """Get email processor integration settings."""
    return EmailProcessorIntegrationSettings(
        integrate_after_scenario_processing=os.getenv('INTEGRATE_AFTER_SCENARIO', 'true').lower() == 'true',
        continue_on_tracking_failure=os.getenv('CONTINUE_ON_TRACKING_FAILURE', 'true').lower() == 'true',
        capture_scenario_results=os.getenv('CAPTURE_SCENARIO_RESULTS', 'true').lower() == 'true',
        capture_intent_classification=os.getenv('CAPTURE_INTENT_CLASSIFICATION', 'true').lower() == 'true',
        use_correlation_ids=os.getenv('USE_CORRELATION_IDS', 'true').lower() == 'true'
    )