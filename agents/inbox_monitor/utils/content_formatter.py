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
from zoneinfo import ZoneInfo

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
        default=5000, 
        description="Maximum length for case description (increased from 2000 for better content retention)"
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


class OriginalEmailContent(BaseModel):
    """Model for extracted original outbound email content."""
    
    subject: str | None = Field(None, description="Original email subject")
    sender_name: str | None = Field(None, description="Original sender name")
    sender_email: str | None = Field(None, description="Original sender email")
    sent_date: str | None = Field(None, description="Original send date")
    body_content: str | None = Field(None, description="Original email body content")
    clean_body: str | None = Field(None, description="Cleaned original email body")
    found: bool = Field(default=False, description="Whether original content was found")
    extraction_method: str | None = Field(None, description="Method used to extract content")


class ConversationContext(BaseModel):
    """Model for email conversation context."""
    
    customer_response: str = Field(..., description="Customer's new response")
    original_email: OriginalEmailContent | None = Field(None, description="Original outbound email")
    conversation_id: str | None = Field(None, description="Email conversation ID")
    thread_references: list[str] = Field(default_factory=list, description="Email thread references")
    has_conversation_context: bool = Field(default=False, description="Whether conversation context was found")


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
    conversation_context: ConversationContext | None = Field(None, description="Conversation context if available")


class ContentFormatter:
    """Utility class for formatting email content for Salesforce cases."""
    
    def __init__(self, config: ContentFormattingConfig | None = None):
        """Initialize content formatter.
        
        Args:
            config: Configuration for content formatting options
        """
        self.config = config or ContentFormattingConfig()
        self.logger = structlog.get_logger(__name__)
        # Boston/Eastern timezone with automatic DST handling
        self.eastern_tz = ZoneInfo("America/New_York")
    
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
            # Fallback: return truncated raw content if configured (increased from 500 for better retention)
            if self.config.truncate_html_fallback and html_content:
                return html_content[:5000] + "..." if len(html_content) > 5000 else html_content
            raise ValueError(f"HTML to text conversion failed: {e}")
    
    def extract_original_email_content(self, html_content: str) -> OriginalEmailContent:
        """Extract original outbound email content from reply email HTML.
        
        Args:
            html_content: HTML content from customer reply email
            
        Returns:
            OriginalEmailContent with extracted information
        """
        try:
            if not html_content:
                return OriginalEmailContent(found=False, extraction_method="no_content")
            
            # Look for forwarded/replied email section
            # Pattern 1: Look for "From:" header in forwarded email
            from_match = re.search(
                r'<b>From:</b>\s*([^<]+)<[^>]*>.*?<br><b>Sent:</b>\s*([^<]+)<[^>]*>.*?<b>Subject:</b>\s*([^<]+)<',
                html_content,
                re.DOTALL | re.IGNORECASE
            )
            
            original_content = OriginalEmailContent()
            
            if from_match:
                # Extract header information
                from_info = from_match.group(1).strip()
                sent_info = from_match.group(2).strip() 
                subject_info = from_match.group(3).strip()
                
                # Parse sender info (format: "Name <email>" or just "email")
                sender_match = re.search(r'([^<]+)<([^>]+)>', from_info)
                if sender_match:
                    original_content.sender_name = sender_match.group(1).strip()
                    original_content.sender_email = sender_match.group(2).strip()
                else:
                    # Just email address
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_info)
                    if email_match:
                        original_content.sender_email = email_match.group().strip()
                
                original_content.sent_date = sent_info
                original_content.subject = subject_info
                original_content.found = True
                original_content.extraction_method = "from_header_pattern"
                
                # Extract the body content after the headers
                # Look for content after the subject line and before any signatures
                body_start = from_match.end()
                remaining_html = html_content[body_start:]
                
                # Remove the divider and get the original email body
                # Look for the actual email content, skipping navigation elements
                body_match = re.search(
                    r'</div>\s*(.+?)(?:<hr|<div[^>]*style[^>]*background-color[^>]*#fff3cd|$)',
                    remaining_html,
                    re.DOTALL | re.IGNORECASE
                )
                
                if body_match:
                    original_body_html = body_match.group(1)
                    original_content.body_content = original_body_html
                    
                    # Clean the HTML to get readable text
                    try:
                        original_content.clean_body = self.html_to_clean_text(original_body_html)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to clean original email HTML",
                            error=str(e)
                        )
                        # Fallback: basic HTML tag removal
                        clean_text = re.sub(r'<[^>]+>', '', original_body_html)
                        clean_text = unescape(clean_text)
                        original_content.clean_body = clean_text.strip()
                
            else:
                # Pattern 2: Look for horizontal rule separator and quoted content
                hr_match = re.search(r'<hr[^>]*>.*?<div[^>]*divRplyFwdMsg', html_content, re.DOTALL | re.IGNORECASE)
                if hr_match:
                    # Found reply/forward section, extract content after it
                    quoted_section = html_content[hr_match.end():]
                    
                    # Extract From, Sent, and Subject information
                    from_match = re.search(r'<b>From:</b>\s*([^<]+)<', quoted_section, re.IGNORECASE)
                    sent_match = re.search(r'<b>Sent:</b>\s*([^<]+)<', quoted_section, re.IGNORECASE)
                    subject_match = re.search(r'<b>Subject:</b>\s*([^<]+)', quoted_section, re.IGNORECASE)
                    
                    if subject_match:
                        original_content.subject = subject_match.group(1).strip()
                        original_content.found = True
                        original_content.extraction_method = "hr_separator_pattern"
                        
                        # Extract From information if available
                        if from_match:
                            from_info = from_match.group(1).strip()
                            # Parse sender info (format: "Name &lt;email&gt;" or just "email")
                            sender_match = re.search(r'([^&]+)&lt;([^&]+)&gt;', from_info)
                            if sender_match:
                                original_content.sender_name = sender_match.group(1).strip()
                                original_content.sender_email = sender_match.group(2).strip()
                            else:
                                # Just email address or name
                                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_info)
                                if email_match:
                                    original_content.sender_email = email_match.group().strip()
                        
                        # Extract Sent date if available
                        if sent_match:
                            original_content.sent_date = sent_match.group(1).strip()
                        
                        # Extract the body content
                        body_start = subject_match.end()
                        remaining_html = quoted_section[body_start:]
                        
                        # Get content until test mode section or end
                        body_match = re.search(
                            r'</div>\s*(.+?)(?:<div[^>]*style[^>]*background-color[^>]*#fff3cd|$)',
                            remaining_html,
                            re.DOTALL | re.IGNORECASE
                        )
                        
                        if body_match:
                            original_body_html = body_match.group(1)
                            original_content.body_content = original_body_html
                            
                            try:
                                original_content.clean_body = self.html_to_clean_text(original_body_html)
                            except Exception:
                                # Fallback cleanup
                                clean_text = re.sub(r'<[^>]+>', '', original_body_html)
                                clean_text = unescape(clean_text)
                                original_content.clean_body = clean_text.strip()
                
                if not original_content.found:
                    original_content.extraction_method = "no_pattern_matched"
            
            self.logger.info(
                "Original email extraction completed",
                found=original_content.found,
                method=original_content.extraction_method,
                has_subject=bool(original_content.subject),
                has_body=bool(original_content.clean_body)
            )
            
            return original_content
            
        except Exception as e:
            self.logger.error(
                "Failed to extract original email content",
                error=str(e)
            )
            return OriginalEmailContent(
                found=False,
                extraction_method=f"error: {str(e)}"
            )
    
    def extract_conversation_context(self, email: Email) -> ConversationContext:
        """Extract conversation context from email including original outbound content.
        
        Args:
            email: Email model to analyze
            
        Returns:
            ConversationContext with customer response and original email
        """
        try:
            if not email or not email.body:
                return ConversationContext(
                    customer_response="No email content available",
                    has_conversation_context=False
                )
            
            html_content = email.body.content
            
            # Extract customer's new response (content before the reply separator)
            customer_response = ""
            
            # Look for content before horizontal rule or "From:" header
            hr_split = re.split(r'<hr[^>]*>|<div[^>]*id="divRplyFwdMsg"', html_content, maxsplit=1, flags=re.IGNORECASE)
            if len(hr_split) > 1:
                # Customer response is before the separator
                customer_html = hr_split[0]
                try:
                    customer_response = self.html_to_clean_text(customer_html).strip()
                except Exception:
                    # Fallback
                    customer_response = re.sub(r'<[^>]+>', '', customer_html).strip()
                    customer_response = unescape(customer_response)
            else:
                # No clear separator, use the whole content as customer response
                try:
                    customer_response = self.html_to_clean_text(html_content).strip()
                except Exception:
                    customer_response = re.sub(r'<[^>]+>', '', html_content).strip()
                    customer_response = unescape(customer_response)
            
            # Extract original email content
            original_email = self.extract_original_email_content(html_content)
            
            # Get thread references from email headers
            thread_references = []
            if email.internet_message_headers:
                references = email.internet_message_headers.get('References', '')
                in_reply_to = email.internet_message_headers.get('In-Reply-To', '')
                if references:
                    thread_references.append(references)
                if in_reply_to and in_reply_to not in thread_references:
                    thread_references.append(in_reply_to)
            
            context = ConversationContext(
                customer_response=customer_response or "No customer response text found",
                original_email=original_email if original_email.found else None,
                conversation_id=email.conversation_id,
                thread_references=thread_references,
                has_conversation_context=original_email.found
            )
            
            self.logger.info(
                "Conversation context extracted",
                has_original_email=original_email.found,
                customer_response_length=len(customer_response),
                thread_references_count=len(thread_references)
            )
            
            return context
            
        except Exception as e:
            self.logger.error(
                "Failed to extract conversation context",
                error=str(e),
                email_id=getattr(email, 'id', 'unknown')
            )
            return ConversationContext(
                customer_response="Error extracting customer response",
                has_conversation_context=False
            )
    
    def extract_signature_info(self, clean_text: str) -> dict[str, str]:
        """Extract signature information from clean text with conservative validation.
        
        Args:
            clean_text: Cleaned email text content (should be customer response only)
            
        Returns:
            Dictionary with extracted signature information
        """
        signature_info = {}
        
        try:
            # Common email closings to filter out from being classified as titles
            email_closings = {
                'best regards', 'sincerely', 'thank you', 'thanks', 'regards', 
                'best', 'warmly', 'cheers', 'yours truly', 'kind regards',
                'with regards', 'yours sincerely', 'respectfully', 'cordially',
                'best wishes', 'looking forward', 'talk soon'
            }
            
            # Phrases that should never be considered titles or companies
            invalid_content = {
                'thank you for', 'i hope', 'please let me know', 'would you', 'can you',
                'looking forward', 'hope this', 'let me know', 'please have', 'i am interested'
            }
            
            # Look for common signature patterns
            lines = clean_text.split('\n')
            
            # Only look at the last few lines for signature (be more conservative)
            # Signatures typically appear in the last 1-4 lines of a message
            max_signature_lines = min(4, len(lines))
            signature_lines = lines[-max_signature_lines:] if len(lines) > 1 else lines
            
            # Extract email (most reliable signature indicator)
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
            
            # Conservative title/company extraction
            for line in signature_lines:
                line = line.strip()
                line_lower = line.lower()
                
                # Skip empty lines, email closings, contact info, and invalid content
                if (not line or 
                    line_lower in email_closings or 
                    line_lower.rstrip(',') in email_closings or
                    any(char in line for char in ['@', 'http']) or
                    any(keyword in line_lower for keyword in ['phone', 'mobile', 'tel', 'cell']) or
                    any(invalid in line_lower for invalid in invalid_content)):
                    continue
                
                # Be very conservative about titles - only accept clear job titles
                clear_title_indicators = [
                    'manager', 'director', 'president', 'officer', 'engineer', 'analyst',
                    'specialist', 'consultant', 'lead', 'senior', 'principal', 'chief',
                    'coordinator', 'supervisor', 'administrator', 'executive'
                ]
                
                # Title must contain a clear indicator AND be reasonably short AND not look like a sentence
                if (line and 
                    len(line) < 60 and  # Shorter length limit
                    len(line.split()) <= 5 and  # Not too many words
                    any(indicator in line_lower for indicator in clear_title_indicators) and
                    not line.endswith('.') and  # Not a sentence
                    'title' not in signature_info):
                    signature_info['title'] = line
                    continue
                
                # Very conservative company extraction - only with clear corporate indicators
                clear_company_indicators = [
                    'inc.', 'corp.', 'ltd.', 'llc', 'corporation', 'company',
                    'technologies', 'systems', 'group', 'consulting', 'services'
                ]
                
                # Company must have clear corporate indicators AND be reasonable length
                if (line and 
                    len(line) < 80 and
                    len(line.split()) <= 6 and
                    any(indicator in line_lower for indicator in clear_company_indicators) and
                    not self._looks_like_person_name(line) and
                    'company' not in signature_info):
                    signature_info['company'] = line
        
        except Exception as e:
            self.logger.warning(
                "Failed to extract signature information",
                error=str(e)
            )
        
        # Final validation - remove anything that still looks suspicious
        validated_info = {}
        
        # Only keep email if it looks valid
        if 'email' in signature_info:
            validated_info['email'] = signature_info['email']
        
        # Only keep phone if it looks valid
        if 'phone' in signature_info:
            validated_info['phone'] = signature_info['phone']
        
        # Be extra conservative with title - must not contain suspicious phrases
        if 'title' in signature_info:
            title = signature_info['title']
            if (not any(phrase in title.lower() for phrase in ['thank you', 'hope', 'please', 'would', 'can']) and
                len(title.split()) <= 5):
                validated_info['title'] = title
        
        # Be extra conservative with company - must not look like email content
        if 'company' in signature_info:
            company = signature_info['company']
            if (not any(phrase in company.lower() for phrase in ['thank you', 'hope', 'please', 'would', 'can']) and
                not company.lower().startswith('i ') and
                len(company.split()) <= 6):
                validated_info['company'] = company
        
        return validated_info
    
    def _parse_original_sent_date(self, sent_date_str: str) -> datetime | None:
        """Parse original email sent date from forwarded email header.
        
        Args:
            sent_date_str: Date string from forwarded email (e.g., "Wednesday, July 30, 2025 6:26 AM")
            
        Returns:
            Parsed datetime object in UTC, or None if parsing fails
        """
        try:
            if not sent_date_str:
                return None
            
            # Clean HTML entities and extra whitespace
            import html
            cleaned_str = html.unescape(sent_date_str).strip()
            self.logger.info(f"Cleaned sent date string: '{sent_date_str}' -> '{cleaned_str}'")
            
            # Use cleaned string for parsing
            sent_date_str = cleaned_str
            
            # Common date formats from forwarded emails
            formats_to_try = [
                # "Wednesday, July 30, 2025 6:26 AM"
                "%A, %B %d, %Y %I:%M %p",
                # "Wed, Jul 30, 2025 6:26 AM" 
                "%a, %b %d, %Y %I:%M %p",
                # "July 30, 2025 6:26 AM"
                "%B %d, %Y %I:%M %p",
                # "7/30/2025 6:26 AM"
                "%m/%d/%Y %I:%M %p",
                # "2025-07-30 06:26 AM"
                "%Y-%m-%d %I:%M %p",
                # ISO format with timezone
                "%Y-%m-%dT%H:%M:%S%z",
                # ISO format without timezone  
                "%Y-%m-%dT%H:%M:%S"
            ]
            
            for date_format in formats_to_try:
                try:
                    # Parse the date string
                    parsed_dt = datetime.strptime(sent_date_str.strip(), date_format)
                    
                    # If no timezone info, assume it's in the same timezone as the current processing
                    if parsed_dt.tzinfo is None:
                        # Default to Eastern time for original emails (since company is Boston-based)
                        parsed_dt = parsed_dt.replace(tzinfo=self.eastern_tz)
                    
                    # Convert to UTC for consistent storage/comparison
                    result_utc = parsed_dt.astimezone(UTC)
                    self.logger.info(f"Successfully parsed '{sent_date_str}' using format '{date_format}' -> {parsed_dt} -> {result_utc} UTC")
                    return result_utc
                    
                except ValueError:
                    continue
            
            # If all formats fail, try a more flexible approach
            try:
                from dateutil import parser
                parsed_dt = parser.parse(sent_date_str)
                
                # If no timezone, assume Eastern
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=self.eastern_tz)
                
                return parsed_dt.astimezone(UTC)
                
            except Exception:
                self.logger.warning(
                    "Failed to parse original email sent date",
                    sent_date_str=sent_date_str
                )
                return None
                
        except Exception as e:
            self.logger.warning(
                "Error parsing original email sent date",
                error=str(e),
                sent_date_str=sent_date_str
            )
            return None
    
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
                clean_text = original_content[:5000] + "..." if len(original_content) > 5000 else original_content
                processing_success = False
            
            # Extract signature information if enabled - only from customer response section
            signature_info = {}
            if self.config.preserve_signature:
                # Extract conversation context first to get customer response only
                temp_conversation_context = None
                try:
                    temp_conversation_context = self.extract_conversation_context(email)
                except Exception:
                    pass
                
                # Use only customer response for signature extraction
                if temp_conversation_context and temp_conversation_context.customer_response:
                    signature_info = self.extract_signature_info(temp_conversation_context.customer_response)
                else:
                    # Fallback to full content if conversation context extraction fails
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
            
            # Extract conversation context (original email + customer response)
            conversation_context = None
            try:
                conversation_context = self.extract_conversation_context(email)
            except Exception as e:
                self.logger.warning(
                    "Failed to extract conversation context",
                    error=str(e),
                    email_id=email.id
                )
            
            return CleanEmailContent(
                clean_text=clean_text,
                customer_name=customer_name,
                customer_email=email.sender.email if email.sender else "unknown",
                customer_title=customer_title,
                customer_company=customer_company,
                signature_info=signature_info,
                original_length=original_length,
                cleaned_length=len(clean_text),
                processing_success=processing_success,
                conversation_context=conversation_context
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
                
                # Add original email sent date and customer response date in Eastern Time
                customer_response_et = email.received_datetime.astimezone(self.eastern_tz)
                description_parts.append(f"Customer Response Date: {customer_response_et.strftime('%Y-%m-%d %H:%M %Z')}")
                
                # Add original email sent date if available from conversation context
                if (clean_content.conversation_context and 
                    clean_content.conversation_context.has_conversation_context and
                    clean_content.conversation_context.original_email and
                    clean_content.conversation_context.original_email.sent_date):
                    
                    self.logger.info(f"Parsing original sent date: '{clean_content.conversation_context.original_email.sent_date}'")
                    original_sent_date = self._parse_original_sent_date(
                        clean_content.conversation_context.original_email.sent_date
                    )
                    self.logger.info(f"Parsed original sent date: {original_sent_date}")
                    if original_sent_date:
                        original_sent_et = original_sent_date.astimezone(self.eastern_tz)
                        description_parts.append(f"Original Email Sent: {original_sent_et.strftime('%Y-%m-%d %H:%M %Z')}")
                        
                        # Calculate response time
                        response_time = email.received_datetime - original_sent_date
                        self.logger.info(f"Response time calculation: {email.received_datetime} - {original_sent_date} = {response_time.total_seconds()} seconds")
                        if response_time.total_seconds() > 0:
                            hours = int(response_time.total_seconds() // 3600)
                            minutes = int((response_time.total_seconds() % 3600) // 60)
                            if hours > 24:
                                days = hours // 24
                                hours = hours % 24
                                description_parts.append(f"Response Time: {days}d {hours}h {minutes}m")
                            else:
                                description_parts.append(f"Response Time: {hours}h {minutes}m")
                        else:
                            self.logger.warning(f"Response time is negative or zero: {response_time.total_seconds()} seconds")
                    else:
                        self.logger.warning("Failed to parse original sent date")
            
            # Add conversation context if available
            if (clean_content.conversation_context and 
                clean_content.conversation_context.has_conversation_context and
                clean_content.conversation_context.original_email):
                
                # Add customer's new response
                description_parts.extend([
                    "",
                    "CUSTOMER RESPONSE:",
                    clean_content.conversation_context.customer_response
                ])
                
                # Add original outbound email context
                original = clean_content.conversation_context.original_email
                description_parts.extend([
                    "",
                    "ORIGINAL OUTBOUND EMAIL:"
                ])
                
                if original.subject:
                    description_parts.append(f"Subject: {original.subject}")
                if original.sender_name and original.sender_email:
                    description_parts.append(f"From: {original.sender_name} <{original.sender_email}>")
                elif original.sender_email:
                    description_parts.append(f"From: {original.sender_email}")
                # Original sent date already shown in CASE INFORMATION section
                # if original.sent_date:
                #     description_parts.append(f"Sent: {original.sent_date}")
                
                if original.clean_body:
                    description_parts.extend([
                        "",
                        "Original Message:",
                        original.clean_body
                    ])
                
                # Thread references removed - no longer needed for Lowtouch Experts
            else:
                # Fallback to original behavior when no conversation context
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
            
            # Log enhanced information
            has_conversation_context = (
                clean_content.conversation_context and 
                clean_content.conversation_context.has_conversation_context
            )
            
            self.logger.info(
                "Created structured case description",
                original_length=clean_content.original_length,
                cleaned_length=clean_content.cleaned_length,
                final_length=len(full_description),
                processing_success=clean_content.processing_success,
                has_conversation_context=has_conversation_context,
                has_original_email=bool(
                    has_conversation_context and
                    clean_content.conversation_context.original_email
                ),
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