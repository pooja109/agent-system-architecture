"""
Comprehensive Error Condition Tests
====================================

Complete tests for error conditions, failure scenarios, and exception handling
to ensure robust error handling and proper error propagation.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ..config.settings import AppSettings, GraphAPISettings, OutputSettings, ProcessingSettings
from ..services.email_processor import EmailProcessor
from ..services.graph_api_client import GraphAPIClient
from ..services.monitor import InboxMonitor


class TestErrorConditionsInboxMonitor:
    """Error condition tests for InboxMonitor."""

    @pytest.fixture
    def monitor_settings(self) -> AppSettings:
        """Create settings for error testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(),
            logging={"level": "DEBUG", "format": "json"},
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def monitor(self, monitor_settings: AppSettings) -> InboxMonitor:
        """Create monitor for error testing."""
        return InboxMonitor(monitor_settings)

    @pytest.mark.asyncio
    async def test_start_with_graph_client_initialization_error(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor start when GraphAPIClient initialization fails."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_client.initialize.side_effect = Exception("Graph API initialization failed")
            mock_graph_class.return_value = mock_graph_client

            with pytest.raises(Exception, match="Graph API initialization failed"):
                await monitor.start()

    @pytest.mark.asyncio
    async def test_start_with_email_processor_initialization_error(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor start when EmailProcessor initialization fails."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            with patch(
                "agents.inbox_monitor.services.monitor.EmailProcessor"
            ) as mock_processor_class:
                mock_processor_class.side_effect = Exception(
                    "Email processor initialization failed"
                )

                with pytest.raises(Exception, match="Email processor initialization failed"):
                    await monitor.start()

    @pytest.mark.asyncio
    async def test_start_with_signal_handler_setup_error(self, monitor: InboxMonitor) -> None:
        """Test monitor start when signal handler setup fails."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            with patch(
                "agents.inbox_monitor.services.monitor.EmailProcessor"
            ) as mock_processor_class:
                mock_processor = AsyncMock()
                mock_processor_class.return_value = mock_processor

                with patch("signal.signal", side_effect=OSError("Signal handler setup failed")):
                    # Mock the monitor loop to exit immediately
                    async def mock_monitor_loop():
                        monitor._running = False

                    monitor._monitor_loop = mock_monitor_loop

                    # Should handle signal handler setup failure gracefully
                    await monitor.start()

    @pytest.mark.asyncio
    async def test_monitor_loop_with_processor_initialization_error(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor loop when processor is not initialized."""
        monitor._running = True
        monitor.email_processor = None

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        call_count = 0

        async def mock_wait(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                monitor._running = False
            raise asyncio.TimeoutError()

        monitor._shutdown_event.wait.side_effect = mock_wait

        await monitor._monitor_loop()

        # Should handle None processor gracefully
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_monitor_loop_with_runtime_processor_error(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when processor fails during runtime."""
        monitor._running = True

        # Mock email processor that becomes None during runtime
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = AttributeError("Processor became None")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should stop due to consecutive failures
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_with_system_exit_error(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when SystemExit is raised."""
        monitor._running = True

        # Mock email processor that raises SystemExit
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = SystemExit("System exit requested")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should stop due to SystemExit
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_with_keyboard_interrupt_error(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when KeyboardInterrupt is raised."""
        monitor._running = True

        # Mock email processor that raises KeyboardInterrupt
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = KeyboardInterrupt("Keyboard interrupt")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should stop due to KeyboardInterrupt
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_with_cancelled_error(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when CancelledError is raised."""
        monitor._running = True

        # Mock email processor that raises CancelledError
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = asyncio.CancelledError("Task cancelled")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should stop due to CancelledError
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_with_memory_error(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when MemoryError is raised."""
        monitor._running = True

        # Mock email processor that raises MemoryError
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = MemoryError("Out of memory")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should stop due to MemoryError
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_health_check_with_graph_client_none_error(self, monitor: InboxMonitor) -> None:
        """Test health check when graph client is None."""
        monitor._running = True
        monitor.graph_client = None

        health = await monitor.health_check()

        assert health["status"] == "healthy"  # Still running
        assert health["graph_api_connected"] is False
        assert health["last_error"] is None

    @pytest.mark.asyncio
    async def test_health_check_with_graph_client_attribute_error(
        self, monitor: InboxMonitor
    ) -> None:
        """Test health check when graph client has attribute error."""
        monitor._running = True

        # Mock graph client with attribute error
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.side_effect = AttributeError(
            "'NoneType' object has no attribute 'request'"
        )
        monitor.graph_client = mock_graph_client

        health = await monitor.health_check()

        assert health["status"] == "unhealthy"
        assert health["graph_api_connected"] is False
        assert "AttributeError" in health["last_error"]

    @pytest.mark.asyncio
    async def test_health_check_with_json_decode_error(self, monitor: InboxMonitor) -> None:
        """Test health check when graph client returns invalid JSON."""
        monitor._running = True

        # Mock graph client with JSON decode error
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        monitor.graph_client = mock_graph_client

        health = await monitor.health_check()

        assert health["status"] == "unhealthy"
        assert health["graph_api_connected"] is False
        assert "JSONDecodeError" in health["last_error"]

    @pytest.mark.asyncio
    async def test_stop_with_graph_client_cleanup_timeout(self, monitor: InboxMonitor) -> None:
        """Test monitor stop when graph client cleanup times out."""
        monitor._running = True

        # Mock graph client with cleanup timeout
        mock_graph_client = AsyncMock()
        mock_graph_client.cleanup.side_effect = asyncio.TimeoutError("Cleanup timeout")
        monitor.graph_client = mock_graph_client

        # Should not raise exception
        await monitor.stop()

        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_stop_with_graph_client_cleanup_connection_error(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor stop when graph client cleanup has connection error."""
        monitor._running = True

        # Mock graph client with cleanup connection error
        mock_graph_client = AsyncMock()
        mock_graph_client.cleanup.side_effect = ConnectionError("Connection failed during cleanup")
        monitor.graph_client = mock_graph_client

        # Should not raise exception
        await monitor.stop()

        assert monitor._running is False

    def test_signal_handler_with_asyncio_error(self, monitor: InboxMonitor) -> None:
        """Test signal handler when asyncio.create_task fails."""
        with patch("signal.signal") as mock_signal:
            monitor._setup_signal_handlers()

            # Get the registered handler
            handler = mock_signal.call_args_list[0][0][1]

            # Test handler with asyncio error
            with patch("asyncio.create_task", side_effect=RuntimeError("Event loop error")):
                # Should not raise exception
                handler(2, None)

    def test_signal_handler_with_invalid_frame(self, monitor: InboxMonitor) -> None:
        """Test signal handler with invalid frame parameter."""
        with patch("signal.signal") as mock_signal:
            monitor._setup_signal_handlers()

            # Get the registered handler
            handler = mock_signal.call_args_list[0][0][1]

            # Test handler with invalid frame
            with patch("asyncio.create_task") as mock_create_task:
                handler(2, "invalid_frame")  # Frame should be None or frame object
                mock_create_task.assert_called_once()


class TestErrorConditionsEmailProcessor:
    """Error condition tests for EmailProcessor."""

    @pytest.fixture
    def processor_settings(self) -> AppSettings:
        """Create settings for error testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(),
            logging={"level": "DEBUG", "format": "json"},
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def mock_graph_client(self) -> AsyncMock:
        """Create mock graph client for error testing."""
        mock_client = AsyncMock()
        return mock_client

    @pytest.fixture
    def processor(
        self, processor_settings: AppSettings, mock_graph_client: AsyncMock
    ) -> EmailProcessor:
        """Create processor for error testing."""
        return EmailProcessor(processor_settings, mock_graph_client)

    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_client_none_error(
        self, processor: EmailProcessor
    ) -> None:
        """Test process inbox when graph client is None."""
        processor.graph_client = None

        with pytest.raises(AttributeError):
            await processor.process_inbox()

    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_client_connection_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when graph client has connection error."""
        mock_graph_client.get_inbox_messages.side_effect = ConnectionError("Connection failed")

        result = await processor.process_inbox()

        assert result["success"] is False
        assert "Connection failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_client_timeout_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when graph client times out."""
        mock_graph_client.get_inbox_messages.side_effect = asyncio.TimeoutError("Request timeout")

        result = await processor.process_inbox()

        assert result["success"] is False
        assert "Request timeout" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_client_authentication_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when graph client has authentication error."""
        mock_graph_client.get_inbox_messages.side_effect = Exception(
            "Authentication failed: Invalid credentials"
        )

        result = await processor.process_inbox()

        assert result["success"] is False
        assert "Authentication failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_client_rate_limit_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when graph client hits rate limit."""
        mock_graph_client.get_inbox_messages.side_effect = Exception(
            "Rate limit exceeded: 429 Too Many Requests"
        )

        result = await processor.process_inbox()

        assert result["success"] is False
        assert "Rate limit exceeded" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_folder_creation_permission_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when folder creation has permission error."""
        mock_messages = [{"id": "msg-1", "subject": "Test"}]
        mock_graph_client.get_inbox_messages.return_value = mock_messages
        mock_graph_client.get_folder_by_name.return_value = None

        # Mock retry_operation to fail with permission error
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (False, None, "Permission denied: Insufficient permissions")

            result = await processor.process_inbox()

        assert result["success"] is False
        assert "Failed to create/get processed folder" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_folder_creation_quota_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when folder creation fails due to quota."""
        mock_messages = [{"id": "msg-1", "subject": "Test"}]
        mock_graph_client.get_inbox_messages.return_value = mock_messages
        mock_graph_client.get_folder_by_name.return_value = None

        # Mock retry_operation to fail with quota error
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (False, None, "Quota exceeded: Storage limit reached")

            result = await processor.process_inbox()

        assert result["success"] is False
        assert "Failed to create/get processed folder" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_all_emails_failing_conversion(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when all emails fail conversion."""
        mock_messages = [
            {"id": "msg-1", "subject": "Test 1"},
            {"id": "msg-2", "subject": "Test 2"},
            {"id": "msg-3", "subject": "Test 3"},
        ]
        mock_graph_client.get_inbox_messages.return_value = mock_messages
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock conversion to always fail
        mock_graph_client.convert_to_email_model.side_effect = ValueError("Conversion failed")

        result = await processor.process_inbox()

        assert result["success"] is False
        assert result["processed_count"] == 0
        assert result["failed_count"] == 3
        assert len(result["errors"]) == 3

    @pytest.mark.asyncio
    async def test_process_inbox_with_all_emails_failing_storage(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when all emails fail storage."""
        mock_messages = [{"id": "msg-1", "subject": "Test"}]
        mock_graph_client.get_inbox_messages.return_value = mock_messages
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "msg-1"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock storage to fail
        with patch.object(processor, "_store_email", side_effect=OSError("Storage failed")):
            result = await processor.process_inbox()

        assert result["success"] is False
        assert result["processed_count"] == 0
        assert result["failed_count"] == 1
        assert "Storage failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_all_emails_failing_move(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when all emails fail to move."""
        mock_messages = [{"id": "msg-1", "subject": "Test"}]
        mock_graph_client.get_inbox_messages.return_value = mock_messages
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "msg-1"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock storage success but move failure
        with patch.object(processor, "_store_email", return_value="/tmp/test.json"), patch(
            "agents.inbox_monitor.services.email_processor.retry_operation"
        ) as mock_retry:
            mock_retry.return_value = (False, None, "Move failed: Permission denied")

            result = await processor.process_inbox()

        assert result["success"] is False
        assert result["processed_count"] == 0
        assert result["failed_count"] == 1
        assert "Failed to move email" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_store_email_with_unsupported_storage_type(
        self, processor: EmailProcessor
    ) -> None:
        """Test email storage with unsupported storage type."""
        processor.settings.output.storage_type = "unsupported-type"

        mock_email = Mock()
        mock_email.id = "test-email"

        with pytest.raises(ValueError, match="Unsupported storage type"):
            await processor._store_email(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_file_with_disk_full_error(self, processor: EmailProcessor) -> None:
        """Test file storage when disk is full."""
        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"

        with patch("builtins.open", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError, match="No space left on device"):
                await processor._store_email_file(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_file_with_permission_denied_error(
        self, processor: EmailProcessor
    ) -> None:
        """Test file storage with permission denied."""
        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError, match="Permission denied"):
                await processor._store_email_file(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_file_with_file_not_found_error(
        self, processor: EmailProcessor
    ) -> None:
        """Test file storage with file not found error."""
        processor.settings.output.output_directory = "/nonexistent/path"

        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"

        with patch("builtins.open", side_effect=FileNotFoundError("Directory not found")):
            with pytest.raises(FileNotFoundError, match="Directory not found"):
                await processor._store_email_file(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_file_with_unicode_encode_error(
        self, processor: EmailProcessor
    ) -> None:
        """Test file storage with Unicode encode error."""
        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.to_ai_format.return_value = {"content": "Invalid \udcff content"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"

        with patch(
            "builtins.open",
            side_effect=UnicodeEncodeError("utf-8", "test", 0, 1, "invalid character"),
        ), pytest.raises(UnicodeEncodeError):
            await processor._store_email_file(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_with_missing_endpoint(self, processor: EmailProcessor) -> None:
        """Test API storage without endpoint configuration."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = None

        mock_email = Mock()
        mock_email.id = "test-email"

        with pytest.raises(ValueError, match="API endpoint not configured"):
            await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_with_connection_error(self, processor: EmailProcessor) -> None:
        """Test API storage with connection error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.to_ai_format.return_value = {"id": "test-email"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            with pytest.raises(httpx.ConnectError):
                await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_with_timeout_error(self, processor: EmailProcessor) -> None:
        """Test API storage with timeout error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.to_ai_format.return_value = {"id": "test-email"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                asyncio.TimeoutError("Request timeout")
            )

            with pytest.raises(asyncio.TimeoutError):
                await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_with_client_error(self, processor: EmailProcessor) -> None:
        """Test API storage with client error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.to_ai_format.return_value = {"id": "test-email"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text.return_value = "Bad Request"

            mock_client.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )

            with pytest.raises(Exception, match="API request failed: 400"):
                await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_with_server_error(self, processor: EmailProcessor) -> None:
        """Test API storage with server error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.to_ai_format.return_value = {"id": "test-email"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text.return_value = "Internal Server Error"

            mock_client.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )

            with pytest.raises(Exception, match="API request failed: 500"):
                await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_with_json_decode_error(self, processor: EmailProcessor) -> None:
        """Test API storage with JSON decode error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email"
        mock_email.to_ai_format.return_value = {"id": "test-email"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

            mock_client.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )

            with pytest.raises(json.JSONDecodeError):
                await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_with_graph_api_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test folder creation with Graph API error."""
        mock_graph_client.get_folder_by_name.side_effect = Exception("Graph API error")

        folder = await processor._ensure_processed_folder("Test Folder")

        assert folder is None

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_with_retry_exhaustion(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test folder creation with retry exhaustion."""
        mock_graph_client.get_folder_by_name.return_value = None

        # Mock retry_operation to fail after exhausting retries
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (False, None, "Max retries exceeded")

            folder = await processor._ensure_processed_folder("Test Folder")

            assert folder is None

    @pytest.mark.asyncio
    async def test_process_single_email_with_unexpected_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test single email processing with unexpected error."""
        mock_message = {"id": "msg-1", "subject": "Test"}

        # Mock conversion to raise unexpected error
        mock_graph_client.convert_to_email_model.side_effect = RuntimeError("Unexpected error")

        result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is False
        assert result.message_id == "msg-1"
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_process_single_email_with_system_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test single email processing with system error."""
        mock_message = {"id": "msg-1", "subject": "Test"}

        # Mock conversion to raise system error
        mock_graph_client.convert_to_email_model.side_effect = SystemError("System error")

        result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is False
        assert "SystemError" in result.error

    @pytest.mark.asyncio
    async def test_process_single_email_with_assertion_error(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test single email processing with assertion error."""
        mock_message = {"id": "msg-1", "subject": "Test"}

        # Mock conversion to raise assertion error
        mock_graph_client.convert_to_email_model.side_effect = AssertionError("Assertion failed")

        result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is False
        assert "AssertionError" in result.error


class TestErrorConditionsGraphAPIClient:
    """Error condition tests for GraphAPIClient."""

    @pytest.fixture
    def graph_client(self) -> GraphAPIClient:
        """Create GraphAPIClient for error testing."""
        from ..config.settings import GraphAPISettings

        settings = GraphAPISettings(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            monitored_email="test@example.com",
        )
        return GraphAPIClient(settings)

    def test_init_with_invalid_msal_configuration(self) -> None:
        """Test initialization with invalid MSAL configuration."""
        from ..config.settings import GraphAPISettings

        # Test with invalid tenant ID
        with pytest.raises(Exception):
            settings = GraphAPISettings(
                tenant_id="",  # Empty tenant ID
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            )
            GraphAPIClient(settings)

    @pytest.mark.asyncio
    async def test_initialize_with_session_creation_error(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test initialization when session creation fails."""
        with patch("httpx.AsyncClient", side_effect=Exception("Client creation failed")):
            with pytest.raises(Exception, match="Session creation failed"):
                await graph_client.initialize()

    @pytest.mark.asyncio
    async def test_cleanup_with_session_close_error(self, graph_client: GraphAPIClient) -> None:
        """Test cleanup when session close fails."""
        mock_session = AsyncMock()
        mock_session.close.side_effect = Exception("Session close failed")
        graph_client._client = mock_session

        # Should not raise exception
        await graph_client.cleanup()

        assert graph_client._client is None

    def test_get_access_token_with_invalid_client_credentials(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test token acquisition with invalid client credentials."""
        graph_client.msal_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials",
        }

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    def test_get_access_token_with_invalid_scope(self, graph_client: GraphAPIClient) -> None:
        """Test token acquisition with invalid scope."""
        graph_client.msal_app.acquire_token_for_client.return_value = {
            "error": "invalid_scope",
            "error_description": "Invalid scope",
        }

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    def test_get_access_token_with_network_error(self, graph_client: GraphAPIClient) -> None:
        """Test token acquisition with network error."""
        graph_client.msal_app.acquire_token_for_client.side_effect = ConnectionError(
            "Network error"
        )

        with pytest.raises(ConnectionError):
            graph_client._get_access_token()

    def test_get_access_token_with_timeout_error(self, graph_client: GraphAPIClient) -> None:
        """Test token acquisition with timeout error."""
        graph_client.msal_app.acquire_token_for_client.side_effect = TimeoutError("Timeout error")

        with pytest.raises(TimeoutError):
            graph_client._get_access_token()

    def test_get_access_token_with_malformed_response(self, graph_client: GraphAPIClient) -> None:
        """Test token acquisition with malformed response."""
        graph_client.msal_app.acquire_token_for_client.return_value = {
            "access_token": None,  # Malformed response
            "expires_in": 3600,
        }

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    def test_get_access_token_with_missing_fields(self, graph_client: GraphAPIClient) -> None:
        """Test token acquisition with missing fields."""
        graph_client.msal_app.acquire_token_for_client.return_value = {
            # Missing access_token and expires_in
        }

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    @pytest.mark.asyncio
    async def test_make_request_with_invalid_method(self, graph_client: GraphAPIClient) -> None:
        """Test API request with invalid HTTP method."""
        graph_client._client = AsyncMock()

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception):
                await graph_client._make_request("INVALID_METHOD", "/test")

    @pytest.mark.asyncio
    async def test_make_request_with_invalid_url(self, graph_client: GraphAPIClient) -> None:
        """Test API request with invalid URL."""
        graph_client._client = AsyncMock()
        graph_client._client.request.side_effect = httpx.InvalidURL("Invalid URL")

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(httpx.InvalidURL):
                await graph_client._make_request("GET", "invalid-url")

    @pytest.mark.asyncio
    async def test_make_request_with_ssl_error(self, graph_client: GraphAPIClient) -> None:
        """Test API request with SSL error."""
        graph_client._client = AsyncMock()
        graph_client._client.request.side_effect = httpx.SSLError("SSL error")

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(httpx.SSLError):
                await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_with_payload_too_large(self, graph_client: GraphAPIClient) -> None:
        """Test API request with payload too large."""
        graph_client._client = AsyncMock()

        # Mock 413 Payload Too Large response
        mock_response = AsyncMock()
        mock_response.status = 413
        mock_response.text.return_value = "Payload Too Large"
        graph_client._client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 413"):
                await graph_client._make_request("POST", "/test", data={"large": "data"})

    @pytest.mark.asyncio
    async def test_get_inbox_messages_with_unauthorized_error(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test inbox messages retrieval with unauthorized error."""
        graph_client._client = AsyncMock()

        # Mock 401 Unauthorized response
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text.return_value = "Unauthorized"
        graph_client._client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 401"):
                await graph_client.get_inbox_messages()

    @pytest.mark.asyncio
    async def test_get_inbox_messages_with_forbidden_error(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test inbox messages retrieval with forbidden error."""
        graph_client._client = AsyncMock()

        # Mock 403 Forbidden response
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.text.return_value = "Forbidden"
        graph_client._client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 403"):
                await graph_client.get_inbox_messages()

    @pytest.mark.asyncio
    async def test_create_folder_with_conflict_error(self, graph_client: GraphAPIClient) -> None:
        """Test folder creation with conflict error."""
        graph_client._client = AsyncMock()

        # Mock 409 Conflict response
        mock_response = AsyncMock()
        mock_response.status = 409
        mock_response.text.return_value = "Folder already exists"
        graph_client._client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 409"):
                await graph_client.create_folder("Test Folder")

    @pytest.mark.asyncio
    async def test_move_message_with_not_found_error(self, graph_client: GraphAPIClient) -> None:
        """Test message move with not found error."""
        graph_client._client = AsyncMock()

        # Mock 404 Not Found response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text.return_value = "Message not found"
        graph_client._client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 404"):
                await graph_client.move_message("nonexistent-msg", "folder-id")

    def test_parse_datetime_with_none_value(self, graph_client: GraphAPIClient) -> None:
        """Test datetime parsing with None value."""
        with pytest.raises(ValueError):
            graph_client._parse_datetime(None)

    def test_parse_datetime_with_empty_string(self, graph_client: GraphAPIClient) -> None:
        """Test datetime parsing with empty string."""
        with pytest.raises(ValueError):
            graph_client._parse_datetime("")

    def test_parse_datetime_with_invalid_format(self, graph_client: GraphAPIClient) -> None:
        """Test datetime parsing with invalid format."""
        with pytest.raises(ValueError):
            graph_client._parse_datetime("2024-01-15 10:30:00")  # Missing 'T' and 'Z'

    def test_convert_to_email_model_with_none_message(self, graph_client: GraphAPIClient) -> None:
        """Test email model conversion with None message."""
        with pytest.raises(TypeError):
            graph_client.convert_to_email_model(None, "proc-123", "1.0.0")

    def test_convert_to_email_model_with_empty_message(self, graph_client: GraphAPIClient) -> None:
        """Test email model conversion with empty message."""
        with pytest.raises(KeyError):
            graph_client.convert_to_email_model({}, "proc-123", "1.0.0")

    def test_convert_to_email_model_with_invalid_processing_id(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test email model conversion with invalid processing ID."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
        }

        with pytest.raises(Exception):
            graph_client.convert_to_email_model(graph_message, None, "1.0.0")

    def test_convert_to_email_model_with_invalid_version(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test email model conversion with invalid version."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
        }

        with pytest.raises(Exception):
            graph_client.convert_to_email_model(graph_message, "proc-123", None)
