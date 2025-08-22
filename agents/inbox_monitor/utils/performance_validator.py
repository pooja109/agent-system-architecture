"""
Performance validation utilities for Phase 3 integration.
Measures and validates performance impact of scenario tracking integration.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from pydantic import BaseModel

try:
    from services.email_processor import EmailProcessor
    from models.email import Email, ProcessingResult
    from config.tracking_integration_settings import TrackingIntegrationSettings
except ImportError:
    from ..services.email_processor import EmailProcessor
    from ..models.email import Email, ProcessingResult  
    from ..config.tracking_integration_settings import TrackingIntegrationSettings

logger = structlog.get_logger(__name__)


class PerformanceMetrics(BaseModel):
    """Performance measurement results."""
    
    baseline_avg_ms: float
    tracking_enabled_avg_ms: float
    overhead_ms: float
    overhead_percentage: float
    sample_size: int
    passed_threshold: bool
    threshold_ms: float
    
    # Detailed statistics
    baseline_min_ms: float
    baseline_max_ms: float
    baseline_std_ms: float
    tracking_min_ms: float
    tracking_max_ms: float
    tracking_std_ms: float


@dataclass
class PerformanceBenchmarkResult:
    """Result of performance benchmark."""
    
    success: bool
    metrics: Optional[PerformanceMetrics]
    error_message: Optional[str]
    test_duration_seconds: float
    recommendation: str


class PerformanceValidator:
    """Validates performance impact of scenario tracking integration."""
    
    def __init__(
        self,
        threshold_percentage: float = 5.0,
        sample_size: int = 50,
        warmup_samples: int = 10
    ):
        """
        Initialize performance validator.
        
        Args:
            threshold_percentage: Maximum acceptable overhead percentage (default 5%)
            sample_size: Number of samples to collect for each test
            warmup_samples: Number of warmup samples to discard
        """
        self.threshold_percentage = threshold_percentage
        self.sample_size = sample_size
        self.warmup_samples = warmup_samples
        self.logger = structlog.get_logger(__name__)
    
    async def validate_integration_performance(
        self,
        email_processor: EmailProcessor,
        test_emails: List[Email],
        settings: TrackingIntegrationSettings
    ) -> PerformanceBenchmarkResult:
        """
        Validate performance impact of tracking integration.
        
        Args:
            email_processor: EmailProcessor instance to test
            test_emails: List of test emails to process
            settings: Integration settings
            
        Returns:
            PerformanceBenchmarkResult with validation results
        """
        test_start = time.time()
        
        try:
            self.logger.info(
                "Starting performance validation",
                threshold_pct=self.threshold_percentage,
                sample_size=self.sample_size,
                test_emails=len(test_emails)
            )
            
            # Ensure we have enough test emails
            if len(test_emails) < self.sample_size:
                return PerformanceBenchmarkResult(
                    success=False,
                    metrics=None,
                    error_message=f"Not enough test emails: {len(test_emails)} < {self.sample_size}",
                    test_duration_seconds=time.time() - test_start,
                    recommendation="Provide more test emails for reliable performance measurement"
                )
            
            # Test 1: Baseline performance (tracking disabled)
            self.logger.info("Measuring baseline performance (tracking disabled)")
            baseline_times = await self._measure_processing_times(
                email_processor=email_processor,
                test_emails=test_emails,
                tracking_enabled=False,
                label="baseline"
            )
            
            if not baseline_times:
                return PerformanceBenchmarkResult(
                    success=False,
                    metrics=None,
                    error_message="Failed to collect baseline performance data",
                    test_duration_seconds=time.time() - test_start,
                    recommendation="Check email processor configuration and test data"
                )
            
            # Test 2: Performance with tracking enabled
            self.logger.info("Measuring performance with tracking enabled")
            tracking_times = await self._measure_processing_times(
                email_processor=email_processor,
                test_emails=test_emails,
                tracking_enabled=True,
                label="tracking_enabled"
            )
            
            if not tracking_times:
                return PerformanceBenchmarkResult(
                    success=False,
                    metrics=None,
                    error_message="Failed to collect tracking performance data",
                    test_duration_seconds=time.time() - test_start,
                    recommendation="Check tracking integration configuration"
                )
            
            # Calculate metrics
            metrics = self._calculate_performance_metrics(
                baseline_times=baseline_times,
                tracking_times=tracking_times,
                threshold_ms=settings.performance_threshold_ms
            )
            
            # Determine success and recommendation
            success = metrics.passed_threshold
            recommendation = self._generate_recommendation(metrics)
            
            self.logger.info(
                "Performance validation completed",
                success=success,
                overhead_pct=metrics.overhead_percentage,
                threshold_pct=self.threshold_percentage,
                baseline_avg=metrics.baseline_avg_ms,
                tracking_avg=metrics.tracking_enabled_avg_ms
            )
            
            return PerformanceBenchmarkResult(
                success=success,
                metrics=metrics,
                error_message=None,
                test_duration_seconds=time.time() - test_start,
                recommendation=recommendation
            )
            
        except Exception as e:
            self.logger.error(
                "Performance validation failed",
                error=str(e),
                error_type=type(e).__name__
            )
            
            return PerformanceBenchmarkResult(
                success=False,
                metrics=None,
                error_message=f"Validation failed: {str(e)}",
                test_duration_seconds=time.time() - test_start,
                recommendation="Check system configuration and try again"
            )
    
    async def _measure_processing_times(
        self,
        email_processor: EmailProcessor,
        test_emails: List[Email],
        tracking_enabled: bool,
        label: str
    ) -> List[float]:
        """Measure processing times for a set of emails."""
        
        # Configure tracking state
        original_tracking_enabled = email_processor.tracking_enabled
        email_processor.tracking_enabled = tracking_enabled
        
        try:
            processing_times = []
            
            # Warmup phase
            self.logger.debug(f"Warmup phase for {label} ({self.warmup_samples} samples)")
            for i in range(self.warmup_samples):
                if i >= len(test_emails):
                    break
                await self._process_single_email_timed(email_processor, test_emails[i])
            
            # Measurement phase
            self.logger.debug(f"Measurement phase for {label} ({self.sample_size} samples)")
            for i in range(self.sample_size):
                if i >= len(test_emails):
                    # Cycle through emails if we have fewer than sample_size
                    email_index = i % len(test_emails)
                else:
                    email_index = i
                
                processing_time = await self._process_single_email_timed(
                    email_processor, test_emails[email_index]
                )
                
                if processing_time is not None:
                    processing_times.append(processing_time)
                
                # Brief pause to prevent overwhelming the system
                await asyncio.sleep(0.01)
            
            self.logger.info(
                f"Collected {len(processing_times)} samples for {label}",
                avg_time_ms=statistics.mean(processing_times) if processing_times else 0,
                min_time_ms=min(processing_times) if processing_times else 0,
                max_time_ms=max(processing_times) if processing_times else 0
            )
            
            return processing_times
            
        finally:
            # Restore original tracking state
            email_processor.tracking_enabled = original_tracking_enabled
    
    async def _process_single_email_timed(
        self,
        email_processor: EmailProcessor,
        email: Email
    ) -> Optional[float]:
        """Process a single email and measure the time."""
        
        try:
            # Convert Email model to dict format expected by processor
            message_dict = self._email_to_message_dict(email)
            
            start_time = time.time()
            
            # Process the email (this is a simplified version for testing)
            result = await email_processor._process_single_email(
                message=message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            end_time = time.time()
            processing_duration_ms = (end_time - start_time) * 1000
            
            return processing_duration_ms
            
        except Exception as e:
            self.logger.warning(
                "Failed to process email during timing",
                error=str(e),
                email_id=email.id
            )
            return None
    
    def _email_to_message_dict(self, email: Email) -> Dict[str, Any]:
        """Convert Email model to dict format for processing."""
        
        return {
            "id": email.id,
            "subject": email.subject,
            "from": {
                "emailAddress": {
                    "address": email.sender.email,
                    "name": email.sender.name
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": recipient.email,
                        "name": recipient.name
                    }
                }
                for recipient in email.recipients.to
            ],
            "body": {
                "contentType": email.body.content_type,
                "content": email.body.content
            },
            "bodyPreview": email.email_body,
            "receivedDateTime": email.received_datetime.isoformat(),
            "hasAttachments": email.has_attachments,
            "importance": email.importance.value,
            "conversationId": email.conversation_id
        }
    
    def _calculate_performance_metrics(
        self,
        baseline_times: List[float],
        tracking_times: List[float],
        threshold_ms: float
    ) -> PerformanceMetrics:
        """Calculate performance metrics from timing data."""
        
        # Basic statistics
        baseline_avg = statistics.mean(baseline_times)
        tracking_avg = statistics.mean(tracking_times)
        
        baseline_min = min(baseline_times)
        baseline_max = max(baseline_times)
        baseline_std = statistics.stdev(baseline_times) if len(baseline_times) > 1 else 0.0
        
        tracking_min = min(tracking_times)
        tracking_max = max(tracking_times)
        tracking_std = statistics.stdev(tracking_times) if len(tracking_times) > 1 else 0.0
        
        # Performance impact calculation
        overhead_ms = tracking_avg - baseline_avg
        overhead_percentage = (overhead_ms / baseline_avg) * 100 if baseline_avg > 0 else 0
        
        # Threshold validation
        passed_threshold = overhead_percentage <= self.threshold_percentage
        
        return PerformanceMetrics(
            baseline_avg_ms=baseline_avg,
            tracking_enabled_avg_ms=tracking_avg,
            overhead_ms=overhead_ms,
            overhead_percentage=overhead_percentage,
            sample_size=min(len(baseline_times), len(tracking_times)),
            passed_threshold=passed_threshold,
            threshold_ms=threshold_ms,
            baseline_min_ms=baseline_min,
            baseline_max_ms=baseline_max,
            baseline_std_ms=baseline_std,
            tracking_min_ms=tracking_min,
            tracking_max_ms=tracking_max,
            tracking_std_ms=tracking_std
        )
    
    def _generate_recommendation(self, metrics: PerformanceMetrics) -> str:
        """Generate performance recommendation based on metrics."""
        
        if metrics.passed_threshold:
            if metrics.overhead_percentage < 1.0:
                return f"✅ EXCELLENT: Tracking overhead is minimal ({metrics.overhead_percentage:.2f}%). Performance impact is negligible."
            elif metrics.overhead_percentage < 3.0:
                return f"✅ GOOD: Tracking overhead is acceptable ({metrics.overhead_percentage:.2f}%). Within performance requirements."
            else:
                return f"✅ ACCEPTABLE: Tracking overhead is within threshold ({metrics.overhead_percentage:.2f}%). Monitor for optimization opportunities."
        else:
            if metrics.overhead_percentage > 10.0:
                return f"❌ CRITICAL: Tracking overhead is too high ({metrics.overhead_percentage:.2f}%). Immediate optimization required."
            elif metrics.overhead_percentage > 7.5:
                return f"⚠️ HIGH: Tracking overhead exceeds threshold ({metrics.overhead_percentage:.2f}%). Consider disabling async operations or reducing batch size."
            else:
                return f"⚠️ MODERATE: Tracking overhead slightly exceeds threshold ({metrics.overhead_percentage:.2f}%). Minor optimizations recommended."


async def run_performance_validation(
    email_processor: EmailProcessor,
    test_emails: List[Email],
    settings: Optional[TrackingIntegrationSettings] = None
) -> PerformanceBenchmarkResult:
    """
    Convenience function to run performance validation.
    
    Args:
        email_processor: EmailProcessor instance
        test_emails: Test emails for validation
        settings: Integration settings (defaults created if None)
        
    Returns:
        PerformanceBenchmarkResult
    """
    
    if settings is None:
        settings = TrackingIntegrationSettings()
    
    validator = PerformanceValidator()
    
    return await validator.validate_integration_performance(
        email_processor=email_processor,
        test_emails=test_emails,
        settings=settings
    )


def create_test_emails(count: int = 100) -> List[Email]:
    """Create test emails for performance validation."""
    
    from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata
    from datetime import datetime, timezone
    import uuid
    
    test_emails = []
    
    for i in range(count):
        email = Email(
            id=f"test_email_{i}_{uuid.uuid4()}",
            conversation_id=f"conversation_{i % 10}",
            received_datetime=datetime.now(timezone.utc),
            sender=EmailSender(
                email=f"customer{i % 20}@example.com",
                name=f"Test Customer {i % 20}"
            ),
            recipients=EmailRecipients(
                to=[EmailRecipient(
                    email="lowtouch@microsoft.com",
                    name="LowTouch Support"
                )]
            ),
            subject=f"Test Email Subject {i}",
            body=EmailBody(
                content_type="text",
                content=f"This is test email content {i} for performance validation testing."
            ),
            email_body=f"Test email preview {i}",
            processing_metadata=ProcessingMetadata(
                process_id=str(uuid.uuid4()),
                monitor_version="1.0.0"
            )
        )
        
        test_emails.append(email)
    
    return test_emails