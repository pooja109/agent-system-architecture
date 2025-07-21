#!/usr/bin/env python3
"""
Simple Scenario Testing
=======================

Test scenarios by directly calling scenario methods without external dependencies.
"""

import asyncio
from datetime import UTC, datetime

from config.settings import get_settings
from models.email import Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata
from services.scenario_processor import ScenarioProcessor, ScenarioResult, ScenarioType


async def test_configuration():
    """Test that configuration loads correctly."""
    print("🔧 Testing Configuration")
    print("=" * 30)

    try:
        settings = get_settings()
        print("✅ Settings loaded")
        print(f"   📧 Test email: {settings.scenarios.test_email}")
        print(f"   👤 Victoria Grant: {settings.scenarios.victoria_grant_email}")
        print(f"   👥 Account Team: {settings.scenarios.account_team_email}")
        print(f"   🤖 AI Foundry: {settings.azure_ai_foundry.endpoint}")
        print(f"   💼 Salesforce: {settings.salesforce.base_url}")
        print(f"   📊 Databricks: {settings.databricks.server_hostname}")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False


async def test_email_model():
    """Test email model creation."""
    print("\n📧 Testing Email Model")
    print("=" * 30)

    try:
        email = Email(
            id="test_email_123",
            conversation_id="test_conversation",
            received_datetime=datetime.now(UTC),
            sender=EmailAddress(email="customer@example.com", name="Test Customer"),
            recipients=EmailRecipients(
                to=[
                    EmailAddress(
                        email="testuser1@mngenvmcap666597.onmicrosoft.com", name="Test User"
                    )
                ]
            ),
            subject="Test Subject",
            body=EmailBody(content_type="text/plain", content="Test email body"),
            body_preview="Test email body...",
            processing_metadata=ProcessingMetadata(
                inbox_monitor_version="2.0.0", processing_id="test_processing_id"
            ),
        )

        print("✅ Email model created")
        print(f"   📨 ID: {email.id}")
        print(f"   👤 Sender: {email.sender.email}")
        print(f"   📄 Subject: {email.subject}")

        # Test AI format conversion
        ai_format = email.to_ai_format()
        print(f"   🤖 AI format keys: {list(ai_format.keys())}")

        return True
    except Exception as e:
        print(f"❌ Email model error: {e}")
        return False


async def test_scenario_processor_init():
    """Test scenario processor initialization."""
    print("\n⚙️ Testing Scenario Processor")
    print("=" * 30)

    try:
        settings = get_settings()
        processor = ScenarioProcessor(settings)

        print("✅ Scenario processor created")
        print(f"   🔧 Settings: {bool(processor.settings)}")
        print(f"   🤖 AI Client: {bool(processor.ai_client)}")
        print(f"   💼 SF Client: {bool(processor.salesforce_client)}")
        print(f"   📊 RR Service: {bool(processor.round_robin_service)}")

        return True
    except Exception as e:
        print(f"❌ Scenario processor error: {e}")
        return False


async def test_scenario_types():
    """Test scenario type enumeration."""
    print("\n📋 Testing Scenario Types")
    print("=" * 30)

    try:
        scenarios = [
            ScenarioType.SCENARIO_5,
            ScenarioType.SCENARIO_6,
            ScenarioType.SCENARIO_7,
            ScenarioType.SCENARIO_8,
            ScenarioType.SCENARIO_9,
            ScenarioType.SCENARIO_10,
            ScenarioType.SCENARIO_11,
            ScenarioType.UNKNOWN,
        ]

        print("✅ Scenario types available:")
        for scenario in scenarios:
            print(f"   🎯 {scenario.value}")

        return True
    except Exception as e:
        print(f"❌ Scenario types error: {e}")
        return False


async def test_scenario_result():
    """Test scenario result model."""
    print("\n📊 Testing Scenario Result")
    print("=" * 30)

    try:
        result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            actions_taken=["test_action_1", "test_action_2"],
            expert_assigned="expert@company.com",
            case_created="case_123",
            emails_sent=["recipient@example.com"],
        )

        print("✅ Scenario result created")
        print(f"   🎯 Type: {result.scenario_type}")
        print(f"   ✅ Success: {result.success}")
        print(f"   🔧 Actions: {result.actions_taken}")
        print(f"   👥 Expert: {result.expert_assigned}")
        print(f"   📋 Case: {result.case_created}")
        print(f"   📧 Emails: {result.emails_sent}")

        return True
    except Exception as e:
        print(f"❌ Scenario result error: {e}")
        return False


async def main():
    """Run all simple tests."""
    print("🧪 Simple Inbox Monitor Tests")
    print("=" * 50)

    results = []
    results.append(await test_configuration())
    results.append(await test_email_model())
    results.append(await test_scenario_processor_init())
    results.append(await test_scenario_types())
    results.append(await test_scenario_result())

    passed = sum(results)
    total = len(results)

    print(f"\n📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed!")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
