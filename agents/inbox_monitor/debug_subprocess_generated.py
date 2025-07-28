#!/usr/bin/env python3
"""
Debug Generated Subprocess Script
==================================

This simulates the exact script that gets generated and executed by the scenario processor.
"""

import sys
import os
email_dir = "/mnt/c/Repos/lowtouch_v6/aou-s01-lowtouch/agents/email"
sys.path.insert(0, email_dir)

# Ensure the subprocess can find the .env file in the root directory
from dotenv import load_dotenv
root_env_path = os.path.join(email_dir, "..", "..", ".env")
print(f"Loading .env from: {root_env_path}")
load_dotenv(root_env_path)

from email_clients.azure_email_client import AzureEmailClient
from services.test_mode_service import TestModeService
from config.settings import get_settings
from database.models import EmailContent
import asyncio
import json

async def send_email():
    try:
        settings = get_settings()
        azure_client = AzureEmailClient(settings.azure_communication)
        test_mode_service = TestModeService(settings)
        
        print(f"TEST_MODE in subprocess: {settings.test_mode.test_mode}")
        print(f"TEST_EMAIL_OVERRIDE in subprocess: {settings.test_mode.test_email_override}")
        
        # Create email content object (simulating scenario 6)
        recipient_email = "testuser1@mngenvmcap666597.onmicrosoft.com"
        recipient_name = "Victoria Grant"
        escaped_subject = "FWD: Please remove me from your list"
        escaped_body = "Customer wants to stop communication"
        
        email_content = EmailContent(
            subject=escaped_subject,
            body_html=escaped_body.replace("\\n", "<br>"),
            recipient_email=recipient_email,
            customer_id="INBOX_MONITOR",
            customer_name=recipient_name,
            contact_name=recipient_name
        )
        
        print(f"Before test mode override: {email_content.recipient_email}")
        
        # Apply test mode override if enabled
        processed_content = test_mode_service.process_email_content(email_content)
        
        print(f"After test mode override: {processed_content.recipient_email}")
        
        result = await azure_client.send_email(
            recipient_email=processed_content.recipient_email,
            subject=processed_content.subject,
            body_html=f"<html><body>{processed_content.body_html}</body></html>"
        )
        
        print(json.dumps({"success": result.success, "message_id": result.message_id or "", "error": result.error_message or ""}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(send_email())