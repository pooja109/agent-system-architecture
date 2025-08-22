"""
Test scenarios for email model integration with scenario tracking.
Tests the new scenario tracking methods added to Email model.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from models.email import (
    Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata, ProcessingResult, EmailImportance
)


class TestEmailScenarioTrackingIntegration:
    """Test Email model integration with scenario tracking."""
    
    @pytest.fixture
    def sample_email(self):
        """Create a sample Email object for testing."""
        return Email(
            id=str(uuid4()),
            conversation_id=str(uuid4()),
            received_datetime=datetime.now(timezone.utc),
            sent_datetime=datetime.now(timezone.utc),
            sender=EmailAddress(email="customer@company.com", name="John Customer"),
            recipients=EmailRecipients(
                to=[EmailAddress(email="support@ourcompany.com", name="Support Team")],
                cc=[EmailAddress(email="manager@ourcompany.com", name="Manager")],
                bcc=[]
            ),
            subject="Product inquiry follow-up",
            body=EmailBody(content_type="text/html", content="<p>Thank you for your response...</p>"),
            email_body="Thank you for your response...",
            importance=EmailImportance.NORMAL,
            has_attachments=True,
            attachment_count=2,
            processing_metadata=ProcessingMetadata(
                monitor_version="1.0.0",
                process_id=str(uuid4()),
                processed_at=datetime.now(timezone.utc),
                retry_count=0
            )
        )
    
    @pytest.fixture
    def sample_processing_result(self):
        """Create a sample ProcessingResult object."""
        return ProcessingResult(
            success=True,
            email_id=str(uuid4()),
            process_id=str(uuid4()),
            sender_email="customer@company.com",
            sender_name="John Customer",
            subject="Product inquiry follow-up",
            error=None,
            destination_folder="Processed/Scenario_5",
            storage_location="/storage/processed/email_123.json",
            processing_duration_ms=2500,
            scenario_type="scenario_5",
            scenario_success=True,
            agent_actions_log=["assigned_expert", "created_case", "moved_email"],
            expert_assigned="Jane Expert",
            case_created="SF_CASE_789456",
            emails_sent=[]
        )
    
    @pytest.fixture
    def mock_scenario_result(self):
        """Create a mock scenario result object."""
        scenario_result = Mock()
        scenario_result.scenario_type = "scenario_5"
        scenario_result.success = True
        scenario_result.agent_actions_log = ["assigned_expert", "created_case"]
        scenario_result.expert_assigned = "Jane Expert"
        scenario_result.case_created = "SF_CASE_789456"
        scenario_result.emails_sent = []
        scenario_result.error_message = None
        return scenario_result
    
    @pytest.fixture
    def mock_intent_result(self):
        """Create a mock AI intent classification result."""
        intent_result = Mock()
        intent_result.intent = "POSITIVE"
        intent_result.confidence = 0.95
        intent_result.reasoning = "Customer expressed satisfaction and provided positive feedback"
        intent_result.detected_phrases = ["thank you", "excellent service", "very helpful"]
        intent_result.processing_duration_ms = 850
        intent_result.model_version = "azure-ai-foundry-v2.1"
        return intent_result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_to_scenario_tracking_data_basic(self, sample_email, sample_processing_result):
        """Test basic scenario tracking data extraction."""
        tracking_data = sample_email.to_scenario_tracking_data(sample_processing_result)
        
        # Check email data extraction
        assert tracking_data["process_id"] == sample_processing_result.process_id
        assert tracking_data["email_id"] == sample_email.id
        assert tracking_data["sender_email"] == "customer@company.com"
        assert tracking_data["sender_name"] == "John Customer"
        assert tracking_data["subject"] == "Product inquiry follow-up"
        assert tracking_data["has_attachments"] is True
        assert tracking_data["attachment_count"] == 2
        
        # Check processing result extraction
        assert tracking_data["process_success"] is True
        assert tracking_data["processing_duration_ms"] == 2500
        assert tracking_data["destination_folder"] == "Processed/Scenario_5"
        assert tracking_data["storage_location"] == "/storage/processed/email_123.json"
        
        # Check recipient extraction
        expected_recipients = ["support@ourcompany.com", "manager@ourcompany.com"]
        assert set(tracking_data["recipient_emails"]) == set(expected_recipients)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_to_scenario_tracking_data_with_scenario_result(self, sample_email, sample_processing_result, mock_scenario_result):
        """Test scenario tracking data with scenario result included."""
        tracking_data = sample_email.to_scenario_tracking_data(
            sample_processing_result, 
            scenario_result=mock_scenario_result
        )
        
        # Check scenario-specific data
        assert tracking_data["scenario_type"] == "scenario_5"
        assert tracking_data["scenario_success"] is True
        assert tracking_data["agent_actions_log"] == ["assigned_expert", "created_case"]
        assert tracking_data["expert_assigned"] == "Jane Expert"
        assert tracking_data["case_created"] == "SF_CASE_789456"
        assert tracking_data["emails_forwarded"] == []
        assert tracking_data["scenario_error_message"] is None
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_to_scenario_tracking_data_with_intent_result(self, sample_email, sample_processing_result, mock_intent_result):
        """Test scenario tracking data with AI intent result included."""
        tracking_data = sample_email.to_scenario_tracking_data(
            sample_processing_result,
            intent_result=mock_intent_result
        )
        
        # Check AI classification data
        assert tracking_data["ai_intent"] == "POSITIVE"
        assert tracking_data["ai_confidence"] == 0.95
        assert tracking_data["ai_reasoning"] == "Customer expressed satisfaction and provided positive feedback"
        assert tracking_data["ai_detected_phrases"] == ["thank you", "excellent service", "very helpful"]
        assert tracking_data["ai_processing_duration_ms"] == 850
        assert tracking_data["ai_model_version"] == "azure-ai-foundry-v2.1"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_to_scenario_tracking_data_with_additional_fields(self, sample_email, sample_processing_result):
        """Test scenario tracking data with additional custom fields."""
        additional_fields = {
            "test_mode": True,
            "environment": "staging",
            "custom_field": "custom_value"
        }
        
        tracking_data = sample_email.to_scenario_tracking_data(
            sample_processing_result,
            **additional_fields
        )
        
        # Check additional fields are included
        assert tracking_data["test_mode"] is True
        assert tracking_data["environment"] == "staging"
        assert tracking_data["custom_field"] == "custom_value"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_to_scenario_tracking_data_complete(self, sample_email, sample_processing_result, mock_scenario_result, mock_intent_result):
        """Test complete scenario tracking data extraction with all parameters."""
        additional_fields = {
            "test_mode": False,
            "environment": "production",
            "correlation_id": "corr_" + str(uuid4())
        }
        
        tracking_data = sample_email.to_scenario_tracking_data(
            sample_processing_result,
            scenario_result=mock_scenario_result,
            intent_result=mock_intent_result,
            **additional_fields
        )
        
        # Should contain data from all sources
        assert "process_id" in tracking_data
        assert "scenario_type" in tracking_data
        assert "ai_intent" in tracking_data
        assert "test_mode" in tracking_data
        assert "correlation_id" in tracking_data
        
        # Verify specific values
        assert tracking_data["scenario_type"] == "scenario_5"
        assert tracking_data["ai_intent"] == "POSITIVE"
        assert tracking_data["test_mode"] is False
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_create_scenario_processing_record_success(self, sample_email, sample_processing_result):
        """Test successful creation of ScenarioProcessingRecord."""
        # Test the method directly - it should work if imports are available
        try:
            result = sample_email.create_scenario_processing_record(sample_processing_result)
            
            # Should return a ScenarioProcessingRecord instance
            assert result is not None
            assert result.process_id == sample_processing_result.process_id
            assert result.email_id == sample_email.id
            assert result.sender_email == sample_email.sender.email
            
        except ImportError:
            # This is expected in some test environments
            pytest.skip("ScenarioProcessingRecord import not available in test environment")
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_scenario_processing_record_import_error(self, sample_email, sample_processing_result):
        """Test handling of import errors when creating scenario processing record."""
        # Simulate import failure
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            with pytest.raises(ImportError, match="Cannot import ScenarioProcessingRecord"):
                sample_email.create_scenario_processing_record(sample_processing_result)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_recipient_extraction_edge_cases(self, sample_email, sample_processing_result):
        """Test recipient extraction with various edge cases."""
        # Test with empty recipients
        sample_email.recipients = EmailRecipients(to=[], cc=[], bcc=[])
        tracking_data = sample_email.to_scenario_tracking_data(sample_processing_result)
        assert tracking_data["recipient_emails"] == []
        
        # Test with only BCC recipients
        sample_email.recipients = EmailRecipients(
            to=[],
            cc=[],
            bcc=[EmailAddress(email="bcc@company.com", name="BCC User")]
        )
        tracking_data = sample_email.to_scenario_tracking_data(sample_processing_result)
        assert tracking_data["recipient_emails"] == ["bcc@company.com"]
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_missing_optional_fields(self, sample_email, sample_processing_result):
        """Test handling of missing optional fields."""
        # Remove optional fields
        sample_email.conversation_id = None
        sample_email.sent_datetime = None
        sample_email.sender.name = None
        
        tracking_data = sample_email.to_scenario_tracking_data(sample_processing_result)
        
        # Should handle None values gracefully
        assert tracking_data["conversation_id"] is None
        assert tracking_data["sent_datetime"] is None
        assert tracking_data["sender_name"] is None
        
        # Required fields should still be present
        assert tracking_data["sender_email"] is not None
        assert tracking_data["process_id"] is not None
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_processing_result_edge_cases(self, sample_email):
        """Test with various ProcessingResult configurations."""
        # Test with failed processing result
        failed_result = ProcessingResult(
            success=False,
            email_id=sample_email.id,
            process_id=str(uuid4()),
            sender_email=sample_email.sender.email,
            error="Processing failed due to network timeout",
            processing_duration_ms=30000,  # Very slow
            scenario_type=None,
            scenario_success=False,
            agent_actions_log=["attempted_processing", "error_logged"],
            expert_assigned=None,
            case_created=None
        )
        
        tracking_data = sample_email.to_scenario_tracking_data(failed_result)
        
        assert tracking_data["process_success"] is False
        assert tracking_data["process_error"] == "Processing failed due to network timeout"
        assert tracking_data["processing_duration_ms"] == 30000
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_enum_value_extraction(self, sample_email, sample_processing_result):
        """Test that enum values are properly extracted."""
        # Test with different importance levels
        sample_email.importance = EmailImportance.HIGH
        tracking_data = sample_email.to_scenario_tracking_data(sample_processing_result)
        assert tracking_data["email_importance"] == "high"
        
        sample_email.importance = EmailImportance.LOW
        tracking_data = sample_email.to_scenario_tracking_data(sample_processing_result)
        assert tracking_data["email_importance"] == "low"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_data_types_consistency(self, sample_email, sample_processing_result, mock_scenario_result, mock_intent_result):
        """Test that data types are consistent with ScenarioProcessingRecord expectations."""
        tracking_data = sample_email.to_scenario_tracking_data(
            sample_processing_result,
            scenario_result=mock_scenario_result,
            intent_result=mock_intent_result
        )
        
        # Check data types
        assert isinstance(tracking_data["process_success"], bool)
        assert isinstance(tracking_data["has_attachments"], bool)
        assert isinstance(tracking_data["attachment_count"], int)
        assert isinstance(tracking_data["processing_duration_ms"], int)
        assert isinstance(tracking_data["recipient_emails"], list)
        assert isinstance(tracking_data["agent_actions_log"], list)
        assert isinstance(tracking_data["ai_confidence"], float)
        assert isinstance(tracking_data["ai_processing_duration_ms"], int)
        
        # Check datetime objects
        assert isinstance(tracking_data["received_datetime"], datetime)
        if tracking_data["sent_datetime"] is not None:
            assert isinstance(tracking_data["sent_datetime"], datetime)