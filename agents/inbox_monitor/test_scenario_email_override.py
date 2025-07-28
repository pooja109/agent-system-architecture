#!/usr/bin/env python3
"""
Test Scenario Email Override
============================

Test if the scenario processor correctly applies email override.
"""

import asyncio
import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from services.scenario_processor import ScenarioProcessor
from config.settings import get_settings
from models.email import Email, EmailAddress, EmailBody, ProcessingMetadata

async def test_scenario_email_override():
    """Test scenario 6 (negative response) with email override."""
    try:
        print("🔧 Loading settings...")
        settings = get_settings()
        
        print(f"🧪 Test mode enabled: {settings.test_mode.enabled}")
        if settings.test_mode.enabled:
            print(f"📧 Email override: {settings.test_mode.target_salesforce_email}")
        
        # Create a test email for scenario 6 (negative response)
        test_email = Email(
            id="test_scenario_override",
            conversation_id="test_conv",
            received_datetime="2025-07-25T20:00:00Z",
            sender=EmailAddress(email="test@example.com", name="Test User"),
            recipients={"to": [], "cc": [], "bcc": []},
            subject="Please remove me from your list",
            body=EmailBody(content_type="text/plain", content="I don't want to receive these emails anymore. Please remove me."),
            body_preview="I don't want to receive these emails...",
            processing_metadata=ProcessingMetadata(
                inbox_monitor_version="test",
                processing_id="test_override"
            )
        )
        
        print(f"📤 Processing scenario 6 (negative) for: {test_email.sender.email}")
        
        scenario_processor = ScenarioProcessor(settings)
        
        async with scenario_processor:
            # This should trigger scenario 6 and forward to Victoria Grant
            # The email should be redirected to jgroenlund@microsoft.com if override is working
            result = await scenario_processor._process_scenario_6(test_email, [])
            
            print(f"📋 Scenario result:")
            print(f"   Success: {result.success}")
            print(f"   Actions taken: {result.actions_taken}")
            print(f"   Emails sent: {result.emails_sent}")
            
            if result.success:
                print("✅ Scenario 6 completed successfully!")
                print("   Check jgroenlund@microsoft.com for the forwarded email")
            else:
                print(f"❌ Scenario 6 failed: {result.error_message}")
                
            return result.success
        
    except Exception as e:
        print(f"❌ Error during scenario test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_scenario_email_override())
    sys.exit(0 if success else 1)