from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

@dataclass
class EmailRecord:
    """Represents a record in the email communication pipeline table."""
    # Primary workflow fields
    batch_id: int
    run_date: str
    agent_name: str
    status: str
    customer_id: str
    
    # Optional workflow fields
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    is_reviewed: Optional[bool] = None
    review_notes: Optional[str] = None
    is_approved: Optional[bool] = None
    approved_notes: Optional[str] = None
    is_email_sent: Optional[bool] = None
    contact_id: Optional[str] = None
    customer_name: Optional[str] = None
    
    # Email tracking fields
    sent_email_id: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    send_timestamp: Optional[datetime] = None
    send_status: Optional[str] = None
    error_message: Optional[str] = None
    acs_message_id: Optional[str] = None
    
    # Blob processing fields
    blob_date_folder: Optional[str] = None
    json_file_path: Optional[str] = None
    html_file_path: Optional[str] = None
    
    # Audit fields
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_by: str = "email_processor"
    
    def __post_init__(self):
        """Initialize computed fields after dataclass creation."""
        if self.sent_email_id is None and self.is_email_sent:
            self.sent_email_id = str(uuid.uuid4())
        
        if self.created_at is None:
            self.created_at = datetime.now()
        
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class ContactInfo:
    """Represents contact information extracted from research output."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    salesforce_account_id: Optional[str] = None
    salesforce_contact_id: Optional[str] = None

@dataclass
class ResearchOutput:
    """Represents the structure of research output JSON files."""
    customer_name: str
    customer_id: str
    sample_email_subject: str
    contact_list: List[ContactInfo]
    
    # Optional fields
    division: Optional[str] = None
    primary_reason_for_outreach: Optional[str] = None
    issue: Optional[str] = None
    sender_details: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    recommendations: Optional[List[str]] = None
    sample_email_body: Optional[str] = None
    citations: Optional[List[str]] = None
    url_citations: Optional[List[str]] = None
    company: Optional[Dict[str, Any]] = None
    account: Optional[Dict[str, Any]] = None
    other_fields: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchOutput':
        """Create ResearchOutput from dictionary (JSON data)."""
        # Parse contact list
        contact_list = []
        for contact_data in data.get('contact_list', []):
            contact = ContactInfo(**contact_data)
            contact_list.append(contact)
        
        return cls(
            customer_name=data.get('customer_name', ''),
            customer_id=data.get('customer_id', ''),
            sample_email_subject=data.get('sample_email_subject', ''),
            contact_list=contact_list,
            division=data.get('division'),
            primary_reason_for_outreach=data.get('primary_reason_for_outreach'),
            issue=data.get('issue'),
            sender_details=data.get('sender_details'),
            summary=data.get('summary'),
            recommendations=data.get('recommendations'),
            sample_email_body=data.get('sample_email_body'),
            citations=data.get('citations'),
            url_citations=data.get('url_citations'),
            company=data.get('company'),
            account=data.get('account'),
            other_fields=data.get('other_fields')
        )
    
    def get_primary_contact(self) -> Optional[ContactInfo]:
        """Get the first contact from the contact list."""
        return self.contact_list[0] if self.contact_list else None

@dataclass
class EmailContent:
    """Represents email content for sending."""
    subject: str
    body_html: str
    recipient_email: str
    
    # Optional fields
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    contact_name: Optional[str] = None
    
@dataclass
class EmailSendResult:
    """Represents the result of an email send operation."""
    success: bool
    message_id: Optional[str] = None
    acs_message_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class BlobFileInfo:
    """Represents information about files in blob storage."""
    container_name: str
    blob_name: str
    full_path: str
    date_folder: str
    customer_id: str
    file_type: str  # 'json' or 'html'
    
    @property
    def communication_output_path(self) -> str:
        """Get the communication_output folder path."""
        return f"{self.date_folder}/{self.customer_id}/communication_output/"