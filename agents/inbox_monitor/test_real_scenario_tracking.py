#!/usr/bin/env python3
"""
Test real scenario tracking with database insertion
"""

import asyncio
import uuid
from datetime import datetime, timezone

from models.email import Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata
from services.scenario_processor import ScenarioProcessor
from config.settings import AppSettings

async def test_real_scenario_tracking():
    """Test the actual scenario processor with real database tracking."""
    print('🔄 Testing REAL scenario processor with database tracking...')
    
    # Create a properly structured test email that will trigger scenario 7 (service inquiry)
    test_email = Email(
        id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        subject='Question about my recent order #12345',
        sender=EmailAddress(
            email='customer@example.com', 
            name='Test Customer'
        ),
        body=EmailBody(
            content_type='text/plain',
            content='Hi, I have a question about my recent order. The tracking number you provided isn\'t working and I can\'t find any updates.'
        ),
        email_body='Hi, I have a question about my recent order...',
        recipients=EmailRecipients(
            to=[EmailAddress(email='inbox@company.com', name='Support')], 
            cc=[], 
            bcc=[]
        ),
        received_datetime=datetime.now(timezone.utc),
        sent_datetime=datetime.now(timezone.utc),
        has_attachments=False,
        attachment_count=0,
        processing_metadata=ProcessingMetadata(
            monitor_version='1.0.0',
            process_id=f'test_{str(uuid.uuid4())[:8]}'
        )
    )
    
    print(f'📧 Created test email: {test_email.id}')
    print(f'📝 Subject: {test_email.subject}')
    print(f'👤 Sender: {test_email.sender.email}')
    
    # Process using real scenario processor
    try:
        settings = AppSettings()
        async with ScenarioProcessor(settings) as processor:
            print('✅ Real scenario processor initialized')
            
            print('🚀 Processing email scenario...')
            result = await processor.process_email_scenario(test_email)
            
            print(f'✅ Scenario processing completed: {result.success}')
            print(f'🎯 Scenario type: {result.scenario_type}')
            print(f'📋 Actions taken: {result.agent_actions_log}')
            print(f'🧑‍💼 Expert assigned: {result.expert_assigned}')
            print(f'📞 Case created: {result.case_created}')
            print(f'📧 Emails sent: {result.emails_sent}')
            
            # Check if there were any errors
            if result.error_message:
                print(f'⚠️  Error message: {result.error_message}')
            
            print('\n🔍 DATABASE TRACKING STATUS:')
            print('   Look for messages above containing:')
            print('   - "Scenario metadata tracking completed successfully"')
            print('   - "Single record inserted successfully"')
            print('   - Any SQL errors or tracking failures')
            
    except Exception as e:
        print(f'❌ Scenario processing failed: {e}')
        import traceback
        traceback.print_exc()
        
    print('\n✅ Test completed. Check logs above for tracking success/failure.')

if __name__ == "__main__":
    asyncio.run(test_real_scenario_tracking())