#!/usr/bin/env python3
"""
Test Email Sending Debug
========================

Simple test to verify email sending is working correctly.
"""

import asyncio
import sys
import os
import json

# Add email agent path
email_dir = os.path.join(os.path.dirname(__file__), "../email")
sys.path.insert(0, email_dir)

from email_clients.azure_email_client import AzureEmailClient
from config.settings import get_settings

async def test_email_sending():
    """Test email sending directly."""
    try:
        print("🔧 Loading settings...")
        settings = get_settings()
        
        print(f"📧 Sender email: {settings.azure_communication.sender_email}")
        print(f"📧 Reply-to email: {settings.azure_communication.reply_to_email}")
        
        print("🔧 Initializing Azure email client...")
        azure_client = AzureEmailClient(settings.azure_communication)
        
        # Test email content
        test_email = "testuser1@mngenvmcap666597.onmicrosoft.com"  # Same as in integration test
        test_subject = "TEST: Email Debug from Inbox Monitor"
        test_body = """
        <html>
        <body>
            <h2>Email Debug Test</h2>
            <p>This is a test email sent directly from the inbox monitor debug script.</p>
            <p>If you receive this email, the email forwarding functionality is working correctly.</p>
            <p>Timestamp: """ + str(asyncio.get_event_loop().time()) + """</p>
        </body>
        </html>
        """
        
        print(f"📤 Sending test email to: {test_email}")
        
        result = await azure_client.send_email(
            recipient_email=test_email,
            subject=test_subject,
            body_html=test_body
        )
        
        print(f"📋 Send result:")
        print(f"   Success: {result.success}")
        print(f"   Message ID: {result.message_id}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
        
        if result.success:
            print("✅ Email sent successfully!")
            print("   Check your inbox (including spam/junk folders)")
        else:
            print("❌ Email sending failed!")
            
        return result.success
        
    except Exception as e:
        print(f"❌ Error during email test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_email_sending())
    sys.exit(0 if success else 1)