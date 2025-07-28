"""
Inbox Monitor Configuration Settings
====================================

Configuration management for the inbox monitor service using Pydantic models.
Loads settings from environment variables with validation.
"""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

# Load environment variables
load_dotenv()


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


class SalesforceSettings(BaseModel):
    """Salesforce API configuration settings."""

    base_url: str = Field(..., description="Salesforce base URL")
    client_id: str = Field(..., description="Salesforce client ID")
    client_secret: str = Field(..., description="Salesforce client secret")
    token_endpoint: str = Field(..., description="Salesforce token endpoint")
    api_version: str = Field(default="v64.0", description="Salesforce API version")
    case_record_type_id: str = Field(..., description="Case record type ID")
    case_queue: str = Field(..., description="Case queue name")


class DatabricksSettings(BaseModel):
    """Databricks configuration settings."""

    server_hostname: str = Field(..., description="Databricks server hostname")
    http_path: str = Field(..., description="Databricks HTTP path")
    access_token: str = Field(..., description="Databricks access token")
    catalog: str = Field(..., description="Databricks catalog name")
    schema_name: str = Field(..., description="Databricks schema name")
    table_suffix: str = Field(default="", description="Table suffix for environments")


class TestModeSettings(BaseModel):
    """Test mode configuration settings."""

    enabled: bool = Field(default=False, description="Enable test mode for email substitution")
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


class AppSettings(BaseModel):
    """Main application settings."""

    graph_api: GraphAPISettings
    processing: ProcessingSettings
    logging: LoggingSettings
    output: OutputSettings
    azure_ai_foundry: AzureAIFoundrySettings
    salesforce: SalesforceSettings
    databricks: DatabricksSettings
    scenarios: ScenarioSettings
    test_mode: TestModeSettings
    content_formatting: ContentFormattingSettings
    environment: str = Field(default="development", description="Application environment")
    dry_run: bool = Field(default=False, description="Run in dry-run mode (don't move emails)")


def get_settings() -> AppSettings:
    """Get application settings from environment variables."""
    return AppSettings(
        graph_api=GraphAPISettings(
            tenant_id=os.getenv("GRAPH_API_TENANT_ID", ""),
            client_id=os.getenv("GRAPH_API_CLIENT_ID", ""),
            client_secret=os.getenv("GRAPH_API_CLIENT_SECRET", ""),
            monitored_email=os.getenv("GRAPH_API_MONITORED_EMAIL", ""),
            authority_url=os.getenv("GRAPH_API_AUTHORITY_URL", "https://login.microsoftonline.com"),
            graph_api_endpoint=os.getenv("GRAPH_API_ENDPOINT", "https://graph.microsoft.com/v1.0"),
        ),
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
        azure_ai_foundry=AzureAIFoundrySettings(
            endpoint=os.getenv("AZURE_AI_ENDPOINT", ""),
            connection_string=os.getenv("AZURE_AI_CONNECTION_STRING", ""),
        ),
        salesforce=SalesforceSettings(
            base_url=os.getenv("SALESFORCE_BASE_URL", ""),
            client_id=os.getenv("SALESFORCE_CLIENT_ID", ""),
            client_secret=os.getenv("SALESFORCE_CLIENT_SECRET", ""),
            token_endpoint=os.getenv("SALESFORCE_TOKEN_ENDPOINT", ""),
            api_version=os.getenv("SALESFORCE_API_VERSION", "v64.0"),
            case_record_type_id=os.getenv("SALESFORCE_CASE_RECORD_TYPE_ID", ""),
            case_queue=os.getenv("SALESFORCE_CASE_QUEUE", ""),
        ),
        databricks=DatabricksSettings(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME", ""),
            http_path=os.getenv("DATABRICKS_HTTP_PATH", ""),
            access_token=os.getenv("DATABRICKS_ACCESS_TOKEN", ""),
            catalog=os.getenv("DATABRICKS_CATALOG", ""),
            schema_name=os.getenv("DATABRICKS_SCHEMA", ""),
            table_suffix=os.getenv("DATABRICKS_TABLE_SUFFIX", ""),
        ),
        scenarios=ScenarioSettings(
            test_email=os.getenv("INBOX_MONITOR_TEST_EMAIL", ""),
            victoria_grant_email=os.getenv("SCENARIO_VICTORIA_GRANT_EMAIL", ""),
            account_team_email=os.getenv("SCENARIO_ACCOUNT_TEAM_EMAIL", ""),
        ),
        test_mode=TestModeSettings(
            enabled=os.getenv("TEST_MODE", "false").lower() == "true",
            test_sender_email=os.getenv("TEST_EMAIL_SENDER", ""),
            target_salesforce_email=os.getenv("TEST_SALESFORCE_EMAIL", ""),
            force_scenario=int(os.getenv("TEST_FORCE_SCENARIO"))
            if os.getenv("TEST_FORCE_SCENARIO")
            else None,
        ),
        content_formatting=ContentFormattingSettings(
            content_format=os.getenv("CONTENT_FORMAT", "structured"),
            max_description_length=int(os.getenv("CONTENT_MAX_DESCRIPTION_LENGTH", "30000")),
            preserve_signature=os.getenv("CONTENT_PRESERVE_SIGNATURE", "true").lower() == "true",
            include_metadata=os.getenv("CONTENT_INCLUDE_METADATA", "true").lower() == "true",
            truncate_html_fallback=os.getenv("CONTENT_TRUNCATE_HTML_FALLBACK", "true").lower() == "true",
        ),
        environment=os.getenv("ENVIRONMENT", "development"),
        dry_run=os.getenv("INBOX_MONITOR_DRY_RUN", "false").lower() == "true",
    )


def validate_settings(settings: AppSettings) -> bool:
    """Validate that all required settings are present."""
    missing_fields = []

    # Validate Graph API settings
    if not settings.graph_api.tenant_id:
        missing_fields.append("GRAPH_API_TENANT_ID")
    if not settings.graph_api.client_id:
        missing_fields.append("GRAPH_API_CLIENT_ID")
    if not settings.graph_api.client_secret:
        missing_fields.append("GRAPH_API_CLIENT_SECRET")
    if not settings.graph_api.monitored_email:
        missing_fields.append("GRAPH_API_MONITORED_EMAIL")

    # Validate Azure AI Foundry settings
    if not settings.azure_ai_foundry.endpoint:
        missing_fields.append("AZURE_AI_ENDPOINT")
    if not settings.azure_ai_foundry.connection_string:
        missing_fields.append("AZURE_AI_CONNECTION_STRING")

    # Validate Salesforce settings
    if not settings.salesforce.base_url:
        missing_fields.append("SALESFORCE_BASE_URL")
    if not settings.salesforce.client_id:
        missing_fields.append("SALESFORCE_CLIENT_ID")
    if not settings.salesforce.client_secret:
        missing_fields.append("SALESFORCE_CLIENT_SECRET")
    if not settings.salesforce.token_endpoint:
        missing_fields.append("SALESFORCE_TOKEN_ENDPOINT")
    if not settings.salesforce.case_record_type_id:
        missing_fields.append("SALESFORCE_CASE_RECORD_TYPE_ID")
    if not settings.salesforce.case_queue:
        missing_fields.append("SALESFORCE_CASE_QUEUE")

    # Validate Databricks settings
    if not settings.databricks.server_hostname:
        missing_fields.append("DATABRICKS_SERVER_HOSTNAME")
    if not settings.databricks.http_path:
        missing_fields.append("DATABRICKS_HTTP_PATH")
    if not settings.databricks.access_token:
        missing_fields.append("DATABRICKS_ACCESS_TOKEN")
    if not settings.databricks.catalog:
        missing_fields.append("DATABRICKS_CATALOG")
    if not settings.databricks.schema_name:
        missing_fields.append("DATABRICKS_SCHEMA")

    # Validate scenario settings
    if not settings.scenarios.test_email:
        missing_fields.append("INBOX_MONITOR_TEST_EMAIL")
    if not settings.scenarios.victoria_grant_email:
        missing_fields.append("SCENARIO_VICTORIA_GRANT_EMAIL")
    if not settings.scenarios.account_team_email:
        missing_fields.append("SCENARIO_ACCOUNT_TEAM_EMAIL")

    # Validate output settings for API type
    if settings.output.storage_type == "api" and not settings.output.api_endpoint:
        missing_fields.append("INBOX_MONITOR_API_ENDPOINT")

    if missing_fields:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")

    return True
