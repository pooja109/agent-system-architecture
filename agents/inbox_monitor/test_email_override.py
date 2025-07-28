#!/usr/bin/env python3
"""
Test Email Override
===================

Test if the email override functionality is working correctly.
"""

import asyncio
import sys
import os
import json

# Add email agent path
email_dir = os.path.join(os.path.dirname(__file__), "../email")
sys.path.insert(0, email_dir)

from email_clients.azure_email_client import AzureEmailClient
from services.test_mode_service import TestModeService
from config.settings import get_settings
from database.models import EmailContent

async def test_email_override():
    """Test email override functionality."""
    try:
        print("🔧 Loading settings...")
        settings = get_settings()
        
        print(f"🧪 Test mode enabled: {settings.test_mode.test_mode}")
        print(f"📧 Test email override: {settings.test_mode.test_email_override}")
        
        azure_client = AzureEmailClient(settings.azure_communication)
        test_mode_service = TestModeService(settings)
        
        # Create test email content
        original_recipient = "testuser1@mngenvmcap666597.onmicrosoft.com"
        email_content = EmailContent(
            subject="Test Email Override from Inbox Monitor",
            body_html="This is a test email to verify email override functionality.<br>Original recipient: " + original_recipient,
            recipient_email=original_recipient,
            customer_id="TEST_OVERRIDE",
            customer_name="Test User",
            contact_name="Test User"
        )
        
        print(f"📤 Original recipient: {email_content.recipient_email}")
        
        # Apply test mode override
        processed_content = test_mode_service.process_email_content(email_content)
        
        print(f"📧 After override: {processed_content.recipient_email}")
        print(f"📋 Subject: {processed_content.subject}")
        
        # Send the email
        result = await azure_client.send_email(
            recipient_email=processed_content.recipient_email,
            subject=processed_content.subject,
            body_html=f"<html><body>{processed_content.body_html}</body></html>"
        )
        
        if result.success:
            print(f"✅ Email sent successfully to: {processed_content.recipient_email}")
            print(f"   Message ID: {result.message_id}")
        else:
            print(f"❌ Email sending failed: {result.error_message}")
            
        return result.success
        
    except Exception as e:
        print(f"❌ Error during email override test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_email_override())
    sys.exit(0 if success else 1)