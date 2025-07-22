"""
Azure AI Foundry Client
=======================

Client for interacting with Azure AI Foundry Agent Services using Semantic Kernel
to classify email intent and determine appropriate response scenarios.
"""

import asyncio
import json
import os
from datetime import datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field

try:
    from config.settings import AzureAIFoundrySettings
except ImportError:
    from ..config.settings import AzureAIFoundrySettings

try:
    from azure.identity.aio import DefaultAzureCredential
    from semantic_kernel.agents import AzureAIAgent

    SK_AVAILABLE = True
except ImportError:
    SK_AVAILABLE = False
    structlog.get_logger(__name__).warning(
        "Semantic Kernel not available. Install with: pip install semantic-kernel[azure]"
    )


class EmailIntent(str, Enum):
    """Email intent classification."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    SERVICE_INQUIRY = "service_inquiry"
    OUT_OF_OFFICE = "out_of_office"
    EMAIL_INVALID = "email_invalid"
    NO_LONGER_WORKS = "no_longer_works"
    UNKNOWN = "unknown"


class IntentClassificationResult(BaseModel):
    """Result of email intent classification."""

    intent: EmailIntent = Field(..., description="Classified intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(..., description="Reasoning for the classification")
    detected_phrases: list[str] = Field(
        default_factory=list, description="Key phrases that influenced the decision"
    )
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class AzureAIFoundryClient:
    """Client for Azure AI Foundry Agent Services using Semantic Kernel."""

    def __init__(self, settings: AzureAIFoundrySettings):
        """Initialize the Azure AI Foundry client.

        Args:
            settings: Azure AI Foundry configuration settings
        """
        self.settings = settings
        self.logger = structlog.get_logger(__name__)
        self.agent: AzureAIAgent | None = None
        self.client = None
        self.credential = None
        self._agent_name = "email-intent-classifier"

        if not SK_AVAILABLE:
            raise ImportError(
                "Semantic Kernel is required. Install with: pip install semantic-kernel[azure]"
            )

    async def __aenter__(self) -> "AzureAIFoundryClient":
        """Async context manager entry."""
        # Set environment variables for Semantic Kernel from connection string
        # Parse connection string: https://endpoint;key;resource_group;project_name
        parts = self.settings.connection_string.split(";")
        if len(parts) < 4:
            raise ValueError(
                "Invalid Azure AI Foundry connection string format. Expected: endpoint;key;resource_group;project_name"
            )

        endpoint_base = parts[0]
        # The endpoint should be in the format: https://base/api/projects/project_name
        project_name = parts[3]
        full_endpoint = f"{endpoint_base}/api/projects/{project_name}"

        # Set environment variables for Semantic Kernel
        os.environ["AZURE_AI_AGENT_ENDPOINT"] = full_endpoint
        if "AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME" not in os.environ:
            os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"] = "gpt-4o"

        # Initialize credential and client using proper Semantic Kernel pattern
        self.credential = DefaultAzureCredential()
        self.client = AzureAIAgent.create_client(credential=self.credential)

        # Get or create the agent
        self.agent = await self._get_or_create_agent()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with ultra-aggressive cleanup."""
        # Import cleanup utilities
        from utils.async_cleanup import suppress_future_warnings
        
        # Activate maximum warning suppression immediately
        suppress_future_warnings()
        
        cleanup_tasks = []
        
        try:
            # Ultra-fast cleanup with minimal timeouts
            if hasattr(self, 'agent') and self.agent:
                async def cleanup_agent():
                    try:
                        if hasattr(self.agent, 'close'):
                            await asyncio.wait_for(self.agent.close(), timeout=0.1)
                    except Exception:
                        pass
                    finally:
                        self.agent = None
                        
                cleanup_tasks.append(cleanup_agent())

            if self.client:
                async def cleanup_client():
                    try:
                        await asyncio.wait_for(self.client.close(), timeout=0.1)
                    except Exception:
                        pass
                    finally:
                        self.client = None
                        
                cleanup_tasks.append(cleanup_client())

            if self.credential:
                async def cleanup_credential():
                    try:
                        if hasattr(self.credential, 'close'):
                            await asyncio.wait_for(self.credential.close(), timeout=0.1)
                    except Exception:
                        pass
                    finally:
                        self.credential = None
                        
                cleanup_tasks.append(cleanup_credential())

            # Run all cleanup tasks concurrently with ultra-short timeout
            if cleanup_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*cleanup_tasks, return_exceptions=True),
                        timeout=0.2
                    )
                except Exception:
                    pass

            # Force close any lingering aiohttp sessions with immediate cleanup
            try:
                import gc
                import aiohttp
                
                # Get all aiohttp sessions and force close them immediately
                for obj in gc.get_objects():
                    if isinstance(obj, aiohttp.ClientSession):
                        try:
                            if not obj.closed:
                                # Don't await, force synchronous close
                                if hasattr(obj._connector, '_close'):
                                    obj._connector._close()
                                obj._closed = True
                        except Exception:
                            pass
                            
                    # Also close TCP connectors directly
                    elif hasattr(obj, '__class__') and 'Connector' in obj.__class__.__name__:
                        try:
                            if hasattr(obj, '_close'):
                                obj._close()
                        except Exception:
                            pass

            except Exception:
                pass

            # Multiple rounds of garbage collection
            import gc
            for _ in range(3):
                gc.collect()

        except Exception:
            pass  # Silent suppression of all cleanup errors

    async def _get_or_create_agent(self) -> AzureAIAgent:
        """Get existing agent or create a new one.

        Returns:
            AzureAIAgent instance
        """
        try:
            # Try to find existing agent by name
            agents_pager = self.client.agents.list_agents()
            async for agent_def in agents_pager:
                if agent_def.name == self._agent_name:
                    self.logger.info(
                        "Found existing email intent classifier agent", agent_id=agent_def.id
                    )
                    return AzureAIAgent(client=self.client, definition=agent_def)

            # Create new agent if not found
            self.logger.info("Creating new email intent classifier agent")

            # Try multiple model deployment names
            model_deployment_candidates = [
                os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4",
                "gpt-35-turbo",
                "gpt-4-turbo",
            ]

            agent_definition = None
            for model_deployment in model_deployment_candidates:
                try:
                    self.logger.info(f"Attempting to create agent with model: {model_deployment}")
                    agent_definition = await self.client.agents.create_agent(
                        model=model_deployment,
                        name=self._agent_name,
                        instructions=self._get_agent_instructions(),
                        description="AI agent specialized in understanding and classifying email intent for customer outreach responses",
                    )
                    self.logger.info(f"Successfully created agent with model: {model_deployment}")
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Failed to create agent with model {model_deployment}: {e}"
                    )
                    continue

            if not agent_definition:
                raise Exception("Failed to create agent with any available model deployment")

            self.logger.info(
                "Created new email intent classifier agent", agent_id=agent_definition.id
            )
            return AzureAIAgent(client=self.client, definition=agent_definition)

        except Exception as e:
            self.logger.error("Failed to get or create agent", error=str(e))
            raise

    async def classify_email_intent(
        self, subject: str, body: str, sender_email: str
    ) -> IntentClassificationResult:
        """Classify email intent using Azure AI Foundry Agent Service.

        Args:
            subject: Email subject line
            body: Email body content
            sender_email: Sender email address

        Returns:
            IntentClassificationResult with classification details

        Raises:
            Exception: If classification fails
        """
        start_time = datetime.utcnow()
        thread = None

        try:
            if not self.agent:
                raise RuntimeError("Client not properly initialized. Use async context manager.")

            # Create the classification request
            prompt = self._create_classification_prompt(subject, body, sender_email)

            # Use the agent's automatic thread management - get_response handles everything
            response = await self.agent.get_response(messages=[prompt], thread=thread)

            # Update thread reference for potential future use
            thread = response.thread

            # Parse the agent's response
            # Extract content from AgentResponseItem -> ChatMessageContent -> content (string)
            if hasattr(response, "content") and hasattr(response.content, "content"):
                content = response.content.content
            elif hasattr(response, "message") and hasattr(response.message, "content"):
                content = response.message.content
            elif hasattr(response, "content"):
                content = str(response.content)
            else:
                content = str(response)

            self.logger.debug(f"Extracted content: {content[:200]}...")

            result = self._parse_agent_response(content)

            # Calculate processing time
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result.processing_time_ms = processing_time_ms

            self.logger.info(
                "Email intent classified successfully",
                intent=result.intent.value,
                confidence=result.confidence,
                processing_time_ms=processing_time_ms,
                sender=sender_email,
            )

            return result

        except Exception as e:
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self.logger.error(
                "Failed to classify email intent",
                error=str(e),
                processing_time_ms=processing_time_ms,
                sender=sender_email,
            )

            # Return fallback result
            return IntentClassificationResult(
                intent=EmailIntent.UNKNOWN,
                confidence=0.0,
                reasoning=f"Classification failed: {e!s}",
                detected_phrases=[],
                processing_time_ms=processing_time_ms,
            )

        finally:
            # Clean up thread if created
            if thread:
                try:
                    await thread.delete()
                except Exception as e:
                    self.logger.warning("Error cleaning up thread", error=str(e))

    def _get_agent_instructions(self) -> str:
        """Get the instructions for the email intent classification agent.

        Returns:
            Agent instructions string
        """
        return """
You are an expert AI agent specializing in email intent classification for a customer outreach system.

Your role is to understand the true intent behind customer email responses, going beyond simple keyword matching to understand context, tone, and underlying meaning.

INTENT CATEGORIES TO CLASSIFY:

1. POSITIVE - Customer shows genuine interest and wants more engagement
   - Expresses interest in products/services
   - Requests more information, calls, or meetings
   - Shows willingness to continue the conversation
   - Positive or curious tone about the offering

2. NEGATIVE - Customer clearly wants to stop communication
   - Explicitly requests to stop contact or be removed
   - Expresses lack of interest or annoyance
   - Uses rejection language or negative tone
   - Indicates they don't want the product/service

3. SERVICE_INQUIRY - Customer has questions about existing services/orders
   - Asks about current orders, accounts, or services
   - Billing or support questions
   - Status inquiries or problem reports
   - Needs help with existing relationship

4. OUT_OF_OFFICE - Automated out-of-office response
   - Automated vacation or absence messages
   - Away messages with return dates
   - Auto-reply indicators

5. EMAIL_INVALID - Email delivery failure or invalid address
   - Bounce messages or delivery failures
   - Invalid email address notifications
   - Mailbox full or user unknown errors

6. NO_LONGER_WORKS - Person no longer works at the company
   - Notifications that the person has left
   - Messages about role changes or departures
   - Forwarding to new contacts

ANALYSIS APPROACH:
- Analyze the overall context and tone, not just keywords
- Consider the sender's likely intent and emotional state
- Look for implicit meanings and subtle cues
- Understand cultural and professional communication patterns
- Consider the business context of customer outreach

RESPONSE FORMAT:
Always respond with valid JSON containing:
{
    "intent": "one of: positive, negative, service_inquiry, out_of_office, email_invalid, no_longer_works",
    "confidence": 0.95,
    "reasoning": "Detailed explanation of your analysis and why you classified it this way",
    "detected_phrases": ["key phrases that influenced your decision"]
}

Focus on understanding the human behind the email, not just matching patterns.
""".strip()

    def _create_classification_prompt(self, subject: str, body: str, sender_email: str) -> str:
        """Create the prompt for email intent classification.

        Args:
            subject: Email subject line
            body: Email body content
            sender_email: Sender email address

        Returns:
            Formatted prompt string
        """
        return f"""
Please analyze this email response and classify the sender's intent:

EMAIL DETAILS:
From: {sender_email}
Subject: {subject}
Body: {body}

Analyze the overall context, tone, and meaning to determine the sender's true intent. Provide your classification in the JSON format specified in your instructions.
""".strip()

    def _parse_agent_response(self, content: str) -> IntentClassificationResult:
        """Parse the agent's response and extract intent classification.

        Args:
            content: Response content string from the agent

        Returns:
            IntentClassificationResult object

        Raises:
            Exception: If parsing fails
        """
        try:
            # Try to parse as JSON directly
            try:
                result_data = json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, try to extract JSON from markdown code blocks or text
                import re

                # First try to extract from markdown code blocks (```json ... ```)
                json_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
                if json_block_match:
                    json_content = json_block_match.group(1).strip()
                    try:
                        result_data = json.loads(json_content)
                    except json.JSONDecodeError:
                        # Fallback to regex pattern for raw JSON
                        json_match = re.search(r"\{.*?\}", content, re.DOTALL)
                        if json_match:
                            result_data = json.loads(json_match.group())
                        else:
                            raise Exception(f"No valid JSON found in agent response: {content}") from None
                else:
                    # Fallback to regex pattern for raw JSON
                    json_match = re.search(r"\{.*?\}", content, re.DOTALL)
                    if json_match:
                        result_data = json.loads(json_match.group())
                    else:
                        raise Exception(f"No valid JSON found in agent response: {content}") from None

            # Map intent string to enum
            intent_str = result_data.get("intent", "unknown").lower()
            try:
                intent = EmailIntent(intent_str)
            except ValueError:
                intent = EmailIntent.UNKNOWN

            # Extract other fields with defaults
            confidence = float(result_data.get("confidence", 0.0))
            reasoning = result_data.get("reasoning", "No reasoning provided")
            detected_phrases = result_data.get("detected_phrases", [])

            # Ensure confidence is within valid range
            confidence = max(0.0, min(1.0, confidence))

            return IntentClassificationResult(
                intent=intent,
                confidence=confidence,
                reasoning=reasoning,
                detected_phrases=detected_phrases,
                processing_time_ms=0,  # Will be set by caller
            )

        except Exception as e:
            raise Exception(f"Failed to parse agent response: {e!s}") from e

    async def test_connection(self) -> bool:
        """Test the connection to Azure AI Foundry Agent Service.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with self:
                # Test with a simple classification
                result = await self.classify_email_intent(
                    subject="Test Connection",
                    body="This is a test message to verify the connection.",
                    sender_email="test@example.com",
                )

                return result.intent != EmailIntent.UNKNOWN

        except Exception as e:
            self.logger.error("Connection test failed", error=str(e))
            return False

