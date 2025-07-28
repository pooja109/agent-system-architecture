"""
Content Formatter Utility
==========================

Utility for converting HTML email content to clean, readable text formats
and applying structured templates for Salesforce case descriptions.
"""

import re
from datetime import datetime, UTC
from html import unescape
from typing import Any

import structlog
from pydantic import BaseModel, Field

try:
    from models.email import Email, EmailAddress
except ImportError:
    from ..models.email import Email, EmailAddress


class ContentFormattingConfig(BaseModel):
    """Configuration for content formatting options."""
    
    content_format: str = Field(
        default="structured", 
        description="Format type: raw, clean_text, structured"
    )
    max_description_length: int = Field(
        default=2000, 
        description="Maximum length for case description"
    )
    preserve_signature: bool = Field(
        default=True, 
        description="Whether to preserve email signature information"
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include customer metadata in description"
    )
    truncate_html_fallback: bool = Field(
        default=True,
        description="Whether to truncate raw HTML if cleaning fails"
    )


class CleanEmailContent(BaseModel):
    """Model for cleaned email content."""
    
    clean_text: str = Field(..., description="Cleaned text content")
    customer_name: str | None = Field(None, description="Extracted customer name")
    customer_email: str = Field(..., description="Customer email address")
    customer_title: str | None = Field(None, description="Customer job title")
    customer_company: str | None = Field(None, description="Customer company")
    signature_info: dict[str, str] = Field(
        default_factory=dict, 
        description="Extracted signature information"
    )
    original_length: int = Field(..., description="Original content length")
    cleaned_length: int = Field(..., description="Cleaned content length")
    processing_success: bool = Field(..., description="Whether cleaning was successful")


class ContentFormatter:
    """Utility class for formatting email content for Salesforce cases."""
    
    def __init__(self, config: ContentFormattingConfig | None = None):
        """Initialize content formatter.
        
        Args:
            config: Configuration for content formatting options
        """
        self.config = config or ContentFormattingConfig()
        self.logger = structlog.get_logger(__name__)
    
    def html_to_clean_text(self, html_content: str) -> str:
        """Convert HTML content to clean, readable text.
        
        Args:
            html_content: Raw HTML content from email
            
        Returns:
            Clean text content with HTML tags and styling removed
            
        Raises:
            ValueError: If HTML content is invalid or empty
        """
        try:
            if not html_content or not isinstance(html_content, str):
                raise ValueError("HTML content must be a non-empty string")
            
            # Remove HTML comments
            text = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
            
            # Remove CSS styles and meta tags
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<meta[^>]*>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove script tags
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            
            # Convert common HTML entities before removing tags
            text = unescape(text)
            
            # Replace <br> and <p> tags with newlines
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)
            
            # Replace div tags with newlines
            text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<div[^>]*>', '', text, flags=re.IGNORECASE)
            
            # Remove all remaining HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            
            # Clean up whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double newlines
            text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
            text = text.strip()
            
            # Remove excessive newlines (more than 2 consecutive)
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            return text
            
        except Exception as e:
            self.logger.error(
                "Failed to convert HTML to clean text",
                error=str(e),
                html_length=len(html_content) if html_content else 0
            )
            # Fallback: return truncated raw content if configured
            if self.config.truncate_html_fallback and html_content:
                return html_content[:500] + "..." if len(html_content) > 500 else html_content
            raise ValueError(f"HTML to text conversion failed: {e}")
    
    def extract_signature_info(self, clean_text: str) -> dict[str, str]:
        """Extract signature information from clean text.
        
        Args:
            clean_text: Cleaned email text content
            
        Returns:
            Dictionary with extracted signature information
        """
        signature_info = {}
        
        try:
            # Common email closings to filter out from being classified as titles
            email_closings = {
                'best regards', 'sincerely', 'thank you', 'thanks', 'regards', 
                'best', 'warmly', 'cheers', 'yours truly', 'kind regards',
                'with regards', 'yours sincerely', 'respectfully', 'cordially'
            }
            
            # Look for common signature patterns
            lines = clean_text.split('\n')
            
            # Find potential signature section (usually after the main message)
            signature_start = -1
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                # Look for signature indicators (but not just closings)
                if any(indicator in line_lower for indicator in [
                    '@', 'phone:', 'mobile:', 'email:'
                ]) or (any(closing in line_lower for closing in email_closings) and i > len(lines) // 2):
                    signature_start = i
                    break
            
            if signature_start >= 0:
                signature_lines = lines[signature_start:]
                
                # Extract email
                for line in signature_lines:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
                    if email_match:
                        signature_info['email'] = email_match.group()
                        break
                
                # Extract phone numbers
                for line in signature_lines:
                    phone_match = re.search(r'(?:phone|tel|mobile|cell)[:.\s]*([+\d\s\-\(\)\.]+)', line, re.IGNORECASE)
                    if phone_match:
                        signature_info['phone'] = phone_match.group(1).strip()
                        break
                
                # Extract company/title information (improved logic)
                for line in signature_lines:
                    line = line.strip()
                    line_lower = line.lower()
                    
                    # Skip empty lines, email closings, and lines with contact info
                    if (not line or 
                        line_lower in email_closings or 
                        line_lower.rstrip(',') in email_closings or
                        any(char in line for char in ['@', 'http']) or
                        any(keyword in line_lower for keyword in ['phone', 'mobile', 'tel', 'cell'])):
                        continue
                    
                    # Look for job titles (lines with common title words)
                    title_indicators = [
                        'architect', 'manager', 'director', 'engineer', 'analyst', 'specialist',
                        'consultant', 'lead', 'senior', 'principal', 'chief', 'vice president',
                        'president', 'officer', 'coordinator', 'supervisor', 'administrator'
                    ]
                    
                    if (line and len(line) < 100 and 
                        any(indicator in line_lower for indicator in title_indicators)):
                        if 'title' not in signature_info:
                            signature_info['title'] = line
                            continue
                    
                    # Company names (non-person names, usually longer or with company indicators)
                    company_indicators = [
                        'inc', 'corp', 'ltd', 'llc', 'company', 'corporation', 'technologies',
                        'solutions', 'systems', 'group', 'consulting', 'services'
                    ]
                    
                    if (line and len(line) < 100 and 'company' not in signature_info and
                        (any(indicator in line_lower for indicator in company_indicators) or
                         (len(line.split()) > 1 and not self._looks_like_person_name(line)))):
                        signature_info['company'] = line
        
        except Exception as e:
            self.logger.warning(
                "Failed to extract signature information",
                error=str(e)
            )
        
        return signature_info
    
    def _looks_like_person_name(self, text: str) -> bool:
        """Check if text looks like a person's name."""
        words = text.split()
        # Simple heuristic: 1-3 words, each word capitalized, no numbers or special chars
        if len(words) > 3:
            return False
        return all(word.istitle() and word.isalpha() for word in words)
    
    def clean_email_content(self, email: Email) -> CleanEmailContent:
        """Process email content and extract clean information.
        
        Args:
            email: Email model to process
            
        Returns:
            CleanEmailContent with processed information
            
        Raises:
            ValueError: If email processing fails
        """
        try:
            if not email or not email.body:
                raise ValueError("Email must have body content")
            
            # Get original content
            original_content = email.body.content
            original_length = len(original_content)
            
            # Convert to clean text
            try:
                clean_text = self.html_to_clean_text(original_content)
                processing_success = True
            except Exception as e:
                self.logger.warning(
                    "HTML cleaning failed, using fallback",
                    error=str(e),
                    email_id=email.id
                )
                clean_text = original_content[:500] + "..." if len(original_content) > 500 else original_content
                processing_success = False
            
            # Extract signature information if enabled
            signature_info = {}
            if self.config.preserve_signature:
                signature_info = self.extract_signature_info(clean_text)
            
            # Extract customer information
            customer_name = None
            customer_title = None
            customer_company = None
            
            if email.sender and email.sender.name:
                customer_name = email.sender.name
            
            # Try to extract title and company from signature
            if signature_info:
                customer_title = signature_info.get('title')
                customer_company = signature_info.get('company')
                
                # Prevent duplicate names: if company matches customer name, clear it
                if customer_company and customer_name and customer_company.strip() == customer_name.strip():
                    customer_company = None
            
            return CleanEmailContent(
                clean_text=clean_text,
                customer_name=customer_name,
                customer_email=email.sender.email if email.sender else "unknown",
                customer_title=customer_title,
                customer_company=customer_company,
                signature_info=signature_info,
                original_length=original_length,
                cleaned_length=len(clean_text),
                processing_success=processing_success
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to clean email content",
                error=str(e),
                email_id=getattr(email, 'id', 'unknown')
            )
            raise ValueError(f"Email content cleaning failed: {e}")
    
    def create_structured_case_description(
        self, 
        email: Email, 
        expert_name: str,
        account_id: str | None = None,
        contact_id: str | None = None
    ) -> str:
        """Create a structured case description using clean content and template.
        
        Args:
            email: Email model
            expert_name: Name of assigned expert
            account_id: Salesforce account ID (optional)
            contact_id: Salesforce contact ID (optional)
            
        Returns:
            Formatted case description string
            
        Raises:
            ValueError: If required parameters are missing
        """
        try:
            if not email or not expert_name:
                raise ValueError("Email and expert_name are required")
            
            # Clean the email content
            clean_content = self.clean_email_content(email)
            
            # Determine response type based on context
            response_type = "POSITIVE"  # Could be made configurable or intelligent
            
            # Build structured description
            description_parts = [
                f"CUSTOMER RESPONSE - {response_type}",
                "",
                "CUSTOMER DETAILS:"
            ]
            
            # Add customer information
            if clean_content.customer_name:
                description_parts.append(f"Name: {clean_content.customer_name}")
            description_parts.append(f"Email: {clean_content.customer_email}")
            
            if clean_content.customer_title:
                description_parts.append(f"Title: {clean_content.customer_title}")
            if clean_content.customer_company:
                description_parts.append(f"Company: {clean_content.customer_company}")
            
            # Add metadata if enabled
            if self.config.include_metadata:
                description_parts.extend([
                    "",
                    "CASE INFORMATION:",
                    f"Subject: {email.subject}",
                    f"Expert Assigned: {expert_name}"
                ])
                
                if account_id:
                    description_parts.append(f"Account ID: {account_id}")
                if contact_id:
                    description_parts.append(f"Contact ID: {contact_id}")
                
                description_parts.append(f"Response Date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
            
            # Add the cleaned message content
            description_parts.extend([
                "",
                "CUSTOMER MESSAGE:",
                clean_content.clean_text
            ])
            
            # Join all parts
            full_description = "\n".join(description_parts)
            
            # Truncate if necessary
            if len(full_description) > self.config.max_description_length:
                truncate_point = self.config.max_description_length - 50
                full_description = full_description[:truncate_point] + "\n\n[Content truncated...]"
            
            self.logger.info(
                "Created structured case description",
                original_length=clean_content.original_length,
                cleaned_length=clean_content.cleaned_length,
                final_length=len(full_description),
                processing_success=clean_content.processing_success,
                email_id=email.id
            )
            
            return full_description
            
        except Exception as e:
            self.logger.error(
                "Failed to create structured case description",
                error=str(e),
                email_id=getattr(email, 'id', 'unknown')
            )
            # Fallback to basic description
            return f"Customer {email.sender.email if email.sender else 'unknown'} responded to outreach.\n\nSubject: {email.subject}\n\nExpert Assigned: {expert_name}"
    
    def format_content(
        self, 
        email: Email, 
        expert_name: str,
        account_id: str | None = None,
        contact_id: str | None = None
    ) -> str:
        """Format email content based on configuration settings.
        
        Args:
            email: Email model
            expert_name: Name of assigned expert  
            account_id: Salesforce account ID (optional)
            contact_id: Salesforce contact ID (optional)
            
        Returns:
            Formatted content string based on configuration
        """
        try:
            if self.config.content_format == "raw":
                # Return raw HTML content
                return email.body.content if email.body else ""
            
            elif self.config.content_format == "clean_text":
                # Return just the cleaned text
                clean_content = self.clean_email_content(email)
                return clean_content.clean_text
            
            elif self.config.content_format == "structured":
                # Return structured template (default)
                return self.create_structured_case_description(
                    email, expert_name, account_id, contact_id
                )
            
            else:
                self.logger.warning(
                    "Unknown content format, using structured",
                    format=self.config.content_format
                )
                return self.create_structured_case_description(
                    email, expert_name, account_id, contact_id
                )
                
        except Exception as e:
            self.logger.error(
                "Content formatting failed, using fallback",
                error=str(e),
                format=self.config.content_format
            )
            # Ultimate fallback
            return f"Customer response received.\nEmail: {email.sender.email if email.sender else 'unknown'}\nSubject: {email.subject}\nExpert: {expert_name}"