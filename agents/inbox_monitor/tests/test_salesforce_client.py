"""
Tests for Salesforce Client
===========================
Unit tests for the Salesforce client used for case creation and contact updates.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.settings import SalesforceSettings  # noqa: E402
from services.salesforce_client import (  # noqa: E402
    CaseCreateRequest,
    CaseCreateResponse,
    ContactUpdateRequest,
    SalesforceClient,
    SalesforceTokenResponse,
)
@pytest.fixture
def salesforce_settings():
    """Create Salesforce settings for testing."""
    return SalesforceSettings(
        base_url="https://test.salesforce.com",
        client_id="test_client_id",
        client_secret="test_client_secret",
        token_endpoint="https://test.salesforce.com/services/oauth2/token",
        api_version="v64.0",
        case_record_type_id="012000000000000",
        case_queue="Expert Team",
    )
@pytest.fixture
def salesforce_client(salesforce_settings):
    """Create Salesforce client for testing."""
    return SalesforceClient(salesforce_settings)
@pytest.fixture
def mock_token_response():
    """Mock token response."""
    return {
        "access_token": "test_access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "instance_url": "https://test.salesforce.com",
    }
class TestSalesforceClient:
    """Test cases for Salesforce client."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_init(self, salesforce_settings):
        """Test client initialization."""
        client = SalesforceClient(salesforce_settings)
        assert client.settings == salesforce_settings
        assert client.client is None
        assert client._access_token is None
        assert client._token_expires_at is None
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_refresh_token_success(self, salesforce_client, mock_token_response):
        """Test successful token refresh."""
        mock_response = MagicMock()
        mock_response.status_code = 200  # httpx uses status_code
        mock_response.json.return_value = mock_token_response
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        salesforce_client.client = mock_client
        await salesforce_client._refresh_token()
        assert salesforce_client._access_token == "test_access_token"
        assert salesforce_client._token_expires_at is not None
        assert salesforce_client._token_expires_at > datetime.now(timezone.utc)
    @pytest.mark.medium
    @pytest.mark.edge_case
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.edge_case
    async def test_refresh_token_failure(self, salesforce_client):
        """Test token refresh failure."""
        mock_response = MagicMock()
        mock_response.status_code = 400  # httpx uses status_code
        mock_response.text = "Invalid client credentials"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        salesforce_client.client = mock_client
        with pytest.raises(Exception) as exc_info:
            await salesforce_client._refresh_token()
        assert "Token request failed with status 400" in str(exc_info.value)
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_get_access_token_valid(self, salesforce_client):
        """Test getting valid access token."""
        # Set up existing valid token
        salesforce_client._access_token = "existing_token"
        salesforce_client._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token = await salesforce_client._get_access_token()
        assert token == "existing_token"
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_get_access_token_expired(self, salesforce_client, mock_token_response):
        """Test getting access token when expired."""
        # Set up expired token
        salesforce_client._access_token = "expired_token"
        salesforce_client._token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        # Mock refresh token
        with patch.object(salesforce_client, "_refresh_token") as mock_refresh:
            salesforce_client._access_token = "new_token"
            token = await salesforce_client._get_access_token()
            mock_refresh.assert_called_once()
            assert token == "new_token"
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_create_case_success(self, salesforce_client):
        """Test successful case creation."""
        case_request = CaseCreateRequest(
            account_id="001000000000000",
            contact_id="003000000000000",
            owner_id="005000000000000",
            subject="Test Case",
            description="Test case description",
            case_queue="Expert Team",
        )
        mock_response = MagicMock()
        mock_response.status_code = 201  # httpx uses status_code
        mock_response.json.return_value = {"id": "500000000000000"}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.create_case(case_request)
            assert isinstance(result, CaseCreateResponse)
            assert result.success is True
            assert result.id == "500000000000000"
            assert result.errors == []
    @pytest.mark.medium
    @pytest.mark.edge_case
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.edge_case
    async def test_create_case_failure(self, salesforce_client):
        """Test case creation failure."""
        case_request = CaseCreateRequest(
            account_id="001000000000000",
            contact_id="003000000000000",
            owner_id="005000000000000",
            subject="Test Case",
            description="Test case description",
            case_queue="Expert Team",
        )
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = ["Required field missing"]
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.create_case(case_request)
            assert isinstance(result, CaseCreateResponse)
            assert result.success is False
            assert result.id == ""
            assert len(result.errors) > 0
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.edge_case
    async def test_update_contact_invalid_email_success(self, salesforce_client):
        """Test successful contact update."""
        contact_update = ContactUpdateRequest(contact_id="003000000000000", is_email_invalid=True)
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_client = AsyncMock()
        mock_client.patch.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.update_contact_invalid_email(contact_update)
            assert result is True
    @pytest.mark.medium
    @pytest.mark.edge_case
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.edge_case
    async def test_update_contact_invalid_email_failure(self, salesforce_client):
        """Test contact update failure."""
        contact_update = ContactUpdateRequest(contact_id="003000000000000", is_email_invalid=True)
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        mock_client = AsyncMock()
        mock_client.patch.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.update_contact_invalid_email(contact_update)
            assert result is False
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_get_contact_details_success(self, salesforce_client):
        """Test successful contact details retrieval."""
        contact_id = "003000000000000"
        mock_contact_data = {
            "Id": contact_id,
            "Email": "test@example.com",
            "AccountId": "001000000000000",
            "FirstName": "John",
            "LastName": "Doe",
            "Account": {"Name": "Test Company", "OwnerId": "005000000000000"},
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_contact_data
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.get_contact_details(contact_id)
            assert result == mock_contact_data
            assert result["Email"] == "test@example.com"
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_get_contact_details_not_found(self, salesforce_client):
        """Test contact details retrieval when contact not found."""
        contact_id = "003000000000000"
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.get_contact_details(contact_id)
            assert result is None
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_test_connection_success(self, salesforce_client):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sobjects": []}
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.test_connection()
            assert result is True
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.edge_case
    async def test_test_connection_failure(self, salesforce_client):
        """Test connection test failure."""
        mock_response = MagicMock()
        mock_response.status = 401
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        salesforce_client.client = mock_client
        with patch.object(salesforce_client, "_get_access_token", return_value="test_token"):
            result = await salesforce_client.test_connection()
            assert result is False
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.unit
    async def test_test_connection_exception(self, salesforce_client):
        """Test connection test with exception."""
        with patch.object(
            salesforce_client, "_get_access_token", side_effect=Exception("Connection error")
        ):
            result = await salesforce_client.test_connection()
            assert result is False
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_context_manager(self, salesforce_client):
        """Test async context manager."""
        async with salesforce_client as client:
            assert client.client is not None
            assert isinstance(client.client, httpx.AsyncClient)
        assert salesforce_client.client is None
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_salesforce_token_response_model(self):
        """Test Salesforce token response model."""
        token_data = {
            "access_token": "test_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "instance_url": "https://test.salesforce.com",
        }
        token_response = SalesforceTokenResponse(**token_data)
        assert token_response.access_token == "test_token"
        assert token_response.token_type == "Bearer"
        assert token_response.expires_in == 3600
        assert token_response.instance_url == "https://test.salesforce.com"
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_case_create_request_model(self):
        """Test case create request model."""
        case_data = {
            "account_id": "001000000000000",
            "contact_id": "003000000000000",
            "owner_id": "005000000000000",
            "subject": "Test Case",
            "description": "Test description",
            "case_queue": "Expert Team",
        }
        case_request = CaseCreateRequest(**case_data)
        assert case_request.account_id == "001000000000000"
        assert case_request.contact_id == "003000000000000"
        assert case_request.owner_id == "005000000000000"
        assert case_request.subject == "Test Case"
        assert case_request.description == "Test description"
        assert case_request.case_queue == "Expert Team"
        assert case_request.origin == "AI Agent"
        assert case_request.status == "Assigned"
        assert case_request.priority == "Medium"
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_contact_update_request_model(self):
        """Test contact update request model."""
        update_data = {"contact_id": "003000000000000", "is_email_invalid": True}
        contact_update = ContactUpdateRequest(**update_data)
        assert contact_update.contact_id == "003000000000000"
        assert contact_update.is_email_invalid is True