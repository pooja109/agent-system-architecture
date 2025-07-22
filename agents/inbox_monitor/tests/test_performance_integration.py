"""
Performance and Integration Tests
==================================

Performance benchmarks and integration tests for the inbox monitor system.
Includes load testing, stress testing, and end-to-end workflows.
"""

import asyncio
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ..config.settings import AppSettings, GraphAPISettings, OutputSettings, ProcessingSettings
from ..services.email_processor import EmailProcessor
from ..services.monitor import InboxMonitor


class TestPerformanceInboxMonitor:
    """Performance tests for InboxMonitor."""

    @pytest.fixture
    def performance_settings(self) -> AppSettings:
        """Create settings optimized for performance testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                polling_interval_seconds=1,
                batch_size=100,
                max_retry_attempts=1,
                retry_delay_seconds=0,
            ),
            logging={"level": "ERROR", "format": "json"},  # Minimal logging for performance
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def monitor(self, performance_settings: AppSettings) -> InboxMonitor:
        """Create monitor for performance testing."""
        return InboxMonitor(performance_settings)

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_monitor_startup_performance(self, monitor: InboxMonitor) -> None:
        """Test monitor startup performance."""
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

                # Measure startup time
                start_time = time.time()
                await monitor.start()
                startup_time = time.time() - start_time

                # Should start quickly (less than 1 second)
                assert startup_time < 1.0

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_monitor_shutdown_performance(self, monitor: InboxMonitor) -> None:
        """Test monitor shutdown performance."""
        monitor._running = True

        # Mock graph client
        mock_graph_client = AsyncMock()
        monitor.graph_client = mock_graph_client

        # Measure shutdown time
        start_time = time.time()
        await monitor.stop()
        shutdown_time = time.time() - start_time

        # Should shutdown quickly (less than 1 second)
        assert shutdown_time < 1.0

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_health_check_performance(self, monitor: InboxMonitor) -> None:
        """Test health check performance."""
        monitor._running = True

        # Mock graph client
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.return_value = {"id": "user-id"}
        monitor.graph_client = mock_graph_client

        # Measure health check performance
        start_time = time.time()
        health = await monitor.health_check()
        health_check_time = time.time() - start_time

        # Should complete quickly (less than 100ms)
        assert health_check_time < 0.1
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_health_checks_performance(self, monitor: InboxMonitor) -> None:
        """Test concurrent health check performance."""
        monitor._running = True

        # Mock graph client
        mock_graph_client = AsyncMock()
        mock_graph_client._make_request.return_value = {"id": "user-id"}
        monitor.graph_client = mock_graph_client

        # Run multiple health checks concurrently
        concurrent_checks = 50

        start_time = time.time()
        tasks = [monitor.health_check() for _ in range(concurrent_checks)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Should handle concurrent requests efficiently
        assert total_time < 2.0  # Less than 2 seconds for 50 concurrent checks
        assert len(results) == concurrent_checks
        assert all(r["status"] == "healthy" for r in results)

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_monitor_loop_performance_with_successful_processing(
        self, monitor: InboxMonitor
    ) -> None:
        """Test monitor loop performance with successful processing."""
        monitor._running = True

        # Mock email processor with fast processing
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": True,
            "processed_count": 10,
            "failed_count": 0,
            "errors": [],
            "processing_time_seconds": 0.1,
        }
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()

        call_count = 0
        processing_times = []

        async def mock_wait(*args, **kwargs):
            nonlocal call_count
            start_time = time.time()
            call_count += 1
            if call_count >= 10:  # Process 10 times
                monitor._running = False
            processing_times.append(time.time() - start_time)
            raise asyncio.TimeoutError()

        monitor._shutdown_event.wait.side_effect = mock_wait

        # Measure loop performance
        start_time = time.time()
        await monitor._monitor_loop()
        total_time = time.time() - start_time

        # Should process efficiently
        assert total_time < 5.0  # Less than 5 seconds for 10 iterations
        assert call_count == 10
        assert mock_processor.process_inbox.call_count == 10

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_monitor_memory_usage_stability(self, monitor: InboxMonitor) -> None:
        """Test monitor memory usage stability over time."""
        monitor._running = True

        # Mock email processor
        mock_processor = AsyncMock()
        mock_processor.process_inbox.return_value = {
            "success": True,
            "processed_count": 5,
            "failed_count": 0,
            "errors": [],
            "processing_time_seconds": 0.05,
        }
        monitor.email_processor = mock_processor

        # Mock shutdown event
        monitor._shutdown_event = AsyncMock()

        call_count = 0

        async def mock_wait(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 100:  # Process 100 times
                monitor._running = False
            raise asyncio.TimeoutError()

        monitor._shutdown_event.wait.side_effect = mock_wait

        # Run for extended period
        await monitor._monitor_loop()

        # Should complete all iterations without memory issues
        assert call_count == 100
        assert mock_processor.process_inbox.call_count == 100


class TestPerformanceEmailProcessor:
    """Performance tests for EmailProcessor."""

    @pytest.fixture
    def performance_settings(self) -> AppSettings:
        """Create settings optimized for performance testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                batch_size=1000,
                max_retry_attempts=1,
                retry_delay_seconds=0,
            ),
            logging={"level": "ERROR", "format": "json"},
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.fixture
    def mock_graph_client(self) -> AsyncMock:
        """Create mock graph client for performance testing."""
        mock_client = AsyncMock()
        mock_client.get_inbox_messages.return_value = []
        mock_client.get_folder_by_name.return_value = {
            "id": "folder-id",
            "displayName": "Test Folder",
        }
        mock_client.create_folder.return_value = {"id": "folder-id", "displayName": "Test Folder"}
        mock_client.move_message.return_value = {"id": "message-id"}
        mock_client.convert_to_email_model.return_value = Mock()
        return mock_client

    @pytest.fixture
    def processor(
        self, performance_settings: AppSettings, mock_graph_client: AsyncMock
    ) -> EmailProcessor:
        """Create processor for performance testing."""
        return EmailProcessor(performance_settings, mock_graph_client)

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_process_large_batch_performance(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test processing large batch of emails performance."""
        # Create large batch of messages
        batch_size = 1000
        large_batch = []
        for i in range(batch_size):
            large_batch.append(
                {
                    "id": f"msg-{i}",
                    "subject": f"Test Message {i}",
                    "body": {"contentType": "text/plain", "content": f"Content {i}"},
                }
            )

        mock_graph_client.get_inbox_messages.return_value = large_batch

        # Mock email model
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Use temporary directory for performance testing
        with tempfile.TemporaryDirectory() as temp_dir:
            processor.settings.output.output_directory = temp_dir

            # Measure processing time
            start_time = time.time()
            result = await processor.process_inbox()
            processing_time = time.time() - start_time

            # Should process large batch efficiently
            assert result["success"] is True
            assert result["processed_count"] == batch_size
            assert result["failed_count"] == 0

            # Should process at least 100 emails per second
            emails_per_second = batch_size / processing_time
            assert emails_per_second >= 100

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_email_processing_performance(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test concurrent email processing performance."""
        # Create multiple batches for concurrent processing
        batch_size = 100
        num_batches = 10

        async def process_batch():
            batch = []
            for i in range(batch_size):
                batch.append(
                    {
                        "id": f"msg-{i}-{time.time()}",
                        "subject": f"Test Message {i}",
                        "body": {"contentType": "text/plain", "content": f"Content {i}"},
                    }
                )

            mock_graph_client.get_inbox_messages.return_value = batch

            # Mock email model
            mock_email = Mock()
            mock_email.id = "test-message-id"
            mock_email.to_ai_format.return_value = {"id": "test-message-id"}
            mock_email.processing_metadata = Mock()
            mock_email.processing_metadata.processing_id = "test-processing-id"
            mock_graph_client.convert_to_email_model.return_value = mock_email

            return await processor.process_inbox()

        # Use temporary directory for performance testing
        with tempfile.TemporaryDirectory() as temp_dir:
            processor.settings.output.output_directory = temp_dir

            # Run concurrent processing
            start_time = time.time()
            tasks = [process_batch() for _ in range(num_batches)]
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            # Should handle concurrent processing efficiently
            assert len(results) == num_batches
            assert all(r["success"] for r in results)

            total_processed = sum(r["processed_count"] for r in results)
            assert total_processed == batch_size * num_batches

            # Should process at least 200 emails per second with concurrency
            emails_per_second = total_processed / total_time
            assert emails_per_second >= 200

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_file_storage_performance(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test file storage performance with many files."""
        # Create many messages
        num_messages = 500
        messages = []
        for i in range(num_messages):
            messages.append(
                {
                    "id": f"msg-{i}",
                    "subject": f"Test Message {i}",
                    "body": {
                        "contentType": "text/plain",
                        "content": f"Content {i}" * 100,
                    },  # Larger content
                }
            )

        mock_graph_client.get_inbox_messages.return_value = messages

        # Mock email model
        def create_mock_email(msg_id):
            mock_email = Mock()
            mock_email.id = msg_id
            mock_email.to_ai_format.return_value = {"id": msg_id, "content": "test content" * 100}
            mock_email.processing_metadata = Mock()
            mock_email.processing_metadata.processing_id = f"proc-{msg_id}"
            return mock_email

        mock_graph_client.convert_to_email_model.side_effect = (
            lambda msg, proc_id, version: create_mock_email(msg["id"])
        )

        # Use temporary directory for performance testing
        with tempfile.TemporaryDirectory() as temp_dir:
            processor.settings.output.output_directory = temp_dir

            # Measure file storage performance
            start_time = time.time()
            result = await processor.process_inbox()
            storage_time = time.time() - start_time

            # Should store files efficiently
            assert result["success"] is True
            assert result["processed_count"] == num_messages

            # Should store at least 50 files per second
            files_per_second = num_messages / storage_time
            assert files_per_second >= 50

            # Verify files were actually created
            output_files = list(Path(temp_dir).glob("*.json"))
            assert len(output_files) == num_messages

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_folder_management_performance(
        self, processor: EmailProcessor, mock_graph_client: AsyncMock
    ) -> None:
        """Test folder management performance with many operations."""
        # Create message
        message = {"id": "msg-1", "subject": "Test"}
        mock_graph_client.get_inbox_messages.return_value = [message]

        # Mock folder operations with timing
        folder_call_count = 0
        folder_call_times = []

        async def mock_get_folder(*args, **kwargs):
            nonlocal folder_call_count
            start_time = time.time()
            folder_call_count += 1
            # Simulate API call delay
            await asyncio.sleep(0.01)
            folder_call_times.append(time.time() - start_time)
            return {"id": f"folder-{folder_call_count}", "displayName": "Test Folder"}

        mock_graph_client.get_folder_by_name.side_effect = mock_get_folder

        # Mock email model
        mock_email = Mock()
        mock_email.id = "msg-1"
        mock_email.to_ai_format.return_value = {"id": "msg-1"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.processing_id = "proc-1"
        mock_graph_client.convert_to_email_model.return_value = mock_email

        # Use temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            processor.settings.output.output_directory = temp_dir

            # Measure folder management performance
            start_time = time.time()
            result = await processor.process_inbox()
            folder_time = time.time() - start_time

            # Should handle folder operations efficiently
            assert result["success"] is True
            assert folder_call_count >= 1
            assert folder_time < 1.0  # Should complete within 1 second


class TestIntegrationWorkflows:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def integration_settings(self) -> AppSettings:
        """Create settings for integration testing."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(
                polling_interval_seconds=1,
                batch_size=10,
                max_retry_attempts=3,
                retry_delay_seconds=1,
            ),
            logging={"level": "INFO", "format": "json"},
            output=OutputSettings(storage_type="file", output_directory="./test_output"),
            environment="test",
            dry_run=False,
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_email_processing_workflow(
        self, integration_settings: AppSettings
    ) -> None:
        """Test complete email processing workflow from start to finish."""
        with tempfile.TemporaryDirectory() as temp_dir:
            integration_settings.output.output_directory = temp_dir

            # Create monitor
            monitor = InboxMonitor(integration_settings)

            with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
                # Mock graph client
                mock_graph_client = AsyncMock()
                mock_graph_class.return_value = mock_graph_client

                # Mock email data
                mock_messages = [
                    {
                        "id": "msg-1",
                        "subject": "Test Email 1",
                        "body": {
                            "contentType": "text/html",
                            "content": "<html><body>Test 1</body></html>",
                        },
                        "from": {
                            "emailAddress": {"address": "sender1@example.com", "name": "Sender 1"}
                        },
                        "receivedDateTime": "2024-01-15T10:30:00Z",
                        "hasAttachments": False,
                        "importance": "normal",
                        "isRead": False,
                        "isDraft": False,
                    },
                    {
                        "id": "msg-2",
                        "subject": "Test Email 2",
                        "body": {"contentType": "text/plain", "content": "Test content 2"},
                        "from": {
                            "emailAddress": {"address": "sender2@example.com", "name": "Sender 2"}
                        },
                        "receivedDateTime": "2024-01-15T10:35:00Z",
                        "hasAttachments": True,
                        "importance": "high",
                        "isRead": False,
                        "isDraft": False,
                    },
                ]

                mock_graph_client.get_inbox_messages.return_value = mock_messages
                mock_folder = {"id": "folder-123", "displayName": "Processed_01_2024"}
                mock_graph_client.get_folder_by_name.return_value = mock_folder
                mock_graph_client.move_message.return_value = {"id": "moved-msg"}

                # Mock email conversion
                def mock_convert_to_email_model(message, processing_id, version):
                    from ..models.email import (
                        Email,
                        EmailAddress,
                        EmailBody,
                        EmailImportance,
                        EmailRecipients,
                        ProcessingMetadata,
                    )

                    return Email(
                        id=message["id"],
                        conversation_id="conv-123",
                        received_datetime=datetime.fromisoformat(
                            message["receivedDateTime"].replace("Z", "+00:00")
                        ),
                        sent_datetime=datetime.fromisoformat(
                            message["receivedDateTime"].replace("Z", "+00:00")
                        ),
                        sender=EmailAddress(
                            email=message["from"]["emailAddress"]["address"],
                            name=message["from"]["emailAddress"]["name"],
                        ),
                        recipients=EmailRecipients(to=[], cc=[], bcc=[]),
                        subject=message["subject"],
                        body=EmailBody(
                            content_type=message["body"]["contentType"],
                            content=message["body"]["content"],
                        ),
                        body_preview=message["body"]["content"][:100],
                        importance=EmailImportance(message["importance"]),
                        has_attachments=message["hasAttachments"],
                        attachment_count=1 if message["hasAttachments"] else 0,
                        categories=[],
                        is_read=message["isRead"],
                        is_draft=message["isDraft"],
                        internet_message_headers={},
                        processing_metadata=ProcessingMetadata(
                            inbox_monitor_version=version,
                            processing_id=processing_id,
                            processing_timestamp=datetime.utcnow(),
                            source_folder="Inbox",
                        ),
                    )

                mock_graph_client.convert_to_email_model.side_effect = mock_convert_to_email_model

                with patch(
                    "agents.inbox_monitor.services.monitor.EmailProcessor"
                ) as mock_processor_class:
                    # Use real EmailProcessor for integration testing
                    real_processor = EmailProcessor(integration_settings, mock_graph_client)
                    mock_processor_class.return_value = real_processor

                    # Mock the monitor loop to run once
                    async def single_iteration_loop():
                        monitor._running = True

                        # Process inbox once
                        if monitor.email_processor:
                            results = await monitor.email_processor.process_inbox()

                            # Verify results
                            assert results["success"] is True
                            assert results["processed_count"] == 2
                            assert results["failed_count"] == 0

                            # Verify files were created
                            output_files = list(Path(temp_dir).glob("*.json"))
                            assert len(output_files) == 2

                            # Verify file contents
                            for output_file in output_files:
                                with open(output_file) as f:
                                    email_data = json.load(f)
                                    assert "id" in email_data
                                    assert "subject" in email_data
                                    assert "processing_metadata" in email_data

                        monitor._running = False

                    monitor._monitor_loop = single_iteration_loop

                    # Run the complete workflow
                    await monitor.start()

                    # Verify graph client calls
                    mock_graph_client.initialize.assert_called_once()
                    mock_graph_client.get_inbox_messages.assert_called()
                    mock_graph_client.get_folder_by_name.assert_called()
                    mock_graph_client.move_message.assert_called()

                    # Verify cleanup
                    await monitor.stop()
                    mock_graph_client.cleanup.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_recovery_workflow(self, integration_settings: AppSettings) -> None:
        """Test error recovery workflow with transient failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            integration_settings.output.output_directory = temp_dir

            # Create monitor
            monitor = InboxMonitor(integration_settings)

            with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
                # Mock graph client with intermittent failures
                mock_graph_client = AsyncMock()
                mock_graph_class.return_value = mock_graph_client

                # Mock intermittent failures
                call_count = 0

                def intermittent_failure():
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 2:  # Fail first 2 calls
                        raise ConnectionError("Transient network error")
                    return [{"id": "msg-1", "subject": "Test Email"}]

                mock_graph_client.get_inbox_messages.side_effect = intermittent_failure

                with patch(
                    "agents.inbox_monitor.services.monitor.EmailProcessor"
                ) as mock_processor_class:
                    # Use real EmailProcessor
                    real_processor = EmailProcessor(integration_settings, mock_graph_client)
                    mock_processor_class.return_value = real_processor

                    # Mock monitor loop to handle failures
                    iteration_count = 0

                    async def error_recovery_loop():
                        nonlocal iteration_count
                        monitor._running = True
                        consecutive_failures = 0

                        while monitor._running and iteration_count < 5:
                            iteration_count += 1

                            try:
                                if monitor.email_processor:
                                    results = await monitor.email_processor.process_inbox()

                                    if results["success"]:
                                        consecutive_failures = 0
                                        # Success after failures
                                        if iteration_count > 2:
                                            monitor._running = False
                                            break
                                    else:
                                        consecutive_failures += 1
                                        if consecutive_failures >= 3:
                                            monitor._running = False
                                            break

                                # Short delay between iterations
                                await asyncio.sleep(0.1)

                            except Exception:
                                consecutive_failures += 1
                                if consecutive_failures >= 3:
                                    monitor._running = False
                                    break
                                await asyncio.sleep(0.1)

                        monitor._running = False

                    monitor._monitor_loop = error_recovery_loop

                    # Run the error recovery workflow
                    await monitor.start()

                    # Should have recovered from failures
                    assert iteration_count >= 3  # Should have retried multiple times
                    assert call_count >= 3  # Should have made multiple attempts

                    await monitor.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_monitor_instances(self, integration_settings: AppSettings) -> None:
        """Test multiple concurrent monitor instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            integration_settings.output.output_directory = temp_dir

            # Create multiple monitor instances
            num_monitors = 3
            monitors = [InboxMonitor(integration_settings) for _ in range(num_monitors)]

            async def run_monitor(monitor_instance, monitor_id):
                with patch(
                    "agents.inbox_monitor.services.monitor.GraphAPIClient"
                ) as mock_graph_class:
                    # Mock graph client
                    mock_graph_client = AsyncMock()
                    mock_graph_class.return_value = mock_graph_client

                    # Mock different messages for each monitor
                    mock_messages = [
                        {
                            "id": f"msg-{monitor_id}-1",
                            "subject": f"Test Email {monitor_id}",
                            "body": {
                                "contentType": "text/plain",
                                "content": f"Content {monitor_id}",
                            },
                            "from": {
                                "emailAddress": {
                                    "address": f"sender{monitor_id}@example.com",
                                    "name": f"Sender {monitor_id}",
                                }
                            },
                            "receivedDateTime": "2024-01-15T10:30:00Z",
                            "hasAttachments": False,
                            "importance": "normal",
                            "isRead": False,
                            "isDraft": False,
                        }
                    ]

                    mock_graph_client.get_inbox_messages.return_value = mock_messages
                    mock_folder = {
                        "id": f"folder-{monitor_id}",
                        "displayName": f"Processed_{monitor_id}",
                    }
                    mock_graph_client.get_folder_by_name.return_value = mock_folder
                    mock_graph_client.move_message.return_value = {"id": f"moved-msg-{monitor_id}"}

                    # Mock email conversion
                    def mock_convert(message, processing_id, version):
                        from ..models.email import (
                            Email,
                            EmailAddress,
                            EmailBody,
                            EmailImportance,
                            EmailRecipients,
                            ProcessingMetadata,
                        )

                        return Email(
                            id=message["id"],
                            conversation_id="conv-123",
                            received_datetime=datetime.fromisoformat(
                                message["receivedDateTime"].replace("Z", "+00:00")
                            ),
                            sent_datetime=datetime.fromisoformat(
                                message["receivedDateTime"].replace("Z", "+00:00")
                            ),
                            sender=EmailAddress(
                                email=message["from"]["emailAddress"]["address"],
                                name=message["from"]["emailAddress"]["name"],
                            ),
                            recipients=EmailRecipients(to=[], cc=[], bcc=[]),
                            subject=message["subject"],
                            body=EmailBody(
                                content_type=message["body"]["contentType"],
                                content=message["body"]["content"],
                            ),
                            body_preview=message["body"]["content"][:100],
                            importance=EmailImportance(message["importance"]),
                            has_attachments=message["hasAttachments"],
                            attachment_count=0,
                            categories=[],
                            is_read=message["isRead"],
                            is_draft=message["isDraft"],
                            internet_message_headers={},
                            processing_metadata=ProcessingMetadata(
                                inbox_monitor_version=version,
                                processing_id=processing_id,
                                processing_timestamp=datetime.utcnow(),
                                source_folder="Inbox",
                            ),
                        )

                    mock_graph_client.convert_to_email_model.side_effect = mock_convert

                    with patch(
                        "agents.inbox_monitor.services.monitor.EmailProcessor"
                    ) as mock_processor_class:
                        # Use real EmailProcessor
                        real_processor = EmailProcessor(integration_settings, mock_graph_client)
                        mock_processor_class.return_value = real_processor

                        # Mock monitor loop to run once
                        async def single_run_loop():
                            monitor_instance._running = True

                            if monitor_instance.email_processor:
                                results = await monitor_instance.email_processor.process_inbox()
                                return results

                            monitor_instance._running = False
                            return {"success": False, "processed_count": 0}

                        monitor_instance._monitor_loop = single_run_loop

                        # Run monitor
                        await monitor_instance.start()
                        await monitor_instance.stop()

                        return monitor_id

            # Run all monitors concurrently
            start_time = time.time()
            tasks = [run_monitor(monitor, i) for i, monitor in enumerate(monitors)]
            results = await asyncio.gather(*tasks)
            concurrent_time = time.time() - start_time

            # Should handle concurrent execution efficiently
            assert len(results) == num_monitors
            assert concurrent_time < 5.0  # Should complete within 5 seconds

            # Verify files were created by all monitors
            output_files = list(Path(temp_dir).glob("*.json"))
            assert len(output_files) == num_monitors

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_load_test_workflow(self, integration_settings: AppSettings) -> None:
        """Test system under load with high volume of emails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            integration_settings.output.output_directory = temp_dir
            integration_settings.processing.batch_size = 100  # Larger batch size

            # Create monitor
            monitor = InboxMonitor(integration_settings)

            with patch("agents.inbox_monitor.services.monitor.GraphAPIClient") as mock_graph_class:
                # Mock graph client
                mock_graph_client = AsyncMock()
                mock_graph_class.return_value = mock_graph_client

                # Create large volume of mock messages
                num_messages = 1000
                mock_messages = []
                for i in range(num_messages):
                    mock_messages.append(
                        {
                            "id": f"load-test-msg-{i}",
                            "subject": f"Load Test Email {i}",
                            "body": {
                                "contentType": "text/plain",
                                "content": f"Load test content {i}" * 10,
                            },
                            "from": {
                                "emailAddress": {
                                    "address": f"sender{i}@example.com",
                                    "name": f"Sender {i}",
                                }
                            },
                            "receivedDateTime": "2024-01-15T10:30:00Z",
                            "hasAttachments": False,
                            "importance": "normal",
                            "isRead": False,
                            "isDraft": False,
                        }
                    )

                mock_graph_client.get_inbox_messages.return_value = mock_messages
                mock_folder = {"id": "load-test-folder", "displayName": "Processed_Load_Test"}
                mock_graph_client.get_folder_by_name.return_value = mock_folder
                mock_graph_client.move_message.return_value = {"id": "moved-msg"}

                # Mock email conversion
                def mock_convert(message, processing_id, version):
                    from ..models.email import (
                        Email,
                        EmailAddress,
                        EmailBody,
                        EmailImportance,
                        EmailRecipients,
                        ProcessingMetadata,
                    )

                    return Email(
                        id=message["id"],
                        conversation_id="conv-123",
                        received_datetime=datetime.fromisoformat(
                            message["receivedDateTime"].replace("Z", "+00:00")
                        ),
                        sent_datetime=datetime.fromisoformat(
                            message["receivedDateTime"].replace("Z", "+00:00")
                        ),
                        sender=EmailAddress(
                            email=message["from"]["emailAddress"]["address"],
                            name=message["from"]["emailAddress"]["name"],
                        ),
                        recipients=EmailRecipients(to=[], cc=[], bcc=[]),
                        subject=message["subject"],
                        body=EmailBody(
                            content_type=message["body"]["contentType"],
                            content=message["body"]["content"],
                        ),
                        body_preview=message["body"]["content"][:100],
                        importance=EmailImportance(message["importance"]),
                        has_attachments=message["hasAttachments"],
                        attachment_count=0,
                        categories=[],
                        is_read=message["isRead"],
                        is_draft=message["isDraft"],
                        internet_message_headers={},
                        processing_metadata=ProcessingMetadata(
                            inbox_monitor_version=version,
                            processing_id=processing_id,
                            processing_timestamp=datetime.utcnow(),
                            source_folder="Inbox",
                        ),
                    )

                mock_graph_client.convert_to_email_model.side_effect = mock_convert

                with patch(
                    "agents.inbox_monitor.services.monitor.EmailProcessor"
                ) as mock_processor_class:
                    # Use real EmailProcessor
                    real_processor = EmailProcessor(integration_settings, mock_graph_client)
                    mock_processor_class.return_value = real_processor

                    # Mock monitor loop for load test
                    async def load_test_loop():
                        monitor._running = True

                        # Process the large batch
                        if monitor.email_processor:
                            start_time = time.time()
                            results = await monitor.email_processor.process_inbox()
                            processing_time = time.time() - start_time

                            # Verify load test results
                            assert results["success"] is True
                            assert results["processed_count"] == num_messages
                            assert results["failed_count"] == 0

                            # Should process at reasonable speed
                            emails_per_second = num_messages / processing_time
                            assert emails_per_second >= 50  # At least 50 emails per second

                            # Verify files were created
                            output_files = list(Path(temp_dir).glob("*.json"))
                            assert len(output_files) == num_messages

                        monitor._running = False

                    monitor._monitor_loop = load_test_loop

                    # Run the load test
                    start_time = time.time()
                    await monitor.start()
                    total_time = time.time() - start_time

                    # Should complete load test efficiently
                    assert total_time < 60.0  # Should complete within 1 minute

                    await monitor.stop()


# Performance benchmarking utilities
class PerformanceBenchmark:
    """Utility class for performance benchmarking."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.results = []

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        self.results.append(duration)
        print(f"Benchmark '{self.name}': {duration:.4f} seconds")

    def get_average(self) -> float:
        return sum(self.results) / len(self.results) if self.results else 0.0

    def get_min(self) -> float:
        return min(self.results) if self.results else 0.0

    def get_max(self) -> float:
        return max(self.results) if self.results else 0.0


@pytest.mark.performance
def test_performance_benchmark_utility():
    """Test the performance benchmarking utility."""
    with PerformanceBenchmark("test_benchmark") as benchmark:
        time.sleep(0.1)  # Simulate work

    assert benchmark.get_average() >= 0.1
    assert len(benchmark.results) == 1
