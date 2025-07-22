"""
Test Mode Validation Tests
==========================

Tests to ensure test mode functionality works correctly for email substitution.
"""

from unittest.mock import Mock

import pytest
from config.settings import DatabricksSettings, TestModeSettings
from services.contact_lookup_service import ContactLookupService


class TestTestModeSettings:
    """Test test mode settings validation."""

    def test_test_mode_disabled_by_default(self):
        """Test that test mode is disabled by default."""
        settings = TestModeSettings()
        assert not settings.enabled
        assert settings.test_sender_email == ""
        assert settings.target_salesforce_email == ""

    def test_test_mode_validation_when_enabled(self):
        """Test validation when test mode is enabled."""
        with pytest.raises(ValueError, match="test_sender_email is required"):
            TestModeSettings(enabled=True, target_salesforce_email="test@salesforce.com")

        with pytest.raises(ValueError, match="target_salesforce_email is required"):
            TestModeSettings(enabled=True, test_sender_email="test@example.com")

    def test_test_mode_valid_configuration(self):
        """Test valid test mode configuration."""
        settings = TestModeSettings(
            enabled=True,
            test_sender_email="test@example.com",
            target_salesforce_email="real@salesforce.com",
        )
        assert settings.enabled
        assert settings.test_sender_email == "test@example.com"
        assert settings.target_salesforce_email == "real@salesforce.com"


class TestContactLookupServiceTestMode:
    """Test contact lookup service with test mode functionality."""

    @pytest.fixture
    def databricks_settings(self):
        """Mock Databricks settings."""
        return DatabricksSettings(
            server_hostname="test.databricks.com",
            http_path="/test/path",
            access_token="test_token",
            catalog="test_catalog",
            schema_name="test_schema",
        )

    @pytest.fixture
    def test_mode_settings_enabled(self):
        """Test mode settings with test mode enabled."""
        return TestModeSettings(
            enabled=True,
            test_sender_email="mytest@example.com",
            target_salesforce_email="real.customer@salesforce.com",
        )

    @pytest.fixture
    def test_mode_settings_disabled(self):
        """Test mode settings with test mode disabled."""
        return TestModeSettings(enabled=False)

    @pytest.fixture
    def mock_databricks_cursor(self):
        """Mock Databricks cursor."""
        cursor = Mock()
        cursor.fetchone.return_value = (
            "real.customer@salesforce.com",
            "001XXXXXXXXXXXXXXX",  # SF Account ID
            "003XXXXXXXXXXXXXXX",  # SF Contact ID
        )
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=None)
        return cursor

    @pytest.fixture
    def mock_databricks_connection(self, mock_databricks_cursor):
        """Mock Databricks connection."""
        connection = Mock()
        connection.cursor.return_value = mock_databricks_cursor
        return connection

    @pytest.mark.asyncio
    async def test_email_substitution_when_test_mode_enabled(
        self, databricks_settings, test_mode_settings_enabled, mock_databricks_connection
    ):
        """Test email substitution when test mode is enabled."""
        service = ContactLookupService(databricks_settings, test_mode_settings_enabled)
        service.connection = mock_databricks_connection

        # Test email should be substituted
        result = await service.lookup_contact_by_email("mytest@example.com")

        # Verify the query was made with the substituted email
        mock_databricks_connection.cursor().execute.assert_called_once()
        args = mock_databricks_connection.cursor().execute.call_args
        query_params = args[0][1]  # Second argument (parameters)
        assert query_params == ["real.customer@salesforce.com"]

        # Verify result contains original email but found data
        assert result.email == "mytest@example.com"  # Original email returned
        assert result.found is True
        assert result.sf_account_id == "001XXXXXXXXXXXXXXX"
        assert result.sf_contact_id == "003XXXXXXXXXXXXXXX"

    @pytest.mark.asyncio
    async def test_no_substitution_when_test_mode_disabled(
        self, databricks_settings, test_mode_settings_disabled, mock_databricks_connection
    ):
        """Test no email substitution when test mode is disabled."""
        service = ContactLookupService(databricks_settings, test_mode_settings_disabled)
        service.connection = mock_databricks_connection

        # Test email should NOT be substituted
        await service.lookup_contact_by_email("mytest@example.com")

        # Verify the query was made with the original email
        mock_databricks_connection.cursor().execute.assert_called_once()
        args = mock_databricks_connection.cursor().execute.call_args
        query_params = args[0][1]  # Second argument (parameters)
        assert query_params == ["mytest@example.com"]

    @pytest.mark.asyncio
    async def test_no_substitution_for_non_test_email(
        self, databricks_settings, test_mode_settings_enabled, mock_databricks_connection
    ):
        """Test no substitution for emails that don't match test sender email."""
        service = ContactLookupService(databricks_settings, test_mode_settings_enabled)
        service.connection = mock_databricks_connection

        # Different email should NOT be substituted
        await service.lookup_contact_by_email("other@example.com")

        # Verify the query was made with the original email
        mock_databricks_connection.cursor().execute.assert_called_once()
        args = mock_databricks_connection.cursor().execute.call_args
        query_params = args[0][1]  # Second argument (parameters)
        assert query_params == ["other@example.com"]

    @pytest.mark.asyncio
    async def test_case_insensitive_email_matching(
        self, databricks_settings, test_mode_settings_enabled, mock_databricks_connection
    ):
        """Test that email matching is case insensitive."""
        service = ContactLookupService(databricks_settings, test_mode_settings_enabled)
        service.connection = mock_databricks_connection

        # Uppercase test email should still be substituted
        result = await service.lookup_contact_by_email("MYTEST@EXAMPLE.COM")

        # Verify the query was made with the substituted email
        mock_databricks_connection.cursor().execute.assert_called_once()
        args = mock_databricks_connection.cursor().execute.call_args
        query_params = args[0][1]  # Second argument (parameters)
        assert query_params == ["real.customer@salesforce.com"]

        # Verify result contains original email (preserving case)
        assert result.email == "MYTEST@EXAMPLE.COM"

    @pytest.mark.asyncio
    async def test_contact_not_found_with_test_mode(
        self, databricks_settings, test_mode_settings_enabled, mock_databricks_connection
    ):
        """Test behavior when contact is not found even with test mode substitution."""
        # Configure cursor to return no results
        mock_databricks_connection.cursor().fetchone.return_value = None

        service = ContactLookupService(databricks_settings, test_mode_settings_enabled)
        service.connection = mock_databricks_connection

        result = await service.lookup_contact_by_email("mytest@example.com")

        # Verify result shows not found but with original email
        assert result.email == "mytest@example.com"
        assert result.found is False
        assert result.sf_account_id is None
        assert result.sf_contact_id is None


class TestEnvironmentVariableMapping:
    """Test environment variable mapping for test mode."""

    def test_environment_variables_parsed_correctly(self):
        """Test that environment variables are parsed correctly."""
        import os

        from config.settings import get_settings

        # Mock environment variables
        original_values = {}
        test_env_vars = {
            "TEST_MODE": "true",
            "TEST_EMAIL_SENDER": "test@example.com",
            "TEST_SALESFORCE_EMAIL": "real@salesforce.com",
        }

        try:
            # Set test environment variables
            for key, value in test_env_vars.items():
                original_values[key] = os.environ.get(key)
                os.environ[key] = value

            # Test that settings are parsed correctly
            settings = get_settings()
            assert settings.test_mode.enabled is True
            assert settings.test_mode.test_sender_email == "test@example.com"
            assert settings.test_mode.target_salesforce_email == "real@salesforce.com"

        finally:
            # Restore original environment variables
            for key, original_value in original_values.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value


if __name__ == "__main__":
    pytest.main([__file__])
