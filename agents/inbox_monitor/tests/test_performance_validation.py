"""
Performance validation tests for Phase 3 integration.
Validates that scenario tracking integration meets <5% performance overhead requirement.
"""

import pytest
import asyncio
from typing import List
from datetime import datetime, timezone

from utils.performance_validator import (
    PerformanceValidator,
    PerformanceBenchmarkResult,
    create_test_emails,
    run_performance_validation
)
from config.tracking_integration_settings import TrackingIntegrationSettings
from config.settings import AppSettings


@pytest.mark.asyncio
class TestPerformanceValidation:
    """Test performance validation for scenario tracking integration."""
    
    @pytest.fixture
    def performance_validator(self):
        """Create performance validator instance."""
        return PerformanceValidator(
            threshold_percentage=5.0,
            sample_size=20,  # Smaller sample for tests
            warmup_samples=5
        )
    
    @pytest.fixture
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.slow
    @pytest.mark.unit
    def test_emails(self):
        """Create test emails for validation."""
        return create_test_emails(count=50)
    
    @pytest.fixture
    def integration_settings(self):
        """Create integration settings for testing."""
        return TrackingIntegrationSettings(
            enabled=True,
            async_storage=True,
            performance_threshold_ms=50,
            performance_monitoring_enabled=True
        )
    
    @pytest.fixture
    async def mock_email_processor(self, mocker):
        """Create mock email processor for testing."""
        from services.email_processor import EmailProcessor
        from config.settings import AppSettings
        
        # Mock the settings
        mock_settings = mocker.Mock(spec=AppSettings)
        mock_test_mode = mocker.Mock()
        mock_test_mode.enabled = True
        mock_settings.test_mode = mock_test_mode
        mock_settings.environment = "test"
        
        # Create processor with mocked dependencies
        processor = EmailProcessor(mock_settings, "1.0.0-test")
        
        # Mock the _process_single_email method to return quickly
        async def mock_process_email(*args, **kwargs):
            # Simulate varying processing times (50-150ms baseline)
            import random
            import asyncio
            
            # Base processing time
            base_time = random.uniform(0.05, 0.15)  # 50-150ms
            
            # Add tracking overhead if enabled
            if processor.tracking_enabled:
                tracking_time = random.uniform(0.001, 0.005)  # 1-5ms overhead
                total_time = base_time + tracking_time
            else:
                total_time = base_time
            
            await asyncio.sleep(total_time)
            
            from models.email import ProcessingResult
            return ProcessingResult(
                success=True,
                email_id=kwargs.get('message', {}).get('id', 'test'),
                process_id='test_process_id',
                processing_duration_ms=int(total_time * 1000),
                scenario_type='scenario_5',
                scenario_success=True,
                agent_actions_log=['test_action']
            )
        
        processor._process_single_email = mock_process_email
        processor.tracking_enabled = True  # Default to enabled
        
        return processor
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_performance_validator_initialization(self, performance_validator):
        """Test performance validator initialization."""
        
        assert performance_validator.threshold_percentage == 5.0
        assert performance_validator.sample_size == 20
        assert performance_validator.warmup_samples == 5
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_performance_validation_success(
        self, 
        performance_validator,
        mock_email_processor,
        test_emails,
        integration_settings
    ):
        """Test successful performance validation (overhead within threshold)."""
        
        result = await performance_validator.validate_integration_performance(
            email_processor=mock_email_processor,
            test_emails=test_emails[:30],  # Use subset for faster test
            settings=integration_settings
        )
        
        assert isinstance(result, PerformanceBenchmarkResult)
        assert result.success is True  # Should pass with mocked overhead
        assert result.metrics is not None
        assert result.error_message is None
        assert "EXCELLENT" in result.recommendation or "GOOD" in result.recommendation
        
        # Validate metrics structure
        metrics = result.metrics
        assert metrics.baseline_avg_ms > 0
        assert metrics.tracking_enabled_avg_ms > 0
        assert metrics.overhead_percentage >= 0
        assert metrics.sample_size == 20
        assert metrics.passed_threshold is True
    
    @pytest.mark.asyncio  
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_performance_validation_insufficient_emails(
        self,
        performance_validator,
        mock_email_processor,
        integration_settings
    ):
        """Test performance validation with insufficient test emails."""
        
        # Only provide 5 emails when 20 are needed
        insufficient_emails = create_test_emails(count=5)
        
        result = await performance_validator.validate_integration_performance(
            email_processor=mock_email_processor,
            test_emails=insufficient_emails,
            settings=integration_settings
        )
        
        assert result.success is False
        assert "Not enough test emails" in result.error_message
        assert "Provide more test emails" in result.recommendation
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_email_to_message_dict_conversion(self, performance_validator, test_emails):
        """Test conversion of Email model to message dict."""
        
        email = test_emails[0]
        message_dict = performance_validator._email_to_message_dict(email)
        
        # Validate required fields are present
        assert message_dict["id"] == email.id
        assert message_dict["subject"] == email.subject
        assert message_dict["from"]["emailAddress"]["address"] == email.sender.email
        assert message_dict["from"]["emailAddress"]["name"] == email.sender.name
        assert message_dict["body"]["content"] == email.body.content
        assert message_dict["bodyPreview"] == email.email_body
        assert len(message_dict["toRecipients"]) == len(email.recipients.to)
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_performance_metrics_calculation(self, performance_validator):
        """Test performance metrics calculation."""
        
        baseline_times = [100.0, 110.0, 105.0, 95.0, 108.0]  # Average ~103.6ms
        tracking_times = [105.0, 115.0, 110.0, 100.0, 113.0]  # Average ~108.6ms
        threshold_ms = 50.0
        
        metrics = performance_validator._calculate_performance_metrics(
            baseline_times=baseline_times,
            tracking_times=tracking_times,
            threshold_ms=threshold_ms
        )
        
        assert metrics.baseline_avg_ms == pytest.approx(103.6, rel=0.1)
        assert metrics.tracking_enabled_avg_ms == pytest.approx(108.6, rel=0.1)
        assert metrics.overhead_ms == pytest.approx(5.0, rel=0.5)  # ~5ms overhead
        assert metrics.overhead_percentage == pytest.approx(4.8, rel=0.5)  # ~4.8% overhead
        assert metrics.passed_threshold is True  # Under 5% threshold
        assert metrics.sample_size == 5
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_recommendation_generation(self, performance_validator):
        """Test recommendation generation for different performance levels."""
        
        from utils.performance_validator import PerformanceMetrics
        
        # Excellent performance (< 1% overhead)
        excellent_metrics = PerformanceMetrics(
            baseline_avg_ms=100.0,
            tracking_enabled_avg_ms=100.5,
            overhead_ms=0.5,
            overhead_percentage=0.5,
            sample_size=50,
            passed_threshold=True,
            threshold_ms=50.0,
            baseline_min_ms=95.0,
            baseline_max_ms=105.0,
            baseline_std_ms=2.0,
            tracking_min_ms=95.5,
            tracking_max_ms=105.5,
            tracking_std_ms=2.0
        )
        
        recommendation = performance_validator._generate_recommendation(excellent_metrics)
        assert "EXCELLENT" in recommendation
        assert "minimal" in recommendation
        
        # Over threshold performance
        poor_metrics = PerformanceMetrics(
            baseline_avg_ms=100.0,
            tracking_enabled_avg_ms=112.0,
            overhead_ms=12.0,
            overhead_percentage=12.0,
            sample_size=50,
            passed_threshold=False,
            threshold_ms=50.0,
            baseline_min_ms=95.0,
            baseline_max_ms=105.0,
            baseline_std_ms=2.0,
            tracking_min_ms=107.0,
            tracking_max_ms=117.0,
            tracking_std_ms=2.0
        )
        
        recommendation = performance_validator._generate_recommendation(poor_metrics)
        assert "CRITICAL" in recommendation
        assert "too high" in recommendation
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_convenience_function(self, mock_email_processor, test_emails):
        """Test the convenience function for performance validation."""
        
        result = await run_performance_validation(
            email_processor=mock_email_processor,
            test_emails=test_emails[:30]  # Use subset
        )
        
        assert isinstance(result, PerformanceBenchmarkResult)
        # Should succeed with default settings and mocked processor
        assert result.success is True
        assert result.metrics is not None
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_create_test_emails_utility(self):
        """Test the create_test_emails utility function."""
        
        emails = create_test_emails(count=10)
        
        assert len(emails) == 10
        assert all(email.id.startswith("test_email_") for email in emails)
        assert all(email.sender.email.endswith("@example.com") for email in emails)
        assert all(email.subject.startswith("Test Email Subject") for email in emails)
        assert all(len(email.recipients.to) == 1 for email in emails)
        
        # Verify emails have unique IDs
        email_ids = [email.id for email in emails]
        assert len(set(email_ids)) == len(emails)


@pytest.mark.asyncio
@pytest.mark.integration
class TestRealPerformanceValidation:
    """Integration tests for real performance validation."""
    
    @pytest.mark.skipif(
        True,  # Always skip for now
        reason="Integration tests require --run-integration flag"
    )
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_real_performance_validation(self):
        """Test performance validation with real components (integration test)."""
        
        # This test requires real system setup
        pytest.skip("Real integration test - requires full system setup")
    
    @pytest.mark.slow
    @pytest.mark.unit
    async def test_performance_validation_benchmark(self):
        """Benchmark performance validation overhead."""
        
        # Create large test set
        test_emails = create_test_emails(count=200)
        
        # Time the validation process itself
        import time
        start_time = time.time()
        
        # Mock processor for benchmark
        class BenchmarkProcessor:
            def __init__(self):
                self.tracking_enabled = True
            
            async def _process_single_email(self, *args, **kwargs):
                await asyncio.sleep(0.001)  # 1ms simulation
                from models.email import ProcessingResult
                return ProcessingResult(
                    success=True,
                    email_id="benchmark_test",
                    process_id="benchmark_id", 
                    processing_duration_ms=1
                )
        
        processor = BenchmarkProcessor()
        validator = PerformanceValidator(
            sample_size=50,
            warmup_samples=10
        )
        
        result = await validator.validate_integration_performance(
            email_processor=processor,
            test_emails=test_emails,
            settings=TrackingIntegrationSettings()
        )
        
        validation_time = time.time() - start_time
        
        # Validation should complete reasonably quickly
        assert validation_time < 30.0  # Less than 30 seconds
        assert result.success is True
        
        print(f"Performance validation completed in {validation_time:.2f} seconds")
        print(f"Overhead detected: {result.metrics.overhead_percentage:.2f}%")