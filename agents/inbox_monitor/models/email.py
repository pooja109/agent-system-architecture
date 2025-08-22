"""
Email Models
============

Pydantic models for email data structures used in the inbox monitor.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class EmailImportance(str, Enum):
    """Email importance levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EmailAddress(BaseModel):
    """Email address with optional display name."""

    email: str = Field(..., description="Email address")
    name: str | None = Field(None, description="Display name")


class EmailBody(BaseModel):
    """Email body content."""

    content_type: str = Field(..., description="Content type (text/plain or text/html)")
    content: str = Field(..., description="Body content")

    @field_validator("content_type")
    def validate_content_type(cls, v: str) -> str:
        """Validate and normalize content type."""
        # Normalize common content type variations
        if v.lower() == "html":
            return "text/html"
        elif v.lower() == "text":
            return "text/plain"
        elif v.lower() in ["text/plain", "text/html"]:
            return v.lower()

        # Check if it's a valid content type
        valid_types = ["text/plain", "text/html"]
        if v not in valid_types:
            raise ValueError(f"Invalid content type: {v}. Must be one of {valid_types}")
        return v


class EmailRecipients(BaseModel):
    """Email recipients structure."""

    to: list[EmailAddress] = Field(default_factory=list, description="To recipients")
    cc: list[EmailAddress] = Field(default_factory=list, description="CC recipients")
    bcc: list[EmailAddress] = Field(default_factory=list, description="BCC recipients")


class ProcessingMetadata(BaseModel):
    """Metadata about email processing."""

    monitor_version: str = Field(..., description="Version of inbox monitor")
    process_id: str = Field(..., description="Unique processing ID")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When the email was processed"
    )
    source_folder: str = Field(default="Inbox", description="Source folder name")
    retry_count: int = Field(default=0, description="Number of processing retries")


class Email(BaseModel):
    """Complete email structure for AI processing."""

    # Core email properties
    id: str = Field(..., description="Unique message ID from Graph API")
    conversation_id: str | None = Field(None, description="Conversation thread ID")
    received_datetime: datetime = Field(..., description="When email was received")
    sent_datetime: datetime | None = Field(None, description="When email was sent")

    # Sender and recipients
    sender: EmailAddress = Field(..., description="Email sender")
    recipients: EmailRecipients = Field(..., description="Email recipients")

    # Email content
    subject: str = Field(..., description="Email subject")
    body: EmailBody = Field(..., description="Email body")
    email_body: str = Field(..., description="Full email body content")

    # Email metadata
    importance: EmailImportance = Field(
        default=EmailImportance.NORMAL, description="Email importance"
    )
    has_attachments: bool = Field(default=False, description="Whether email has attachments")
    attachment_count: int = Field(default=0, description="Number of attachments")
    categories: list[str] = Field(default_factory=list, description="Email categories/labels")
    is_read: bool = Field(default=False, description="Read status")
    is_draft: bool = Field(default=False, description="Draft status")

    # Additional headers and metadata
    internet_message_headers: dict[str, str] = Field(
        default_factory=dict, description="Internet message headers"
    )

    # Raw Graph API data storage
    email_payload: Optional[str] = Field(
        None, description="Complete Graph API message JSON response as string"
    )
    email_headers: Optional[str] = Field(
        None, description="Graph API internetMessageHeaders array as JSON string"
    )

    # Processing metadata
    processing_metadata: ProcessingMetadata = Field(..., description="Metadata about processing")

    # Removed deprecated json_encoders - using custom serialization in to_ai_format() instead

    def to_ai_format(self) -> dict[str, Any]:
        """Convert to format suitable for AI processing."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "received_datetime": self.received_datetime.isoformat() + "Z",
            "sender": {"email": self.sender.email, "name": self.sender.name},
            "recipients": {
                "to": [{"email": r.email, "name": r.name} for r in self.recipients.to],
                "cc": [{"email": r.email, "name": r.name} for r in self.recipients.cc],
                "bcc": [{"email": r.email, "name": r.name} for r in self.recipients.bcc],
            },
            "subject": self.subject,
            "body": {
                "content_type": self.body.content_type,
                "content": self.body.content,
            },
            "email_body": self.email_body,
            "importance": self.importance.value,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            "categories": self.categories,
            "internet_message_headers": self.internet_message_headers,
            "processed_at": self.processing_metadata.processed_at.isoformat() + "Z",
            "processing_metadata": {
                "monitor_version": self.processing_metadata.monitor_version,
                "process_id": self.processing_metadata.process_id,
            },
        }

    def to_scenario_tracking_data(
        self,
        processing_result: "ProcessingResult",
        scenario_result: Optional[Any] = None,
        intent_result: Optional[Any] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """
        Convert Email and ProcessingResult to data suitable for scenario tracking.
        
        Args:
            processing_result: ProcessingResult object with processing details
            scenario_result: ScenarioResult object with scenario-specific data
            intent_result: IntentClassificationResult with AI classification data
            **additional_fields: Additional fields to include in tracking data
            
        Returns:
            Dictionary with data formatted for ScenarioProcessingRecord creation
        """
        # Base email data
        tracking_data = {
            "process_id": processing_result.process_id,
            "email_id": self.id,
            "conversation_id": self.conversation_id,
            "sender_email": self.sender.email,
            "sender_name": self.sender.name,
            "subject": self.subject,
            "received_datetime": self.received_datetime,
            "sent_datetime": self.sent_datetime,
            "email_body": self.email_body,
            "email_importance": self.importance.value,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            
            # Processing result data
            "process_success": processing_result.success,
            "processing_duration_ms": processing_result.processing_duration_ms,
            "process_error": processing_result.error,
            "destination_folder": processing_result.destination_folder,
            "storage_location": processing_result.storage_location,
            "monitor_version": self.processing_metadata.monitor_version,
            "retry_count": self.processing_metadata.retry_count,
        }
        
        # Extract recipient emails
        recipients = []
        for recipient_type in ["to", "cc", "bcc"]:
            recipient_list = getattr(self.recipients, recipient_type, [])
            for recipient in recipient_list:
                recipients.append(recipient.email)
        tracking_data["recipient_emails"] = recipients
        
        # Add scenario result data if provided
        if scenario_result:
            tracking_data.update({
                "scenario_type": getattr(scenario_result, "scenario_type", None),
                "scenario_success": getattr(scenario_result, "success", None),
                "agent_actions_log": getattr(scenario_result, "agent_actions_log", []),
                "expert_assigned": getattr(scenario_result, "expert_assigned", None),
                "case_created": getattr(scenario_result, "case_created", None),
                "emails_forwarded": getattr(scenario_result, "emails_sent", []),
                "scenario_error_message": getattr(scenario_result, "error_message", None),
            })
        
        # Add AI classification data if provided
        if intent_result:
            tracking_data.update({
                "ai_intent": getattr(intent_result, "intent", None),
                "ai_confidence": getattr(intent_result, "confidence", None),
                "ai_reasoning": getattr(intent_result, "reasoning", None),
                "ai_detected_phrases": getattr(intent_result, "detected_phrases", []),
                "ai_processing_duration_ms": getattr(intent_result, "processing_duration_ms", None),
                "ai_model_version": getattr(intent_result, "model_version", None),
            })
        
        # Add any additional fields
        tracking_data.update(additional_fields)
        
        return tracking_data

    def create_scenario_processing_record(
        self,
        processing_result: "ProcessingResult",
        scenario_result: Optional[Any] = None,
        intent_result: Optional[Any] = None,
        **additional_fields
    ):
        """
        Create a ScenarioProcessingRecord from this Email and processing results.
        
        Args:
            processing_result: ProcessingResult object with processing details
            scenario_result: ScenarioResult object with scenario-specific data
            intent_result: IntentClassificationResult with AI classification data
            **additional_fields: Additional fields to include in the record
            
        Returns:
            ScenarioProcessingRecord instance ready for Databricks storage
        """
        try:
            from ..database.scenario_tracking_models import ScenarioProcessingRecord
        except ImportError:
            # Fallback import for testing or standalone usage
            try:
                from database.scenario_tracking_models import ScenarioProcessingRecord
            except ImportError:
                raise ImportError(
                    "Cannot import ScenarioProcessingRecord. "
                    "Ensure scenario_tracking_models.py is available."
                )
        
        tracking_data = self.to_scenario_tracking_data(
            processing_result=processing_result,
            scenario_result=scenario_result,
            intent_result=intent_result,
            **additional_fields
        )
        
        return ScenarioProcessingRecord(**tracking_data)


class ProcessingResult(BaseModel):
    """Result of email processing operation."""

    success: bool = Field(..., description="Whether processing succeeded")
    email_id: str = Field(..., description="ID of processed email")
    process_id: str = Field(..., description="Unique processing ID")
    sender_email: str | None = Field(None, description="Email sender address")
    sender_name: str | None = Field(None, description="Email sender display name")
    subject: str | None = Field(None, description="Email subject")
    error: str | None = Field(None, description="Error message if failed")
    destination_folder: str | None = Field(None, description="Folder where email was moved")
    storage_location: str | None = Field(None, description="Where processed email was stored")
    processing_duration_ms: int = Field(..., description="Processing time in milliseconds")
    scenario_type: str | None = Field(None, description="Type of scenario processed")
    scenario_success: bool | None = Field(None, description="Whether scenario processing succeeded")
    agent_actions_log: list[str] = Field(
        default_factory=list, description="Actions taken during scenario processing"
    )
    expert_assigned: str | None = Field(None, description="Expert assigned (if applicable)")
    case_created: str | None = Field(None, description="Salesforce case ID (if created)")
    emails_sent: list[str] = Field(
        default_factory=list, description="Emails sent during processing"
    )
    
    # Tracking operation status fields
    tracking_success: bool | None = Field(None, description="Whether scenario tracking succeeded")
    tracking_time_ms: float | None = Field(None, description="Time spent on tracking operation in milliseconds")
    tracking_error: str | None = Field(None, description="Error message if tracking failed")
    tracking_record_created: bool | None = Field(None, description="Whether tracking record was created")
    tracking_async_queued: bool | None = Field(None, description="Whether tracking was queued for async processing")


# Aliases for backwards compatibility and different naming conventions
EmailMessage = Email
ProcessedEmail = ProcessingResult
