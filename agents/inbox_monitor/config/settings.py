"""
Inbox Monitor Configuration Settings
====================================

Configuration management for the inbox monitor service using Pydantic models.
Loads settings from environment variables with validation.
"""

import os
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator, SecretStr

# Import scenario tracking configuration
try:
    from .scenario_tracking_settings import ScenarioTrackingConfiguration
    from .tracking_integration_settings import (
        TrackingIntegrationSettings,
        EmailProcessorIntegrationSettings
    )
except ImportError:
    from scenario_tracking_settings import ScenarioTrackingConfiguration
    from tracking_integration_settings import (
        TrackingIntegrationSettings,
        EmailProcessorIntegrationSettings
    )

# Load environment variables - support both isolated and repo-wide deployment
import pathlib

# Cache for container detection to avoid repeated environment checks
_is_container_cache = None

def _is_containerized_environment() -> bool:
    """Check if running in a containerized environment with caching."""
    global _is_container_cache
    if _is_container_cache is None:
        _is_container_cache = (
            os.getenv("KUBERNETES_SERVICE_HOST") is not None or 
            os.getenv("IS_CONTAINER", "").lower() == "true"
        )
    return _is_container_cache

def ensure_environment_loaded() -> None:
    """Ensure environment variables are loaded, using fallback if main.py didn't run.
    
    This function provides a fallback environment loading mechanism for cases where
    config/settings.py is imported directly without going through main.py.
    
    In most cases, main.py will have already loaded the environment, so this
    function will detect that and skip redundant loading.
    """
    # Check if environment was already loaded by main.py
    if os.getenv("ENV_LOADED") == "true" or os.getenv("INBOX_MONITOR_ROOT"):
        # Environment already loaded by main.py or similar
        return
    
    # Check if we're in a containerized environment (cached)
    if _is_containerized_environment():
        # In container, environment should be set by orchestrator
        return
    
    # Fallback environment loading for direct config imports
    try:
        from dotenv import load_dotenv
        
        service_root = pathlib.Path(__file__).parent.parent
        potential_env_files = [
            service_root / ".env",  # Local to inbox_monitor
            pathlib.Path.cwd() / ".env",  # Current working directory
            service_root.parent.parent.parent / ".env",  # Main repo root (backward compatibility)
        ]
        
        for env_file in potential_env_files:
            if env_file.exists():
                load_dotenv(env_file, override=False)  # Don't override already set vars
                break
                
    except ImportError:
        # python-dotenv not available, assume production environment
        pass

# Load environment on module import (fallback only)
ensure_environment_loaded()


class GraphAPISettings(BaseModel):
    """Microsoft Graph API configuration settings."""

    tenant_id: str = Field(..., description="Azure AD tenant ID")
    client_id: str = Field(..., description="Application (client) ID")
    client_secret: str = Field(..., description="Client secret")
    monitored_email: str = Field(..., description="Email address to monitor")
    authority_url: str = Field(
        default="https://login.microsoftonline.com",
        description="Azure AD authority URL",
    )
    graph_api_endpoint: str = Field(
        default="https://graph.microsoft.com/v1.0",
        description="Microsoft Graph API endpoint",
    )
    scopes: list[str] = Field(
        default_factory=lambda: ["https://graph.microsoft.com/.default"],
        description="OAuth2 scopes for Graph API",
    )
    
    @classmethod
    async def from_key_vault(cls, key_vault_client, monitored_email: str) -> "GraphAPISettings":
        """Create GraphAPISettings from Azure Key Vault credentials.
        
        Args:
            key_vault_client: Initialized AzureKeyVaultClient instance
            monitored_email: Email address to monitor (from environment variable)
            
        Returns:
            GraphAPISettings with credentials from Key Vault
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        try:
            from ..services.azure_key_vault_client import KeyVaultException
        except ImportError:
            from services.azure_key_vault_client import KeyVaultException
        
        try:
            # Retrieve Graph API credentials from Key Vault
            graph_credentials = await key_vault_client.get_graph_api_credentials()
            
            return cls(
                tenant_id=graph_credentials.tenant_id,
                client_id=graph_credentials.client_id,
                client_secret=graph_credentials.client_secret.get_secret_value(),
                monitored_email=monitored_email,
                authority_url="https://login.microsoftonline.com",
                graph_api_endpoint="https://graph.microsoft.com/v1.0",
                scopes=["https://graph.microsoft.com/.default"]
            )
            
        except Exception as e:
            raise KeyVaultException(f"Failed to create GraphAPISettings from Key Vault: {e}") from e


class ProcessingSettings(BaseModel):
    """Email processing configuration settings."""

    polling_interval_seconds: int = Field(
        default=300, description="Interval between inbox checks in seconds"  # 5 minutes
    )
    batch_size: int = Field(default=10, description="Maximum number of emails to process per batch")
    max_retry_attempts: int = Field(
        default=3, description="Maximum retry attempts for failed operations"
    )
    retry_delay_seconds: int = Field(
        default=30, description="Delay between retry attempts in seconds"
    )
    processed_folder_prefix: str = Field(
        default="Processed", description="Prefix for processed email folders"
    )


class LoggingSettings(BaseModel):
    """Logging configuration settings."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Logging format (json or standard)")

    @model_validator(mode="after")
    def validate_level(self) -> "LoggingSettings":
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            raise ValueError(f"Invalid logging level: {self.level}")
        return self


class OutputSettings(BaseModel):
    """Output configuration for processed emails."""

    storage_type: str = Field(
        default="file",
        description="Storage type for processed emails (file, blob, or api)",
    )
    output_directory: str = Field(
        default="./output", description="Directory for storing processed email files"
    )
    api_endpoint: str | None = Field(
        None,
        description="API endpoint for sending processed emails (if storage_type is 'api')",
    )
    api_key: str | None = Field(
        None, description="API key for authentication (if storage_type is 'api')"
    )

    @model_validator(mode="after")
    def validate_api_settings(self) -> "OutputSettings":
        """Validate API settings when storage_type is 'api'."""
        if self.storage_type == "api" and not self.api_endpoint:
            raise ValueError("api_endpoint is required when storage_type is 'api'")
        return self


class AzureAIFoundrySettings(BaseModel):
    """Azure AI Foundry configuration settings."""

    endpoint: str = Field(..., description="Azure AI Foundry endpoint")
    connection_string: str = Field(..., description="Azure AI Foundry connection string")
    original_subject_classifier_agent_name: str = Field(
        default="original-subject-extractor",
        description="Agent name for original subject extraction"
    )
    
    @classmethod
    async def from_key_vault(cls, key_vault_client) -> "AzureAIFoundrySettings":
        """Create AzureAIFoundrySettings from Azure Key Vault credentials.
        
        Args:
            key_vault_client: Initialized AzureKeyVaultClient instance
            
        Returns:
            AzureAIFoundrySettings with credentials from Key Vault
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        try:
            from ..services.azure_key_vault_client import KeyVaultException
        except ImportError:
            from services.azure_key_vault_client import KeyVaultException
        
        try:
            # Retrieve AI Foundry credentials from Key Vault
            ai_foundry_credentials = await key_vault_client.get_ai_foundry_credentials()
            
            return cls(
                endpoint=ai_foundry_credentials.endpoint,
                connection_string=""  # No longer used with Service Principal authentication
            )
            
        except Exception as e:
            raise KeyVaultException(f"Failed to create AzureAIFoundrySettings from Key Vault: {e}") from e


class SalesforceSettings(BaseModel):
    """Salesforce API configuration settings."""

    base_url: str = Field(..., description="Salesforce base URL")
    client_id: str = Field(..., description="Salesforce client ID")
    client_secret: str = Field(..., description="Salesforce client secret")
    token_endpoint: str = Field(..., description="Salesforce token endpoint")
    api_version: str = Field(default="v64.0", description="Salesforce API version")
    case_record_type_id: str = Field(..., description="Case record type ID")
    case_queue: str = Field(..., description="Case queue name")
    
    @classmethod
    async def from_key_vault(cls, key_vault_client) -> "SalesforceSettings":
        """Create SalesforceSettings from Azure Key Vault credentials.
        
        Args:
            key_vault_client: Initialized AzureKeyVaultClient instance
            
        Returns:
            SalesforceSettings with credentials from Key Vault
            
        Raises:
            KeyVaultException: If credential retrieval fails
        """
        try:
            from ..services.azure_key_vault_client import KeyVaultException
        except ImportError:
            from services.azure_key_vault_client import KeyVaultException
        
        try:
            # Retrieve Salesforce credentials from Key Vault
            salesforce_credentials = await key_vault_client.get_salesforce_credentials()
            
            return cls(
                base_url=salesforce_credentials.base_url,
                client_id=salesforce_credentials.client_id,
                client_secret=salesforce_credentials.client_secret.get_secret_value(),
                token_endpoint=salesforce_credentials.token_endpoint,
                api_version=salesforce_credentials.api_version,
                case_record_type_id=salesforce_credentials.case_record_type_id,
                case_queue=salesforce_credentials.case_queue
            )
            
        except Exception as e:
            raise KeyVaultException(f"Failed to create SalesforceSettings from Key Vault: {e}") from e


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
    
    # Azure AI Foundry secret names in Key Vault
    azure_ai_foundry_endpoint_secret_name: str = Field(
        default="azure-ai-foundry-endpoint",
        description="Key Vault secret name for Azure AI Foundry endpoint"
    )
    azure_ai_foundry_tenant_id_secret_name: str = Field(
        default="azure-ai-foundry-tenant-id",
        description="Key Vault secret name for Azure AI Foundry tenant ID"
    )
    azure_ai_foundry_client_id_secret_name: str = Field(
        default="azure-ai-foundry-client-id", 
        description="Key Vault secret name for Azure AI Foundry client ID"
    )
    azure_ai_foundry_client_secret_secret_name: str = Field(
        default="azure-ai-foundry-client-secret",
        description="Key Vault secret name for Azure AI Foundry client secret"
    )
    
    # Graph API secret names in Key Vault
    graph_api_tenant_id_secret_name: str = Field(
        default="graph-api-tenant-id",
        description="Key Vault secret name for Graph API tenant ID"
    )
    graph_api_client_id_secret_name: str = Field(
        default="graph-api-client-id",
        description="Key Vault secret name for Graph API client ID"
    )
    graph_api_client_secret_secret_name: str = Field(
        default="graph-api-client-secret", 
        description="Key Vault secret name for Graph API client secret"
    )
    
    # Salesforce secret names in Key Vault
    salesforce_base_url_secret_name: str = Field(
        default="sf-base-url",
        description="Key Vault secret name for Salesforce base URL"
    )
    salesforce_client_id_secret_name: str = Field(
        default="sf-client-id",
        description="Key Vault secret name for Salesforce client ID"
    )
    salesforce_client_secret_secret_name: str = Field(
        default="sf-client-secret",
        description="Key Vault secret name for Salesforce client secret"
    )
    salesforce_token_endpoint_secret_name: str = Field(
        default="sf-token-endpoint",
        description="Key Vault secret name for Salesforce token endpoint"
    )
    salesforce_api_version_secret_name: str = Field(
        default="sf-api-version",
        description="Key Vault secret name for Salesforce API version"
    )
    salesforce_case_record_type_id_secret_name: str = Field(
        default="sf-case-record-type-id",
        description="Key Vault secret name for Salesforce case record type ID"
    )
    salesforce_case_queue_secret_name: str = Field(
        default="sf-case-queue",
        description="Key Vault secret name for Salesforce case queue"
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




class TestModeSettings(BaseModel):
    """Test mode configuration settings."""

    enabled: bool = Field(default=False, description="Enable test mode for all services")
    email_test_mode: bool = Field(default=False, description="Enable test mode specifically for email functionality")
    test_sender_email: str = Field(
        default="", description="Your test email address that sends emails"
    )
    target_salesforce_email: str = Field(
        default="", description="Real Salesforce customer email to substitute"
    )
    force_scenario: int | None = Field(
        default=None,
        description="Force a specific scenario for testing (e.g., 9 for email invalid)",
    )
    force_scenario_9: bool = Field(
        default=False,
        description="Explicit flag to force Scenario 9 (email invalid) - must be True to activate",
    )

    @model_validator(mode="after")
    def validate_test_mode(self) -> "TestModeSettings":
        """Validate test mode settings when enabled."""
        if self.enabled:
            if not self.test_sender_email:
                raise ValueError("test_sender_email is required when test mode is enabled")
            if not self.target_salesforce_email:
                raise ValueError("target_salesforce_email is required when test mode is enabled")

        # Validate force_scenario if provided
        if self.force_scenario is not None:
            valid_scenarios = [5, 6, 7, 8, 9, 10, 11]
            if self.force_scenario not in valid_scenarios:
                raise ValueError(
                    f"force_scenario must be one of {valid_scenarios}, got {self.force_scenario}"
                )

        return self


class ContentFormattingSettings(BaseModel):
    """Content formatting configuration settings."""
    
    content_format: str = Field(
        default="structured", 
        description="Format type: raw, clean_text, structured"
    )
    max_description_length: int = Field(
        default=30000, 
        description="Maximum length for case description"
    )
    preserve_signature: bool = Field(
        default=True, 
        description="Whether to preserve email signature information"
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include customer metadata in description"
    )
    truncate_html_fallback: bool = Field(
        default=True,
        description="Whether to truncate raw HTML if cleaning fails"
    )
    
    @model_validator(mode="after")
    def validate_content_format(self) -> "ContentFormattingSettings":
        """Validate content format setting."""
        valid_formats = ["raw", "clean_text", "structured"]
        if self.content_format not in valid_formats:
            raise ValueError(f"Invalid content format: {self.content_format}. Must be one of {valid_formats}")
        return self


class ScenarioSettings(BaseModel):
    """Scenario-specific configuration settings."""

    test_email: str = Field(..., description="Test email for all scenarios")
    victoria_grant_email: str = Field(..., description="Victoria Grant email address")
    account_team_email: str = Field(..., description="Account team email address")


class MonitoringSettings(BaseModel):
    """Health monitoring and operational settings."""
    
    health_check_port: int = Field(
        default=8080,
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


class PromptManagementSettings(BaseModel):
    """External prompt management configuration settings."""
    
    prompts_base_path: str = Field(
        default="prompts",
        description="Base path for external prompt files (relative to application root)"
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="Time-to-live for prompt cache entries in seconds"
    )
    enable_hot_reload: bool = Field(
        default=False,
        description="Enable hot reloading of prompt files in development"
    )
    schema_validation: bool = Field(
        default=True,
        description="Enable schema validation for prompt files"
    )
    max_cache_size: int = Field(
        default=100,
        description="Maximum number of cached prompt entries"
    )
    preload_prompts: List[str] = Field(
        default_factory=lambda: ["email_classification", "email_forwarding"],
        description="List of prompt categories to preload on startup"
    )
    performance_monitoring: bool = Field(
        default=True,
        description="Enable performance monitoring for prompt operations"
    )
    fallback_enabled: bool = Field(
        default=True,
        description="Enable fallback to hardcoded prompts when external prompts fail"
    )


class AppSettings(BaseModel):
    """Main application settings."""

    graph_api: GraphAPISettings
    processing: ProcessingSettings
    logging: LoggingSettings
    output: OutputSettings
    azure_ai_foundry: AzureAIFoundrySettings
    salesforce: SalesforceSettings
    databricks_oauth: DatabricksOAuthSettings
    key_vault: KeyVaultSettings
    scenarios: ScenarioSettings
    test_mode: TestModeSettings
    content_formatting: ContentFormattingSettings
    monitoring: MonitoringSettings
    prompt_management: PromptManagementSettings
    scenario_tracking: ScenarioTrackingConfiguration = Field(
        default_factory=ScenarioTrackingConfiguration,
        description="Scenario processing tracking configuration"
    )
    tracking_integration: TrackingIntegrationSettings = Field(
        default_factory=TrackingIntegrationSettings.from_environment,
        description="Email processor integration settings for scenario tracking"
    )
    email_processor_integration: EmailProcessorIntegrationSettings = Field(
        default_factory=EmailProcessorIntegrationSettings,
        description="Email processor specific integration settings"
    )
    environment: str = Field(default="development", description="Application environment")
    dry_run: bool = Field(default=False, description="Run in dry-run mode (don't move emails)")


async def get_settings(test_mode: bool = False) -> AppSettings:
    """Get application settings from environment variables and Key Vault.
    
    Args:
        test_mode: Whether to use mock services (True) or real services (False)
    """
    # Initialize Key Vault client first
    try:
        from services.azure_key_vault_client import AzureKeyVaultClient
    except ImportError:
        try:
            from ..services.azure_key_vault_client import AzureKeyVaultClient
        except ImportError:
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from services.azure_key_vault_client import AzureKeyVaultClient
    
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
        # Azure AI Foundry secret names from environment variables or defaults
        azure_ai_foundry_endpoint_secret_name=os.getenv(
            "KEY_VAULT_AZURE_AI_FOUNDRY_ENDPOINT_SECRET",
            "azure-ai-foundry-endpoint"
        ),
        azure_ai_foundry_tenant_id_secret_name=os.getenv(
            "KEY_VAULT_AZURE_AI_FOUNDRY_TENANT_ID_SECRET",
            "azure-ai-foundry-tenant-id"
        ),
        azure_ai_foundry_client_id_secret_name=os.getenv(
            "KEY_VAULT_AZURE_AI_FOUNDRY_CLIENT_ID_SECRET",
            "azure-ai-foundry-client-id"
        ),
        azure_ai_foundry_client_secret_secret_name=os.getenv(
            "KEY_VAULT_AZURE_AI_FOUNDRY_CLIENT_SECRET_SECRET",
            "azure-ai-foundry-client-secret"
        ),
        # Graph API secret names from environment variables or defaults
        graph_api_tenant_id_secret_name=os.getenv(
            "KEY_VAULT_GRAPH_API_TENANT_ID_SECRET",
            "graph-api-tenant-id"
        ),
        graph_api_client_id_secret_name=os.getenv(
            "KEY_VAULT_GRAPH_API_CLIENT_ID_SECRET",
            "graph-api-client-id"
        ),
        graph_api_client_secret_secret_name=os.getenv(
            "KEY_VAULT_GRAPH_API_CLIENT_SECRET_SECRET",
            "graph-api-client-secret"
        ),
        # Salesforce secret names from environment variables or defaults
        salesforce_base_url_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_BASE_URL_SECRET",
            "sf-base-url"
        ),
        salesforce_client_id_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_CLIENT_ID_SECRET",
            "sf-client-id"
        ),
        salesforce_client_secret_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_CLIENT_SECRET_SECRET",
            "sf-client-secret"
        ),
        salesforce_token_endpoint_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_TOKEN_ENDPOINT_SECRET",
            "sf-token-endpoint"
        ),
        salesforce_api_version_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_API_VERSION_SECRET",
            "sf-api-version"
        ),
        salesforce_case_record_type_id_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_CASE_RECORD_TYPE_ID_SECRET",
            "sf-case-record-type-id"
        ),
        salesforce_case_queue_secret_name=os.getenv(
            "KEY_VAULT_SALESFORCE_CASE_QUEUE_SECRET",
            "sf-case-queue"
        ),
    )
    
    # Initialize Key Vault client and retrieve credentials
    async with AzureKeyVaultClient(key_vault_settings, test_mode=test_mode) as key_vault_client:
        graph_api = await GraphAPISettings.from_key_vault(
            key_vault_client, 
            os.getenv("GRAPH_API_MONITORED_EMAIL", "")
        )
        azure_ai_foundry = await AzureAIFoundrySettings.from_key_vault(key_vault_client)
        salesforce = await SalesforceSettings.from_key_vault(key_vault_client)
    
    return AppSettings(
        graph_api=graph_api,
        processing=ProcessingSettings(
            polling_interval_seconds=int(os.getenv("INBOX_MONITOR_POLLING_INTERVAL", "300")),
            batch_size=int(os.getenv("INBOX_MONITOR_BATCH_SIZE", "10")),
            max_retry_attempts=int(os.getenv("INBOX_MONITOR_MAX_RETRY_ATTEMPTS", "3")),
            retry_delay_seconds=int(os.getenv("INBOX_MONITOR_RETRY_DELAY", "30")),
            processed_folder_prefix=os.getenv("INBOX_MONITOR_PROCESSED_FOLDER_PREFIX", "Processed"),
        ),
        logging=LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"), format=os.getenv("LOG_FORMAT", "json")
        ),
        output=OutputSettings(
            storage_type=os.getenv("INBOX_MONITOR_OUTPUT_TYPE", "file"),
            output_directory=os.getenv("INBOX_MONITOR_OUTPUT_DIR", "./output"),
            api_endpoint=os.getenv("INBOX_MONITOR_API_ENDPOINT"),
            api_key=os.getenv("INBOX_MONITOR_API_KEY"),
        ),
        azure_ai_foundry=azure_ai_foundry,
        salesforce=salesforce,
        databricks_oauth=DatabricksOAuthSettings(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME", ""),
            http_path=os.getenv("DATABRICKS_HTTP_PATH", ""),
            catalog=os.getenv("DATABRICKS_CATALOG", ""),
            schema_name=os.getenv("DATABRICKS_SCHEMA", ""),
            table_suffix=os.getenv("DATABRICKS_TABLE_SUFFIX", ""),
        ),
        key_vault=key_vault_settings,
        scenarios=ScenarioSettings(
            test_email=os.getenv("INBOX_MONITOR_TEST_EMAIL", ""),
            victoria_grant_email=os.getenv("SCENARIO_VICTORIA_GRANT_EMAIL", ""),
            account_team_email=os.getenv("SCENARIO_ACCOUNT_TEAM_EMAIL", ""),
        ),
        test_mode=TestModeSettings(
            enabled=test_mode,  # Use the parameter passed to get_settings() - controls service mocking
            email_test_mode=os.getenv("TEST_MODE_EMAIL", "false").lower() == "true",  # Controls email substitution only
            test_sender_email=os.getenv("TEST_EMAIL_SENDER", ""),
            target_salesforce_email=os.getenv("TEST_SALESFORCE_EMAIL", ""),
            force_scenario=int(os.getenv("TEST_FORCE_SCENARIO"))
            if os.getenv("TEST_FORCE_SCENARIO")
            else None,
            force_scenario_9=os.getenv("FORCE_SCENARIO_9", "false").lower() == "true",
        ),
        content_formatting=ContentFormattingSettings(
            content_format=os.getenv("CONTENT_FORMAT", "structured"),
            max_description_length=int(os.getenv("CONTENT_MAX_DESCRIPTION_LENGTH", "30000")),
            preserve_signature=os.getenv("CONTENT_PRESERVE_SIGNATURE", "true").lower() == "true",
            include_metadata=os.getenv("CONTENT_INCLUDE_METADATA", "true").lower() == "true",
            truncate_html_fallback=os.getenv("CONTENT_TRUNCATE_HTML_FALLBACK", "true").lower() == "true",
        ),
        monitoring=MonitoringSettings(
            health_check_port=int(os.getenv("HEALTH_CHECK_PORT", "8080")),
            health_check_enabled=os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true",
            metrics_collection_interval_seconds=int(os.getenv("METRICS_COLLECTION_INTERVAL", "60")),
            connection_pool_health_check_interval_seconds=int(os.getenv("CONNECTION_POOL_HEALTH_CHECK_INTERVAL", "30")),
            oauth_health_check_interval_seconds=int(os.getenv("OAUTH_HEALTH_CHECK_INTERVAL", "120")),
        ),
        prompt_management=PromptManagementSettings(
            prompts_base_path=os.getenv("PROMPTS_BASE_PATH", "prompts"),
            cache_ttl_seconds=int(os.getenv("PROMPT_CACHE_TTL_SECONDS", "300")),
            enable_hot_reload=os.getenv("PROMPT_ENABLE_HOT_RELOAD", "false").lower() == "true",
            schema_validation=os.getenv("PROMPT_SCHEMA_VALIDATION", "true").lower() == "true",
            max_cache_size=int(os.getenv("PROMPT_MAX_CACHE_SIZE", "100")),
            preload_prompts=os.getenv("PROMPT_PRELOAD_LIST", "email_classification,email_forwarding").split(","),
            performance_monitoring=os.getenv("PROMPT_PERFORMANCE_MONITORING", "true").lower() == "true",
            fallback_enabled=os.getenv("PROMPT_FALLBACK_ENABLED", "true").lower() == "true",
        ),
        scenario_tracking=ScenarioTrackingConfiguration(
            enabled=os.getenv("SCENARIO_TRACKING_ENABLED", "true").lower() == "true",
            table_suffix=os.getenv("SCENARIO_TRACKING_TABLE_SUFFIX", ""),
            batch_insert_size=int(os.getenv("SCENARIO_TRACKING_BATCH_SIZE", "100")),
            async_insert=os.getenv("SCENARIO_TRACKING_ASYNC_INSERT", "true").lower() == "true",
            retry_attempts=int(os.getenv("SCENARIO_TRACKING_RETRY_ATTEMPTS", "3")),
            retry_delay_seconds=float(os.getenv("SCENARIO_TRACKING_RETRY_DELAY", "2.0")),
            connection_timeout_seconds=int(os.getenv("SCENARIO_TRACKING_CONNECTION_TIMEOUT", "30")),
            performance_monitoring_enabled=os.getenv("SCENARIO_TRACKING_PERFORMANCE_MONITORING", "true").lower() == "true",
            slow_query_threshold_ms=int(os.getenv("SCENARIO_TRACKING_SLOW_QUERY_THRESHOLD", "5000")),
            health_check_interval_seconds=int(os.getenv("SCENARIO_TRACKING_HEALTH_CHECK_INTERVAL", "300")),
            data_retention_days=int(os.getenv("SCENARIO_TRACKING_DATA_RETENTION_DAYS", "365")),
            archive_after_days=int(os.getenv("SCENARIO_TRACKING_ARCHIVE_AFTER_DAYS", "90")),
            cleanup_enabled=os.getenv("SCENARIO_TRACKING_CLEANUP_ENABLED", "false").lower() == "true",
        ),
        environment=os.getenv("ENVIRONMENT", "development"),
        dry_run=os.getenv("INBOX_MONITOR_DRY_RUN", "false").lower() == "true",
    )


def validate_settings(settings: AppSettings) -> bool:
    """Validate that all required settings are present."""
    missing_fields = []

    # Graph API and Azure AI Foundry validation removed - now handled by Key Vault
    
    # Validate monitored email is still required from environment
    if not settings.graph_api.monitored_email:
        missing_fields.append("GRAPH_API_MONITORED_EMAIL")

    # Salesforce validation removed - now handled by Key Vault

    # Validate Databricks OAuth settings
    if not settings.databricks_oauth.server_hostname:
        missing_fields.append("DATABRICKS_SERVER_HOSTNAME")
    if not settings.databricks_oauth.http_path:
        missing_fields.append("DATABRICKS_HTTP_PATH")
    if not settings.databricks_oauth.catalog:
        missing_fields.append("DATABRICKS_CATALOG")
    if not settings.databricks_oauth.schema_name:
        missing_fields.append("DATABRICKS_SCHEMA")

    # Validate scenario settings
    if not settings.scenarios.test_email:
        missing_fields.append("INBOX_MONITOR_TEST_EMAIL")
    if not settings.scenarios.victoria_grant_email:
        missing_fields.append("SCENARIO_VICTORIA_GRANT_EMAIL")
    if not settings.scenarios.account_team_email:
        missing_fields.append("SCENARIO_ACCOUNT_TEAM_EMAIL")

    # Validate Key Vault settings
    if not settings.key_vault.key_vault_url:
        missing_fields.append("AZURE_KEY_VAULT_URL")
    if not settings.key_vault.azure_tenant_id:
        missing_fields.append("AZURE_TENANT_ID")
    if not settings.key_vault.azure_client_id:
        missing_fields.append("AZURE_CLIENT_ID")
    if not settings.key_vault.azure_client_secret.get_secret_value():
        missing_fields.append("AZURE_CLIENT_SECRET")

    # Validate output settings for API type
    if settings.output.storage_type == "api" and not settings.output.api_endpoint:
        missing_fields.append("INBOX_MONITOR_API_ENDPOINT")

    if missing_fields:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")

    return True
