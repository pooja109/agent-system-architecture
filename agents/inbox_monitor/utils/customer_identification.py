"""
Customer Identification
=======================

Utilities for generating consistent customer IDs and extracting organization information
from email data. Provides privacy-conscious customer identification and business intelligence.
"""

from typing import Dict, Any, Optional
import hashlib
import re
import structlog

logger = structlog.get_logger(__name__)


def extract_customer_metadata(email_data: Optional[Any]) -> Dict[str, Optional[str]]:
    """
    Extract customer ID and organization from email data.
    NOTE: customer_id and customer_organization fields were removed from database schema.
    This function now returns empty metadata to maintain compatibility.
    
    Args:
        email_data: Email data object containing sender information
    
    Returns:
        Dict containing customer_id and customer_organization (both None)
    """
    
    # Return empty metadata since these fields don't exist in the database
    metadata = {
        'customer_id': None,
        'customer_organization': None
    }
    
    logger.debug("Customer identification disabled - fields removed from database schema")
    return metadata
    
    # Original functionality preserved below but commented out:
    """
    Original metadata extraction code:
    
    metadata = {
        'customer_id': None,
        'customer_organization': None
    }
    
    if not email_data:
        logger.warning("No email data available for customer extraction")
        return metadata
    
    try:
        # Extract sender email for ID generation
        sender_email = extract_sender_email(email_data)
        
        if sender_email:
            # Generate consistent customer ID
            metadata['customer_id'] = generate_customer_id(sender_email)
            
            # Extract organization from email domain
            metadata['customer_organization'] = extract_organization_from_email(sender_email)
            
        # Try to enhance organization from email body/signature
        enhanced_org = extract_organization_from_content(email_data)
        if enhanced_org and not metadata['customer_organization']:
            metadata['customer_organization'] = enhanced_org
        
        logger.debug(f"Extracted customer metadata: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting customer metadata: {e}")
        return metadata
"""


def generate_customer_id(sender_email: str) -> str:
    """
    Generate a consistent, privacy-conscious customer ID from sender email.
    
    Uses email domain + local part hash for consistency while preserving privacy.
    
    Args:
        sender_email: Email address to generate ID from
        
    Returns:
        Consistent customer identifier
    """
    
    try:
        # Split email into local and domain parts
        local_part, domain = sender_email.lower().split('@', 1)
        
        # Create hash of local part for privacy
        local_hash = hashlib.md5(local_part.encode()).hexdigest()[:8]
        
        # Clean domain for readability
        domain_clean = domain.replace('.', '_').replace('-', '_')
        
        # Combine for readable but consistent ID
        customer_id = f"{domain_clean}_{local_hash}"
        
        # Truncate if too long
        if len(customer_id) > 50:
            customer_id = customer_id[:50]
        
        return customer_id
        
    except Exception as e:
        logger.error(f"Error generating customer ID for {sender_email}: {e}")
        # Fallback to simple hash
        return hashlib.md5(sender_email.lower().encode()).hexdigest()[:16]


def extract_organization_from_email(sender_email: str) -> Optional[str]:
    """Extract organization name from email domain."""
    
    try:
        domain = sender_email.split('@')[1].lower()
        
        # Remove common TLDs and format nicely
        domain_parts = domain.split('.')
        
        # Skip generic email providers
        generic_providers = {
            'gmail', 'outlook', 'hotmail', 'yahoo', 'aol', 'icloud',
            'live', 'msn', 'comcast', 'verizon', 'att'
        }
        
        if domain_parts[0] in generic_providers:
            return f"Personal Email ({domain_parts[0].title()})"
        
        # Extract organization name (usually first part of domain)
        org_name = domain_parts[0].replace('-', ' ').replace('_', ' ').title()
        
        # Add domain context for clarity
        if len(domain_parts) > 2:
            tld = '.'.join(domain_parts[-2:])
            return f"{org_name} ({tld})"
        else:
            return org_name
        
    except Exception as e:
        logger.error(f"Error extracting organization from {sender_email}: {e}")
        return None


def extract_organization_from_content(email_data: Optional[Any]) -> Optional[str]:
    """
    Extract organization name from email signature or content.
    
    This is a basic implementation that looks for common signature patterns.
    
    Args:
        email_data: Email data object with body content
        
    Returns:
        Organization name if found, None otherwise
    """
    
    if not email_data:
        return None
    
    try:
        # Get email body content
        body_content = get_email_body_content(email_data)
        if not body_content:
            return None
        
        # Look for signature patterns
        signature_patterns = [
            r'(?:Best regards?|Sincerely|Thanks?),?\s*\n.*?\n([A-Z][A-Za-z\s&]+(?:Inc|Corp|LLC|Ltd|Company|Co\.))',
            r'([A-Z][A-Za-z\s&]+(?:Inc|Corp|LLC|Ltd|Company|Co\.))\s*\n',
            r'Phone:.*?\n.*?([A-Z][A-Za-z\s&]+(?:Inc|Corp|LLC|Ltd|Company|Co\.))',
        ]
        
        for pattern in signature_patterns:
            match = re.search(pattern, body_content, re.IGNORECASE | re.MULTILINE)
            if match:
                org_name = match.group(1).strip()
                if len(org_name) < 100:  # Reasonable length check
                    return org_name
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting organization from content: {e}")
        return None


def extract_sender_email(email_data: Optional[Any]) -> Optional[str]:
    """Extract sender email address from various email data formats."""
    
    if not email_data:
        return None
    
    try:
        # EmailAddress object format
        if hasattr(email_data, 'sender') and email_data.sender:
            sender = email_data.sender
            if hasattr(sender, 'email_address'):
                return sender.email_address
            elif hasattr(sender, 'email'):
                return sender.email
        
        # Dictionary format
        elif hasattr(email_data, 'sender') and isinstance(email_data.sender, dict):
            sender_dict = email_data.sender
            return sender_dict.get('email_address') or sender_dict.get('email')
        
        # Direct email field
        elif hasattr(email_data, 'from_email'):
            return email_data.from_email
        
        # Sender email field
        elif hasattr(email_data, 'sender_email'):
            return email_data.sender_email
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting sender email: {e}")
        return None


def get_email_body_content(email_data: Optional[Any]) -> Optional[str]:
    """Extract email body content for signature parsing."""
    
    if not email_data:
        return None
    
    try:
        # Try various body field names
        body_fields = ['body', 'body_content', 'content', 'message_body']
        
        for field in body_fields:
            if hasattr(email_data, field):
                body = getattr(email_data, field)
                if isinstance(body, str) and body.strip():
                    return body
                elif hasattr(body, 'content'):
                    return body.content
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting email body content: {e}")
        return None