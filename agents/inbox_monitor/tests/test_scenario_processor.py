"""
Tests for Scenario Processor
=============================

Unit tests for the scenario processor that handles email scenarios (5-11).
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import (  # noqa: E402
    AppSettings,
    AzureAIFoundrySettings,
    DatabricksSettings,
    SalesforceSettings,
    ScenarioSettings,
)
from models.email import (
    Email,
    EmailAddress,
    EmailBody,
    EmailRecipients,
    ProcessingMetadata,
)
from services.azure_ai_foundry_client import EmailIntent, IntentClassificationResult  # noqa: E402
from services.round_robin_service import ExpertAssignment  # noqa: E402
from services.salesforce_client import CaseCreateResponse  # noqa: E402
from services.scenario_processor import (
    ScenarioProcessor,
    ScenarioResult,
    ScenarioType,
)


@pytest.fixture
def app_settings():
    """Create application settings for testing."""
    return AppSettings(
        graph_api=MagicMock(),
        processing=MagicMock(),
        logging=MagicMock(),
        output=MagicMock(),
        azure_ai_foundry=AzureAIFoundrySettings(
            endpoint="https://test.ai.azure.com",
            connection_string="https://test.ai.azure.com;test-key;test-rg;test-project",
        ),
        salesforce=SalesforceSettings(
            base_url="https://test.salesforce.com",
            client_id="test_client_id",
            client_secret="test_client_secret",
            token_endpoint="https://test.salesforce.com/services/oauth2/token",
            api_version="v64.0",
            case_record_type_id="012000000000000",
            case_queue="Expert Team",
        ),
        databricks=DatabricksSettings(
            server_hostname="test.databricks.com",
            http_path="/sql/1.0/warehouses/test",
            access_token="test_token",
            catalog="test_catalog",
            schema_name="test_schema",
            table_suffix="_test",
        ),
        scenarios=ScenarioSettings(
            test_email="test@example.com",
            victoria_grant_email="victoria.grant@company.com",
            account_team_email="accountteam@company.com",
        ),
        environment="test",
        dry_run=False,
    )


@pytest.fixture
def scenario_processor(app_settings):
    """Create scenario processor for testing."""
    return ScenarioProcessor(app_settings)


@pytest.fixture
def sample_email():
    """Create sample email for testing."""
    return Email(
        id="test_email_id",
        conversation_id="test_conversation_id",
        received_datetime=datetime.utcnow(),
        sender=EmailAddress(email="customer@example.com", name="Customer Name"),
        recipients=EmailRecipients(
            to=[EmailAddress(email="monitored@company.com", name="Monitored Email")]
        ),
        subject="Test Subject",
        body=EmailBody(content_type="text/plain", content="Test email body content"),
        body_preview="Test email body...",
        processing_metadata=ProcessingMetadata(
            inbox_monitor_version="2.0.0", processing_id="test_processing_id"
        ),
    )


@pytest.fixture
def mock_graph_client():
    """Create mock Graph API client."""
    return MagicMock()


@pytest.fixture
def mock_intent_result():
    """Create mock intent classification result."""
    return IntentClassificationResult(
        intent=EmailIntent.POSITIVE,
        confidence=0.95,
        reasoning="Customer expressed interest",
        detected_phrases=["interested", "tell me more"],
        processing_time_ms=100,
    )


class TestScenarioProcessor:
    """Test cases for scenario processor."""

    def test_init(self, app_settings):
        """Test scenario processor initialization."""
        processor = ScenarioProcessor(app_settings)
        assert processor.settings == app_settings
        assert processor.ai_foundry_client is not None
        assert processor.salesforce_client is not None
        assert processor.round_robin_service is not None

    @pytest.mark.asyncio
    async def test_process_email_scenario_success(
        self, scenario_processor, sample_email, mock_graph_client
    ):
        """Test successful email scenario processing."""
        mock_intent_result = IntentClassificationResult(
            intent=EmailIntent.POSITIVE,
            confidence=0.95,
            reasoning="Customer expressed interest",
            detected_phrases=["interested"],
            processing_time_ms=100,
        )

        mock_scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5_POSITIVE,
            success=True,
            actions_taken=["expert_assigned", "case_created"],
            processing_time_ms=200,
        )

        with patch.object(
            scenario_processor.ai_foundry_client,
            "__aenter__",
            return_value=scenario_processor.ai_foundry_client,
        ), patch.object(scenario_processor.ai_foundry_client, "__aexit__", return_value=None):
            with patch.object(
                scenario_processor.ai_foundry_client,
                "classify_email_intent",
                return_value=mock_intent_result,
            ):
                with patch.object(
                    scenario_processor,
                    "_route_to_scenario_handler",
                    return_value=mock_scenario_result,
                ):
                    result = await scenario_processor.process_email_scenario(sample_email)

                    assert result.success is True
                    assert result.scenario_type == ScenarioType.SCENARIO_5_POSITIVE
                    assert result.processing_time_ms > 0
                    assert result.metadata["intent"] == "positive"
                    assert result.metadata["intent_confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_process_email_scenario_failure(
        self, scenario_processor, sample_email, mock_graph_client
    ):
        """Test email scenario processing failure."""
        with patch.object(
            scenario_processor.ai_foundry_client,
            "__aenter__",
            return_value=scenario_processor.ai_foundry_client,
        ), patch.object(scenario_processor.ai_foundry_client, "__aexit__", return_value=None):
            with patch.object(
                scenario_processor.ai_foundry_client,
                "classify_email_intent",
                side_effect=Exception("AI Error"),
            ):
                result = await scenario_processor.process_email_scenario(sample_email)

                assert result.success is False
                assert result.error_message == "AI Error"
                assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_route_to_scenario_handler_positive(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test routing to positive scenario handler."""
        mock_intent_result.intent = EmailIntent.POSITIVE

        with patch.object(scenario_processor, "_handle_scenario_5_positive") as mock_handler:
            mock_handler.return_value = ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_5_POSITIVE,
                success=True,
                actions_taken=[],
                processing_time_ms=100,
            )

            result = await scenario_processor._route_to_scenario_handler(
                sample_email, mock_intent_result, mock_graph_client
            )

            mock_handler.assert_called_once_with(
                sample_email, mock_intent_result, mock_graph_client
            )
            assert result.scenario_type == ScenarioType.SCENARIO_5_POSITIVE

    @pytest.mark.asyncio
    async def test_route_to_scenario_handler_negative(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test routing to negative scenario handler."""
        mock_intent_result.intent = EmailIntent.NEGATIVE

        with patch.object(scenario_processor, "_handle_scenario_6_negative") as mock_handler:
            mock_handler.return_value = ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_6_NEGATIVE,
                success=True,
                actions_taken=[],
                processing_time_ms=100,
            )

            result = await scenario_processor._route_to_scenario_handler(
                sample_email, mock_intent_result, mock_graph_client
            )

            mock_handler.assert_called_once_with(
                sample_email, mock_intent_result, mock_graph_client
            )
            assert result.scenario_type == ScenarioType.SCENARIO_6_NEGATIVE

    @pytest.mark.asyncio
    async def test_handle_scenario_5_positive_success(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test successful handling of scenario 5 (positive response)."""
        mock_contact_info = {
            "sf_account_id": "001000000000000",
            "sf_contact_id": "003000000000000",
            "customer_name": "Test Customer",
        }

        mock_assignment = ExpertAssignment(
            assignment_id="assignment_1",
            expert_id="expert_1",
            expert_email="expert1@company.com",
            expert_name="Expert One",
            customer_email="customer@example.com",
            lead_status="assigned",
            assignment_date=datetime.utcnow(),
            last_assignment_timestamp=datetime.utcnow(),
            assignment_count=1,
        )

        mock_case_response = CaseCreateResponse(id="case_123", success=True, errors=[])

        with patch.object(
            scenario_processor, "_get_contact_info_from_databricks", return_value=mock_contact_info
        ), patch.object(
            scenario_processor.round_robin_service,
            "__aenter__",
            return_value=scenario_processor.round_robin_service,
        ), patch.object(
            scenario_processor.round_robin_service, "__aexit__", return_value=None
        ), patch.object(
            scenario_processor.round_robin_service,
            "create_assignment_table",
            return_value=True,
        ), patch.object(
            scenario_processor.round_robin_service,
            "assign_lead_to_expert",
            return_value=mock_assignment,
        ), patch.object(
            scenario_processor.salesforce_client,
            "__aenter__",
            return_value=scenario_processor.salesforce_client,
        ), patch.object(
            scenario_processor.salesforce_client,
            "__aexit__",
            return_value=None,
        ), patch.object(
            scenario_processor.salesforce_client,
            "create_case",
            return_value=mock_case_response,
        ):
            result = await scenario_processor._handle_scenario_5_positive(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is True
            assert result.scenario_type == ScenarioType.SCENARIO_5_POSITIVE
            assert result.expert_assigned == "expert1@company.com"
            assert result.case_created == "case_123"
            assert "contact_info_retrieved" in result.actions_taken
            assert "expert_assigned" in result.actions_taken
            assert "salesforce_case_created" in result.actions_taken

    @pytest.mark.asyncio
    async def test_handle_scenario_5_positive_no_contact_info(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test scenario 5 handling when contact info not found."""
        with patch.object(
            scenario_processor, "_get_contact_info_from_databricks", return_value=None
        ):
            result = await scenario_processor._handle_scenario_5_positive(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is False
            assert result.scenario_type == ScenarioType.SCENARIO_5_POSITIVE
            assert "contact_lookup_failed" in result.actions_taken
            assert "Could not find contact information" in result.error_message

    @pytest.mark.asyncio
    async def test_handle_scenario_6_negative_success(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test successful handling of scenario 6 (negative response)."""
        with patch.object(scenario_processor, "_forward_email_to_recipient", return_value=True):
            result = await scenario_processor._handle_scenario_6_negative(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is True
            assert result.scenario_type == ScenarioType.SCENARIO_6_NEGATIVE
            assert "email_forwarded_to_victoria_grant" in result.actions_taken
            assert scenario_processor.settings.scenarios.victoria_grant_email in result.emails_sent

    @pytest.mark.asyncio
    async def test_handle_scenario_6_negative_forward_failure(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test scenario 6 handling when email forwarding fails."""
        with patch.object(scenario_processor, "_forward_email_to_recipient", return_value=False):
            result = await scenario_processor._handle_scenario_6_negative(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is False
            assert result.scenario_type == ScenarioType.SCENARIO_6_NEGATIVE
            assert "email_forward_failed" in result.actions_taken
            assert "Failed to forward email to Victoria Grant" in result.error_message

    @pytest.mark.asyncio
    async def test_handle_scenario_7_service_inquiry_success(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test successful handling of scenario 7 (service inquiry)."""
        with patch.object(scenario_processor, "_forward_email_to_recipient", return_value=True):
            result = await scenario_processor._handle_scenario_7_service_inquiry(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is True
            assert result.scenario_type == ScenarioType.SCENARIO_7_SERVICE_INQUIRY
            assert "email_forwarded_to_account_team" in result.actions_taken
            assert scenario_processor.settings.scenarios.account_team_email in result.emails_sent

    @pytest.mark.asyncio
    async def test_handle_scenario_8_out_of_office_success(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test successful handling of scenario 8 (out of office)."""
        with patch.object(scenario_processor, "_update_databricks_email_status", return_value=True):
            result = await scenario_processor._handle_scenario_8_out_of_office(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is True
            assert result.scenario_type == ScenarioType.SCENARIO_8_OUT_OF_OFFICE
            assert "databricks_updated_out_of_office" in result.actions_taken
            assert result.metadata["status_updated"] == "out_of_office"

    @pytest.mark.asyncio
    async def test_handle_scenario_9_email_invalid_success(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test successful handling of scenario 9 (email invalid)."""
        mock_contact_info = {"sf_contact_id": "003000000000000", "customer_name": "Test Customer"}

        with patch.object(
            scenario_processor, "_get_contact_info_from_databricks", return_value=mock_contact_info
        ), patch.object(
            scenario_processor.salesforce_client,
            "__aenter__",
            return_value=scenario_processor.salesforce_client,
        ), patch.object(
            scenario_processor.salesforce_client, "__aexit__", return_value=None
        ), patch.object(
            scenario_processor.salesforce_client,
            "update_contact_invalid_email",
            return_value=True,
        ), patch.object(
            scenario_processor, "_update_databricks_email_status", return_value=True
        ):
            result = await scenario_processor._handle_scenario_9_email_invalid(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is True
            assert result.scenario_type == ScenarioType.SCENARIO_9_EMAIL_INVALID
            assert "contact_info_retrieved" in result.actions_taken
            assert "salesforce_contact_updated" in result.actions_taken
            assert "databricks_updated_invalid_email" in result.actions_taken

    @pytest.mark.asyncio
    async def test_handle_scenario_10_no_longer_works_success(
        self, scenario_processor, sample_email, mock_graph_client, mock_intent_result
    ):
        """Test successful handling of scenario 10 (no longer works)."""
        with patch.object(scenario_processor, "_forward_email_to_recipient", return_value=True):
            result = await scenario_processor._handle_scenario_10_no_longer_works(
                sample_email, mock_intent_result, mock_graph_client
            )

            assert result.success is True
            assert result.scenario_type == ScenarioType.SCENARIO_10_NO_LONGER_WORKS
            assert "email_forwarded_to_victoria_grant" in result.actions_taken
            assert scenario_processor.settings.scenarios.victoria_grant_email in result.emails_sent

    @pytest.mark.asyncio
    async def test_forward_email_to_recipient_success(
        self, scenario_processor, sample_email, mock_graph_client
    ):
        """Test successful email forwarding."""

        mock_graph_client.send_email = AsyncMock(return_value=(True, "message_id", None))

        with patch(
            "services.scenario_processor.retry_operation", return_value=(True, "message_id", None)
        ):
            result = await scenario_processor._forward_email_to_recipient(
                sample_email, "recipient@example.com", "Recipient Name", "[TEST]", mock_graph_client
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_forward_email_to_recipient_failure(
        self, scenario_processor, sample_email, mock_graph_client
    ):
        """Test email forwarding failure."""
        with patch(
            "services.scenario_processor.retry_operation", return_value=(False, None, "Send failed")
        ):
            result = await scenario_processor._forward_email_to_recipient(
                sample_email, "recipient@example.com", "Recipient Name", "[TEST]", mock_graph_client
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_get_contact_info_from_databricks_success(self, scenario_processor):
        """Test successful contact info retrieval from Databricks."""
        mock_contact_info = {
            "customer_id": "customer_123",
            "customer_name": "Test Customer",
            "recipient_email": "customer@example.com",
            "sf_contact_id": "003000000000000",
            "sf_account_id": "dummy_account_id",
        }

        with patch.object(
            scenario_processor.round_robin_service,
            "__aenter__",
            return_value=scenario_processor.round_robin_service,
        ):
            with patch.object(
                scenario_processor.round_robin_service, "__aexit__", return_value=None
            ):
                mock_cursor = MagicMock()
                mock_cursor.description = [
                    ("customer_id",),
                    ("customer_name",),
                    ("recipient_email",),
                    ("sf_contact_id",),
                    ("sf_account_id",),
                ]
                mock_cursor.fetchone.return_value = (
                    "customer_123",
                    "Test Customer",
                    "customer@example.com",
                    "003000000000000",
                    "dummy_account_id",
                )

                scenario_processor.round_robin_service.connection = MagicMock()
                scenario_processor.round_robin_service.connection.cursor.return_value.__enter__.return_value = (
                    mock_cursor
                )

                result = await scenario_processor._get_contact_info_from_databricks(
                    "customer@example.com"
                )

                assert result == mock_contact_info

    @pytest.mark.asyncio
    async def test_get_contact_info_from_databricks_not_found(self, scenario_processor):
        """Test contact info retrieval when contact not found."""
        with patch.object(
            scenario_processor.round_robin_service,
            "__aenter__",
            return_value=scenario_processor.round_robin_service,
        ):
            with patch.object(
                scenario_processor.round_robin_service, "__aexit__", return_value=None
            ):
                mock_cursor = MagicMock()
                mock_cursor.fetchone.return_value = None

                scenario_processor.round_robin_service.connection = MagicMock()
                scenario_processor.round_robin_service.connection.cursor.return_value.__enter__.return_value = (
                    mock_cursor
                )

                result = await scenario_processor._get_contact_info_from_databricks(
                    "customer@example.com"
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_update_databricks_email_status_success(self, scenario_processor):
        """Test successful Databricks email status update."""
        with patch.object(
            scenario_processor.round_robin_service,
            "__aenter__",
            return_value=scenario_processor.round_robin_service,
        ):
            with patch.object(
                scenario_processor.round_robin_service, "__aexit__", return_value=None
            ):
                mock_cursor = MagicMock()
                mock_cursor.rowcount = 1

                scenario_processor.round_robin_service.connection = MagicMock()
                scenario_processor.round_robin_service.connection.cursor.return_value.__enter__.return_value = (
                    mock_cursor
                )

                result = await scenario_processor._update_databricks_email_status(
                    "customer@example.com", "out_of_office", "Out of office detected"
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_update_databricks_email_status_no_rows_updated(self, scenario_processor):
        """Test Databricks email status update when no rows updated."""
        with patch.object(
            scenario_processor.round_robin_service,
            "__aenter__",
            return_value=scenario_processor.round_robin_service,
        ):
            with patch.object(
                scenario_processor.round_robin_service, "__aexit__", return_value=None
            ):
                mock_cursor = MagicMock()
                mock_cursor.rowcount = 0

                scenario_processor.round_robin_service.connection = MagicMock()
                scenario_processor.round_robin_service.connection.cursor.return_value.__enter__.return_value = (
                    mock_cursor
                )

                result = await scenario_processor._update_databricks_email_status(
                    "customer@example.com", "out_of_office", "Out of office detected"
                )

                assert result is False

    def test_scenario_result_model(self):
        """Test scenario result model."""
        result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5_POSITIVE,
            success=True,
            actions_taken=["action1", "action2"],
            expert_assigned="expert@company.com",
            case_created="case_123",
            emails_sent=["recipient@example.com"],
            processing_time_ms=500,
            metadata={"key": "value"},
        )

        assert result.scenario_type == ScenarioType.SCENARIO_5_POSITIVE
        assert result.success is True
        assert result.actions_taken == ["action1", "action2"]
        assert result.expert_assigned == "expert@company.com"
        assert result.case_created == "case_123"
        assert result.emails_sent == ["recipient@example.com"]
        assert result.processing_time_ms == 500
        assert result.metadata == {"key": "value"}

    def test_scenario_result_model_defaults(self):
        """Test scenario result model with default values."""
        result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5_POSITIVE, success=True, processing_time_ms=500
        )

        assert result.actions_taken == []
        assert result.expert_assigned is None
        assert result.case_created is None
        assert result.emails_sent == []
        assert result.error_message is None
        assert result.metadata == {}
