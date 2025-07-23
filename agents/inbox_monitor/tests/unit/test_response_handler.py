"""
Unit Tests for Response Handler Service
======================================

Comprehensive tests for the simplified response handler.
Tests cover customer response processing, logging, and error handling.

This test suite follows enterprise Python standards with:
- Complete test coverage for all methods
- Mock dependencies for isolated testing
- Comprehensive error scenario testing
- Type annotations and documentation
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

# Import the module under test
try:
    from agents.inbox_monitor.config.settings import AppSettings
    from agents.inbox_monitor.services.response_handler import (
        CustomerLookupError,
        ResponseHandler,
        ResponseHandlerError,
    )
    from agents.inbox_monitor.services.scenario_processor import ScenarioProcessor
except ImportError:
    # Fallback for different import structures
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from config.settings import AppSettings
    from services.response_handler import CustomerLookupError, ResponseHandler, ResponseHandlerError
    from services.scenario_processor import ScenarioProcessor


class TestResponseHandler:
    """Test suite for ResponseHandler class."""

    @pytest.fixture
    def mock_settings(self) -> AppSettings:
        """Create mock AppSettings for testing."""
        settings = Mock(spec=AppSettings)
        settings.debug = False
        return settings

    @pytest.fixture
    def mock_scenario_processor(self) -> ScenarioProcessor:
        """Create mock ScenarioProcessor for testing."""
        processor = Mock(spec=ScenarioProcessor)
        processor.process_scenario = AsyncMock()
        return processor

    @pytest.fixture
    def response_handler(
        self, mock_settings: AppSettings, mock_scenario_processor: ScenarioProcessor
    ) -> ResponseHandler:
        """Create ResponseHandler instance for testing."""
        return ResponseHandler(
            settings=mock_settings,
            scenario_processor=mock_scenario_processor,
            scheduling_api_base="http://test-scheduling:8000",
        )

    @pytest.fixture
    def sample_email_message(self) -> dict[str, Any]:
        """Sample email message for testing."""
        return {
            "id": "test-email-123",
            "from": {"emailAddress": {"address": "customer@test.com", "name": "Test Customer"}},
            "conversationId": "conv-123",
            "receivedDateTime": "2025-01-15T10:30:00Z",
            "subject": "Re: Your email",
            "body": {"content": "Thank you for your email."},
        }

    def test_init_valid_parameters(
        self, mock_settings: AppSettings, mock_scenario_processor: ScenarioProcessor
    ):
        """Test ResponseHandler initialization with valid parameters."""
        handler = ResponseHandler(
            settings=mock_settings,
            scenario_processor=mock_scenario_processor,
            scheduling_api_base="http://test:8000",
        )

        assert handler.settings == mock_settings
        assert handler.scenario_processor == mock_scenario_processor
        assert handler.scheduling_api_base == "http://test:8000"
        assert handler._http_timeout is not None

    def test_init_invalid_parameters(self):
        """Test ResponseHandler initialization with invalid parameters."""
        with pytest.raises(ValueError, match="AppSettings instance is required"):
            ResponseHandler(
                settings=None, scenario_processor=Mock(), scheduling_api_base="http://test:8000"
            )

        with pytest.raises(ValueError, match="ScenarioProcessor instance is required"):
            ResponseHandler(
                settings=Mock(), scenario_processor=None, scheduling_api_base="http://test:8000"
            )

    @pytest.mark.asyncio
    async def test_process_customer_response_success(
        self, response_handler: ResponseHandler, sample_email_message: dict[str, Any]
    ):
        """Test successful customer response processing."""
        scenario = 7

        # Mock dependencies
        with patch.object(
            response_handler, "_find_customer_by_email"
        ) as mock_find_customer, patch.object(
            response_handler, "_cancel_scheduled_emails"
        ) as mock_cancel, patch.object(
            response_handler, "_track_response"
        ) as mock_track:
            # Setup mocks
            mock_find_customer.return_value = {
                "customer_id": "CUST_123",
                "salesforce_account_id": "SF_123",
            }
            mock_cancel.return_value = 3
            mock_track.return_value = None

            # Execute
            await response_handler.process_customer_response(
                email_message=sample_email_message, scenario=scenario
            )

            # Verify calls
            mock_find_customer.assert_called_once_with("customer@test.com")
            mock_cancel.assert_called_once_with(
                customer_id="CUST_123", reason="customer_response_scenario_7"
            )
            mock_track.assert_called_once_with(
                customer_id="CUST_123",
                sender_email="customer@test.com",
                conversation_id="conv-123",
                scenario=7,
                received_time="2025-01-15T10:30:00Z",
            )
            response_handler.scenario_processor.process_scenario.assert_called_once_with(
                sample_email_message, scenario
            )

    @pytest.mark.asyncio
    async def test_process_customer_response_invalid_parameters(
        self, response_handler: ResponseHandler
    ):
        """Test customer response processing with invalid parameters."""
        # Test empty email message
        with pytest.raises(ValueError, match="email_message cannot be empty"):
            await response_handler.process_customer_response(email_message=None, scenario=7)

        # Test invalid scenario
        with pytest.raises(ValueError, match="scenario must be an integer between 5 and 11"):
            await response_handler.process_customer_response(
                email_message={"from": {"emailAddress": {"address": "test@test.com"}}}, scenario=4
            )

    @pytest.mark.asyncio
    async def test_process_customer_response_no_sender_email(
        self, response_handler: ResponseHandler
    ):
        """Test customer response processing with missing sender email."""
        email_message = {"id": "test-123"}  # No sender email

        with pytest.raises(ValueError, match="No sender email found in response"):
            await response_handler.process_customer_response(
                email_message=email_message, scenario=7
            )

    @pytest.mark.asyncio
    async def test_process_customer_response_customer_not_found(
        self, response_handler: ResponseHandler, sample_email_message: dict[str, Any]
    ):
        """Test customer response processing when customer is not found."""
        with patch.object(response_handler, "_find_customer_by_email") as mock_find_customer:
            mock_find_customer.return_value = None

            with pytest.raises(CustomerLookupError, match="No customer found for email"):
                await response_handler.process_customer_response(
                    email_message=sample_email_message, scenario=7
                )

    @pytest.mark.asyncio
    async def test_find_customer_by_email_success(self, response_handler: ResponseHandler):
        """Test successful customer lookup by email."""
        # Since the actual implementation uses a placeholder,
        # we test the method returns the expected format
        result = await response_handler._find_customer_by_email("test@example.com")

        assert result is not None
        assert "customer_id" in result
        assert result["customer_id"].startswith("CUST_")

    @pytest.mark.asyncio
    async def test_find_customer_by_email_invalid_email(self, response_handler: ResponseHandler):
        """Test customer lookup with invalid email."""
        with pytest.raises(ValueError, match="Email must be a non-empty string"):
            await response_handler._find_customer_by_email("")

        with pytest.raises(ValueError, match="Invalid email format"):
            await response_handler._find_customer_by_email("invalid-email")

    @pytest.mark.asyncio
    async def test_cancel_scheduled_emails_api_success(self, response_handler: ResponseHandler):
        """Test successful email cancellation via API."""
        customer_id = "CUST_123"
        reason = "test_cancellation"

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cancelled_count": 5}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock(
                return_value=mock_response
            )

            result = await response_handler._cancel_scheduled_emails(
                customer_id=customer_id, reason=reason
            )

            assert result == 5

    @pytest.mark.asyncio
    async def test_cancel_scheduled_emails_api_not_found(self, response_handler: ResponseHandler):
        """Test email cancellation when no emails found."""
        customer_id = "CUST_123"
        reason = "test_cancellation"

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock(
                return_value=mock_response
            )

            result = await response_handler._cancel_scheduled_emails(
                customer_id=customer_id, reason=reason
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_cancel_scheduled_emails_api_error(self, response_handler: ResponseHandler):
        """Test email cancellation API error handling."""
        customer_id = "CUST_123"
        reason = "test_cancellation"

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal server error"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(SchedulingAPIError, match="API call failed with status 500"):
                await response_handler._cancel_scheduled_emails(
                    customer_id=customer_id, reason=reason
                )

    @pytest.mark.asyncio
    async def test_cancel_scheduled_emails_timeout(self, response_handler: ResponseHandler):
        """Test email cancellation timeout handling."""
        customer_id = "CUST_123"
        reason = "test_cancellation"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            with pytest.raises(SchedulingAPIError, match="Timeout calling scheduling API"):
                await response_handler._cancel_scheduled_emails(
                    customer_id=customer_id, reason=reason
                )

    @pytest.mark.asyncio
    async def test_cancel_scheduled_emails_invalid_parameters(
        self, response_handler: ResponseHandler
    ):
        """Test email cancellation with invalid parameters."""
        with pytest.raises(ValueError, match="customer_id cannot be empty"):
            await response_handler._cancel_scheduled_emails(customer_id="", reason="test")

        with pytest.raises(ValueError, match="reason cannot be empty"):
            await response_handler._cancel_scheduled_emails(customer_id="CUST_123", reason="")

    @pytest.mark.asyncio
    async def test_track_response_success(self, response_handler: ResponseHandler):
        """Test successful response tracking."""
        # This should not raise any exceptions
        await response_handler._track_response(
            customer_id="CUST_123",
            sender_email="test@example.com",
            conversation_id="conv-123",
            scenario=7,
            received_time="2025-01-15T10:30:00Z",
        )

    @pytest.mark.asyncio
    async def test_track_response_invalid_parameters(self, response_handler: ResponseHandler):
        """Test response tracking with invalid parameters."""
        with pytest.raises(ValueError, match="customer_id cannot be empty"):
            await response_handler._track_response(
                customer_id="",
                sender_email="test@example.com",
                conversation_id="conv-123",
                scenario=7,
                received_time="2025-01-15T10:30:00Z",
            )

        with pytest.raises(ValueError, match="scenario must be an integer"):
            await response_handler._track_response(
                customer_id="CUST_123",
                sender_email="test@example.com",
                conversation_id="conv-123",
                scenario="invalid",
                received_time="2025-01-15T10:30:00Z",
            )

    @pytest.mark.asyncio
    async def test_get_cancellation_stats_success(self, response_handler: ResponseHandler):
        """Test successful cancellation stats retrieval."""
        customer_id = "CUST_123"

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "customer_id": customer_id,
            "schedules": [{"schedule_id": "SCH_123", "status": "cancelled"}],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await response_handler.get_cancellation_stats(customer_id)

            assert result["customer_id"] == customer_id
            assert "schedules" in result

    @pytest.mark.asyncio
    async def test_get_cancellation_stats_not_found(self, response_handler: ResponseHandler):
        """Test cancellation stats retrieval when customer not found."""
        customer_id = "CUST_123"

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await response_handler.get_cancellation_stats(customer_id)

            assert result["customer_id"] == customer_id
            assert result["schedules"] == []


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_scheduling_api_error(self):
        """Test SchedulingAPIError exception."""
        error = SchedulingAPIError("Test error", 500)
        assert str(error) == "Test error"
        assert error.status_code == 500

        error_no_code = SchedulingAPIError("Test error")
        assert str(error_no_code) == "Test error"
        assert error_no_code.status_code is None

    def test_customer_lookup_error(self):
        """Test CustomerLookupError exception."""
        error = CustomerLookupError("Customer not found")
        assert str(error) == "Customer not found"


# Integration test helpers
@pytest.mark.integration
class TestResponseHandlerIntegration:
    """Integration tests for ResponseHandler (requires actual dependencies)."""

    @pytest.mark.asyncio
    async def test_end_to_end_response_processing(self):
        """Test end-to-end response processing with real dependencies."""
        # This would be implemented when actual database integration is available
        pytest.skip("Integration test requires actual dependencies")

    @pytest.mark.asyncio
    async def test_scheduling_api_integration(self):
        """Test actual integration with scheduling API."""
        # This would be implemented when scheduling API is deployed
        pytest.skip("Integration test requires running scheduling API")
