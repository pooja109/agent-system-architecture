#!/usr/bin/env python3
"""
Check Email Status
==================

Check the status of sent emails using Azure Communication Services.
"""

import asyncio
import sys
import os

# Add email agent path
email_dir = os.path.join(os.path.dirname(__file__), "../email")
sys.path.insert(0, email_dir)

from email_clients.azure_email_client import AzureEmailClient
from config.settings import get_settings

async def check_email_status(message_id: str):
    """Check the status of a sent email."""
    try:
        print(f"🔍 Checking status for message ID: {message_id}")
        
        settings = get_settings()
        azure_client = AzureEmailClient(settings.azure_communication)
        
        status = await azure_client.get_send_status(message_id)
        
        if status:
            print(f"📋 Email status:")
            for key, value in status.items():
                print(f"   {key}: {value}")
        else:
            print("❓ No status information available")
            
    except Exception as e:
        print(f"❌ Error checking email status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test with the message ID from the previous test
    message_id = "c450aa95-bc6a-4df6-a4ab-9da8dd541323"
    asyncio.run(check_email_status(message_id))