"""
Email Metadata Extractor
========================

Utilities for extracting email-specific metadata like attachment count and thread ID
from various email data formats. Supports Microsoft Graph API and other email sources.
"""

from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


def extract_email_metadata(email_data: Optional[Any]) -> Dict[str, Any]:
    """
    Extract email-specific metadata like attachment count.
    NOTE: email_thread_id was removed from database schema.
    
    Args:
        email_data: Email data object from various sources
    
    Returns:
        Dict containing attachment_count (thread_id removed from schema)
    """
    
    metadata = {
        'attachment_count': 0
        # Note: email_thread_id removed as it doesn't exist in database table
    }
    
    if not email_data:
        logger.warning("No email data available for metadata extraction")
        return metadata
    
    try:
        # Extract attachment count
        metadata['attachment_count'] = count_email_attachments(email_data)
        
        # Note: Thread ID extraction removed as field doesn't exist in database
        
        logger.debug(f"Extracted email metadata: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting email metadata: {e}")
        return metadata


def count_email_attachments(email_data: Optional[Any]) -> int:
    """
    Count the number of attachments in the email.
    
    Args:
        email_data: Email data object with attachment information
        
    Returns:
        Number of attachments (0 if none or unable to determine)
    """
    
    if not email_data:
        return 0
    
    try:
        # Check for attachments array/list
        if hasattr(email_data, 'attachments'):
            attachments = email_data.attachments
            if attachments is None:
                # If attachments list is None but has_attachments is True, fall through to check boolean
                if hasattr(email_data, 'has_attachments') and email_data.has_attachments:
                    return 1
                return 0
            elif isinstance(attachments, list):
                return len(attachments)
            elif hasattr(attachments, '__len__'):
                return len(attachments)
        
        # Check for attachment count field
        elif hasattr(email_data, 'attachment_count'):
            count = email_data.attachment_count
            if isinstance(count, int):
                return count
        
        # Check for has_attachments boolean
        elif hasattr(email_data, 'has_attachments'):
            # If we know there are attachments but can't count them, return 1
            return 1 if email_data.has_attachments else 0
        
        # Check Microsoft Graph API specific fields
        elif hasattr(email_data, 'hasAttachments'):
            return 1 if email_data.hasAttachments else 0
        
        return 0
        
    except Exception as e:
        logger.error(f"Error counting email attachments: {e}")
        return 0


def extract_thread_id(email_data: Optional[Any]) -> Optional[str]:
    """
    Extract email thread/conversation ID for conversation tracking.
    
    Args:
        email_data: Email data object with thread/conversation information
        
    Returns:
        Thread/conversation ID if available, None otherwise
    """
    
    if not email_data:
        return None
    
    try:
        # Microsoft Graph API thread ID patterns
        thread_fields = [
            'conversationId',      # Graph API standard
            'conversation_id',     # Snake case variant
            'threadId',           # Alternative Graph API field
            'thread_id',          # Snake case variant
            'messageId',          # Message ID as thread fallback
            'message_id',         # Snake case variant
        ]
        
        for field in thread_fields:
            if hasattr(email_data, field):
                thread_id = getattr(email_data, field)
                if thread_id and isinstance(thread_id, str) and thread_id.strip():
                    return thread_id.strip()
        
        # Check for thread info in headers
        if hasattr(email_data, 'headers'):
            headers = email_data.headers
            if isinstance(headers, dict):
                # Look for conversation/thread headers
                header_fields = [
                    'Thread-Index',
                    'In-Reply-To', 
                    'References',
                    'Message-ID'
                ]
                
                for header_field in header_fields:
                    if header_field in headers:
                        value = headers[header_field]
                        if value and isinstance(value, str):
                            return value.strip()
        
        # Dictionary format check
        if isinstance(email_data, dict):
            for field in thread_fields:
                if field in email_data:
                    thread_id = email_data[field]
                    if thread_id and isinstance(thread_id, str):
                        return thread_id.strip()
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting thread ID: {e}")
        return None