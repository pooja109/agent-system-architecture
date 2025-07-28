#!/usr/bin/env python3
"""
Debug Subprocess Email Script
=============================

Test the exact subprocess script that gets generated to see why email override isn't working.
"""

import os
import sys

# Get email agent path
email_dir = os.path.join(os.path.dirname(__file__), "../email")
sys.path.insert(0, email_dir)

from email_clients.azure_email_client import AzureEmailClient
from services.test_mode_service import TestModeService
from config.settings import get_settings
from database.models import EmailContent
import asyncio
import json

async def debug_email_script():
    try:
        settings = get_settings()
        azure_client = AzureEmailClient(settings.azure_communication)
        test_mode_service = TestModeService(settings)
        
        print(f"Settings loaded: TEST_MODE={settings.test_mode.test_mode}")
        print(f"Override email: {settings.test_mode.test_email_override}")
        
        # Create email content object
        recipient_email = "testuser1@mngenvmcap666597.onmicrosoft.com"
        recipient_name = "Victoria Grant"
        escaped_subject = "FWD: Test Subject"
        escaped_body = "This is a test forward email body."
        
        email_content = EmailContent(
            subject=escaped_subject,
            body_html=escaped_body.replace("\\n", "<br>"),
            recipient_email=recipient_email,
            customer_id="INBOX_MONITOR",
            customer_name=recipient_name,
            contact_name=recipient_name
        )
        
        print(f"Original email content:")
        print(f"  Recipient: {email_content.recipient_email}")
        print(f"  Subject: {email_content.subject}")
        
        # Apply test mode override if enabled
        processed_content = test_mode_service.process_email_content(email_content)
        
        print(f"After test mode processing:")
        print(f"  Recipient: {processed_content.recipient_email}")
        print(f"  Subject: {processed_content.subject}")
        
        result = await azure_client.send_email(
            recipient_email=processed_content.recipient_email,
            subject=processed_content.subject,
            body_html=f"<html><body>{processed_content.body_html}</body></html>"
        )
        
        print(f"Send result: success={result.success}, message_id={result.message_id}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_email_script())