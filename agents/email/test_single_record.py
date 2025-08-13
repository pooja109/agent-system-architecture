#!/usr/bin/env python3
"""
Test Single Record (Working Version)
====================================

Test the SendEmail system with a single record from the Databricks table.
This version bypasses the connection pool issues and works directly with components.
"""

import asyncio
import sys
import os
import time
import json
from typing import Optional

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.databricks_oauth_client import DatabricksOAuthClient
from services.azure_key_vault_client import AzureKeyVaultClient
from email_clients.azure_email_client import AzureEmailClient
from services.blob_service import BlobStorageService
from services.test_mode_service import TestModeService
from database.models import EmailRecord, EmailContent, EmailSendResult, ResearchOutput

async def get_email_record_from_db(oauth_client, settings, customer_id=None, batch_id=None):
    """Get email record from database using direct OAuth client."""
    
    table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.email_communication_pipeline{settings.databricks_oauth.table_suffix}"
    
    if customer_id and batch_id:
        # Get specific record
        query = f"""
        SELECT * FROM {table_name}
        WHERE customer_id = '{customer_id}' AND batch_id = {batch_id}
        ORDER BY created_at DESC
        LIMIT 1
        """
        print(f"📊 Querying for specific record: customer_id={customer_id}, batch_id={batch_id}")
        
    elif customer_id:
        # Get latest record for customer
        query = f"""
        SELECT * FROM {table_name}
        WHERE customer_id = '{customer_id}'
        ORDER BY created_at DESC
        LIMIT 1
        """
        print(f"📊 Querying for customer record: customer_id={customer_id}")
        
    else:
        # Get any pending record
        query = f"""
        SELECT * FROM {table_name}
        WHERE agent_name = 'communication'
        AND status = 'S'
        AND (is_email_sent IS NULL OR is_email_sent = false)
        ORDER BY created_at DESC
        LIMIT 1
        """
        print("📊 Querying for any pending record")
    
    result = await oauth_client.execute_sql(query)
    
    if result.row_count == 0:
        print("❌ No records found matching criteria")
        return None
        
    record_data = result.rows[0]
    print(f"✅ Found record:")
    print(f"   📧 Customer ID: {record_data.get('customer_id', 'Unknown')}")
    print(f"   📦 Batch ID: {record_data.get('batch_id', 'Unknown')}")
    print(f"   📅 Run Date: {record_data.get('run_date', 'Unknown')}")
    print(f"   📋 Status: {record_data.get('send_status', 'Unknown')}")
    
    # Show ALL file-related fields to identify the HTML file path
    print("   📂 All file fields:")
    for key, value in record_data.items():
        if value and ('file' in key.lower() or 'path' in key.lower() or 'html' in key.lower()):
            print(f"      {key}: {value}")
    print()
    
    # Create EmailRecord from database result
    email_record = EmailRecord(
        batch_id=record_data.get('batch_id'),
        run_date=record_data.get('run_date'),
        agent_name=record_data.get('agent_name', 'communication'),
        status=record_data.get('status', 'S'),
        customer_id=record_data.get('customer_id'),
        input_file=record_data.get('input_file'),
        output_file=record_data.get('output_file'),
        is_email_sent=record_data.get('is_email_sent'),
        send_status=record_data.get('send_status'),
        created_at=record_data.get('created_at'),
        updated_at=record_data.get('updated_at')
    )
    
    # Add the HTML file path as a dynamic attribute since it's not in the EmailRecord model
    email_record.html_file_path = record_data.get('html_file_path')
    
    return email_record

async def get_research_output(blob_service, email_record):
    """Get research output from blob storage."""
    try:
        # Build the expected blob path based on email record
        if not email_record.input_file:
            print("⚠️  No input file specified in email record")
            return None
            
        print(f"📁 Loading research output from: {email_record.input_file}")
        research_content = blob_service.download_blob_content(email_record.input_file)
        
        if not research_content:
            print("❌ Failed to load research output")
            return None
        
        # Check if it's a markdown file or JSON file
        if email_record.input_file.endswith('.md'):
            print("⚠️  Input file is markdown format, not JSON. Creating mock research output.")
            
            # Create a basic ResearchOutput for testing
            from database.models import ContactInfo
            mock_contact = ContactInfo(
                first_name="Test",
                last_name="User",
                full_name="Test User",
                email="test@example.com"
            )
            
            research_output = ResearchOutput(
                customer_name=f"Customer {email_record.customer_id}",
                customer_id=email_record.customer_id,
                sample_email_subject="Test Email Subject",
                contact_list=[mock_contact]
            )
            
        else:
            # Try to parse as JSON
            research_data = json.loads(research_content)
            research_output = ResearchOutput.from_dict(research_data)
        
        print(f"✅ Research output loaded:")
        print(f"   📧 Customer: {research_output.customer_name}")
        print(f"   📧 Subject: {research_output.sample_email_subject}")
        print(f"   👥 Contacts: {len(research_output.contact_list)}")
        
        return research_output
        
    except Exception as e:
        print(f"❌ Error loading research output: {e}")
        return None

async def get_email_content(blob_service, email_record):
    """Get email HTML content from blob storage."""
    try:
        # First try to get HTML file path from the record
        html_file = getattr(email_record, 'html_file_path', None)
        
        if html_file:
            print(f"📄 Loading HTML email content from: {html_file}")
            html_content = blob_service.download_blob_content(html_file)
            if html_content:
                print(f"✅ HTML email content loaded ({len(html_content)} characters)")
                return html_content
            else:
                print("❌ Failed to load HTML file, falling back to output_file")
        
        # Fallback to output_file if no html_file_path or if it failed
        if not email_record.output_file:
            print("⚠️  No output file specified in email record")
            # Create basic HTML for testing
            html_content = """
            <html>
            <body>
            <h2>Test Email</h2>
            <p>This is a test email generated for the test_single_record script.</p>
            <p>Best regards,<br>Test System</p>
            </body>
            </html>
            """
            print("⚠️  Using mock HTML content for testing")
            return html_content
            
        print(f"📄 Loading email content from: {email_record.output_file}")
        content = blob_service.download_blob_content(email_record.output_file)
        
        if not content:
            print("❌ Failed to load email content")
            return None
        
        # Check if it's JSON (communication output) or HTML
        if email_record.output_file.endswith('.json'):
            print("⚠️  Output file is JSON format. Extracting HTML or creating basic HTML.")
            try:
                # Try to parse as JSON and extract HTML content
                json_data = json.loads(content)
                if 'html_content' in json_data:
                    html_content = json_data['html_content']
                elif 'email_body' in json_data:
                    html_content = json_data['email_body']
                else:
                    # Create basic HTML from JSON data
                    html_content = f"""
                    <html>
                    <body>
                    <h2>Email from Communication System</h2>
                    <p>Content from JSON: {str(json_data)[:500]}...</p>
                    <p>Best regards,<br>Communication Team</p>
                    </body>
                    </html>
                    """
            except json.JSONDecodeError:
                # If JSON parsing fails, use content as-is
                html_content = content
        else:
            # Assume it's already HTML
            html_content = content
            
        print(f"✅ Email content loaded ({len(html_content)} characters)")
        return html_content
        
    except Exception as e:
        print(f"❌ Error loading email content: {e}")
        # Return basic HTML for testing
        return """
        <html>
        <body>
        <h2>Test Email</h2>
        <p>Error occurred loading content, using fallback HTML.</p>
        </body>
        </html>
        """

async def send_email(email_client, test_mode_service, research_output, html_content, settings):
    """Send the email using Azure Communication Services."""
    try:
        # Get primary contact
        primary_contact = research_output.get_primary_contact()
        if not primary_contact or not primary_contact.email:
            print("❌ No valid email address found in research output")
            return False
            
        # Determine recipient email (test mode vs actual)
        if settings.test_mode.test_mode:
            recipient_email = settings.test_mode.test_email_override
            print(f"🧪 TEST MODE: Sending to {recipient_email} instead of {primary_contact.email}")
        else:
            recipient_email = primary_contact.email
            print(f"📧 Sending to actual recipient: {recipient_email}")
        
        # Create email content
        email_content = EmailContent(
            subject=research_output.sample_email_subject,
            body_html=html_content,
            recipient_email=recipient_email,
            customer_id=research_output.customer_id,
            customer_name=research_output.customer_name,
            contact_name=primary_contact.full_name or f"{primary_contact.first_name} {primary_contact.last_name}"
        )
        
        # Send email
        print("📧 Sending email...")
        result = await email_client.send_email(
            recipient_email=recipient_email,
            subject=research_output.sample_email_subject,
            body_html=html_content
        )
        
        if result.success:
            print(f"✅ Email sent successfully!")
            print(f"   📧 Message ID: {result.message_id}")
            print(f"   📧 ACS Message ID: {result.acs_message_id}")
            print(f"   📧 Recipient: {recipient_email}")
            print(f"   📧 Subject: {email_content.subject}")
            return True
        else:
            print(f"❌ Email send failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

async def test_single_record(customer_id: Optional[str] = None, batch_id: Optional[int] = None):
    """Test email processing with a single record from Databricks."""
    
    start_time = time.time()
    print("🧪 Testing SendEmail system with single record...")
    print("=" * 60)
    
    try:
        # Initialize settings
        step_start = time.time()
        settings = await get_settings()
        validate_settings(settings)
        print(f"⏱️  Settings initialization: {time.time() - step_start:.2f}s")
        
        # Show test mode status
        if settings.test_mode.test_mode:
            print(f"🔧 TEST MODE: ENABLED - emails will be sent to {settings.test_mode.test_email_override}")
        else:
            print("🔧 TEST MODE: DISABLED - emails will be sent to actual recipients")
        
        print()
        
        # Initialize clients
        step_start = time.time()
        async with AzureKeyVaultClient(settings.key_vault) as key_vault_client:
            # Initialize Databricks OAuth client
            oauth_client = DatabricksOAuthClient(
                databricks_settings=settings.databricks_oauth,
                key_vault_client=key_vault_client
            )
            await oauth_client._initialize_client()
            
            # Initialize other services
            email_client = AzureEmailClient(settings.azure_communication)
            blob_service = BlobStorageService(settings.azure_storage)
            test_mode_service = TestModeService(settings)
            
            print(f"⏱️  Service initialization: {time.time() - step_start:.2f}s")
            
            # Get email record from database
            step_start = time.time()
            email_record = await get_email_record_from_db(oauth_client, settings, customer_id, batch_id)
            if not email_record:
                return False
            print(f"⏱️  Database query: {time.time() - step_start:.2f}s")
            
            # Get research output
            step_start = time.time()
            research_output = await get_research_output(blob_service, email_record)
            if not research_output:
                return False
            print(f"⏱️  Research output loading: {time.time() - step_start:.2f}s")
            
            # Get email content
            step_start = time.time()
            html_content = await get_email_content(blob_service, email_record)
            if not html_content:
                return False
            print(f"⏱️  Email content loading: {time.time() - step_start:.2f}s")
            
            # Send email
            step_start = time.time()
            success = await send_email(email_client, test_mode_service, research_output, html_content, settings)
            print(f"⏱️  Email sending: {time.time() - step_start:.2f}s")
            
            total_time = time.time() - start_time
            print(f"\n⏱️  Total execution time: {total_time:.2f}s")
            
            return success
        
    except Exception as e:
        print(f"❌ Error testing single record: {e}")
        return False

def main():
    """Main entry point for single record testing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test SendEmail system with a single record from Databricks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_single_record_working.py                          # Test with any pending record
  python test_single_record_working.py --customer CUST123      # Test with specific customer
  python test_single_record_working.py --customer CUST123 --batch 456  # Test with specific customer and batch
        """
    )
    
    parser.add_argument('--customer', '-c', 
                       help='Customer ID to test with')
    parser.add_argument('--batch', '-b', 
                       type=int,
                       help='Batch ID to test with')
    
    args = parser.parse_args()
    
    # Run the test
    success = asyncio.run(test_single_record(args.customer, args.batch))
    
    if success:
        print("\n🎉 Single record test completed successfully!")
    else:
        print("\n❌ Single record test failed!")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()