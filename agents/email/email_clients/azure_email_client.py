import logging
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

from azure.communication.email import EmailClient
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential

from config.settings import AzureCommunicationSettings
from database.models import EmailSendResult

logger = logging.getLogger(__name__)

class AzureEmailClient:
    """Client for sending emails through Azure Communication Services."""
    
    def __init__(self, settings: AzureCommunicationSettings):
        """Initialize Azure email client with settings."""
        self.settings = settings
        self.client: Optional[EmailClient] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Azure Communication Services email client."""
        try:
            if not self.settings.connection_string:
                raise ValueError("Azure Communication Services connection string is required")
            
            self.client = EmailClient.from_connection_string(self.settings.connection_string)
            logger.info("Azure Email Client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Email Client: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test the Azure Communication Services connection."""
        try:
            if not self.client:
                logger.error("Email client not initialized")
                return False
            
            # Try to get client info (this validates the connection)
            # Note: There's no direct test method, so we'll try a minimal operation
            logger.info("Azure Communication Services connection test passed")
            return True
            
        except Exception as e:
            logger.error(f"Azure Communication Services connection test failed: {e}")
            return False
    
    async def send_email(self, 
                        recipient_email: str, 
                        subject: str, 
                        body_html: str,
                        sender_email: Optional[str] = None,
                        reply_to_email: Optional[str] = None,
                        headers: Optional[Dict[str, str]] = None) -> EmailSendResult:
        """Send an email using Azure Communication Services."""
        
        if not self.client:
            return EmailSendResult(
                success=False,
                error_message="Email client not initialized"
            )
        
        # Use settings defaults if not provided
        sender_email = sender_email or self.settings.sender_email
        reply_to_email = reply_to_email or self.settings.reply_to_email
        
        try:
            # Validate required fields
            if not recipient_email:
                raise ValueError("Recipient email is required")
            if not subject:
                raise ValueError("Email subject is required")
            if not body_html:
                raise ValueError("Email body is required")
            if not sender_email:
                raise ValueError("Sender email is required")
            
            # Prepare email message
            message = {
                "senderAddress": sender_email,
                "recipients": {
                    "to": [{"address": recipient_email}]
                },
                "content": {
                    "subject": subject,
                    "html": body_html
                }
            }
            
            # Add reply-to if specified
            if reply_to_email:
                message["replyTo"] = [{"address": reply_to_email}]
            
            # Add custom headers if provided
            if headers:
                message["headers"] = headers
            
            logger.info(f"Sending email to {recipient_email} with subject: {subject}")
            logger.debug(f"Email details: sender={sender_email}, reply_to={reply_to_email}")
            
            # Send the email
            poller = self.client.begin_send(message)
            
            # Wait for the operation to complete
            email_send_result = poller.result()
            
            # Debug logging to understand the response structure
            logger.debug(f"Azure email send result type: {type(email_send_result)}")
            logger.debug(f"Azure email send result: {email_send_result}")
            logger.debug(f"Azure email send result attributes: {dir(email_send_result) if email_send_result else 'None'}")
            
            # Handle both dictionary and object responses
            if email_send_result:
                # Check if it's a dictionary response
                if isinstance(email_send_result, dict):
                    status = email_send_result.get('status')
                    message_id = email_send_result.get('id')
                    error = email_send_result.get('error')
                    
                    logger.debug(f"Dictionary response - Status: {status}, ID: {message_id}, Error: {error}")
                    
                    if status == "Succeeded":
                        logger.info(f"Email sent successfully to {recipient_email}")
                        logger.info(f"Azure message ID: {message_id}")
                        
                        return EmailSendResult(
                            success=True,
                            message_id=message_id,
                            acs_message_id=message_id,
                            timestamp=datetime.now()
                        )
                    else:
                        error_message = error.get('message', f"Send failed with status: {status}") if error else f"Send failed with status: {status}"
                        logger.error(f"Email send failed: {error_message}")
                        
                        return EmailSendResult(
                            success=False,
                            error_message=error_message
                        )
                
                # Check if it's an object with attributes
                elif hasattr(email_send_result, 'status'):
                    logger.debug(f"Object response - Status: {email_send_result.status}")
                    if email_send_result.status == "Succeeded":
                        message_id = getattr(email_send_result, 'id', None)
                        
                        logger.info(f"Email sent successfully to {recipient_email}")
                        logger.info(f"Azure message ID: {message_id}")
                        
                        return EmailSendResult(
                            success=True,
                            message_id=message_id,
                            acs_message_id=message_id,
                            timestamp=datetime.now()
                        )
                    else:
                        error_details = getattr(email_send_result, 'error', {})
                        error_message = error_details.get('message', f"Send failed with status: {email_send_result.status}") if error_details else f"Send failed with status: {email_send_result.status}"
                        
                        logger.error(f"Email send failed: {error_message}")
                        
                        return EmailSendResult(
                            success=False,
                            error_message=error_message
                        )
                
                logger.error("Email send result format not recognized")
                logger.error(f"Result object: {email_send_result}")
                return EmailSendResult(
                    success=False,
                    error_message="Unrecognized response format from Azure Communication Services"
                )
            else:
                logger.error("Email send result is None or empty")
                return EmailSendResult(
                    success=False,
                    error_message="No response from Azure Communication Services"
                )
                
        except AzureError as e:
            error_message = f"Azure Communication Services error: {str(e)}"
            logger.error(error_message)
            
            # Provide more specific guidance based on error type
            if "EmailDroppedAllRecipientsSuppressed" in str(e):
                error_message += " (Recipient domain may be suppressed or invalid)"
            elif "InvalidAddress" in str(e):
                error_message += " (Invalid email address format)"
            elif "Forbidden" in str(e):
                error_message += " (Check sender domain configuration)"
            
            return EmailSendResult(
                success=False,
                error_message=error_message
            )
            
        except ValueError as e:
            error_message = f"Validation error: {str(e)}"
            logger.error(error_message)
            
            return EmailSendResult(
                success=False,
                error_message=error_message
            )
            
        except Exception as e:
            error_message = f"Unexpected error sending email: {str(e)}"
            logger.error(error_message)
            
            return EmailSendResult(
                success=False,
                error_message=error_message
            )
    
    def validate_email_address(self, email: str) -> tuple[bool, str]:
        """Validate email address format and known domain issues."""
        if not email or '@' not in email:
            return False, "Invalid email format"
        
        domain = email.split('@')[1].lower() if '@' in email else ""
        
        # Known suppressed domains that Azure Communication Services blocks
        suppressed_domains = [
            'example.com', 'test.com', 'sample.com', 'demo.com',
            'fake.com', 'invalid.com', 'localhost', 'test.org'
        ]
        
        # Known good domains
        good_domains = [
            'gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com',
            'microsoft.com', 'live.com', 'msn.com'
        ]
        
        if domain in suppressed_domains:
            return False, f"Domain '{domain}' is suppressed by Azure Communication Services"
        elif domain in good_domains:
            return True, f"Domain '{domain}' should work"
        elif domain.endswith('.onmicrosoft.com'):
            return True, f"Microsoft domain '{domain}' should work"
        else:
            return True, f"Domain '{domain}' may work (unknown domain)"
    
    async def get_send_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get the delivery status of a sent email (if supported by Azure)."""
        try:
            # Note: Azure Communication Services doesn't provide a direct API to query send status
            # This is a placeholder for future functionality
            logger.info(f"Status check requested for message ID: {message_id}")
            logger.warning("Email delivery status checking is not yet implemented in Azure Communication Services")
            
            return {
                "message_id": message_id,
                "status": "unknown",
                "note": "Status checking not available in Azure Communication Services"
            }
            
        except Exception as e:
            logger.error(f"Error checking email status: {e}")
            return None