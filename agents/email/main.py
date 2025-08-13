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
import json
from typing import Optional
from aiohttp import web, ClientSession

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config.settings import get_settings, validate_settings
from services.email_service import EmailService
from services.databricks_connection_pool import initialize_connection_pool, shutdown_connection_pool
from database.databricks_client import DatabricksClient
from simple_processor import SimpleEmailProcessor
from services.health_check_service import HealthCheckService

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


# Health Check HTTP Endpoints
async def health_check_handler(request: web.Request) -> web.Response:
    """Simple health check endpoint for load balancers."""
    try:
        health_service = HealthCheckService()
        health_status = await health_service.get_simple_health_status()
        
        status_code = 200 if health_status["status"] == "HEALTHY" else 503
        
        return web.Response(
            text=json.dumps(health_status, indent=2),
            status=status_code,
            content_type="application/json"
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({
                "status": "UNHEALTHY",
                "error": str(e),
                "timestamp": "unknown"
            }, indent=2),
            status=503,
            content_type="application/json"
        )


async def health_detailed_handler(request: web.Request) -> web.Response:
    """Detailed health check endpoint with comprehensive system information."""
    try:
        health_service = HealthCheckService()
        health_status = await health_service.get_comprehensive_health_status()
        
        status_code = 200 if health_status["overall_status"] == "HEALTHY" else 503
        
        return web.Response(
            text=json.dumps(health_status, indent=2),
            status=status_code,
            content_type="application/json"
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({
                "overall_status": "UNHEALTHY",
                "error": str(e),
                "timestamp": "unknown",
                "components": []
            }, indent=2),
            status=503,
            content_type="application/json"
        )


async def readiness_handler(request: web.Request) -> web.Response:
    """Kubernetes readiness probe endpoint."""
    try:
        health_service = HealthCheckService()
        readiness_status = await health_service.get_readiness_status()
        
        status_code = 200 if readiness_status["ready"] else 503
        
        return web.Response(
            text=json.dumps(readiness_status, indent=2),
            status=status_code,
            content_type="application/json"
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({
                "ready": False,
                "status": "NOT_READY",
                "error": str(e),
                "timestamp": "unknown"
            }, indent=2),
            status=503,
            content_type="application/json"
        )


async def create_health_check_server(port: int = 8081) -> web.Application:
    """Create health check HTTP server."""
    app = web.Application()
    
    # Add health check routes
    app.router.add_get("/health", health_check_handler)
    app.router.add_get("/health/detailed", health_detailed_handler)
    app.router.add_get("/ready", readiness_handler)
    
    # Add root route for basic info
    async def root_handler(request: web.Request) -> web.Response:
        return web.Response(
            text=json.dumps({
                "service": "email",
                "status": "running",
                "oauth_migration": "enabled",
                "connection_pooling": "enabled",
                "endpoints": {
                    "health": "/health",
                    "detailed_health": "/health/detailed", 
                    "readiness": "/ready"
                }
            }, indent=2),
            content_type="application/json"
        )
    
    app.router.add_get("/", root_handler)
    
    return app


async def run_continuous():
    """Run the email processor continuously with health check server."""
    settings = await get_settings()
    validate_settings(settings)
    
    print("🚀 Starting Email Agent with OAuth Migration and Health Monitoring")
    print("⚠️  For full scheduling, consider using the email_processor module")
    
    try:
        # Initialize connection pool
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault
        )
        print("✅ Connection pool initialized")
        
        # Start health check server if enabled
        runner = None
        if settings.monitoring.health_check_enabled:
            health_port = int(os.getenv("HEALTH_CHECK_PORT", "8081"))
            health_app = await create_health_check_server(health_port)
            runner = web.AppRunner(health_app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", health_port)
            await site.start()
            print(f"🏥 Health check server started on port {health_port}")
            print(f"   Health endpoints: http://localhost:{health_port}/health")
            print(f"   Detailed health: http://localhost:{health_port}/health/detailed")
            print(f"   Readiness probe: http://localhost:{health_port}/ready")
        else:
            print("🚫 Health check endpoints disabled (HEALTH_CHECK_ENABLED=false)")
        
        print("✅ Email agent running with health monitoring")
        print("💡 Use 'python main.py process' to process emails once")
        print("🛑 Press Ctrl+C to stop...")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        
        # Cleanup
        if runner is not None:
            print("🏥 Shutting down health check server...")
            try:
                await runner.cleanup()
            except Exception as e:
                print(f"⚠️  Error stopping health check server: {e}")
        else:
            print("🏥 No health check server to shutdown")
        
        print("🔧 Shutting down connection pool...")
        await shutdown_connection_pool()
        print("✅ Email agent stopped successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Email agent failed: {e}")
        try:
            await shutdown_connection_pool()
        except:
            pass
        return False

async def process_once():
    """Process emails once and exit."""
    settings = await get_settings()
    validate_settings(settings)
    
    # Initialize connection pool for processing
    await initialize_connection_pool(
        settings.databricks_oauth,
        settings.key_vault,
        settings.connection_pool
    )
    
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
        await shutdown_connection_pool()

async def send_test_email(email: str):
    """Send a test email."""
    settings = await get_settings()
    validate_settings(settings)
    
    # Initialize connection pool for testing
    await initialize_connection_pool(
        settings.databricks_oauth,
        settings.key_vault,
        settings.connection_pool
    )
    
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
        await shutdown_connection_pool()

async def setup_database():
    """Set up database tables."""
    try:
        print("🔧 Setting up database tables...")
        
        settings = await get_settings()
        validate_settings(settings)
        
        # Initialize connection pool for database operations
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            settings.connection_pool
        )
        
        try:
            async with DatabricksClient() as client:
                if await client.create_tables():
                    print("✅ Database tables created successfully!")
                    return True
                else:
                    print("❌ Failed to create database tables")
                    return False
        finally:
            await shutdown_connection_pool()
                
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

async def show_status():
    """Show system status."""
    try:
        print("📊 System Status")
        print("=" * 50)
        
        settings = await get_settings()
        
        # Validate settings
        try:
            validate_settings(settings)
            print("✅ Configuration: Valid")
        except Exception as e:
            print(f"❌ Configuration: Invalid - {e}")
            return False
        
        # Test connections
        print("\n🔗 Connection Tests:")
        
        # Initialize connection pool for all tests
        try:
            await initialize_connection_pool(
                settings.databricks_oauth,
                settings.key_vault,
                settings.connection_pool
            )
            
            # Test Databricks connection pool
            try:
                async with DatabricksClient() as db_client:
                    if await db_client.test_connection():
                        print("✅ Databricks: Connected (using connection pool)")
                    else:
                        print("❌ Databricks: Connection failed")
            except Exception as e:
                print(f"❌ Databricks: {e}")
            
            # Test Email Service (while connection pool is still active)
            try:
                async with DatabricksClient() as db_client:
                    email_service = EmailService(db_client, settings)
                    if await email_service.initialize():
                        print("✅ Azure Communication Services: Connected")
                        print("✅ Azure Blob Storage: Connected")
                        email_service.cleanup()
                    else:
                        print("❌ Email services: Connection failed")
            except Exception as e:
                print(f"❌ Email services: {e}")
            
            # Shutdown connection pool after all tests
            await shutdown_connection_pool()
            
        except Exception as e:
            print(f"❌ Connection pool initialization failed: {e}")
            try:
                await shutdown_connection_pool()
            except:
                pass
        
        # Show configuration
        print(f"\n⚙️  Configuration:")
        print(f"   Environment: {settings.environment}")
        print(f"   Processing interval: {settings.processing.interval_minutes} minutes")
        print(f"   Batch size: {settings.processing.batch_size}")
        print(f"   Max retry attempts: {settings.processing.max_retry_attempts}")
        print(f"   Databricks catalog: {settings.databricks_oauth.catalog}")
        print(f"   Databricks schema: {settings.databricks_oauth.schema_name}")
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
        
        settings = await get_settings()
        validate_settings(settings)
        
        # Initialize connection pool for statistics
        await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            settings.connection_pool
        )
        
        try:
            async with DatabricksClient() as db_client:
                email_service = EmailService(db_client, settings)
                
                if not await email_service.initialize():
                    print("❌ Failed to initialize email service")
                    return False
                
                stats = await email_service.get_processing_stats(days)
                
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
        
        finally:
            await shutdown_connection_pool()
        
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
        # Try to get basic logging settings from environment variables
        # We can't await here since we're not in an async context yet
        log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")
        log_format = args.log_format or os.getenv("LOG_FORMAT", "json")
    except:
        log_level = args.log_level or "INFO"
        log_format = args.log_format or "json"
    
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