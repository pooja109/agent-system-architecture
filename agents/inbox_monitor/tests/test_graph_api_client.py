"""
Tests for Graph API Client
==========================

Unit tests for Microsoft Graph API client.
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ..config.settings import GraphAPISettings
from ..models.email import EmailImportance
from ..services.graph_api_client import GraphAPIClient


class TestGraphAPIClient:
    """Test GraphAPIClient class."""

    @pytest.fixture
    def graph_settings(self):
        """Create test Graph API settings."""
        return GraphAPISettings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            monitored_email="test@example.com",
        )

    @pytest.fixture
    def graph_client(self, graph_settings, mock_msal_app):
        """Create Graph API client with mocked MSAL."""
        with patch(
            "agents.inbox_monitor.services.graph_api_client.ConfidentialClientApplication"
        ) as mock_msal:
            mock_msal.return_value = mock_msal_app
            client = GraphAPIClient(graph_settings)
            client.msal_app = mock_msal_app  # Ensure the mock is set
            return client

    @pytest.mark.asyncio
    async def test_initialize_cleanup(self, graph_client):
        """Test client initialization and cleanup."""
        await graph_client.initialize()
        assert graph_client._client is not None
        assert isinstance(graph_client._client, httpx.AsyncClient)

        await graph_client.cleanup()
        assert graph_client._client is None

    @pytest.mark.asyncio
    async def test_context_manager(self, graph_client):
        """Test using client as async context manager."""
        async with graph_client as client:
            assert client._client is not None
        assert graph_client._client is None

    def test_get_access_token_cached(self, graph_client):
        """Test getting cached access token."""
        # Set up cache
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.timestamp.return_value = 1000
            graph_client._token_cache = {
                "access_token": "cached-token",
                "expires_at": 2000,  # Future timestamp
            }

            token = graph_client._get_access_token()

        assert token == "cached-token"
        # Should not call MSAL
        graph_client.msal_app.acquire_token_for_client.assert_not_called()

    def test_get_access_token_new(self, graph_client):
        """Test acquiring new access token."""
        graph_client._token_cache = None

        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.timestamp.return_value = 1000
            token = graph_client._get_access_token()

        assert token == "test-access-token"
        graph_client.msal_app.acquire_token_for_client.assert_called_once_with(
            scopes=["https://graph.microsoft.com/.default"]
        )

    def test_get_access_token_error(self, graph_client):
        """Test error handling when acquiring token fails."""
        graph_client.msal_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials",
        }

        with pytest.raises(Exception, match="Failed to acquire token"):
            graph_client._get_access_token()

    @pytest.mark.asyncio
    async def test_make_request_success(self, graph_client, mock_httpx_client):
        """Test successful API request."""
        graph_client._client = mock_httpx_client

        # Configure mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"id": "123", "name": "Test"})
        mock_response.text = '{"id": "123", "name": "Test"}'

        mock_httpx_client.request.return_value = mock_response

        # Mock _get_access_token to avoid MSAL calls
        with patch.object(graph_client, "_get_access_token", return_value="test-token"):
            result = await graph_client._make_request("GET", "/test/endpoint")

        assert result == {"id": "123", "name": "Test"}
        mock_httpx_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_error(self, graph_client, mock_httpx_client):
        """Test API request error handling."""
        graph_client._client = mock_httpx_client

        # Configure mock error response
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "Bad request"}'

        mock_httpx_client.request.return_value = mock_response

        with pytest.raises(Exception, match="Graph API request failed: 400"):
            await graph_client._make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_get_inbox_messages(self, graph_client, mock_httpx_client, mock_graph_message):
        """Test getting inbox messages."""
        graph_client._client = mock_httpx_client

        # Configure mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"value": [mock_graph_message]})
        mock_response.text = '{"value": []}'

        mock_httpx_client.request.return_value = mock_response

        messages = await graph_client.get_inbox_messages(limit=5)

        assert len(messages) == 1
        assert messages[0]["id"] == "test-message-id-123"

        # Verify request parameters
        call_args = mock_httpx_client.request.call_args
        assert call_args[1]["params"]["$top"] == 5
        assert "$orderby" in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_create_folder_success(self, graph_client, mock_httpx_client, mock_folder):
        """Test creating a new folder."""
        graph_client._client = mock_httpx_client

        # Configure mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=mock_folder)
        mock_response.text = "{}"

        mock_httpx_client.request.return_value = mock_response

        folder = await graph_client.create_folder("Test Folder")

        assert folder["id"] == "test-folder-id-123"
        assert folder["displayName"] == "Processed_01_2024"

    @pytest.mark.asyncio
    async def test_create_folder_already_exists(self, graph_client, mock_httpx_client, mock_folder):
        """Test creating folder that already exists."""
        graph_client._client = mock_httpx_client

        # First call fails with "already exists"
        mock_error_response = AsyncMock()
        mock_error_response.status_code = 400
        mock_error_response.text = '{"error": "Folder already exists"}'

        mock_httpx_client.request.return_value = mock_error_response

        # Mock get_folder_by_name to return existing folder
        with patch.object(
            graph_client, "get_folder_by_name", return_value=mock_folder
        ) as mock_get_folder:
            folder = await graph_client.create_folder("Test Folder")

        assert folder == mock_folder
        mock_get_folder.assert_called_once_with("Test Folder")

    @pytest.mark.asyncio
    async def test_move_message(self, graph_client, mock_httpx_client):
        """Test moving a message to another folder."""
        graph_client._client = mock_httpx_client

        # Configure mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"id": "moved-message-id"})
        mock_response.text = "{}"

        mock_httpx_client.request.return_value = mock_response

        result = await graph_client.move_message("message-123", "folder-456")

        assert result["id"] == "moved-message-id"

        # Verify request
        call_args = mock_httpx_client.request.call_args
        assert call_args[1]["json"]["destinationId"] == "folder-456"

    def test_parse_email_address(self, graph_client):
        """Test parsing email address from Graph API format."""
        address_data = {"emailAddress": {"address": "test@example.com", "name": "Test User"}}

        email_address = graph_client._parse_email_address(address_data)
        assert email_address.email == "test@example.com"
        assert email_address.name == "Test User"

    def test_parse_email_address_no_name(self, graph_client):
        """Test parsing email address without name."""
        address_data = {"emailAddress": {"address": "test@example.com"}}

        email_address = graph_client._parse_email_address(address_data)
        assert email_address.email == "test@example.com"
        assert email_address.name is None

    def test_parse_importance(self, graph_client):
        """Test parsing importance levels."""
        assert graph_client._parse_importance("low") == EmailImportance.LOW
        assert graph_client._parse_importance("normal") == EmailImportance.NORMAL
        assert graph_client._parse_importance("high") == EmailImportance.HIGH
        assert graph_client._parse_importance("unknown") == EmailImportance.NORMAL

    def test_convert_to_email_model(self, graph_client, mock_graph_message):
        """Test converting Graph API message to Email model."""
        email = graph_client.convert_to_email_model(
            mock_graph_message, "test-processing-id", "1.0.0"
        )

        assert email.id == "test-message-id-123"
        assert email.subject == "Test Email Subject"
        assert email.sender.email == "sender@example.com"
        assert email.sender.name == "Test Sender"
        assert len(email.recipients.to) == 1
        assert email.recipients.to[0].email == "recipient@example.com"
        assert email.body.content_type == "text/html"
        assert email.importance == EmailImportance.NORMAL
        assert email.processing_metadata.inbox_monitor_version == "1.0.0"
        assert email.processing_metadata.processing_id == "test-processing-id"
