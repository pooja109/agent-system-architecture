"""
Tests for Inbox Monitor Service
================================
Unit tests for the main monitoring service.
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.monitor import InboxMonitor  # noqa: E402
class TestInboxMonitor:
    """Test InboxMonitor class."""
    @pytest.fixture
    def monitor(self, mock_settings):
        """Create inbox monitor instance."""
        return InboxMonitor(mock_settings)
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_stop(self, monitor):
        """Test starting and stopping the monitor."""
        # Mock the monitor loop to exit after one iteration
        async def mock_monitor_loop():
            monitor._running = False
        # Mock GraphAPIClient
        with patch("services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client
            # Mock EmailProcessor
            with patch(
                "services.monitor.EmailProcessor"
            ) as mock_processor_class:
                mock_processor = AsyncMock()
                mock_processor_class.return_value = mock_processor
                # Replace the monitor loop with our mock
                monitor._monitor_loop = mock_monitor_loop
                # Start the monitor
                await monitor.start()
                # Verify initialization
                assert monitor.graph_client is not None
                assert monitor.email_processor is not None
                # The mock_graph_client should have had initialize called
                mock_graph_client.initialize.assert_called_once()
                # Stop the monitor
                await monitor.stop()
                # The mock_graph_client should have had cleanup called  
                mock_graph_client.cleanup.assert_called_once()
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_monitor_loop_success(self, monitor):
        """Test successful monitoring loop iteration."""
        monitor._running = True
        # Mock email processor
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": True,
            "processed_count": 5,
            "failed_count": 0,
            "errors": [],
            "processing_time_seconds": 2.5,
        }
        monitor.email_processor = mock_processor
        # Mock shutdown event to stop after one iteration
        monitor._shutdown_event = AsyncMock()
        # Create a counter to limit iterations
        iteration_count = 0
        async def mock_wait(*args, **kwargs):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= 1:
                monitor._running = False
            raise asyncio.TimeoutError()
        monitor._shutdown_event.wait.side_effect = mock_wait
        # Run the monitor loop
        await monitor._monitor_loop()
        # Verify processing was called
        mock_processor.process_inbox.assert_called_once()
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_monitor_loop_with_failures(self, monitor):
        """Test monitoring loop with processing failures."""
        monitor._running = True
        # Mock email processor to fail
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": False,
            "processed_count": 2,
            "failed_count": 3,
            "errors": ["Error 1", "Error 2"],
            "processing_time_seconds": 1.5,
        }
        monitor.email_processor = mock_processor
        # Track consecutive failures
        iteration_count = 0
        max_iterations = 6  # Should stop after 5 failures
        async def mock_sleep(duration):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= max_iterations:
                monitor._running = False
        # Mock shutdown event and sleep
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_loop()
        # Should have stopped due to consecutive failures
        assert monitor._running is False
        assert iteration_count < max_iterations  # Stopped before max iterations
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_monitor_loop_exception_handling(self, monitor):
        """Test exception handling in monitor loop."""
        monitor._running = True
        # Mock email processor to raise exception
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = Exception("Processing error")
        monitor.email_processor = mock_processor
        # Track iterations
        iteration_count = 0
        async def mock_sleep(duration):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= 5:
                monitor._running = False
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await monitor._monitor_loop()
        # Should have stopped due to consecutive failures
        assert monitor._running is False
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.asyncio
    async def test_monitor_loop_shutdown_during_wait(self, monitor):
        """Test shutdown signal during wait period."""
        monitor._running = True
        # Mock email processor
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": True,
            "processed_count": 1,
            "failed_count": 0,
            "errors": [],
            "processing_time_seconds": 0.1,
        }
        monitor.email_processor = mock_processor
        # Mock shutdown event to trigger during wait
        monitor._shutdown_event = AsyncMock()
        async def simulate_shutdown(*args, **kwargs):
            monitor._running = False
            return  # Simulate shutdown signal
        monitor._shutdown_event.wait.side_effect = simulate_shutdown
        await monitor._monitor_loop()
        # Should have processed once and then stopped
        mock_processor.process_inbox.assert_called_once()
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.integration
    @pytest.mark.slow
    def test_signal_handlers(self, monitor):
        """Test signal handler setup."""
        with patch("signal.signal") as mock_signal:
            monitor._setup_signal_handlers()
            # Should register handlers for SIGINT and SIGTERM
            assert mock_signal.call_count == 2
            # Get the registered handler
            handler = mock_signal.call_args_list[0][0][1]
            # Test handler creates stop task
            with patch("asyncio.create_task") as mock_create_task:
                handler(2, None)  # SIGINT
                mock_create_task.assert_called_once()
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, monitor):
        """Test health check when service is healthy."""
        monitor._running = True
        # Mock graph client
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.return_value = {"id": "user-id"}
        monitor.graph_client = mock_graph_client
        health = await monitor.health_check()
        assert health["status"] == "healthy"
        assert health["graph_api_connected"] is True
        assert health["last_error"] is None
        assert "timestamp" in health
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, monitor):
        """Test health check when service is unhealthy."""
        monitor._running = True
        # Mock graph client to fail
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.side_effect = Exception("Connection failed")
        monitor.graph_client = mock_graph_client
        health = await monitor.health_check()
        assert health["status"] == "unhealthy"
        assert health["graph_api_connected"] is False
        assert health["last_error"] == "Connection failed"
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.asyncio
    async def test_health_check_stopped(self, monitor):
        """Test health check when service is stopped."""
        monitor._running = False
        monitor.graph_client = None
        health = await monitor.health_check()
        assert health["status"] == "stopped"
        assert health["graph_api_connected"] is False