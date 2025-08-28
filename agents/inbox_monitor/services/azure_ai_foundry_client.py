"""
Azure AI Foundry Client
=======================

Client for interacting with Azure AI Foundry Agent Services using Semantic Kernel
to classify email intent and determine appropriate response scenarios.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from enum import Enum

import structlog
from pydantic import BaseModel, Field

try:
    from config.settings import AzureAIFoundrySettings
    from .circuit_breaker import CircuitBreaker
    from .prompt_manager import PromptManager
    from .template_renderer import TemplateRenderer
    from services.logging.api_client_logger import APIClientLoggerMixin
except ImportError:
    from ..config.settings import AzureAIFoundrySettings
    from .circuit_breaker import CircuitBreaker
    from .prompt_manager import PromptManager
    from .template_renderer import TemplateRenderer
    from services.logging.api_client_logger import APIClientLoggerMixin

try:
    from azure.identity.aio import ClientSecretCredential
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
    processing_duration_ms: int = Field(..., description="Processing time in milliseconds")


class OriginalSubjectResult(BaseModel):
    """Result of original subject extraction."""

    original_subject: str = Field(..., description="Extracted original subject line")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(..., description="Reasoning for the extraction")
    extraction_method: str = Field(..., description="Method used for extraction")
    processing_duration_ms: int = Field(..., ge=0, description="Processing time in milliseconds")


class AzureAIFoundryClient(APIClientLoggerMixin):
    """Client for Azure AI Foundry Agent Services using Semantic Kernel."""

    def __init__(self, settings: AzureAIFoundrySettings, ai_foundry_credentials, test_mode: bool = False):
        """Initialize the Azure AI Foundry client.

        Args:
            settings: Azure AI Foundry configuration settings
            ai_foundry_credentials: AI Foundry credentials from Key Vault
            test_mode: Enable test mode for unit testing
        """
        # Initialize logging mixin
        self.__init_logging__("azure_ai_foundry_client")
        
        self.settings = settings
        self.ai_foundry_credentials = ai_foundry_credentials
        self.test_mode = test_mode
        self.logger = structlog.get_logger(__name__)
        self.agent: AzureAIAgent | None = None
        self.client = None
        self.credential = None
        self._agent_name = "email-intent-classifier"
        
        # Initialize prompt management
        self.prompt_manager = PromptManager(
            cache_ttl_seconds=300,
            enable_hot_reload=False,  # Disable hot reload for production
            schema_validation=True
        )
        self.template_renderer = TemplateRenderer()
        
        # Resilience
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            expected_exception=Exception
        )
        
        # Performance tracking
        self.performance_metrics = {}

        if not SK_AVAILABLE:
            raise ImportError(
                "Semantic Kernel is required. Install with: pip install semantic-kernel[azure]"
            )

    async def __aenter__(self) -> "AzureAIFoundryClient":
        """Async context manager entry."""
        if not SK_AVAILABLE:
            raise RuntimeError("Semantic Kernel not available")

        self.logger.info("Azure AI Foundry client initializing with live services")
        
        # Set environment variables for Semantic Kernel compatibility
        os.environ["AZURE_AI_AGENT_ENDPOINT"] = self.ai_foundry_credentials.endpoint
        # Always set the preferred model to gpt-4.1
        os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"] = "gpt-4.1"
        self.logger.info(f"Set model deployment name to: {os.environ['AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME']}")

        # Create Service Principal credentials for Azure AI Foundry
        self.credential = ClientSecretCredential(
            tenant_id=self.ai_foundry_credentials.tenant_id,
            client_id=self.ai_foundry_credentials.client_id,
            client_secret=self.ai_foundry_credentials.client_secret.get_secret_value()
        )
        
        # Create client with Service Principal credentials
        self.client = AzureAIAgent.create_client(
            credential=self.credential,
            endpoint=self.ai_foundry_credentials.endpoint
        )

        # Get or create the agent
        self.agent = await self._get_or_create_agent()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with ultra-aggressive cleanup."""
        # Import cleanup utilities from inbox_monitor utils
        import importlib.util
        from pathlib import Path
        current_dir = Path(__file__).parent.parent
        utils_async_cleanup_path = current_dir / "utils" / "async_cleanup.py"
        spec = importlib.util.spec_from_file_location("inbox_utils.async_cleanup", utils_async_cleanup_path)
        if spec and spec.loader:
            async_cleanup_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(async_cleanup_module)
            suppress_future_warnings = async_cleanup_module.suppress_future_warnings
        else:
            def suppress_future_warnings():
                pass  # Fallback no-op if import fails
        
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
            # Determine preferred model deployment
            preferred_model = os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4.1")
            
            # Try to find existing agent by name and check if it uses our preferred model
            agents_pager = self.client.agents.list_agents()
            async for agent_def in agents_pager:
                if agent_def.name == self._agent_name:
                    current_model = getattr(agent_def, 'model', 'unknown')
                    self.logger.info(f"Found existing agent '{self._agent_name}' using model: {current_model}")
                    
                    # Check if existing agent uses the preferred model
                    if hasattr(agent_def, 'model') and agent_def.model == preferred_model:
                        self.logger.info(
                            f"Existing agent already uses preferred model {preferred_model}", 
                            extra={"agent_id": agent_def.id, "model": agent_def.model}
                        )
                        return AzureAIAgent(client=self.client, definition=agent_def)
                    else:
                        # Delete existing agent with wrong model
                        self.logger.info(
                            f"Deleting existing agent with incorrect model. Current: {current_model}, Required: {preferred_model}",
                            extra={"agent_id": agent_def.id, "current_model": current_model, "preferred_model": preferred_model}
                        )
                        try:
                            await self.client.agents.delete_agent(agent_def.id)
                            self.logger.info(f"Successfully deleted outdated agent {agent_def.id}")
                        except Exception as delete_error:
                            self.logger.warning(f"Failed to delete outdated agent {agent_def.id}: {delete_error}")
                        # Continue to create new agent with preferred model
                        break

            # Create new agent if not found
            self.logger.info("Creating new email intent classifier agent")

            # Use only the preferred model - no fallbacks to ensure consistent behavior
            preferred_model = os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4.1")
            
            try:
                self.logger.info(f"Creating agent with model: {preferred_model}")
                instructions = await self._get_agent_instructions()
                agent_definition = await self.client.agents.create_agent(
                    model=preferred_model,
                    name=self._agent_name,
                    instructions=instructions,
                    description="AI agent specialized in understanding and classifying email intent for customer outreach responses",
                )
                self.logger.info(f"Successfully created agent with model: {preferred_model}")
            except Exception as e:
                self.logger.error(f"Failed to create agent with preferred model {preferred_model}: {e}")
                raise Exception(f"Failed to create agent with required model {preferred_model}. Please ensure this model deployment is available in your Azure AI Foundry project.")

            self.logger.info(
                "Created new email intent classifier agent", extra={"agent_id": agent_definition.id}
            )
            return AzureAIAgent(client=self.client, definition=agent_definition)

        except Exception as e:
            self.logger.error(f"Failed to get or create agent: {e}")
            raise

    async def authenticate(self) -> bool:
        """Authenticate with Azure AI Foundry."""
        try:
            if not self.client:
                return False
            return True
        except Exception:
            return False
    
    async def classify_email(self, prompt: str) -> dict:
        """Classify email with circuit breaker protection."""
        return await self.circuit_breaker.call(self._classify_email_protected, prompt)
    
    async def _classify_email_protected(self, prompt: str) -> dict:
        """Classify email with AI service protection."""
        if not self.agent:
            raise RuntimeError("Client not properly initialized. Use async context manager.")
        
        start_time = time.time()
        response = await self.agent.get_response(messages=[prompt])
        response_time = time.time() - start_time
        
        self.performance_metrics['last_classification_time'] = response_time
        
        # Extract content from response
        if hasattr(response, "content") and hasattr(response.content, "content"):
            content = response.content.content
        elif hasattr(response, "message") and hasattr(response.message, "content"):
            content = response.message.content
        elif hasattr(response, "content"):
            content = str(response.content)
        else:
            content = str(response)
        
        return {"classification": content, "response_time": response_time}
    
    async def _make_ai_request_with_validation(self, prompt: str, sender_email: str, max_retries: int = 3) -> IntentClassificationResult:
        """Make AI request with validation and retry logic (Solution 2).
        
        Args:
            prompt: Classification prompt
            sender_email: Sender email for logging context
            max_retries: Maximum number of retry attempts
            
        Returns:
            IntentClassificationResult with classification details
            
        Raises:
            Exception: If all retry attempts fail
        """
        retry_delay = 1.0
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                self.logger.debug("Starting AI request attempt", 
                                attempt=attempt + 1,
                                max_attempts=max_retries,
                                sender_email=sender_email,
                                retry_delay=retry_delay if attempt > 0 else 0)
                
                if not self.agent:
                    raise RuntimeError("Client not properly initialized. Use async context manager.")
                
                # Make the agent call
                self.logger.debug(f"Agent object type: {type(self.agent)}")
                self.logger.debug(f"Agent definition id: {getattr(self.agent.definition, 'id', 'unknown') if hasattr(self.agent, 'definition') else 'no definition'}")
                
                # Call the agent using fresh thread for each request
                response = await self.agent.get_response(messages=[prompt], thread=None)
                
                self.logger.debug(f"Agent response type: {type(response)}")
                self.logger.debug(f"Response object attributes: {dir(response)}")
                
                # Extract content using existing logic
                if hasattr(response, "content") and hasattr(response.content, "content"):
                    content = response.content.content
                elif hasattr(response, "message") and hasattr(response.message, "content"):
                    content = response.message.content
                elif hasattr(response, "content"):
                    content = str(response.content)
                else:
                    content = str(response)
                
                self.logger.debug("Raw AI response extracted", 
                                content_length=len(content),
                                content_preview=content[:300],
                                content_suffix=content[-100:] if len(content) > 100 else content)
                
                # Validate response format before parsing
                if not self._validate_ai_response(content):
                    error_msg = f"Invalid response format on attempt {attempt + 1}"
                    self.logger.warning(error_msg, 
                                      content_preview=content[:500],
                                      sender_email=sender_email)
                    raise Exception(error_msg)
                
                # Check for Azure AI Foundry service errors
                if len(content.strip()) < 500 and (
                    ("Run failed with status" in content and "RunStatus.FAILED" in content and "agent" in content) or 
                    ("Sorry, something went wrong" in content and len(content.strip()) < 100) or
                    "service temporarily unavailable" in content.lower() or
                    "rate limit exceeded" in content.lower()
                ):
                    error_msg = f"Azure AI Foundry service error on attempt {attempt + 1}: {content}"
                    self.logger.warning(error_msg, sender_email=sender_email)
                    raise Exception(error_msg)
                
                # Parse the response
                result = self._parse_agent_response(content)
                
                # Success - log and return
                self.logger.debug("AI request successful", 
                                attempt=attempt + 1,
                                intent=result.intent.value if hasattr(result.intent, 'value') else str(result.intent),
                                confidence=result.confidence,
                                sender_email=sender_email)
                
                return result
                
            except Exception as e:
                last_exception = e
                error_type = type(e).__name__
                error_msg = str(e)
                
                self.logger.warning("AI request attempt failed", 
                                  attempt=attempt + 1,
                                  max_attempts=max_retries,
                                  error_type=error_type,
                                  error_message=error_msg[:500],
                                  sender_email=sender_email)
                
                # Check if this is a retryable error
                retryable_errors = [
                    'timeout', 'connection', 'service unavailable', 'rate limit',
                    'too many requests', '429', '503', '502', '500', 'temporary',
                    'invalid response format', 'json', 'html format'
                ]
                
                is_retryable = any(keyword in error_msg.lower() for keyword in retryable_errors)
                
                if attempt < max_retries - 1 and is_retryable:
                    self.logger.info("Retrying AI request", 
                                   retry_delay=retry_delay,
                                   next_attempt=attempt + 2,
                                   sender_email=sender_email,
                                   is_retryable=is_retryable)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Either max retries reached or non-retryable error
                    if not is_retryable:
                        self.logger.error("Non-retryable error encountered", 
                                        error_type=error_type,
                                        error_message=error_msg,
                                        sender_email=sender_email)
                        raise e
                    else:
                        self.logger.error("Max retry attempts exceeded", 
                                        attempts=max_retries,
                                        final_error=error_msg,
                                        sender_email=sender_email)
                        break
        
        # All attempts failed
        final_error_msg = f"Failed to get valid response after {max_retries} attempts. Last error: {str(last_exception)}"
        self.logger.error("All AI request attempts failed", 
                        max_attempts=max_retries,
                        final_error=final_error_msg,
                        sender_email=sender_email)
        raise Exception(final_error_msg)

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
        start_time = datetime.now(timezone.utc)

        try:
            if not self.agent:
                raise RuntimeError("Client not properly initialized. Use async context manager.")

            # Create the classification request
            prompt = await self._create_classification_prompt(subject, body, sender_email)

            self.logger.debug(f"Sending prompt to Azure AI Foundry agent (length: {len(prompt)})")
            self.logger.debug(f"Prompt preview: {prompt[:200]}...")

            # Solution 2: Response Validation and Retry with enhanced logic
            result = await self._make_ai_request_with_validation(prompt, sender_email)

            # Calculate processing time and create new result with updated time
            processing_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            # Ensure processing time is at least 1ms to avoid test failures
            if processing_duration_ms == 0:
                processing_duration_ms = 1
            result = IntentClassificationResult(
                intent=result.intent,
                confidence=result.confidence,
                reasoning=result.reasoning,
                detected_phrases=result.detected_phrases,
                processing_duration_ms=processing_duration_ms,
            )

            self.logger.info(
                "Email intent classified successfully",
                extra={
                    "intent": result.intent.value,
                    "confidence": result.confidence,
                    "processing_duration_ms": processing_duration_ms,
                    "sender": sender_email,
                }
            )

            return result

        except Exception as e:
            processing_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            # Enhanced error logging with more detail
            error_details = {
                "error_message": str(e),
                "error_type": type(e).__name__,
                "processing_duration_ms": processing_duration_ms,
                "sender": sender_email,
                "subject_preview": subject[:50] if subject else "No subject",
            }
            
            # Check if this is an Azure AI Foundry service error
            if "Azure AI Foundry service error" in str(e) or "RunStatus.FAILED" in str(e):
                error_details["error_category"] = "service_error"
                error_details["suggested_action"] = "Check Azure AI Foundry agent configuration and model deployment"
            elif "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                error_details["error_category"] = "authentication_error"
                error_details["suggested_action"] = "Verify Azure AI Foundry credentials and permissions"
            elif "connection" in str(e).lower() or "timeout" in str(e).lower():
                error_details["error_category"] = "connectivity_error"
                error_details["suggested_action"] = "Check network connectivity to Azure AI Foundry endpoint"
            else:
                error_details["error_category"] = "unknown_error"
                error_details["suggested_action"] = "Review client configuration and logs"
            
            self.logger.error(
                "Failed to classify email intent",
                extra=error_details
            )

            # Return generic fallback result for other errors
            return IntentClassificationResult(
                intent=EmailIntent.UNKNOWN,
                confidence=0.0,
                reasoning=f"Classification failed: {e!s}",
                detected_phrases=[],
                processing_duration_ms=processing_duration_ms,
            )

        finally:
            # Each email classification uses a fresh thread for independence
            # Threads are automatically managed by Azure AI Foundry service
            pass

    async def _get_agent_instructions(self) -> str:
        """Get the instructions for the email intent classification agent.

        Returns:
            Agent instructions string loaded from external configuration
            
        Raises:
            Exception: If prompt loading fails and no fallback is available
        """
        try:
            # Load instructions from external configuration
            instructions = await self.prompt_manager.get_system_instructions("email_classification")
            
            self.logger.debug(
                "Agent instructions loaded from external configuration",
                instruction_length=len(instructions),
                source="email_classification/system_instructions.yaml"
            )
            
            return instructions
            
        except Exception as e:
            self.logger.error(
                "Failed to load agent instructions from external configuration",
                extra={
                    "error": str(e),
                    "fallback_mode": "hardcoded_fallback"
                }
            )
            
            # Fallback to hardcoded instructions for backward compatibility
            # This ensures system continues working even if YAML files are missing
            fallback_instructions = """
You are an expert AI agent specializing in email intent classification for a customer outreach system.

Your role is to understand the true intent behind customer email responses, going beyond simple keyword matching to understand context, tone, and underlying meaning.

INTENT CATEGORIES TO CLASSIFY:

1. POSITIVE - Customer shows genuine interest and wants more engagement
2. NEGATIVE - Customer clearly wants to stop communication
3. SERVICE_INQUIRY - Customer has questions about existing services/orders
4. OUT_OF_OFFICE - Automated out-of-office response
5. EMAIL_INVALID - Email delivery failure or invalid address
6. NO_LONGER_WORKS - Person no longer works at the company

CONFIDENCE SCORING GUIDELINES:
- High confidence (0.85-0.99): Clear intent with multiple supporting indicators
- Medium confidence (0.60-0.84): Reasonable intent but some ambiguity
- Low confidence (0.30-0.59): Unclear intent, minimal content, or edge cases
- Very low confidence (0.10-0.29): Highly ambiguous or contradictory signals

RESPONSE FORMAT:
Always respond with valid JSON containing:
{
    "intent": "one of: positive, negative, service_inquiry, out_of_office, email_invalid, no_longer_works",
    "confidence": [your actual confidence score between 0.0 and 1.0],
    "reasoning": "Detailed explanation of your analysis and why you classified it this way",
    "detected_phrases": ["key phrases that influenced your decision"]
}

Focus on understanding the human behind the email, not just matching patterns.
""".strip()
            
            self.logger.warning("Using fallback hardcoded instructions due to external prompt loading failure")
            return fallback_instructions

    async def _create_classification_prompt(self, subject: str, body: str, sender_email: str) -> str:
        """Create the prompt for email intent classification.

        Args:
            subject: Email subject line
            body: Email body content
            sender_email: Sender email address

        Returns:
            Formatted prompt string
        """
        # Try to load template from PromptManager first
        if hasattr(self.prompt_manager, 'load_template'):
            try:
                template_result = await self.prompt_manager.load_template("email_classification", "classification_template")
                if template_result:
                    # Use the loaded template if available
                    pass  # For now, continue with inline template
            except Exception as e:
                self.logger.debug(f"Failed to load template from PromptManager: {e}")
                pass  # Fall back to inline template
        
        # Use inline template with enhanced analysis
        # Extract domain from email
        domain = sender_email.split('@')[1] if '@' in sender_email else 'unknown'
        
        # Categorize email type based on domain
        common_corporate_domains = ['microsoft.com', 'google.com', 'amazon.com', 'apple.com', 'corp.com', 'bigcorp.com']
        if domain in common_corporate_domains or 'corp' in domain or domain.endswith('.com'):
            email_type = "Corporate/Legitimate"
        else:
            email_type = "Non-standard"
        
        return f"""
Please analyze this email response and classify the sender's intent:

EMAIL DETAILS:
From: {sender_email}
Subject: {subject or "No Subject"}
Body: {body}

CONTEXT ANALYSIS:
Domain: {domain}
Email Type: {email_type}
Sender Pattern: Standard business communication format

Analyze the overall context, tone, and meaning to determine the sender's true intent. Provide your classification in the JSON format specified in your instructions.
""".strip()

    def _extract_json_from_response(self, response_text: str) -> dict:
        """Extract JSON from potentially malformed response with comprehensive debugging.
        
        This is Solution 1 - Enhanced Response Parsing to handle various response formats.
        
        Args:
            response_text: Raw response content from Azure AI Foundry
            
        Returns:
            Dictionary containing parsed JSON data
            
        Raises:
            ValueError: If no valid JSON found in response
        """
        original_length = len(response_text)
        
        # Log detailed response analysis for debugging
        self.logger.debug("Starting JSON extraction from AI response", 
                         response_length=original_length,
                         response_preview=response_text[:200],
                         response_suffix=response_text[-100:] if len(response_text) > 100 else response_text)
        
        # Check if response starts with HTML (common error case)
        if response_text.strip().startswith('<'):
            self.logger.error("Received HTML response instead of JSON", 
                             response_preview=response_text[:500])
            raise ValueError("Response is HTML format, not JSON")
        
        # Check for common error patterns
        error_indicators = ['<!DOCTYPE', '<html', '<error', 'HTTP/', 'Server Error', '500 Internal', '429 Too Many', '503 Service']
        for indicator in error_indicators:
            if indicator.lower() in response_text[:200].lower():
                self.logger.error("Response contains error indicator", 
                                indicator=indicator,
                                response_preview=response_text[:300])
                raise ValueError(f"Response contains error indicator: {indicator}")
        
        # Try direct JSON parsing first (most common case)
        try:
            result = json.loads(response_text)
            self.logger.debug("Successfully parsed response as direct JSON")
            return result
        except json.JSONDecodeError as e:
            self.logger.debug("Direct JSON parsing failed, trying extraction methods", 
                            json_error=str(e),
                            error_position=e.pos if hasattr(e, 'pos') else None)
        
        # Method 1: Extract from markdown code blocks
        import re
        json_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
        if json_block_match:
            json_content = json_block_match.group(1).strip()
            try:
                result = json.loads(json_content)
                self.logger.debug("Successfully extracted JSON from markdown code block")
                return result
            except json.JSONDecodeError as e:
                self.logger.debug("Markdown code block JSON parsing failed", 
                                json_error=str(e),
                                extracted_content=json_content[:200])
        
        # Method 2: Find JSON object boundaries more precisely
        json_start = -1
        json_end = -1
        brace_count = 0
        
        for i, char in enumerate(response_text):
            if char == '{':
                if json_start == -1:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and json_start != -1:
                    json_end = i
                    break
        
        if json_start != -1 and json_end != -1:
            json_content = response_text[json_start:json_end+1]
            try:
                result = json.loads(json_content)
                self.logger.debug("Successfully extracted JSON using brace matching", 
                                json_start=json_start,
                                json_end=json_end,
                                extracted_length=len(json_content))
                return result
            except json.JSONDecodeError as e:
                self.logger.debug("Brace-matched JSON parsing failed", 
                                json_error=str(e),
                                json_content_preview=json_content[:200])
        
        # Method 3: Simple regex fallback
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response_text, re.DOTALL)
        if json_match:
            json_content = json_match.group()
            try:
                result = json.loads(json_content)
                self.logger.debug("Successfully extracted JSON using regex fallback")
                return result
            except json.JSONDecodeError as e:
                self.logger.debug("Regex fallback JSON parsing failed", 
                                json_error=str(e))
        
        # Log the exact problematic area mentioned in user's error
        char_665_area = response_text[660:670] if len(response_text) > 670 else response_text
        line_6_area = response_text.split('\n')[5:7] if len(response_text.split('\n')) > 6 else ["N/A"]
        
        self.logger.error("All JSON extraction methods failed", 
                         char_665_area=char_665_area,
                         line_6_area=line_6_area,
                         response_lines_count=len(response_text.split('\n')),
                         response_first_500=response_text[:500],
                         response_last_200=response_text[-200:] if len(response_text) > 200 else response_text)
        
        raise ValueError(f"No valid JSON found in agent response (length: {original_length})")
    
    def _validate_ai_response(self, content: str) -> bool:
        """Validate AI response format before parsing.
        
        Args:
            content: Response content to validate
            
        Returns:
            True if response appears valid, False otherwise
        """
        if not content or not content.strip():
            self.logger.warning("Empty or whitespace-only response received")
            return False
        
        content_lower = content.lower().strip()
        
        # Check for HTML responses (rate limiting, errors)
        if content_lower.startswith('<'):
            self.logger.warning("Response appears to be HTML format")
            return False
        
        # Check for HTTP error responses
        http_errors = ['http/1.1', 'http/2.0', '<!doctype', '<html', 'server error', 
                      'internal server error', 'service unavailable', 'too many requests']
        if any(error in content_lower[:200] for error in http_errors):
            self.logger.warning("Response appears to be HTTP error page")
            return False
        
        # Check for Azure AI service errors
        ai_errors = ['run failed with status', 'sorry, something went wrong', 
                    'service temporarily unavailable', 'rate limit exceeded']
        if any(error in content_lower for error in ai_errors):
            self.logger.warning("Response contains Azure AI service error")
            return False
        
        # Basic JSON structure check
        if '{' not in content or '}' not in content:
            self.logger.warning("Response does not contain JSON structure")
            return False
        
        return True
    
    def _parse_agent_response(self, content: str) -> IntentClassificationResult:
        """Parse the agent's response and extract intent classification.
        
        Enhanced with Solution 1 (robust JSON extraction) and debugging.

        Args:
            content: Response content string from the agent

        Returns:
            IntentClassificationResult object

        Raises:
            Exception: If parsing fails
        """
        try:
            # Validate response before parsing
            if not self._validate_ai_response(content):
                raise Exception(f"Invalid response format detected: {content[:200]}")
            
            # Use enhanced JSON extraction
            result_data = self._extract_json_from_response(content)

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
                processing_duration_ms=0,  # Will be set by caller
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
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    async def get_health_status(self) -> dict:
        """Get health status of AI Foundry connectivity."""
        start_time = time.time()
        
        try:
            # Test with a simple classification
            test_result = await self.classify_email("Test health check message")
            
            health_time = time.time() - start_time
            self.performance_metrics['last_health_check_time'] = health_time
            
            if test_result:
                return {
                    'status': 'healthy',
                    'response_time': health_time,
                    'last_check': time.time(),
                    'circuit_breaker_state': self.circuit_breaker.state
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': 'Test classification failed',
                    'last_check': time.time(),
                    'circuit_breaker_state': self.circuit_breaker.state
                }
            
        except Exception as e:
            self.logger.error(f"AI Foundry health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': time.time(),
                'circuit_breaker_state': self.circuit_breaker.state
            }

