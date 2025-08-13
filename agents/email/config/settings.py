import os
from typing import Optional
from pydantic import BaseModel, Field, model_validator, SecretStr
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AzureCommunicationSettings(BaseModel):
    connection_string: str = Field(..., description="Azure Communication Services connection string")
    sender_email: str = Field(..., description="Sender email address")
    reply_to_email: str = Field(..., description="Reply-to email address")
    
    @classmethod
    async def from_key_vault(cls, key_vault_client) -> "AzureCommunicationSettings":
        """Create AzureCommunicationSettings from Azure Key Vault credentials.
        
        Args:
            key_vault_client: Initialized AzureKeyVaultClient instance
            
        Returns:
            AzureCommunicationSettings with credentials from Key Vault
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        try:
            from services.azure_key_vault_client import KeyVaultException
        except ImportError:
            try:
                from ..services.azure_key_vault_client import KeyVaultException
            except ImportError:
                raise ImportError("KeyVaultException not available")
        
        try:
            # Retrieve ACS credentials from Key Vault
            acs_credentials = await key_vault_client.get_acs_credentials()
            
            # Extract connection string and sender email
            connection_string = acs_credentials.connection_string.get_secret_value()
            sender_email = acs_credentials.sender_email
            
            # Use sender_email as reply_to_email if not configured separately
            reply_to_email = sender_email
            
            return cls(
                connection_string=connection_string,
                sender_email=sender_email,
                reply_to_email=reply_to_email
            )
            
        except Exception as e:
            raise KeyVaultException(f"Failed to create AzureCommunicationSettings from Key Vault: {e}") from e

class AzureStorageSettings(BaseModel):
    connection_string: Optional[str] = Field(None, description="Azure Storage connection string")
    account_name: Optional[str] = Field(None, description="Azure Storage account name (for SAS token auth)")
    sas_token: Optional[str] = Field(None, description="Azure Storage SAS token")
    container_name: str = Field(default="lowtouch", description="Blob container name")
    
    @model_validator(mode='after')
    def validate_authentication(self):
        """Validate that either connection_string or account_name+sas_token is provided."""
        if not self.connection_string and not (self.account_name and self.sas_token):
            raise ValueError(
                "Either connection_string OR both account_name and sas_token must be provided"
            )
        if self.connection_string and (self.account_name or self.sas_token):
            raise ValueError(
                "Cannot use both connection_string and SAS token authentication. Choose one method."
            )
        return self

class KeyVaultSettings(BaseModel):
    """Azure Key Vault configuration settings."""
    
    key_vault_url: str = Field(..., description="Azure Key Vault URL")
    azure_tenant_id: str = Field(..., description="Azure AD tenant ID for Key Vault access")
    azure_client_id: str = Field(..., description="Service principal client ID for Key Vault access")
    azure_client_secret: SecretStr = Field(..., description="Service principal client secret for Key Vault access")
    
    # Secret names in Key Vault
    tenant_id_secret_name: str = Field(
        default="sales-engagement-service-principal-tenantid",
        description="Key Vault secret name for Databricks tenant ID"
    )
    client_id_secret_name: str = Field(
        default="sales-engagement-service-principal-clientid", 
        description="Key Vault secret name for Databricks client ID"
    )
    client_secret_secret_name: str = Field(
        default="sales-engagement-service-principal-secretid",
        description="Key Vault secret name for Databricks client secret"
    )
    
    # ACS secret names in Key Vault
    acs_connection_string_secret_name: str = Field(
        default="azure-communication-connection-string",
        description="Key Vault secret name for ACS connection string"
    )
    acs_sender_email_secret_name: str = Field(
        default="azure-communication-sender-email",
        description="Key Vault secret name for ACS sender email"
    )
    
    # Caching settings
    credential_cache_hours: int = Field(
        default=1,
        description="Hours to cache retrieved credentials"
    )



class DatabricksOAuthSettings(BaseModel):
    """Databricks OAuth configuration settings (replaces DatabricksSettings)."""
    
    server_hostname: str = Field(..., description="Databricks server hostname")
    http_path: str = Field(..., description="Databricks HTTP path")
    catalog: str = Field(..., description="Databricks catalog name")
    schema_name: str = Field(..., description="Databricks schema name")
    table_suffix: str = Field(default="", description="Table suffix for environments")
    
    # OAuth will be handled by Key Vault retrieved credentials
    # No access_token field needed anymore



class ProcessingSettings(BaseModel):
    interval_minutes: int = Field(default=5, description="Processing interval in minutes")
    max_retry_attempts: int = Field(default=3, description="Maximum retry attempts for failed operations")
    batch_size: int = Field(default=10, description="Number of records to process in each batch")

class LoggingSettings(BaseModel):
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Logging format")

class TestModeSettings(BaseModel):
    test_mode: bool = Field(default=False, description="Enable test mode to override email addresses")
    test_email_override: Optional[str] = Field(None, description="Email address to use in test mode")


class ConnectionPoolSettings(BaseModel):
    """Connection pool configuration settings."""
    
    min_connections: int = Field(default=2, description="Minimum connections to maintain")
    max_connections: int = Field(default=5, description="Maximum connections in pool")
    connection_timeout_seconds: int = Field(default=30, description="Connection acquisition timeout")
    health_check_interval_seconds: int = Field(default=300, description="Health check interval (5 minutes)")
    max_connection_age_seconds: int = Field(default=3600, description="Maximum connection age (1 hour)")
    connection_idle_timeout_seconds: int = Field(default=1800, description="Idle connection timeout (30 minutes)")
    pool_warmup_timeout_seconds: int = Field(default=60, description="Pool initialization timeout")
    connection_retry_attempts: int = Field(default=3, description="Connection creation retry attempts")
    connection_retry_delay_seconds: float = Field(default=1.0, description="Delay between retry attempts")

class MonitoringSettings(BaseModel):
    """Health monitoring and operational settings."""
    
    health_check_port: int = Field(
        default=8081,
        description="Port for health check HTTP server"
    )
    health_check_enabled: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )
    metrics_collection_interval_seconds: int = Field(
        default=60,
        description="Interval for collecting performance metrics in seconds"
    )
    connection_pool_health_check_interval_seconds: int = Field(
        default=30,
        description="Interval for connection pool health checks in seconds"
    )
    oauth_health_check_interval_seconds: int = Field(
        default=120,
        description="Interval for OAuth authentication health checks in seconds"
    )
    performance_alert_thresholds: dict = Field(
        default_factory=lambda: {
            "connection_acquisition_p95_ms": 500,
            "query_execution_avg_ms": 2000,
            "throughput_ops_per_sec": 20,
            "pool_utilization_percent": 80,
            "error_rate_percent": 5
        },
        description="Performance alert thresholds for monitoring"
    )


class AppSettings(BaseModel):
    azure_communication: AzureCommunicationSettings
    azure_storage: AzureStorageSettings
    databricks_oauth: DatabricksOAuthSettings
    key_vault: KeyVaultSettings
    processing: ProcessingSettings
    logging: LoggingSettings
    test_mode: TestModeSettings
    monitoring: MonitoringSettings
    connection_pool: ConnectionPoolSettings
    environment: str = Field(default="development", description="Application environment")

async def get_settings() -> AppSettings:
    """Get application settings from environment variables and Key Vault."""
    # Initialize Key Vault client first
    try:
        from services.azure_key_vault_client import AzureKeyVaultClient
    except ImportError:
        try:
            from ..services.azure_key_vault_client import AzureKeyVaultClient
        except ImportError:
            raise ImportError("AzureKeyVaultClient not available")
    
    key_vault_settings = KeyVaultSettings(
        key_vault_url=os.getenv("AZURE_KEY_VAULT_URL", ""),
        azure_tenant_id=os.getenv("AZURE_TENANT_ID", ""),
        azure_client_id=os.getenv("AZURE_CLIENT_ID", ""),
        azure_client_secret=SecretStr(os.getenv("AZURE_CLIENT_SECRET", "")),
        # Make secret names configurable via environment variables
        tenant_id_secret_name=os.getenv(
            "KEY_VAULT_TENANT_ID_SECRET", 
            "sales-engagement-service-principal-tenantid"
        ),
        client_id_secret_name=os.getenv(
            "KEY_VAULT_CLIENT_ID_SECRET",
            "sales-engagement-service-principal-clientid"
        ),
        client_secret_secret_name=os.getenv(
            "KEY_VAULT_CLIENT_SECRET_SECRET",
            "sales-engagement-service-principal-secretid"
        ),
        # ACS secret names from environment variables or defaults
        acs_connection_string_secret_name=os.getenv(
            "KEY_VAULT_ACS_CONNECTION_STRING_SECRET",
            "azure-communication-connection-string"
        ),
        acs_sender_email_secret_name=os.getenv(
            "KEY_VAULT_ACS_SENDER_EMAIL_SECRET", 
            "azure-communication-sender-email"
        ),
    )
    
    # Initialize Key Vault client and retrieve ACS credentials
    async with AzureKeyVaultClient(key_vault_settings) as key_vault_client:
        azure_communication = await AzureCommunicationSettings.from_key_vault(key_vault_client)
    
    return AppSettings(
        azure_communication=azure_communication,
        azure_storage=AzureStorageSettings(
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
            sas_token=os.getenv("AZURE_STORAGE_SAS_TOKEN"),
            container_name=os.getenv("BLOB_CONTAINER_NAME", "lowtouch")
        ),
        databricks_oauth=DatabricksOAuthSettings(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME", ""),
            http_path=os.getenv("DATABRICKS_HTTP_PATH", ""),
            catalog=os.getenv("DATABRICKS_CATALOG", ""),
            schema_name=os.getenv("DATABRICKS_SCHEMA", ""),
            table_suffix=os.getenv("DATABRICKS_TABLE_SUFFIX", "")
        ),
        key_vault=key_vault_settings,
        processing=ProcessingSettings(
            interval_minutes=int(os.getenv("PROCESSING_INTERVAL_MINUTES", "5")),
            max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            batch_size=int(os.getenv("BATCH_SIZE", "10"))
        ),
        logging=LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "json")
        ),
        test_mode=TestModeSettings(
            test_mode=os.getenv("TEST_MODE", "false").lower() == "true",
            test_email_override=os.getenv("TEST_EMAIL_OVERRIDE")
        ),
        monitoring=MonitoringSettings(
            health_check_port=int(os.getenv("HEALTH_CHECK_PORT", "8081")),
            health_check_enabled=os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true",
            metrics_collection_interval_seconds=int(os.getenv("METRICS_COLLECTION_INTERVAL", "60")),
            connection_pool_health_check_interval_seconds=int(os.getenv("CONNECTION_POOL_HEALTH_CHECK_INTERVAL", "30")),
            oauth_health_check_interval_seconds=int(os.getenv("OAUTH_HEALTH_CHECK_INTERVAL", "120")),
        ),
        connection_pool=ConnectionPoolSettings(
            min_connections=int(os.getenv("CONNECTION_POOL_MIN_CONNECTIONS", "2")),
            max_connections=int(os.getenv("CONNECTION_POOL_MAX_CONNECTIONS", "5")),
            connection_timeout_seconds=int(os.getenv("CONNECTION_POOL_TIMEOUT_SECONDS", "30")),
            health_check_interval_seconds=int(os.getenv("CONNECTION_POOL_HEALTH_CHECK_INTERVAL", "300")),
            max_connection_age_seconds=int(os.getenv("CONNECTION_POOL_MAX_AGE_SECONDS", "3600")),
            connection_idle_timeout_seconds=int(os.getenv("CONNECTION_POOL_IDLE_TIMEOUT_SECONDS", "1800")),
            pool_warmup_timeout_seconds=int(os.getenv("CONNECTION_POOL_WARMUP_TIMEOUT_SECONDS", "60")),
            connection_retry_attempts=int(os.getenv("CONNECTION_POOL_RETRY_ATTEMPTS", "3")),
            connection_retry_delay_seconds=float(os.getenv("CONNECTION_POOL_RETRY_DELAY_SECONDS", "1.0"))
        ),
        environment=os.getenv("ENVIRONMENT", "development")
    )

def validate_settings(settings: AppSettings) -> bool:
    """Validate that all required settings are present."""
    missing_fields = []
    
    # Azure Communication Services validation removed - now handled by Key Vault
    
    # Validate Azure Storage (either connection string OR account name + SAS token)
    if not settings.azure_storage.connection_string:
        if not settings.azure_storage.account_name:
            missing_fields.append("AZURE_STORAGE_ACCOUNT_NAME (required when not using connection string)")
        if not settings.azure_storage.sas_token:
            missing_fields.append("AZURE_STORAGE_SAS_TOKEN (required when not using connection string)")
    
    # Validate Databricks OAuth
    required_databricks_oauth = [
        (settings.databricks_oauth.server_hostname, "DATABRICKS_SERVER_HOSTNAME"),
        (settings.databricks_oauth.http_path, "DATABRICKS_HTTP_PATH"),
        (settings.databricks_oauth.catalog, "DATABRICKS_CATALOG"),
        (settings.databricks_oauth.schema_name, "DATABRICKS_SCHEMA")
    ]
    
    for field, name in required_databricks_oauth:
        if not field:
            missing_fields.append(name)
    
    # Validate Key Vault OAuth settings
    required_key_vault = [
        (settings.key_vault.key_vault_url, "AZURE_KEY_VAULT_URL"),
        (settings.key_vault.azure_tenant_id, "AZURE_TENANT_ID"),
        (settings.key_vault.azure_client_id, "AZURE_CLIENT_ID"),
        (settings.key_vault.azure_client_secret.get_secret_value(), "AZURE_CLIENT_SECRET")
    ]
    
    for field, name in required_key_vault:
        if not field:
            missing_fields.append(name)
    
    # Validate Key Vault settings
    if not settings.key_vault.key_vault_url:
        missing_fields.append("AZURE_KEY_VAULT_URL")
    if not settings.key_vault.azure_tenant_id:
        missing_fields.append("AZURE_TENANT_ID")
    if not settings.key_vault.azure_client_id:
        missing_fields.append("AZURE_CLIENT_ID")
    if not settings.key_vault.azure_client_secret.get_secret_value():
        missing_fields.append("AZURE_CLIENT_SECRET")

    # Validate test mode settings
    if settings.test_mode.test_mode and not settings.test_mode.test_email_override:
        missing_fields.append("TEST_EMAIL_OVERRIDE (required when TEST_MODE=true)")
    
    if missing_fields:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")
    
    return True