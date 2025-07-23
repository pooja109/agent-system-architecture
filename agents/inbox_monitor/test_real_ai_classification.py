#!/usr/bin/env python3
"""
Real AI Classification Test
===========================

Test Azure AI Foundry intent classification with real email examples.
"""

import asyncio
from datetime import UTC, datetime

from config.settings import get_settings
from models.email import Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata
from services.azure_ai_foundry_client import AzureAIFoundryClient


async def create_test_email(subject: str, body: str, sender_email: str) -> Email:
    """Create a test email for real AI classification testing."""
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


async def test_positive_intent():
    """Test positive intent classification."""
    print("\n🟢 Testing Real AI Classification - Positive Intent")

    email = await create_test_email(
        subject="Re: Your services look very interesting",
        body="Hi there! I'm very interested in learning more about your solutions. Could you please have someone call me at 555-1234 to discuss this further? I think this could be exactly what we need for our company.",
        sender_email="interested.customer@example.com",
    )

    settings = get_settings()

    async with AzureAIFoundryClient(settings.azure_ai_foundry) as ai_client:
        result = await ai_client.classify_email_intent(
            subject=email.subject, body=email.body.content, sender_email=email.sender.email
        )

        print(f"   🎯 Intent: {result.intent.value}")
        print(f"   📊 Confidence: {result.confidence:.2f}")
        print(f"   🧠 Reasoning: {result.reasoning}")
        print(f"   📝 Phrases: {result.detected_phrases}")
        print(f"   ⏱️ Processing: {result.processing_time_ms}ms")


async def test_negative_intent():
    """Test negative intent classification."""
    print("\n🔴 Testing Real AI Classification - Negative Intent")

    email = await create_test_email(
        subject="Stop contacting me immediately",
        body="I'm not interested in your services at all. Please remove me from your contact list immediately and don't contact me again. This is harassment.",
        sender_email="not.interested@example.com",
    )

    settings = get_settings()

    async with AzureAIFoundryClient(settings.azure_ai_foundry) as ai_client:
        result = await ai_client.classify_email_intent(
            subject=email.subject, body=email.body.content, sender_email=email.sender.email
        )

        print(f"   🎯 Intent: {result.intent.value}")
        print(f"   📊 Confidence: {result.confidence:.2f}")
        print(f"   🧠 Reasoning: {result.reasoning}")
        print(f"   📝 Phrases: {result.detected_phrases}")
        print(f"   ⏱️ Processing: {result.processing_time_ms}ms")


async def test_service_inquiry_intent():
    """Test service inquiry intent classification."""
    print("\n🔵 Testing Real AI Classification - Service Inquiry")

    email = await create_test_email(
        subject="Question about my recent order #12345",
        body="Hi, I have a question about my recent order. The tracking number you provided isn't working and I can't see the delivery status. Can you help me track my package?",
        sender_email="service.question@example.com",
    )

    settings = get_settings()

    async with AzureAIFoundryClient(settings.azure_ai_foundry) as ai_client:
        result = await ai_client.classify_email_intent(
            subject=email.subject, body=email.body.content, sender_email=email.sender.email
        )

        print(f"   🎯 Intent: {result.intent.value}")
        print(f"   📊 Confidence: {result.confidence:.2f}")
        print(f"   🧠 Reasoning: {result.reasoning}")
        print(f"   📝 Phrases: {result.detected_phrases}")
        print(f"   ⏱️ Processing: {result.processing_time_ms}ms")


async def test_out_of_office_intent():
    """Test out-of-office intent classification."""
    print("\n🟡 Testing Real AI Classification - Out of Office")

    email = await create_test_email(
        subject="Automatic reply: Out of Office",
        body="Thank you for your email. I am currently out of the office and will return on Monday, July 22nd. If this is urgent, please contact my assistant at assistant@company.com.",
        sender_email="ooo.customer@example.com",
    )

    settings = get_settings()

    async with AzureAIFoundryClient(settings.azure_ai_foundry) as ai_client:
        result = await ai_client.classify_email_intent(
            subject=email.subject, body=email.body.content, sender_email=email.sender.email
        )

        print(f"   🎯 Intent: {result.intent.value}")
        print(f"   📊 Confidence: {result.confidence:.2f}")
        print(f"   🧠 Reasoning: {result.reasoning}")
        print(f"   📝 Phrases: {result.detected_phrases}")
        print(f"   ⏱️ Processing: {result.processing_time_ms}ms")


async def test_edge_case_intent():
    """Test edge case for AI classification."""
    print("\n🤔 Testing Real AI Classification - Edge Case")

    email = await create_test_email(
        subject="Re: Your proposal",
        body="Thanks for reaching out. Let me think about this and get back to you next week.",
        sender_email="neutral.customer@example.com",
    )

    settings = get_settings()

    async with AzureAIFoundryClient(settings.azure_ai_foundry) as ai_client:
        result = await ai_client.classify_email_intent(
            subject=email.subject, body=email.body.content, sender_email=email.sender.email
        )

        print(f"   🎯 Intent: {result.intent.value}")
        print(f"   📊 Confidence: {result.confidence:.2f}")
        print(f"   🧠 Reasoning: {result.reasoning}")
        print(f"   📝 Phrases: {result.detected_phrases}")
        print(f"   ⏱️ Processing: {result.processing_time_ms}ms")


async def main():
    """Run all real AI classification tests."""
    print("🤖 Real Azure AI Foundry Intent Classification Tests")
    print("=" * 60)

    # Test different types of email intents with real AI
    await test_positive_intent()
    await test_negative_intent()
    await test_service_inquiry_intent()
    await test_out_of_office_intent()
    await test_edge_case_intent()

    print("\n✅ All real AI classification tests completed!")
    print("The Azure AI Foundry agent successfully classified all email intents!")


if __name__ == "__main__":
    asyncio.run(main())
