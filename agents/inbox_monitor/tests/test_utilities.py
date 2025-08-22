"""
Test Utilities and Helpers
============================
Enhanced test utilities, fixtures, and helper functions for comprehensive testing.
"""
import asyncio
import contextlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any
import pytest
from config.settings import (
    AppSettings,
    AzureAIFoundrySettings,
    ContentFormattingSettings,
    DatabricksOAuthSettings,
    GraphAPISettings,
    KeyVaultSettings,
    LoggingSettings,
    MonitoringSettings,
    OutputSettings,
    ProcessingSettings,
    PromptManagementSettings,
    SalesforceSettings,
    ScenarioSettings,
    TestModeSettings,
)
from models.email import (
    Email,
    EmailAddress,
    EmailBody,
    EmailImportance,
    EmailRecipients,
    ProcessingMetadata,
    ProcessingResult,
)
class TestDataFactory:
    """Factory class for creating test data."""
    @staticmethod
    def create_graph_message(
        message_id: str | None = None,
        subject: str | None = None,
        sender_email: str | None = None,
        sender_name: str | None = None,
        content: str | None = None,
        content_type: str = "text/html",
        received_datetime: str | None = None,
        importance: str = "normal",
        has_attachments: bool = False,
        is_read: bool = False,
        is_draft: bool = False,
        to_recipients: list[dict[str, Any]] | None = None,
        cc_recipients: list[dict[str, Any]] | None = None,
        bcc_recipients: list[dict[str, Any]] | None = None,
        categories: list[str] | None = None,
        headers: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a mock Graph API message."""
        message_id = message_id or f"msg-{uuid.uuid4().hex[:8]}"
        subject = subject or f"Test Subject {message_id}"
        sender_email = sender_email or "test@example.com"
        sender_name = sender_name or "Test Sender"
        content = content or f"Test content for {message_id}"
        received_datetime = received_datetime or datetime.now(timezone.utc).isoformat() + "Z"
        message = {
            "id": message_id,
            "conversationId": f"conv-{uuid.uuid4().hex[:8]}",
            "subject": subject,
            "bodyPreview": content[:100],
            "body": {
                "contentType": content_type,
                "content": content,
            },
            "from": {
                "emailAddress": {
                    "address": sender_email,
                    "name": sender_name,
                }
            },
            "toRecipients": to_recipients or [],
            "ccRecipients": cc_recipients or [],
            "bccRecipients": bcc_recipients or [],
            "receivedDateTime": received_datetime,
            "sentDateTime": received_datetime,
            "hasAttachments": has_attachments,
            "importance": importance,
            "categories": categories or [],
            "isRead": is_read,
            "isDraft": is_draft,
            "internetMessageHeaders": headers or [],
        }
        # Add any additional fields from kwargs
        message.update(kwargs)
        return message
    @staticmethod
    def create_email_address(
        email: str | None = None,
        name: str | None = None,
    ) -> EmailAddress:
        """Create an EmailAddress instance."""
        email = email or f"user{uuid.uuid4().hex[:8]}@example.com"
        name = name or f"User {uuid.uuid4().hex[:8]}"
        return EmailAddress(email=email, name=name)
    @staticmethod
    def create_email_body(
        content_type: str = "text/html",
        content: str | None = None,
    ) -> EmailBody:
        """Create an EmailBody instance."""
        content = content or f"<html><body>Test content {uuid.uuid4().hex[:8]}</body></html>"
        return EmailBody(content_type=content_type, content=content)
    @staticmethod
    def create_email_recipients(
        to_count: int = 1,
        cc_count: int = 0,
        bcc_count: int = 0,
    ) -> EmailRecipients:
        """Create EmailRecipients instance."""
        to_recipients = [
            TestDataFactory.create_email_address(f"to{i}@example.com", f"To User {i}")
            for i in range(to_count)
        ]
        cc_recipients = [
            TestDataFactory.create_email_address(f"cc{i}@example.com", f"CC User {i}")
            for i in range(cc_count)
        ]
        bcc_recipients = [
            TestDataFactory.create_email_address(f"bcc{i}@example.com", f"BCC User {i}")
            for i in range(bcc_count)
        ]
        return EmailRecipients(to=to_recipients, cc=cc_recipients, bcc=bcc_recipients)
    @staticmethod
    def create_processing_metadata(
        version: str = "1.0.0",
        process_id: str | None = None,
        source_folder: str = "Inbox",
    ) -> ProcessingMetadata:
        """Create ProcessingMetadata instance."""
        process_id = process_id or str(uuid.uuid4())
        return ProcessingMetadata(
            monitor_version=version,
            process_id=process_id,
            processed_at=datetime.now(timezone.utc),
            source_folder=source_folder,
        )
    @staticmethod
    def create_email_model(
        email_id: str | None = None,
        subject: str | None = None,
        sender_email: str | None = None,
        content: str | None = None,
        importance: EmailImportance = EmailImportance.NORMAL,
        has_attachments: bool = False,
        is_read: bool = False,
        is_draft: bool = False,
        to_count: int = 1,
        cc_count: int = 0,
        bcc_count: int = 0,
        categories: list[str] | None = None,
        headers: dict[str, str] | None = None,
        process_id: str | None = None,
        version: str = "1.0.0",
    ) -> Email:
        """Create a complete Email model instance."""
        email_id = email_id or f"email-{uuid.uuid4().hex[:8]}"
        subject = subject or f"Test Subject {email_id}"
        sender_email = sender_email or "sender@example.com"
        content = content or f"Test content for {email_id}"
        categories = categories or []
        headers = headers or {}
        return Email(
            id=email_id,
            conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
            received_datetime=datetime.now(timezone.utc),
            sent_datetime=datetime.now(timezone.utc),
            sender=TestDataFactory.create_email_address(sender_email, "Test Sender"),
            recipients=TestDataFactory.create_email_recipients(to_count, cc_count, bcc_count),
            subject=subject,
            body=TestDataFactory.create_email_body(content=content),
            email_body=content[:100],
            importance=importance,
            has_attachments=has_attachments,
            attachment_count=1 if has_attachments else 0,
            categories=categories,
            is_read=is_read,
            is_draft=is_draft,
            internet_message_headers=headers,
            processing_metadata=TestDataFactory.create_processing_metadata(
                version=version,
                process_id=process_id,
            ),
        )
    @staticmethod
    def create_processing_result(
        success: bool = True,
        message_id: str | None = None,
        process_id: str | None = None,
        stored_path: str | None = None,
        destination_folder: str | None = None,
        error: str | None = None,
    ) -> ProcessingResult:
        """Create ProcessingResult instance."""
        message_id = message_id or f"msg-{uuid.uuid4().hex[:8]}"
        process_id = process_id or str(uuid.uuid4())
        stored_path = stored_path or f"/tmp/{message_id}.json"
        destination_folder = destination_folder or "Processed_01_2024"
        return ProcessingResult(
            success=success,
            message_id=message_id,
            process_id=process_id,
            stored_path=stored_path,
            destination_folder=destination_folder,
            error=error,
        )
    @staticmethod
    def create_app_settings(
        tenant_id: str = "test-tenant-id",
        client_id: str = "test-client-id",
        client_secret: str = "test-client-secret",
        monitored_email: str = "test@example.com",
        polling_interval: int = 300,
        batch_size: int = 10,
        max_retry_attempts: int = 3,
        retry_delay: int = 30,
        storage_type: str = "file",
        output_directory: str = "./test_output",
        api_endpoint: str | None = None,
        api_key: str | None = None,
        environment: str = "test",
        dry_run: bool = False,
        log_level: str = "INFO",
        log_format: str = "json",
    ) -> AppSettings:
        """Create AppSettings instance."""
        return AppSettings(
            graph_api=GraphAPISettings(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                monitored_email=monitored_email,
            ),
            processing=ProcessingSettings(
                polling_interval_seconds=polling_interval,
                batch_size=batch_size,
                max_retry_attempts=max_retry_attempts,
                retry_delay_seconds=retry_delay,
            ),
            logging=LoggingSettings(level=log_level, format=log_format),
            output=OutputSettings(
                storage_type=storage_type,
                output_directory=output_directory,
                api_endpoint=api_endpoint,
                api_key=api_key,
            ),
            azure_ai_foundry=AzureAIFoundrySettings(
                endpoint="https://test.azureai.com",
                connection_string="test-connection-string"
            ),
            salesforce=SalesforceSettings(
                base_url="https://test.my.salesforce.com",
                client_id="test-client-id",
                client_secret="test-client-secret",
                token_endpoint="https://test.my.salesforce.com/services/oauth2/token",
                case_record_type_id="test-record-type",
                case_queue="test-queue"
            ),
            databricks_oauth=DatabricksOAuthSettings(
                server_hostname="test.databricks.com",
                oauth_client_id="test-oauth-client",
                oauth_client_secret="test-oauth-secret",
                http_path="/sql/1.0/warehouses/test",
                catalog="test_catalog",
                schema_name="test_schema"
            ),
            key_vault=KeyVaultSettings(
                key_vault_url="https://test.vault.azure.net/",
                azure_tenant_id="test-tenant",
                azure_client_id="test-client",
                azure_client_secret="test-secret"
            ),
            scenarios=ScenarioSettings(
                test_email="test@example.com",
                victoria_grant_email="victoria@example.com",
                account_team_email="accountteam@example.com"
            ),
            test_mode=TestModeSettings(
                enabled=True,
                test_email_override="test@example.com",
                test_sender_email="testsender@example.com",
                target_salesforce_email="targettest@example.com"
            ),
            content_formatting=ContentFormattingSettings(
                max_body_length=10000,
                max_subject_length=200,
                truncation_suffix="..."
            ),
            monitoring=MonitoringSettings(
                enabled=True,
                metrics_interval_seconds=60,
                health_check_enabled=True
            ),
            prompt_management=PromptManagementSettings(
                templates_path="./templates",
                cache_duration_minutes=30
            ),
            environment=environment,
            dry_run=dry_run,
        )
    @staticmethod
    def create_batch_of_messages(
        count: int,
        base_id: str = "batch",
        vary_content: bool = True,
        vary_senders: bool = True,
        vary_importance: bool = True,
        include_attachments: bool = False,
    ) -> list[dict[str, Any]]:
        """Create a batch of test messages."""
        messages = []
        importances = ["low", "normal", "high"]
        for i in range(count):
            message_id = f"{base_id}-{i}"
            # Vary content if requested
            if vary_content:
                subject = f"Test Subject {i} - {uuid.uuid4().hex[:8]}"
                content = f"Test content for message {i}. " * (i % 10 + 1)
            else:
                subject = f"Test Subject {i}"
                content = f"Test content for message {i}"
            # Vary senders if requested
            if vary_senders:
                sender_email = f"sender{i}@example.com"
                sender_name = f"Sender {i}"
            else:
                sender_email = "sender@example.com"
                sender_name = "Test Sender"
            # Vary importance if requested
            importance = importances[i % len(importances)] if vary_importance else "normal"
            # Include attachments if requested
            has_attachments = include_attachments and (i % 3 == 0)
            message = TestDataFactory.create_graph_message(
                message_id=message_id,
                subject=subject,
                sender_email=sender_email,
                sender_name=sender_name,
                content=content,
                importance=importance,
                has_attachments=has_attachments,
            )
            messages.append(message)
        return messages
class MockGraphAPIClient:
    """Enhanced mock Graph API client with realistic behavior."""
    def __init__(self, settings: Any | None = None):
        self.settings = settings or TestDataFactory.create_app_settings().graph_api
        self.messages = []
        self.folders = {}
        self.message_moves = []
        self.call_delays = {}
        self.failure_modes = {}
        self.call_counts = {}
        # Default folders
        self.folders["Inbox"] = {"id": "inbox-id", "displayName": "Inbox"}
        self.folders["Sent Items"] = {"id": "sent-id", "displayName": "Sent Items"}
    def set_inbox_messages(self, messages: list[dict[str, Any]]):
        """Set messages that should be returned by get_inbox_messages."""
        self.messages = messages
    def add_folder(self, name: str, folder_id: str | None = None):
        """Add a folder to the mock client."""
        folder_id = folder_id or f"folder-{uuid.uuid4().hex[:8]}"
        self.folders[name] = {"id": folder_id, "displayName": name}
        return self.folders[name]
    def set_call_delay(self, method: str, delay: float):
        """Set artificial delay for method calls."""
        self.call_delays[method] = delay
    def set_failure_mode(self, method: str, exception: Exception, fail_count: int = 1):
        """Set method to fail with exception for specified number of calls."""
        self.failure_modes[method] = {"exception": exception, "fail_count": fail_count}
    async def _apply_delay_and_failures(self, method: str):
        """Apply configured delays and failures."""
        # Apply delay if configured
        if method in self.call_delays:
            await asyncio.sleep(self.call_delays[method])
        # Apply failures if configured
        if method in self.failure_modes:
            failure_info = self.failure_modes[method]
            if failure_info["fail_count"] > 0:
                failure_info["fail_count"] -= 1
                if failure_info["fail_count"] == 0:
                    del self.failure_modes[method]
                raise failure_info["exception"]
        # Track call counts
        self.call_counts[method] = self.call_counts.get(method, 0) + 1
    async def initialize(self):
        """Initialize the client."""
        await self._apply_delay_and_failures("initialize")
    async def cleanup(self):
        """Clean up the client."""
        await self._apply_delay_and_failures("cleanup")
    async def get_inbox_messages(self, limit: int | None = None, filter_query: str | None = None):
        """Get inbox messages."""
        await self._apply_delay_and_failures("get_inbox_messages")
        messages = self.messages.copy()
        if limit:
            messages = messages[:limit]
        return messages
    async def create_folder(self, name: str, parent_folder_id: str | None = None):
        """Create a folder."""
        await self._apply_delay_and_failures("create_folder")
        if name in self.folders:
            raise Exception(f"Folder {name} already exists")
        folder = self.add_folder(name)
        return folder
    async def get_folder_by_name(self, name: str):
        """Get folder by name."""
        await self._apply_delay_and_failures("get_folder_by_name")
        return self.folders.get(name)
    async def move_message(self, message_id: str, folder_id: str):
        """Move message to folder."""
        await self._apply_delay_and_failures("move_message")
        self.message_moves.append({"message_id": message_id, "folder_id": folder_id})
        return {"id": message_id, "parentFolderId": folder_id}
    def convert_to_email_model(self, message: dict[str, Any], process_id: str, version: str):
        """Convert Graph message to Email model."""
        return TestDataFactory.create_email_model(
            email_id=message["id"],
            subject=message.get("subject", ""),
            sender_email=message.get("from", {}).get("emailAddress", {}).get("address", ""),
            content=message.get("body", {}).get("content", ""),
            process_id=process_id,
            version=version,
        )
    async def _make_request(self, method: str, url: str, **kwargs):
        """Make a request to the Graph API."""
        await self._apply_delay_and_failures("_make_request")
        # Return mock response based on URL
        if "/me" in url:
            return {"id": "user-id", "displayName": "Test User"}
        elif "/messages" in url:
            return {"value": self.messages}
        elif "/mailFolders" in url:
            return {"value": list(self.folders.values())}
        else:
            return {"value": []}
    def get_call_count(self, method: str) -> int:
        """Get call count for a method."""
        return self.call_counts.get(method, 0)
    def get_message_moves(self) -> list[dict[str, str]]:
        """Get list of message moves."""
        return self.message_moves.copy()
    def reset_stats(self):
        """Reset call counts and move tracking."""
        self.call_counts.clear()
        self.message_moves.clear()
class MockFileSystem:
    """Mock file system for testing file operations."""
    def __init__(self):
        self.files = {}
        self.directories = set()
        self.permissions = {}
        self.failures = {}
        # Add root directory
        self.directories.add("/")
        self.directories.add("/tmp")
    def create_directory(self, path: str):
        """Create a directory."""
        self.directories.add(path)
    def create_file(self, path: str, content: str):
        """Create a file with content."""
        directory = os.path.dirname(path)
        if directory not in self.directories:
            raise FileNotFoundError(f"Directory {directory} does not exist")
        self.files[path] = content
    def read_file(self, path: str) -> str:
        """Read file content."""
        if path not in self.files:
            raise FileNotFoundError(f"File {path} does not exist")
        return self.files[path]
    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        return path in self.files
    def directory_exists(self, path: str) -> bool:
        """Check if directory exists."""
        return path in self.directories
    def set_permission_error(self, path: str, error: Exception):
        """Set permission error for a path."""
        self.failures[path] = error
    def clear_failures(self):
        """Clear all failure configurations."""
        self.failures.clear()
    def get_file_count(self) -> int:
        """Get total number of files."""
        return len(self.files)
    def get_files_by_pattern(self, pattern: str) -> list[str]:
        """Get files matching a pattern."""
        import fnmatch
        return [path for path in self.files if fnmatch.fnmatch(path, pattern)]
    def get_directory_listing(self, path: str) -> list[str]:
        """Get directory listing."""
        if path not in self.directories:
            raise FileNotFoundError(f"Directory {path} does not exist")
        return [f for f in self.files if os.path.dirname(f) == path]
class AsyncContextManager:
    """Helper for creating async context managers in tests."""
    def __init__(self, return_value=None, exception=None):
        self.return_value = return_value
        self.exception = exception
    async def __aenter__(self):
        if self.exception:
            raise self.exception
        return self.return_value
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
class MockAssertions:
    """Enhanced assertions for testing."""
    @staticmethod
    def assert_email_model_valid(email: Email):
        """Assert that an email model is valid."""
        assert email.id is not None
        assert email.conversation_id is not None
        assert email.received_datetime is not None
        assert email.sender is not None
        assert email.recipients is not None
        assert email.subject is not None
        assert email.body is not None
        assert email.processing_metadata is not None
        assert email.processing_metadata.process_id is not None
        assert email.processing_metadata.monitor_version is not None
        assert email.processing_metadata.processed_at is not None
    @staticmethod
    def assert_processing_result_valid(result: ProcessingResult):
        """Assert that a processing result is valid."""
        assert result.email_id is not None
        if result.success:
            assert result.process_id is not None
            assert result.storage_location is not None
            assert result.error is None
        else:
            assert result.error is not None
    @staticmethod
    def assert_processing_summary_valid(summary: dict[str, Any]):
        """Assert that a processing summary is valid."""
        required_fields = ["success", "processed_count", "failed_count", "errors"]
        for field in required_fields:
            assert field in summary
        assert isinstance(summary["success"], bool)
        assert isinstance(summary["processed_count"], int)
        assert isinstance(summary["failed_count"], int)
        assert isinstance(summary["errors"], list)
        assert summary["processed_count"] >= 0
        assert summary["failed_count"] >= 0
        if summary["success"]:
            assert summary["failed_count"] == 0
        else:
            assert summary["failed_count"] > 0 or len(summary["errors"]) > 0
    @staticmethod
    def assert_health_check_valid(health: dict[str, Any]):
        """Assert that a health check result is valid."""
        required_fields = ["status", "timestamp", "graph_api_connected"]
        for field in required_fields:
            assert field in health
        assert health["status"] in ["healthy", "unhealthy", "stopped"]
        assert isinstance(health["timestamp"], str)
        assert isinstance(health["graph_api_connected"], bool)
        if health["status"] == "unhealthy":
            assert "last_error" in health
            assert health["last_error"] is not None
    @staticmethod
    def assert_performance_acceptable(duration: float, max_duration: float, operation: str):
        """Assert that performance is acceptable."""
        assert (
            duration <= max_duration
        ), f"{operation} took {duration:.3f}s, expected <= {max_duration:.3f}s"
    @staticmethod
    def assert_file_content_valid(file_path: str, expected_fields: list[str] | None = None):
        """Assert that a JSON file contains valid email data."""
        assert os.path.exists(file_path), f"File {file_path} does not exist"
        with open(file_path) as f:
            data = json.load(f)
        # Check basic structure
        assert isinstance(data, dict)
        assert "id" in data
        assert "processing_metadata" in data
        # Check expected fields if provided
        if expected_fields:
            for field in expected_fields:
                assert field in data, f"Field {field} not found in {file_path}"
@contextlib.asynccontextmanager
async def temporary_test_environment():
    """Create a temporary test environment with cleanup."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up test environment
        test_env = {
            "temp_dir": temp_dir,
            "output_dir": os.path.join(temp_dir, "output"),
            "mock_fs": MockFileSystem(),
            "mock_graph_client": MockGraphAPIClient(),
        }
        # Create output directory
        os.makedirs(test_env["output_dir"], exist_ok=True)
        try:
            yield test_env
        finally:
            # Cleanup is handled by tempfile.TemporaryDirectory
            pass
class MockDataManager:
    """Manage test data and scenarios."""
    def __init__(self):
        self.scenarios = {}
        self.test_data = {}
    def add_scenario(self, name: str, description: str, data: dict[str, Any]):
        """Add a test scenario."""
        self.scenarios[name] = {
            "description": description,
            "data": data,
            "created_at": datetime.now(timezone.utc),
        }
    def get_scenario(self, name: str) -> dict[str, Any] | None:
        """Get a test scenario."""
        return self.scenarios.get(name)
    def add_test_data(self, name: str, data: Any):
        """Add test data."""
        self.test_data[name] = data
    def get_test_data(self, name: str) -> Any:
        """Get test data."""
        return self.test_data.get(name)
    def create_email_scenarios(self):
        """Create common email test scenarios."""
        scenarios = {
            "simple_email": {
                "description": "Simple text email",
                "data": TestDataFactory.create_graph_message(
                    subject="Simple Test Email",
                    content="This is a simple test email",
                    content_type="text/plain",
                ),
            },
            "html_email": {
                "description": "HTML email with formatting",
                "data": TestDataFactory.create_graph_message(
                    subject="HTML Test Email",
                    content="<html><body><h1>Test</h1><p>HTML content</p></body></html>",
                    content_type="text/html",
                ),
            },
            "email_with_attachments": {
                "description": "Email with attachments",
                "data": TestDataFactory.create_graph_message(
                    subject="Email with Attachments",
                    content="This email has attachments",
                    has_attachments=True,
                ),
            },
            "high_importance_email": {
                "description": "High importance email",
                "data": TestDataFactory.create_graph_message(
                    subject="URGENT: High Priority",
                    content="This is a high priority email",
                    importance="high",
                ),
            },
            "email_with_unicode": {
                "description": "Email with Unicode characters",
                "data": TestDataFactory.create_graph_message(
                    subject="Unicode Test: 中文字符 émojis 🚀",
                    content="Content with Unicode: русский العربية 😀🎉",
                    sender_email="unicode@测试.com",
                    sender_name="Unicode User 中文",
                ),
            },
            "large_email": {
                "description": "Large email content",
                "data": TestDataFactory.create_graph_message(
                    subject="Large Email Test",
                    content="Large content: " + "X" * 10000,
                    sender_email="large@example.com",
                ),
            },
        }
        for name, scenario in scenarios.items():
            self.add_scenario(name, scenario["description"], scenario["data"])
    def create_error_scenarios(self):
        """Create error test scenarios."""
        scenarios = {
            "malformed_email": {
                "description": "Malformed email data",
                "data": {
                    "id": "malformed-msg",
                    "subject": None,  # Invalid
                    "body": {"contentType": "invalid", "content": "test"},
                    "from": None,  # Invalid
                    "receivedDateTime": "invalid-date",
                },
            },
            "missing_required_fields": {
                "description": "Email missing required fields",
                "data": {
                    "id": "incomplete-msg",
                    # Missing receivedDateTime
                    "subject": "Incomplete Email",
                },
            },
            "invalid_datetime": {
                "description": "Email with invalid datetime",
                "data": {
                    "id": "invalid-date-msg",
                    "subject": "Invalid Date",
                    "receivedDateTime": "2024-13-45T25:99:99Z",
                },
            },
        }
        for name, scenario in scenarios.items():
            self.add_scenario(name, scenario["description"], scenario["data"])
    def create_performance_scenarios(self):
        """Create performance test scenarios."""
        scenarios = {
            "small_batch": {
                "description": "Small batch of emails",
                "data": TestDataFactory.create_batch_of_messages(10),
            },
            "medium_batch": {
                "description": "Medium batch of emails",
                "data": TestDataFactory.create_batch_of_messages(100),
            },
            "large_batch": {
                "description": "Large batch of emails",
                "data": TestDataFactory.create_batch_of_messages(1000),
            },
            "varied_content": {
                "description": "Batch with varied content",
                "data": TestDataFactory.create_batch_of_messages(
                    50, vary_content=True, vary_senders=True, vary_importance=True
                ),
            },
        }
        for name, scenario in scenarios.items():
            self.add_scenario(name, scenario["description"], scenario["data"])
# Global test data manager instance
test_data_manager = MockDataManager()
# Initialize common scenarios
test_data_manager.create_email_scenarios()
test_data_manager.create_error_scenarios()
test_data_manager.create_performance_scenarios()
# Pytest fixtures using the utilities
@pytest.fixture
def data_factory():
    """Provide TestDataFactory instance."""
    return TestDataFactory()
@pytest.fixture
def mock_graph_client():
    """Provide MockGraphAPIClient instance."""
    return MockGraphAPIClient()
@pytest.mark.integration
@pytest.fixture
@pytest.mark.medium
def test_file_system():
    """Provide MockFileSystem instance."""
    return MockFileSystem()
@pytest.mark.integration
@pytest.fixture
@pytest.mark.medium
def test_assertions():
    """Provide MockAssertions instance."""
    return MockAssertions()
@pytest.fixture
def data_manager():
    """Provide TestDataManager instance."""
    return test_data_manager
@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.email
@pytest.fixture
async def test_environment():
    """Provide temporary test environment."""
    async with temporary_test_environment() as env:
        yield env
# Parametrized fixtures for common test scenarios
@pytest.fixture(
    params=[
        "simple_email",
        "html_email",
        "email_with_attachments",
        "high_importance_email",
    ]
)
def email_scenario(request, data_manager):
    """Parametrized fixture for email scenarios."""
    return data_manager.get_scenario(request.param)
@pytest.fixture(
    params=[
        "malformed_email",
        "missing_required_fields",
        "invalid_datetime",
    ]
)
def error_scenario(request, data_manager):
    """Parametrized fixture for error scenarios."""
    return data_manager.get_scenario(request.param)
@pytest.fixture(
    params=[
        "small_batch",
        "medium_batch",
        "large_batch",
    ]
)
def performance_scenario(request, data_manager):
    """Parametrized fixture for performance scenarios."""
    return data_manager.get_scenario(request.param)
# Test marker applications for utilities module
# All tests in this module are marked with appropriate performance and functional markers

@pytest.mark.fast
class TestTestDataFactory:
    """Test the TestDataFactory class."""
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_graph_message_defaults(self):
        """Test creating graph message with defaults."""
        factory = TestDataFactory()
        message = factory.create_graph_message()
        assert "id" in message
        assert "subject" in message
        assert "body" in message
        assert message["body"]["contentType"] == "text/html"
        assert message["hasAttachments"] is False
        assert message["importance"] == "normal"
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_email_address_defaults(self):
        """Test creating email address with defaults."""
        factory = TestDataFactory()
        address = factory.create_email_address()
        assert "@example.com" in address.email
        assert address.name is not None
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_batch_of_messages(self):
        """Test creating batch of messages."""
        factory = TestDataFactory()
        messages = factory.create_batch_of_messages(5)
        assert len(messages) == 5
        assert all("id" in msg for msg in messages)
        assert all("subject" in msg for msg in messages)
    @pytest.mark.fast
    class TestMockGraphAPIClient:
        """Test the MockGraphAPIClient class."""
        
        @pytest.mark.fast
        @pytest.mark.unit
        def test_client_initialization(self):
            """Test mock client initialization."""
            client = MockGraphAPIClient()
            assert "Inbox" in client.folders
            assert "Sent Items" in client.folders
            assert len(client.messages) == 0
            assert len(client.call_counts) == 0
        
        @pytest.mark.fast
        @pytest.mark.integration
        async def test_get_inbox_messages(self):
            """Test getting inbox messages."""
            client = MockGraphAPIClient()
            test_messages = [{"id": "msg1", "subject": "Test"}]
            client.set_inbox_messages(test_messages)
            messages = await client.get_inbox_messages()
            assert len(messages) == 1
            assert messages[0]["id"] == "msg1"
            assert client.get_call_count("get_inbox_messages") == 1
    
        @pytest.mark.fast
        @pytest.mark.integration  
        async def test_failure_modes(self):
            """Test client failure simulation."""
            client = MockGraphAPIClient()
            test_exception = Exception("Test failure")
            client.set_failure_mode("get_inbox_messages", test_exception, 1)
            with pytest.raises(Exception, match="Test failure"):
                await client.get_inbox_messages()
            # Should work on second call
            messages = await client.get_inbox_messages()
            assert messages == []
@pytest.mark.fast
class TestMockFileSystem:
    """Test the MockFileSystem class."""
    @pytest.mark.fast
    @pytest.mark.unit
    def test_file_operations(self):
        """Test basic file operations."""
        fs = MockFileSystem()
        # Test directory operations
        fs.create_directory("/test")
        assert fs.directory_exists("/test")
        # Test file operations
        fs.create_file("/test/file.txt", "content")
        assert fs.file_exists("/test/file.txt")
        assert fs.read_file("/test/file.txt") == "content"
    


    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.unit
    def test_file_not_found_errors(self):
        """Test file system error conditions."""
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.read_file("/nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            fs.create_file("/nonexistent/file.txt", "content")
@pytest.mark.fast
@pytest.mark.unit
class TestMockAssertions:
    """Test the MockAssertions utility class."""
    
    @pytest.mark.fast
    @pytest.mark.email
    @pytest.mark.unit
    def test_email_model_validation(self, mock_email_model):
        """Test email model validation."""
        assertions = MockAssertions()
        # Should not raise for valid email
        assertions.assert_email_model_valid(mock_email_model)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_processing_result_validation(self):
        """Test processing result validation."""
        assertions = MockAssertions()
        # Test successful result
        success_result = ProcessingResult(
            success=True,
            email_id="test-msg",
            process_id="test-proc",
            processing_duration_ms=100,
            storage_location="/test/path"
        )
        assertions.assert_processing_result_valid(success_result)
        # Test failure result
        failure_result = ProcessingResult(
            success=False,
            email_id="test-msg",
            process_id="test-proc-fail",
            processing_duration_ms=50,
            error="Test error"
        )
        assertions.assert_processing_result_valid(failure_result)
class TestMockDataManager:
    """Test the MockDataManager class."""


    @pytest.mark.fast
    @pytest.mark.integration
    def test_scenario_management(self):
        """Test adding and retrieving scenarios."""
        manager = MockDataManager()
        test_data = {"key": "value"}
        manager.add_scenario("test_scenario", "Test description", test_data)
        scenario = manager.get_scenario("test_scenario")
        assert scenario is not None
        assert scenario["description"] == "Test description"
        assert scenario["data"] == test_data



    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.email
    def test_email_scenarios_creation(self):
        """Test creating email scenarios."""
        manager = MockDataManager()
        manager.create_email_scenarios()
        scenarios = ["simple_email", "html_email", "email_with_attachments", "high_importance_email"]
        for scenario_name in scenarios:
            scenario = manager.get_scenario(scenario_name)
            assert scenario is not None
            assert "data" in scenario
            assert "description" in scenario
@pytest.mark.fast
@pytest.mark.integration
class TestTemporaryEnvironment:
    """Test the temporary test environment context manager."""
    
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_environment_creation(self):
        """Test creating temporary test environment."""
        async with temporary_test_environment() as env:
            assert "temp_dir" in env
            assert "output_dir" in env
            assert "mock_fs" in env
            assert "mock_graph_client" in env
            assert os.path.exists(env["temp_dir"])
            assert os.path.exists(env["output_dir"])
            assert isinstance(env["mock_fs"], MockFileSystem)
            assert isinstance(env["mock_graph_client"], MockGraphAPIClient)
# Apply markers to existing parametrized fixture tests
pytest.param = pytest.mark.fast(pytest.param)
pytest.param = pytest.mark.integration(pytest.param)