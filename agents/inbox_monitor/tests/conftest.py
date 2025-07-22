"""
Test Configuration and Fixtures
================================

Shared pytest fixtures for inbox monitor tests.
"""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from ..config.settings import (
    AppSettings,
    GraphAPISettings,
    LoggingSettings,
    OutputSettings,
    ProcessingSettings,
)
from ..models.email import (
    Email,
    EmailAddress,
    EmailBody,
    EmailImportance,
    EmailRecipients,
    ProcessingMetadata,
)


@pytest.fixture
def mock_settings():
    """Create mock application settings for testing."""
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
            processed_folder_prefix="Processed",
        ),
        logging=LoggingSettings(level="INFO", format="json"),
        output=OutputSettings(storage_type="file", output_directory="./test_output"),
        environment="test",
        dry_run=False,
    )


@pytest.fixture
def mock_graph_message():
    """Create a mock Graph API message."""
    return {
        "id": "test-message-id-123",
        "conversationId": "test-conversation-id",
        "subject": "Test Email Subject",
        "bodyPreview": "This is a test email preview...",
        "body": {
            "contentType": "text/html",
            "content": "<html><body>This is a test email body</body></html>",
        },
        "from": {"emailAddress": {"address": "sender@example.com", "name": "Test Sender"}},
        "toRecipients": [
            {
                "emailAddress": {
                    "address": "recipient@example.com",
                    "name": "Test Recipient",
                }
            }
        ],
        "ccRecipients": [],
        "bccRecipients": [],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "sentDateTime": "2024-01-15T10:29:00Z",
        "hasAttachments": False,
        "importance": "normal",
        "categories": ["Test"],
        "isRead": False,
        "isDraft": False,
        "internetMessageHeaders": [
            {"name": "Message-ID", "value": "<test@example.com>"},
            {"name": "Subject", "value": "Test Email Subject"},
        ],
    }


@pytest.fixture
def mock_email_model():
    """Create a mock Email model."""
    processing_metadata = ProcessingMetadata(
        inbox_monitor_version="1.0.0",
        processing_id=str(uuid.uuid4()),
        processing_timestamp=datetime.utcnow(),
        source_folder="Inbox",
    )

    return Email(
        id="test-message-id-123",
        conversation_id="test-conversation-id",
        received_datetime=datetime.utcnow(),
        sent_datetime=datetime.utcnow(),
        sender=EmailAddress(email="sender@example.com", name="Test Sender"),
        recipients=EmailRecipients(
            to=[EmailAddress(email="recipient@example.com", name="Test Recipient")]
        ),
        subject="Test Email Subject",
        body=EmailBody(
            content_type="text/html",
            content="<html><body>Test email body</body></html>",
        ),
        body_preview="This is a test email preview...",
        importance=EmailImportance.NORMAL,
        has_attachments=False,
        attachment_count=0,
        categories=["Test"],
        is_read=False,
        is_draft=False,
        internet_message_headers={
            "Message-ID": "<test@example.com>",
            "Subject": "Test Email Subject",
        },
        processing_metadata=processing_metadata,
    )


@pytest.fixture
def mock_folder():
    """Create a mock folder response."""
    return {
        "id": "test-folder-id-123",
        "displayName": "Processed_01_2024",
        "parentFolderId": "inbox-folder-id",
        "childFolderCount": 0,
        "unreadItemCount": 0,
        "totalItemCount": 5,
    }


@pytest.fixture
def mock_msal_app():
    """Create a mock MSAL application."""
    mock_app = Mock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "test-access-token",
        "expires_in": 3600,
    }
    return mock_app


@pytest.fixture
def mock_msal_app_error():
    """Create a mock MSAL application that fails."""
    mock_app = Mock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Invalid client credentials",
    }
    return mock_app


@pytest.fixture
def mock_graph_message_minimal():
    """Create a minimal mock Graph API message."""
    return {
        "id": "minimal-message-id",
        "subject": "Minimal Test",
        "body": {"contentType": "text/plain", "content": "Minimal content"},
        "from": {"emailAddress": {"address": "minimal@example.com"}},
        "toRecipients": [],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "hasAttachments": False,
        "importance": "normal",
        "isRead": False,
        "isDraft": False,
    }


@pytest.fixture
def mock_graph_message_with_attachments():
    """Create a mock Graph API message with attachments."""
    return {
        "id": "message-with-attachments",
        "subject": "Email with Attachments",
        "body": {
            "contentType": "text/html",
            "content": "<html><body>Email with attachments</body></html>",
        },
        "from": {
            "emailAddress": {
                "address": "sender@example.com",
                "name": "Sender With Attachments",
            }
        },
        "toRecipients": [
            {"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}
        ],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "sentDateTime": "2024-01-15T10:29:00Z",
        "hasAttachments": True,
        "importance": "high",
        "categories": ["Important", "Work"],
        "isRead": False,
        "isDraft": False,
        "internetMessageHeaders": [
            {"name": "Message-ID", "value": "<attachment-test@example.com>"},
            {"name": "Subject", "value": "Email with Attachments"},
        ],
    }


@pytest.fixture
def mock_graph_message_malformed():
    """Create a malformed mock Graph API message for error testing."""
    return {
        "id": "malformed-message",
        "subject": None,  # Invalid subject
        "body": {
            "contentType": "invalid-type",  # Invalid content type
            "content": "Test content",
        },
        "from": None,  # Missing sender
        "receivedDateTime": "invalid-date",  # Invalid date format
        "hasAttachments": "not-boolean",  # Invalid boolean
        "importance": "super-high",  # Invalid importance
        "isRead": "maybe",  # Invalid boolean
        "isDraft": 1,  # Invalid boolean
    }


@pytest.fixture
async def mock_httpx_client():
    """Create a mock HTTPX client."""
    client = AsyncMock()

    # Mock response
    response = AsyncMock()
    response.status_code = 200
    response.json = Mock(return_value={"value": []})
    response.text = '{"value": []}'

    # Configure client.request to return the response
    client.request.return_value = response
    client.post.return_value = response
    client.get.return_value = response

    return client


@pytest.fixture
def mock_graph_client(mock_settings, mock_msal_app, mock_httpx_client):
    """Create a mock GraphAPIClient."""
    from ..services.graph_api_client import GraphAPIClient

    client = GraphAPIClient(mock_settings.graph_api)
    client.msal_app = mock_msal_app
    client._client = mock_httpx_client

    # Mock methods
    client.get_inbox_messages = AsyncMock(return_value=[])
    client.create_folder = AsyncMock(
        return_value={"id": "test-folder-id", "displayName": "Test Folder"}
    )
    client.get_folder_by_name = AsyncMock(return_value=None)
    client.move_message = AsyncMock(return_value={"id": "test-message-id"})
    client.convert_to_email_model = Mock()

    return client


@pytest.fixture
def mock_graph_client_failing(mock_settings, mock_msal_app_error, mock_httpx_client):
    """Create a mock GraphAPIClient that fails authentication."""
    from ..services.graph_api_client import GraphAPIClient

    client = GraphAPIClient(mock_settings.graph_api)
    client.msal_app = mock_msal_app_error
    client._client = mock_httpx_client

    # Mock methods to fail
    client.get_inbox_messages = AsyncMock(side_effect=Exception("Authentication failed"))
    client.create_folder = AsyncMock(side_effect=Exception("Authentication failed"))
    client.get_folder_by_name = AsyncMock(side_effect=Exception("Authentication failed"))
    client.move_message = AsyncMock(side_effect=Exception("Authentication failed"))

    return client


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
