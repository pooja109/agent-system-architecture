#!/usr/bin/env python3
"""
Inbox Monitor Main Application
==============================

Main entry point for the inbox monitor service.
Provides command-line interface for monitoring operations.

Usage:
    python main.py run                          # Run continuous monitor
    python main.py check                        # Check inbox once and exit
    python main.py setup                        # Setup Databricks tables
    python main.py status                       # Show system status
    python main.py test                         # Test Graph API connection
    python main.py --help                       # Show help
"""

import argparse
import asyncio
import logging
import os
import sys

from config.settings import get_settings, validate_settings
from services.email_processor import EmailProcessor
from services.graph_api_client import GraphAPIClient
from services.monitor import InboxMonitor

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def setup_logging(level: str = "INFO", format_type: str = "json") -> None:
    """Set up logging configuration."""
    if format_type == "json":
        import structlog

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, level.upper()),
        )
    else:
        # Standard logging format
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )


async def run_continuous() -> bool:
    """Run the inbox monitor continuously."""
    settings = get_settings()
    validate_settings(settings)

    monitor = InboxMonitor(settings)

    try:
        print("🚀 Starting Inbox Monitor")
        print(f"📧 Monitoring: {settings.graph_api.monitored_email}")
        print(f"⏱️  Polling interval: {settings.processing.polling_interval_seconds} seconds")
        print(f"📁 Output: {settings.output.storage_type}")
        if settings.dry_run:
            print("🧪 DRY RUN MODE: Emails will not be moved")
        print("\nPress Ctrl+C to stop...")

        await monitor.start()

    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested...")
    except Exception as e:
        print(f"❌ Monitor failed: {e}")
        return False
    finally:
        print("🛑 Stopping monitor...")
        await monitor.stop()

    print("✅ Monitor stopped successfully")
    return True


async def check_once() -> bool:
    """Check inbox once and exit."""
    settings = get_settings()
    validate_settings(settings)

    print("🔄 Checking inbox once...")

    async with GraphAPIClient(settings.graph_api) as graph_client:
        processor = EmailProcessor(settings, graph_client)

        results = await processor.process_inbox()

        if results.get("success", False):
            print("✅ Inbox check completed:")
            print(f"   📊 Processed: {results.get('processed_count', 0)} emails")
            print(f"   ❌ Failed: {results.get('failed_count', 0)} emails")
            print(f"   ⏱️  Time: {results.get('processing_time_seconds', 0):.2f} seconds")

            if results.get("failed_count", 0) > 0:
                print("\n❌ Failed emails:")
                for error in results.get("errors", []):
                    print(f"   - {error}")
        else:
            print("❌ Inbox check failed:")
            for error in results.get("errors", []):
                print(f"   - {error}")
            return False

    return True


async def test_connection() -> bool:
    """Test Graph API connection."""
    settings = get_settings()
    validate_settings(settings)

    print("🔗 Testing Graph API connection...")

    try:
        async with GraphAPIClient(settings.graph_api) as graph_client:
            # Try to get user info
            user_info = await graph_client._make_request(
                "GET", f"/users/{settings.graph_api.monitored_email}"
            )

            print("✅ Connection successful!")
            print(f"   📧 Email: {user_info.get('mail', 'N/A')}")
            print(f"   👤 Display Name: {user_info.get('displayName', 'N/A')}")
            print(f"   🆔 ID: {user_info.get('id', 'N/A')}")

            # Try to access mailbox
            inbox_info = await graph_client._make_request(
                "GET", f"/users/{settings.graph_api.monitored_email}/mailFolders/Inbox"
            )

            print("\n📬 Inbox Access:")
            print(f"   📁 Folder: {inbox_info.get('displayName', 'N/A')}")
            print(f"   📊 Total items: {inbox_info.get('totalItemCount', 0)}")
            print(f"   📨 Unread items: {inbox_info.get('unreadItemCount', 0)}")

            return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


async def show_status() -> bool:
    """Show system status."""
    try:
        print("📊 Inbox Monitor Status")
        print("=" * 50)

        settings = get_settings()

        # Validate settings
        try:
            validate_settings(settings)
            print("✅ Configuration: Valid")
        except Exception as e:
            print(f"❌ Configuration: Invalid - {e}")
            return False

        # Show configuration
        print("\n⚙️  Configuration:")
        print(f"   Environment: {settings.environment}")
        print(f"   Monitored email: {settings.graph_api.monitored_email}")
        print(f"   Polling interval: {settings.processing.polling_interval_seconds} seconds")
        print(f"   Batch size: {settings.processing.batch_size}")
        print(f"   Max retry attempts: {settings.processing.max_retry_attempts}")
        print(f"   Output type: {settings.output.storage_type}")

        if settings.output.storage_type == "file":
            print(f"   Output directory: {settings.output.output_directory}")
        elif settings.output.storage_type == "api":
            print(f"   API endpoint: {settings.output.api_endpoint}")

        print("\n🧪 Modes:")
        print(f"   Dry run: {'ENABLED' if settings.dry_run else 'DISABLED'}")

        # Test connection
        print("\n🔗 Testing connections...")
        if await test_connection():
            print("✅ All connections healthy")
        else:
            print("❌ Connection issues detected")
            return False

        return True

    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return False


async def setup_databricks() -> bool:
    """Setup Databricks tables for round-robin assignment."""
    try:
        print("🔧 Setting up Databricks tables...")

        # Import the setup function
        from setup_databricks import main as setup_main

        # Run the setup
        await setup_main()

        print("✅ Databricks setup completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Databricks setup failed: {e}")
        return False



def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Inbox Monitor - Email Processing Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                    # Run continuous monitor
  python main.py check                  # Check inbox once
  python main.py setup                  # Setup Databricks tables
  python main.py test                   # Test Graph API connection
  python main.py status                 # Show system status
        """,
    )

    parser.add_argument(
        "command", choices=["run", "check", "setup", "test", "status"], help="Command to execute"
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    parser.add_argument(
        "--log-format",
        default="json",
        choices=["standard", "json"],
        help="Logging format",
    )

    args = parser.parse_args()

    # Set up logging
    try:
        settings = get_settings()
        log_level = args.log_level or settings.logging.level
        log_format = args.log_format or settings.logging.format
    except Exception:
        log_level = args.log_level
        log_format = args.log_format

    setup_logging(log_level, log_format)

    # Route to appropriate function
    async def run_command() -> bool:
        try:
            if args.command == "run":
                return await run_continuous()

            elif args.command == "check":
                return await check_once()

            elif args.command == "setup":
                return await setup_databricks()

            elif args.command == "test":
                return await test_connection()

            elif args.command == "status":
                return await show_status()

            else:
                parser.print_help()
                return False

        except KeyboardInterrupt:
            print("\n🛑 Operation cancelled by user")
            return True
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

    # Run the command
    try:
        success = asyncio.run(run_command())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Application terminated by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
