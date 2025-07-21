"""
Inbox Monitor Service
=====================

Main monitoring service that continuously polls the inbox for new emails.
"""

import asyncio
import signal
from datetime import datetime
from typing import Any

import structlog

try:
    # Try absolute imports first (for direct script execution)
    from config.settings import AppSettings
    from services.email_processor import EmailProcessor
    from services.graph_api_client import GraphAPIClient

    from utils.async_cleanup import graceful_shutdown, suppress_future_warnings
except ImportError:
    # Fall back to relative imports (for module execution)
    from ..config.settings import AppSettings
    from ..utils.async_cleanup import graceful_shutdown, suppress_future_warnings
    from .email_processor import EmailProcessor
    from .graph_api_client import GraphAPIClient


class InboxMonitor:
    """Continuous inbox monitoring service."""

    def __init__(self, settings: AppSettings):
        """Initialize inbox monitor.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = structlog.get_logger(__name__)
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.graph_client: GraphAPIClient | None = None
        self.email_processor: EmailProcessor | None = None

    async def start(self) -> None:
        """Start the inbox monitor service."""
        self.logger.info(
            "Starting inbox monitor",
            environment=self.settings.environment,
            monitored_email=self.settings.graph_api.monitored_email,
            polling_interval=self.settings.processing.polling_interval_seconds,
        )

        # Suppress future warnings during startup
        suppress_future_warnings()

        # Initialize clients
        self.graph_client = GraphAPIClient(self.settings.graph_api)
        await self.graph_client.initialize()

        self.email_processor = EmailProcessor(self.settings, self.graph_client)

        # Set up signal handlers
        self._setup_signal_handlers()

        # Start monitoring
        self._running = True
        await self._monitor_loop()

    async def stop(self) -> None:
        """Stop the inbox monitor service."""
        self.logger.info("Stopping inbox monitor")
        self._running = False
        self._shutdown_event.set()

        # Cleanup resources
        if self.graph_client:
            await self.graph_client.cleanup()

        # Perform graceful shutdown
        await graceful_shutdown(timeout=5.0)

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        consecutive_failures = 0
        max_consecutive_failures = 5

        while self._running:
            try:
                start_time = datetime.utcnow()

                self.logger.info("Starting inbox check")

                # Process inbox
                if self.email_processor:
                    results = await self.email_processor.process_inbox()
                else:
                    results = {
                        "success": False,
                        "error": "Email processor not initialized",
                    }

                if results["success"]:
                    consecutive_failures = 0
                    self.logger.info(
                        "Inbox check completed successfully",
                        processed=results["processed_count"],
                        failed=results["failed_count"],
                        duration=results.get("processing_time_seconds", 0),
                    )
                else:
                    consecutive_failures += 1
                    self.logger.error(
                        "Inbox check completed with errors",
                        processed=results["processed_count"],
                        failed=results["failed_count"],
                        errors=results["errors"],
                    )

                # Check if we should stop due to too many failures
                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error(
                        f"Too many consecutive failures ({consecutive_failures}), stopping monitor"
                    )
                    self._running = False
                    break

                # Calculate time until next run
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                sleep_time = max(
                    0,
                    self.settings.processing.polling_interval_seconds - processing_time,
                )

                if self._running and sleep_time > 0:
                    self.logger.info(f"Waiting {sleep_time:.1f} seconds until next check")

                    # Wait for either the sleep time or shutdown signal
                    try:
                        await asyncio.wait_for(self._shutdown_event.wait(), timeout=sleep_time)
                        # If we get here, shutdown was requested
                        self.logger.info("Shutdown requested during wait")
                        break
                    except asyncio.TimeoutError:
                        # Normal timeout, check if we should still continue
                        if not self._running:
                            self.logger.info("Shutdown detected after timeout")
                            break
                        # Otherwise continue to next iteration
                        pass

            except Exception as e:
                error_str = str(e)

                # Don't count connection cleanup errors as failures
                if (
                    "SSL shutdown timed out" in error_str
                    or "ClientConnectionError" in error_str
                    or "Connection lost" in error_str
                ):
                    self.logger.warning(
                        "Connection cleanup error (not counted as failure)",
                        error=error_str,
                        consecutive_failures=consecutive_failures,
                    )
                else:
                    consecutive_failures += 1
                    self.logger.error(
                        "Unexpected error in monitor loop",
                        error=error_str,
                        consecutive_failures=consecutive_failures,
                    )

                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error(
                        f"Too many consecutive failures ({consecutive_failures}), stopping monitor"
                    )
                    self._running = False
                    break

                # Wait before retrying
                if self._running:
                    await asyncio.sleep(self.settings.processing.retry_delay_seconds)

        self.logger.info("Monitor loop ended")

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown")

            # Force exit on second Ctrl+C immediately
            if hasattr(self, "_signal_count"):
                self._signal_count += 1
                self.logger.warning(f"Signal count: {self._signal_count}")
                if self._signal_count >= 2:
                    self.logger.warning("Force quit requested - immediate exit")
                    import os

                    os._exit(1)  # More forceful than sys.exit()
            else:
                self._signal_count = 1

            self._running = False
            self._shutdown_event.set()

            # Get the current event loop and stop it if needed
            try:
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    # Schedule the loop to stop on the next iteration
                    loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass  # No running loop

        # Handle SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on the service.

        Returns:
            Health check results
        """
        health = {
            "status": "healthy" if self._running else "stopped",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "graph_api_connected": False,
            "last_error": None,
        }

        if self.graph_client:
            try:
                # Test Graph API connection
                await self.graph_client._make_request("GET", "/me")
                health["graph_api_connected"] = True
            except Exception as e:
                health["status"] = "unhealthy"
                health["last_error"] = str(e)

        return health
