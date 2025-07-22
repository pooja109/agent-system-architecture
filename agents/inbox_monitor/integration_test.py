#!/usr/bin/env python3
"""
Integration Testing Script
==========================

Test the complete inbox monitor system with real connections.
"""

import asyncio

from config.settings import get_settings, validate_settings
from services.email_processor import EmailProcessor
from services.graph_api_client import GraphAPIClient


async def test_system_status():
    """Test overall system status and connections."""
    print("🔍 Testing System Status")
    print("=" * 30)

    try:
        # Load and validate settings
        settings = get_settings()
        validate_settings(settings)
        print("✅ Configuration: Valid")

        # Test Graph API connection
        async with GraphAPIClient(settings.graph_api) as graph_client:
            user_info = await graph_client._make_request(
                "GET", f"/users/{settings.graph_api.monitored_email}"
            )
            print(f"✅ Graph API: Connected as {user_info.get('displayName')}")

            # Test inbox access
            inbox_info = await graph_client._make_request(
                "GET", f"/users/{settings.graph_api.monitored_email}/mailFolders/Inbox"
            )
            print(f"✅ Inbox Access: {inbox_info.get('totalItemCount')} total items")

        return True

    except Exception as e:
        print(f"❌ System Status Error: {e}")
        return False


async def test_email_processing():
    """Test email processing functionality."""
    print("\n📧 Testing Email Processing")
    print("=" * 30)

    try:
        settings = get_settings()

        async with GraphAPIClient(settings.graph_api) as graph_client:
            processor = EmailProcessor(settings, graph_client)

            # Process inbox (dry run)
            settings.dry_run = True
            results = await processor.process_inbox()

            print("✅ Processing completed:")
            print(f"   📊 Processed: {results.get('processed_count', 0)} emails")
            print(f"   ❌ Failed: {results.get('failed_count', 0)} emails")
            print(f"   ⏱️  Time: {results.get('processing_time_seconds', 0):.2f} seconds")

            if results.get("failed_count", 0) > 0:
                print("⚠️  Failed emails:")
                for error in results.get("errors", []):
                    print(f"   - {error}")

            return results.get("success", False)

    except Exception as e:
        print(f"❌ Email Processing Error: {e}")
        return False


async def main():
    """Run integration tests."""
    print("🧪 Inbox Monitor Integration Tests")
    print("=" * 50)

    # Test system status
    status_ok = await test_system_status()

    if status_ok:
        # Test email processing
        processing_ok = await test_email_processing()

        if processing_ok:
            print("\n🎉 All integration tests passed!")
        else:
            print("\n❌ Email processing tests failed!")
    else:
        print("\n❌ System status tests failed!")


if __name__ == "__main__":
    asyncio.run(main())
