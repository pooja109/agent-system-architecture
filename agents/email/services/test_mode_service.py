"""
Test Mode Service
================

Handles email address overrides and test mode functionality.
"""

import logging
from typing import Optional

from config.settings import AppSettings
from database.models import EmailContent, ResearchOutput

logger = logging.getLogger(__name__)

class TestModeService:
    """Service for handling test mode email overrides."""
    
    def __init__(self, settings: AppSettings):
        """Initialize test mode service."""
        self.settings = settings
        self.test_mode = settings.test_mode.test_mode
        self.override_email = settings.test_mode.test_email_override
        
        if self.test_mode:
            logger.info(f"TEST MODE ENABLED - All emails will be sent to: {self.override_email}")
        else:
            logger.info("Test mode disabled - emails will be sent to actual recipients")
    
    def process_email_content(self, email_content: EmailContent) -> EmailContent:
        """Process email content and apply test mode overrides if enabled."""
        if not self.test_mode:
            return email_content
        
        # Store original email for logging
        original_email = email_content.recipient_email
        
        # Override the recipient email
        email_content.recipient_email = self.override_email
        
        # Modify the subject to indicate test mode
        email_content.subject = f"[TEST MODE] {email_content.subject}"
        
        # Add test mode header to the email body (at the bottom)
        test_header = self._create_test_mode_header(original_email, email_content.customer_name)
        
        email_content.body_html = self._inject_test_header_at_bottom(email_content.body_html, test_header)
        
        logger.info(f"TEST MODE: Redirected email from {original_email} to {self.override_email}")
        logger.info(f"TEST MODE: Customer {email_content.customer_id} - {email_content.customer_name}")
        
        return email_content
    
    def process_research_output(self, research_output: ResearchOutput) -> ResearchOutput:
        """Process research output and apply test mode overrides if enabled."""
        if not self.test_mode:
            return research_output
        
        # Store original contact info for logging
        original_contact = research_output.get_primary_contact()
        if original_contact:
            original_email = original_contact.email
            logger.info(f"TEST MODE: Would have sent to {original_email}, redirecting to {self.override_email}")
            
            # Override the contact email
            original_contact.email = self.override_email
            
            # Update the contact name to indicate test mode
            original_contact.full_name = f"[TEST] {original_contact.full_name or 'Unknown'}"
        
        return research_output
    
    def _create_test_mode_header(self, original_email: str, customer_name: Optional[str] = None) -> str:
        """Create test mode header for email."""
        customer_info = f" for {customer_name}" if customer_name else ""
        return f"""
        <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 10px 0; border-radius: 5px; font-family: Arial, sans-serif;">
            <h3 style="color: #856404; margin-top: 0;">🧪 TEST MODE ACTIVE</h3>
            <p style="color: #856404; margin: 5px 0;"><strong>Original Recipient:</strong> {original_email}</p>
            <p style="color: #856404; margin: 5px 0;"><strong>Customer{customer_info}:</strong> This email would normally be sent to the address above.</p>
            <p style="color: #856404; margin: 5px 0;"><strong>Test Override:</strong> Email redirected to {self.override_email}</p>
        </div>
        """
    
    def _inject_test_header_at_bottom(self, html_content: str, test_header: str) -> str:
        """Inject test mode header at the bottom of HTML email content."""
        try:
            # Try to inject before </body> tag
            if '</body>' in html_content.lower():
                # Find the </body> tag and inject header before it
                body_end = html_content.lower().rfind('</body>')
                if body_end != -1:
                    return (html_content[:body_end] + 
                           test_header + 
                           html_content[body_end:])
            
            # If no </body> tag, try to inject before </html>
            elif '</html>' in html_content.lower():
                html_end = html_content.lower().rfind('</html>')
                if html_end != -1:
                    return (html_content[:html_end] + 
                           test_header + 
                           html_content[html_end:])
            
            # If neither tag found, append to content
            return html_content + test_header
            
        except Exception as e:
            logger.error(f"Error injecting test header at bottom: {e}")
            # If injection fails, just append the header
            return html_content + test_header
    
    def _inject_test_header(self, html_content: str, test_header: str) -> str:
        """Inject test mode header into HTML email content (legacy method - injects at top)."""
        try:
            # Try to inject after <body> tag
            if '<body>' in html_content.lower():
                # Find the <body> tag and inject header after it
                body_start = html_content.lower().find('<body>')
                if body_start != -1:
                    # Find the end of the <body> tag
                    body_tag_end = html_content.find('>', body_start) + 1
                    return (html_content[:body_tag_end] + 
                           test_header + 
                           html_content[body_tag_end:])
            
            # If no <body> tag, try to inject at the beginning of content
            elif '<html>' in html_content.lower():
                html_start = html_content.lower().find('<html>')
                if html_start != -1:
                    # Find the end of the <html> tag
                    html_tag_end = html_content.find('>', html_start) + 1
                    return (html_content[:html_tag_end] + 
                           test_header + 
                           html_content[html_tag_end:])
            
            # If neither tag found, prepend to content
            return test_header + html_content
            
        except Exception as e:
            logger.error(f"Error injecting test header: {e}")
            # If injection fails, just prepend the header
            return test_header + html_content
    
    def get_test_mode_info(self) -> dict:
        """Get test mode information for status/debugging."""
        return {
            'test_mode_enabled': self.test_mode,
            'override_email': self.override_email if self.test_mode else None,
            'environment': self.settings.environment
        }
    
    def log_test_mode_summary(self, email_count: int = 0):
        """Log a summary of test mode activity."""
        if self.test_mode:
            logger.info(f"TEST MODE SUMMARY:")
            logger.info(f"  - Test mode: ENABLED")
            logger.info(f"  - Override email: {self.override_email}")
            logger.info(f"  - Emails processed: {email_count}")
            logger.info(f"  - Environment: {self.settings.environment}")
        else:
            logger.info(f"TEST MODE SUMMARY: Test mode disabled, emails sent to actual recipients")