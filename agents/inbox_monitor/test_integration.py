#!/usr/bin/env python3
"""
Integration test for inbox monitor
==================================

This script provides a simple integration test to verify
the inbox monitor functionality without actual Graph API calls.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Local imports after path modification
from config.settings import (  # noqa: E402
    AppSettings,
    GraphAPISettings,
    LoggingSettings,
    OutputSettings,
    ProcessingSettings,
)
from models.email import (  # noqa: E402
    Email,
    EmailAddress,
    EmailBody,
    EmailImportance,
    EmailRecipients,
    ProcessingMetadata,
)


def create_test_email():
    """Create a test email for demonstration."""
    processing_metadata = ProcessingMetadata(
        inbox_monitor_version="1.0.0",
        processing_id="test-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        processing_timestamp=datetime.utcnow(),
    )

    email = Email(
        id="test-email-001",
        conversation_id="test-conversation-001",
        received_datetime=datetime.utcnow(),
        sent_datetime=datetime.utcnow(),
        sender=EmailAddress(email="sender@example.com", name="Test Sender"),
        recipients=EmailRecipients(
            to=[EmailAddress(email="recipient@example.com", name="Test Recipient")]
        ),
        subject="Test Email for Inbox Monitor",
        body=EmailBody(
            content_type="text/html",
            content="<html><body><h1>Test Email</h1><p>This is a test email for the inbox monitor.</p></body></html>",
        ),
        body_preview="This is a test email for the inbox monitor...",
        importance=EmailImportance.NORMAL,
        has_attachments=False,
        attachment_count=0,
        categories=["Test"],
        is_read=False,
        is_draft=False,
        internet_message_headers={
            "Message-ID": "<test@example.com>",
            "Subject": "Test Email for Inbox Monitor",
        },
        processing_metadata=processing_metadata,
    )

    return email


def test_email_model():
    """Test email model creation and serialization."""
    print("Testing Email Model...")

    email = create_test_email()

    # Test conversion to AI format
    ai_format = email.to_ai_format()

    print(f"✅ Email created with ID: {email.id}")
    print(f"✅ Processing ID: {email.processing_metadata.processing_id}")
    print(f"✅ Subject: {email.subject}")
    print(f"✅ Sender: {email.sender.email}")

    # Save to file
    output_dir = Path("./test_output")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"test_email_{email.processing_metadata.processing_id}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ai_format, f, indent=2, ensure_ascii=False)

    print(f"✅ Email saved to: {output_file}")

    return True


def test_settings():
    """Test settings configuration."""
    print("\nTesting Settings Configuration...")

    # Create test settings
    settings = AppSettings(
        graph_api=GraphAPISettings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            monitored_email="test@example.com",
        ),
        processing=ProcessingSettings(polling_interval_seconds=300, batch_size=10),
        logging=LoggingSettings(level="INFO", format="json"),
        output=OutputSettings(storage_type="file", output_directory="./test_output"),
        environment="test",
        dry_run=True,
    )

    print(f"✅ Settings created for environment: {settings.environment}")
    print(f"✅ Monitored email: {settings.graph_api.monitored_email}")
    print(f"✅ Polling interval: {settings.processing.polling_interval_seconds} seconds")
    print(f"✅ Batch size: {settings.processing.batch_size}")
    print(f"✅ Dry run mode: {settings.dry_run}")

    return True


async def test_folder_name_generation():
    """Test folder name generation."""
    print("\nTesting Folder Name Generation...")

    from services.email_processor import EmailProcessor

    # Mock settings and graph client
    settings = AppSettings(
        graph_api=GraphAPISettings(
            tenant_id="test",
            client_id="test",
            client_secret="test",
            monitored_email="test@example.com",
        ),
        processing=ProcessingSettings(),
        logging=LoggingSettings(),
        output=OutputSettings(),
        environment="test",
    )

    # Create processor (without graph client for this test)
    processor = EmailProcessor(settings, None)

    folder_name = processor._get_processed_folder_name()

    # Verify format
    import re

    pattern = r"Processed_\d{2}_\d{4}"

    if re.match(pattern, folder_name):
        print(f"✅ Generated folder name: {folder_name}")
        return True
    else:
        print(f"❌ Invalid folder name format: {folder_name}")
        return False


def main():
    """Run integration tests."""
    print("=" * 60)
    print("Inbox Monitor Integration Test")
    print("=" * 60)

    success = True

    # Test 1: Email Model
    if not test_email_model():
        success = False

    # Test 2: Settings
    if not test_settings():
        success = False

    # Test 3: Folder Name Generation
    if not asyncio.run(test_folder_name_generation()):
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✅ All integration tests passed!")
    else:
        print("❌ Some tests failed!")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
