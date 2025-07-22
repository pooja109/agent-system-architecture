"""
Email Models
============

Pydantic models for email data structures used in the inbox monitor.
"""

from datetime import datetime
from enum import Enum
from typing import Any

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

    inbox_monitor_version: str = Field(..., description="Version of inbox monitor")
    processing_id: str = Field(..., description="Unique processing ID")
    processing_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the email was processed"
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
    body_preview: str = Field(..., description="Preview of email body (first 255 characters)")

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

    # Processing metadata
    processing_metadata: ProcessingMetadata = Field(..., description="Metadata about processing")

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat() + "Z"}}

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
            "body_preview": self.body_preview,
            "importance": self.importance.value,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            "categories": self.categories,
            "internet_message_headers": self.internet_message_headers,
            "processed_timestamp": self.processing_metadata.processing_timestamp.isoformat() + "Z",
            "processing_metadata": {
                "inbox_monitor_version": self.processing_metadata.inbox_monitor_version,
                "processing_id": self.processing_metadata.processing_id,
            },
        }


class ProcessingResult(BaseModel):
    """Result of email processing operation."""

    success: bool = Field(..., description="Whether processing succeeded")
    email_id: str = Field(..., description="ID of processed email")
    processing_id: str = Field(..., description="Unique processing ID")
    error: str | None = Field(None, description="Error message if failed")
    moved_to_folder: str | None = Field(None, description="Folder where email was moved")
    output_location: str | None = Field(None, description="Where processed email was stored")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    scenario_type: str | None = Field(None, description="Type of scenario processed")
    scenario_success: bool | None = Field(None, description="Whether scenario processing succeeded")
    actions_taken: list[str] = Field(
        default_factory=list, description="Actions taken during scenario processing"
    )
    expert_assigned: str | None = Field(None, description="Expert assigned (if applicable)")
    case_created: str | None = Field(None, description="Salesforce case ID (if created)")
    emails_sent: list[str] = Field(
        default_factory=list, description="Emails sent during processing"
    )
