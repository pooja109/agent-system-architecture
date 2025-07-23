#!/usr/bin/env python3
"""
Manual Scenario Testing Script
===============================

Test each scenario by simulating different email types.
"""

import asyncio
from datetime import UTC, datetime

from config.settings import get_settings
from models.email import Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata
from services.scenario_processor import ScenarioProcessor


async def create_test_email(subject: str, body: str, sender_email: str) -> Email:
    """Create a test email for scenario testing."""
    return Email(
        id=f"test_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
        conversation_id="test_conversation",
        received_datetime=datetime.now(UTC),
        sender=EmailAddress(email=sender_email, name="Test Customer"),
        recipients=EmailRecipients(
            to=[EmailAddress(email="testuser1@mngenvmcap666597.onmicrosoft.com", name="Test User")]
        ),
        subject=subject,
        body=EmailBody(content_type="text/plain", content=body),
        body_preview=body[:255],
        processing_metadata=ProcessingMetadata(
            inbox_monitor_version="2.0.0", processing_id="test_processing_id"
        ),
    )


async def test_scenario_5_positive():
    """Test Scenario 5: Positive Response"""
    print("\n🟢 Testing Scenario 5: Positive Response")

    email = await create_test_email(
        subject="Re: Your services look interesting",
        body="Hi, I'm very interested in learning more about your solutions. Please have someone call me to discuss further.",
        sender_email="interested.customer@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        result = await processor.process_email_scenario(email)
        print(f"   ✅ Success: {result.success}")
        print(f"   🎯 Scenario: {result.scenario_type}")
        print(f"   👥 Expert: {result.expert_assigned}")
        print(f"   📋 Case: {result.case_created}")
        print(f"   🔧 Actions: {result.actions_taken}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def test_scenario_6_negative():
    """Test Scenario 6: Negative Response"""
    print("\n🔴 Testing Scenario 6: Negative Response")

    email = await create_test_email(
        subject="Stop contacting me",
        body="I'm not interested in your services. Please remove me from your contact list immediately.",
        sender_email="not.interested@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        result = await processor.process_email_scenario(email)
        print(f"   ✅ Success: {result.success}")
        print(f"   🎯 Scenario: {result.scenario_type}")
        print(f"   📧 Forwarded to: {result.emails_sent}")
        print(f"   🔧 Actions: {result.actions_taken}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def test_scenario_7_service_inquiry():
    """Test Scenario 7: Service Inquiry"""
    print("\n🔵 Testing Scenario 7: Service Inquiry")

    email = await create_test_email(
        subject="Question about my order",
        body="Hi, I have a question about my recent order. Where can I track the delivery status?",
        sender_email="service.question@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        result = await processor.process_email_scenario(email)
        print(f"   ✅ Success: {result.success}")
        print(f"   🎯 Scenario: {result.scenario_type}")
        print(f"   📧 Forwarded to: {result.emails_sent}")
        print(f"   🔧 Actions: {result.actions_taken}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def test_scenario_8_out_of_office():
    """Test Scenario 8: Out of Office"""
    print("\n🟡 Testing Scenario 8: Out of Office")

    email = await create_test_email(
        subject="Automatic reply: Out of Office",
        body="Thank you for your email. I am currently out of the office and will return on Monday. I will respond to your message when I return.",
        sender_email="ooo.customer@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        result = await processor.process_email_scenario(email)
        print(f"   ✅ Success: {result.success}")
        print(f"   🎯 Scenario: {result.scenario_type}")
        print(f"   📊 Status updated: {result.metadata.get('status_updated', 'N/A')}")
        print(f"   🔧 Actions: {result.actions_taken}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def test_scenario_9_email_invalid():
    """Test Scenario 9: Email Invalid"""
    print("\n🟠 Testing Scenario 9: Email Invalid")

    email = await create_test_email(
        subject="Delivery Status Notification (Failure)",
        body="Your message could not be delivered. The email address may be invalid or the mailbox may be full.",
        sender_email="mailer-daemon@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        result = await processor.process_email_scenario(email)
        print(f"   ✅ Success: {result.success}")
        print(f"   🎯 Scenario: {result.scenario_type}")
        print(f"   🔧 Actions: {result.actions_taken}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def test_scenario_10_no_longer_works():
    """Test Scenario 10: No Longer Works"""
    print("\n🟣 Testing Scenario 10: No Longer Works")

    email = await create_test_email(
        subject="Re: Your recent outreach",
        body="Hi, John no longer works at this company. He left last month to pursue other opportunities.",
        sender_email="hr@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        result = await processor.process_email_scenario(email)
        print(f"   ✅ Success: {result.success}")
        print(f"   🎯 Scenario: {result.scenario_type}")
        print(f"   📧 Forwarded to: {result.emails_sent}")
        print(f"   🔧 Actions: {result.actions_taken}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def main():
    """Run all scenario tests."""
    print("🧪 Running Inbox Monitor Scenario Tests")
    print("=" * 50)

    # Test each scenario
    await test_scenario_5_positive()
    await test_scenario_6_negative()
    await test_scenario_7_service_inquiry()
    await test_scenario_8_out_of_office()
    await test_scenario_9_email_invalid()
    await test_scenario_10_no_longer_works()

    print("\n✅ All scenario tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
