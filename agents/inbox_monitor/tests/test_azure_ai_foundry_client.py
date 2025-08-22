"""
Tests for Azure AI Foundry Client
=================================
Unit tests for the Azure AI Foundry client used for email intent classification.
"""
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch
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
def mock_ai_foundry_credentials():
    """Create mock AI Foundry credentials for testing."""
    class MockSecretValue:
        def get_secret_value(self):
            return 'test-client-secret'
    class MockCredentials:
        def __init__(self):
            self.api_key = 'test-api-key'
            self.endpoint = 'https://test.ai.azure.com'
            self.tenant_id = 'test-tenant-id'
            self.client_id = 'test-client-id'
            self.client_secret = MockSecretValue()
    return MockCredentials()
@pytest.fixture
def azure_ai_client(azure_ai_settings, mock_ai_foundry_credentials):
    """Create Azure AI Foundry client for testing."""
    return AzureAIFoundryClient(azure_ai_settings, mock_ai_foundry_credentials)
class TestAzureAIFoundryClient:
    """Test cases for Azure AI Foundry client."""
    
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.smoke
    def test_init(self, azure_ai_settings, mock_ai_foundry_credentials):
        """Test client initialization."""
        client = AzureAIFoundryClient(azure_ai_settings, mock_ai_foundry_credentials)
        assert client.settings == azure_ai_settings
        assert client.ai_foundry_credentials == mock_ai_foundry_credentials
        assert client.agent is None  # Should be None until initialized
        assert client.client is None
        assert client.credential is None
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.prompt
    async def test_create_intent_classification_prompt(self, azure_ai_client):
        """Test prompt creation for intent classification."""
        subject = "Test Subject"
        body = "I'm interested in learning more about your services."
        sender = "test@example.com"
        prompt = await azure_ai_client._create_classification_prompt(subject, body, sender)
        # Verify the essential components are included
        assert subject in prompt
        assert body in prompt
        assert sender in prompt
        # Check for key elements that should be in the classification prompt
        assert "analyze" in prompt.lower() or "classify" in prompt.lower()
        assert "intent" in prompt.lower()
        assert len(prompt) > 100  # Should be a substantial prompt
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_positive(self, azure_ai_client):
        """Test parsing positive intent classification response."""
        response_content = json.dumps({
            "intent": "positive", 
            "confidence": 0.95,
            "reasoning": "Customer expressed interest",
            "detected_phrases": ["interested", "learning more"],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert isinstance(result, IntentClassificationResult)
        assert result.intent == EmailIntent.POSITIVE
        assert result.confidence == 0.95
        assert result.reasoning == "Customer expressed interest"
        assert result.detected_phrases == ["interested", "learning more"]
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_negative(self, azure_ai_client):
        """Test parsing negative intent classification response."""
        response_content = json.dumps({
            "intent": "negative",
            "confidence": 0.90,
            "reasoning": "Customer wants to stop contact",
            "detected_phrases": ["not interested", "stop messaging"],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.intent == EmailIntent.NEGATIVE
        assert result.confidence == 0.90
        assert result.reasoning == "Customer wants to stop contact"
        assert result.detected_phrases == ["not interested", "stop messaging"]
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_service_inquiry(self, azure_ai_client):
        """Test parsing service inquiry intent classification response."""
        response_content = json.dumps({
            "intent": "service_inquiry",
            "confidence": 0.85,
            "reasoning": "Customer has billing question",
            "detected_phrases": ["billing question", "account issue"],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.intent == EmailIntent.SERVICE_INQUIRY
        assert result.confidence == 0.85
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_out_of_office(self, azure_ai_client):
        """Test parsing out of office intent classification response."""
        response_content = json.dumps({
            "intent": "out_of_office",
            "confidence": 0.98,
            "reasoning": "Auto-reply out of office message",
            "detected_phrases": ["out of office", "vacation"],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.intent == EmailIntent.OUT_OF_OFFICE
        assert result.confidence == 0.98
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_email_invalid(self, azure_ai_client):
        """Test parsing email invalid intent classification response."""
        response_content = json.dumps({
            "intent": "email_invalid",
            "confidence": 0.99,
            "reasoning": "Email delivery failed",
            "detected_phrases": ["delivery failed", "invalid email"],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.intent == EmailIntent.EMAIL_INVALID
        assert result.confidence == 0.99
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_no_longer_works(self, azure_ai_client):
        """Test parsing no longer works intent classification response."""
        response_content = json.dumps({
            "intent": "no_longer_works",
            "confidence": 0.92,
            "reasoning": "Person left the company",
            "detected_phrases": ["left the company", "no longer work"],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.intent == EmailIntent.NO_LONGER_WORKS
        assert result.confidence == 0.92
    @pytest.mark.fast
    @pytest.mark.integration
    def test_parse_classification_response_unknown_intent(self, azure_ai_client):
        """Test parsing unknown intent classification response."""
        response_content = json.dumps({
            "intent": "unknown_intent",
            "confidence": 0.50,
            "reasoning": "Intent unclear",
            "detected_phrases": [],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.intent == EmailIntent.UNKNOWN
        assert result.confidence == 0.50


    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
    @pytest.mark.edge_case
    def test_parse_classification_response_invalid_json(self, azure_ai_client):
        """Test parsing invalid JSON response."""
        response_content = "This is not valid JSON"
        with pytest.raises(Exception) as exc_info:
            azure_ai_client._parse_agent_response(response_content)
        assert "Failed to parse classification response" in str(exc_info.value) or "JSON" in str(exc_info.value)


    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
    def test_parse_classification_response_confidence_bounds(self, azure_ai_client):
        """Test confidence score bounds handling."""
        # Test confidence > 1.0
        response_content = json.dumps({
            "intent": "positive",
            "confidence": 1.5,
            "reasoning": "Test",
            "detected_phrases": [],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.confidence == 1.0
        # Test confidence < 0.0
        response_content = json.dumps({
            "intent": "positive",
            "confidence": -0.5,
            "reasoning": "Test",
            "detected_phrases": [],
        })
        result = azure_ai_client._parse_agent_response(response_content)
        assert result.confidence == 0.0
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.azure
    async def test_make_api_call_success(self, azure_ai_client):
        """Test successful API call."""
        # Mock the agent response instead of session
        mock_agent = AsyncMock()
        mock_response = MagicMock()
        mock_response.content.content = json.dumps(
            {
                "intent": "positive",
                "confidence": 0.95,
                "reasoning": "Test",
                "detected_phrases": [],
            }
        )
        mock_agent.get_response.return_value = mock_response
        # Initialize agent
        azure_ai_client.agent = mock_agent
        result = await azure_ai_client.classify_email("test prompt")
        assert "classification" in result
        assert json.loads(result["classification"])["intent"] == "positive"
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.azure
    async def test_make_api_call_http_error(self, azure_ai_client):
        """Test API call with HTTP error."""
        # Mock agent to raise exception
        mock_agent = AsyncMock()
        mock_agent.get_response.side_effect = Exception("API call failed with status 400")
        # Initialize agent
        azure_ai_client.agent = mock_agent
        with pytest.raises(Exception) as exc_info:
            await azure_ai_client.classify_email("test prompt")
        assert "API call failed with status 400" in str(exc_info.value)
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_make_api_call_no_session(self, azure_ai_client):
        """Test API call without agent initialization."""
        # Ensure agent is not initialized (test default state)
        azure_ai_client.agent = None
        with pytest.raises(RuntimeError) as exc_info:
            await azure_ai_client.classify_email("test prompt")
        assert "Client not properly initialized" in str(exc_info.value)
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.email
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
        # Mock the agent response instead of _make_api_call
        mock_agent = AsyncMock()
        mock_agent.get_response = AsyncMock()
        mock_agent.get_response.return_value.content.content = mock_response["content"]
        azure_ai_client.agent = mock_agent
        result = await azure_ai_client.classify_email_intent(
            subject="Interested in your services",
            body="I'd like to know more about your products.",
            sender_email="test@example.com",
        )
        assert isinstance(result, IntentClassificationResult)
        assert result.intent == EmailIntent.POSITIVE
        assert result.confidence == 0.95
        assert result.processing_duration_ms > 0
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.azure
    async def test_classify_email_intent_failure(self, azure_ai_client):
        """Test email intent classification failure."""
        # Mock the agent to raise an exception
        mock_agent = AsyncMock()
        mock_agent.get_response = AsyncMock(side_effect=Exception("API Error"))
        azure_ai_client.agent = mock_agent
        result = await azure_ai_client.classify_email_intent(
            subject="Test", body="Test body", sender_email="test@example.com"
        )
        assert result.intent == EmailIntent.UNKNOWN
        assert result.confidence == 0.0
        assert "Classification failed: API Error" in result.reasoning
        assert result.processing_duration_ms > 0
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    async def test_context_manager(self, azure_ai_client):
        """Test async context manager."""
        # Mock the _get_or_create_agent method to avoid Azure SDK calls
        mock_agent = Mock()
        mock_agent.name = "test-agent"
        async def mock_get_or_create_agent():
            return mock_agent
        with patch.object(azure_ai_client, '_get_or_create_agent', side_effect=mock_get_or_create_agent):
            async with azure_ai_client as client:
                assert client is not None
                assert client.agent is not None
                assert client.agent.name == "test-agent"
        assert azure_ai_client is not None
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.azure
    async def test_test_connection_success(self, azure_ai_client):
        """Test successful connection test."""
        mock_result = IntentClassificationResult(
            intent=EmailIntent.POSITIVE,
            confidence=0.95,
            reasoning="Test successful",
            detected_phrases=[],
            processing_duration_ms=100,
        )
        # Mock the agent to ensure proper initialization
        mock_agent = AsyncMock()
        mock_agent.name = "test-agent"
        # Mock _get_or_create_agent to avoid Azure SDK calls
        async def mock_get_or_create_agent():
            return mock_agent
        # Patch both agent creation and classification to avoid real API calls
        with patch.object(azure_ai_client, '_get_or_create_agent', side_effect=mock_get_or_create_agent):
            with patch.object(azure_ai_client, "classify_email_intent", return_value=mock_result) as mock_classify:
                result = await azure_ai_client.test_connection()
                assert result is True
                # Verify classify_email_intent was called with test data
                mock_classify.assert_called_once_with(
                    subject="Test Connection",
                    body="This is a test message to verify the connection.",
                    sender_email="test@example.com"
                )
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.azure
    async def test_test_connection_failure(self, azure_ai_client):
        """Test connection test failure."""
        mock_result = IntentClassificationResult(
            intent=EmailIntent.UNKNOWN,
            confidence=0.0,
            reasoning="Test failed",
            detected_phrases=[],
            processing_duration_ms=100,
        )
        with patch.object(azure_ai_client, "classify_email_intent", return_value=mock_result):
            result = await azure_ai_client.test_connection()
            assert result is False
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.azure
    async def test_test_connection_exception(self, azure_ai_client):
        """Test connection test with exception."""
        with patch.object(
            azure_ai_client, "classify_email_intent", side_effect=Exception("Connection error")
        ):
            result = await azure_ai_client.test_connection()
            assert result is False
class TestExternalPromptIntegration:
    """Test external prompt loading integration with Azure AI Foundry Client."""
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.prompt
    async def test_external_system_instructions_loading(self, azure_ai_settings):
        """Test that system instructions are loaded from external YAML files."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Test external prompt loading
            instructions = await client._get_agent_instructions()
            # Verify instructions content
            assert isinstance(instructions, str)
            assert len(instructions) > 1000  # Should be substantial content
            assert "INTENT CATEGORIES" in instructions
            assert "CONFIDENCE SCORING" in instructions
            assert "RESPONSE FORMAT" in instructions
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.prompt
    async def test_external_template_rendering(self, azure_ai_settings):
        """Test that classification templates are rendered from external files."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Test template rendering
            test_subject = "Meeting Request"
            test_body = "I would like to schedule a call to discuss your product."
            test_sender = "john.doe@company.com"
            prompt = await client._create_classification_prompt(
                subject=test_subject,
                body=test_body,
                sender_email=test_sender
            )
            # Verify prompt content
            assert isinstance(prompt, str)
            assert test_subject in prompt
            assert test_body in prompt
            assert test_sender in prompt
            assert "company.com" in prompt  # Domain extraction
            assert "Please analyze this email response" in prompt
            assert "EMAIL DETAILS:" in prompt
            assert "CONTEXT ANALYSIS:" in prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.prompt
    async def test_fallback_behavior_system_instructions(self, azure_ai_settings):
        """Test fallback behavior when external system instructions fail to load."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Mock prompt manager to simulate loading failure
            with patch.object(client.prompt_manager, 'get_system_instructions') as mock_get:
                mock_get.side_effect = Exception("File not found")
                # Should fall back to hardcoded instructions
                instructions = await client._get_agent_instructions()
                # Verify fallback content
                assert isinstance(instructions, str)
                assert len(instructions) > 100  # Should have fallback content
                assert "intent classification" in instructions.lower()
                # Verify attempt was made to load external
                mock_get.assert_called_once_with("email_classification")
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.prompt
    async def test_fallback_behavior_template_rendering(self, azure_ai_settings):
        """Test fallback behavior when external template rendering fails."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Mock prompt manager to simulate template loading failure
            with patch.object(client.prompt_manager, 'load_template') as mock_load:
                mock_load.side_effect = Exception("Template not found")
                # Should fall back to inline prompt generation
                prompt = await client._create_classification_prompt(
                    subject="Test",
                    body="Test message",
                    sender_email="test@example.com"
                )
                # Verify fallback content
                assert isinstance(prompt, str)
                assert "test@example.com" in prompt
                assert "Test" in prompt
                assert "Please analyze this email response" in prompt
                # Verify attempt was made to load external template
                mock_load.assert_called_once_with("email_classification", "classification_template")
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.prompt
    async def test_prompt_manager_integration(self, azure_ai_settings):
        """Test that PromptManager is properly integrated."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Verify PromptManager initialization
            assert client.prompt_manager is not None
            assert client.template_renderer is not None
            assert hasattr(client.prompt_manager, 'get_system_instructions')
            assert hasattr(client.prompt_manager, 'load_template')
            assert hasattr(client.template_renderer, 'render_template')
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.prompt
    async def test_template_variable_processing(self, azure_ai_settings):
        """Test template variable processing and substitution."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Test with various email formats and content
            test_cases = [
                {
                    "subject": "Re: Product Demo",
                    "body": "Thanks for the demo. I'm interested in learning more about pricing.",
                    "sender": "ceo@bigcorp.com",
                    "expected_domain": "bigcorp.com",
                    "expected_type": "Corporate/Legitimate"
                },
                {
                    "subject": "",  # Empty subject
                    "body": "Test",
                    "sender": "user@personal.email",  
                    "expected_domain": "personal.email",
                    "expected_type": "Non-standard"
                }
            ]
            for case in test_cases:
                prompt = await client._create_classification_prompt(
                    subject=case["subject"],
                    body=case["body"], 
                    sender_email=case["sender"]
                )
                # Verify variable substitution
                assert case["sender"] in prompt
                assert case["expected_domain"] in prompt
                assert case["expected_type"] in prompt
                # Verify subject handling (empty should become "No Subject")
                if case["subject"]:
                    assert case["subject"] in prompt
                else:
                    # Template should handle empty subject appropriately
                    assert len(prompt) > 100  # Should still generate valid prompt
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.prompt
    @pytest.mark.azure
    async def test_external_prompts_preserve_functionality(self, azure_ai_settings):
        """Test that external prompt loading preserves all original functionality."""
        with patch('services.azure_ai_foundry_client.SK_AVAILABLE', True):
            client = AzureAIFoundryClient(azure_ai_settings, {}, test_mode=True)
            # Mock the agent and classification response
            mock_agent = AsyncMock()
            mock_response = MagicMock()
            mock_response.content.content = json.dumps({
                "intent": "positive",
                "confidence": 0.92,
                "reasoning": "Customer shows interest",
                "detected_phrases": ["interested", "more information"]
            })
            mock_agent.get_response.return_value = mock_response
            with patch.object(client, '_get_or_create_agent', return_value=mock_agent):
                client.agent = mock_agent
                # Test full classification workflow
                result = await client.classify_email_intent(
                    subject="Product Inquiry",
                    body="I'm interested in learning more about your product.",
                    sender_email="customer@company.com"
                )
                # Verify result structure and content
                assert isinstance(result, IntentClassificationResult)
                assert result.intent == EmailIntent.POSITIVE
                assert result.confidence == 0.92
                assert result.reasoning == "Customer shows interest"
                assert result.detected_phrases == ["interested", "more information"]
                assert result.processing_duration_ms > 0