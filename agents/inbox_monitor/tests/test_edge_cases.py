"""
Edge Case Tests for Inbox Monitor
==================================

Comprehensive tests for edge cases and boundary conditions.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from ..models.email import (
    EmailImportance,
)
from ..services.email_processor import EmailProcessor
from ..services.graph_api_client import GraphAPIClient
from ..services.monitor import InboxMonitor


class TestEmailProcessorEdgeCases:
    """Test edge cases for EmailProcessor."""

    @pytest.fixture
    def processor(self, mock_settings, mock_graph_client):
        """Create email processor instance."""
        return EmailProcessor(mock_settings, mock_graph_client)

    @pytest.mark.asyncio
    async def test_process_inbox_with_empty_response(self, processor, mock_graph_client):
        """Test processing inbox when Graph API returns empty response."""
        mock_graph_client.get_inbox_messages.return_value = []

        results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 0
        assert results["failed_count"] == 0
        assert results["processing_results"] == []

    @pytest.mark.asyncio
    async def test_process_inbox_with_none_response(self, processor, mock_graph_client):
        """Test processing inbox when Graph API returns None."""
        mock_graph_client.get_inbox_messages.return_value = None

        results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 0
        assert results["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_process_inbox_with_large_batch(
        self, processor, mock_graph_client, mock_graph_message, mock_folder
    ):
        """Test processing inbox with maximum batch size."""
        # Create a large batch of messages
        messages = [mock_graph_message.copy() for _ in range(50)]
        for i, msg in enumerate(messages):
            msg["id"] = f"message-{i}"
            msg["subject"] = f"Test Message {i}"

        mock_graph_client.get_inbox_messages.return_value = messages
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 50
        assert results["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_process_inbox_with_special_characters(
        self, processor, mock_graph_client, mock_folder
    ):
        """Test processing emails with special characters and Unicode."""
        special_message = {
            "id": "special-chars-message",
            "subject": "Test with émojis 🚀 and spëcial chars: àáâãäåæçèéêë",
            "body": {
                "contentType": "text/html",
                "content": "<html><body>Content with 中文字符 and emojis: 😀🎉💡</body></html>",
            },
            "from": {
                "emailAddress": {
                    "address": "tëst@éxample.com",
                    "name": "Tëst Üser 中文",
                }
            },
            "toRecipients": [],
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False,
            "importance": "normal",
            "isRead": False,
            "isDraft": False,
        }

        mock_graph_client.get_inbox_messages.return_value = [special_message]
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "special-chars-message"
        mock_email.to_ai_format.return_value = {
            "id": "special-chars-message",
            "subject": special_message["subject"],
        }
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()) as mock_file:
            results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 1
        # Verify Unicode content was written
        mock_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_inbox_with_extremely_long_subject(
        self, processor, mock_graph_client, mock_folder
    ):
        """Test processing email with extremely long subject line."""
        long_subject = "A" * 10000  # 10KB subject line

        long_message = {
            "id": "long-subject-message",
            "subject": long_subject,
            "body": {"contentType": "text/plain", "content": "Short content"},
            "from": {"emailAddress": {"address": "test@example.com", "name": "Test User"}},
            "toRecipients": [],
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False,
            "importance": "normal",
            "isRead": False,
            "isDraft": False,
        }

        mock_graph_client.get_inbox_messages.return_value = [long_message]
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "long-subject-message"
        mock_email.to_ai_format.return_value = {
            "id": "long-subject-message",
            "subject": long_subject,
        }
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_inbox_with_empty_body(self, processor, mock_graph_client, mock_folder):
        """Test processing email with empty body content."""
        empty_body_message = {
            "id": "empty-body-message",
            "subject": "Empty Body Test",
            "body": {"contentType": "text/plain", "content": ""},
            "from": {"emailAddress": {"address": "test@example.com", "name": "Test User"}},
            "toRecipients": [],
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False,
            "importance": "normal",
            "isRead": False,
            "isDraft": False,
        }

        mock_graph_client.get_inbox_messages.return_value = [empty_body_message]
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "empty-body-message"
        mock_email.to_ai_format.return_value = {
            "id": "empty-body-message",
            "content": "",
        }
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_inbox_with_missing_sender(
        self, processor, mock_graph_client, mock_folder
    ):
        """Test processing email with missing sender information."""
        no_sender_message = {
            "id": "no-sender-message",
            "subject": "No Sender Test",
            "body": {"contentType": "text/plain", "content": "Test content"},
            "from": None,  # Missing sender
            "toRecipients": [],
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False,
            "importance": "normal",
            "isRead": False,
            "isDraft": False,
        }

        mock_graph_client.get_inbox_messages.return_value = [no_sender_message]
        mock_graph_client.get_folder_by_name.return_value = mock_folder

        # Mock email conversion to handle missing sender
        mock_email = Mock()
        mock_email.id = "no-sender-message"
        mock_email.to_ai_format.return_value = {
            "id": "no-sender-message",
            "sender": None,
        }
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch("builtins.open", mock_open()):
            results = await processor.process_inbox()

        assert results["success"] is True
        assert results["processed_count"] == 1

    @pytest.mark.asyncio
    async def test_store_email_file_with_permission_error(self, processor, mock_email_model):
        """Test file storage with permission error."""
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                await processor._store_email_file(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_file_with_disk_full(self, processor, mock_email_model):
        """Test file storage with disk full error."""
        with patch("builtins.open", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError):
                await processor._store_email_file(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_api_with_network_timeout(self, processor, mock_email_model):
        """Test API storage with network timeout."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post.side_effect = (
                asyncio.TimeoutError("Network timeout")
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(asyncio.TimeoutError):
                await processor._store_email_api(mock_email_model)

    @pytest.mark.asyncio
    async def test_store_email_api_with_invalid_json_response(self, processor, mock_email_model):
        """Test API storage with invalid JSON response."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(json.JSONDecodeError):
                await processor._store_email_api(mock_email_model)

    def test_get_processed_folder_name_edge_cases(self, processor):
        """Test folder name generation with edge cases."""
        # Test with mocked datetime at year/month boundaries
        with patch("datetime.datetime") as mock_datetime:
            # Test January (month 01)
            mock_datetime.utcnow.return_value.strftime.side_effect = ["01", "2024"]
            folder_name = processor._get_processed_folder_name()
            assert folder_name == "Processed_01_2024"

            # Test December (month 12)
            mock_datetime.utcnow.return_value.strftime.side_effect = ["12", "2024"]
            folder_name = processor._get_processed_folder_name()
            assert folder_name == "Processed_12_2024"

            # Test year 2099
            mock_datetime.utcnow.return_value.strftime.side_effect = ["06", "2099"]
            folder_name = processor._get_processed_folder_name()
            assert folder_name == "Processed_06_2099"

    @pytest.mark.asyncio
    async def test_ensure_processed_folder_with_retry_exhaustion(
        self, processor, mock_graph_client
    ):
        """Test folder creation with retry exhaustion."""
        mock_graph_client.get_folder_by_name.return_value = None

        # Mock retry_operation to fail after exhausting retries
        with patch("agents.inbox_monitor.services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (False, None, "Max retries exceeded")

            folder = await processor._ensure_processed_folder("Test Folder")
            assert folder is None

    @pytest.mark.asyncio
    async def test_process_single_email_with_conversion_error(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with conversion error."""
        mock_graph_client.convert_to_email_model.side_effect = ValueError("Invalid email format")

        result = await processor._process_single_email(
            mock_graph_message, "folder-id", "Test Folder"
        )

        assert result.success is False
        assert "Invalid email format" in result.error
        assert result.moved_to_folder is None

    @pytest.mark.asyncio
    async def test_process_single_email_with_storage_error(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with storage error."""
        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Mock storage to fail
        with patch.object(processor, "_store_email", side_effect=OSError("Storage failed")):
            result = await processor._process_single_email(
                mock_graph_message, "folder-id", "Test Folder"
            )

        assert result.success is False
        assert "Storage failed" in result.error

    @pytest.mark.asyncio
    async def test_process_single_email_with_move_failure(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with move failure."""
        # Mock email conversion and storage
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        with patch.object(processor, "_store_email", return_value="/tmp/test.json"):
            # Mock retry_operation to fail
            with patch(
                "agents.inbox_monitor.services.email_processor.retry_operation"
            ) as mock_retry:
                mock_retry.return_value = (False, None, "Move failed")

                result = await processor._process_single_email(
                    mock_graph_message, "folder-id", "Test Folder"
                )

        assert result.success is False
        assert "Failed to move email: Move failed" in result.error


class TestGraphAPIClientEdgeCases:
    """Test edge cases for GraphAPIClient."""

    @pytest.fixture
    def graph_client(self, mock_settings):
        """Create Graph API client for testing."""

        return GraphAPIClient(mock_settings.graph_api)

    def test_token_cache_expiry_edge_case(self, graph_client):
        """Test token cache behavior at expiry boundary."""
        # Set token to expire in 1 second
        graph_client._token_cache = {
            "access_token": "old-token",
            "expires_at": datetime.utcnow().timestamp() + 1,
        }

        # Mock MSAL to return new token
        graph_client.msal_app.acquire_token_for_client.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }

        # Wait for expiry
        import time

        time.sleep(1.1)

        token = graph_client._get_access_token()
        assert token == "new-token"
        graph_client.msal_app.acquire_token_for_client.assert_called_once()

    def test_parse_email_address_edge_cases(self, graph_client):
        """Test email address parsing with edge cases."""
        # Test with empty email address
        empty_address = {"emailAddress": {"address": "", "name": ""}}
        result = graph_client._parse_email_address(empty_address)
        assert result.email == ""
        assert result.name == ""

        # Test with missing name field
        no_name = {"emailAddress": {"address": "test@example.com"}}
        result = graph_client._parse_email_address(no_name)
        assert result.email == "test@example.com"
        assert result.name is None

        # Test with None values
        none_values = {"emailAddress": {"address": None, "name": None}}
        result = graph_client._parse_email_address(none_values)
        assert result.email is None
        assert result.name is None

    def test_parse_importance_edge_cases(self, graph_client):
        """Test importance parsing with edge cases."""
        # Test with None
        assert graph_client._parse_importance(None) == EmailImportance.NORMAL

        # Test with empty string
        assert graph_client._parse_importance("") == EmailImportance.NORMAL

        # Test with mixed case
        assert graph_client._parse_importance("HIGH") == EmailImportance.HIGH
        assert graph_client._parse_importance("Low") == EmailImportance.LOW

        # Test with invalid values
        assert graph_client._parse_importance("super-critical") == EmailImportance.NORMAL
        assert graph_client._parse_importance("123") == EmailImportance.NORMAL

    def test_convert_to_email_model_with_minimal_data(self, graph_client):
        """Test email model conversion with minimal data."""
        minimal_message = {
            "id": "minimal-id",
            "receivedDateTime": "2024-01-15T10:30:00Z",
        }

        email = graph_client.convert_to_email_model(minimal_message, "test-processing-id", "1.0.0")

        assert email.id == "minimal-id"
        assert email.subject == ""
        assert email.body.content == ""
        assert email.sender.email == ""
        assert len(email.recipients.to) == 0
        assert email.importance == EmailImportance.NORMAL

    def test_convert_to_email_model_with_malformed_dates(self, graph_client):
        """Test email model conversion with malformed dates."""
        malformed_message = {
            "id": "malformed-id",
            "receivedDateTime": "invalid-date-format",
            "sentDateTime": "2024-13-45T25:99:99Z",  # Invalid date
        }

        with pytest.raises(ValueError):
            graph_client.convert_to_email_model(malformed_message, "test-processing-id", "1.0.0")

    def test_convert_to_email_model_with_extreme_values(self, graph_client):
        """Test email model conversion with extreme values."""
        extreme_message = {
            "id": "extreme-id",
            "subject": "A" * 100000,  # Very long subject
            "body": {
                "contentType": "text/html",
                "content": "<html>" + "B" * 1000000 + "</html>",  # Very long content
            },
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "from": {"emailAddress": {"address": "test@example.com"}},
            "toRecipients": [
                {"emailAddress": {"address": f"user{i}@example.com"}} for i in range(1000)
            ],  # Many recipients
            "categories": [f"Category{i}" for i in range(100)],  # Many categories
            "internetMessageHeaders": [
                {"name": f"Header{i}", "value": f"Value{i}"} for i in range(500)
            ],  # Many headers
        }

        email = graph_client.convert_to_email_model(extreme_message, "test-processing-id", "1.0.0")

        assert email.id == "extreme-id"
        assert len(email.subject) == 100000
        assert len(email.recipients.to) == 1000
        assert len(email.categories) == 100
        assert len(email.internet_message_headers) == 500


class TestInboxMonitorEdgeCases:
    """Test edge cases for InboxMonitor."""

    @pytest.fixture
    def monitor(self, mock_settings):
        """Create inbox monitor instance."""
        return InboxMonitor(mock_settings)

    @pytest.mark.asyncio
    async def test_monitor_with_rapid_shutdown(self, monitor):
        """Test monitor behavior with rapid start/stop cycles."""
        # Mock components
        with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            # Start and immediately stop
            start_task = asyncio.create_task(monitor.start())
            await asyncio.sleep(0.01)  # Very short delay
            await monitor.stop()

            # Wait for start task to complete
            await start_task

            # Verify cleanup was called
            mock_graph_client.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_with_processing_timeout(self, monitor):
        """Test monitor behavior when processing takes too long."""
        monitor._running = True

        # Mock email processor with very slow processing
        mock_processor = AsyncMock()
        slow_future = asyncio.Future()
        mock_processor.process_inbox.return_value = slow_future
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        # This should timeout and not hang
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(monitor._monitor_loop(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_monitor_with_memory_pressure(self, monitor):
        """Test monitor behavior under memory pressure."""
        monitor._running = True

        # Mock email processor to simulate memory pressure
        mock_processor = AsyncMock()
        mock_processor.process_inbox.side_effect = MemoryError("Out of memory")
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()
        monitor._shutdown_event.wait.side_effect = asyncio.TimeoutError

        # Run one iteration and verify it handles memory error
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

    @pytest.mark.asyncio
    async def test_health_check_with_partial_failure(self, monitor):
        """Test health check with partial system failure."""
        monitor._running = True

        # Mock graph client with intermittent failures
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.side_effect = [
            {"id": "user-id"},  # First call succeeds
            Exception("Network error"),  # Second call fails
        ]
        monitor.graph_client = mock_graph_client

        # First health check should succeed
        health1 = await monitor.health_check()
        assert health1["status"] == "healthy"
        assert health1["graph_api_connected"] is True

        # Second health check should fail
        health2 = await monitor.health_check()
        assert health2["status"] == "unhealthy"
        assert health2["graph_api_connected"] is False
        assert "Network error" in health2["last_error"]

    def test_signal_handler_edge_cases(self, monitor):
        """Test signal handler with edge cases."""
        with patch("signal.signal") as mock_signal:
            monitor._setup_signal_handlers()

            # Get the registered handler
            handler = mock_signal.call_args_list[0][0][1]

            # Test handler with different signal numbers
            with patch("asyncio.create_task") as mock_create_task:
                handler(2, None)  # SIGINT
                mock_create_task.assert_called_once()

                mock_create_task.reset_mock()
                handler(15, None)  # SIGTERM
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_loop_with_zero_polling_interval(self, monitor):
        """Test monitor loop with zero polling interval."""
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

        # Mock shutdown event to trigger after short delay
        monitor._shutdown_event = AsyncMock()

        call_count = 0

        async def mock_wait():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:  # Stop after 3 calls
                monitor._running = False
            return

        monitor._shutdown_event.wait.side_effect = mock_wait

        await monitor._monitor_loop()

        # Should have processed multiple times quickly
        assert mock_processor.process_inbox.call_count >= 3

    @pytest.mark.asyncio
    async def test_monitor_loop_with_negative_sleep_time(self, monitor):
        """Test monitor loop when processing takes longer than polling interval."""
        monitor.settings.processing.polling_interval_seconds = 1  # 1 second interval
        monitor._running = True

        # Mock email processor with slow processing (2 seconds)
        mock_processor = AsyncMock()

        async def slow_process():
            await asyncio.sleep(2)  # Simulate slow processing
            return {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "errors": [],
                "processing_time_seconds": 2.0,
            }

        mock_processor.process_inbox.side_effect = slow_process
        monitor.email_processor = mock_processor

        # Mock shutdown event to trigger after processing
        monitor._shutdown_event = AsyncMock()

        call_count = 0

        async def mock_wait():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:  # Stop after 1 call
                monitor._running = False
            return

        monitor._shutdown_event.wait.side_effect = mock_wait

        start_time = asyncio.get_event_loop().time()
        await monitor._monitor_loop()
        end_time = asyncio.get_event_loop().time()

        # Should have processed without additional delay
        assert end_time - start_time >= 2.0  # At least the processing time
        assert mock_processor.process_inbox.call_count == 1
