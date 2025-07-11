#!/usr/bin/env python3
"""
SendEmail Main Application
==========================

Main entry point for the SendEmail application.
Provides command-line interface for email processing operations.

Usage:
    python main.py run                          # Run continuous email processor
    python main.py process                      # Process emails once and exit
    python main.py test <email>                 # Send test email
    python main.py setup                        # Setup database tables
    python main.py status                       # Show system status
    python main.py stats [days]                 # Show processing statistics
    python main.py --help                       # Show help
"""

import asyncio
import argparse
import logging
import sys
import os
from typing import Optional

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.email_service import EmailService
from database.databricks_client import DatabricksClient
from simple_processor import SimpleEmailProcessor

def setup_logging(level: str = "INFO", format_type: str = "json"):
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
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, level.upper())
        )
    else:
        # Standard logging format
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            stream=sys.stdout
        )

async def run_continuous():
    """Run the email processor continuously."""
    print("🚀 For continuous processing, use: python run_email_processor.py")
    print("⚠️  The continuous mode with full scheduling requires the email_processor module")
    print("💡 For now, you can run: python main.py process (to process once)")
    return True

async def process_once():
    """Process emails once and exit."""
    processor = SimpleEmailProcessor()
    
    try:
        print("🔄 Processing emails once...")
        
        if not await processor.initialize():
            print("❌ Failed to initialize email processor")
            return False
        
        results = await processor.process_emails_once()
        
        if results.get('success', False):
            processed = results.get('processed', 0)
            sent = results.get('sent', 0)
            failed = results.get('failed', 0)
            
            print(f"✅ Processing completed:")
            print(f"   📊 Processed: {processed} records")
            print(f"   📧 Sent: {sent} emails")
            print(f"   ❌ Failed: {failed} emails")
            
            if failed > 0 and 'details' in results:
                print("\n❌ Failed emails:")
                for detail in results['details']:
                    if not detail.get('success', True):
                        print(f"   - Batch {detail.get('batch_id')}, Customer {detail.get('customer_id')}: {detail.get('error')}")
        else:
            print(f"❌ Processing failed: {results.get('error', 'Unknown error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing emails: {e}")
        return False
    finally:
        await processor.cleanup()

async def send_test_email(email: str):
    """Send a test email."""
    processor = SimpleEmailProcessor()
    
    try:
        print(f"📧 Sending test email to: {email}")
        
        results = await processor.test_system(email)
        
        if results.get('success', False):
            print(f"✅ Test email sent successfully!")
            if 'message_id' in results:
                print(f"   📨 Message ID: {results['message_id']}")
        else:
            print(f"❌ Test email failed: {results.get('error', 'Unknown error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        return False
    finally:
        await processor.cleanup()

async def setup_database():
    """Set up database tables."""
    try:
        print("🔧 Setting up database tables...")
        
        settings = get_settings()
        validate_settings(settings)
        
        with DatabricksClient(settings.databricks) as client:
            if client.create_tables():
                print("✅ Database tables created successfully!")
                return True
            else:
                print("❌ Failed to create database tables")
                return False
                
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

async def show_status():
    """Show system status."""
    try:
        print("📊 System Status")
        print("=" * 50)
        
        settings = get_settings()
        
        # Validate settings
        try:
            validate_settings(settings)
            print("✅ Configuration: Valid")
        except Exception as e:
            print(f"❌ Configuration: Invalid - {e}")
            return False
        
        # Test connections
        print("\n🔗 Connection Tests:")
        
        # Test Databricks
        try:
            with DatabricksClient(settings.databricks) as db_client:
                if db_client.test_connection():
                    print("✅ Databricks: Connected")
                else:
                    print("❌ Databricks: Connection failed")
        except Exception as e:
            print(f"❌ Databricks: {e}")
        
        # Test Email Service
        try:
            email_service = EmailService(settings)
            if await email_service.initialize():
                print("✅ Azure Communication Services: Connected")
                print("✅ Azure Blob Storage: Connected")
                email_service.cleanup()
            else:
                print("❌ Email services: Connection failed")
        except Exception as e:
            print(f"❌ Email services: {e}")
        
        # Show configuration
        print(f"\n⚙️  Configuration:")
        print(f"   Environment: {settings.environment}")
        print(f"   Processing interval: {settings.processing.interval_minutes} minutes")
        print(f"   Batch size: {settings.processing.batch_size}")
        print(f"   Max retry attempts: {settings.processing.max_retry_attempts}")
        print(f"   Databricks catalog: {settings.databricks.catalog}")
        print(f"   Databricks schema: {settings.databricks.schema}")
        print(f"   Blob container: {settings.azure_storage.container_name}")
        
        # Show test mode status
        print(f"\n🧪 Test Mode:")
        if settings.test_mode.test_mode:
            print(f"   Status: ENABLED")
            print(f"   Override email: {settings.test_mode.test_email_override}")
            print(f"   ⚠️  All emails will be redirected to the override address")
        else:
            print(f"   Status: DISABLED")
            print(f"   Emails will be sent to actual recipients")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return False

async def show_stats(days: int = 7):
    """Show processing statistics."""
    try:
        print(f"📈 Email Processing Statistics (Last {days} days)")
        print("=" * 50)
        
        settings = get_settings()
        email_service = EmailService(settings)
        
        if not await email_service.initialize():
            print("❌ Failed to initialize email service")
            return False
        
        stats = email_service.get_processing_stats(days)
        
        if 'error' in stats:
            print(f"❌ Error getting stats: {stats['error']}")
            return False
        
        print(f"📊 Summary:")
        print(f"   Total processed: {stats.get('total_processed', 0)}")
        print(f"   Successfully sent: {stats.get('sent', 0)}")
        print(f"   Failed: {stats.get('failed', 0)}")
        print(f"   Success rate: {stats.get('success_rate', 0):.1f}%")
        
        if stats.get('details'):
            print(f"\n📋 Details:")
            for detail in stats['details']:
                status = detail.get('send_status', 'unknown')
                count = detail.get('count', 0)
                print(f"   {status}: {count}")
        
        email_service.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SendEmail - Enterprise Email Processing System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                    # Run continuous processor
  python main.py process                # Process emails once
  python main.py test user@example.com  # Send test email
  python main.py setup                  # Setup database
  python main.py status                 # Show system status
  python main.py stats 30               # Show 30-day statistics
        """
    )
    
    parser.add_argument('command', 
                       choices=['run', 'process', 'test', 'setup', 'status', 'stats'],
                       help='Command to execute')
    
    parser.add_argument('argument', 
                       nargs='?',
                       help='Additional argument (email for test, days for stats)')
    
    parser.add_argument('--log-level',
                       default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    parser.add_argument('--log-format',
                       default='standard',
                       choices=['standard', 'json'],
                       help='Logging format')
    
    args = parser.parse_args()
    
    # Set up logging
    try:
        settings = get_settings()
        log_level = args.log_level or settings.logging.level
        log_format = args.log_format or settings.logging.format
    except:
        log_level = args.log_level
        log_format = args.log_format
    
    setup_logging(log_level, log_format)
    
    # Route to appropriate function
    async def run_command():
        try:
            if args.command == 'run':
                return await run_continuous()
            
            elif args.command == 'process':
                return await process_once()
            
            elif args.command == 'test':
                if not args.argument:
                    print("❌ Test command requires an email address")
                    print("Usage: python main.py test user@example.com")
                    return False
                return await send_test_email(args.argument)
            
            elif args.command == 'setup':
                return await setup_database()
            
            elif args.command == 'status':
                return await show_status()
            
            elif args.command == 'stats':
                days = 7
                if args.argument:
                    try:
                        days = int(args.argument)
                    except ValueError:
                        print("❌ Days argument must be a number")
                        return False
                return await show_stats(days)
            
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