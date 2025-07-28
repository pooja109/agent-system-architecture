#!/usr/bin/env python3
"""
Test Single Record
==================

Test the SendEmail system with a single record from the Databricks table.
"""

import asyncio
import sys
import os
import time
from typing import Optional

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from database.databricks_client import DatabricksClient
from services.email_service import EmailService
from simple_processor import SimpleEmailProcessor

async def test_single_record(customer_id: Optional[str] = None, batch_id: Optional[int] = None):
    """Test email processing with a single record from Databricks."""
    
    start_time = time.time()
    print("🧪 Testing SendEmail system with single record...")
    print("=" * 60)
    
    try:
        # Initialize settings
        step_start = time.time()
        settings = get_settings()
        validate_settings(settings)
        print(f"⏱️  Settings initialization: {time.time() - step_start:.2f}s")
        
        # Show test mode status
        if settings.test_mode.test_mode:
            print(f"🔧 TEST MODE: ENABLED - emails will be sent to {settings.test_mode.test_email_override}")
        else:
            print("🔧 TEST MODE: DISABLED - emails will be sent to actual recipients")
        
        print()
        
        # Initialize database client
        step_start = time.time()
        db_client = DatabricksClient(settings.databricks)
        
        if not db_client.connect():
            print("❌ Failed to connect to Databricks")
            return False
        print(f"⏱️  Database connection: {time.time() - step_start:.2f}s")
        
        # Get a single record for testing
        if customer_id and batch_id:
            # Get specific record using custom query
            query = f"""
            SELECT * FROM {settings.databricks.catalog}.{settings.databricks.schema}.email_communication_pipeline{settings.databricks.table_suffix}
            WHERE customer_id = '{customer_id}' AND batch_id = {batch_id}
            ORDER BY created_at DESC
            LIMIT 1
            """
            
            print(f"📊 Querying database for specific record...")
            query_start = time.time()
            result = db_client.execute_query(query)
            print(f"⏱️  Database query: {time.time() - query_start:.2f}s")
            
            if not result or len(result) == 0:
                print("❌ No records found matching criteria")
                print(f"   Customer ID: {customer_id}")
                print(f"   Batch ID: {batch_id}")
                return False
            
            record_data = result[0]
            print(f"✅ Found specific record:")
            print(f"   📧 Customer ID: {record_data.get('customer_id', 'Unknown')}")
            print(f"   📦 Batch ID: {record_data.get('batch_id', 'Unknown')}")
            print(f"   📅 Run Date: {record_data.get('run_date', 'Unknown')}")
            print(f"   📋 Status: {record_data.get('send_status', 'Unknown')}")
            print(f"   📄 Input File: {record_data.get('input_file', 'Not set')}")
            print(f"   📄 Output File: {record_data.get('output_file', 'Not set')}")
            print()
            
            # Create EmailRecord from database result (for specific record lookup)
            from database.models import EmailRecord
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
            
        elif customer_id:
            # Get latest record for specific customer using custom query
            query = f"""
            SELECT * FROM {settings.databricks.catalog}.{settings.databricks.schema}.email_communication_pipeline{settings.databricks.table_suffix}
            WHERE customer_id = '{customer_id}'
            ORDER BY created_at DESC
            LIMIT 1
            """
            
            print(f"📊 Querying database for customer record...")
            query_start = time.time()
            result = db_client.execute_query(query)
            print(f"⏱️  Database query: {time.time() - query_start:.2f}s")
            
            if not result or len(result) == 0:
                print("❌ No records found matching criteria")
                print(f"   Customer ID: {customer_id}")
                return False
            
            record_data = result[0]
            print(f"✅ Found customer record:")
            print(f"   📧 Customer ID: {record_data.get('customer_id', 'Unknown')}")
            print(f"   📦 Batch ID: {record_data.get('batch_id', 'Unknown')}")
            print(f"   📅 Run Date: {record_data.get('run_date', 'Unknown')}")
            print(f"   📋 Status: {record_data.get('send_status', 'Unknown')}")
            print(f"   📄 Input File: {record_data.get('input_file', 'Not set')}")
            print(f"   📄 Output File: {record_data.get('output_file', 'Not set')}")
            print()
            
            # Create EmailRecord from database result (for customer lookup)
            from database.models import EmailRecord
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
            
        else:
            # Get any pending record using the existing get_pending_emails method
            print(f"📊 Getting pending email records...")
            query_start = time.time()
            pending_records = db_client.get_pending_emails(limit=1)
            print(f"⏱️  Database query: {time.time() - query_start:.2f}s")
            
            if not pending_records:
                print("❌ No pending email records found")
                print("   No records match the email processing criteria:")
                print("   - agent_name = 'communication'")
                print("   - status = 'S'")
                print("   - is_email_sent IS NULL OR is_email_sent = false")
                return False
            
            email_record = pending_records[0]
            print(f"✅ Found pending record:")
            print(f"   📧 Customer ID: {email_record.customer_id}")
            print(f"   📦 Batch ID: {email_record.batch_id}")
            print(f"   📅 Run Date: {email_record.run_date}")
            print(f"   📋 Agent: {email_record.agent_name}")
            print(f"   📋 Status: {email_record.status}")
            print(f"   📋 Email Sent: {email_record.is_email_sent}")
            print(f"   📄 Input File: {email_record.input_file or 'Not set'}")
            print(f"   📄 Output File: {email_record.output_file or 'Not set'}")
            print()
        
        # Initialize email service
        step_start = time.time()
        email_service = EmailService(settings)
        
        if not await email_service.initialize():
            print("❌ Failed to initialize email service")
            return False
        print(f"⏱️  Email service initialization: {time.time() - step_start:.2f}s")
        
        print("📧 Processing single email record...")
        print("-" * 40)
        
        # Process the single record
        processing_start = time.time()
        result = await email_service._process_single_email(email_record)
        processing_time = time.time() - processing_start
        print(f"⏱️  Email processing: {processing_time:.2f}s")
        
        print("📊 Processing Results:")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Customer ID: {result.get('customer_id', 'Unknown')}")
        print(f"   Batch ID: {result.get('batch_id', 'Unknown')}")
        
        if result.get('success'):
            print(f"   ✅ Recipient: {result.get('recipient_email', 'Unknown')}")
            print(f"   ✅ Subject: {result.get('subject', 'Unknown')}")
            print(f"   ✅ Message ID: {result.get('message_id', 'Unknown')}")
            
            if settings.test_mode.test_mode:
                print(f"   🧪 TEST MODE: Email sent to {settings.test_mode.test_email_override}")
            else:
                print(f"   📧 Email sent to actual recipient")
        else:
            print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
            if 'attempted_email' in result:
                print(f"   ❌ Attempted email: {result['attempted_email']}")
        
        # Cleanup
        email_service.cleanup()
        db_client.disconnect()
        
        total_time = time.time() - start_time
        print(f"\n⏱️  Total execution time: {total_time:.2f}s")
        
        return result.get('success', False)
        
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
  python test_single_record.py                          # Test with any pending record
  python test_single_record.py --customer CUST123      # Test with specific customer
  python test_single_record.py --customer CUST123 --batch 456  # Test with specific customer and batch
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