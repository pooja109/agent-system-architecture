"""
Tests for Azure AI Foundry Client
=================================

Unit tests for the Azure AI Foundry client used for email intent classification.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import AzureAIFoundrySettings  # noqa: E402
from services.azure_ai_foundry_client import (  # noqa: E402
    AzureAIFoundryClient,
    EmailIntent,
    IntentClassificationResult,
)


@pytest.fixture
def azure_ai_settings():
    """Create Azure AI Foundry settings for testing."""
    return AzureAIFoundrySettings(
        endpoint="https://test.ai.azure.com",
        connection_string="https://test.ai.azure.com;test-key;test-rg;test-project",
    )


@pytest.fixture
def azure_ai_client(azure_ai_settings):
    """Create Azure AI Foundry client for testing."""
    return AzureAIFoundryClient(azure_ai_settings)


class TestAzureAIFoundryClient:
    """Test cases for Azure AI Foundry client."""

    def test_init(self, azure_ai_settings):
        """Test client initialization."""
        client = AzureAIFoundryClient(azure_ai_settings)
        assert client.settings == azure_ai_settings
        assert client.session is None

    def test_create_intent_classification_prompt(self, azure_ai_client):
        """Test prompt creation for intent classification."""
        subject = "Test Subject"
        body = "I'm interested in learning more about your services."
        sender = "test@example.com"

        prompt = azure_ai_client._create_intent_classification_prompt(subject, body, sender)

        assert subject in prompt
        assert body in prompt
        assert sender in prompt
        assert "POSITIVE" in prompt
        assert "NEGATIVE" in prompt
        assert "SERVICE_INQUIRY" in prompt
        assert "OUT_OF_OFFICE" in prompt
        assert "EMAIL_INVALID" in prompt
        assert "NO_LONGER_WORKS" in prompt

    def test_parse_classification_response_positive(self, azure_ai_client):
        """Test parsing positive intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "positive",
                    "confidence": 0.95,
                    "reasoning": "Customer expressed interest",
                    "detected_phrases": ["interested", "learning more"],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert isinstance(result, IntentClassificationResult)
        assert result.intent == EmailIntent.POSITIVE
        assert result.confidence == 0.95
        assert result.reasoning == "Customer expressed interest"
        assert result.detected_phrases == ["interested", "learning more"]

    def test_parse_classification_response_negative(self, azure_ai_client):
        """Test parsing negative intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "negative",
                    "confidence": 0.90,
                    "reasoning": "Customer wants to stop contact",
                    "detected_phrases": ["not interested", "stop messaging"],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert result.intent == EmailIntent.NEGATIVE
        assert result.confidence == 0.90
        assert result.reasoning == "Customer wants to stop contact"
        assert result.detected_phrases == ["not interested", "stop messaging"]

    def test_parse_classification_response_service_inquiry(self, azure_ai_client):
        """Test parsing service inquiry intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "service_inquiry",
                    "confidence": 0.85,
                    "reasoning": "Customer has billing question",
                    "detected_phrases": ["billing question", "account issue"],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert result.intent == EmailIntent.SERVICE_INQUIRY
        assert result.confidence == 0.85

    def test_parse_classification_response_out_of_office(self, azure_ai_client):
        """Test parsing out of office intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "out_of_office",
                    "confidence": 0.98,
                    "reasoning": "Auto-reply out of office message",
                    "detected_phrases": ["out of office", "vacation"],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert result.intent == EmailIntent.OUT_OF_OFFICE
        assert result.confidence == 0.98

    def test_parse_classification_response_email_invalid(self, azure_ai_client):
        """Test parsing email invalid intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "email_invalid",
                    "confidence": 0.99,
                    "reasoning": "Email delivery failed",
                    "detected_phrases": ["delivery failed", "invalid email"],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert result.intent == EmailIntent.EMAIL_INVALID
        assert result.confidence == 0.99

    def test_parse_classification_response_no_longer_works(self, azure_ai_client):
        """Test parsing no longer works intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "no_longer_works",
                    "confidence": 0.92,
                    "reasoning": "Person left the company",
                    "detected_phrases": ["left the company", "no longer work"],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert result.intent == EmailIntent.NO_LONGER_WORKS
        assert result.confidence == 0.92

    def test_parse_classification_response_unknown_intent(self, azure_ai_client):
        """Test parsing unknown intent classification response."""
        response = {
            "content": json.dumps(
                {
                    "intent": "unknown_intent",
                    "confidence": 0.50,
                    "reasoning": "Intent unclear",
                    "detected_phrases": [],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)

        assert result.intent == EmailIntent.UNKNOWN
        assert result.confidence == 0.50

    def test_parse_classification_response_invalid_json(self, azure_ai_client):
        """Test parsing invalid JSON response."""
        response = {"content": "This is not valid JSON"}

        with pytest.raises(Exception) as exc_info:
            azure_ai_client._parse_classification_response(response)

        assert "Failed to parse classification response" in str(exc_info.value)

    def test_parse_classification_response_confidence_bounds(self, azure_ai_client):
        """Test confidence score bounds handling."""
        # Test confidence > 1.0
        response = {
            "content": json.dumps(
                {
                    "intent": "positive",
                    "confidence": 1.5,
                    "reasoning": "Test",
                    "detected_phrases": [],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)
        assert result.confidence == 1.0

        # Test confidence < 0.0
        response = {
            "content": json.dumps(
                {
                    "intent": "positive",
                    "confidence": -0.5,
                    "reasoning": "Test",
                    "detected_phrases": [],
                }
            )
        }

        result = azure_ai_client._parse_classification_response(response)
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_make_api_call_success(self, azure_ai_client):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "positive",
                                    "confidence": 0.95,
                                    "reasoning": "Test",
                                    "detected_phrases": [],
                                }
                            )
                        }
                    }
                ]
            }
        )

        mock_session = MagicMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        azure_ai_client.session = mock_session

        result = await azure_ai_client._make_api_call("test prompt")

        assert "content" in result
        assert json.loads(result["content"])["intent"] == "positive"

    @pytest.mark.asyncio
    async def test_make_api_call_http_error(self, azure_ai_client):
        """Test API call with HTTP error."""
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")

        mock_session = MagicMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        azure_ai_client.session = mock_session

        with pytest.raises(Exception) as exc_info:
            await azure_ai_client._make_api_call("test prompt")

        assert "API call failed with status 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_api_call_no_session(self, azure_ai_client):
        """Test API call without session."""
        with pytest.raises(RuntimeError) as exc_info:
            await azure_ai_client._make_api_call("test prompt")

        assert "Client session not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_email_intent_success(self, azure_ai_client):
        """Test successful email intent classification."""
        mock_response = {
            "content": json.dumps(
                {
                    "intent": "positive",
                    "confidence": 0.95,
                    "reasoning": "Customer expressed interest",
                    "detected_phrases": ["interested", "tell me more"],
                }
            )
        }

        with patch.object(azure_ai_client, "_make_api_call", return_value=mock_response):
            azure_ai_client.session = MagicMock()

            result = await azure_ai_client.classify_email_intent(
                subject="Interested in your services",
                body="I'd like to know more about your products.",
                sender_email="test@example.com",
            )

            assert isinstance(result, IntentClassificationResult)
            assert result.intent == EmailIntent.POSITIVE
            assert result.confidence == 0.95
            assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_classify_email_intent_failure(self, azure_ai_client):
        """Test email intent classification failure."""
        with patch.object(azure_ai_client, "_make_api_call", side_effect=Exception("API Error")):
            azure_ai_client.session = MagicMock()

            result = await azure_ai_client.classify_email_intent(
                subject="Test", body="Test body", sender_email="test@example.com"
            )

            assert result.intent == EmailIntent.UNKNOWN
            assert result.confidence == 0.0
            assert "Classification failed: API Error" in result.reasoning
            assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_context_manager(self, azure_ai_client):
        """Test async context manager."""
        async with azure_ai_client as client:
            assert client is not None

        assert azure_ai_client is not None

    @pytest.mark.asyncio
    async def test_test_connection_success(self, azure_ai_client):
        """Test successful connection test."""
        mock_result = IntentClassificationResult(
            intent=EmailIntent.POSITIVE,
            confidence=0.95,
            reasoning="Test successful",
            detected_phrases=[],
            processing_time_ms=100,
        )

        with patch.object(azure_ai_client, "classify_email_intent", return_value=mock_result):
            result = await azure_ai_client.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, azure_ai_client):
        """Test connection test failure."""
        mock_result = IntentClassificationResult(
            intent=EmailIntent.UNKNOWN,
            confidence=0.0,
            reasoning="Test failed",
            detected_phrases=[],
            processing_time_ms=100,
        )

        with patch.object(azure_ai_client, "classify_email_intent", return_value=mock_result):
            result = await azure_ai_client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_exception(self, azure_ai_client):
        """Test connection test with exception."""
        with patch.object(
            azure_ai_client, "classify_email_intent", side_effect=Exception("Connection error")
        ):
            result = await azure_ai_client.test_connection()
            assert result is False
