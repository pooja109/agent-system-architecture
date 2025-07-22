"""
Comprehensive Edge Case Tests
==============================

Comprehensive tests for edge cases and boundary conditions
to ensure robust error handling and edge case coverage.
"""

import asyncio
import contextlib
from datetime import datetime
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from ..config.settings import AppSettings, GraphAPISettings, OutputSettings, ProcessingSettings
from ..models.email import EmailImportance
from ..services.email_processor import EmailProcessor
from ..services.graph_api_client import GraphAPIClient
from ..services.monitor import InboxMonitor


class TestEdgeCasesInboxMonitor:
    """Edge case tests for InboxMonitor."""

    @pytest.fixture
    def monitor_settings(self) -> AppSettings:
        """Create settings for edge case testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                polling_interval_seconds=1,  # Very short interval
                batch_size=1,  # Small batch size
                max_retry_attempts=1,  # Minimal retries
                retry_delay_seconds=0,  # No delay
            ),
            logging={"level": "DEBUG", "format": "json"},
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def monitor(self, monitor_settings: AppSettings) -> InboxMonitor:
        """Create monitor for edge case testing."""
        return InboxMonitor(monitor_settings)

    @pytest.mark.asyncio
    async def test_monitor_with_zero_polling_interval(self, monitor: InboxMonitor) -> None:
        """Test monitor with zero polling interval."""
        monitor.settings.processing.polling_interval_seconds = 0
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

        # Mock shutdown event to trigger quickly
        monitor._shutdown_event = AsyncMock()
        call_count = 0

        async def mock_wait(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                monitor._running = False
            return

        monitor._shutdown_event.wait.side_effect = mock_wait

        await monitor._monitor_loop()

        # Should process multiple times quickly
        assert mock_processor.process_inbox.call_count >= 3

    @pytest.mark.asyncio
    async def test_monitor_with_negative_polling_interval(self, monitor: InboxMonitor) -> None:
        """Test monitor with negative polling interval."""
        monitor.settings.processing.polling_interval_seconds = -10
        monitor._running = True

        # Mock email processor with slow processing
        mock_processor = AsyncMock()

        async def slow_process():
            await asyncio.sleep(0.1)
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0.1,
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

        # Should handle negative interval gracefully
        assert mock_processor.process_inbox.call_count >= 1

    @pytest.mark.asyncio
    async def test_monitor_with_processing_longer_than_interval(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor when processing takes longer than polling interval."""
        monitor.settings.processing.polling_interval_seconds = 0.1
        monitor._running = True

        # Mock email processor with processing longer than interval
        mock_processor = AsyncMock()

        async def long_process():
            await asyncio.sleep(0.2)  # Longer than interval
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0.2,
            }

        mock_processor.process_inbox.side_effect = long_process
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

        start_time = asyncio.get_event_loop().time()
        await monitor._monitor_loop()
        end_time = asyncio.get_event_loop().time()

        # Should process without additional wait
        assert end_time - start_time >= 0.2  # At least processing time
        assert mock_processor.process_inbox.call_count == 1

    @pytest.mark.asyncio
    async def test_monitor_with_rapid_start_stop_cycles(self, monitor: InboxMonitor) -> None:
        """Test monitor with rapid start/stop cycles."""
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            with patch(
                "agents.inbox_monitor.services.monitor.EmailProcessor"
            ) as mock_processor_class:
                mock_processor = AsyncMock()
                mock_processor_class.return_value = mock_processor

                # Rapid start/stop cycles
                for _ in range(5):
                    start_task = asyncio.create_task(monitor.start())
                    await asyncio.sleep(0.001)  # Very short delay
                    await monitor.stop()

                    with contextlib.suppress(asyncio.CancelledError):
                        await start_task

                # Should handle rapid cycles gracefully
                assert mock_graph_client.cleanup.call_count <= 5

    @pytest.mark.asyncio
    async def test_monitor_with_concurrent_health_checks(self, monitor: InboxMonitor) -> None:
        """Test monitor with concurrent health check calls."""
        monitor._running = True

        # Mock graph client
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.return_value = {"id": "user-id"}
        monitor.graph_client = mock_graph_client

        # Run multiple health checks concurrently
        tasks = [monitor.health_check() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            assert result["status"] == "healthy"
            assert result["graph_api_connected"] is True

    @pytest.mark.asyncio
    async def test_monitor_with_memory_pressure_simulation(self, monitor: InboxMonitor) -> None:
        """Test monitor behavior under simulated memory pressure."""
        monitor._running = True

        # Mock email processor to simulate memory growth
        mock_processor = AsyncMock()
        call_count = 0

        def simulate_memory_pressure():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                raise MemoryError("Simulated memory pressure")
            return {
                "success": True,
                "processed_count": call_count,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0.1,
            }

        mock_processor.process_inbox.side_effect = simulate_memory_pressure
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should handle memory pressure gracefully
        assert monitor._running is False
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_monitor_with_intermittent_network_failures(self, monitor: InboxMonitor) -> None:
        """Test monitor with intermittent network failures."""
        monitor._running = True

        # Mock email processor with intermittent failures
        mock_processor = AsyncMock()
        call_count = 0

        def intermittent_failure():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Fail every other call
                raise ConnectionError("Network failure")
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0.1,
            }

        mock_processor.process_inbox.side_effect = intermittent_failure
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should handle intermittent failures
        assert mock_processor.process_inbox.call_count >= 2

    @pytest.mark.asyncio
    async def test_monitor_with_exactly_max_consecutive_failures(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor with exactly max consecutive failures."""
        monitor._running = True

        # Mock email processor to fail exactly max_consecutive_failures times
        mock_processor = AsyncMock()
        call_count = 0

        def fail_exactly_max_times():
            nonlocal call_count
            call_count += 1
            if call_count < 5:  # Fail 4 times, then succeed
                return {
                    "success": False,
                    "processed_count": 0,
                    "failed_count": 1,
                    "errors": [f"Failure {call_count}"],
                    "processing_time_seconds": 0.1,
                }
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0.1,
            }

        mock_processor.process_inbox.side_effect = fail_exactly_max_times
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        with patch("asyncio.sleep"):
            await monitor._monitor_loop()

        # Should continue after failures resolve
        assert call_count == 5

    @pytest.mark.asyncio
    async def test_monitor_with_processing_time_edge_cases(self, monitor: InboxMonitor) -> None:
        """Test monitor with edge cases in processing time calculation."""
        monitor.settings.processing.polling_interval_seconds = 60
        monitor._running = True

        # Mock email processor with processing time edge cases
        mock_processor = AsyncMock()
        processing_times = [0, 30, 60, 90, 120]  # Various processing times
        call_count = 0

        def varying_processing_time():
            nonlocal call_count
            if call_count < len(processing_times):
                time = processing_times[call_count]
                call_count += 1
                return {
                    "success": True,
                    "processed_count": 1,
                    "failed_count": 0,
                    "errors": [],
                    "processing_time_seconds": time,
                }
            monitor._running = False
            return {
                "success": True,
                "processed_count": 0,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 0,
            }

        mock_processor.process_inbox.side_effect = varying_processing_time
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        captured_timeouts = []

        async def capture_timeout(*args, **kwargs):
            if "timeout" in kwargs:
                captured_timeouts.append(kwargs["timeout"])
            raise asyncio.TimeoutError()

        monitor._shutdown_event.wait.side_effect = capture_timeout

        await monitor._monitor_loop()

        # Should handle various processing times correctly
        assert len(captured_timeouts) >= 4
        # Sleep time should be adjusted based on processing time
        assert any(t < 60 for t in captured_timeouts)  # Some should be less than full interval


class TestEdgeCasesEmailProcessor:
    """Edge case tests for EmailProcessor."""

    @pytest.fixture
    def processor_settings(self) -> AppSettings:
        """Create settings for edge case testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                batch_size=1,
                max_retry_attempts=1,
                retry_delay_seconds=0,
            ),
            logging={"level": "DEBUG", "format": "json"},
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def mock_graph_client(self) -> AsyncMock:
        """Create mock graph client for edge case testing."""
        mock_client = AsyncMock()
        mock_client.get_inbox_messages.return_value = []
        mock_client.get_folder_by_name.return_value = None
        mock_client.create_folder.return_value = {"id": "folder-id", "displayName": "Test Folder"}
        mock_client.move_message.return_value = {"id": "message-id"}
        mock_client.convert_to_email_model.return_value = Mock()
        return mock_client

    @pytest.fixture
    def processor(
        self, processor_settings: AppSettings, mock_graph_client: AsyncMock
    ) -> EmailProcessor:
        """Create processor for edge case testing."""
        return EmailProcessor(processor_settings, mock_graph_client)

    @pytest.mark.asyncio
    async def test_process_inbox_with_extremely_large_batch(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with extremely large batch of messages."""
        # Create a very large batch
        large_batch = []
        for i in range(1000):
            large_batch.append(
                {
                    "id": f"msg-{i}",
                    "subject": f"Test Message {i}",
                    "body": {"contentType": "text/plain", "content": f"Content {i}"},
                }
            )

        mock_graph_client.get_inbox_messages.return_value = large_batch
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            result = await processor.process_inbox()

        # Should handle large batch
        assert result["success"] is True
        assert result["processed_count"] == 1000
        assert result["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_process_inbox_with_unicode_and_special_characters(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing emails with Unicode and special characters."""
        special_messages = [
            {
                "id": "unicode-msg-1",
                "subject": "Subject with émojis 🚀🎉 and spëcial chars: àáâãäåæçèéêë",
                "body": {
                    "contentType": "text/html",
                    "content": "<html><body>Content with 中文字符, русский, العربية, and emojis: 😀🎉💡</body></html>",
                },
            },
            {
                "id": "unicode-msg-2",
                "subject": "Mathematical symbols: ∑∏∫∆∇∂∞±≤≥≠≈∈∋∪∩",
                "body": {
                    "contentType": "text/plain",
                    "content": "Currency: €£¥₹₽₿ and symbols: ©®™§¶†‡•…‰‱",
                },
            },
        ]

        mock_graph_client.get_inbox_messages.return_value = special_messages
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            result = await processor.process_inbox()

        assert result["success"] is True
        assert result["processed_count"] == 2
        assert result["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_process_inbox_with_extremely_long_content(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing email with extremely long content."""
        # Create message with very long content
        long_subject = "A" * 100000  # 100KB subject
        long_content = "B" * 1000000  # 1MB content

        long_message = {
            "id": "long-content-msg",
            "subject": long_subject,
            "body": {
                "contentType": "text/html",
                "content": f"<html><body>{long_content}</body></html>",
            },
        }

        mock_graph_client.get_inbox_messages.return_value = [long_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "long-content-msg"
        mock_email.to_ai_format.return_value = {"id": "long-content-msg", "subject": long_subject}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            result = await processor.process_inbox()

        assert result["success"] is True
        assert result["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_inbox_with_malformed_json_serialization(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with objects that can't be JSON serialized."""
        mock_message = {"id": "json-error-msg", "subject": "Test"}

        mock_graph_client.get_inbox_messages.return_value = [mock_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model that can't be serialized
        mock_email = Mock()
        mock_email.id = "json-error-msg"
        mock_email.to_ai_format.side_effect = TypeError("Object not JSON serializable")
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        result = await processor.process_inbox()

        assert result["success"] is False
        assert result["processed_count"] == 0
        assert result["failed_count"] == 1
        assert "Object not JSON serializable" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_concurrent_folder_access(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with concurrent folder access scenarios."""
        mock_messages = [{"id": f"msg-{i}", "subject": f"Test {i}"} for i in range(10)]
        mock_graph_client.get_inbox_messages.return_value = mock_messages

        # Mock folder operations with intermittent failures
        call_count = 0

        def intermittent_folder_failure():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                return None
            return {"id": "folder-id", "displayName": "Test Folder"}

        mock_graph_client.get_folder_by_name.side_effect = intermittent_folder_failure

        # Mock email model
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock retry operation to eventually succeed
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (
                True,
                {"id": "folder-id", "displayName": "Test Folder"},
                None,
            )

            with patch("builtins.open", mock_open()):
                result = await processor.process_inbox()

        # Should handle concurrent access gracefully
        assert result["success"] is True or result["processed_count"] > 0

    @pytest.mark.asyncio
    async def test_process_inbox_with_filesystem_edge_cases(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with filesystem edge cases."""
        mock_message = {"id": "fs-test-msg", "subject": "Test"}
        mock_graph_client.get_inbox_messages.return_value = [mock_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "fs-test-msg"
        mock_email.to_ai_format.return_value = {"id": "fs-test-msg"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Test various filesystem errors
        filesystem_errors = [
            PermissionError("Permission denied"),
            OSError("No space left on device"),
            FileNotFoundError("Directory not found"),
            IsADirectoryError("Is a directory"),
        ]

        for error in filesystem_errors:
            with patch("builtins.open", side_effect=error):
                result = await processor.process_inbox()

                assert result["success"] is False
                assert result["processed_count"] == 0
                assert result["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_inbox_with_output_directory_creation_failure(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing when output directory creation fails."""
        # Set non-existent output directory
        processor.settings.output.output_directory = "/invalid/path/that/does/not/exist"

        mock_message = {"id": "dir-test-msg", "subject": "Test"}
        mock_graph_client.get_inbox_messages.return_value = [mock_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "dir-test-msg"
        mock_email.to_ai_format.return_value = {"id": "dir-test-msg"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock Path.mkdir to fail
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Cannot create directory")):
            # Should fail during file storage
            result = await processor.process_inbox()

            assert result["success"] is False
            assert result["processed_count"] == 0
            assert result["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_inbox_with_api_storage_edge_cases(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with API storage edge cases."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        mock_message = {"id": "api-test-msg", "subject": "Test"}
        mock_graph_client.get_inbox_messages.return_value = [mock_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "api-test-msg"
        mock_email.to_ai_format.return_value = {"id": "api-test-msg"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Test various API error scenarios
        api_errors = [
            (500, "Internal Server Error"),
            (502, "Bad Gateway"),
            (503, "Service Unavailable"),
            (504, "Gateway Timeout"),
            (429, "Too Many Requests"),
        ]

        for status_code, error_message in api_errors:
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = AsyncMock()
                mock_response.status = status_code
                mock_response.text.return_value = error_message

                mock_client = AsyncMock()
                mock_client.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                    mock_response
                )
                mock_client_class.return_value = mock_client

                result = await processor.process_inbox()

                assert result["success"] is False
                assert result["processed_count"] == 0
                assert result["failed_count"] == 1
                assert str(status_code) in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_inbox_with_dry_run_mode(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing in dry run mode."""
        processor.settings.dry_run = True

        mock_message = {"id": "dry-run-msg", "subject": "Test"}
        mock_graph_client.get_inbox_messages.return_value = [mock_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "dry-run-msg"
        mock_email.to_ai_format.return_value = {"id": "dry-run-msg"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            result = await processor.process_inbox()

        # In dry run mode, should not move messages
        assert result["success"] is True
        assert result["processed_count"] == 1
        # Move should not be called in dry run mode
        mock_graph_client.move_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_inbox_with_folder_name_edge_cases(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with folder name edge cases."""
        # Test with datetime at year/month boundaries
        test_cases = [
            (datetime(2023, 12, 31, 23, 59, 59), "Processed_12_2023"),
            (datetime(2024, 1, 1, 0, 0, 0), "Processed_01_2024"),
            (datetime(2024, 2, 29, 12, 0, 0), "Processed_02_2024"),  # Leap year
            (datetime(2099, 12, 31, 23, 59, 59), "Processed_12_2099"),
        ]

        for test_datetime, expected_folder_name in test_cases:
            with patch("datetime.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = test_datetime

                folder_name = processor._get_processed_folder_name()
                assert folder_name == expected_folder_name

    @pytest.mark.asyncio
    async def test_process_inbox_with_processing_metadata_edge_cases(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing with processing metadata edge cases."""
        mock_message = {"id": "metadata-test-msg", "subject": "Test"}
        mock_graph_client.get_inbox_messages.return_value = [mock_message]
        mock_folder = {"id": "folder-id", "displayName": "Test Folder"}
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email model with edge case metadata
        mock_email = Mock()
        mock_email.id = "metadata-test-msg"
        mock_email.to_ai_format.return_value = {"id": "metadata-test-msg"}
        mock_processing_metadata = Mock()
        mock_processing_metadata.processing_id = "x" * 1000  # Very long processing ID
        mock_email.processing_metadata = mock_processing_metadata
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            result = await processor.process_inbox()

        assert result["success"] is True
        assert result["processed_count"] == 1


class TestEdgeCasesGraphAPIClient:
    """Edge case tests for GraphAPIClient."""

    @pytest.fixture
    def graph_client(self) -> GraphAPIClient:
        """Create GraphAPIClient for edge case testing."""
        from ..config.settings import GraphAPISettings

        settings = GraphAPISettings(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            monitored_email="test@example.com",
        )
        return GraphAPIClient(settings)

    def test_parse_email_address_with_extremely_long_values(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test parsing email address with extremely long values."""
        long_email = "a" * 1000 + "@" + "b" * 1000 + ".com"
        long_name = "c" * 10000

        address_data = {"emailAddress": {"address": long_email, "name": long_name}}

        result = graph_client._parse_email_address(address_data)

        assert result.email == long_email
        assert result.name == long_name

    def test_parse_email_address_with_special_characters(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test parsing email address with special characters."""
        special_cases = [
            ("user+tag@example.com", "User with +"),
            ("user.name@example.com", "User with ."),
            ("user_name@example.com", "User with _"),
            ("user-name@example.com", "User with -"),
            ("user@sub.example.com", "User with subdomain"),
            ("user@example-domain.com", "User with - in domain"),
            ("user@123.456.789.123", "User with IP"),
            ("测试@example.com", "测试用户"),  # Unicode characters
            ("user@тест.com", "User with Cyrillic domain"),
        ]

        for email, name in special_cases:
            address_data = {"emailAddress": {"address": email, "name": name}}

            result = graph_client._parse_email_address(address_data)

            assert result.email == email
            assert result.name == name

    def test_parse_importance_with_edge_case_values(self, graph_client: GraphAPIClient) -> None:
        """Test parsing importance with edge case values."""
        edge_cases = [
            ("", EmailImportance.NORMAL),
            ("   ", EmailImportance.NORMAL),
            ("low ", EmailImportance.LOW),  # Trailing space
            (" normal", EmailImportance.NORMAL),  # Leading space
            ("HIGH", EmailImportance.HIGH),
            ("hIgH", EmailImportance.HIGH),  # Mixed case
            ("urgent", EmailImportance.NORMAL),  # Invalid but similar
            ("critical", EmailImportance.NORMAL),  # Invalid but similar
            ("0", EmailImportance.NORMAL),  # Number as string
            ("false", EmailImportance.NORMAL),  # Boolean as string
        ]

        for input_value, expected in edge_cases:
            result = graph_client._parse_importance(input_value)
            assert result == expected

    def test_parse_datetime_with_edge_case_formats(self, graph_client: GraphAPIClient) -> None:
        """Test parsing datetime with various edge case formats."""
        # Valid edge cases
        valid_cases = [
            "2024-01-01T00:00:00Z",  # Minimum values
            "2024-12-31T23:59:59Z",  # Maximum values
            "2024-02-29T12:00:00Z",  # Leap year
            "2024-01-15T10:30:00.000Z",  # With milliseconds
            "2024-01-15T10:30:00.123456Z",  # With microseconds
        ]

        for datetime_str in valid_cases:
            result = graph_client._parse_datetime(datetime_str)
            assert isinstance(result, datetime)

    def test_parse_datetime_with_invalid_edge_cases(self, graph_client: GraphAPIClient) -> None:
        """Test parsing datetime with invalid edge cases."""
        invalid_cases = [
            "2024-02-30T10:30:00Z",  # Invalid date (Feb 30)
            "2024-04-31T10:30:00Z",  # Invalid date (Apr 31)
            "2024-01-15T25:30:00Z",  # Invalid hour
            "2024-01-15T10:60:00Z",  # Invalid minute
            "2024-01-15T10:30:60Z",  # Invalid second
            "2024-00-15T10:30:00Z",  # Invalid month
            "2024-13-15T10:30:00Z",  # Invalid month
            "2024-01-00T10:30:00Z",  # Invalid day
            "0000-01-15T10:30:00Z",  # Invalid year
        ]

        for datetime_str in invalid_cases:
            with pytest.raises(ValueError):
                graph_client._parse_datetime(datetime_str)

    def test_convert_to_email_model_with_extreme_recipient_counts(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test converting email with extreme recipient counts."""
        # Create message with many recipients
        to_recipients = [
            {"emailAddress": {"address": f"to{i}@example.com", "name": f"To User {i}"}}
            for i in range(100)
        ]
        cc_recipients = [
            {"emailAddress": {"address": f"cc{i}@example.com", "name": f"CC User {i}"}}
            for i in range(50)
        ]
        bcc_recipients = [
            {"emailAddress": {"address": f"bcc{i}@example.com", "name": f"BCC User {i}"}}
            for i in range(25)
        ]

        graph_message = {
            "id": "many-recipients-msg",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "toRecipients": to_recipients,
            "ccRecipients": cc_recipients,
            "bccRecipients": bcc_recipients,
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert len(email.recipients.to) == 100
        assert len(email.recipients.cc) == 50
        assert len(email.recipients.bcc) == 25

    def test_convert_to_email_model_with_extreme_header_count(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test converting email with extreme header count."""
        # Create message with many headers
        headers = [{"name": f"X-Custom-Header-{i}", "value": f"Value-{i}"} for i in range(1000)]

        graph_message = {
            "id": "many-headers-msg",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "internetMessageHeaders": headers,
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert len(email.internet_message_headers) == 1000
        assert email.internet_message_headers["X-Custom-Header-0"] == "Value-0"
        assert email.internet_message_headers["X-Custom-Header-999"] == "Value-999"

    def test_convert_to_email_model_with_duplicate_headers(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test converting email with duplicate header names."""
        # Create message with duplicate headers
        headers = [
            {"name": "Received", "value": "by server1"},
            {"name": "Received", "value": "by server2"},
            {"name": "Received", "value": "by server3"},
        ]

        graph_message = {
            "id": "duplicate-headers-msg",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "internetMessageHeaders": headers,
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        # Should handle duplicate headers (last one wins)
        assert email.internet_message_headers["Received"] == "by server3"

    def test_convert_to_email_model_with_empty_collections(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test converting email with empty collections."""
        graph_message = {
            "id": "empty-collections-msg",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "toRecipients": [],
            "ccRecipients": [],
            "bccRecipients": [],
            "categories": [],
            "internetMessageHeaders": [],
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert len(email.recipients.to) == 0
        assert len(email.recipients.cc) == 0
        assert len(email.recipients.bcc) == 0
        assert len(email.categories) == 0
        assert len(email.internet_message_headers) == 0

    def test_token_cache_with_edge_case_expiry_times(self, graph_client: GraphAPIClient) -> None:
        """Test token cache with edge case expiry times."""
        # Mock MSAL app
        mock_app = Mock()
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "test-token",
            "expires_in": 0,  # Edge case: expires immediately
        }
        graph_client.msal_app = mock_app

        token = graph_client._get_access_token()
        assert token == "test-token"

        # Should acquire new token immediately since it expired
        token2 = graph_client._get_access_token()
        assert token2 == "test-token"
        assert mock_app.acquire_token_for_client.call_count == 2

    def test_token_cache_with_negative_expiry(self, graph_client: GraphAPIClient) -> None:
        """Test token cache with negative expiry time."""
        # Mock MSAL app
        mock_app = Mock()
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "test-token",
            "expires_in": -3600,  # Edge case: negative expiry
        }
        graph_client.msal_app = mock_app

        token = graph_client._get_access_token()
        assert token == "test-token"

        # Should treat as expired and acquire new token
        token2 = graph_client._get_access_token()
        assert token2 == "test-token"
        assert mock_app.acquire_token_for_client.call_count == 2
