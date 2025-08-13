"""
Azure Key Vault Client for Secure Credential Management
======================================================

Client for retrieving Databricks service principal credentials from Azure Key Vault
with comprehensive error handling, retry logic, and security best practices.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

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

from services.logging.api_client_logger import APIClientLoggerMixin


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


class AIFoundryCredentials(BaseModel):
    """Model for Azure AI Foundry credentials."""
    
    endpoint: str = Field(..., description="Azure AI Foundry endpoint")
    tenant_id: str = Field(..., description="Azure AI Foundry tenant ID")
    client_id: str = Field(..., description="Azure AI Foundry client ID")
    client_secret: SecretStr = Field(..., description="Azure AI Foundry client secret")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When credentials were retrieved")
    
    def is_expired(self, max_age_hours: int = 1) -> bool:
        """Check if credentials should be refreshed."""
        age = datetime.now(timezone.utc) - self.retrieved_at
        return age > timedelta(hours=max_age_hours)


class GraphAPICredentials(BaseModel):
    """Model for Microsoft Graph API credentials."""
    
    tenant_id: str = Field(..., description="Graph API tenant ID")
    client_id: str = Field(..., description="Graph API client ID")
    client_secret: SecretStr = Field(..., description="Graph API client secret")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When credentials were retrieved")
    
    def is_expired(self, max_age_hours: int = 1) -> bool:
        """Check if credentials should be refreshed."""
        age = datetime.now(timezone.utc) - self.retrieved_at
        return age > timedelta(hours=max_age_hours)


class SalesforceCredentials(BaseModel):
    """Model for Salesforce credentials."""
    
    base_url: str = Field(..., description="Salesforce base URL")
    client_id: str = Field(..., description="Salesforce client ID")
    client_secret: SecretStr = Field(..., description="Salesforce client secret")
    token_endpoint: str = Field(..., description="Salesforce token endpoint")
    api_version: str = Field(..., description="Salesforce API version")
    case_record_type_id: str = Field(..., description="Salesforce case record type ID")
    case_queue: str = Field(..., description="Salesforce case queue")
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


class AzureKeyVaultClient(APIClientLoggerMixin):
    """Client for secure retrieval of credentials from Azure Key Vault."""
    
    def __init__(self, settings: KeyVaultSettings = None, vault_url: str = None, test_mode: bool = True):
        """Initialize Key Vault client with settings.
        
        Args:
            settings: Key Vault configuration settings
            vault_url: Key Vault URL (alternative to settings)
            test_mode: Whether to run in test mode (True) or real service mode (False)
        """
        # Initialize logging first
        self.__init_logging__("azure_key_vault_client")
        
        self.settings = settings
        self.vault_url = vault_url or (settings.key_vault_url if settings else None)
        self.test_mode = test_mode
        self._client: Optional[SecretClient] = None
        self._credentials: Optional[ServicePrincipalCredentials] = None
        self._ai_foundry_credentials: Optional[AIFoundryCredentials] = None
        self._graph_api_credentials: Optional[GraphAPICredentials] = None
        self._salesforce_credentials: Optional[SalesforceCredentials] = None
        self._credential_provider: Optional[ClientSecretCredential] = None
        
        if test_mode:
            self.log_user_message("🧪 Azure Key Vault client initialized in test mode")
        
    async def __aenter__(self) -> "AzureKeyVaultClient":
        """Async context manager entry."""
        if not self.test_mode:
            await self._initialize_client()
        else:
            self.logger.info("Key Vault client entered context manager in test mode")
        return self
        
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if not self.test_mode:
            await self._cleanup()
        else:
            self.logger.info("Key Vault client exited context manager in test mode")
    
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
                    f"Successfully authenticated to Azure Key Vault (vault_url: {self.settings.key_vault_url}, secret_count: {len(secret_list)})"
                )
            except ClientAuthenticationError as e:
                raise KeyVaultAuthenticationError(
                    f"Failed to authenticate to Key Vault: {e}"
                ) from e
                
        except Exception as e:
            self.logger.error(
                f"Failed to initialize Key Vault client (vault_url: {self.settings.key_vault_url}): {e}"
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
                self.logger.warning(f"Error during credential provider cleanup: {e}")
        
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
            self.log_diagnostic("Using cached Databricks credentials", level="debug")
            return self._credentials
        
        # In test mode, return mock credentials without requiring real client initialization
        if self.test_mode:
            mock_credentials = ServicePrincipalCredentials(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321", 
                client_secret=SecretStr("mock-databricks-secret-value")
            )
            self._credentials = mock_credentials
            self.log_diagnostic("Using mock Databricks credentials for test mode", level="debug")
            return mock_credentials
            
        if not self._client:
            await self._initialize_client()
            
        try:
            correlation_id = self.log_operation_start("get_databricks_credentials", force_refresh=force_refresh)
            
            if not self.test_mode:
                self.log_user_message("🔐 Retrieving Databricks credentials from Key Vault...")
            
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
            
            self.log_operation_success(
                "get_databricks_credentials", 
                correlation_id,
                result_summary="Credentials retrieved successfully",
                client_id=client_id,
                tenant_id=tenant_id
            )
            
            if not self.test_mode:
                self.log_user_message("✅ Databricks credentials retrieved successfully")
            
            return credentials
            
        except Exception as e:
            self.log_operation_error("get_databricks_credentials", correlation_id, e)
            
            if not self.test_mode:
                self.log_user_message(f"❌ Failed to retrieve Databricks credentials: {e}", level="error")
                
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
                    f"Successfully retrieved secret (secret: {secret_name}, attempt: {attempt + 1})"
                )
                return secret.value
                
            except ResourceNotFoundError:
                raise KeyVaultSecretError(f"Secret '{secret_name}' not found in Key Vault")
                
            except (ServiceRequestError, AzureError) as e:
                if attempt == max_retries - 1:
                    raise KeyVaultSecretError(
                        f"Failed to retrieve secret '{secret_name}' after {max_retries} attempts: {e}"
                    ) from e
                    
                self.logger.warning(f"Secret retrieval failed, retrying (secret: {secret_name}, attempt: {attempt + 1}, delay: {retry_delay}s): {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                
        raise KeyVaultSecretError(f"Failed to retrieve secret '{secret_name}' after all retries")
    
    async def get_ai_foundry_credentials(self, force_refresh: bool = False) -> AIFoundryCredentials:
        """Retrieve Azure AI Foundry credentials from Key Vault.
        
        Args:
            force_refresh: Force retrieval even if cached credentials are available
            
        Returns:
            AIFoundryCredentials with endpoint, tenant_id, client_id, and client_secret
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        # Return cached credentials if available and not expired
        if (not force_refresh and 
            self._ai_foundry_credentials and 
            not self._ai_foundry_credentials.is_expired()):
            self.logger.debug("Using cached AI Foundry credentials")
            return self._ai_foundry_credentials
        
        # In test mode, return mock credentials
        if self.test_mode:
            mock_credentials = AIFoundryCredentials(
                endpoint="https://mock-ai-foundry.eastus.inference.ml.azure.com",
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                client_secret=SecretStr("mock-ai-foundry-secret-value")
            )
            self._ai_foundry_credentials = mock_credentials
            self.logger.debug("Using mock AI Foundry credentials for test mode")
            return mock_credentials
            
        if not self._client:
            await self._initialize_client()
            
        try:
            self.logger.info("Retrieving Azure AI Foundry credentials from Key Vault")
            
            # Retrieve all required secrets in parallel for performance
            tasks = [
                self._get_secret_async(self.settings.azure_ai_foundry_endpoint_secret_name),
                self._get_secret_async(self.settings.azure_ai_foundry_tenant_id_secret_name),
                self._get_secret_async(self.settings.azure_ai_foundry_client_id_secret_name),
                self._get_secret_async(self.settings.azure_ai_foundry_client_secret_secret_name)
            ]
            
            endpoint, tenant_id, client_id, client_secret = await asyncio.gather(*tasks)
            
            # Create credentials model
            credentials = AIFoundryCredentials(
                endpoint=endpoint,
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=SecretStr(client_secret)
            )
            
            # Cache for future use
            self._ai_foundry_credentials = credentials
            
            self.logger.info(
                f"Successfully retrieved Azure AI Foundry credentials (endpoint: {endpoint}, tenant_id: {tenant_id}, client_id: {client_id})"
            )
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve Azure AI Foundry credentials from Key Vault: {e}")
            raise KeyVaultSecretError(f"Failed to retrieve Azure AI Foundry credentials: {e}") from e
    
    async def get_graph_api_credentials(self, force_refresh: bool = False) -> GraphAPICredentials:
        """Retrieve Microsoft Graph API credentials from Key Vault.
        
        Args:
            force_refresh: Force retrieval even if cached credentials are available
            
        Returns:
            GraphAPICredentials with tenant_id, client_id, and client_secret
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        # Return cached credentials if available and not expired
        if (not force_refresh and 
            self._graph_api_credentials and 
            not self._graph_api_credentials.is_expired()):
            self.logger.debug("Using cached Graph API credentials")
            return self._graph_api_credentials
        
        # In test mode, return mock credentials
        if self.test_mode:
            mock_credentials = GraphAPICredentials(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                client_secret=SecretStr("mock-graph-api-secret-value")
            )
            self._graph_api_credentials = mock_credentials
            self.logger.debug("Using mock Graph API credentials for test mode")
            return mock_credentials
            
        if not self._client:
            await self._initialize_client()
            
        try:
            self.logger.info("Retrieving Microsoft Graph API credentials from Key Vault")
            
            # Retrieve all required secrets in parallel for performance
            tasks = [
                self._get_secret_async(self.settings.graph_api_tenant_id_secret_name),
                self._get_secret_async(self.settings.graph_api_client_id_secret_name),
                self._get_secret_async(self.settings.graph_api_client_secret_secret_name)
            ]
            
            tenant_id, client_id, client_secret = await asyncio.gather(*tasks)
            
            # Create credentials model
            credentials = GraphAPICredentials(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=SecretStr(client_secret)
            )
            
            # Cache for future use
            self._graph_api_credentials = credentials
            
            self.logger.info(
                f"Successfully retrieved Microsoft Graph API credentials (tenant_id: {tenant_id}, client_id: {client_id})"
            )
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve Microsoft Graph API credentials from Key Vault: {e}")
            raise KeyVaultSecretError(f"Failed to retrieve Microsoft Graph API credentials: {e}") from e
    
    async def get_salesforce_credentials(self, force_refresh: bool = False) -> SalesforceCredentials:
        """Retrieve Salesforce credentials from Key Vault.
        
        Args:
            force_refresh: Force retrieval even if cached credentials are available
            
        Returns:
            SalesforceCredentials with all Salesforce configuration values
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        # Return cached credentials if available and not expired
        if (not force_refresh and 
            self._salesforce_credentials and 
            not self._salesforce_credentials.is_expired()):
            self.logger.debug("Using cached Salesforce credentials")
            return self._salesforce_credentials
        
        # In test mode, return mock credentials
        if self.test_mode:
            mock_credentials = SalesforceCredentials(
                base_url="https://mock-salesforce.my.salesforce.com",
                client_id="mock-salesforce-client-id",
                client_secret=SecretStr("mock-salesforce-client-secret"),
                token_endpoint="https://mock-salesforce.my.salesforce.com/services/oauth2/token",
                api_version="v58.0",
                case_record_type_id="012MOCK000000000AAA",
                case_queue="Mock Test Queue"
            )
            self._salesforce_credentials = mock_credentials
            self.logger.debug("Using mock Salesforce credentials for test mode")
            return mock_credentials
            
        if not self._client:
            await self._initialize_client()
            
        try:
            self.logger.info("Retrieving Salesforce credentials from Key Vault")
            
            # Retrieve all required secrets in parallel for performance
            tasks = [
                self._get_secret_async(self.settings.salesforce_base_url_secret_name),
                self._get_secret_async(self.settings.salesforce_client_id_secret_name),
                self._get_secret_async(self.settings.salesforce_client_secret_secret_name),
                self._get_secret_async(self.settings.salesforce_token_endpoint_secret_name),
                self._get_secret_async(self.settings.salesforce_api_version_secret_name),
                self._get_secret_async(self.settings.salesforce_case_record_type_id_secret_name),
                self._get_secret_async(self.settings.salesforce_case_queue_secret_name)
            ]
            
            (base_url, client_id, client_secret, token_endpoint, 
             api_version, case_record_type_id, case_queue) = await asyncio.gather(*tasks)
            
            # Create credentials model
            credentials = SalesforceCredentials(
                base_url=base_url,
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_endpoint=token_endpoint,
                api_version=api_version,
                case_record_type_id=case_record_type_id,
                case_queue=case_queue
            )
            
            # Cache for future use
            self._salesforce_credentials = credentials
            
            self.logger.info(
                f"Successfully retrieved Salesforce credentials (base_url: {base_url}, client_id: {client_id}, api_version: {api_version}, case_queue: {case_queue})"
            )
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve Salesforce credentials from Key Vault: {e}")
            raise KeyVaultSecretError(f"Failed to retrieve Salesforce credentials: {e}") from e
    
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
            self.logger.error(f"Key Vault connectivity test failed: {e}")
            return False