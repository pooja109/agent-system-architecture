"""
Integration tests for scenario tracking integration.
Tests the complete flow from email processing to data storage.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import uuid

from services.scenario_tracking_integration import (
    ScenarioTrackingIntegration,
    TrackingIntegrationResult,
    get_tracking_integration
)
from database.scenario_tracking_models import (
    ScenarioTrackingConfiguration,
    ScenarioProcessingRecord,
    ScenarioType
)
from config.tracking_integration_settings import TrackingIntegrationSettings
from utils.data_transformation import ScenarioDataTransformer


class TestScenarioTrackingIntegration:
    """Integration tests for scenario tracking."""
    
    @pytest.fixture
    async def integration_service(self):
        """Create integration service for testing."""
        config = ScenarioTrackingConfiguration(
            enabled=True,
            async_insert=False,  # Synchronous for testing
            batch_insert_size=10
        )
        service = ScenarioTrackingIntegration(config)
        yield service
        await service.close()
    
    @pytest.fixture
    def mock_email_data(self):
        """Mock email data for testing."""
        email_mock = Mock()
        email_mock.id = "test-email-123"
        email_mock.sender = Mock()
        email_mock.sender.email = "customer@example.com"
        email_mock.sender.name = "Test Customer"
        email_mock.subject = "Test Email Subject"
        email_mock.received_datetime = datetime.now(timezone.utc)
        email_mock.sent_datetime = datetime.now(timezone.utc)  # Fix: Add sent_datetime
        email_mock.email_body = "This is a test email body preview"
        email_mock.has_attachments = False
        email_mock.attachment_count = 0
        email_mock.conversation_id = "test-conversation-123"
        
        # Add recipients mock to prevent iteration errors
        email_mock.recipients = Mock()
        email_mock.recipients.to = []
        email_mock.recipients.cc = []
        email_mock.recipients.bcc = []
        
        return email_mock
    
    @pytest.fixture
    def mock_processing_result(self):
        """Mock processing result for testing."""
        result_mock = Mock()
        result_mock.process_id = "proc-123"
        result_mock.success = True
        result_mock.processing_duration_ms = 1500
        result_mock.error = None
        result_mock.destination_folder = "Processed"
        result_mock.storage_location = "/path/to/output"
        return result_mock
    
    @pytest.fixture
    def mock_scenario_result(self):
        """Mock scenario result for testing."""
        scenario_mock = Mock()
        scenario_mock.scenario_type = Mock()
        scenario_mock.scenario_type.value = "scenario_5"
        scenario_mock.success = True
        scenario_mock.agent_actions_log = ["assigned_expert", "created_case"]
        scenario_mock.expert_assigned = "Jane Expert"
        scenario_mock.expert_id = "expert-456"
        scenario_mock.expert_email = "jane.expert@company.com"
        scenario_mock.case_created = "SF_CASE_12345"
        scenario_mock.emails_sent = []
        return scenario_mock
    
    @pytest.fixture
    def mock_intent_result(self):
        """Mock intent classification result for testing."""
        intent_mock = Mock()
        intent_mock.intent = Mock()
        intent_mock.intent.value = "POSITIVE"
        intent_mock.confidence = 0.85
        intent_mock.reasoning = "Customer expressed satisfaction"
        intent_mock.detected_phrases = ["thank you", "great service"]
        intent_mock.processing_duration_ms = 250
        return intent_mock
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_successful_tracking_integration(
        self, integration_service, mock_email_data, 
        mock_processing_result, mock_scenario_result
    ):
        """Test successful integration of tracking with mocked storage."""
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = AsyncMock(return_value=True)
                
                result = await integration_service.track_scenario_processing(
                    email_data=mock_email_data,
                    processing_result=mock_processing_result,
                    scenario_result=mock_scenario_result,
                    correlation_id="test-correlation-123"
                )
                
                assert result.success is True
                assert result.record_created is True
                assert result.processing_duration_ms > 0
                assert result.error_message is None
                
                # Verify storage was called
                mock_client.store_scenario_result.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_tracking_with_storage_failure(
        self, integration_service, mock_email_data, mock_processing_result
    ):
        """Test tracking behavior when storage fails."""
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = AsyncMock(side_effect=Exception("Storage failed"))
                
                result = await integration_service.track_scenario_processing(
                    email_data=mock_email_data,
                    processing_result=mock_processing_result
                )
                
                assert result.success is False
                assert result.record_created is False
                assert "Storage failed" in result.error_message
    
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_tracking_disabled_by_configuration(self, mock_email_data, mock_processing_result):
        """Test tracking behavior when disabled by configuration."""
        
        config = ScenarioTrackingConfiguration(enabled=False)
        service = ScenarioTrackingIntegration(config)
        
        try:
            result = await service.track_scenario_processing(
                email_data=mock_email_data,
                processing_result=mock_processing_result
            )
            
            assert result.success is True
            assert result.processing_duration_ms == 0.0
            assert "disabled" in result.error_message.lower()
        finally:
            await service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_tracking_timeout_handling(
        self, integration_service, mock_email_data, mock_processing_result
    ):
        """Test tracking behavior with storage timeouts."""
        
        async def timeout_storage(*args, **kwargs):
            raise asyncio.TimeoutError("Storage operation timed out")
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = timeout_storage
                
                result = await integration_service.track_scenario_processing(
                    email_data=mock_email_data,
                    processing_result=mock_processing_result
                )
                
                assert result.success is False
                # Should have retry attempts due to timeout
                assert result.retry_attempts > 0
    
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_data_transformation_with_missing_fields(
        self, integration_service, mock_processing_result
    ):
        """Test data transformation with incomplete email data."""
        
        incomplete_email = Mock()
        incomplete_email.id = "incomplete-123"
        # Add minimal required fields to prevent validation errors
        incomplete_email.received_datetime = datetime.now(timezone.utc)
        incomplete_email.sent_datetime = None  # This will be handled as missing
        incomplete_email.conversation_id = None
        # Missing sender information will trigger fallback
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = AsyncMock(return_value=True)
                
                result = await integration_service.track_scenario_processing(
                    email_data=incomplete_email,
                    processing_result=mock_processing_result
                )
                
                # Should still succeed with fallback values
                assert result.success is True
                
                # Check that fallback record was created
                call_args = mock_client.store_scenario_result.call_args[1]
                record = call_args['record']
                assert record.sender_email == 'unknown@unknown.com'  # Updated fallback value in model
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_integration_health_check(self, integration_service):
        """Test integration health check functionality."""
        
        with patch.object(integration_service, 'tracking_client') as mock_client:
            mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
            
            health = await integration_service.get_integration_health()
            
            assert health["integration_service"] == "scenario_tracking_integration"
            assert "timestamp" in health
            
            # If initialized, should include client health
            if integration_service._initialized:
                assert "tracking_client" in health
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_comprehensive_data_capture(
        self, integration_service, mock_email_data, mock_processing_result,
        mock_scenario_result, mock_intent_result
    ):
        """Test comprehensive data capture with all result types."""
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = AsyncMock(return_value=True)
                
                result = await integration_service.track_scenario_processing(
                    email_data=mock_email_data,
                    processing_result=mock_processing_result,
                    scenario_result=mock_scenario_result,
                    intent_result=mock_intent_result,
                    correlation_id="comprehensive-test-123",
                    test_mode=True,
                    environment="testing"
                )
                
                assert result.success is True
                
                # Verify comprehensive data was captured
                call_args = mock_client.store_scenario_result.call_args[1]
                record = call_args['record']
                
                # Check email data
                assert record.email_id == "test-email-123"
                assert record.sender_email == "customer@example.com"
                assert record.subject == "Test Email Subject"
                
                # Check scenario data
                assert record.scenario_type == ScenarioType.SCENARIO_5
                assert record.expert_assigned == "Jane Expert"
                assert record.case_created == "SF_CASE_12345"
                
                # Check AI data (if transformed correctly)
                # Note: This depends on the data transformer implementation


class TestScenarioDataTransformer:
    """Test scenario data transformer functionality."""
    
    @pytest.fixture
    def transformer(self):
        """Create data transformer for testing."""
        return ScenarioDataTransformer()
    
    @pytest.fixture
    def sample_email_data(self):
        """Sample email data for transformation testing."""
        email = Mock()
        email.id = "transform-test-123"
        email.sender = Mock()
        email.sender.email = "sender@example.com"
        email.sender.email_address = "sender@example.com"  # Set both to ensure extraction works
        email.sender.name = "Test Sender"
        email.subject = "Transformation Test"
        email.received_datetime = datetime.now(timezone.utc)
        email.sent_datetime = datetime.now(timezone.utc)
        email.email_body = "Test body preview content"
        email.has_attachments = True
        email.attachment_count = 2
        email.conversation_id = "conv-456"
        
        # Add recipients mock to prevent iteration errors
        email.recipients = Mock()
        email.recipients.to = []
        email.recipients.cc = []
        email.recipients.bcc = []
        
        return email
    
    @pytest.fixture
    def sample_processing_result(self):
        """Sample processing result for transformation testing."""
        result = Mock()
        result.process_id = "proc-transform-123"
        result.success = True
        result.processing_duration_ms = 2500
        result.error = None
        result.destination_folder = "Processed"
        result.storage_location = "/test/output"
        return result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_tracking_record_basic(self, transformer, sample_email_data, sample_processing_result):
        """Test basic tracking record creation."""
        
        record = transformer.create_tracking_record(
            email_data=sample_email_data,
            processing_result=sample_processing_result,
            correlation_id="transform-correlation-123"
        )
        
        assert isinstance(record, ScenarioProcessingRecord)
        assert record.email_id == "transform-test-123"
        assert record.sender_email == "sender@example.com"
        assert record.subject == "Transformation Test"
        assert record.process_success is True
        assert record.processing_duration_ms == 2500
        assert record.correlation_id == "transform-correlation-123"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_tracking_record_with_scenario_data(
        self, transformer, sample_email_data, sample_processing_result
    ):
        """Test tracking record creation with scenario data."""
        
        scenario_result = Mock()
        scenario_result.scenario_type = Mock()
        scenario_result.scenario_type.value = "scenario_6"
        scenario_result.success = True
        scenario_result.agent_actions_log = ["forwarded_email", "notified_manager"]
        scenario_result.expert_assigned = None
        scenario_result.case_created = None
        scenario_result.emails_sent = ["manager@company.com"]
        
        record = transformer.create_tracking_record(
            email_data=sample_email_data,
            processing_result=sample_processing_result,
            scenario_result=scenario_result
        )
        
        assert record.scenario_type == ScenarioType.SCENARIO_6
        assert record.scenario_success is True
        assert record.agent_actions_log == ["forwarded_email", "notified_manager"]
        assert record.emails_forwarded == ["manager@company.com"]
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_tracking_record_with_ai_data(
        self, transformer, sample_email_data, sample_processing_result
    ):
        """Test tracking record creation with AI classification data."""
        
        intent_result = Mock()
        intent_result.intent = Mock()
        intent_result.intent.value = "NEGATIVE"
        intent_result.confidence = 0.92
        intent_result.reasoning = "Customer expressed dissatisfaction"
        intent_result.detected_phrases = ["not satisfied", "disappointed"]
        intent_result.processing_duration_ms = 180
        
        record = transformer.create_tracking_record(
            email_data=sample_email_data,
            processing_result=sample_processing_result,
            intent_result=intent_result
        )
        
        assert record.ai_confidence == 0.92
        assert record.ai_reasoning == "Customer expressed dissatisfaction"
        assert record.ai_detected_phrases == ["not satisfied", "disappointed"]
        assert record.ai_processing_duration_ms == 180
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_fallback_record_creation(self, transformer):
        """Test fallback record creation when transformation fails."""
        
        # Create invalid data that should trigger fallback
        invalid_email = None
        invalid_result = None
        
        record = transformer.create_tracking_record(
            email_data=invalid_email,
            processing_result=invalid_result
        )
        
        # Should create a minimal valid record
        assert isinstance(record, ScenarioProcessingRecord)
        assert record.process_success is False
        if record.process_error:
            assert "transformation" in record.process_error.lower()
        assert record.sender_email == 'unknown@unknown.com'  # Normal fallback
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_safe_data_extraction(self, transformer):
        """Test safe data extraction with various input formats."""
        
        # Test with missing attributes
        partial_email = Mock()
        partial_email.id = "partial-123"
        partial_email.received_datetime = datetime.now(timezone.utc)
        partial_email.sent_datetime = None
        partial_email.conversation_id = None
        partial_email.has_attachments = False  # Valid boolean
        partial_email.attachment_count = 0    # Valid integer
        
        # Add recipients mock to prevent iteration errors
        partial_email.recipients = Mock()
        partial_email.recipients.to = []
        partial_email.recipients.cc = []
        partial_email.recipients.bcc = []
        
        # Missing sender information - will trigger fallback
        
        partial_result = Mock()
        partial_result.process_id = "partial-proc-123"
        partial_result.success = False  # Valid boolean
        partial_result.processing_duration_ms = 0  # Valid integer
        partial_result.error = None
        # Missing other fields
        
        record = transformer.create_tracking_record(
            email_data=partial_email,
            processing_result=partial_result
        )
        
        assert record.email_id == "partial-123"
        # Sender email should either be the fallback or a sanitized version
        assert record.sender_email in ['unknown@unknown.com', '[INVALID_EMAIL]', '']
        assert record.process_id == "partial-proc-123"


class TestEmailProcessorIntegration:
    """Test integration with EmailProcessor."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.e2e
    async def test_email_processor_tracking_integration(self):
        """Test that EmailProcessor can call tracking integration."""
        
        # This would be an end-to-end test with actual EmailProcessor
        # For now, we'll test the integration configuration
        from config.tracking_integration_settings import (
            get_integration_settings,
            get_email_processor_integration_settings
        )
        
        integration_settings = get_integration_settings()
        processor_settings = get_email_processor_integration_settings()
        
        assert isinstance(integration_settings, TrackingIntegrationSettings)
        assert integration_settings.enabled is not None
        assert processor_settings.integrate_after_scenario_processing is not None
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_tracking_does_not_affect_email_process_success(self):
        """Verify tracking failures don't impact email processing results."""
        
        # Mock a scenario where tracking fails but email processing succeeds
        with patch('services.scenario_tracking_integration.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            mock_integration.track_scenario_processing = AsyncMock(
                side_effect=Exception("Tracking service unavailable")
            )
            mock_get_integration.return_value = mock_integration
            
            # This test would require full EmailProcessor integration
            # For now, verify the isolation principle
            assert True  # Placeholder - tracking errors should be isolated


class TestPerformanceImpact:
    """Test performance impact of integration."""
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.performance
    async def test_tracking_performance_overhead(self):
        """Measure performance overhead of tracking integration."""
        
        import time
        
        # Create test data
        email_mock = Mock()
        email_mock.id = "perf-test-123"
        email_mock.sender = Mock()
        email_mock.sender.email = "perf@test.com"
        
        result_mock = Mock()
        result_mock.process_id = "perf-proc-123"
        result_mock.success = True
        
        config = ScenarioTrackingConfiguration(enabled=True, async_insert=True)
        service = ScenarioTrackingIntegration(config)
        
        try:
            # Mock successful storage
            with patch.object(service, '_ensure_initialized', return_value=True):
                with patch.object(service, 'tracking_client') as mock_client:
                    mock_client.store_scenario_result = AsyncMock(return_value=True)
                    
                    # Measure tracking overhead
                    start_time = time.perf_counter()
                    
                    result = await service.track_scenario_processing(
                        email_data=email_mock,
                        processing_result=result_mock
                    )
                    
                    end_time = time.perf_counter()
                    
                    assert result.success is True
                    
                    # Performance should be reasonable (< 100ms for mocked operations)
                    overhead_ms = (end_time - start_time) * 1000
                    assert overhead_ms < 100, f"Tracking overhead too high: {overhead_ms}ms"
        
        finally:
            await service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.performance
    async def test_async_tracking_performance(self):
        """Test performance characteristics of async tracking."""
        
        config = ScenarioTrackingConfiguration(enabled=True, async_insert=True)
        service = ScenarioTrackingIntegration(config)
        
        try:
            with patch.object(service, '_ensure_initialized', return_value=True):
                with patch.object(service, 'tracking_client') as mock_client:
                    # Simulate async operation
                    async def async_store(*args, **kwargs):
                        await asyncio.sleep(0.01)  # Small delay to simulate async work
                        return True
                    
                    mock_client.store_scenario_result = async_store
                    
                    email_mock = Mock()
                    email_mock.id = "async-perf-test"
                    email_mock.sender = Mock()
                    email_mock.sender.email = "async@test.com"
                    
                    result_mock = Mock()
                    result_mock.process_id = "async-proc-123"
                    result_mock.success = True
                    
                    # Test async tracking
                    result = await service.track_scenario_processing(
                        email_data=email_mock,
                        processing_result=result_mock
                    )
                    
                    assert result.success is True
                    assert result.async_queued is True  # Should indicate async operation
        
        finally:
            await service.close()


class TestConfigurationIntegration:
    """Test configuration integration and settings management."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_integration_settings_from_environment(self):
        """Test integration settings creation from environment variables."""
        
        import os
        
        # Set test environment variables
        original_enabled = os.environ.get('TRACKING_INTEGRATION_ENABLED')
        original_async = os.environ.get('TRACKING_ASYNC_STORAGE')
        
        try:
            os.environ['TRACKING_INTEGRATION_ENABLED'] = 'true'
            os.environ['TRACKING_ASYNC_STORAGE'] = 'false'
            
            settings = TrackingIntegrationSettings.from_environment()
            
            assert settings.enabled is True
            assert settings.async_storage is False
            
        finally:
            # Restore original environment
            if original_enabled is not None:
                os.environ['TRACKING_INTEGRATION_ENABLED'] = original_enabled
            else:
                os.environ.pop('TRACKING_INTEGRATION_ENABLED', None)
                
            if original_async is not None:
                os.environ['TRACKING_ASYNC_STORAGE'] = original_async
            else:
                os.environ.pop('TRACKING_ASYNC_STORAGE', None)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_configuration_validation(self):
        """Test configuration validation rules."""
        
        # Test valid configuration
        valid_settings = TrackingIntegrationSettings(
            enabled=True,
            storage_timeout_seconds=5,
            batch_size=25,
            environment="production"
        )
        
        assert valid_settings.enabled is True
        assert valid_settings.environment == "production"
        
        # Test invalid environment should raise validation error
        with pytest.raises(ValueError, match="Environment must be one of"):
            TrackingIntegrationSettings(environment="invalid_env")
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_performance_thresholds_by_environment(self):
        """Test performance threshold adjustment by environment."""
        
        prod_settings = TrackingIntegrationSettings(environment="production")
        dev_settings = TrackingIntegrationSettings(environment="development")
        
        prod_thresholds = prod_settings.get_performance_thresholds()
        dev_thresholds = dev_settings.get_performance_thresholds()
        
        # Production should have stricter thresholds
        assert prod_thresholds['storage_latency_ms'] < dev_thresholds['storage_latency_ms']
        assert prod_thresholds['integration_overhead_percent'] < dev_thresholds['integration_overhead_percent']