"""
Test suite for Azure Key Vault Client in email agent.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta, timezone

from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
from pydantic import SecretStr

from services.azure_key_vault_client import (
    AzureKeyVaultClient,
    ServicePrincipalCredentials,
    KeyVaultException,
    KeyVaultAuthenticationError,
    KeyVaultSecretError
)
from config.settings import KeyVaultSettings


class TestServicePrincipalCredentials:
    """Test service principal credentials model."""
    
    def test_credentials_creation(self):
        """Test creating credentials with valid data."""
        credentials = ServicePrincipalCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id", 
            client_secret=SecretStr("test-secret")
        )
        
        assert credentials.tenant_id == "test-tenant-id"
        assert credentials.client_id == "test-client-id"
        assert credentials.client_secret.get_secret_value() == "test-secret"
        assert isinstance(credentials.retrieved_at, datetime)
    
    def test_credentials_expiration(self):
        """Test credential expiration logic."""
        # Fresh credentials should not be expired
        credentials = ServicePrincipalCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-secret")
        )
        assert not credentials.is_expired()
        
        # Old credentials should be expired
        old_credentials = ServicePrincipalCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-secret"),
            retrieved_at=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        assert old_credentials.is_expired()


class TestAzureKeyVaultClient:
    """Test Azure Key Vault client functionality."""
    
    @pytest.fixture
    def key_vault_settings(self):
        """Create test Key Vault settings."""
        return KeyVaultSettings(
            key_vault_url="https://test-vault.vault.azure.net/",
            azure_tenant_id="test-tenant-id",
            azure_client_id="test-client-id",
            azure_client_secret=SecretStr("test-secret"),
            tenant_id_secret_name="test-tenant-secret",
            client_id_secret_name="test-client-secret",
            client_secret_secret_name="test-secret-secret"
        )
    
    @pytest.fixture
    def key_vault_client(self, key_vault_settings):
        """Create Key Vault client for testing."""
        return AzureKeyVaultClient(key_vault_settings)
    
    @pytest.mark.asyncio
    async def test_client_initialization_success(self, key_vault_client):
        """Test successful client initialization."""
        with patch('services.azure_key_vault_client.ClientSecretCredential') as mock_cred, \
             patch('services.azure_key_vault_client.SecretClient') as mock_client:
            
            # Mock successful authentication test
            mock_client_instance = Mock()
            mock_client_instance.list_properties_of_secrets.return_value = []
            mock_client.return_value = mock_client_instance
            
            await key_vault_client._initialize_client()
            
            # Verify credential provider creation
            mock_cred.assert_called_once_with(
                tenant_id="test-tenant-id",
                client_id="test-client-id", 
                client_secret="test-secret"
            )
            
            # Verify client creation
            mock_client.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_client_initialization_auth_failure(self, key_vault_client):
        """Test client initialization with authentication failure."""
        with patch('services.azure_key_vault_client.ClientSecretCredential') as mock_cred, \
             patch('services.azure_key_vault_client.SecretClient') as mock_client:
            
            # Mock authentication failure
            mock_client_instance = Mock()
            mock_client_instance.list_properties_of_secrets.side_effect = ClientAuthenticationError("Auth failed")
            mock_client.return_value = mock_client_instance
            
            with pytest.raises(KeyVaultException, match="Key Vault client initialization failed"):
                await key_vault_client._initialize_client()
    
    @pytest.mark.asyncio
    async def test_get_databricks_credentials_success(self, key_vault_client):
        """Test successful credential retrieval."""
        with patch.object(key_vault_client, '_initialize_client'), \
             patch.object(key_vault_client, '_get_secret_async') as mock_get_secret:
            
            # Mock client initialization
            key_vault_client._client = Mock()
            
            # Mock secret retrieval
            mock_get_secret.side_effect = ["tenant-id", "client-id", "client-secret"]
            
            credentials = await key_vault_client.get_databricks_credentials()
            
            assert credentials.tenant_id == "tenant-id"
            assert credentials.client_id == "client-id"
            assert credentials.client_secret.get_secret_value() == "client-secret"
            
            # Verify all secrets were requested
            assert mock_get_secret.call_count == 3
    
    @pytest.mark.asyncio
    async def test_get_databricks_credentials_cached(self, key_vault_client):
        """Test cached credential retrieval."""
        # Set up cached credentials
        cached_credentials = ServicePrincipalCredentials(
            tenant_id="cached-tenant",
            client_id="cached-client",
            client_secret=SecretStr("cached-secret")
        )
        key_vault_client._credentials = cached_credentials
        
        with patch.object(key_vault_client, '_get_secret_async') as mock_get_secret:
            credentials = await key_vault_client.get_databricks_credentials()
            
            # Should return cached credentials without calling Key Vault
            assert credentials == cached_credentials
            mock_get_secret.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_secret_with_retry(self, key_vault_client):
        """Test secret retrieval with retry logic."""
        mock_client = Mock()
        key_vault_client._client = mock_client
        
        # Mock first call fails, second succeeds
        mock_secret = Mock()
        mock_secret.value = "secret-value"
        from azure.core.exceptions import ServiceRequestError
        mock_client.get_secret.side_effect = [ServiceRequestError("Transient error"), mock_secret]
        
        with patch('asyncio.sleep'):  # Mock sleep to speed up test
            result = await key_vault_client._get_secret_async("test-secret")
            
        assert result == "secret-value"
        assert mock_client.get_secret.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_secret_not_found(self, key_vault_client):
        """Test secret retrieval when secret doesn't exist."""
        mock_client = Mock()
        key_vault_client._client = mock_client
        mock_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")
        
        with pytest.raises(KeyVaultSecretError, match="Secret 'test-secret' not found"):
            await key_vault_client._get_secret_async("test-secret")
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, key_vault_client):
        """Test successful connection test."""
        with patch.object(key_vault_client, '_initialize_client'), \
             patch.object(key_vault_client, 'get_databricks_credentials') as mock_get_creds:
            
            mock_get_creds.return_value = ServicePrincipalCredentials(
                tenant_id="test", client_id="test", client_secret=SecretStr("test")
            )
            
            result = await key_vault_client.test_connection()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self, key_vault_client):
        """Test connection test failure."""
        with patch.object(key_vault_client, '_initialize_client'), \
             patch.object(key_vault_client, 'get_databricks_credentials') as mock_get_creds:
            
            mock_get_creds.side_effect = KeyVaultException("Connection failed")
            
            result = await key_vault_client.test_connection()
            assert result is False


@pytest.mark.integration
class TestAzureKeyVaultIntegration:
    """Integration tests for Key Vault client (requires actual Key Vault access)."""
    
    @pytest.mark.asyncio
    async def test_real_key_vault_connection(self):
        """Test connection to real Key Vault (requires environment setup)."""
        # This test requires actual service principal credentials
        # Skip if not in integration test environment
        import os
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled")
        
        settings = KeyVaultSettings(
            key_vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
            azure_tenant_id=os.getenv("AZURE_TENANT_ID"),
            azure_client_id=os.getenv("AZURE_CLIENT_ID"),
            azure_client_secret=SecretStr(os.getenv("AZURE_CLIENT_SECRET"))
        )
        
        async with AzureKeyVaultClient(settings) as client:
            # Test connection
            connection_result = await client.test_connection()
            assert connection_result is True
            
            # Test credential retrieval
            credentials = await client.get_databricks_credentials()
            assert credentials.tenant_id
            assert credentials.client_id
            assert credentials.client_secret.get_secret_value()