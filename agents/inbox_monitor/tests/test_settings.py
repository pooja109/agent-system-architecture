"""
Tests for Configuration Settings
================================
Unit tests for settings and configuration management.
"""
import os
from unittest.mock import AsyncMock, patch
import pytest
from config.settings import (
    AppSettings,
    GraphAPISettings,
    LoggingSettings,
    OutputSettings,
    ProcessingSettings,
    AzureAIFoundrySettings,
    SalesforceSettings,
    get_settings,
    validate_settings,
)
@pytest.mark.fast
@pytest.mark.unit
class TestGraphAPISettings:
    """Test GraphAPISettings model."""
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_graph_api_settings_creation(self):
        """Test creating Graph API settings."""
        settings = GraphAPISettings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            monitored_email="test@example.com",
        )
        assert settings.tenant_id == "test-tenant"
        assert settings.client_id == "test-client"
        assert settings.client_secret == "test-secret"
        assert settings.monitored_email == "test@example.com"
        assert settings.authority_url == "https://login.microsoftonline.com"
        assert settings.graph_api_endpoint == "https://graph.microsoft.com/v1.0"
        assert settings.scopes == ["https://graph.microsoft.com/.default"]
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_graph_api_settings_custom_urls(self):
        """Test Graph API settings with custom URLs."""
        settings = GraphAPISettings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            monitored_email="test@example.com",
            authority_url="https://custom.authority.com",
            graph_api_endpoint="https://custom.graph.com/v2.0",
        )
        assert settings.authority_url == "https://custom.authority.com"
        assert settings.graph_api_endpoint == "https://custom.graph.com/v2.0"
class TestProcessingSettings:
    """Test ProcessingSettings model."""
    @pytest.mark.retry
    @pytest.mark.medium
    @pytest.mark.unit
    @pytest.mark.fast
    def test_processing_settings_defaults(self):
        """Test processing settings with defaults."""
        settings = ProcessingSettings()
        assert settings.polling_interval_seconds == 300
        assert settings.batch_size == 10
        assert settings.max_retry_attempts == 3
        assert settings.retry_delay_seconds == 30
        assert settings.processed_folder_prefix == "Processed"
    @pytest.mark.retry
    @pytest.mark.medium
    @pytest.mark.unit
    @pytest.mark.fast
    def test_processing_settings_custom(self):
        """Test processing settings with custom values."""
        settings = ProcessingSettings(
            polling_interval_seconds=600,
            batch_size=20,
            max_retry_attempts=5,
            retry_delay_seconds=60,
            processed_folder_prefix="Archived",
        )
        assert settings.polling_interval_seconds == 600
        assert settings.batch_size == 20
        assert settings.max_retry_attempts == 5
        assert settings.retry_delay_seconds == 60
        assert settings.processed_folder_prefix == "Archived"
class TestLoggingSettings:
    """Test LoggingSettings model."""
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_logging_settings_defaults(self):
        """Test logging settings with defaults."""
        settings = LoggingSettings()
        assert settings.level == "INFO"
        assert settings.format == "json"
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_logging_settings_valid_level(self):
        """Test logging settings with valid level."""
        settings = LoggingSettings(level="DEBUG", format="standard")
        assert settings.level == "DEBUG"
        assert settings.format == "standard"


    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.unit
    @pytest.mark.fast
    def test_logging_settings_invalid_level(self):
        """Test logging settings with invalid level."""
        with pytest.raises(ValueError, match="Invalid logging level"):
            LoggingSettings(level="INVALID")
class TestOutputSettings:
    """Test OutputSettings model."""
    @pytest.mark.email
    @pytest.mark.medium
    @pytest.mark.unit
    @pytest.mark.fast
    def test_output_settings_file_storage(self):
        """Test output settings for file storage."""
        settings = OutputSettings(storage_type="file", output_directory="/tmp/emails")
        assert settings.storage_type == "file"
        assert settings.output_directory == "/tmp/emails"
        assert settings.api_endpoint is None
        assert settings.api_key is None
    @pytest.mark.email
    @pytest.mark.medium
    @pytest.mark.unit
    @pytest.mark.fast
    def test_output_settings_api_storage(self):
        """Test output settings for API storage."""
        settings = OutputSettings(
            storage_type="api",
            api_endpoint="https://api.example.com/emails",
            api_key="test-key",
        )
        assert settings.storage_type == "api"
        assert settings.api_endpoint == "https://api.example.com/emails"
        assert settings.api_key == "test-key"


    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_output_settings_api_missing_endpoint(self):
        """Test API storage without endpoint raises error."""
        with pytest.raises(ValueError, match="api_endpoint is required"):
            OutputSettings(storage_type="api")
class TestAppSettings:
    """Test AppSettings model."""
    @pytest.mark.azure
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.unit
    def test_app_settings_creation(self, mock_settings):
        """Test creating app settings."""
        assert mock_settings.environment == "test"
        assert mock_settings.dry_run is False
        assert mock_settings.graph_api.tenant_id == "test-tenant-id"
        assert mock_settings.processing.batch_size == 10
        assert mock_settings.logging.level == "INFO"
        assert mock_settings.output.storage_type == "file"
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.unit
    def test_app_settings_dry_run(self, mock_settings):
        """Test app settings with dry run enabled."""
        mock_settings.dry_run = True
        assert mock_settings.dry_run is True
class TestGetSettings:
    """Test get_settings function."""
    @patch.dict(
        os.environ,
        {
            "AZURE_KEY_VAULT_URL": "https://test-vault.vault.azure.net/",
            "AZURE_TENANT_ID": "test-tenant",
            "AZURE_CLIENT_ID": "test-client",
            "AZURE_CLIENT_SECRET": "test-secret",
            "GRAPH_API_MONITORED_EMAIL": "env@example.com",
            "INBOX_MONITOR_POLLING_INTERVAL": "600",
            "INBOX_MONITOR_BATCH_SIZE": "20",
            "LOG_LEVEL": "DEBUG",
            "ENVIRONMENT": "production",
            "INBOX_MONITOR_DRY_RUN": "true",
            "DATABRICKS_SERVER_HOSTNAME": "test.databricks.com",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/test",
            "DATABRICKS_CATALOG": "test_catalog",
            "DATABRICKS_SCHEMA": "test_schema",
            "INBOX_MONITOR_TEST_EMAIL": "test@example.com",
            "SCENARIO_VICTORIA_GRANT_EMAIL": "victoria@test.com",
            "SCENARIO_ACCOUNT_TEAM_EMAIL": "team@test.com",
        },
    )
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @patch("services.azure_key_vault_client.AzureKeyVaultClient")
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_get_settings_from_env(self, mock_key_vault_client):
        """Test getting settings from environment variables."""
        # Mock Key Vault client and its methods
        mock_client_instance = AsyncMock()
        mock_key_vault_client.return_value.__aenter__.return_value = mock_client_instance
        # Mock the from_key_vault class methods
        with patch("config.settings.GraphAPISettings.from_key_vault") as mock_graph_kv, \
             patch("config.settings.AzureAIFoundrySettings.from_key_vault") as mock_ai_kv, \
             patch("config.settings.SalesforceSettings.from_key_vault") as mock_sf_kv:
            # Set up return values for Key Vault methods
            mock_graph_kv.return_value = GraphAPISettings(
                tenant_id="env-tenant",
                client_id="env-client", 
                client_secret="env-secret",
                monitored_email="env@example.com"
            )
            mock_ai_kv.return_value = AzureAIFoundrySettings(
                endpoint="https://test.ai.azure.com",
                connection_string="test-connection"
            )
            mock_sf_kv.return_value = SalesforceSettings(
                base_url="https://test.salesforce.com",
                client_id="sf-client",
                client_secret="sf-secret", 
                token_endpoint="https://test.salesforce.com/oauth2/token",
                api_version="v64.0",
                case_record_type_id="012000000000000",
                case_queue="Test Queue"
            )
            settings = await get_settings()
        assert settings.graph_api.tenant_id == "env-tenant"
        assert settings.graph_api.client_id == "env-client"
        assert settings.graph_api.client_secret == "env-secret"
        assert settings.graph_api.monitored_email == "env@example.com"
        assert settings.processing.polling_interval_seconds == 600
        assert settings.processing.batch_size == 20
        assert settings.logging.level == "DEBUG"
        assert settings.environment == "production"
        assert settings.dry_run is True
    @patch.dict(
        os.environ, 
        {
            "AZURE_KEY_VAULT_URL": "https://test-vault.vault.azure.net/",
            "AZURE_TENANT_ID": "test-tenant",
            "AZURE_CLIENT_ID": "test-client", 
            "AZURE_CLIENT_SECRET": "test-secret",
            "GRAPH_API_MONITORED_EMAIL": "test@example.com",
            "DATABRICKS_SERVER_HOSTNAME": "test.databricks.com",
            "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/test",
            "DATABRICKS_CATALOG": "test_catalog",
            "DATABRICKS_SCHEMA": "test_schema",
            "INBOX_MONITOR_TEST_EMAIL": "test@example.com",
            "SCENARIO_VICTORIA_GRANT_EMAIL": "victoria@test.com",
            "SCENARIO_ACCOUNT_TEAM_EMAIL": "team@test.com",
        }, 
        clear=False
    )
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
    @pytest.mark.azure
    @patch("services.azure_key_vault_client.AzureKeyVaultClient")
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_get_settings_defaults(self, mock_key_vault_client):
        """Test getting settings with defaults when env vars not set."""
        # Mock Key Vault client and its methods
        mock_client_instance = AsyncMock()
        mock_key_vault_client.return_value.__aenter__.return_value = mock_client_instance
        # Mock the from_key_vault class methods with default values
        with patch("config.settings.GraphAPISettings.from_key_vault") as mock_graph_kv, \
             patch("config.settings.AzureAIFoundrySettings.from_key_vault") as mock_ai_kv, \
             patch("config.settings.SalesforceSettings.from_key_vault") as mock_sf_kv:
            # Set up return values for Key Vault methods with defaults
            mock_graph_kv.return_value = GraphAPISettings(
                tenant_id="",
                client_id="default-client",
                client_secret="default-secret",
                monitored_email="test@example.com"
            )
            mock_ai_kv.return_value = AzureAIFoundrySettings(
                endpoint="https://default.ai.azure.com",
                connection_string="default-connection"
            )
            mock_sf_kv.return_value = SalesforceSettings(
                base_url="https://default.salesforce.com",
                client_id="default-sf-client",
                client_secret="default-sf-secret",
                token_endpoint="https://default.salesforce.com/oauth2/token",
                api_version="v64.0",
                case_record_type_id="012000000000000",
                case_queue="Default Queue"
            )
            settings = await get_settings()
        assert settings.graph_api.tenant_id == ""
        assert settings.processing.polling_interval_seconds == 300
        assert settings.logging.level == "INFO"
        assert settings.environment == "development"
        assert settings.dry_run is False
class TestValidateSettings:
    """Test validate_settings function."""
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.unit
    def test_validate_settings_valid(self, mock_settings):
        """Test validating valid settings."""
        assert validate_settings(mock_settings) is True
    @pytest.mark.azure
    @pytest.mark.email
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.unit
    def test_validate_settings_missing_databricks(self):
        """Test validation fails with missing Databricks settings."""
        from config.settings import (
            AzureAIFoundrySettings, SalesforceSettings, DatabricksOAuthSettings,
            KeyVaultSettings, ScenarioSettings, TestModeSettings,
            ContentFormattingSettings, MonitoringSettings, PromptManagementSettings
        )
        settings = AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="test-tenant",
                client_id="test-client",
                client_secret="test-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(),
            logging=LoggingSettings(),
            output=OutputSettings(),
            azure_ai_foundry=AzureAIFoundrySettings(
                endpoint="https://test.ai.azure.com",
                connection_string="test-connection"
            ),
            salesforce=SalesforceSettings(
                base_url="https://test.salesforce.com",
                client_id="sf-test-client",
                client_secret="sf-test-secret",
                token_endpoint="https://test.salesforce.com/oauth2/token",
                api_version="v64.0",
                case_record_type_id="012000000000000",
                case_queue="Test Queue"
            ),
            databricks_oauth=DatabricksOAuthSettings(
                server_hostname="",  # Missing - this should cause validation failure
                http_path="/sql/1.0/warehouses/test",
                catalog="test_catalog",
                schema_name="test_schema",
                table_suffix="_test"
            ),
            key_vault=KeyVaultSettings(
                key_vault_url="https://test.vault.azure.net/",
                azure_tenant_id="test-tenant",
                azure_client_id="test-client",
                azure_client_secret="test-secret"
            ),
            scenarios=ScenarioSettings(
                test_email="test@example.com",
                victoria_grant_email="victoria@test.com",
                account_team_email="team@test.com"
            ),
            test_mode=TestModeSettings(),
            content_formatting=ContentFormattingSettings(),
            monitoring=MonitoringSettings(),
            prompt_management=PromptManagementSettings(),
            environment="test",
        )
        with pytest.raises(ValueError, match="Missing required environment variables"):
            validate_settings(settings)


    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_validate_settings_missing_api_endpoint(self):
        """Test validation fails with API storage but no endpoint."""
        # Test that Pydantic validation catches this at model creation
        with pytest.raises(ValueError, match="api_endpoint is required"):
            OutputSettings(storage_type="api", api_endpoint="")  # Missing