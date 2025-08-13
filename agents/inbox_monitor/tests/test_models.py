"""
Tests for Email Models
======================
Unit tests for email data models.
"""
from datetime import datetime
import pytest
from models.email import (
    EmailAddress,
    EmailBody,
    EmailImportance,
    EmailRecipients,
    ProcessingMetadata,
    ProcessingResult,
)


@pytest.mark.fast
@pytest.mark.unit
class TestEmailAddress:
    """Test EmailAddress model."""
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_email_address_creation(self):
        """Test creating email address with all fields."""
        address = EmailAddress(email="test@example.com", name="Test User")
        assert address.email == "test@example.com"
        assert address.name == "Test User"
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_email_address_minimal(self):
        """Test creating email address with only required fields."""
        address = EmailAddress(email="test@example.com")
        assert address.email == "test@example.com"
        assert address.name is None


@pytest.mark.fast
class TestEmailBody:
    """Test EmailBody model."""
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_email_body_html(self):
        """Test creating HTML email body."""
        body = EmailBody(content_type="text/html", content="<html><body>Test</body></html>")
        assert body.content_type == "text/html"
        assert body.content == "<html><body>Test</body></html>"
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_email_body_plain(self):
        """Test creating plain text email body."""
        body = EmailBody(content_type="text/plain", content="Plain text content")
        assert body.content_type == "text/plain"
        assert body.content == "Plain text content"
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_email_body_invalid_type(self):
        """Test invalid content type raises error."""
        with pytest.raises(ValueError, match="Invalid content type"):
            EmailBody(content_type="text/invalid", content="Content")


@pytest.mark.fast
class TestEmailRecipients:
    """Test EmailRecipients model."""
    @pytest.mark.ci_safe
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_recipients_all_fields(self):
        """Test recipients with all fields populated."""
        recipients = EmailRecipients(
            to=[EmailAddress(email="to@example.com")],
            cc=[EmailAddress(email="cc@example.com")],
            bcc=[EmailAddress(email="bcc@example.com")],
        )
        assert len(recipients.to) == 1
        assert len(recipients.cc) == 1
        assert len(recipients.bcc) == 1
    @pytest.mark.ci_safe
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_recipients_empty(self):
        """Test recipients with empty lists."""
        recipients = EmailRecipients()
        assert recipients.to == []
        assert recipients.cc == []
        assert recipients.bcc == []


@pytest.mark.fast
@pytest.mark.unit
class TestProcessingMetadata:
    """Test ProcessingMetadata model."""




    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.email
    def test_processing_metadata_defaults(self):
        """Test processing metadata with defaults."""
        metadata = ProcessingMetadata(inbox_monitor_version="1.0.0", processing_id="test-id-123")
        assert metadata.inbox_monitor_version == "1.0.0"
        assert metadata.processing_id == "test-id-123"
        assert metadata.source_folder == "Inbox"
        assert metadata.retry_count == 0
        assert isinstance(metadata.processing_timestamp, datetime)


class TestEmail:
    """Test Email model."""
    




    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.email
    def test_email_creation_full(self, mock_email_model):
        """Test creating email with all fields."""
        email = mock_email_model
        assert email.id == "test-message-id-123"
        assert email.subject == "Test Email Subject"
        assert email.sender.email == "sender@example.com"
        assert len(email.recipients.to) == 1
        assert email.importance == EmailImportance.NORMAL



    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.email
    def test_email_to_ai_format(self, mock_email_model):
        """Test converting email to AI format."""
        email = mock_email_model
        ai_format = email.to_ai_format()
        assert ai_format["id"] == email.id
        assert ai_format["subject"] == email.subject
        assert ai_format["sender"]["email"] == email.sender.email
        assert ai_format["body"]["content_type"] == email.body.content_type
        assert ai_format["importance"] == "normal"
        assert "processing_metadata" in ai_format
        assert ai_format["processing_metadata"]["inbox_monitor_version"] == "1.0.0"



    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.email
    def test_email_datetime_serialization(self, mock_email_model):
        """Test datetime fields are properly serialized."""
        email = mock_email_model
        ai_format = email.to_ai_format()
        # Check datetime fields end with 'Z' for UTC
        assert ai_format["received_datetime"].endswith("Z")
        assert ai_format["processed_timestamp"].endswith("Z")


@pytest.mark.fast
class TestProcessingResult:
    """Test ProcessingResult model."""
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_processing_result_success(self):
        """Test successful processing result."""
        result = ProcessingResult(
            success=True,
            email_id="test-email-123",
            processing_id="test-processing-123",
            moved_to_folder="Processed_01_2024",
            output_location="/output/email_123.json",
            processing_time_ms=1500,
        )
        assert result.success is True
        assert result.error is None
        assert result.moved_to_folder == "Processed_01_2024"
        assert result.processing_time_ms == 1500
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_processing_result_failure(self):
        """Test failed processing result."""
        result = ProcessingResult(
            success=False,
            email_id="test-email-123",
            processing_id="test-processing-123",
            error="Failed to move email: API error",
            processing_time_ms=500,
        )
        assert result.success is False
        assert result.error == "Failed to move email: API error"
        assert result.moved_to_folder is None
        assert result.output_location is None


@pytest.mark.fast
@pytest.mark.unit
class TestEmailImportance:
    """Test EmailImportance enum."""
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_importance_values(self):
        """Test importance enum values."""
        assert EmailImportance.LOW.value == "low"
        assert EmailImportance.NORMAL.value == "normal"
        assert EmailImportance.HIGH.value == "high"
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_importance_comparison(self):
        """Test importance enum comparison."""
        assert EmailImportance.LOW != EmailImportance.HIGH
        assert EmailImportance.NORMAL == EmailImportance.NORMAL