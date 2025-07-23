"""
Comprehensive GraphAPIClient Tests
===================================

Complete unit tests for GraphAPIClient with edge cases and error conditions.
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from msal import ConfidentialClientApplication

from ..config.settings import GraphAPISettings
from ..models.email import (
    EmailImportance,
)
from ..services.graph_api_client import GraphAPIClient


class TestGraphAPIClientUnit:
    """Comprehensive unit tests for GraphAPIClient class."""

    @pytest.fixture
    def graph_settings(self) -> GraphAPISettings:
        """Create GraphAPISettings for testing."""
        return GraphAPISettings(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            monitored_email="test@example.com",
            authority_url="https://login.microsoftonline.com",
            graph_api_endpoint="https://graph.microsoft.com/v1.0",
            scopes=["https://graph.microsoft.com/.default"],
        )

    @pytest.fixture
    def graph_client(self, graph_settings: GraphAPISettings) -> GraphAPIClient:
        """Create GraphAPIClient instance."""
        return GraphAPIClient(graph_settings)

    @pytest.fixture
    def mock_msal_app(self) -> Mock:
        """Create mock MSAL application."""
        mock_app = Mock()
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "test-access-token",
            "expires_in": 3600,
        }
        return mock_app

    @pytest.fixture
    def mock_msal_app_error(self) -> Mock:
        """Create mock MSAL application that returns error."""
        mock_app = Mock()
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials",
        }
        return mock_app

    @pytest.fixture
    def mock_httpx_client(self) -> AsyncMock:
        """Create mock aiohttp session."""
        session = AsyncMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={"value": []})
        response.text = AsyncMock(return_value='{"value": []}')

        session.request.return_value.__aenter__.return_value = response
        return session

    def test_init_graph_client(self, graph_settings: GraphAPISettings) -> None:
        """Test GraphAPIClient initialization."""
        client = GraphAPIClient(graph_settings)

        assert client.settings == graph_settings
        assert client.logger is not None
        assert client.msal_app is not None
        assert isinstance(client.msal_app, ConfidentialClientApplication)
        assert client._token_cache is None
        assert client._session is None

    def test_init_graph_client_with_different_settings(self) -> None:
        """Test GraphAPIClient initialization with different settings."""
        custom_settings = GraphAPISettings(
            tenant_id="custom-tenant",
            client_id="custom-client",
            client_secret="custom-secret",
            monitored_email="custom@example.com",
            authority_url="https://custom.authority.com",
            graph_api_endpoint="https://custom.graph.com/v1.0",
            scopes=["custom.scope"],
        )

        client = GraphAPIClient(custom_settings)

        assert client.settings.tenant_id == "custom-tenant"
        assert client.settings.authority_url == "https://custom.authority.com"
        assert client.settings.scopes == ["custom.scope"]

    @pytest.mark.asyncio
    async def test_async_context_manager(self, graph_client: GraphAPIClient) -> None:
        """Test async context manager functionality."""
        with patch.object(graph_client, "initialize") as mock_init:
            with patch.object(graph_client, "cleanup") as mock_cleanup:
                async with graph_client as client:
                    assert client is graph_client
                    mock_init.assert_called_once()

                mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_success(self, graph_client: GraphAPIClient) -> None:
        """Test successful client initialization."""
        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            await graph_client.initialize()

            assert graph_client._client == mock_session
            mock_session_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_success(self, graph_client: GraphAPIClient) -> None:
        """Test successful client cleanup."""
        mock_session = AsyncMock()
        graph_client._client = mock_session

        await graph_client.cleanup()

        mock_session.close.assert_called_once()
        assert graph_client._client is None

    @pytest.mark.asyncio
    async def test_cleanup_with_none_session(self, graph_client: GraphAPIClient) -> None:
        """Test cleanup when session is None."""
        graph_client._client = None

        # Should not raise exception
        await graph_client.cleanup()

        assert graph_client._client is None

    def test_get_access_token_success(
        self, graph_client: GraphAPIClient, mock_msal_app: Mock
    ) -> None:
        """Test successful token acquisition."""
        graph_client.msal_app = mock_msal_app

        token = graph_client._get_access_token()

        assert token == "test-access-token"
        mock_msal_app.acquire_token_for_client.assert_called_once_with(
            scopes=graph_client.settings.scopes
        )

    def test_get_access_token_from_cache(
        self, graph_client: GraphAPIClient, mock_msal_app: Mock
    ) -> None:
        """Test token retrieval from cache."""
        graph_client.msal_app = mock_msal_app

        # Set up cache with valid token
        future_time = datetime.utcnow() + timedelta(hours=1)
        graph_client._token_cache = {
            "access_token": "cached-token",
            "expires_at": future_time.timestamp(),
        }

        token = graph_client._get_access_token()

        assert token == "cached-token"
        # Should not call MSAL app since token is cached
        mock_msal_app.acquire_token_for_client.assert_not_called()

    def test_get_access_token_cache_expired(
        self, graph_client: GraphAPIClient, mock_msal_app: Mock
    ) -> None:
        """Test token acquisition when cache is expired."""
        graph_client.msal_app = mock_msal_app

        # Set up cache with expired token
        past_time = datetime.utcnow() - timedelta(hours=1)
        graph_client._token_cache = {
            "access_token": "expired-token",
            "expires_at": past_time.timestamp(),
        }

        token = graph_client._get_access_token()

        assert token == "test-access-token"
        # Should call MSAL app since token is expired
        mock_msal_app.acquire_token_for_client.assert_called_once()

    def test_get_access_token_error(
        self, graph_client: GraphAPIClient, mock_msal_app_error: Mock
    ) -> None:
        """Test token acquisition with error response."""
        graph_client.msal_app = mock_msal_app_error

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    def test_get_access_token_msal_exception(self, graph_client: GraphAPIClient) -> None:
        """Test token acquisition when MSAL raises exception."""
        graph_client.msal_app.acquire_token_for_client.side_effect = Exception("MSAL error")

        with pytest.raises(Exception, match="MSAL error"):
            graph_client._get_access_token()

    def test_get_access_token_caching_logic(
        self, graph_client: GraphAPIClient, mock_msal_app: Mock
    ) -> None:
        """Test token caching logic."""
        graph_client.msal_app = mock_msal_app

        # Mock datetime.utcnow to control cache expiration
        with patch("agents.inbox_monitor.services.graph_api_client.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)

            token = graph_client._get_access_token()

            assert token == "test-access-token"
            assert graph_client._token_cache is not None
            assert graph_client._token_cache["access_token"] == "test-access-token"
            # Should expire 5 minutes before actual expiry
            expected_expiry = datetime(2024, 1, 1, 12, 0, 0).timestamp() + 3600 - 300
            assert graph_client._token_cache["expires_at"] == expected_expiry

    @pytest.mark.asyncio
    async def test_make_request_success(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test successful API request."""
        graph_client._client = mock_httpx_client

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client._make_request("GET", "/test")

        assert result == {"value": []}
        mock_httpx_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_without_session(self, graph_client: GraphAPIClient) -> None:
        """Test API request without initialized session."""
        graph_client._client = None

        with pytest.raises(Exception, match="Client not initialized"):
            await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_http_error(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test API request with HTTP error."""
        graph_client._client = mock_httpx_client

        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text.return_value = "Not Found"
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 404"):
                await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_timeout(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test API request with timeout."""
        graph_client._client = mock_httpx_client
        mock_httpx_client.request.side_effect = asyncio.TimeoutError("Request timeout")

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(asyncio.TimeoutError):
                await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_connection_error(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test API request with connection error."""
        graph_client._client = mock_httpx_client
        mock_httpx_client.request.side_effect = httpx.ConnectError("Connection failed")

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(httpx.ConnectError):
                await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_json_decode_error(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test API request with JSON decode error."""
        graph_client._client = mock_httpx_client

        # Mock response with invalid JSON
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text.return_value = "Invalid JSON"
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(json.JSONDecodeError):
                await graph_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_with_post_data(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test API request with POST data."""
        graph_client._client = mock_httpx_client
        post_data = {"key": "value"}

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            await graph_client._make_request("POST", "/test", data=post_data)

        # Verify POST request was made with correct data
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "POST"  # Method
        assert call_args[1]["json"] == post_data  # Data

    @pytest.mark.asyncio
    async def test_get_inbox_messages_success(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test successful inbox messages retrieval."""
        graph_client._client = mock_httpx_client

        mock_messages = [
            {"id": "msg-1", "subject": "Test 1"},
            {"id": "msg-2", "subject": "Test 2"},
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"value": mock_messages}
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.get_inbox_messages()

        assert result == mock_messages
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_inbox_messages_with_limit(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test inbox messages retrieval with limit."""
        graph_client._client = mock_httpx_client

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"value": []}
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            await graph_client.get_inbox_messages(limit=5)

        # Verify limit was included in request
        call_args = mock_httpx_client.request.call_args
        assert "$top=5" in call_args[0][1]  # URL should contain top parameter

    @pytest.mark.asyncio
    async def test_get_inbox_messages_empty_response(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test inbox messages retrieval with empty response."""
        graph_client._client = mock_httpx_client

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {}  # Missing 'value' key
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.get_inbox_messages()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_inbox_messages_with_filter(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test inbox messages retrieval with filter."""
        graph_client._client = mock_httpx_client

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"value": []}
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            await graph_client.get_inbox_messages(filter_query="isRead eq false")

        # Verify filter was included in request
        call_args = mock_httpx_client.request.call_args
        assert "$filter=isRead%20eq%20false" in call_args[0][1]  # URL should contain filter

    @pytest.mark.asyncio
    async def test_create_folder_success(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test successful folder creation."""
        graph_client._client = mock_httpx_client

        mock_folder = {"id": "folder-123", "displayName": "Test Folder"}
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json.return_value = mock_folder
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.create_folder("Test Folder")

        assert result == mock_folder

        # Verify POST request was made with correct data
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json"]["displayName"] == "Test Folder"

    @pytest.mark.asyncio
    async def test_create_folder_with_parent(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test folder creation with parent folder."""
        graph_client._client = mock_httpx_client

        mock_folder = {"id": "folder-123", "displayName": "Test Folder"}
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json.return_value = mock_folder
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.create_folder("Test Folder", parent_folder_id="parent-123")

        assert result == mock_folder

        # Verify URL contains parent folder ID
        call_args = mock_httpx_client.request.call_args
        assert "parent-123" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_create_folder_conflict(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test folder creation with conflict (folder already exists)."""
        graph_client._client = mock_httpx_client

        mock_response = AsyncMock()
        mock_response.status = 409
        mock_response.text.return_value = "Folder already exists"
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 409"):
                await graph_client.create_folder("Test Folder")

    @pytest.mark.asyncio
    async def test_get_folder_by_name_success(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test successful folder retrieval by name."""
        graph_client._client = mock_httpx_client

        mock_folder = {"id": "folder-123", "displayName": "Test Folder"}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"value": [mock_folder]}
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.get_folder_by_name("Test Folder")

        assert result == mock_folder

        # Verify filter was used in request
        call_args = mock_httpx_client.request.call_args
        assert "$filter=displayName%20eq%20%27Test%20Folder%27" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_folder_by_name_not_found(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test folder retrieval when folder not found."""
        graph_client._client = mock_httpx_client

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"value": []}  # Empty result
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.get_folder_by_name("Nonexistent Folder")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_folder_by_name_multiple_results(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test folder retrieval with multiple results (returns first)."""
        graph_client._client = mock_httpx_client

        mock_folders = [
            {"id": "folder-1", "displayName": "Test Folder"},
            {"id": "folder-2", "displayName": "Test Folder"},
        ]
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"value": mock_folders}
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.get_folder_by_name("Test Folder")

        assert result == mock_folders[0]  # Should return first match

    @pytest.mark.asyncio
    async def test_move_message_success(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test successful message move."""
        graph_client._client = mock_httpx_client

        mock_message = {"id": "msg-123", "parentFolderId": "new-folder-id"}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_message
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client.move_message("msg-123", "new-folder-id")

        assert result == mock_message

        # Verify PATCH request was made with correct data
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "PATCH"
        assert call_args[1]["json"]["parentFolderId"] == "new-folder-id"

    @pytest.mark.asyncio
    async def test_move_message_not_found(
        self, graph_client: GraphAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test message move when message not found."""
        graph_client._client = mock_httpx_client

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text.return_value = "Message not found"
        mock_httpx_client.request.return_value.__aenter__.return_value = mock_response

        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            with pytest.raises(Exception, match="Graph API request failed: 404"):
                await graph_client.move_message("nonexistent-msg", "folder-id")

    def test_parse_email_address_complete(self, graph_client: GraphAPIClient) -> None:
        """Test parsing complete email address."""
        address_data = {"emailAddress": {"address": "test@example.com", "name": "Test User"}}

        result = graph_client._parse_email_address(address_data)

        assert result.email == "test@example.com"
        assert result.name == "Test User"

    def test_parse_email_address_minimal(self, graph_client: GraphAPIClient) -> None:
        """Test parsing minimal email address."""
        address_data = {"emailAddress": {"address": "test@example.com"}}

        result = graph_client._parse_email_address(address_data)

        assert result.email == "test@example.com"
        assert result.name is None

    def test_parse_email_address_empty(self, graph_client: GraphAPIClient) -> None:
        """Test parsing empty email address."""
        address_data = {"emailAddress": {"address": "", "name": ""}}

        result = graph_client._parse_email_address(address_data)

        assert result.email == ""
        assert result.name == ""

    def test_parse_email_address_missing_structure(self, graph_client: GraphAPIClient) -> None:
        """Test parsing email address with missing structure."""
        address_data = {}

        result = graph_client._parse_email_address(address_data)

        assert result.email == ""
        assert result.name is None

    def test_parse_email_address_none_values(self, graph_client: GraphAPIClient) -> None:
        """Test parsing email address with None values."""
        address_data = {"emailAddress": {"address": None, "name": None}}

        result = graph_client._parse_email_address(address_data)

        assert result.email is None
        assert result.name is None

    def test_parse_email_address_malformed(self, graph_client: GraphAPIClient) -> None:
        """Test parsing malformed email address."""
        address_data = {"emailAddress": None}

        with pytest.raises(TypeError):
            graph_client._parse_email_address(address_data)

    def test_parse_importance_valid_values(self, graph_client: GraphAPIClient) -> None:
        """Test parsing valid importance values."""
        test_cases = [
            ("low", EmailImportance.LOW),
            ("normal", EmailImportance.NORMAL),
            ("high", EmailImportance.HIGH),
            ("LOW", EmailImportance.LOW),
            ("NORMAL", EmailImportance.NORMAL),
            ("HIGH", EmailImportance.HIGH),
        ]

        for input_value, expected in test_cases:
            result = graph_client._parse_importance(input_value)
            assert result == expected

    def test_parse_importance_invalid_values(self, graph_client: GraphAPIClient) -> None:
        """Test parsing invalid importance values."""
        invalid_values = [None, "", "invalid", "critical", "medium", 123, []]

        for invalid_value in invalid_values:
            result = graph_client._parse_importance(invalid_value)
            assert result == EmailImportance.NORMAL

    def test_parse_datetime_valid(self, graph_client: GraphAPIClient) -> None:
        """Test parsing valid datetime strings."""
        test_cases = [
            "2024-01-15T10:30:00Z",
            "2024-01-15T10:30:00.123Z",
            "2024-12-31T23:59:59Z",
        ]

        for datetime_str in test_cases:
            result = graph_client._parse_datetime(datetime_str)
            assert isinstance(result, datetime)

    def test_parse_datetime_invalid(self, graph_client: GraphAPIClient) -> None:
        """Test parsing invalid datetime strings."""
        invalid_values = [
            "invalid-date",
            "2024-13-01T10:30:00Z",  # Invalid month
            "2024-01-32T10:30:00Z",  # Invalid day
            "2024-01-15T25:30:00Z",  # Invalid hour
            "",
            None,
        ]

        for invalid_value in invalid_values:
            with pytest.raises(ValueError):
                graph_client._parse_datetime(invalid_value)

    def test_convert_to_email_model_complete(self, graph_client: GraphAPIClient) -> None:
        """Test converting complete Graph message to email model."""
        graph_message = {
            "id": "msg-123",
            "conversationId": "conv-123",
            "subject": "Test Subject",
            "bodyPreview": "Test preview",
            "body": {"contentType": "text/html", "content": "<html><body>Test</body></html>"},
            "from": {"emailAddress": {"address": "sender@example.com", "name": "Sender Name"}},
            "toRecipients": [{"emailAddress": {"address": "to@example.com", "name": "To Name"}}],
            "ccRecipients": [{"emailAddress": {"address": "cc@example.com", "name": "CC Name"}}],
            "bccRecipients": [],
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "sentDateTime": "2024-01-15T10:29:00Z",
            "hasAttachments": True,
            "importance": "high",
            "categories": ["Work", "Important"],
            "isRead": False,
            "isDraft": False,
            "internetMessageHeaders": [
                {"name": "Message-ID", "value": "<test@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
            ],
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert email.id == "msg-123"
        assert email.conversation_id == "conv-123"
        assert email.subject == "Test Subject"
        assert email.body_preview == "Test preview"
        assert email.body.content_type == "text/html"
        assert email.body.content == "<html><body>Test</body></html>"
        assert email.sender.email == "sender@example.com"
        assert email.sender.name == "Sender Name"
        assert len(email.recipients.to) == 1
        assert email.recipients.to[0].email == "to@example.com"
        assert len(email.recipients.cc) == 1
        assert email.recipients.cc[0].email == "cc@example.com"
        assert len(email.recipients.bcc) == 0
        assert email.has_attachments is True
        assert email.importance == EmailImportance.HIGH
        assert email.categories == ["Work", "Important"]
        assert email.is_read is False
        assert email.is_draft is False
        assert email.internet_message_headers["Message-ID"] == "<test@example.com>"
        assert email.processing_metadata.processing_id == "proc-123"
        assert email.processing_metadata.inbox_monitor_version == "1.0.0"

    def test_convert_to_email_model_minimal(self, graph_client: GraphAPIClient) -> None:
        """Test converting minimal Graph message to email model."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert email.id == "msg-123"
        assert email.conversation_id == ""
        assert email.subject == ""
        assert email.body_preview == ""
        assert email.body.content_type == "text/plain"
        assert email.body.content == ""
        assert email.sender.email == ""
        assert email.sender.name is None
        assert len(email.recipients.to) == 0
        assert len(email.recipients.cc) == 0
        assert len(email.recipients.bcc) == 0
        assert email.has_attachments is False
        assert email.importance == EmailImportance.NORMAL
        assert email.categories == []
        assert email.is_read is False
        assert email.is_draft is False
        assert email.internet_message_headers == {}

    def test_convert_to_email_model_missing_required_field(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test converting Graph message missing required fields."""
        graph_message = {
            "id": "msg-123"
            # Missing receivedDateTime
        }

        with pytest.raises(KeyError):
            graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

    def test_convert_to_email_model_invalid_datetime(self, graph_client: GraphAPIClient) -> None:
        """Test converting Graph message with invalid datetime."""
        graph_message = {"id": "msg-123", "receivedDateTime": "invalid-datetime"}

        with pytest.raises(ValueError):
            graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

    def test_convert_to_email_model_attachment_count(self, graph_client: GraphAPIClient) -> None:
        """Test email model conversion with attachment count calculation."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": True,
            "attachments": [
                {"id": "att-1", "name": "file1.txt"},
                {"id": "att-2", "name": "file2.pdf"},
            ],
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert email.has_attachments is True
        assert email.attachment_count == 2

    def test_convert_to_email_model_no_attachments(self, graph_client: GraphAPIClient) -> None:
        """Test email model conversion with no attachments."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False,
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert email.has_attachments is False
        assert email.attachment_count == 0

    def test_convert_to_email_model_internet_headers(self, graph_client: GraphAPIClient) -> None:
        """Test email model conversion with internet message headers."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "internetMessageHeaders": [
                {"name": "Message-ID", "value": "<test@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "sender@example.com"},
            ],
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        expected_headers = {
            "Message-ID": "<test@example.com>",
            "Subject": "Test Subject",
            "From": "sender@example.com",
        }

        assert email.internet_message_headers == expected_headers

    def test_convert_to_email_model_empty_headers(self, graph_client: GraphAPIClient) -> None:
        """Test email model conversion with empty internet headers."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "internetMessageHeaders": [],
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-123", "1.0.0")

        assert email.internet_message_headers == {}

    def test_convert_to_email_model_with_processing_metadata(
        self, graph_client: GraphAPIClient
    ) -> None:
        """Test email model conversion with processing metadata."""
        graph_message = {
            "id": "msg-123",
            "receivedDateTime": "2024-01-15T10:30:00Z",
        }

        email = graph_client.convert_to_email_model(graph_message, "proc-456", "2.0.0")

        assert email.processing_metadata.processing_id == "proc-456"
        assert email.processing_metadata.inbox_monitor_version == "2.0.0"
        assert email.processing_metadata.source_folder == "Inbox"
        assert isinstance(email.processing_metadata.processing_timestamp, datetime)
