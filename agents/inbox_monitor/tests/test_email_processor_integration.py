"""
Comprehensive integration tests for EmailProcessor scenario tracking integration.
Tests end-to-end functionality per Phase 3 requirements.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

from services.email_processor import EmailProcessor
from services.scenario_tracking_integration import (
    ScenarioTrackingIntegration,
    TrackingIntegrationResult,
    get_tracking_integration
)
from models.email import Email, ProcessingResult
from config.settings import AppSettings
from config.tracking_integration_settings import TrackingIntegrationSettings


@pytest.fixture
def mock_app_settings():
    """Create mock app settings for testing."""
    settings = Mock(spec=AppSettings)
    
    # Properly configure test_mode mock
    settings.test_mode = Mock()
    settings.test_mode.enabled = True
    settings.test_mode.test_sender_email = "test@example.com"
    
    settings.environment = "test"
    
    # Configure output mock
    settings.output = Mock()
    settings.output.storage_type = "file"
    settings.output.base_path = "/tmp/test_emails"
    settings.output.output_directory = "/tmp/test_emails"  # Add output_directory for Path() usage
    
    # Mock other required settings
    settings.graph_api = Mock()
    
    # Configure processing mock with required attributes
    settings.processing = Mock()
    settings.processing.max_retry_attempts = 3
    settings.processing.retry_delay_seconds = 1.0
    
    settings.logging = Mock()
    settings.azure_ai_foundry = Mock()
    settings.salesforce = Mock()
    settings.databricks_oauth = Mock()
    settings.key_vault = Mock()
    settings.scenarios = Mock()
    
    # Add dry_run attribute that EmailProcessor expects
    settings.dry_run = False
    
    # Configure content_formatting mock with proper values for Pydantic validation
    settings.content_formatting = Mock()
    settings.content_formatting.content_format = "structured"
    settings.content_formatting.max_description_length = 5000
    settings.content_formatting.preserve_signature = True
    settings.content_formatting.include_metadata = True
    settings.content_formatting.truncate_html_fallback = True
    
    settings.monitoring = Mock()
    settings.prompt_management = Mock()
    
    return settings


@pytest.fixture 
def mock_tracking_settings():
    """Create mock tracking settings."""
    return TrackingIntegrationSettings(
        enabled=True,
        async_storage=True,
        performance_monitoring_enabled=True,
        performance_threshold_ms=50
    )


@pytest.fixture
def test_email():
    """Create a test email for processing."""
    from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata
    import uuid
    
    return Email(
        id=f"test_email_{uuid.uuid4()}",
        conversation_id="test_conversation",
        received_datetime=datetime.now(timezone.utc),
        sender=EmailAddress(
            email="customer@example.com",
            name="Test Customer"
        ),
        recipients=EmailRecipients(
            to=[EmailAddress(
                email="lowtouch@microsoft.com",
                name="LowTouch Support"
            )]
        ),
        subject="Test Integration Email",
        body=EmailBody(
            content_type="text",
            content="This is a test email for integration testing."
        ),
        email_body="Test email for integration",
        processing_metadata=ProcessingMetadata(
            process_id=str(uuid.uuid4()),
            monitor_version="1.0.0-test"
        )
    )


@pytest.fixture
def test_message_dict(test_email):
    """Convert test email to message dict format."""
    return {
        "id": test_email.id,
        "subject": test_email.subject,
        "from": {
            "emailAddress": {
                "address": test_email.sender.email,
                "name": test_email.sender.name
            }
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": recipient.email,
                    "name": recipient.name
                }
            }
            for recipient in test_email.recipients.to
        ],
        "body": {
            "contentType": test_email.body.content_type,
            "content": test_email.body.content
        },
        "bodyPreview": test_email.email_body,
        "receivedDateTime": test_email.received_datetime.isoformat(),
        "hasAttachments": test_email.has_attachments,
        "importance": test_email.importance.value,
        "conversationId": test_email.conversation_id
    }


@pytest.mark.asyncio
class TestEmailProcessorIntegration:
    """Test EmailProcessor integration with scenario tracking."""
    
    @pytest.fixture
    async def email_processor(self, mock_app_settings, mock_tracking_settings):
        """Create EmailProcessor with mocked dependencies."""
        
        processor = EmailProcessor(mock_app_settings, "1.0.0-test")
        
        # Mock the dependencies
        processor.graph_client = AsyncMock()
        processor.scenario_processor = AsyncMock()
        processor.tracking_enabled = True
        processor.tracking_settings = mock_tracking_settings
        
        # Mock graph_client.convert_to_email_model to return our test email (synchronous method)
        processor.graph_client.convert_to_email_model = Mock()
        
        # Mock scenario processor to return a scenario result
        from services.scenario_processor import ScenarioResult, ScenarioType
        from services.azure_ai_foundry_client import IntentClassificationResult, EmailIntent
        
        mock_scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            agent_actions_log=["assigned_expert", "created_case"],
            expert_assigned="Jane Expert",
            case_created="SF_CASE_12345",
            emails_sent=[],
            intent_result=IntentClassificationResult(
                intent=EmailIntent.POSITIVE,
                confidence=0.95,
                reasoning="Customer expressed satisfaction with service",
                detected_phrases=["thank you", "great service"],
                processing_duration_ms=150
            ),
            # Enhanced metadata (Phase 3)
            processing_metadata={
                'email_id': 'test_email_123',
                'processing_start_time': 1234567890,
                'total_processing_duration_ms': 1500,
                'test_mode': True
            },
            processing_time_breakdown={
                'ai_classification_ms': 150,
                'scenario_processing_ms': 350,
                'total_processing_ms': 1500
            },
            scenario_decision_factors=[
                "Using AI classification for email intent",
                "Processing scenario: scenario_5"
            ],
            classification_confidence=0.95,
            ai_reasoning_detailed="Customer expressed satisfaction with service",
            expert_id="expert_123",
            expert_email="jane.expert@company.com",
            assignment_method="round_robin"
        )
        
        processor.scenario_processor.process_email_scenario.return_value = mock_scenario_result
        
        # Mock _store_email method
        processor._store_email = AsyncMock(return_value="/tmp/test_emails/test_email.json")
        
        # Mock _get_correlation_id method
        processor._get_correlation_id = Mock(return_value="test_correlation_123")
        
        # Mock _get_current_memory_usage method
        processor._get_current_memory_usage = Mock(return_value=45.7)
        
        return processor
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_scenario_tracking_integration_enabled(
        self, email_processor, test_email, test_message_dict
    ):
        """Test that scenario tracking integration is called when enabled."""
        
        # Mock the tracking integration
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            mock_integration.track_scenario_processing.return_value = TrackingIntegrationResult(
                success=True,
                processing_duration_ms=25.5,
                record_created=True,
                async_queued=True
            )
            mock_get_integration.return_value = mock_integration
            
            # Mock convert_to_email_model to return our test email
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email
            result = await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Verify processing succeeded
            assert result.success is True
            assert result.email_id == test_email.id
            assert result.scenario_type == "scenario_5"
            assert result.scenario_success is True
            assert result.expert_assigned == "Jane Expert"
            assert result.case_created == "SF_CASE_12345"
            
            # Verify tracking was called
            mock_get_integration.assert_called_once()
            mock_integration.track_scenario_processing.assert_called_once()
            
            # Verify tracking fields in result
            assert result.tracking_success is True
            assert result.tracking_time_ms > 0
            assert result.tracking_record_created is True
            assert result.tracking_async_queued is True
            assert result.tracking_error is None
    
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_scenario_tracking_integration_disabled(
        self, email_processor, test_email, test_message_dict
    ):
        """Test email processing when scenario tracking is disabled."""
        
        # Disable tracking
        email_processor.tracking_enabled = False
        email_processor.graph_client.convert_to_email_model.return_value = test_email
        
        # Process the email
        result = await email_processor._process_single_email(
            message=test_message_dict,
            folder_id="test_folder",
            folder_name="Test Folder"
        )
        
        # Verify processing succeeded
        assert result.success is True
        assert result.email_id == test_email.id
        
        # Verify tracking fields indicate disabled state
        assert result.tracking_success is None
        assert result.tracking_time_ms == 0.0
        assert result.tracking_error == "Tracking disabled"
        assert result.tracking_record_created is False
        assert result.tracking_async_queued is False
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_tracking_failure_does_not_affect_email_processing(
        self, email_processor, test_email, test_message_dict
    ):
        """Test that tracking failures don't impact email processing success."""
        
        # Mock tracking to fail
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            mock_integration.track_scenario_processing.side_effect = Exception("Tracking service unavailable")
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email - should succeed despite tracking failure
            result = await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Verify email processing still succeeded
            assert result.success is True
            assert result.email_id == test_email.id
            assert result.scenario_type == "scenario_5"
            
            # Verify tracking failure is recorded but doesn't fail processing
            assert result.tracking_success is False
            assert result.tracking_error is not None
            assert "Tracking service unavailable" in result.tracking_error
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_enhanced_processing_result_construction(
        self, email_processor, test_email, test_message_dict
    ):
        """Test that enhanced processing result construction includes all scenario data."""
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            
            # Capture the arguments passed to track_scenario_processing
            captured_args = None
            
            def capture_tracking_call(*args, **kwargs):
                nonlocal captured_args
                captured_args = {
                    'args': args,
                    'kwargs': kwargs
                }
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=30.0,
                    record_created=True,
                    async_queued=False
                )
            
            mock_integration.track_scenario_processing.side_effect = capture_tracking_call
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email
            result = await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Verify the enhanced processing result was passed to tracking
            assert captured_args is not None
            
            # Check the processing_result argument
            processing_result = captured_args['kwargs']['processing_result']
            assert processing_result.sender_email == test_email.sender.email
            assert processing_result.sender_name == test_email.sender.name
            assert processing_result.subject == test_email.subject
            assert processing_result.scenario_type == "scenario_5"
            assert processing_result.scenario_success is True
            assert processing_result.expert_assigned == "Jane Expert"
            assert processing_result.case_created == "SF_CASE_12345"
            
            # Check additional context
            additional_context = captured_args['kwargs']
            assert additional_context['test_mode'] is True
            assert additional_context['environment'] == "test"
            assert additional_context['monitor_version'] == "1.0.0-test"
            assert 'processed_at' in additional_context
    
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_correlation_id_management(
        self, email_processor, test_email, test_message_dict
    ):
        """Test proper correlation ID management in tracking."""
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            
            captured_correlation_id = None
            
            def capture_correlation_id(*args, **kwargs):
                nonlocal captured_correlation_id
                captured_correlation_id = kwargs.get('correlation_id')
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=20.0,
                    record_created=True,
                    async_queued=False
                )
            
            mock_integration.track_scenario_processing.side_effect = capture_correlation_id
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Mock the log_processing_start method to return expected correlation ID
            with patch.object(email_processor, 'log_processing_start', return_value="test_correlation_123"):
                # Process the email
                await email_processor._process_single_email(
                    message=test_message_dict,
                    folder_id="test_folder",
                    folder_name="Test Folder"
                )
            
            # Verify correlation ID was passed
            assert captured_correlation_id == "test_correlation_123"
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_performance_context_inclusion(
        self, email_processor, test_email, test_message_dict
    ):
        """Test that performance context is included when enabled."""
        
        # Enable performance tracking in settings
        email_processor.settings.performance_tracking = True
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            
            captured_context = None
            
            def capture_context(*args, **kwargs):
                nonlocal captured_context
                captured_context = kwargs
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=40.0,
                    record_created=True,
                    async_queued=False
                )
            
            mock_integration.track_scenario_processing.side_effect = capture_context
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email
            await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Verify performance context was included
            assert captured_context is not None
            assert 'memory_usage_mb' in captured_context
            assert captured_context['memory_usage_mb'] == 45.7
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_comprehensive_metadata_capture(
        self, email_processor, test_email, test_message_dict
    ):
        """Test that comprehensive metadata from ScenarioProcessor is captured."""
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            
            captured_scenario_result = None
            captured_intent_result = None
            
            def capture_metadata(*args, **kwargs):
                nonlocal captured_scenario_result, captured_intent_result
                captured_scenario_result = kwargs.get('scenario_result')
                captured_intent_result = kwargs.get('intent_result')
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=35.0,
                    record_created=True,
                    async_queued=False
                )
            
            mock_integration.track_scenario_processing.side_effect = capture_metadata
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email
            await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Verify comprehensive metadata was captured
            assert captured_scenario_result is not None
            assert captured_scenario_result.processing_metadata is not None
            assert captured_scenario_result.processing_time_breakdown is not None
            assert captured_scenario_result.scenario_decision_factors is not None
            assert captured_scenario_result.classification_confidence == 0.95
            assert captured_scenario_result.ai_reasoning_detailed == "Customer expressed satisfaction with service"
            assert captured_scenario_result.expert_id == "expert_123"
            assert captured_scenario_result.expert_email == "jane.expert@company.com"
            
            # Verify intent result is passed through
            assert captured_intent_result is not None
            assert captured_intent_result.intent.value == "POSITIVE"
            assert captured_intent_result.confidence == 0.95
    
    @pytest.mark.asyncio 
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_timing_integration(self, email_processor, test_email, test_message_dict):
        """Test that tracking timing is properly measured and recorded."""
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            
            # Simulate tracking taking some time
            async def slow_tracking(*args, **kwargs):
                await asyncio.sleep(0.01)  # 10ms delay
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=15.0,  # Internal tracking time
                    record_created=True,
                    async_queued=False
                )
            
            mock_integration.track_scenario_processing.side_effect = slow_tracking
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email
            result = await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Verify tracking time is recorded (should be >= 10ms from our delay)
            assert result.tracking_time_ms >= 10.0
            assert result.tracking_time_ms < 100.0  # Reasonable upper bound
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_error_handling_isolation(
        self, email_processor, test_email, test_message_dict
    ):
        """Test that scenario processing errors don't prevent tracking."""
        
        # Mock scenario processor to fail
        email_processor.scenario_processor.process_email_scenario.side_effect = Exception("Scenario processing failed")
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock(spec=ScenarioTrackingIntegration)
            mock_integration.track_scenario_processing.return_value = TrackingIntegrationResult(
                success=True,
                processing_duration_ms=20.0,
                record_created=True,
                async_queued=False
            )
            mock_get_integration.return_value = mock_integration
            
            email_processor.graph_client.convert_to_email_model.return_value = test_email
            
            # Process the email - should handle scenario failure gracefully
            result = await email_processor._process_single_email(
                message=test_message_dict,
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Email processing should still succeed (moved to processed folder)
            assert result.success is True
            assert result.email_id == test_email.id
            
            # Tracking should still be attempted (with None scenario_result)
            mock_integration.track_scenario_processing.assert_called_once()
            call_kwargs = mock_integration.track_scenario_processing.call_args[1]
            assert call_kwargs['scenario_result'] is None
            assert call_kwargs['intent_result'] is None
            
            # Verify tracking succeeded despite scenario failure
            assert result.tracking_success is True
            assert result.tracking_record_created is True


@pytest.mark.asyncio
class TestEmailProcessorIntegrationEdgeCases:
    """Test edge cases and error conditions for EmailProcessor integration."""
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_integration_with_malformed_scenario_result(
        self, mock_app_settings, mock_tracking_settings
    ):
        """Test integration handles malformed scenario results gracefully."""
        
        processor = EmailProcessor(mock_app_settings, "1.0.0-test")
        processor.tracking_enabled = True
        processor.tracking_settings = mock_tracking_settings
        
        # Mock scenario processor to return malformed result
        malformed_result = Mock()
        malformed_result.scenario_type = None  # Missing required field
        malformed_result.success = True
        malformed_result.agent_actions_log = []
        
        processor.scenario_processor = AsyncMock()
        processor.scenario_processor.process_email_scenario.return_value = malformed_result
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            mock_integration.track_scenario_processing.return_value = TrackingIntegrationResult(
                success=True,
                processing_duration_ms=25.0,
                record_created=True,
                async_queued=False
            )
            mock_get_integration.return_value = mock_integration
            
            # Mock other dependencies
            processor.graph_client = AsyncMock()
            test_email = Mock()
            test_email.id = "malformed_test"
            test_email.sender.email = "test@example.com"
            test_email.sender.name = "Test"
            test_email.subject = "Malformed Test"
            processor.graph_client.convert_to_email_model.return_value = test_email
            processor._store_email = AsyncMock(return_value="/tmp/test")
            processor._get_correlation_id = Mock(return_value="correlation_123")
            processor._get_current_memory_usage = Mock(return_value=50.0)
            
            # Should handle malformed result without crashing
            result = await processor._process_single_email(
                message={"id": "malformed_test"},
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Processing should still succeed
            assert result.success is True
            
            # Tracking should be attempted (integration should handle malformed data)
            mock_integration.track_scenario_processing.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_integration_timeout_handling(
        self, mock_app_settings, mock_tracking_settings
    ):
        """Test that integration handles tracking timeouts gracefully."""
        
        processor = EmailProcessor(mock_app_settings, "1.0.0-test")
        processor.tracking_enabled = True
        processor.tracking_settings = mock_tracking_settings
        
        # Mock dependencies
        processor.graph_client = AsyncMock()
        processor.scenario_processor = AsyncMock()
        
        # Mock scenario result
        from services.scenario_processor import ScenarioResult, ScenarioType
        mock_scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            agent_actions_log=["test_action"]
        )
        processor.scenario_processor.process_email_scenario.return_value = mock_scenario_result
        
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            
            # Mock tracking to timeout
            async def timeout_tracking(*args, **kwargs):
                await asyncio.sleep(2.0)  # Long delay
                return TrackingIntegrationResult(success=True, processing_duration_ms=2000.0)
            
            mock_integration.track_scenario_processing.side_effect = timeout_tracking
            mock_get_integration.return_value = mock_integration
            
            # Mock other methods
            test_email = Mock()
            test_email.id = "timeout_test"
            test_email.sender.email = "test@example.com"
            test_email.sender.name = "Test"
            test_email.subject = "Timeout Test"
            processor.graph_client.convert_to_email_model.return_value = test_email
            processor._store_email = AsyncMock(return_value="/tmp/test")
            processor._get_correlation_id = Mock(return_value="correlation_123")
            processor._get_current_memory_usage = Mock(return_value=50.0)
            
            # Process with timeout - should complete but may have tracking timeout
            result = await processor._process_single_email(
                message={"id": "timeout_test"},
                folder_id="test_folder",
                folder_name="Test Folder"
            )
            
            # Email processing should still succeed
            assert result.success is True
            assert result.email_id == "timeout_test"
            
            # Tracking timing should be recorded (even if it took a while)
            assert result.tracking_time_ms >= 1000.0  # At least 1 second