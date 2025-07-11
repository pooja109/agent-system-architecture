import logging
import asyncio
import signal
import sys
import time
from typing import Optional
from datetime import datetime, timedelta

from config.settings import get_settings, validate_settings
from services.email_service import EmailService

logger = logging.getLogger(__name__)

class EmailProcessor:
    """Main email processing service that runs on a schedule."""
    
    def __init__(self):
        """Initialize the email processor."""
        self.settings = get_settings()
        self.email_service: Optional[EmailService] = None
        self.running = False
        self.last_run_time: Optional[datetime] = None
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
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
            start_time = datetime.now()
            
            # Process pending emails
            results = await self.email_service.process_pending_emails()
            
            # Update last run time
            self.last_run_time = start_time
            
            # Log results
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if results.get('success', False):
                logger.info(f"Email processing completed in {duration:.2f}s: "
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
    
    def _get_next_run_time(self) -> datetime:
        """Calculate next run time based on interval."""
        interval_minutes = self.settings.processing.interval_minutes
        return datetime.now() + timedelta(minutes=interval_minutes)
    
    async def _run_processing_job(self):
        """Run the processing job."""
        try:
            results = await self.process_emails_once()
            return results
            
        except Exception as e:
            logger.error(f"Error in processing job: {e}")
            return {'success': False, 'error': str(e)}
    
    async def run_continuous(self):
        """Run the email processor continuously with scheduled processing."""
        logger.info("Starting continuous email processor...")
        
        self.running = True
        interval_minutes = self.settings.processing.interval_minutes
        interval_seconds = interval_minutes * 60
        
        logger.info(f"Email processing scheduled every {interval_minutes} minutes")
        
        # Run initial processing
        logger.info("Running initial email processing...")
        await self._run_processing_job()
        
        # Main processing loop
        next_run = self._get_next_run_time()
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Check if it's time to run processing
                if current_time >= next_run:
                    logger.info("Running scheduled email processing...")
                    await self._run_processing_job()
                    next_run = self._get_next_run_time()
                
                # Sleep for a short time to avoid busy waiting
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main processing loop: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(30)  # Wait 30 seconds on error
        
        logger.info("Email processor stopped")
    
    async def run_single_batch(self) -> dict:
        """Run a single batch of email processing (useful for testing)."""
        try:
            if not await self.initialize():
                return {'success': False, 'error': 'Failed to initialize'}
            
            results = await self.process_emails_once()
            
            await self.cleanup()
            
            return results
            
        except Exception as e:
            logger.error(f"Error in single batch run: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> dict:
        """Get current processor status."""
        return {
            'running': self.running,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'settings': {
                'interval_minutes': self.settings.processing.interval_minutes,
                'batch_size': self.settings.processing.batch_size,
                'max_retry_attempts': self.settings.processing.max_retry_attempts
            },
            'environment': self.settings.environment
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

async def main():
    """Main entry point for the email processor."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    processor = EmailProcessor()
    
    try:
        # Initialize
        if not await processor.initialize():
            logger.error("Failed to initialize email processor")
            sys.exit(1)
        
        # Check command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            
            if command == 'once':
                # Run once and exit
                logger.info("Running email processor once...")
                results = await processor.process_emails_once()
                print(f"Results: {results}")
                
            elif command == 'test' and len(sys.argv) > 2:
                # Send test email
                test_email = sys.argv[2]
                logger.info(f"Sending test email to {test_email}...")
                results = await processor.test_system(test_email)
                print(f"Test results: {results}")
                
            elif command == 'status':
                # Show status
                status = processor.get_status()
                print(f"Processor status: {status}")
                
            else:
                print("Usage:")
                print("  python -m email.email_processor           # Run continuously")
                print("  python -m email.email_processor once      # Run once and exit")
                print("  python -m email.email_processor test <email>  # Send test email")
                print("  python -m email.email_processor status    # Show status")
                sys.exit(1)
        else:
            # Run continuously
            processor.run_continuous()
    
    except Exception as e:
        logger.error(f"Email processor failed: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        await processor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())