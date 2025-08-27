import logging
from typing import Optional, Dict, Any, List
import asyncio
import uuid
from datetime import datetime

from config.settings import AppSettings
from database.models import EmailRecord, EmailContent, EmailSendResult, ResearchOutput
from email_clients.azure_email_client import AzureEmailClient
from services.blob_service import BlobStorageService
from services.test_mode_service import TestModeService
from services.pooled_service_base import PooledServiceBase

logger = logging.getLogger(__name__)

class EmailService(PooledServiceBase):
    """Main service for processing and sending emails."""
    
    def __init__(self, databricks_client, settings: AppSettings):
        """Initialize email service with all required clients."""
        super().__init__()
        self.databricks_client = databricks_client  # Store for compatibility
        self.settings = settings
        self.azure_email_client = AzureEmailClient(settings.azure_communication)
        self.blob_service = BlobStorageService(settings.azure_storage)
        self.test_mode_service = TestModeService(settings)
        
    async def initialize(self) -> bool:
        """Initialize all service connections."""
        try:
            # Initialize connection pool reference
            from services.databricks_connection_pool import get_connection_pool
            self._connection_pool = await get_connection_pool()
            
            # Initialize the databricks client's connection pool as well
            self.databricks_client._connection_pool = self._connection_pool
            
            # Test Databricks connection
            if not await self.databricks_client.test_connection():
                logger.error("Databricks connection test failed")
                return False
            
            # Test Azure email connection
            if not await self.azure_email_client.test_connection():
                logger.error("Azure email connection test failed")
                return False
            
            # Test blob storage connection
            if not self.blob_service.test_connection():
                logger.error("Blob storage connection test failed")
                return False
            
            logger.info("All service connections initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize email service: {e}")
            return False
    
    def cleanup(self):
        """Clean up service connections."""
        try:
            # Connection pool cleanup handled globally, no individual cleanup needed
            logger.info("Email service cleanup completed")
        except Exception as e:
            logger.error(f"Error during email service cleanup: {e}")
    
    async def process_pending_emails(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Process all pending emails from the database."""
        batch_size = batch_size or self.settings.processing.batch_size
        
        try:
            # Get pending email records using DatabricksClient
            pending_records = await self.databricks_client.get_pending_emails(limit=batch_size)
            
            if not pending_records:
                logger.info("No pending emails to process")
                return {
                    'success': True,
                    'processed': 0,
                    'sent': 0,
                    'failed': 0,
                    'message': 'No pending emails found'
                }
            
            logger.info(f"Processing {len(pending_records)} pending email records")
            
            # Process each record
            results = {
                'success': True,
                'processed': len(pending_records),
                'sent': 0,
                'failed': 0,
                'details': []
            }
            
            for record in pending_records:
                try:
                    result = await self._process_single_email(record)
                    results['details'].append(result)
                    
                    if result['success']:
                        results['sent'] += 1
                    else:
                        results['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing email for batch_id={record.batch_id}, customer_id={record.customer_id}: {e}")
                    results['failed'] += 1
                    results['details'].append({
                        'batch_id': record.batch_id,
                        'customer_id': record.customer_id,
                        'success': False,
                        'error': str(e)
                    })
            
            logger.info(f"Email processing completed: {results['sent']} sent, {results['failed']} failed")
            return results
            
        except Exception as e:
            logger.error(f"Error processing pending emails: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _process_single_email(self, record: EmailRecord) -> Dict[str, Any]:
        """Process a single email record."""
        try:
            logger.info(f"Processing email for batch_id={record.batch_id}, customer_id={record.customer_id}")
            
            # Step 1: Load email content from blob storage
            email_content = await self._load_email_content_from_blob(record)
            if not email_content:
                error_msg = "Failed to load email content from blob storage"
                logger.error(error_msg)
                
                # Update all communication records with failure
                await self.databricks_client.update_all_customer_records_failed(
                    record.batch_id, 
                    record.customer_id, 
                    error_msg
                )
                
                return {
                    'batch_id': record.batch_id,
                    'customer_id': record.customer_id,
                    'success': False,
                    'error': error_msg
                }
            
            # Step 1.5: Apply test mode overrides if enabled
            original_email = email_content.recipient_email
            email_content = self.test_mode_service.process_email_content(email_content)
            
            # Debug: Check final email content before sending
            logger.info(f"Final email content length: {len(email_content.body_html)} characters")
            # Step 2: Send the email
            send_result = await self.azure_email_client.send_email(
                recipient_email=email_content.recipient_email,
                subject=email_content.subject,
                body_html=email_content.body_html,
                headers={
                    "X-Email-Type": "Communication-Pipeline",
                    "X-Customer-ID": record.customer_id,
                    "X-Batch-ID": str(record.batch_id),
                    "X-Test-Mode": str(self.test_mode_service.test_mode),
                    "X-Original-Recipient": original_email if self.test_mode_service.test_mode else email_content.recipient_email
                }
            )
            
            # Step 3: Update all communication records for this customer
            if send_result.success:
                # Update all communication records with success
                success = await self.databricks_client.update_all_customer_records_sent(
                    batch_id=record.batch_id,
                    customer_id=record.customer_id,
                    sent_email_id=send_result.message_id or str(uuid.uuid4()),
                    recipient_email=email_content.recipient_email,
                    subject=email_content.subject,
                    acs_message_id=send_result.acs_message_id,
                    send_status="sent"
                )
                
                if success:
                    logger.info(f"Successfully sent email to {email_content.recipient_email}")
                    return {
                        'batch_id': record.batch_id,
                        'customer_id': record.customer_id,
                        'success': True,
                        'recipient_email': email_content.recipient_email,
                        'subject': email_content.subject,
                        'message_id': send_result.message_id
                    }
                else:
                    logger.error("Email sent but failed to update database")
                    return {
                        'batch_id': record.batch_id,
                        'customer_id': record.customer_id,
                        'success': False,
                        'error': "Email sent but database update failed"
                    }
            else:
                # Update all communication records with failure
                await self.databricks_client.update_all_customer_records_failed(
                    batch_id=record.batch_id,
                    customer_id=record.customer_id,
                    error_message=send_result.error_message or "Unknown send error",
                    attempted_email=email_content.recipient_email
                )
                
                logger.error(f"Failed to send email: {send_result.error_message}")
                return {
                    'batch_id': record.batch_id,
                    'customer_id': record.customer_id,
                    'success': False,
                    'error': send_result.error_message,
                    'attempted_email': email_content.recipient_email
                }
                
        except Exception as e:
            error_msg = f"Unexpected error processing email: {str(e)}"
            logger.error(error_msg)
            
            # Try to update all communication records with failure
            try:
                await self.databricks_client.update_all_customer_records_failed(
                    record.batch_id, 
                    record.customer_id, 
                    error_msg
                )
            except Exception as db_error:
                logger.error(f"Also failed to update database: {db_error}")
            
            return {
                'batch_id': record.batch_id,
                'customer_id': record.customer_id,
                'success': False,
                'error': error_msg
            }
    
    async def _load_email_content_from_blob(self, record: EmailRecord) -> Optional[EmailContent]:
        """Load email content from blob storage by finding all related communication records."""
        try:
            # Get all communication records for this customer/batch to find the JSON and HTML files
            all_comm_records = await self.databricks_client.get_communication_records_for_customer(
                record.batch_id, record.customer_id
            )
            
            if not all_comm_records:
                logger.error(f"No communication records found for batch_id={record.batch_id}, customer_id={record.customer_id}")
                return None
            
            # Find the JSON research output and HTML email files from the records
            json_blob_name = None
            html_blob_name = None
            
            for comm_record in all_comm_records:
                if comm_record.json_file_path:
                    json_blob_name = self._extract_blob_name_from_url(comm_record.json_file_path)
                elif comm_record.html_file_path:
                    html_blob_name = self._extract_blob_name_from_url(comm_record.html_file_path)
            
            # If we didn't find them in the specific paths, check output_file names
            if not json_blob_name or not html_blob_name:
                for comm_record in all_comm_records:
                    output_file = comm_record.output_file
                    if output_file:
                        blob_name = self._extract_blob_name_from_url(output_file)
                        if blob_name.endswith('_research_output.json') and not json_blob_name:
                            json_blob_name = blob_name
                        elif blob_name.endswith('_email.html') and not html_blob_name:
                            html_blob_name = blob_name
            
            if not json_blob_name:
                logger.error(f"Could not find JSON research output file for customer {record.customer_id}")
                return None
            
            if not html_blob_name:
                logger.error(f"Could not find HTML email file for customer {record.customer_id}")
                return None
            
            # Load research output JSON
            research_output = self.blob_service.load_research_output(json_blob_name)
            if not research_output:
                logger.error(f"Failed to load research output from {json_blob_name}")
                return None
            
            # Apply test mode overrides to research output
            research_output = self.test_mode_service.process_research_output(research_output)
            
            # Load email HTML
            email_html = self.blob_service.load_email_html(html_blob_name)
            if not email_html:
                logger.error(f"Failed to load email HTML from {html_blob_name}")
                return None
                
            # Debug: Check what we actually loaded
            logger.info(f"Loaded email HTML length: {len(email_html)} characters")
            
            # Extract email details
            primary_contact = research_output.get_primary_contact()
            if not primary_contact or not primary_contact.email:
                logger.error("No valid primary contact email found in research output")
                return None
            
            # Create email content
            email_content = EmailContent(
                subject=research_output.sample_email_subject,
                body_html=email_html,
                recipient_email=primary_contact.email,
                customer_id=research_output.customer_id,
                customer_name=research_output.customer_name,
                contact_name=primary_contact.full_name
            )
            
            logger.info(f"Successfully loaded email content for {email_content.recipient_email}")
            return email_content
            
        except Exception as e:
            logger.error(f"Error loading email content from blob: {e}")
            return None
    
    def _extract_blob_name_from_url(self, blob_path: str) -> str:
        """Return blob path as-is since we now store blob paths directly in the database."""
        return blob_path
    
    async def test_email_sending(self, test_email: str) -> Dict[str, Any]:
        """Send a test email to verify the system is working."""
        try:
            test_subject = "SendEmail System Test"
            test_body = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Test Email</title>
            </head>
            <body>
                <p>This is a test email from the SendEmail system.</p>
                <p>If you received this email, the system is working correctly.</p>
                <p>Timestamp: {timestamp}</p>
            </body>
            </html>
            """.format(timestamp=datetime.now().isoformat())
            
            # Apply test mode override to test email if enabled
            if self.test_mode_service.test_mode:
                logger.info(f"TEST MODE: Test email would be sent to {test_email}, redirecting to {self.test_mode_service.override_email}")
                test_email = self.test_mode_service.override_email
                test_subject = f"[TEST MODE] {test_subject}"
                test_body = f"""
                <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0;">
                    <h4>🧪 TEST MODE SYSTEM TEST</h4>
                    <p>This is a system test email running in test mode.</p>
                </div>
                {test_body}
                """
            
            # Send test email
            send_result = await self.azure_email_client.send_email(
                recipient_email=test_email,
                subject=test_subject,
                body_html=test_body,
                headers={
                    "X-Email-Type": "System-Test",
                    "X-Test-Mode": str(self.test_mode_service.test_mode)
                }
            )
            
            if send_result.success:
                logger.info(f"Test email sent successfully to {test_email}")
                return {
                    'success': True,
                    'message': f'Test email sent to {test_email}',
                    'message_id': send_result.message_id
                }
            else:
                logger.error(f"Test email failed: {send_result.error_message}")
                return {
                    'success': False,
                    'error': send_result.error_message
                }
                
        except Exception as e:
            logger.error(f"Error sending test email: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_processing_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get email processing statistics."""
        try:
            stats = await self.databricks_client.get_email_stats(days)
            return stats
        except Exception as e:
            logger.error(f"Error getting processing stats: {e}")
            return {'error': str(e)}