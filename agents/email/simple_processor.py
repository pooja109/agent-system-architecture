"""
Simple Email Processor for main.py usage
"""
import logging
import asyncio
from typing import Optional

from config.settings import get_settings, validate_settings
from services.email_service import EmailService

logger = logging.getLogger(__name__)

class SimpleEmailProcessor:
    """Simplified email processor for main.py usage."""
    
    def __init__(self):
        """Initialize the simple email processor."""
        self.settings = get_settings()
        self.email_service: Optional[EmailService] = None
    
    async def initialize(self) -> bool:
        """Initialize the email processor and all services."""
        try:
            # Validate settings
            validate_settings(self.settings)
            logger.info("Settings validation passed")
            
            # Initialize email service
            self.email_service = EmailService(self.settings)
            
            if not await self.email_service.initialize():
                logger.error("Failed to initialize email service")
                return False
            
            logger.info("Email processor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize email processor: {e}")
            return False
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.email_service:
                self.email_service.cleanup()
            logger.info("Email processor cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def process_emails_once(self) -> dict:
        """Process emails once and return results."""
        if not self.email_service:
            raise RuntimeError("Email service not initialized")
        
        try:
            logger.info("Starting email processing batch...")
            
            # Process pending emails
            results = await self.email_service.process_pending_emails()
            
            # Log results
            if results.get('success', False):
                logger.info(f"Email processing completed: "
                          f"{results.get('sent', 0)} sent, {results.get('failed', 0)} failed")
            else:
                logger.error(f"Email processing failed: {results.get('error', 'Unknown error')}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error during email processing: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_system(self, test_email: str) -> dict:
        """Test the email system with a test email."""
        try:
            if not self.email_service:
                if not await self.initialize():
                    return {'success': False, 'error': 'Failed to initialize email service'}
            
            # Send test email
            result = await self.email_service.test_email_sending(test_email)
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing system: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> dict:
        """Get current processor status."""
        return {
            'settings': {
                'interval_minutes': self.settings.processing.interval_minutes,
                'batch_size': self.settings.processing.batch_size,
                'max_retry_attempts': self.settings.processing.max_retry_attempts
            },
            'environment': self.settings.environment
        }