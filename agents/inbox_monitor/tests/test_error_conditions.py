"""
Error Condition Tests for Inbox Monitor
========================================

Comprehensive tests for error conditions and failure scenarios.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ..services.email_processor import EmailProcessor
from ..services.graph_api_client import GraphAPIClient
from ..services.monitor import InboxMonitor


class TestEmailProcessorErrorConditions:
    """Test error conditions for EmailProcessor."""

    @pytest.fixture
    def processor(self, mock_settings, mock_graph_client):
        """Create email processor instance."""
        return EmailProcessor(mock_settings, mock_graph_client)

    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_api_failure(self, processor, mock_graph_client):
        """Test inbox processing when Graph API fails."""
        mock_graph_client.get_inbox_messages.side_effect = Exception("Graph API unavailable")

        results = await processor.process_inbox()

        assert results["success"] is False
        assert results["processed_count"] == 0
        assert results["failed_count"] == 0
        assert "Graph API unavailable" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_authentication_failure(self, processor, mock_graph_client):
        """Test inbox processing with authentication failure."""
        mock_graph_client.get_inbox_messages.side_effect = Exception(
            "Authentication failed: Invalid credentials"
        )

        results = await processor.process_inbox()

        assert results["success"] is False
        assert "Authentication failed" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_network_timeout(self, processor, mock_graph_client):
        """Test inbox processing with network timeout."""
        mock_graph_client.get_inbox_messages.side_effect = asyncio.TimeoutError("Network timeout")

        results = await processor.process_inbox()

        assert results["success"] is False
        assert "Network timeout" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_rate_limiting(self, processor, mock_graph_client):
        """Test inbox processing with rate limiting."""
        mock_graph_client.get_inbox_messages.side_effect = Exception(
            "Rate limit exceeded: 429 Too Many Requests"
        )

        results = await processor.process_inbox()

        assert results["success"] is False
        assert "Rate limit exceeded" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_folder_creation_permission_denied(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test inbox processing when folder creation is denied."""
        mock_graph_client.get_inbox_messages.return_value = [mock_graph_message]
        mock_graph_client.get_folder_by_name.return_value = None
        mock_graph_client.create_folder.side_effect = Exception(
            "Insufficient permissions to create folder"
        )

        results = await processor.process_inbox()

        assert results["success"] is False
        assert "Failed to create/get processed folder" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_partial_processing_failures(
        self, processor, mock_graph_client, mock_graph_message, mock_folder
    ):
        """Test inbox processing with some emails failing."""
        # Create multiple messages
        messages = [mock_graph_message.copy() for _ in range(3)]
        for i, msg in enumerate(messages):
            msg["id"] = f"message-{i}"

        mock_graph_client.get_inbox_messages.return_value = messages
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock conversion to fail for second message
        def mock_convert(message, processing_id, version):
            if message["id"] == "message-1":
                raise ValueError("Conversion failed for message-1")
            mock_email = Mock()
            mock_email.id = message["id"]
            mock_email.to_ai_format.return_value = {"id": message["id"]}
            mock_email.processing_metadata = Mock()
            mock_email.processing_metadata.processing_id = processing_id
            return mock_email

        mock_graph_client.convert_to_email_model.side_effect = mock_convert

        with patch("builtins.open", Mock()):
            results = await processor.process_inbox()

        assert results["success"] is False
        assert results["processed_count"] == 2
        assert results["failed_count"] == 1
        assert "Conversion failed for message-1" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_store_email_with_invalid_storage_type(self, processor, mock_email_model):
        """Test email storage with invalid storage type."""
        processor.settings.output.storage_type = "invalid-type"

        with pytest.raises(ValueError, match="Unsupported storage type"):
            await processor._store_email(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_file_with_invalid_path(self, processor, mock_email_model):
        """Test file storage with invalid path."""
        # Set output directory to an invalid path
        processor.settings.output.output_directory = "/invalid/path/that/does/not/exist"

        with pytest.raises(FileNotFoundError):
            await processor._store_email_file(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_api_without_endpoint(self, processor, mock_email_model):
        """Test API storage without endpoint configuration."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = None

        with pytest.raises(ValueError, match="API endpoint not configured"):
            await processor._store_email_api(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_api_with_server_error(self, processor, mock_email_model):
        """Test API storage with server error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception, match="API request failed: 500"):
                await processor._store_email_api(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_api_with_connection_error(self, processor, mock_email_model):
        """Test API storage with connection error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            with pytest.raises(httpx.ConnectError):
                await processor._store_email_api(mock_email_model)

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_with_graph_api_error(self, processor, mock_graph_client):
        """Test folder creation with Graph API error."""
        mock_graph_client.get_folder_by_name.side_effect = Exception("Graph API error")

        folder = await processor._ensure_processed_folder("Test Folder")
        assert folder is None

    @pytest.mark.asyncio
    async def test_process_single_email_with_json_serialization_error(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with JSON serialization error."""
        # Mock email conversion to return non-serializable object
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.side_effect = TypeError("Object is not JSON serializable")
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        result = await processor._process_single_email(
            mock_graph_message, "folder-id", "Test Folder"
        )

        assert result.success is False
        assert "Object is not JSON serializable" in result.error

    @pytest.mark.asyncio
    async def test_process_single_email_with_unicode_error(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with Unicode encoding error."""
        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock file writing to fail with encoding error
        with patch(
            "builtins.open",
            side_effect=UnicodeEncodeError("utf-8", "test", 0, 1, "invalid character"),
        ):
            result = await processor._process_single_email(
                mock_graph_message, "folder-id", "Test Folder"
            )

        assert result.success is False
        assert "UnicodeEncodeError" in result.error


class TestGraphAPIClientErrorConditions:
    """Test error conditions for GraphAPIClient."""

    @pytest.fixture
    def graph_client(self, mock_settings):
        """Create Graph API client for testing."""

        return GraphAPIClient(mock_settings.graph_api)

    def test_get_access_token_with_msal_error(self, graph_client):
        """Test token acquisition with MSAL error."""
        graph_client.msal_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials",
        }

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    def test_get_access_token_with_network_error(self, graph_client):
        """Test token acquisition with network error."""
        graph_client.msal_app.acquire_token_for_client.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            graph_client._get_access_token()

    @pytest.mark.asyncio
    async def test_make_request_without_initialization(self, graph_client):
        """Test making request without initializing client."""
        graph_client._client = None

        with pytest.raises(Exception, match="Client not initialized"):
            await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_with_http_error(self, graph_client, mock_httpx_client):
        """Test making request with HTTP error."""
        graph_client._client = mock_httpx_client

        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Graph API request failed: 404"):
            await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_with_connection_timeout(self, graph_client, mock_httpx_client):
        """Test making request with connection timeout."""
        graph_client._client = mock_httpx_client
        mock_httpx_client.request.side_effect = asyncio.TimeoutError("Connection timeout")

        with pytest.raises(asyncio.TimeoutError):
            await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_get_inbox_messages_with_malformed_response(
        self, graph_client, mock_httpx_client
    ):
        """Test getting inbox messages with malformed response."""
        graph_client._client = mock_httpx_client

        # Mock response with malformed JSON
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = AsyncMock(return_value="Invalid JSON response")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(json.JSONDecodeError):
            await graph_client.get_inbox_messages()

    @pytest.mark.asyncio
    async def test_get_inbox_messages_with_empty_response(self, graph_client, mock_httpx_client):
        """Test getting inbox messages with empty response."""
        graph_client._client = mock_httpx_client

        # Mock empty response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})  # Missing 'value' key
        mock_response.text = AsyncMock(return_value="{}")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        messages = await graph_client.get_inbox_messages()
        assert messages == []

    @pytest.mark.asyncio
    async def test_create_folder_with_quota_exceeded(self, graph_client, mock_httpx_client):
        """Test creating folder when quota is exceeded."""
        graph_client._client = mock_httpx_client

        # Mock quota exceeded response
        mock_response = AsyncMock()
        mock_response.status = 507
        mock_response.text = AsyncMock(return_value="Insufficient Storage")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Graph API request failed: 507"):
            await graph_client.create_folder("Test Folder")

    @pytest.mark.asyncio
    async def test_create_folder_with_permission_denied(self, graph_client, mock_httpx_client):
        """Test creating folder with permission denied."""
        graph_client._client = mock_httpx_client

        # Mock permission denied response
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value="Forbidden: Insufficient permissions")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Graph API request failed: 403"):
            await graph_client.create_folder("Test Folder")

    @pytest.mark.asyncio
    async def test_move_message_with_message_not_found(self, graph_client, mock_httpx_client):
        """Test moving message when message doesn't exist."""
        graph_client._client = mock_httpx_client

        # Mock message not found response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Message not found")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Graph API request failed: 404"):
            await graph_client.move_message("nonexistent-message", "folder-id")

    @pytest.mark.asyncio
    async def test_move_message_with_folder_not_found(self, graph_client, mock_httpx_client):
        """Test moving message to non-existent folder."""
        graph_client._client = mock_httpx_client

        # Mock folder not found response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid folder ID")

        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Graph API request failed: 400"):
            await graph_client.move_message("message-id", "nonexistent-folder")

    def test_convert_to_email_model_with_missing_required_fields(self, graph_client):
        """Test email model conversion with missing required fields."""
        incomplete_message = {
            "id": "test-id"
            # Missing receivedDateTime
        }

        with pytest.raises(KeyError):
            graph_client.convert_to_email_model(incomplete_message, "test-processing-id", "1.0.0")

    def test_convert_to_email_model_with_invalid_date_format(self, graph_client):
        """Test email model conversion with invalid date format."""
        invalid_message = {"id": "test-id", "receivedDateTime": "not-a-date"}

        with pytest.raises(ValueError):
            graph_client.convert_to_email_model(invalid_message, "test-processing-id", "1.0.0")

    def test_parse_email_address_with_malformed_data(self, graph_client):
        """Test parsing email address with malformed data."""
        # Test with completely missing structure
        malformed_data = {}
        result = graph_client._parse_email_address(malformed_data)
        assert result.email == ""
        assert result.name is None

        # Test with nested None values
        nested_none = {"emailAddress": None}
        with pytest.raises(TypeError):
            graph_client._parse_email_address(nested_none)


class TestInboxMonitorErrorConditions:
    """Test error conditions for InboxMonitor."""

    @pytest.fixture
    def monitor(self, mock_settings):
        """Create inbox monitor instance."""
        return InboxMonitor(mock_settings)

    @pytest.mark.asyncio
    async def test_start_with_graph_client_initialization_failure(self, monitor):
        """Test monitor start when Graph client initialization fails."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_client.initialize.side_effect = Exception(
                "Failed to initialize Graph client"
            )
            mock_graph_class.return_value = mock_graph_client

            with pytest.raises(Exception, match="Failed to initialize Graph client"):
                await monitor.start()

    @pytest.mark.asyncio
    async def test_monitor_loop_with_persistent_failures(self, monitor):
        """Test monitor loop with persistent processing failures."""
        monitor._running = True

        # Mock email processor to always fail
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": False,
            "processed_count": 0,
            "failed_count": 5,
            "errors": ["Persistent error"] * 5,
            "processing_time_seconds": 0.1,
        }
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        # Mock sleep to avoid actual delays
        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should have stopped due to consecutive failures
        assert monitor._running is False
        assert mock_processor.process_inbox.call_count == 5  # Max consecutive failures

    @pytest.mark.asyncio
    async def test_monitor_loop_with_unexpected_exception(self, monitor):
        """Test monitor loop with unexpected exception."""
        monitor._running = True

        # Mock email processor to raise unexpected exception
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = RuntimeError("Unexpected system error")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        # Mock sleep to avoid actual delays
        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should have stopped due to consecutive failures
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_with_memory_leak_simulation(self, monitor):
        """Test monitor loop with simulated memory leak."""
        monitor._running = True

        # Mock email processor to simulate memory growth
        mock_processor = AsyncMock()
        call_count = 0

        def simulate_memory_leak():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                raise MemoryError("Out of memory")
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0.1,
            }

        mock_processor.process_inbox.side_effect = simulate_memory_leak
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        # Mock sleep to avoid actual delays
        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should have stopped due to memory error
        assert monitor._running is False
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_health_check_with_graph_client_none(self, monitor):
        """Test health check when graph client is None."""
        monitor._running = True
        monitor.graph_client = None

        health = await monitor.health_check()

        assert health["status"] == "healthy"  # Still running
        assert health["graph_api_connected"] is False
        assert health["last_error"] is None

    @pytest.mark.asyncio
    async def test_health_check_with_graph_client_timeout(self, monitor):
        """Test health check with graph client timeout."""
        monitor._running = True

        # Mock graph client with timeout
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.side_effect = asyncio.TimeoutError("Health check timeout")
        monitor.graph_client = mock_graph_client

        health = await monitor.health_check()

        assert health["status"] == "unhealthy"
        assert health["graph_api_connected"] is False
        assert "Health check timeout" in health["last_error"]

    @pytest.mark.asyncio
    async def test_stop_with_cleanup_failure(self, monitor):
        """Test monitor stop when cleanup fails."""
        monitor._running = True

        # Mock graph client with cleanup failure
        mock_graph_client = AsyncMock()
        mock_graph_client.cleanup.side_effect = Exception("Cleanup failed")
        monitor.graph_client = mock_graph_client

        # Stop should complete even if cleanup fails
        await monitor.stop()

        assert monitor._running is False
        assert monitor._shutdown_event.is_set()

    def test_signal_handler_with_invalid_signal(self, monitor):
        """Test signal handler with invalid signal number."""
        with patch("signal.signal") as mock_signal:
            monitor._setup_signal_handlers()

            # Get the registered handler
            handler = mock_signal.call_args_list[0][0][1]

            # Test handler with invalid signal
            with patch("asyncio.create_task") as mock_create_task:
                handler(999, None)  # Invalid signal number
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_with_corrupted_settings(self, monitor):
        """Test monitor behavior with corrupted settings."""
        # Corrupt the settings during runtime
        monitor.settings.processing.polling_interval_seconds = -1  # Invalid value
        monitor.settings.processing.max_retry_attempts = 0  # Invalid value

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

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()

        call_count = 0

        async def mock_wait():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                monitor._running = False
            return

        monitor._shutdown_event.wait.side_effect = mock_wait

        # Should handle corrupted settings gracefully
        await monitor._monitor_loop()

        assert mock_processor.process_inbox.call_count == 1

    @pytest.mark.asyncio
    async def test_monitor_with_disk_space_exhaustion(self, monitor):
        """Test monitor behavior when disk space is exhausted."""
        monitor._running = True

        # Mock email processor to simulate disk space exhaustion
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = OSError("No space left on device")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        # Mock sleep to avoid actual delays
        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should have stopped due to consecutive failures
        assert monitor._running is False


class TestRetryUtilityErrorConditions:
    """Test error conditions for retry utility."""

    @pytest.mark.asyncio
    async def test_retry_operation_with_all_attempts_failing(self):
        """Test retry operation when all attempts fail."""
        from ..utils.retry import retry_operation

        async def always_fails():
            raise Exception("Always fails")

        success, result, error = await retry_operation(
            always_fails, "Test operation", max_attempts=3, delay_seconds=0.01
        )

        assert success is False
        assert result is None
        assert "Always fails" in error

    @pytest.mark.asyncio
    async def test_retry_operation_with_timeout(self):
        """Test retry operation with timeout."""
        from ..utils.retry import retry_operation

        async def slow_operation():
            await asyncio.sleep(1)  # Simulate slow operation
            return "success"

        success, result, error = await retry_operation(
            slow_operation, "Slow operation", max_attempts=1, delay_seconds=0.01
        )

        # Should complete successfully (no timeout in retry_operation)
        assert success is True
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_operation_with_intermittent_failures(self):
        """Test retry operation with intermittent failures."""
        from ..utils.retry import retry_operation

        call_count = 0

        async def intermittent_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Failure {call_count}")
            return "success"

        success, result, error = await retry_operation(
            intermittent_failure,
            "Intermittent operation",
            max_attempts=3,
            delay_seconds=0.01,
        )

        assert success is True
        assert result == "success"
        assert error is None
        assert call_count == 3

    def test_retry_with_backoff_decorator_error_conditions(self):
        """Test retry with backoff decorator error conditions."""
        from ..utils.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=2, delay_seconds=0.01)
        async def failing_function():
            raise ValueError("Function always fails")

        # Test that the decorator properly handles exceptions
        import asyncio

        async def test_decorator():
            with pytest.raises(ValueError, match="Function always fails"):
                await failing_function()

        asyncio.run(test_decorator())
