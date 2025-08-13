#!/usr/bin/env python3
"""
Inbox Monitor Main Application
==============================

Main entry point for the inbox monitor service.
Provides command-line interface for monitoring operations with intelligent logging.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import json
import time
from aiohttp import web, ClientSession
from typing import Optional

# Import Phase 1, 2, 3 & 4 components
from cli.argument_parser import CLIArgumentParser
from cli.config_manager import ConfigurationManager
from cli.environment_detector import EnvironmentDetector
from utils.custom_logging import initialize_logging, LoggingConfig, cleanup_logging
from utils.custom_logging.http_client_config import HTTPClientLogSuppressor
from utils.custom_logging.service_integration import ServiceLoggingIntegration

# Import Phase 4 UI components
from ui import UIManager, ProgressType, OperationType

# Import existing components
from config.settings import get_settings, validate_settings
from services.email_processor import EmailProcessor
from services.graph_api_client import GraphAPIClient
from services.monitor import InboxMonitor
from services.databricks_connection_pool import (
    initialize_connection_pool, 
    shutdown_connection_pool,
    ConnectionPoolConfig
)
from services.health_check_service import HealthCheckService

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def setup_logging_system(cli_args: argparse.Namespace) -> tuple[LoggingConfig, ServiceLoggingIntegration, UIManager]:
    """Set up the complete logging system and UI based on CLI arguments and environment."""
    try:
        # Create configuration manager and load configuration
        config_manager = ConfigurationManager()
        
        # Convert CLI args to dictionary for configuration manager
        # Use getattr with defaults for attributes that may not exist when no command is specified
        cli_config = {
            'quiet': getattr(cli_args, 'quiet', False),
            'verbose': getattr(cli_args, 'verbose', False),
            'debug': getattr(cli_args, 'debug', False),
            'format': getattr(cli_args, 'format', 'clean'),
            'no_color': getattr(cli_args, 'no_color', False),
            'no_timestamps': getattr(cli_args, 'no_timestamps', False),
            'show_logger_names': getattr(cli_args, 'show_logger_names', False),
            'log_level': getattr(cli_args, 'log_level', None),
            'environment': getattr(cli_args, 'environment', None),
            'force_console_logging': getattr(cli_args, 'force_console_logging', False)
        }
        
        # Load complete configuration from all sources
        logging_config = config_manager.load_configuration(
            cli_args=cli_config,
            config_file_path=getattr(cli_args, 'config_file', None),
            environment_override=cli_config.get('environment')
        )
        
        # Initialize the logging system
        initialize_logging(logging_config)
        
        # Configure HTTP client logging suppression
        http_suppressor = HTTPClientLogSuppressor(logging_config)
        http_suppressor.configure_http_client_logging()
        
        # Create service integration utilities
        from utils.custom_logging.logger_factory import LoggerFactory
        logger_factory = LoggerFactory()
        service_integration = ServiceLoggingIntegration(logger_factory)
        
        # Create UI manager with CLI configuration
        cli_parser = CLIArgumentParser()
        ui_config = cli_parser.get_verbosity_config(cli_args)
        ui_manager = UIManager(ui_config)
        
        return logging_config, service_integration, ui_manager
        
    except Exception as e:
        # Fallback to basic logging if setup fails
        print(f"Warning: Failed to set up advanced logging: {e}")
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        # Create basic UI manager for fallback
        from rich.console import Console
        basic_ui_config = {'progress_enabled': False, 'color_enabled': False}
        basic_ui = UIManager(basic_ui_config)
        return None, None, basic_ui


# Legacy setup_logging function removed - replaced by setup_logging_system()


def show_live_mode_info(test_mode_enabled: bool = False, email_test_mode_enabled: bool = False) -> None:
    """Show information about live mode execution."""
    if test_mode_enabled:
        print("🧪 LIVE MODE with TEST MODE enabled")
        print("   • Using mock/test services for all operations")
    elif email_test_mode_enabled:
        print("🔧 LIVE MODE with EMAIL TEST MODE enabled")
        print("   • Using real services with email substitution only")
        print(f"   • Emails will be sent to: {os.getenv('TEST_EMAIL_OVERRIDE', 'not configured')}")
        print(f"   • Salesforce searches will use: {os.getenv('TEST_SALESFORCE_EMAIL', 'not configured')}")
    else:
        print("🚀 LIVE MODE - Full production services")
        print("   • Connecting to real Azure services")
        print("   • Processing real emails with real recipients")
        print("   • Creating real cases and notifications")


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        cleanup_logging()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


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
        
        # Add prompt system metrics
        metrics_collector = get_metrics_collector()
        prompt_health = metrics_collector.get_health_status()
        prompt_stats = metrics_collector.get_current_statistics()
        
        health_status["prompt_system"] = {
            "health": prompt_health,
            "statistics": prompt_stats
        }
        
        status_code = 200 if health_status["overall_status"] == "HEALTHY" else 503
        
        return web.Response(
            text=json.dumps(health_status, indent=2, default=str),
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


async def prompt_metrics_handler(request: web.Request) -> web.Response:
    """Endpoint for prompt system metrics."""
    try:
        metrics_collector = get_metrics_collector()
        
        # Get query parameters
        format_type = request.query.get('format', 'json')
        hours = int(request.query.get('hours', '1'))
        
        if format_type == 'prometheus':
            metrics_data = metrics_collector.export_metrics('prometheus')
            content_type = 'text/plain'
        else:
            # JSON format with optional time series
            if 'timeseries' in request.query:
                metrics_data = json.dumps(
                    metrics_collector.get_time_series_data(hours), 
                    indent=2, 
                    default=str
                )
            else:
                metrics_data = json.dumps(
                    metrics_collector.get_current_statistics(), 
                    indent=2, 
                    default=str
                )
            content_type = 'application/json'
        
        return web.Response(
            text=metrics_data,
            status=200,
            content_type=content_type
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({
                "error": str(e),
                "timestamp": "unknown"
            }, indent=2),
            status=500,
            content_type="application/json"
        )


async def service_info_handler(request: web.Request) -> web.Response:
    """Service information endpoint."""
    try:
        metrics_collector = get_metrics_collector()
        health_status = metrics_collector.get_health_status()
        
        service_info = {
            "service": "inbox_monitor",
            "version": "1.0.0",
            "status": "running",
            "features": {
                "oauth_migration": "enabled",
                "connection_pooling": "enabled",
                "external_prompts": "enabled",
                "prompt_metrics": "enabled"
            },
            "endpoints": {
                "health": "/health",
                "detailed_health": "/health/detailed", 
                "readiness": "/ready",
                "prompt_metrics": "/metrics/prompts",
                "service_info": "/info"
            },
            "prompt_system": {
                "status": health_status["overall_status"],
                "health_score": health_status["health_score"]
            }
        }
        
        return web.Response(
            text=json.dumps(service_info, indent=2),
            status=200,
            content_type="application/json"
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({
                "service": "inbox_monitor",
                "status": "error",
                "error": str(e)
            }, indent=2),
            status=500,
            content_type="application/json"
        )


async def create_health_check_server(port: int = 8080) -> web.Application:
    """Create health check HTTP server."""
    app = web.Application()
    
    # Add health check routes
    app.router.add_get("/health", health_check_handler)
    app.router.add_get("/health/detailed", health_detailed_handler)
    app.router.add_get("/ready", readiness_handler)
    
    # Add prompt system metrics routes
    app.router.add_get("/metrics/prompts", prompt_metrics_handler)
    app.router.add_get("/info", service_info_handler)
    
    # Add root route for basic info
    async def root_handler(request: web.Request) -> web.Response:
        return web.Response(
            text=json.dumps({
                "service": "inbox_monitor",
                "status": "running",
                "oauth_migration": "enabled",
                "connection_pooling": "enabled",
                "endpoints": {
                    "health": "/health",
                    "detailed_health": "/health/detailed", 
                    "readiness": "/ready",
                    "prompt_metrics": "/metrics/prompts",
                    "service_info": "/info"
                }
            }, indent=2),
            content_type="application/json"
        )
    
    app.router.add_get("/", root_handler)
    
    return app


async def run_continuous() -> bool:
    """Run the inbox monitor continuously with connection pooling and signal handling."""
    settings = await get_settings()
    validate_settings(settings)

    try:
        print("🚀 Starting Inbox Monitor with Connection Pooling")
        print(f"📧 Monitoring: {settings.graph_api.monitored_email}")
        print(f"⏱️  Polling interval: {settings.processing.polling_interval_seconds} seconds")
        print(f"📁 Output: {settings.output.storage_type}")
        if settings.dry_run:
            print("🧪 DRY RUN MODE: Emails will not be moved")
        
        # Initialize connection pool with configuration and warehouse readiness
        print("🔧 Initializing Databricks connection pool...")
        print("📡 Note: If this is the first startup after inactivity, the SQL warehouse may need 5-10 minutes to start")
        
        pool_config = ConnectionPoolConfig(
            min_connections=int(os.getenv("CONNECTION_POOL_MIN_CONNECTIONS", "2")),
            max_connections=int(os.getenv("CONNECTION_POOL_MAX_CONNECTIONS", "5")),
            health_check_interval_seconds=int(os.getenv("CONNECTION_POOL_HEALTH_CHECK_INTERVAL", "300")),
            max_connection_age_seconds=int(os.getenv("CONNECTION_POOL_MAX_AGE_SECONDS", "3600")),
            # Enhanced timeouts for warehouse startup scenarios
            connection_timeout_seconds=int(os.getenv("CONNECTION_POOL_CONNECTION_TIMEOUT", "300")),
            pool_warmup_timeout_seconds=int(os.getenv("CONNECTION_POOL_WARMUP_TIMEOUT", "900"))
        )
        
        print(f"⏱️  Pool configuration: {pool_config.min_connections}-{pool_config.max_connections} connections, "
              f"{pool_config.connection_timeout_seconds}s connection timeout, "
              f"{pool_config.pool_warmup_timeout_seconds}s warmup timeout")
        
        connection_pool = await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        print(f"✅ Connection pool initialized successfully with {pool_config.min_connections}-{pool_config.max_connections} connections")

        # Metrics collection will be initialized as part of individual services
        print("📊 Connection pool and metrics are ready")

        # Setup graceful shutdown
        shutdown_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
            shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        monitor = InboxMonitor(settings)
        
        # Start health check server if enabled
        runner = None
        if settings.monitoring.health_check_enabled:
            health_port = int(os.getenv("HEALTH_CHECK_PORT", "8080"))
            health_app = await create_health_check_server(health_port)
            runner = web.AppRunner(health_app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", health_port)
            await site.start()
            print(f"🏥 Health check server started on port {health_port}")
            print(f"   Health endpoints: http://localhost:{health_port}/health")
            print(f"   Detailed health: http://localhost:{health_port}/health/detailed")
            print(f"   Readiness probe: http://localhost:{health_port}/ready")
            print(f"   Prompt metrics: http://localhost:{health_port}/metrics/prompts")
            print(f"   Service info: http://localhost:{health_port}/info")
        else:
            print("🚫 Health check endpoints disabled (HEALTH_CHECK_ENABLED=false)")
        
        print("\nPress Ctrl+C to stop...")

        # Run monitor until shutdown signal
        monitor_task = asyncio.create_task(monitor.start())
        
        # Wait for shutdown signal or monitor completion
        done, pending = await asyncio.wait(
            [monitor_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel any remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        print("🛑 Stopping monitor...")
        try:
            await monitor.stop()
        except Exception as e:
            print(f"⚠️  Error stopping monitor: {e}")
        
        # Shutdown health check server
        if runner is not None:
            print("🏥 Shutting down health check server...")
            try:
                await runner.cleanup()
            except Exception as e:
                print(f"⚠️  Error stopping health check server: {e}")
        else:
            print("🏥 No health check server to shutdown")
        
        # Stop prompt metrics collection
        print("📊 Stopping prompt metrics collection...")
        # Metrics collection cleanup handled by individual services
        print("✅ Prompt metrics collection stopped")
        
        # Shutdown connection pool
        print("🔧 Shutting down connection pool...")
        await shutdown_connection_pool()
        print("✅ Connection pool shutdown complete")

        print("✅ Monitor stopped successfully")
        return True

    except Exception as e:
        print(f"❌ Monitor failed: {e}")
        # Ensure pool is shutdown even on failure
        try:
            await shutdown_connection_pool()
        except:
            pass
        return False


async def validate_settings_safely(mock_mode: bool = False) -> bool:
    """Validate settings with optional mock mode for safe testing."""
    try:
        # Check TEST_MODE and TEST_MODE_EMAIL environment variables
        test_mode_enabled = os.getenv("TEST_MODE", "false").lower() == "true"
        email_test_mode_enabled = os.getenv("TEST_MODE_EMAIL", "false").lower() == "true"
        
        if mock_mode:
            print("🧪 MOCK MODE: Skipping real service validation")
            return True
        
        if test_mode_enabled:
            print(f"🧪 TEST MODE ENABLED: All services using mock/test mode")
        
        if email_test_mode_enabled:
            print(f"📧 EMAIL TEST MODE: Using TEST_EMAIL_OVERRIDE={os.getenv('TEST_EMAIL_OVERRIDE', 'not set')} and TEST_SALESFORCE_EMAIL={os.getenv('TEST_SALESFORCE_EMAIL', 'not set')}")
            
        # For live mode, get settings with test_mode parameter based on environment variable
        settings = await get_settings(test_mode=test_mode_enabled)
        validate_settings(settings)
        return True
    except Exception as e:
        print(f"❌ Settings validation failed: {e}")
        return False


async def check_once(ui_manager=None, mock_mode: bool = False) -> bool:
    """Check inbox once and exit."""
    if not await validate_settings_safely(mock_mode):
        return False
        
    # Handle mock mode vs live mode
    if mock_mode:
        return await check_once_mock_mode(ui_manager)
    
    # Get TEST_MODE and TEST_MODE_EMAIL settings
    test_mode_enabled = os.getenv("TEST_MODE", "false").lower() == "true"
    email_test_mode_enabled = os.getenv("TEST_MODE_EMAIL", "false").lower() == "true"
    
    # For live mode, validate and get settings with proper test mode flag
    settings = await get_settings(test_mode=test_mode_enabled)
    validate_settings(settings)
    
    # Show information about the mode we're running in and which inbox we're monitoring
    print(f"📬 Monitoring inbox: {settings.graph_api.monitored_email}")
    show_live_mode_info(test_mode_enabled, email_test_mode_enabled)
    
    # First, check if there are any emails to process (lightweight operation)
    print("🔄 Checking for emails...")
    async with GraphAPIClient(settings.graph_api) as graph_client:
        messages = await graph_client.get_inbox_messages(
            limit=settings.processing.batch_size
        )
        
        if not messages:
            print("📭 No emails found in inbox - no processing needed")
            return True
    
    # Only initialize heavy services if there are emails to process
    print(f"📧 Found {len(messages)} email(s) - initializing processing services...")
    
    # Initialize connection pool for LIVE mode operations
    pool_config = ConnectionPoolConfig(
        min_connections=2,
        max_connections=5,
        health_check_interval_seconds=int(os.getenv("CONNECTION_POOL_HEALTH_CHECK_INTERVAL", "300")),
        max_connection_age_seconds=int(os.getenv("CONNECTION_POOL_MAX_AGE_SECONDS", "3600")),
        connection_timeout_seconds=int(os.getenv("CONNECTION_POOL_CONNECTION_TIMEOUT", "300")),
        pool_warmup_timeout_seconds=int(os.getenv("CONNECTION_POOL_WARMUP_TIMEOUT", "900")),
        idle_timeout_seconds=int(os.getenv("CONNECTION_POOL_IDLE_TIMEOUT", "1800"))
    )
    
    try:
        connection_pool = await initialize_connection_pool(
            settings.databricks_oauth,
            settings.key_vault,
            pool_config
        )
        print("✅ Connection pool initialized for email processing")
    except Exception as e:
        print(f"❌ Failed to initialize connection pool: {e}")
        return False

    if ui_manager:
        # Use rich formatting for output
        progress_manager = ui_manager.get_progress_manager()
        
        # Show progress with UI  
        with progress_manager.start_progress_display("Inbox Check"):
            async with GraphAPIClient(settings.graph_api) as graph_client:
                processor = EmailProcessor(settings, graph_client, progress_manager)
                # Note: We already checked for messages above, but EmailProcessor will re-fetch
                # This could be further optimized by modifying EmailProcessor to accept pre-fetched messages
                results = await processor.process_inbox()
                
                # Format results with rich UI
                duration = results.get('processing_time_seconds', 0)
                ui_manager.format_inbox_results(
                    results.get('processed_count', 0),
                    results.get('failed_count', 0), 
                    duration,
                    results.get('processing_results', [])
                )
                
                return results.get("success", False)
    else:
        # Fallback to simple print output
        print("🔄 Processing emails...")

        async with GraphAPIClient(settings.graph_api) as graph_client:
            processor = EmailProcessor(settings, graph_client)
            # Note: We already checked for messages above, but EmailProcessor will re-fetch  
            # This could be further optimized by modifying EmailProcessor to accept pre-fetched messages
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

        # Cleanup connection pool
        try:
            await shutdown_connection_pool()
            print("✅ Connection pool shutdown complete")
        except Exception as e:
            print(f"⚠️  Error shutting down connection pool: {e}")

        return True


async def check_once_mock_mode(ui_manager=None) -> bool:
    """Mock mode inbox check that simulates functionality without real services."""
    import time
    import random
    
    print("🧪 MOCK MODE - Simulating inbox check...")
    print("📧 Mock Email: test@example.com -> 'Demo: Email processing test'")
    
    # Simulate processing time
    await asyncio.sleep(0.5)
    
    if ui_manager:
        # Use rich formatting for mock output
        progress_manager = ui_manager.get_progress_manager()
        
        with progress_manager.start_progress_display("Mock Inbox Check"):
            # Simulate email processing stages
            print("🔄 Connecting to mock services...")
            await asyncio.sleep(0.3)
            
            print("📧 Processing mock emails...")
            await asyncio.sleep(0.5)
            
            print("🧠 Running AI classification (mock)...")
            await asyncio.sleep(0.4)
            
            print("✉️  Generating response (mock)...")
            await asyncio.sleep(0.3)
            
            # Mock results
            processed_count = random.randint(2, 5)
            failed_count = 0
            duration = 1.5
            
            # Format mock results as expected by UI manager
            mock_email_details = []
            for i in range(processed_count):
                mock_email_details.append({
                    'id': f'mock_email_{i+1}',
                    'subject': f'Mock Email {i+1}: Demo processing test',
                    'from': f'test{i+1}@example.com',
                    'status': 'success',
                    'action': 'processed (mock)',
                    'message': f'Mock email {i+1} processed successfully'
                })
            
            ui_manager.format_inbox_results(
                processed_count,
                failed_count, 
                duration,
                mock_email_details
            )
    else:
        # Fallback to simple print output
        print("🔄 Simulating inbox processing...")
        await asyncio.sleep(1.0)
        
        processed_count = random.randint(2, 5)
        print("✅ Mock inbox check completed:")
        print(f"   📊 Processed: {processed_count} emails (simulated)")
        print(f"   ❌ Failed: 0 emails")
        print(f"   ⏱️  Time: 1.5 seconds (simulated)")
        print("   🧪 All operations were simulated - no real services were used")
    
    return True


async def test_connection(mock_mode: bool = False) -> bool:
    """Test Graph API connection."""
    if mock_mode:
        print("🧪 MOCK MODE - Simulating connection test...")
        await asyncio.sleep(0.8)
        print("✅ Mock connection test successful!")
        print("   📧 Email: test@example.com (mock)")
        print("   👤 Display Name: Test User (mock)")
        print("   🆔 ID: mock-user-id-12345")
        print("\n📬 Mock Inbox Access:")
        print("   📁 Folder: Inbox (mock)")
        print("   📊 Total items: 42 (mock)")
        print("   📨 Unread items: 5 (mock)")
        print("   🧪 All connection details were simulated - no real services were used")
        return True

    # Get TEST_MODE and TEST_MODE_EMAIL settings
    test_mode_enabled = os.getenv("TEST_MODE", "false").lower() == "true"
    email_test_mode_enabled = os.getenv("TEST_MODE_EMAIL", "false").lower() == "true"
    
    if not await validate_settings_safely(mock_mode):
        return False
        
    # Show information about the mode we're running in  
    show_live_mode_info(test_mode_enabled, email_test_mode_enabled)

    # For live mode, validate and get settings with proper test mode flag  
    settings = await get_settings(test_mode=test_mode_enabled)
    validate_settings(settings)

    print(f"📬 Monitoring inbox: {settings.graph_api.monitored_email}")
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

        settings = await get_settings()

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

        # Import the setup function from utils folder
        from utils.setup_databricks import main as setup_main

        # Run the setup
        await setup_main()

        print("✅ Databricks setup completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Databricks setup failed: {e}")
        return False


async def run_inbox_check(args: argparse.Namespace, 
                         service_integration: Optional[ServiceLoggingIntegration] = None,
                         ui_manager: Optional[UIManager] = None) -> None:
    """Run a single inbox check with enhanced logging and rich UI."""
    # Get loggers first
    if service_integration:
        console_logger = service_integration.logger_factory.get_console_logger("main")
        diagnostic_logger = service_integration.logger_factory.get_structured_logger("main")
    else:
        console_logger = logging.getLogger("console")
        diagnostic_logger = logging.getLogger("diagnostic")
    
    # Check for mock mode - get it from the main() function processing
    mock_mode = getattr(args, '_computed_mock_mode', False)
    
    # Show user-friendly progress with rich formatting
    if ui_manager:
        with ui_manager.get_progress_manager().start_progress_display("Inbox Check"):
            progress_manager = ui_manager.get_progress_manager()
            operation_id = progress_manager.create_operation(
                OperationType.INBOX_CHECK, 
                "Checking inbox once...", 
                ProgressType.SPINNER
            )
    else:
        console_logger.info("🔄 Checking inbox once...")
    
    # Log diagnostic information
    diagnostic_logger.info("Starting inbox check", extra={
        'operation': 'inbox_check',
        'limit': getattr(args, 'limit', 10),
        'event_type': 'inbox_check_start'
    })
    
    try:
        # Use the updated check_once function with mock mode support
        success = await check_once(ui_manager, mock_mode)
        
        # Log results
        if success:
            diagnostic_logger.info("Inbox check completed successfully", extra={
                'operation': 'inbox_check',
                'mock_mode': mock_mode,
                'event_type': 'inbox_check_success'
            })
        else:
            diagnostic_logger.error("Inbox check failed", extra={
                'operation': 'inbox_check',
                'mock_mode': mock_mode,
                'event_type': 'inbox_check_failure'
            })
        
    except Exception as e:
        # Handle error with UI manager if available
        if ui_manager:
            ui_manager.format_error_details(e, {"operation": "inbox_check"})
            
            # Fail progress operation
            if 'operation_id' in locals() and operation_id:
                progress_manager = ui_manager.get_progress_manager()
                progress_manager.fail_operation(operation_id, e, "Inbox check failed")
        else:
            console_logger.error(f"❌ Inbox check failed: {e}")
            
        diagnostic_logger.error("Inbox check failed", extra={
            'operation': 'inbox_check',
            'error_type': type(e).__name__,
            'error_message': str(e),
            'event_type': 'inbox_check_error'
        }, exc_info=True)
        raise
    
    finally:
        # Cleanup
        if 'graph_client' in locals():
            await graph_client.close()


async def run_system_status(args: argparse.Namespace,
                           service_integration: Optional[ServiceLoggingIntegration] = None,
                           ui_manager: Optional[UIManager] = None) -> None:
    """Show system status with appropriate detail level and rich formatting."""
    # Get loggers
    if service_integration:
        console_logger = service_integration.logger_factory.get_console_logger("main")
        diagnostic_logger = service_integration.logger_factory.get_structured_logger("main")
    else:
        console_logger = logging.getLogger("console")
        diagnostic_logger = logging.getLogger("diagnostic")
    
    # Show progress with rich UI if available
    if ui_manager:
        with ui_manager.get_progress_manager().start_progress_display("System Status Check"):
            progress_manager = ui_manager.get_progress_manager()
            operation_id = progress_manager.create_operation(
                OperationType.SYSTEM_STATUS,
                "Checking system status...",
                ProgressType.SPINNER
            )
    else:
        console_logger.info("🔍 Checking system status...")
    
    try:
        # Check various system components
        health_service = HealthCheckService()
        
        if service_integration:
            service_integration.retrofit_service_methods(health_service,
                                                       service_integration.logger_factory.get_logger("services.health_check"))
        
        status = await health_service.get_comprehensive_health_status()
        
        # Complete the progress operation
        if ui_manager and 'operation_id' in locals():
            progress_manager.complete_operation(operation_id, "Status check completed")
        
        # Show status using rich formatting or fallback to basic logging
        detailed = getattr(args, 'detailed', False) or getattr(args, 'debug', False)
        
        if ui_manager:
            # Use rich formatting for status display
            ui_manager.format_system_status(status, detailed=detailed)
        else:
            # Fallback to basic console logging
            if detailed:
                console_logger.info("📊 Detailed System Status:")
                components = status.get('components', [])
                for component in components:
                    component_name = component.get('name', 'Unknown')
                    component_status = component.get('status', 'UNKNOWN')
                    status_icon = "✅" if component_status == 'HEALTHY' else "❌"
                    message = component.get('message', '')
                    console_logger.info(f"   {status_icon} {component_name}: {component_status} - {message}")
            else:
                components = status.get('components', [])
                healthy_count = sum(1 for comp in components if comp.get('status') == 'HEALTHY')
                total_count = len(components)
                overall_icon = "✅" if healthy_count == total_count else "⚠️"
                console_logger.info(f"{overall_icon} System Status: {healthy_count}/{total_count} components healthy")
        
        # Always log detailed status for diagnostics
        diagnostic_logger.info("System status check completed", extra={
            'operation': 'status_check',
            'status': status,
            'healthy_components': sum(1 for comp in status.get('components', []) if comp.get('status') == 'HEALTHY'),
            'total_components': len(status.get('components', [])),
            'event_type': 'status_check_success'
        })
        
    except Exception as e:
        console_logger.error(f"❌ Status check failed: {e}")
        diagnostic_logger.error("Status check failed", extra={
            'operation': 'status_check',
            'error_type': type(e).__name__,
            'error_message': str(e),
            'event_type': 'status_check_error'
        }, exc_info=True)
        raise


def main() -> None:
    """Main entry point with enhanced CLI and logging."""
    # Set up signal handlers
    setup_signal_handlers()
    
    # Parse command line arguments
    cli_parser = CLIArgumentParser()
    args = cli_parser.parse_args()
    
    # Set up logging system and UI based on CLI args and environment
    logging_config, service_integration, ui_manager = setup_logging_system(args)
    
    # Show welcome message if appropriate
    if not getattr(args, 'quiet', False) and ui_manager:
        ui_manager.show_welcome_message("1.0.0")
    
    try:
        # Check for mock mode and live mode flags
        mock_mode = getattr(args, 'mock_mode', False) or getattr(args, 'mock', False)
        live_mode = getattr(args, 'live', False)
        
        # Handle conflicting flags
        if mock_mode and live_mode:
            print("❌ Error: Cannot use both --mock-mode and --live flags")
            sys.exit(1)
        
        # For main.py (production version), default is LIVE mode
        # Only use mock mode if explicitly requested with --mock-mode flag
        if not mock_mode and not live_mode:
            live_mode = True  # Default to live mode for production main.py
            
        # Store computed mode on args for other functions to use
        args._computed_mock_mode = mock_mode
        args._computed_live_mode = live_mode
        
        # Run the requested command
        if args.command == 'check':
            asyncio.run(run_inbox_check(args, service_integration, ui_manager))
        elif args.command == 'run':
            # Use existing continuous monitor logic with enhanced logging
            if mock_mode:
                print("❌ Error: Continuous monitoring not supported in mock mode. Remove --mock-mode for continuous monitoring.")
                sys.exit(1)
            asyncio.run(run_continuous())
        elif args.command == 'status':
            asyncio.run(run_system_status(args, service_integration, ui_manager))
        elif args.command == 'test':
            # Use test logic with mock mode support
            success = asyncio.run(test_connection(mock_mode))
            if not success:
                sys.exit(1)
        elif args.command == 'setup':
            # Use existing setup logic with enhanced logging
            if mock_mode:
                print("❌ Error: Setup not supported in mock mode. Remove --mock-mode for database setup.")
                sys.exit(1)
            asyncio.run(setup_databricks())
        else:
            cli_parser.print_help()
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Operation failed: {e}")
        sys.exit(1)
    finally:
        # Clean up logging system
        cleanup_logging()


# Legacy function removed - replaced by main() with enhanced CLI and logging system


if __name__ == "__main__":
    main()
