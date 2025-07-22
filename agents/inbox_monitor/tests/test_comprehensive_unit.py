"""
Comprehensive Unit Tests for Inbox Monitor
============================================

Complete unit tests for all public methods with 90%+ coverage.
Follows enterprise Python testing standards.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from ..config.settings import (
    AppSettings,
    GraphAPISettings,
    LoggingSettings,
    OutputSettings,
    ProcessingSettings,
)
from ..services.email_processor import EmailProcessor
from ..services.monitor import InboxMonitor


class TestInboxMonitorUnit:
    """Comprehensive unit tests for InboxMonitor class."""

    @pytest.fixture
    def mock_settings(self) -> AppSettings:
        """Create mock application settings."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                polling_interval_seconds=300,
                batch_size=10,
                max_retry_attempts=3,
                retry_delay_seconds=30,
            ),
            logging=LoggingSettings(level="INFO", format="json"),
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def monitor(self, mock_settings: AppSettings) -> InboxMonitor:
        """Create InboxMonitor instance."""
        return InboxMonitor(mock_settings)

    def test_init_monitor_with_valid_settings(self, mock_settings: AppSettings) -> None:
        """Test monitor initialization with valid settings."""
        monitor = InboxMonitor(mock_settings)

        assert monitor.settings == mock_settings
        assert monitor._running is False
        assert monitor._shutdown_event is not None
        assert monitor.graph_client is None
        assert monitor.email_processor is None
        assert monitor.logger is not None

    def test_init_monitor_with_different_environments(self) -> None:
        """Test monitor initialization with different environment settings."""
        environments = ["development", "staging", "production", "test"]

        for env in environments:
            settings = AppSettings(
                graph_api=GraphAPISettings(
                    tenant_id="test-tenant-id",
                    client_id="test-client-id",
                    client_secret="test-client-secret",
                    monitored_email="test@example.com",
                ),
                processing=ProcessingSettings(),
                logging=LoggingSettings(),
                output=OutputSettings(),
                environment=env,
                dry_run=False,
            )

            monitor = InboxMonitor(settings)
            assert monitor.settings.environment == env

    @pytest.mark.asyncio
    async def test_start_monitor_success(self, monitor: InboxMonitor) -> None:
        """Test successful monitor start."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            with patch(
                "agents.inbox_monitor.services.monitor.EmailProcessor"
            ) as mock_processor_class:
                mock_processor = AsyncMock()
                mock_processor_class.return_value = mock_processor

                # Mock the monitor loop to exit immediately
                async def mock_monitor_loop():
                    monitor._running = False

                monitor._monitor_loop = mock_monitor_loop

                await monitor.start()

                # Verify initialization
                mock_graph_client.initialize.assert_called_once()
                mock_processor_class.assert_called_once_with(monitor.settings, mock_graph_client)
                assert monitor.graph_client == mock_graph_client
                assert monitor.email_processor == mock_processor

    @pytest.mark.asyncio
    async def test_start_monitor_with_graph_client_failure(self, monitor: InboxMonitor) -> None:
        """Test monitor start when GraphAPIClient initialization fails."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_client.initialize.side_effect = Exception("Graph API initialization failed")
            mock_graph_class.return_value = mock_graph_client

            with pytest.raises(Exception, match="Graph API initialization failed"):
                await monitor.start()

    @pytest.mark.asyncio
    async def test_stop_monitor_success(self, monitor: InboxMonitor) -> None:
        """Test successful monitor stop."""
        monitor._running = True

        # Mock graph client
        mock_graph_client = AsyncMock()
        monitor.graph_client = mock_graph_client

        await monitor.stop()

        assert monitor._running is False
        assert monitor._shutdown_event.is_set()
        mock_graph_client.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_monitor_with_cleanup_failure(self, monitor: InboxMonitor) -> None:
        """Test monitor stop when cleanup fails."""
        monitor._running = True

        # Mock graph client with cleanup failure
        mock_graph_client = AsyncMock()
        mock_graph_client.cleanup.side_effect = Exception("Cleanup failed")
        monitor.graph_client = mock_graph_client

        # Should not raise exception
        await monitor.stop()

        assert monitor._running is False
        assert monitor._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_monitor_without_graph_client(self, monitor: InboxMonitor) -> None:
        """Test monitor stop when graph_client is None."""
        monitor._running = True
        monitor.graph_client = None

        await monitor.stop()

        assert monitor._running is False
        assert monitor._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_monitor_loop_single_iteration_success(self, monitor: InboxMonitor) -> None:
        """Test monitor loop single iteration with success."""
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

        # Mock shutdown event to trigger after one iteration
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

        # Verify processing was called
        mock_processor.process_inbox.assert_called_once()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_monitor_loop_consecutive_failures(self, monitor: InboxMonitor) -> None:
        """Test monitor loop with consecutive failures leading to shutdown."""
        monitor._running = True

        # Mock email processor to always fail
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": False,
            "processed_count": 0,
            "failed_count": 5,
            "errors": ["Processing failed"],
            "processing_time_seconds": 1.0,
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
    async def test_monitor_loop_exception_handling(self, monitor: InboxMonitor) -> None:
        """Test monitor loop exception handling."""
        monitor._running = True

        # Mock email processor to raise exception
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = RuntimeError("Unexpected error")
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
    async def test_monitor_loop_shutdown_during_wait(self, monitor: InboxMonitor) -> None:
        """Test monitor loop shutdown during wait period."""
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

    @pytest.mark.asyncio
    async def test_monitor_loop_with_zero_sleep_time(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when processing takes longer than polling interval."""
        monitor.settings.processing.polling_interval_seconds = 1
        monitor._running = True

        # Mock email processor with slow processing
        mock_processor = AsyncMock()

        async def slow_process():
            await asyncio.sleep(0.1)  # Simulate processing time longer than interval
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 2.0,  # Longer than polling interval
            }

        mock_processor.process_inbox.side_effect = slow_process
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()

        call_count = 0

        async def mock_wait(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                monitor._running = False
            return

        monitor._shutdown_event.wait.side_effect = mock_wait

        await monitor._monitor_loop()

        # Should have processed without additional delay
        mock_processor.process_inbox.assert_called_once()

    def test_setup_signal_handlers(self, monitor: InboxMonitor) -> None:
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

    def test_setup_signal_handlers_with_different_signals(self, monitor: InboxMonitor) -> None:
        """Test signal handler setup with different signal types."""
        with patch("signal.signal") as mock_signal:
            monitor._setup_signal_handlers()

            # Get the registered handler
            handler = mock_signal.call_args_list[0][0][1]

            # Test handler with different signal numbers
            with patch("asyncio.create_task") as mock_create_task:
                handler(15, None)  # SIGTERM
                mock_create_task.assert_called_once()

                mock_create_task.reset_mock()
                handler(2, None)  # SIGINT
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, monitor: InboxMonitor) -> None:
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
        assert isinstance(health["timestamp"], str)

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, monitor: InboxMonitor) -> None:
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
        assert "timestamp" in health

    @pytest.mark.asyncio
    async def test_health_check_stopped(self, monitor: InboxMonitor) -> None:
        """Test health check when service is stopped."""
        monitor._running = False
        monitor.graph_client = None

        health = await monitor.health_check()

        assert health["status"] == "stopped"
        assert health["graph_api_connected"] is False
        assert health["last_error"] is None

    @pytest.mark.asyncio
    async def test_health_check_with_graph_client_timeout(self, monitor: InboxMonitor) -> None:
        """Test health check with Graph API timeout."""
        monitor._running = True

        # Mock graph client with timeout
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.side_effect = asyncio.TimeoutError("Request timeout")
        monitor.graph_client = mock_graph_client

        health = await monitor.health_check()

        assert health["status"] == "unhealthy"
        assert health["graph_api_connected"] is False
        assert "Request timeout" in health["last_error"]

    @pytest.mark.asyncio
    async def test_health_check_with_none_graph_client(self, monitor: InboxMonitor) -> None:
        """Test health check when graph_client is None."""
        monitor._running = True
        monitor.graph_client = None

        health = await monitor.health_check()

        assert health["status"] == "healthy"  # Still running
        assert health["graph_api_connected"] is False
        assert health["last_error"] is None

    @pytest.mark.asyncio
    async def test_monitor_loop_with_mixed_results(self, monitor: InboxMonitor) -> None:
        """Test monitor loop with mixed success and failure results."""
        monitor._running = True

        # Mock email processor with mixed results
        mock_processor = AsyncMock()
        results = [
            {"success": True, "processed_count": 3, "failed_count": 0, "errors": []},
            {
                "success": False,
                "processed_count": 1,
                "failed_count": 2,
                "errors": ["Error 1", "Error 2"],
            },
            {"success": True, "processed_count": 2, "failed_count": 0, "errors": []},
        ]

        call_count = 0

        def get_result():
            nonlocal call_count
            if call_count < len(results):
                result = results[call_count]
                call_count += 1
                return result
            monitor._running = False
            return {"success": True, "processed_count": 0, "failed_count": 0, "errors": []}

        mock_processor.process_inbox.side_effect = get_result
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        await monitor._monitor_loop()

        # Should have processed multiple times
        assert mock_processor.process_inbox.call_count >= 3
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_processing_time_calculation(self, monitor: InboxMonitor) -> None:
        """Test monitor loop processing time calculation and sleep adjustment."""
        monitor.settings.processing.polling_interval_seconds = 10
        monitor._running = True

        # Mock email processor with known processing time
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": True,
            "processed_count": 1,
            "failed_count": 0,
            "errors": [],
            "processing_time_seconds": 5.0,
        }
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()

        wait_times = []

        async def capture_wait_time(*args, **kwargs):
            if "timeout" in kwargs:
                wait_times.append(kwargs["timeout"])
            monitor._running = False
            raise asyncio.TimeoutError()

        monitor._shutdown_event.wait.side_effect = capture_wait_time

        await monitor._monitor_loop()

        # Should have calculated proper sleep time
        assert len(wait_times) > 0
        # Sleep time should be less than polling interval due to processing time
        assert wait_times[0] < monitor.settings.processing.polling_interval_seconds

    @pytest.mark.asyncio
    async def test_monitor_loop_with_email_processor_none(self, monitor: InboxMonitor) -> None:
        """Test monitor loop when email processor is None."""
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

        # Should have handled None processor gracefully
        assert call_count == 1
        assert monitor._running is False


class TestEmailProcessorUnit:
    """Comprehensive unit tests for EmailProcessor class."""

    @pytest.fixture
    def mock_settings(self) -> AppSettings:
        """Create mock application settings."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                polling_interval_seconds=300,
                batch_size=10,
                max_retry_attempts=3,
                retry_delay_seconds=30,
            ),
            logging=LoggingSettings(level="INFO", format="json"),
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def mock_graph_client(self) -> AsyncMock:
        """Create mock Graph API client."""
        mock_client = AsyncMock()
        mock_client.get_inbox_messages.return_value = []
        mock_client.get_folder_by_name.return_value = None
        mock_client.create_folder.return_value = {
            "id": "test-folder-id",
            "displayName": "Test Folder",
        }
        mock_client.move_message.return_value = {"id": "test-message-id"}
        mock_client.convert_to_email_model.return_value = Mock()
        return mock_client

    @pytest.fixture
    def processor(self, mock_settings: AppSettings, mock_graph_client: AsyncMock) -> EmailProcessor:
        """Create EmailProcessor instance."""
        return EmailProcessor(mock_settings, mock_graph_client)

    def test_init_processor_with_file_storage(
        self, mock_settings: AppSettings, mock_graph_client: AsyncMock
    ) -> None:
        """Test processor initialization with file storage."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            processor = EmailProcessor(mock_settings, mock_graph_client)

            assert processor.settings == mock_settings
            assert processor.graph_client == mock_graph_client
            assert processor.version == "2.0.0"
            assert processor.logger is not None
            assert processor.scenario_processor is not None
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_init_processor_with_api_storage(self, mock_graph_client: AsyncMock) -> None:
        """Test processor initialization with API storage."""
        settings = AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(),
            logging=LoggingSettings(),
            output=OutputSettings(storage_type="api", api_endpoint="https://api.example.com"),
            environment="test",
            dry_run=False,
        )

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            processor = EmailProcessor(settings, mock_graph_client)

            assert processor.settings.output.storage_type == "api"
            # Should not create directory for API storage
            mock_mkdir.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_inbox_no_messages(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when no messages are available."""
        mock_graph_client.get_inbox_messages.return_value = []

        result = await processor.process_inbox()

        assert result["success"] is True
        assert result["processed_count"] == 0
        assert result["failed_count"] == 0
        assert result["errors"] == []
        assert result["processing_results"] == []

    @pytest.mark.asyncio
    async def test_process_inbox_with_messages(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox with messages."""
        # Mock messages
        mock_messages = [
            {"id": "msg-1", "subject": "Test 1"},
            {"id": "msg-2", "subject": "Test 2"},
        ]
        mock_graph_client.get_inbox_messages.return_value = mock_messages

        # Mock folder
        mock_folder = {"id": "folder-id", "displayName": "Processed_01_2024"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "test-email-id"
        mock_email.to_ai_format.return_value = {"id": "test-email-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock file storage
        with patch("builtins.open", mock_open()):
            with patch.object(processor, "_store_email", return_value="/tmp/test.json"):
                result = await processor.process_inbox()

        assert result["success"] is True
        assert result["processed_count"] == 2
        assert result["failed_count"] == 0
        assert len(result["processing_results"]) == 2

    @pytest.mark.asyncio
    async def test_process_inbox_folder_creation_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when folder creation fails."""
        mock_messages = [{"id": "msg-1", "subject": "Test 1"}]
        mock_graph_client.get_inbox_messages.return_value = mock_messages
        mock_graph_client.get_folder_by_name.return_value = None

        # Mock retry_operation to fail
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (False, None, "Folder creation failed")

            result = await processor.process_inbox()

        assert result["success"] is False
        assert result["processed_count"] == 0
        assert result["failed_count"] == 0
        assert "Failed to create/get processed folder" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_graph_api_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test process inbox when Graph API fails."""
        mock_graph_client.get_inbox_messages.side_effect = Exception("Graph API error")

        result = await processor.process_inbox()

        assert result["success"] is False
        assert result["processed_count"] == 0
        assert result["failed_count"] == 0
        assert "Graph API error" in result["errors"][0]

    def test_get_processed_folder_name(self, processor: EmailProcessor) -> None:
        """Test processed folder name generation."""
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.side_effect = ["03", "2024"]

            folder_name = processor._get_processed_folder_name()

            assert folder_name == "Processed_03_2024"
            assert mock_datetime.utcnow.return_value.strftime.call_count == 2

    def test_get_processed_folder_name_different_months(self, processor: EmailProcessor) -> None:
        """Test processed folder name generation for different months."""
        test_cases = [
            (["01", "2024"], "Processed_01_2024"),
            (["12", "2024"], "Processed_12_2024"),
            (["06", "2025"], "Processed_06_2025"),
        ]

        for strftime_returns, expected in test_cases:
            with patch("datetime.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value.strftime.side_effect = strftime_returns

                folder_name = processor._get_processed_folder_name()

                assert folder_name == expected

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_exists(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test ensure processed folder when folder exists."""
        mock_folder = {"id": "existing-folder-id", "displayName": "Processed_01_2024"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        result = await processor._ensure_processed_folder("Processed_01_2024")

        assert result == mock_folder
        mock_graph_client.get_folder_by_name.assert_called_once_with("Processed_01_2024")
        mock_graph_client.create_folder.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_create_new(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test ensure processed folder when folder needs to be created."""
        mock_graph_client.get_folder_by_name.return_value = None
        mock_new_folder = {"id": "new-folder-id", "displayName": "Processed_01_2024"}

        # Mock retry_operation to succeed
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (True, mock_new_folder, None)

            result = await processor._ensure_processed_folder("Processed_01_2024")

        assert result == mock_new_folder
        mock_graph_client.get_folder_by_name.assert_called_once_with("Processed_01_2024")

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_creation_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test ensure processed folder when creation fails."""
        mock_graph_client.get_folder_by_name.return_value = None

        # Mock retry_operation to fail
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (False, None, "Creation failed")

            result = await processor._ensure_processed_folder("Processed_01_2024")

        assert result is None

    @pytest.mark.asyncio
    async def test_process_single_email_success(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test successful single email processing."""
        mock_message = {"id": "msg-1", "subject": "Test Email"}

        # Mock email model
        mock_email = Mock()
        mock_email.id = "msg-1"
        mock_email.to_ai_format.return_value = {"id": "msg-1", "subject": "Test Email"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-id-1"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock storage and move
        with patch.object(processor, "_store_email", return_value="/tmp/test.json"), patch(
            "agents.inbox_monitor.services.email_processor.retry_operation"
        ) as mock_retry:
            mock_retry.return_value = (True, {"id": "msg-1"}, None)

            result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is True
        assert result.message_id == "msg-1"
        assert result.processing_id == "proc-id-1"
        assert result.stored_path == "/tmp/test.json"
        assert result.moved_to_folder == "Test Folder"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_process_single_email_conversion_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test single email processing with conversion failure."""
        mock_message = {"id": "msg-1", "subject": "Test Email"}
        mock_graph_client.convert_to_email_model.side_effect = ValueError("Conversion failed")

        result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is False
        assert result.message_id == "msg-1"
        assert result.processing_id is None
        assert result.stored_path is None
        assert result.moved_to_folder is None
        assert "Conversion failed" in result.error

    @pytest.mark.asyncio
    async def test_process_single_email_storage_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test single email processing with storage failure."""
        mock_message = {"id": "msg-1", "subject": "Test Email"}

        # Mock email model
        mock_email = Mock()
        mock_email.id = "msg-1"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-id-1"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock storage to fail
        with patch.object(processor, "_store_email", side_effect=OSError("Storage failed")):
            result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is False
        assert result.message_id == "msg-1"
        assert result.processing_id == "proc-id-1"
        assert result.stored_path is None
        assert result.moved_to_folder is None
        assert "Storage failed" in result.error

    @pytest.mark.asyncio
    async def test_process_single_email_move_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test single email processing with move failure."""
        mock_message = {"id": "msg-1", "subject": "Test Email"}

        # Mock email model
        mock_email = Mock()
        mock_email.id = "msg-1"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-id-1"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock storage success but move failure
        with patch.object(processor, "_store_email", return_value="/tmp/test.json"), patch(
            "agents.inbox_monitor.services.email_processor.retry_operation"
        ) as mock_retry:
            mock_retry.return_value = (False, None, "Move failed")

            result = await processor._process_single_email(mock_message, "folder-id", "Test Folder")

        assert result.success is False
        assert result.message_id == "msg-1"
        assert result.processing_id == "proc-id-1"
        assert result.stored_path == "/tmp/test.json"
        assert result.moved_to_folder is None
        assert "Failed to move email: Move failed" in result.error

    @pytest.mark.asyncio
    async def test_store_email_file_success(self, processor: EmailProcessor) -> None:
        """Test successful file storage."""
        mock_email = Mock()
        mock_email.id = "test-email-id"
        mock_email.to_ai_format.return_value = {"id": "test-email-id", "subject": "Test"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-id"

        with patch("builtins.open", mock_open()) as mock_file:
            with patch("json.dump") as mock_json_dump:
                result = await processor._store_email_file(mock_email)

        assert result is not None
        assert result.endswith("test-email-id_proc-id.json")
        mock_file.assert_called_once()
        mock_json_dump.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_email_file_permission_error(self, processor: EmailProcessor) -> None:
        """Test file storage with permission error."""
        mock_email = Mock()
        mock_email.id = "test-email-id"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-id"

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                await processor._store_email_file(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_success(self, processor: EmailProcessor) -> None:
        """Test successful API storage."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email-id"
        mock_email.to_ai_format.return_value = {"id": "test-email-id", "subject": "Test"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"id": "api-id", "status": "stored"}

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )
            mock_client_class.return_value = mock_client

            result = await processor._store_email_api(mock_email)

        assert result == "https://api.example.com/emails/api-id"

    @pytest.mark.asyncio
    async def test_store_email_api_server_error(self, processor: EmailProcessor) -> None:
        """Test API storage with server error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_email = Mock()
        mock_email.id = "test-email-id"
        mock_email.to_ai_format.return_value = {"id": "test-email-id"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text.return_value = "Internal Server Error"

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception, match="API request failed: 500"):
                await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_without_endpoint(self, processor: EmailProcessor) -> None:
        """Test API storage without endpoint configuration."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = None

        mock_email = Mock()

        with pytest.raises(ValueError, match="API endpoint not configured"):
            await processor._store_email_api(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_invalid_storage_type(self, processor: EmailProcessor) -> None:
        """Test email storage with invalid storage type."""
        processor.settings.output.storage_type = "invalid-type"

        mock_email = Mock()

        with pytest.raises(ValueError, match="Unsupported storage type"):
            await processor._store_email(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_file_type(self, processor: EmailProcessor) -> None:
        """Test email storage with file type."""
        processor.settings.output.storage_type = "file"

        mock_email = Mock()

        with patch.object(
            processor, "_store_email_file", return_value="/tmp/test.json"
        ) as mock_store:
            result = await processor._store_email(mock_email)

        assert result == "/tmp/test.json"
        mock_store.assert_called_once_with(mock_email)

    @pytest.mark.asyncio
    async def test_store_email_api_type(self, processor: EmailProcessor) -> None:
        """Test email storage with API type."""
        processor.settings.output.storage_type = "api"

        mock_email = Mock()

        with patch.object(
            processor, "_store_email_api", return_value="https://api.example.com/1"
        ) as mock_store:
            result = await processor._store_email(mock_email)

        assert result == "https://api.example.com/1"
        mock_store.assert_called_once_with(mock_email)
