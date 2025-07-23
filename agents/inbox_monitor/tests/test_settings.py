"""
Tests for Configuration Settings
================================

Unit tests for settings and configuration management.
"""

import os
from unittest.mock import patch

import pytest

from ..config.settings import (
    AppSettings,
    GraphAPISettings,
    LoggingSettings,
    OutputSettings,
    ProcessingSettings,
    get_settings,
    validate_settings,
)


class TestGraphAPISettings:
    """Test GraphAPISettings model."""

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

    def test_processing_settings_defaults(self):
        """Test processing settings with defaults."""
        settings = ProcessingSettings()

        assert settings.polling_interval_seconds == 300
        assert settings.batch_size == 10
        assert settings.max_retry_attempts == 3
        assert settings.retry_delay_seconds == 30
        assert settings.processed_folder_prefix == "Processed"

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

    def test_logging_settings_defaults(self):
        """Test logging settings with defaults."""
        settings = LoggingSettings()

        assert settings.level == "INFO"
        assert settings.format == "json"

    def test_logging_settings_valid_level(self):
        """Test logging settings with valid level."""
        settings = LoggingSettings(level="DEBUG", format="standard")

        assert settings.level == "DEBUG"
        assert settings.format == "standard"

    def test_logging_settings_invalid_level(self):
        """Test logging settings with invalid level."""
        with pytest.raises(ValueError, match="Invalid logging level"):
            LoggingSettings(level="INVALID")


class TestOutputSettings:
    """Test OutputSettings model."""

    def test_output_settings_file_storage(self):
        """Test output settings for file storage."""
        settings = OutputSettings(storage_type="file", output_directory="/tmp/emails")

        assert settings.storage_type == "file"
        assert settings.output_directory == "/tmp/emails"
        assert settings.api_endpoint is None
        assert settings.api_key is None

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

    def test_output_settings_api_missing_endpoint(self):
        """Test API storage without endpoint raises error."""
        with pytest.raises(ValueError, match="api_endpoint is required"):
            OutputSettings(storage_type="api")


class TestAppSettings:
    """Test AppSettings model."""

    def test_app_settings_creation(self, mock_settings):
        """Test creating app settings."""
        assert mock_settings.environment == "test"
        assert mock_settings.dry_run is False
        assert mock_settings.graph_api.tenant_id == "test-tenant-id"
        assert mock_settings.processing.batch_size == 10
        assert mock_settings.logging.level == "INFO"
        assert mock_settings.output.storage_type == "file"

    def test_app_settings_dry_run(self, mock_settings):
        """Test app settings with dry run enabled."""
        mock_settings.dry_run = True
        assert mock_settings.dry_run is True


class TestGetSettings:
    """Test get_settings function."""

    @patch.dict(
        os.environ,
        {
            "GRAPH_API_TENANT_ID": "env-tenant",
            "GRAPH_API_CLIENT_ID": "env-client",
            "GRAPH_API_CLIENT_SECRET": "env-secret",
            "GRAPH_API_MONITORED_EMAIL": "env@example.com",
            "INBOX_MONITOR_POLLING_INTERVAL": "600",
            "INBOX_MONITOR_BATCH_SIZE": "20",
            "LOG_LEVEL": "DEBUG",
            "ENVIRONMENT": "production",
            "INBOX_MONITOR_DRY_RUN": "true",
        },
    )
    def test_get_settings_from_env(self):
        """Test getting settings from environment variables."""
        settings = get_settings()

        assert settings.graph_api.tenant_id == "env-tenant"
        assert settings.graph_api.client_id == "env-client"
        assert settings.graph_api.client_secret == "env-secret"
        assert settings.graph_api.monitored_email == "env@example.com"
        assert settings.processing.polling_interval_seconds == 600
        assert settings.processing.batch_size == 20
        assert settings.logging.level == "DEBUG"
        assert settings.environment == "production"
        assert settings.dry_run is True

    @patch.dict(os.environ, {}, clear=True)
    def test_get_settings_defaults(self):
        """Test getting settings with defaults when env vars not set."""
        settings = get_settings()

        assert settings.graph_api.tenant_id == ""
        assert settings.processing.polling_interval_seconds == 300
        assert settings.logging.level == "INFO"
        assert settings.environment == "development"
        assert settings.dry_run is False


class TestValidateSettings:
    """Test validate_settings function."""

    def test_validate_settings_valid(self, mock_settings):
        """Test validating valid settings."""
        assert validate_settings(mock_settings) is True

    def test_validate_settings_missing_graph_api(self):
        """Test validation fails with missing Graph API settings."""
        settings = AppSettings(
            graph_api=GraphAPISettings(
                tenant_id="",  # Missing
                client_id="test-client",
                client_secret="test-secret",
                monitored_email="test@example.com",
            ),
            processing=ProcessingSettings(),
            logging=LoggingSettings(),
            output=OutputSettings(),
            environment="test",
        )

        with pytest.raises(ValueError, match="Missing required environment variables"):
            validate_settings(settings)

    def test_validate_settings_missing_api_endpoint(self):
        """Test validation fails with API storage but no endpoint."""
        # Test that Pydantic validation catches this at model creation
        with pytest.raises(ValueError, match="api_endpoint is required"):
            OutputSettings(storage_type="api", api_endpoint="")  # Missing
