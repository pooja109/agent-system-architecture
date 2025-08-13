"""
Azure Key Vault Client for Secure Credential Management
======================================================

Client for retrieving Databricks service principal credentials from Azure Key Vault
with comprehensive error handling, retry logic, and security best practices.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
import structlog

from azure.keyvault.secrets import SecretClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import (
    AzureError, 
    ClientAuthenticationError,
    ResourceNotFoundError,
    ServiceRequestError
)
from pydantic import BaseModel, Field, SecretStr

try:
    from config.settings import KeyVaultSettings
except ImportError:
    from ..config.settings import KeyVaultSettings


class ServicePrincipalCredentials(BaseModel):
    """Model for Databricks service principal credentials."""
    
    tenant_id: str = Field(..., description="Azure AD tenant ID")
    client_id: str = Field(..., description="Service principal client ID")
    client_secret: SecretStr = Field(..., description="Service principal client secret")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When credentials were retrieved")
    
    def is_expired(self, max_age_hours: int = 1) -> bool:
        """Check if credentials should be refreshed."""
        age = datetime.now(timezone.utc) - self.retrieved_at
        return age > timedelta(hours=max_age_hours)


class ACSCredentials(BaseModel):
    """Model for Azure Communication Services credentials."""
    
    connection_string: SecretStr = Field(..., description="ACS connection string")
    sender_email: str = Field(..., description="ACS sender email address")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When credentials were retrieved")
    
    def is_expired(self, max_age_hours: int = 1) -> bool:
        """Check if credentials should be refreshed."""
        age = datetime.now(timezone.utc) - self.retrieved_at
        return age > timedelta(hours=max_age_hours)


class KeyVaultException(Exception):
    """Base exception for Key Vault operations."""
    pass


class KeyVaultAuthenticationError(KeyVaultException):
    """Raised when Key Vault authentication fails."""
    pass


class KeyVaultSecretError(KeyVaultException):
    """Raised when secret retrieval fails.""" 
    pass


class MockToken:
    """Mock token for testing."""
    def __init__(self):
        self.token = "mock_azure_token_12345"
        self.expires_on = datetime.now(timezone.utc).timestamp() + 3600  # 1 hour from now


class MockAzureCredential:
    """Mock Azure credential for testing."""
    async def get_token(self, scope: str):
        """Return mock token."""
        return MockToken()


class AzureKeyVaultClient:
    """Client for secure retrieval of credentials from Azure Key Vault."""
    
    def __init__(self, settings: KeyVaultSettings = None, vault_url: str = None, test_mode: bool = True):
        """Initialize Key Vault client with settings.
        
        Args:
            settings: Key Vault configuration settings
            vault_url: Key Vault URL (alternative to settings)
            test_mode: Whether to run in test mode (True) or real service mode (False)
        """
        self.settings = settings
        self.vault_url = vault_url or (settings.key_vault_url if settings else None)
        self.test_mode = test_mode
        self.logger = structlog.get_logger(__name__)
        self._client: Optional[SecretClient] = None
        self._credentials: Optional[ServicePrincipalCredentials] = None
        self._acs_credentials: Optional[ACSCredentials] = None
        self._credential_provider: Optional[ClientSecretCredential] = None
        
    async def __aenter__(self) -> "AzureKeyVaultClient":
        """Async context manager entry."""
        await self._initialize_client()
        return self
        
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._cleanup()
    
    async def initialize(self) -> None:
        """Initialize the Key Vault client for real service testing."""
        if not self.test_mode:
            await self._initialize_client()
        else:
            self.logger.info("Key Vault client initialized in test mode")
    
    async def close(self) -> None:
        """Close the Key Vault client and clean up resources."""
        if not self.test_mode:
            await self._cleanup()
        else:
            self.logger.info("Key Vault client closed in test mode")
    
    async def get_secret(self, secret_name: str) -> str:
        """Get a secret from Key Vault."""
        if self.test_mode:
            # Return mock values for testing
            mock_secrets = {
                'databricks-server-hostname': 'mock.databricks.com',
                'databricks-access-token': 'dapi-mock-token-12345',
                'azure-tenant-id': '12345678-1234-1234-1234-123456789012'
            }
            return mock_secrets.get(secret_name, f'mock-{secret_name}')
        
        # Real implementation would retrieve from Key Vault
        if not self._client:
            await self._initialize_client()
        
        try:
            secret = self._client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            self.logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise KeyVaultSecretError(f"Failed to retrieve secret {secret_name}") from e
    
    async def get_azure_credential(self):
        """Get Azure credential for authentication."""
        if self.test_mode:
            # Return mock credential for testing
            return MockAzureCredential()
        
        if not self._credential_provider:
            await self._initialize_client()
        
        return self._credential_provider
    
    async def _initialize_client(self) -> None:
        """Initialize Azure Key Vault client with service principal authentication."""
        try:
            # Create credential provider using service principal
            self._credential_provider = ClientSecretCredential(
                tenant_id=self.settings.azure_tenant_id,
                client_id=self.settings.azure_client_id,
                client_secret=self.settings.azure_client_secret.get_secret_value()
            )
            
            # Create Key Vault client
            self._client = SecretClient(
                vault_url=self.settings.key_vault_url,
                credential=self._credential_provider
            )
            
            # Test authentication by attempting to list secrets (without reading values)
            try:
                # This will raise an exception if authentication fails
                secret_list = list(self._client.list_properties_of_secrets())
                self.logger.info(
                    "Successfully authenticated to Azure Key Vault",
                    vault_url=self.settings.key_vault_url,
                    secret_count=len(secret_list)
                )
            except ClientAuthenticationError as e:
                raise KeyVaultAuthenticationError(
                    f"Failed to authenticate to Key Vault: {e}"
                ) from e
                
        except Exception as e:
            self.logger.error(
                "Failed to initialize Key Vault client",
                error=str(e),
                vault_url=self.settings.key_vault_url
            )
            raise KeyVaultException(f"Key Vault client initialization failed: {e}") from e
    
    async def _cleanup(self) -> None:
        """Clean up client resources."""
        if self._credential_provider:
            # Close credential provider if it has cleanup methods
            try:
                if hasattr(self._credential_provider, 'close'):
                    close_result = self._credential_provider.close()
                    if hasattr(close_result, '__await__'):
                        await close_result
                    # else: it's a sync method, just let it complete
            except Exception as e:
                self.logger.warning("Error during credential provider cleanup", error=str(e))
        
        self._client = None
        self._credential_provider = None
    
    async def get_databricks_credentials(self, force_refresh: bool = False) -> ServicePrincipalCredentials:
        """Retrieve Databricks service principal credentials from Key Vault.
        
        Args:
            force_refresh: Force retrieval even if cached credentials are available
            
        Returns:
            ServicePrincipalCredentials with tenant_id, client_id, and client_secret
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        # Return cached credentials if available and not expired
        if (not force_refresh and 
            self._credentials and 
            not self._credentials.is_expired()):
            self.logger.debug("Using cached Databricks credentials")
            return self._credentials
            
        if not self._client:
            raise KeyVaultException("Key Vault client not initialized")
            
        try:
            self.logger.info("Retrieving Databricks service principal credentials from Key Vault")
            
            # Retrieve all required secrets in parallel for performance
            tasks = [
                self._get_secret_async(self.settings.tenant_id_secret_name),
                self._get_secret_async(self.settings.client_id_secret_name),
                self._get_secret_async(self.settings.client_secret_secret_name)
            ]
            
            tenant_id, client_id, client_secret = await asyncio.gather(*tasks)
            
            # Create credentials model
            credentials = ServicePrincipalCredentials(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=SecretStr(client_secret)
            )
            
            # Cache for future use
            self._credentials = credentials
            
            self.logger.info(
                "Successfully retrieved Databricks service principal credentials",
                client_id=client_id,
                tenant_id=tenant_id
            )
            
            return credentials
            
        except Exception as e:
            self.logger.error(
                "Failed to retrieve Databricks credentials from Key Vault",
                error=str(e),
                vault_url=self.settings.key_vault_url
            )
            raise KeyVaultSecretError(f"Failed to retrieve Databricks credentials: {e}") from e
    
    async def _get_secret_async(self, secret_name: str) -> str:
        """Retrieve a single secret from Key Vault with retry logic.
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Secret value as string
            
        Raises:
            KeyVaultSecretError: If secret retrieval fails
        """
        if not self._client:
            raise KeyVaultException("Key Vault client not initialized")
            
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                secret = self._client.get_secret(secret_name)
                if not secret.value:
                    raise KeyVaultSecretError(f"Secret '{secret_name}' exists but has no value")
                    
                self.logger.debug(
                    "Successfully retrieved secret",
                    secret_name=secret_name,
                    attempt=attempt + 1
                )
                return secret.value
                
            except ResourceNotFoundError:
                raise KeyVaultSecretError(f"Secret '{secret_name}' not found in Key Vault")
                
            except (ServiceRequestError, AzureError) as e:
                if attempt == max_retries - 1:
                    raise KeyVaultSecretError(
                        f"Failed to retrieve secret '{secret_name}' after {max_retries} attempts: {e}"
                    ) from e
                    
                self.logger.warning(
                    "Secret retrieval failed, retrying",
                    secret_name=secret_name,
                    attempt=attempt + 1,
                    error=str(e),
                    retry_delay=retry_delay
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                
        raise KeyVaultSecretError(f"Failed to retrieve secret '{secret_name}' after all retries")
    
    async def get_acs_credentials(self, force_refresh: bool = False) -> ACSCredentials:
        """Retrieve Azure Communication Services credentials from Key Vault.
        
        Args:
            force_refresh: Force retrieval even if cached credentials are available
            
        Returns:
            ACSCredentials with connection_string and sender_email
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        # Return cached credentials if available and not expired
        if (not force_refresh and 
            self._acs_credentials and 
            not self._acs_credentials.is_expired()):
            self.logger.debug("Using cached ACS credentials")
            return self._acs_credentials
            
        if not self._client:
            raise KeyVaultException("Key Vault client not initialized")
            
        try:
            self.logger.info("Retrieving ACS credentials from Key Vault")
            
            # Retrieve ACS secrets in parallel for performance
            tasks = [
                self._get_secret_async(self.settings.acs_connection_string_secret_name),
                self._get_secret_async(self.settings.acs_sender_email_secret_name)
            ]
            
            connection_string, sender_email = await asyncio.gather(*tasks)
            
            # Create credentials model
            credentials = ACSCredentials(
                connection_string=SecretStr(connection_string),
                sender_email=sender_email
            )
            
            # Cache for future use
            self._acs_credentials = credentials
            
            self.logger.info(
                "Successfully retrieved ACS credentials",
                sender_email=sender_email
            )
            
            return credentials
            
        except Exception as e:
            self.logger.error(
                "Failed to retrieve ACS credentials from Key Vault",
                error=str(e),
                vault_url=self.settings.key_vault_url
            )
            raise KeyVaultSecretError(f"Failed to retrieve ACS credentials: {e}") from e
    
    async def test_connection(self) -> bool:
        """Test Key Vault connectivity and authentication.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            if not self._client:
                await self._initialize_client()
                
            # Attempt to retrieve credentials as a connectivity test
            await self.get_databricks_credentials()
            
            self.logger.info("Key Vault connectivity test successful")
            return True
            
        except Exception as e:
            self.logger.error("Key Vault connectivity test failed", error=str(e))
            return False