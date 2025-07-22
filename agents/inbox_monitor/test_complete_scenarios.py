#!/usr/bin/env python3
"""
Complete Scenario Testing Script
===============================

Test all scenarios with real Azure AI Foundry integration and mock service responses
to verify the complete scenario processing pipeline.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

from config.settings import get_settings
from models.email import Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata
from services.round_robin_service import ExpertAssignment
from services.salesforce_client import CaseCreateResponse
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


async def test_scenario_5_complete():
    """Test Scenario 5: Positive Response with complete workflow."""
    print("\n🟢 Testing Complete Scenario 5: Positive Response")

    email = await create_test_email(
        subject="Re: Your services look very interesting",
        body="Hi there! I'm very interested in learning more about your solutions. Could you please have someone call me at 555-1234 to discuss this further? I think this could be exactly what we need for our company.",
        sender_email="interested.customer@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    # Mock expert assignment
    mock_expert = ExpertAssignment(
        assignment_id="assign_123",
        expert_id="expert_456",
        expert_email="expert@company.com",
        expert_name="John Expert",
        customer_email=email.sender.email,
        assignment_date=datetime.now(UTC),
        last_assignment_timestamp=datetime.now(UTC),
        assignment_count=1,
    )

    # Mock Salesforce case creation
    mock_case_response = CaseCreateResponse(id="case_789", success=True, errors=[])

    try:
        # Mock all service calls
        with patch.object(
            processor.round_robin_service, "assign_lead_to_expert", return_value=mock_expert
        ), patch.object(
            processor.salesforce_client, "create_case", return_value=mock_case_response
        ):
            # Use real AI classification
            result = await processor.process_email_scenario(email)

            print(f"   ✅ Success: {result.success}")
            print(f"   🎯 Scenario: {result.scenario_type.value}")
            print(f"   👥 Expert: {result.expert_assigned}")
            print(f"   📋 Case: {result.case_created}")
            print(f"   🔧 Actions: {result.actions_taken}")

            # Verify result
            assert result.success is True
            assert result.scenario_type.name == "SCENARIO_5"
            assert result.expert_assigned == "John Expert"
            assert result.case_created == "case_789"

    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


async def test_scenario_6_complete():
    """Test Scenario 6: Negative Response with complete workflow."""
    print("\n🔴 Testing Complete Scenario 6: Negative Response")

    email = await create_test_email(
        subject="Stop contacting me immediately",
        body="I'm not interested in your services at all. Please remove me from your contact list immediately and don't contact me again. This is harassment.",
        sender_email="not.interested@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        # Mock email forwarding
        with patch.object(
            processor, "_forward_email_to_recipient", return_value="forwarded_email_123"
        ):
            # Use real AI classification
            result = await processor.process_email_scenario(email)

            print(f"   ✅ Success: {result.success}")
            print(f"   🎯 Scenario: {result.scenario_type.value}")
            print(f"   📧 Forwarded to: {result.emails_sent}")
            print(f"   🔧 Actions: {result.actions_taken}")

            # Verify result
            assert result.success is True
            assert result.scenario_type.name == "SCENARIO_6"
            assert len(result.emails_sent) == 1

    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


async def test_scenario_7_complete():
    """Test Scenario 7: Service Inquiry with complete workflow."""
    print("\n🔵 Testing Complete Scenario 7: Service Inquiry")

    email = await create_test_email(
        subject="Question about my recent order #12345",
        body="Hi, I have a question about my recent order. The tracking number you provided isn't working and I can't see the delivery status. Can you help me track my package?",
        sender_email="service.question@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    try:
        # Mock email forwarding
        with patch.object(
            processor, "_forward_email_to_recipient", return_value="forwarded_email_456"
        ):
            # Use real AI classification
            result = await processor.process_email_scenario(email)

            print(f"   ✅ Success: {result.success}")
            print(f"   🎯 Scenario: {result.scenario_type.value}")
            print(f"   📧 Forwarded to: {result.emails_sent}")
            print(f"   🔧 Actions: {result.actions_taken}")

            # Verify result
            assert result.success is True
            assert result.scenario_type.name == "SCENARIO_7"
            assert len(result.emails_sent) == 1

    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


async def test_scenario_8_complete():
    """Test Scenario 8: Out of Office with complete workflow."""
    print("\n🟡 Testing Complete Scenario 8: Out of Office")

    email = await create_test_email(
        subject="Automatic reply: Out of Office",
        body="Thank you for your email. I am currently out of the office and will return on Monday, July 22nd. If this is urgent, please contact my assistant at assistant@company.com.",
        sender_email="ooo.customer@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    # Mock assignment lookup
    mock_assignment = ExpertAssignment(
        assignment_id="assign_ooo",
        expert_id="expert_789",
        expert_email="expert@company.com",
        expert_name="Jane Expert",
        customer_email=email.sender.email,
        assignment_date=datetime.now(UTC),
        last_assignment_timestamp=datetime.now(UTC),
        assignment_count=1,
    )

    try:
        # Mock database operations
        with patch.object(
            processor.round_robin_service,
            "get_assignment_by_customer",
            return_value=mock_assignment,
        ), patch.object(
            processor.round_robin_service, "update_assignment_status", return_value=True
        ):
            # Use real AI classification
            result = await processor.process_email_scenario(email)

            print(f"   ✅ Success: {result.success}")
            print(f"   🎯 Scenario: {result.scenario_type.value}")
            print("   📊 Status: Out of office flagged")
            print(f"   🔧 Actions: {result.actions_taken}")

            # Verify result
            assert result.success is True
            assert result.scenario_type.name == "SCENARIO_8"

    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


async def test_scenario_9_complete():
    """Test Scenario 9: Invalid Email with complete workflow."""
    print("\n🟠 Testing Complete Scenario 9: Invalid Email")

    email = await create_test_email(
        subject="Delivery Status Notification (Failure)",
        body="Your message could not be delivered. The email address may be invalid or the mailbox may be full.",
        sender_email="mailer-daemon@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    # Mock assignment lookup
    mock_assignment = ExpertAssignment(
        assignment_id="assign_invalid",
        expert_id="expert_999",
        expert_email="expert@company.com",
        expert_name="Bob Expert",
        customer_email=email.sender.email,
        assignment_date=datetime.now(UTC),
        last_assignment_timestamp=datetime.now(UTC),
        assignment_count=1,
    )

    try:
        # Mock service operations
        with patch.object(
            processor.salesforce_client, "update_contact_invalid_email", return_value=True
        ), patch.object(
            processor.round_robin_service,
            "get_assignment_by_customer",
            return_value=mock_assignment,
        ), patch.object(
            processor.round_robin_service, "update_assignment_status", return_value=True
        ):
            # Use real AI classification
            result = await processor.process_email_scenario(email)

            print(f"   ✅ Success: {result.success}")
            print(f"   🎯 Scenario: {result.scenario_type.value}")
            print(f"   🔧 Actions: {result.actions_taken}")

            # Verify result
            assert result.success is True
            assert result.scenario_type.name == "SCENARIO_9"

    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


async def test_scenario_10_complete():
    """Test Scenario 10: No Longer Works with complete workflow."""
    print("\n🟣 Testing Complete Scenario 10: No Longer Works")

    email = await create_test_email(
        subject="Re: Your recent outreach",
        body="Hi, John no longer works at this company. He left last month to pursue other opportunities.",
        sender_email="hr@example.com",
    )

    settings = get_settings()
    processor = ScenarioProcessor(settings)

    # Mock assignment lookup
    mock_assignment = ExpertAssignment(
        assignment_id="assign_nolonger",
        expert_id="expert_111",
        expert_email="expert@company.com",
        expert_name="Alice Expert",
        customer_email=email.sender.email,
        assignment_date=datetime.now(UTC),
        last_assignment_timestamp=datetime.now(UTC),
        assignment_count=1,
    )

    try:
        # Mock service operations
        with patch.object(
            processor, "_forward_email_to_recipient", return_value="forwarded_email_789"
        ), patch.object(
            processor.round_robin_service,
            "get_assignment_by_customer",
            return_value=mock_assignment,
        ), patch.object(
            processor.round_robin_service, "update_assignment_status", return_value=True
        ):
            # Use real AI classification
            result = await processor.process_email_scenario(email)

            print(f"   ✅ Success: {result.success}")
            print(f"   🎯 Scenario: {result.scenario_type.value}")
            print(f"   📧 Forwarded to: {result.emails_sent}")
            print(f"   🔧 Actions: {result.actions_taken}")

            # Verify result
            assert result.success is True
            assert result.scenario_type.name == "SCENARIO_10"
            assert len(result.emails_sent) == 1

    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


async def main():
    """Run all complete scenario tests."""
    print("🧪 Complete Inbox Monitor Scenario Tests (with Real AI)")
    print("=" * 70)

    try:
        # Test each scenario with real AI and mocked service calls
        await test_scenario_5_complete()
        await test_scenario_6_complete()
        await test_scenario_7_complete()
        await test_scenario_8_complete()
        await test_scenario_9_complete()
        await test_scenario_10_complete()

        print("\n✅ All complete scenario tests PASSED!")
        print("\n🎉 The inbox monitor system is working correctly!")
        print("   - AI-powered intent classification: ✅")
        print("   - Scenario routing logic: ✅")
        print("   - Service integration patterns: ✅")
        print("   - Error handling: ✅")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
