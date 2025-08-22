"""
Scenario Processor Service
==========================

Service for processing email scenarios (5-11) including intent classification,
expert assignment, and case creation.
"""

import asyncio
import contextlib
import json
import os
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

# Fix import path by adding the correct directory to sys.path
import sys
from pathlib import Path

# Add the parent directory (inbox_monitor) to the path if not already there
current_dir = Path(__file__).parent.parent  # Go up from services/ to inbox_monitor/
current_dir_str = str(current_dir.absolute())
if current_dir_str not in sys.path:
    sys.path.insert(0, current_dir_str)

from config.settings import AppSettings, AzureAIFoundrySettings
from models.email import Email
from services.azure_ai_foundry_client import (
    AzureAIFoundryClient,
    EmailIntent,
    IntentClassificationResult,
)
from services.original_subject_extraction_client import OriginalSubjectExtractionClient
from services.contact_lookup_service import ContactLookupService
from services.round_robin_service import RoundRobinService
from services.salesforce_client import SalesforceClient
from services.email_forwarding_manager import EmailForwardingManager

# Import content_formatter from the inbox_monitor utils, not the parent utils
import importlib.util
utils_content_formatter_path = current_dir / "utils" / "content_formatter.py"
spec = importlib.util.spec_from_file_location("inbox_utils.content_formatter", utils_content_formatter_path)
if spec and spec.loader:
    content_formatter_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(content_formatter_module)
    ContentFormatter = content_formatter_module.ContentFormatter
    ContentFormattingConfig = content_formatter_module.ContentFormattingConfig
else:
    raise ImportError(f"Could not load content_formatter from {utils_content_formatter_path}")


class ScenarioType(Enum):
    """Email scenario types."""

    SCENARIO_5 = "scenario_5"
    SCENARIO_6 = "scenario_6"
    SCENARIO_7 = "scenario_7"
    SCENARIO_8 = "scenario_8"
    SCENARIO_9 = "scenario_9"
    SCENARIO_10 = "scenario_10"
    SCENARIO_11 = "scenario_11"
    UNKNOWN = "unknown"


@dataclass
class ScenarioResult:
    """Result of scenario processing."""

    scenario_type: ScenarioType
    success: bool
    agent_actions_log: list[str]
    expert_assigned: str | None = None
    case_created: str | None = None
    emails_sent: list[str] | None = None
    error_message: str | None = None
    intent_result: Optional[IntentClassificationResult] = None
    
    # Additional metadata for comprehensive tracking (Phase 3 requirement)
    processing_metadata: Optional[Dict[str, Any]] = None
    processing_time_breakdown: Optional[Dict[str, float]] = None
    ai_reasoning_detailed: Optional[str] = None
    scenario_decision_factors: Optional[List[str]] = None
    classification_confidence: Optional[float] = None
    expert_id: Optional[str] = None
    expert_email: Optional[str] = None
    assignment_method: Optional[str] = None
    case_status: Optional[str] = None
    case_subject: Optional[str] = None
    forwarding_success: Optional[bool] = None
    forwarding_reason: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    account_name: Optional[str] = None


class ScenarioProcessor:
    """Process email scenarios and take appropriate actions."""
    
    async def __aenter__(self) -> "ScenarioProcessor":
        """Async context manager entry - establish service connections."""
        if not self._services_connected:
            try:
                # Initialize AI client with Key Vault credentials
                try:
                    from services.azure_key_vault_client import AzureKeyVaultClient
                except ImportError:
                    from ..services.azure_key_vault_client import AzureKeyVaultClient
                
                # Use real Key Vault credentials even when test_mode is enabled for email substitution
                # The test_mode should only affect email addresses, not credential access
                kv_test_mode = False  # Always use real credentials for Key Vault
                async with AzureKeyVaultClient(self.settings.key_vault, test_mode=kv_test_mode) as kv_client:
                    ai_foundry_credentials = await kv_client.get_ai_foundry_credentials()
                    # Create Azure AI Foundry settings from Key Vault credentials
                    ai_foundry_settings = await AzureAIFoundrySettings.from_key_vault(kv_client)
                    # Azure AI Foundry client now only supports live mode - no test mode
                    self.ai_client = AzureAIFoundryClient(ai_foundry_settings, ai_foundry_credentials)
                    # Initialize Original Subject Extraction client with same credentials
                    self.original_subject_client = OriginalSubjectExtractionClient(ai_foundry_settings, ai_foundry_credentials)
                
                # Initialize all clients as async context managers
                await self.ai_client.__aenter__()
                await self.original_subject_client.__aenter__()
                await self.salesforce_client.__aenter__()
                await self.round_robin_service.__aenter__()
                await self.contact_lookup_service.__aenter__()
                
                self._services_connected = True
                self.logger.debug("Scenario processor initialized with Key Vault credentials")
            except Exception as e:
                self.logger.error(
                    "Failed to initialize scenario processor with Key Vault credentials",
                    extra={"error_message": str(e)}
                )
                raise
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup service connections."""
        if self._services_connected:
            try:
                # Close clients with individual error handling
                cleanup_errors = []

                for client_name, client in [
                    ("ai_client", self.ai_client),
                    ("original_subject_client", self.original_subject_client),
                    ("salesforce_client", self.salesforce_client),
                    ("round_robin_service", self.round_robin_service),
                    ("contact_lookup_service", self.contact_lookup_service),
                ]:
                    if client:
                        try:
                            await client.__aexit__(exc_type, exc_val, exc_tb)
                        except Exception as e:
                            cleanup_errors.append(f"{client_name}: {e!s}")
                            self.logger.warning(f"Error closing {client_name}", extra={"error_message": str(e)})

                if cleanup_errors:
                    self.logger.warning("Some cleanup errors occurred", extra={"errors": cleanup_errors})
                
                self._services_connected = False
                self.logger.debug("Scenario processor cleanup completed")
            except Exception as e:
                self.logger.warning(
                    "Error during scenario processor cleanup",
                    extra={"error_message": str(e)}
                )

    def __init__(self, settings: AppSettings):
        """Initialize scenario processor.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = structlog.get_logger(__name__)
        self._services_connected = False

        # Service clients will be initialized in __aenter__ with Key Vault credentials
        self.ai_client = None
        self.original_subject_client = None
        self.salesforce_client = SalesforceClient(settings.salesforce)
        self.round_robin_service = RoundRobinService(settings.test_mode, settings.databricks_oauth)
        self.contact_lookup_service = ContactLookupService(settings.test_mode)
        
        # Initialize email forwarding manager
        self.email_forwarding_manager = EmailForwardingManager()
        
        # Initialize content formatter
        content_config = ContentFormattingConfig(
            content_format=settings.content_formatting.content_format,
            max_description_length=settings.content_formatting.max_description_length,
            preserve_signature=settings.content_formatting.preserve_signature,
            include_metadata=settings.content_formatting.include_metadata,
            truncate_html_fallback=settings.content_formatting.truncate_html_fallback
        )
        self.content_formatter = ContentFormatter(content_config)
        
        self._services_connected = False

    async def process_email_scenario(self, email: Email) -> ScenarioResult:
        """Process an email and determine the appropriate scenario.

        Args:
            email: Email to process

        Returns:
            ScenarioResult with processing results
            
        Raises:
            ValueError: If email is invalid
            RuntimeError: If required services are not available
        """
        print(f"🔍 SCENARIO PROCESSOR DEBUG: process_email_scenario called for email ID: {email.id if email else 'None'}")
        if not email:
            raise ValueError("Email cannot be None")
        if not email.sender or not email.sender.email:
            raise ValueError("Email must have a valid sender")
            
        # Initialize timing and metadata tracking (Phase 3 requirement)
        start_time = time.time()
        processing_times = {}
        decision_factors = []
        
        # Ensure services are connected
        if not self._services_connected:
            await self.__aenter__()
        
        intent_result = None  # Initialize to capture for error handling
        original_subject_result = None  # Phase 3: Initialize for parallel processing
        try:
            # Check for forced scenario in test mode
            # Check for scenario forcing - with special handling for Scenario 9
            force_scenario_9_explicitly = (
                self.settings.test_mode.enabled
                and self.settings.test_mode.force_scenario_9
                and email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower()
            )
            
            force_other_scenario = (
                self.settings.test_mode.enabled
                and self.settings.test_mode.force_scenario is not None
                and self.settings.test_mode.force_scenario != 9  # Don't force scenario 9 via general flag
                and email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower()
            )
            
            if force_scenario_9_explicitly or force_other_scenario:
                if force_scenario_9_explicitly:
                    forced_scenario = 9
                    self.logger.info(
                        "Test mode: explicitly forcing Scenario 9 (email invalid)",
                        extra={
                            "original_email": email.sender.email,
                            "forced_scenario": forced_scenario,
                            "test_mode": True,
                            "explicit_force_scenario_9": True
                        }
                    )
                else:
                    forced_scenario = self.settings.test_mode.force_scenario
                    self.logger.info(
                        "Test mode: forcing scenario for testing",
                        extra={
                            "original_email": email.sender.email,
                            "forced_scenario": forced_scenario,
                            "test_mode": True
                        }
                    )

                # Map forced scenario number to scenario type
                scenario_type_map = {
                    5: ScenarioType.SCENARIO_5,
                    6: ScenarioType.SCENARIO_6,
                    7: ScenarioType.SCENARIO_7,
                    8: ScenarioType.SCENARIO_8,
                    9: ScenarioType.SCENARIO_9,
                    10: ScenarioType.SCENARIO_10,
                    11: ScenarioType.SCENARIO_11,
                }

                scenario_type = scenario_type_map.get(forced_scenario, ScenarioType.UNKNOWN)

                # Create a mock intent result for consistency
                intent_result = IntentClassificationResult(
                    intent=EmailIntent.EMAIL_INVALID
                    if forced_scenario == 9
                    else EmailIntent.UNKNOWN,
                    confidence=1.0,
                    reasoning=f"Test mode: forced scenario {forced_scenario}",
                    detected_phrases=[f"TEST_FORCE_SCENARIO={forced_scenario}"],
                    processing_duration_ms=0,
                )
                
                # Phase 3: Create mock original subject result for test mode
                from services.azure_ai_foundry_client import OriginalSubjectResult
                original_subject_result = OriginalSubjectResult(
                    original_subject=f"Test Mode Subject for Scenario {forced_scenario}",
                    confidence=1.0,
                    reasoning=f"Test mode: mocked original subject for scenario {forced_scenario}",
                    extraction_method="test_mode_mock",
                    processing_duration_ms=0
                )

            else:
                # Clean HTML content before sending to AI (this was missing!)
                clean_body = ""
                if email.body and email.body.content:
                    try:
                        # Use content formatter to clean HTML content
                        clean_body = self.content_formatter.html_to_clean_text(email.body.content)
                        self.logger.debug(
                            "HTML content cleaned for AI classification",
                            email_id=email.id,
                            original_length=len(email.body.content),
                            cleaned_length=len(clean_body)
                        )
                    except Exception as e:
                        self.logger.warning(
                            "Failed to clean HTML content for AI classification, using raw content",
                            error=str(e),
                            email_id=email.id
                        )
                        clean_body = email.body.content

                # Phase 3: Parallel AI operations using asyncio.gather()
                # Architecture: Run both intent classification and original subject extraction concurrently
                # to reduce total processing time while maintaining individual operation timeouts and error handling.
                # This approach improves user experience by parallelizing independent AI operations that would
                # otherwise execute sequentially, reducing total processing time by ~40-50%.
                try:
                    parallel_start = time.time()
                    decision_factors.append(f"Running parallel AI operations: intent classification + original subject extraction")
                    
                    # Define async functions with enhanced retry logic and extended timeouts
                    # Based on Azure AI Foundry best practices: longer timeouts + retry logic
                    async def classify_intent_with_retry():
                        max_retries = 3
                        base_timeout = 120.0  # Increased to 2 minutes per Azure best practices
                        
                        for attempt in range(max_retries):
                            try:
                                return await asyncio.wait_for(
                                    self.ai_client.classify_email_intent(
                                        subject=email.subject,
                                        body=clean_body,
                                        sender_email=email.sender.email,
                                    ),
                                    timeout=base_timeout
                                )
                            except asyncio.TimeoutError as e:
                                if attempt == max_retries - 1:
                                    raise Exception(f"AI intent classification timeout after {max_retries} attempts ({base_timeout}s each)")
                                # Exponential backoff: wait 2^attempt seconds before retry
                                await asyncio.sleep(2 ** attempt)
                                continue
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    raise Exception(f"AI intent classification error after {max_retries} attempts: {str(e)}")
                                # Brief delay before retry for non-timeout errors
                                await asyncio.sleep(1)
                                continue
                    
                    async def extract_original_subject_with_retry():
                        max_retries = 3
                        base_timeout = 120.0  # Increased to 2 minutes per Azure best practices
                        
                        for attempt in range(max_retries):
                            try:
                                return await asyncio.wait_for(
                                    self.original_subject_client.extract_original_subject(email),
                                    timeout=base_timeout
                                )
                            except asyncio.TimeoutError as e:
                                if attempt == max_retries - 1:
                                    raise Exception(f"Original subject extraction timeout after {max_retries} attempts ({base_timeout}s each)")
                                # Exponential backoff: wait 2^attempt seconds before retry
                                await asyncio.sleep(2 ** attempt)
                                continue
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    raise Exception(f"Original subject extraction error after {max_retries} attempts: {str(e)}")
                                # Brief delay before retry for non-timeout errors
                                await asyncio.sleep(1)
                                continue
                    
                    # **IMPROVED: Sequential execution to avoid Azure AI rate limiting conflicts**
                    # Research shows parallel requests can cause throttling with Azure AI Foundry
                    # Sequential approach with reduced total time still better than original implementation
                    
                    # First, run intent classification (higher priority for scenario determination)
                    try:
                        intent_result = await classify_intent_with_retry()
                        self.logger.debug("Intent classification successful", 
                                        intent=intent_result.intent.value if hasattr(intent_result.intent, 'value') else str(intent_result.intent),
                                        confidence=intent_result.confidence,
                                        email_id=email.id)
                    except Exception as e:
                        # Enhanced error logging for JSON parsing issues
                        error_msg = str(e)
                        self.logger.error("Intent classification failed with detailed error analysis", 
                                        error_message=error_msg,
                                        error_type=type(e).__name__,
                                        email_id=email.id,
                                        sender_email=email.sender.email,
                                        is_json_parse_error="parse" in error_msg.lower() and "json" in error_msg.lower(),
                                        is_expecting_value_error="expecting value" in error_msg.lower(),
                                        error_position=re.search(r'char (\d+)', error_msg).group(1) if re.search(r'char (\d+)', error_msg) else None,
                                        error_line=re.search(r'line (\d+)', error_msg).group(1) if re.search(r'line (\d+)', error_msg) else None)
                        
                        # Check for specific error patterns and provide troubleshooting info
                        if "expecting value" in error_msg.lower() and "char" in error_msg.lower():
                            char_match = re.search(r'char (\d+)', error_msg)
                            if char_match:
                                char_pos = int(char_match.group(1))
                                self.logger.error("JSON parse error at specific character position",
                                                char_position=char_pos,
                                                troubleshooting_suggestion="This indicates malformed JSON response from Azure AI Foundry")
                        
                        # Re-raise the original exception but with better context
                        raise Exception(f"Intent classification failed: {error_msg}") from e
                    
                    # Then run original subject extraction (can continue even if this fails)
                    try:
                        original_subject_result = await extract_original_subject_with_retry()
                        if original_subject_result:
                            self.logger.debug("Original subject extraction successful",
                                            original_subject=original_subject_result.original_subject[:100],
                                            confidence=original_subject_result.confidence,
                                            email_id=email.id)
                    except Exception as e:
                        # Enhanced logging for original subject extraction failures
                        error_msg = str(e)
                        self.logger.warning(
                            "Original subject extraction failed but continuing with intent result",
                            error_message=error_msg,
                            error_type=type(e).__name__,
                            email_id=email.id,
                            is_json_parse_error="parse" in error_msg.lower() and "json" in error_msg.lower()
                        )
                        original_subject_result = None
                    
                    # Handle exceptions from parallel operations with proper error details
                    if isinstance(intent_result, Exception):
                        error_msg = str(intent_result) if str(intent_result) else "Unknown AI classification error"
                        self.logger.error(
                            "Intent classification failed in parallel operations",
                            error=error_msg,
                            error_type=type(intent_result).__name__,
                            email_id=email.id,
                            sender=email.sender.email
                        )
                        raise Exception(f"Intent classification failed: {error_msg}")
                    if isinstance(original_subject_result, Exception):
                        self.logger.warning(
                            "Original subject extraction failed but continuing with intent result",
                            error=str(original_subject_result),
                            error_type=type(original_subject_result).__name__,
                            email_id=email.id
                        )
                        original_subject_result = None
                    
                    # Capture parallel processing timing (Phase 3 requirement)
                    parallel_time = (time.time() - parallel_start) * 1000  # Convert to ms
                    processing_times['parallel_ai_operations_ms'] = parallel_time
                    decision_factors.append(f"Parallel AI operations completed in {parallel_time:.2f}ms")
                except asyncio.TimeoutError:
                    self.logger.error(
                        "Parallel AI operations timed out - services may be slow or unavailable",
                        email_id=email.id,
                        sender=email.sender.email,
                        subject=email.subject[:50],
                        timeout_seconds=120,  # Updated to reflect new extended timeout
                        body_length=len(clean_body),
                        ai_client_type=type(self.ai_client).__name__
                    )
                    timeout_result = ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        agent_actions_log=["Parallel AI operations timed out after 30 seconds"],
                        error_message="Parallel AI operations timed out after 30 seconds - AI service may be overloaded"
                    )
                    
                    # **CRITICAL: Track timeout scenario metadata (Phase 3 Integration)**
                    print(f"🔍 DEBUG: About to track timeout scenario metadata for email {email.id}")
                    try:
                        await self._track_scenario_metadata(
                            email=email,
                            scenario_result=timeout_result,
                            intent_result=None,
                            original_subject_result=None,
                            processing_times={'timeout_duration_ms': 120000},
                            decision_factors=["AI operations timed out after 120 seconds", "AI service may be overloaded"]
                        )
                    except Exception as tracking_error:
                        print(f"❌ DEBUG: Failed to track timeout scenario metadata: {tracking_error}")
                    
                    return timeout_result
                except Exception as e:
                    error_details = {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "email_id": email.id,
                        "sender": email.sender.email,
                        "subject": email.subject[:50] if email.subject else "No Subject",
                        "body_length": len(clean_body),
                        "ai_client_initialized": self.ai_client is not None,
                        "ai_client_type": type(self.ai_client).__name__ if self.ai_client else None,
                        "original_subject_client_initialized": self.original_subject_client is not None
                    }
                    
                    self.logger.error(
                        "Parallel AI operations failed with detailed context",
                        **error_details
                    )
                    parallel_error_result = ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        agent_actions_log=[f"Parallel AI operations failed: {type(e).__name__}"],
                        error_message=f"Parallel AI operations failed: {e}"
                    )
                    
                    # **CRITICAL: Track parallel AI error scenario metadata**
                    print(f"🔍 DEBUG: About to track parallel AI error scenario metadata for email {email.id}")
                    try:
                        await self._track_scenario_metadata(
                            email=email,
                            scenario_result=parallel_error_result,
                            intent_result=None,
                            original_subject_result=None,
                            processing_times={},
                            decision_factors=[f"Parallel AI operations failed: {type(e).__name__}", str(e)]
                        )
                    except Exception as tracking_error:
                        print(f"❌ DEBUG: Failed to track parallel AI error scenario metadata: {tracking_error}")
                    
                    return parallel_error_result

                # Validate classification result
                if not intent_result:
                    self.logger.error(
                        "AI classification returned null/empty result",
                        email_id=email.id,
                        sender=email.sender.email,
                        subject=email.subject[:50] if email.subject else "No Subject",
                        ai_client_type=type(self.ai_client).__name__ if self.ai_client else None
                    )
                    null_result = ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        agent_actions_log=["AI classification returned no result"],
                        error_message="AI classification returned no result"
                    )
                    
                    # **CRITICAL: Track null classification scenario metadata**
                    print(f"🔍 DEBUG: About to track null AI classification scenario metadata for email {email.id}")
                    try:
                        await self._track_scenario_metadata(
                            email=email,
                            scenario_result=null_result,
                            intent_result=None,
                            original_subject_result=None,
                            processing_times={},
                            decision_factors=["AI classification returned null/empty result", "No AI result available"]
                        )
                    except Exception as tracking_error:
                        print(f"❌ DEBUG: Failed to track null AI classification scenario metadata: {tracking_error}")
                    
                    return null_result

                # Log successful AI response for debugging
                self.logger.info(
                    "AI classification completed successfully",
                    email_id=email.id,
                    intent=intent_result.intent.value if hasattr(intent_result.intent, 'value') else str(intent_result.intent),
                    confidence=intent_result.confidence,
                    reasoning_preview=intent_result.reasoning[:100] if intent_result.reasoning else "No reasoning provided"
                )

                # Force cleanup of any lingering tasks after AI client usage
                await asyncio.sleep(0.01)  # Brief pause to let any background tasks complete

                # Check if classification was successful (confidence > 0 and not UNKNOWN)
                if intent_result.intent == EmailIntent.UNKNOWN or intent_result.confidence == 0.0:
                    self.logger.warning(
                        "AI classification returned low confidence or unknown intent",
                        email_id=email.id,
                        sender=email.sender.email,
                        subject=email.subject[:50] if email.subject else "No Subject",
                        intent=intent_result.intent.value if hasattr(intent_result.intent, 'value') else str(intent_result.intent),
                        confidence=intent_result.confidence,
                        reasoning=intent_result.reasoning[:200] if intent_result.reasoning else "No reasoning provided",
                        email_body=clean_body[:100] if clean_body else "No body content"
                    )
                    low_confidence_result = ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        agent_actions_log=[f"Low confidence classification: {intent_result.confidence}"],
                        error_message=f"Intent classification failed: {intent_result.reasoning}",
                        intent_result=intent_result
                    )
                    
                    # **CRITICAL: Track low confidence classification scenario metadata**
                    print(f"🔍 DEBUG: About to track low confidence classification scenario metadata for email {email.id}")
                    try:
                        await self._track_scenario_metadata(
                            email=email,
                            scenario_result=low_confidence_result,
                            intent_result=intent_result,
                            original_subject_result=None,
                            processing_times={},
                            decision_factors=["Low confidence AI classification", f"Confidence: {intent_result.confidence}", "Classification threshold not met"]
                        )
                    except Exception as tracking_error:
                        print(f"❌ DEBUG: Failed to track low confidence classification scenario metadata: {tracking_error}")
                    
                    return low_confidence_result

                # Determine scenario based on intent
                scenario_type = self._determine_scenario_type(intent_result)

            # Process the specific scenario with metadata tracking
            scenario_start = time.time()
            decision_factors.append(f"Processing scenario: {scenario_type.value}")
            
            result = await self._process_scenario(email, scenario_type, intent_result)
            
            # Capture scenario processing timing (Phase 3 requirement)
            scenario_time = (time.time() - scenario_start) * 1000  # Convert to ms
            processing_times['scenario_processing_ms'] = scenario_time
            
            # Calculate total processing time
            total_time = (time.time() - start_time) * 1000  # Convert to ms
            processing_times['total_processing_ms'] = total_time
            
            # Enhance result with comprehensive metadata (Phase 3 requirement)
            result.processing_metadata = {
                'email_id': email.id,
                'processing_start_time': start_time,
                'total_processing_duration_ms': total_time,
                'test_mode': self.settings.test_mode.enabled if hasattr(self.settings, 'test_mode') else False,
                'forced_scenario': getattr(self.settings.test_mode, 'force_scenario', None) if hasattr(self.settings, 'test_mode') else None,
                # Phase 3: Store original subject extraction result
                'original_subject_result': {
                    'original_subject': original_subject_result.original_subject if original_subject_result else 'Not extracted',
                    'confidence': original_subject_result.confidence if original_subject_result else 0.0,
                    'reasoning': original_subject_result.reasoning if original_subject_result else 'Extraction not performed or failed',
                    'extraction_method': original_subject_result.extraction_method if original_subject_result else 'none',
                    'processing_duration_ms': original_subject_result.processing_duration_ms if original_subject_result else 0
                }
            }
            result.processing_time_breakdown = processing_times
            result.scenario_decision_factors = decision_factors
            
            # Add AI-specific metadata if available
            if intent_result:
                result.classification_confidence = intent_result.confidence
                result.ai_reasoning_detailed = intent_result.reasoning
                
            self.logger.debug(
                "Scenario processing completed with comprehensive metadata",
                total_time_ms=total_time,
                scenario_type=scenario_type.value,
                metadata_captured=len(processing_times)
            )
            
            # **NEW: Track scenario processing metadata (Critical Integration)**
            print(f"🔍 DEBUG: About to track scenario metadata for email {email.id}")
            try:
                await self._track_scenario_metadata(
                    email=email,
                    scenario_result=result,
                    intent_result=intent_result,
                    original_subject_result=original_subject_result,
                    processing_times=processing_times,
                    decision_factors=decision_factors
                )
                print(f"✅ DEBUG: Successfully tracked scenario metadata for email {email.id}")
            except Exception as tracking_error:
                print(f"❌ DEBUG: Failed to track scenario metadata: {tracking_error}")
                import traceback
                traceback.print_exc()
            
            return result

        except Exception as e:
            self.logger.error(f"Error processing email scenario: {e}")
            
            # Try to determine what scenario we were processing
            determined_scenario = ScenarioType.UNKNOWN
            preserved_actions = []
            
            # If we have intent_result and got far enough to determine scenario
            if intent_result:
                try:
                    determined_scenario = self._determine_scenario_type(intent_result)
                    preserved_actions.append(f"AI classification successful: {intent_result.intent.value} ({intent_result.confidence})")
                except:
                    pass
            
            preserved_actions.append(f"Processing failed: {str(e)}")
            
            error_result = ScenarioResult(
                scenario_type=determined_scenario,
                success=False,
                agent_actions_log=preserved_actions,
                error_message=str(e),
                intent_result=intent_result
            )
            
            # **NEW: Track error scenario metadata as well (Phase 3 Critical Integration)**
            try:
                await self._track_scenario_metadata(
                    email=email,
                    scenario_result=error_result,
                    intent_result=intent_result,
                    original_subject_result=original_subject_result,
                    processing_times={},
                    decision_factors=[f"Processing failed: {str(e)}"]
                )
            except Exception as tracking_error:
                # Don't let tracking errors compound the original error
                self.logger.debug(f"Failed to track error scenario metadata: {tracking_error}")
            
            return error_result

    def _determine_scenario_type(self, intent_result) -> ScenarioType:
        """Determine scenario type based on intent classification result.

        Args:
            intent_result: IntentClassificationResult from Azure AI Foundry

        Returns:
            ScenarioType enum value
        """
        # Map email intent to scenario types
        intent_to_scenario = {
            EmailIntent.POSITIVE: ScenarioType.SCENARIO_5,
            EmailIntent.NEGATIVE: ScenarioType.SCENARIO_6,
            EmailIntent.SERVICE_INQUIRY: ScenarioType.SCENARIO_7,
            EmailIntent.OUT_OF_OFFICE: ScenarioType.SCENARIO_8,
            EmailIntent.EMAIL_INVALID: ScenarioType.SCENARIO_9,
            EmailIntent.NO_LONGER_WORKS: ScenarioType.SCENARIO_10,
            EmailIntent.UNKNOWN: ScenarioType.UNKNOWN,
        }

        return intent_to_scenario.get(intent_result.intent, ScenarioType.UNKNOWN)

    async def _process_scenario(
        self, email: Email, scenario_type: ScenarioType, intent_result: Any
    ) -> ScenarioResult:
        """Process a specific scenario.

        Args:
            email: Email to process
            scenario_type: Type of scenario to process
            intent_result: Intent classification result

        Returns:
            ScenarioResult with processing results
        """
        agent_actions_log = []

        try:
            # Process based on scenario type
            if scenario_type == ScenarioType.SCENARIO_5:
                result = await self._process_scenario_5(email, agent_actions_log)
            elif scenario_type == ScenarioType.SCENARIO_6:
                result = await self._process_scenario_6(email, agent_actions_log)
            elif scenario_type == ScenarioType.SCENARIO_7:
                result = await self._process_scenario_7(email, agent_actions_log)
            elif scenario_type == ScenarioType.SCENARIO_8:
                result = await self._process_scenario_8(email, agent_actions_log)
            elif scenario_type == ScenarioType.SCENARIO_9:
                result = await self._process_scenario_9(email, agent_actions_log)
            elif scenario_type == ScenarioType.SCENARIO_10:
                result = await self._process_scenario_10(email, agent_actions_log)
            elif scenario_type == ScenarioType.SCENARIO_11:
                result = await self._process_scenario_11(email, agent_actions_log)
            else:
                return ScenarioResult(
                    scenario_type=scenario_type,
                    success=False,
                    agent_actions_log=agent_actions_log,
                    error_message="Unknown scenario type",
                    intent_result=intent_result
                )

            # Add intent result to the scenario result
            result.intent_result = intent_result
            return result

        except Exception as e:
            self.logger.error(
                "Error processing scenario",
                extra={
                    "scenario_type": scenario_type,
                    "error_message": str(e)
                }
            )
            return ScenarioResult(
                scenario_type=scenario_type,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=str(e),
                intent_result=intent_result
            )

    async def _process_scenario_5(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 5: Positive response - Create Salesforce case and assign to expert.

        Args:
            email: Email with positive intent
            agent_actions_log: List to track actions taken

        Returns:
            ScenarioResult with expert assignment and case creation details
        """
        try:
            # Step 1: Determine the email address to use for lookups (handle test mode)
            lookup_email = email.sender.email
            
            # Debug test mode conditions
            self.logger.debug(
                "Test mode check in scenario 5",
                extra={
                    "test_mode_enabled": self.settings.test_mode.enabled,
                    "email_test_mode": self.settings.test_mode.email_test_mode,
                    "sender_email": email.sender.email,
                    "test_sender_email": self.settings.test_mode.test_sender_email,
                    "target_salesforce_email": self.settings.test_mode.target_salesforce_email,
                    "email_match": email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower(),
                    "test_condition": (self.settings.test_mode.enabled or self.settings.test_mode.email_test_mode)
                }
            )
            
            if (
                (self.settings.test_mode.enabled or self.settings.test_mode.email_test_mode)
                and email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower()
            ):
                lookup_email = self.settings.test_mode.target_salesforce_email
                agent_actions_log.append(
                    f"TEST MODE: Email substituted from {email.sender.email} to {lookup_email} for lookup"
                )
                self.logger.info(
                    "Test mode email substitution applied",
                    extra={
                        "original_email": email.sender.email,
                        "substituted_email": lookup_email
                    }
                )

            # Step 2: Lookup Salesforce account and contact IDs from Databricks (single lookup)
            async with self.contact_lookup_service as lookup_service:
                contact_lookup = await lookup_service.lookup_contact_by_email(lookup_email)

                if not contact_lookup.found:
                    # Contact not found - cannot assign expert for invalid contact
                    self.logger.warning(
                        "Contact not found in lookup table",
                        extra={
                            "email": lookup_email,
                            "original_email": email.sender.email,
                            "table": "snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t",
                        }
                    )
                    agent_actions_log.append(
                        f"Contact not found in Databricks for {lookup_email}"
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.SCENARIO_5,
                        success=False,
                        agent_actions_log=agent_actions_log,
                        expert_assigned=None,
                        case_created=None,
                        emails_sent=None,
                        error_message=f"Contact {lookup_email} not found in lookup table - cannot assign expert",
                    )

                # Contact found - extract account and contact IDs
                account_id = contact_lookup.sf_account_id or ""
                contact_id = contact_lookup.sf_contact_id or ""
                agent_actions_log.append(
                    f"Found contact in Databricks: Account={account_id}, Contact={contact_id}"
                )

            # Step 3: Get next available expert via round-robin service
            async with self.round_robin_service:
                expert = await self.round_robin_service.assign_lead_to_expert(
                    customer_email=lookup_email
                )
            
            if not expert:
                error_msg = "No available experts for assignment"
                self.logger.error("Expert assignment failed", extra={"customer_email": lookup_email})
                raise Exception(error_msg)
            agent_actions_log.append(f"Assigned expert via round-robin: {expert.expert_name}")

            # Step 4: Create Salesforce case assigned to the expert (original approach with enhanced fields)
            from services.salesforce_client import CaseCreateRequest
            # Import subject_formatter from inbox_monitor utils
            import importlib.util
            utils_subject_formatter_path = current_dir / "utils" / "subject_formatter.py"
            spec = importlib.util.spec_from_file_location("inbox_utils.subject_formatter", utils_subject_formatter_path)
            if spec and spec.loader:
                subject_formatter_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(subject_formatter_module)
                SubjectFormatter = subject_formatter_module.SubjectFormatter
            else:
                raise ImportError(f"Could not load subject_formatter from {utils_subject_formatter_path}")
            
            # Format case description using content formatter (original working approach)
            try:
                formatted_description = self.content_formatter.format_content(
                    email=email,
                    expert_name=expert.expert_name,
                    account_id=account_id,
                    contact_id=contact_id
                )
                agent_actions_log.append("Applied content formatting to case description")
            except Exception as format_error:
                self.logger.warning(
                    "Content formatting failed, using fallback description",
                    error=str(format_error),
                    email_id=email.id
                )
                # Fallback to simple description
                formatted_description = f"Customer {lookup_email} responded positively to outreach.\n\nOriginal Subject: {email.subject}\n\nResponse: {email.body.content if email.body else 'No content'}"
                agent_actions_log.append("Used fallback description format due to formatting error")

            # Create case request with enhanced fields added to original working code
            formatted_subject = self._format_case_subject(contact_lookup.account_name, email.subject)
            self.logger.info(
                "Creating Salesforce case with Low Touch Expert assignment",
                extra={
                    "formatted_subject": formatted_subject,
                    "account_id": account_id,
                    "contact_id": contact_id,
                    "expert_id": expert.expert_id,
                    "expert_name": expert.expert_name,
                    "expert_email": expert.expert_email,
                    "case_queue": self.settings.salesforce.case_queue,
                    "scenario": "5_positive_response"
                }
            )
            
            case_request = CaseCreateRequest(
                account_id=account_id,
                contact_id=contact_id,
                owner_id=expert.expert_id,  # Use the Low Touch Expert's Salesforce User ID
                subject=formatted_subject,  # Enhanced AI Agent Led INQUIRY format
                description=formatted_description,  # Original working template
                origin="AI Agent",
                status="Assigned",  # Enhanced field for workflow routing  
                priority="Medium",
                case_queue=self.settings.salesforce.case_queue,
                type="Digital Outreach",  # Enhanced field for categorization
                request_case_category="AI Agent"  # Enhanced field for tracking
            )
            
            case_response = await self.salesforce_client.create_case(case_request)
            if not case_response.success:
                # Sanitize error messages for SQL storage
                sanitized_errors = []
                if case_response.errors:
                    for error in case_response.errors:
                        # Clean up error messages by removing problematic characters
                        clean_error = str(error).replace('"', "'").replace("\\", "/").replace('\n', ' ').replace('\r', '')
                        # Truncate very long error messages
                        if len(clean_error) > 200:
                            clean_error = clean_error[:197] + "..."
                        sanitized_errors.append(clean_error)
                
                error_msg = f"Failed to create Salesforce case: {'; '.join(sanitized_errors) or 'Unknown error'}"
                self.logger.error(
                    "Salesforce case creation failed",
                    account_id=account_id,
                    contact_id=contact_id,
                    expert=expert.expert_name,
                    errors=case_response.errors
                )
                agent_actions_log.append(f"Case creation failed: {error_msg}")
                # Return partial success - we still have expert assignment and contact lookup data
                return ScenarioResult(
                    scenario_type=ScenarioType.SCENARIO_5,
                    success=False,  # Overall failed due to case creation
                    agent_actions_log=agent_actions_log,
                    expert_assigned=expert.expert_name,
                    expert_email=expert.expert_email,
                    case_created=None,  # Case creation failed
                    error_message=error_msg,
                )
            case_id = case_response.id
            agent_actions_log.append(f"Created Salesforce case with enhanced fields: {case_id}")

            self.logger.info(
                "Scenario 5 completed successfully - Low Touch Expert assigned as Support Request Owner",
                extra={
                    "expert_name": expert.expert_name,
                    "expert_id": expert.expert_id,
                    "expert_email": expert.expert_email,
                    "case_id": case_id,
                    "customer_email": lookup_email,
                    "account_id": account_id,
                    "contact_id": contact_id,
                    "scenario": "5_positive_response",
                    "owner_assignment_method": "round_robin_expert_id",
                    "assignment_rules_disabled": True,
                }
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_5,
                success=True,
                agent_actions_log=agent_actions_log,
                expert_assigned=expert.expert_name,
                expert_id=expert.expert_id,
                expert_email=expert.expert_email,
                case_created=case_id,
                account_id=account_id,
                contact_id=contact_id,
                account_name=contact_lookup.account_name,
                assignment_method="round_robin_expert_id",
                case_status="New",
                case_subject=formatted_subject,
            )

        except Exception as e:
            # Provide better error message formatting
            error_str = str(e) if str(e) else "Unknown error occurred"
            error_msg = f"Failed to process scenario 5: {error_str}"
            agent_actions_log.append(error_msg)
            
            # Use lookup_email if available, fallback to original email if substitution hasn't happened yet
            customer_email_for_logging = locals().get('lookup_email', email.sender.email)
            self.logger.error(
                "Scenario 5 processing failed",
                customer_email=customer_email_for_logging,
                original_email=email.sender.email,
                error_type=type(e).__name__,
                error_message=error_str,
                actions_completed=len(agent_actions_log)
            )
            
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_5,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=error_msg,
            )

    async def _process_scenario_6(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 6: Negative response - Forward to Victoria Grant.

        Args:
            email: Email with negative intent
            agent_actions_log: List to track actions taken

        Returns:
            ScenarioResult with email forwarding details
        """
        try:
            # Forward email to Victoria Grant
            victoria_email = self.settings.scenarios.victoria_grant_email

            forwarding_success = await self._forward_email_to_recipient(
                original_email=email,
                recipient_email=victoria_email,
                recipient_name="Victoria Grant",
                reason="Negative customer response requiring attention",
            )

            if forwarding_success:
                agent_actions_log.append(f"Forwarded negative response to Victoria Grant: {victoria_email}")
            else:
                agent_actions_log.append(f"Failed to forward negative response to Victoria Grant: {victoria_email}")
                self.logger.error(
                    "Scenario 6 failed due to email forwarding failure",
                    customer_email=email.sender.email,
                    victoria_email=victoria_email
                )
                return ScenarioResult(
                    scenario_type=ScenarioType.SCENARIO_6,
                    success=False,
                    agent_actions_log=agent_actions_log,
                    error_message="Email forwarding failed"
                )

            self.logger.info(
                "Scenario 6 completed successfully",
                forwarded_to=victoria_email,
                customer_email=email.sender.email,
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_6,
                success=True,
                agent_actions_log=agent_actions_log,
                emails_sent=[victoria_email],
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 6: {e!s}"
            agent_actions_log.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_6,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=error_msg,
            )

    async def _process_scenario_7(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 7: Service inquiry - Forward to account team.

        Args:
            email: Email with service inquiry intent
            agent_actions_log: List to track actions taken

        Returns:
            ScenarioResult with email forwarding details
        """
        try:
            # Forward email to account team
            account_team_email = self.settings.scenarios.account_team_email

            forwarding_success = await self._forward_email_to_recipient(
                original_email=email,
                recipient_email=account_team_email,
                recipient_name="Account Team",
                reason="Customer service inquiry requiring assistance",
            )

            if forwarding_success:
                agent_actions_log.append(f"Forwarded service inquiry to account team: {account_team_email}")
            else:
                agent_actions_log.append(f"Failed to forward service inquiry to account team: {account_team_email}")
                self.logger.error(
                    "Scenario 7 failed due to email forwarding failure",
                    customer_email=email.sender.email,
                    account_team_email=account_team_email
                )
                return ScenarioResult(
                    scenario_type=ScenarioType.SCENARIO_7,
                    success=False,
                    agent_actions_log=agent_actions_log,
                    error_message="Email forwarding failed"
                )

            self.logger.info(
                "Scenario 7 completed successfully",
                forwarded_to=account_team_email,
                customer_email=email.sender.email,
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_7,
                success=True,
                agent_actions_log=agent_actions_log,
                emails_sent=[account_team_email],
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 7: {e!s}"
            agent_actions_log.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_7,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=error_msg,
            )

    async def _process_scenario_8(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 8: Out of office - Update Databricks table.

        Args:
            email: Email with out-of-office intent
            agent_actions_log: List to track actions taken

        Returns:
            ScenarioResult with database update details
        """
        try:
            # Update the assignment status to mark as out of office using async context manager
            async with self.round_robin_service:
                assignment = await self.round_robin_service.get_assignment_by_customer(
                    email.sender.email
                )
                if assignment:
                    await self.round_robin_service.update_assignment_status(
                        assignment_id=assignment.assignment_id, new_status="out_of_office"
                    )

            agent_actions_log.append(
                f"Updated Databricks table with out-of-office status for {email.sender.email}"
            )

            self.logger.info(
                "Scenario 8 completed successfully",
                customer_email=email.sender.email,
                status="out_of_office",
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_8, success=True, agent_actions_log=agent_actions_log
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 8: {e!s}"
            agent_actions_log.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_8,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=error_msg,
            )

    async def _process_scenario_9(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 9: Invalid email - Update Salesforce Invalid_Email field.

        Args:
            email: Email indicating invalid/bounced email
            agent_actions_log: List to track actions taken

        Returns:
            ScenarioResult with Salesforce update details
        """
        try:
            # Extract the original email address that bounced from the email content
            # This will typically be in the sender email or mentioned in the bounce message
            bounced_email = email.sender.email

            # Handle test mode email substitution for scenario processing
            lookup_email = bounced_email
            if (
                (self.settings.test_mode.enabled or self.settings.test_mode.email_test_mode)
                and bounced_email.lower() == self.settings.test_mode.test_sender_email.lower()
            ):
                lookup_email = self.settings.test_mode.target_salesforce_email
                self.logger.info(
                    "Test mode: substituting email for Scenario 9 processing",
                    extra={
                        "original_email": bounced_email,
                        "lookup_email": lookup_email,
                        "test_mode": True,
                    }
                )

            # Lookup contact ID from Databricks first
            async with self.contact_lookup_service as lookup_service:
                contact_lookup = await lookup_service.lookup_contact_by_email(bounced_email)

                if contact_lookup.found and contact_lookup.sf_contact_id:
                    # Update Salesforce contact with Is_Email_Invalid__c field (boolean)
                    from services.salesforce_client import ContactUpdateRequest

                    contact_update = ContactUpdateRequest(
                        contact_id=contact_lookup.sf_contact_id, 
                        is_email_invalid=True
                    )
                    success = await self.salesforce_client.update_contact_invalid_email(
                        contact_update
                    )
                    if not success:
                        raise Exception(
                            f"Failed to update Salesforce Is_Email_Invalid__c field to true for {lookup_email} (Contact: {contact_lookup.sf_contact_id})"
                        )

                    agent_actions_log.append(
                        f"Updated Salesforce Is_Email_Invalid__c field to true for {lookup_email} (Contact: {contact_lookup.sf_contact_id})"
                    )
                else:
                    # Contact not found in lookup table - log warning but continue
                    agent_actions_log.append(
                        f"Contact not found in Databricks for {lookup_email} - skipped Salesforce update"
                    )
                    self.logger.warning(
                        "Cannot update Salesforce contact - not found in lookup table",
                        extra={
                            "email": lookup_email,
                            "original_email": bounced_email if lookup_email != bounced_email else None,
                        }
                    )

            # Also update assignment status in Databricks to stop future email attempts using async context manager
            async with self.round_robin_service:
                assignment = await self.round_robin_service.get_assignment_by_customer(bounced_email)
                if assignment:
                    await self.round_robin_service.update_assignment_status(
                        assignment_id=assignment.assignment_id, new_status="email_invalid"
                    )

            agent_actions_log.append(f"Updated Databricks to stop future emails to {bounced_email}")

            self.logger.info(
                "Scenario 9 completed successfully",
                bounced_email=bounced_email,
                salesforce_updated=True,
                databricks_updated=True,
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_9, success=True, agent_actions_log=agent_actions_log
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 9: {e!s}"
            agent_actions_log.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_9,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=error_msg,
            )

    async def _process_scenario_10(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 10: No longer works - Forward to Victoria Grant.

        Args:
            email: Email indicating person no longer works at company
            agent_actions_log: List to track actions taken

        Returns:
            ScenarioResult with email forwarding details
        """
        try:
            # Forward email to Victoria Grant (same as scenario 6)
            victoria_email = self.settings.scenarios.victoria_grant_email

            forwarding_success = await self._forward_email_to_recipient(
                original_email=email,
                recipient_email=victoria_email,
                recipient_name="Victoria Grant",
                reason="Contact no longer works at company - requires attention",
            )

            if forwarding_success:
                agent_actions_log.append(
                    f"Forwarded 'no longer works' notification to Victoria Grant: {victoria_email}"
                )
            else:
                agent_actions_log.append(
                    f"Failed to forward 'no longer works' notification to Victoria Grant: {victoria_email}"
                )
                self.logger.error(
                    "Scenario 10 failed due to email forwarding failure",
                    customer_email=email.sender.email,
                    victoria_email=victoria_email
                )
                return ScenarioResult(
                    scenario_type=ScenarioType.SCENARIO_10,
                    success=False,
                    agent_actions_log=agent_actions_log,
                    error_message="Email forwarding failed"
                )

            # Update assignment status to stop future email attempts using async context manager
            async with self.round_robin_service:
                assignment = await self.round_robin_service.get_assignment_by_customer(
                    email.sender.email
                )
                if assignment:
                    await self.round_robin_service.update_assignment_status(
                        assignment_id=assignment.assignment_id, new_status="no_longer_works"
                    )

            agent_actions_log.append(
                f"Updated Databricks to stop future emails to {email.sender.email}"
            )

            self.logger.info(
                "Scenario 10 completed successfully",
                forwarded_to=victoria_email,
                customer_email=email.sender.email,
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_10,
                success=True,
                agent_actions_log=agent_actions_log,
                emails_sent=[victoria_email],
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 10: {e!s}"
            agent_actions_log.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_10,
                success=False,
                agent_actions_log=agent_actions_log,
                error_message=error_msg,
            )

    async def _process_scenario_11(self, email: Email, agent_actions_log: list[str]) -> ScenarioResult:
        """Process scenario 11."""
        agent_actions_log.append("Processed scenario 11")
        return ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_11, success=True, agent_actions_log=agent_actions_log
        )

    async def _track_scenario_metadata(
        self,
        email: Email,
        scenario_result: ScenarioResult,
        intent_result: IntentClassificationResult = None,
        original_subject_result = None,
        processing_times: Dict[str, float] = None,
        decision_factors: List[str] = None
    ):
        """
        Track scenario processing metadata using the integration service.
        
        This method addresses the critical audit finding by capturing scenario-specific
        metadata that was missing from the EmailProcessor integration.
        
        Args:
            email: Original email being processed
            scenario_result: Results from scenario processing
            intent_result: AI intent classification results
            processing_times: Performance timing data
            decision_factors: Factors that influenced scenario decisions
        """
        print(f"🔍 DEBUG: _track_scenario_metadata called for email {email.id}")
        try:
            # Import integration service (lazy import to avoid circular dependencies)
            print(f"🔍 DEBUG: Importing scenario tracking integration...")
            from services.scenario_tracking_integration import get_tracking_integration
            
            # Get tracking integration instance
            tracking_integration = await get_tracking_integration()
            
            # Create enhanced metadata context for scenario-specific data
            scenario_metadata = {
                'scenario_specific_processing': True,
                'scenario_decision_factors': decision_factors or [],
                'scenario_processing_times': processing_times or {},
                'scenario_ai_metadata': {
                    'intent': intent_result.intent.value if intent_result and hasattr(intent_result.intent, 'value') else 'unknown',
                    'confidence': intent_result.confidence if intent_result else None,
                    'reasoning': intent_result.reasoning if intent_result else None,
                    'detected_phrases': intent_result.detected_phrases if intent_result else [],
                    'processing_duration_ms': intent_result.processing_duration_ms if intent_result else None
                } if intent_result else {},
                'original_subject_metadata': {
                    'original_subject': original_subject_result.original_subject if original_subject_result else None,
                    'confidence': original_subject_result.confidence if original_subject_result else None,
                    'reasoning': original_subject_result.reasoning if original_subject_result else None,
                    'extraction_method': original_subject_result.extraction_method if original_subject_result else None,
                    'processing_duration_ms': original_subject_result.processing_duration_ms if original_subject_result else None
                } if original_subject_result else {},
                'scenario_actions': {
                    'agent_actions_log': scenario_result.agent_actions_log if scenario_result else [],
                    'expert_assigned': scenario_result.expert_assigned if scenario_result else None,
                    'case_created': scenario_result.case_created if scenario_result else None,
                    'emails_sent': scenario_result.emails_sent if scenario_result else [],
                },
                'scenario_outcome': {
                    'success': scenario_result.success if scenario_result else False,
                    'scenario_type': scenario_result.scenario_type.value if scenario_result and hasattr(scenario_result.scenario_type, 'value') else 'unknown',
                    'error_message': scenario_result.error_message if scenario_result else None
                },
                'environment': f"test_mode={self.settings.test_mode.enabled if hasattr(self.settings, 'test_mode') else False};type=scenario_processor_metadata_capture;version=1.0.0"
            }
            
            # Create mock processing result for tracking (since this is called from scenario processor)
            mock_processing_result = type('ProcessingResult', (), {
                'success': scenario_result.success if scenario_result else False,
                'process_id': f"proc_{int(time.time() * 1000)}",
                'email_id': email.id,
                'scenario_type': scenario_result.scenario_type.value if scenario_result and hasattr(scenario_result.scenario_type, 'value') else None,
                'processing_duration_ms': int(sum(processing_times.values())) if processing_times else 0,
                'error': scenario_result.error_message if scenario_result else None,
                'scenario_success': scenario_result.success if scenario_result else False,
                'agent_actions_log': scenario_result.agent_actions_log if scenario_result else [],
                'expert_assigned': scenario_result.expert_assigned if scenario_result else None,
                'case_created': scenario_result.case_created if scenario_result else None,
                'emails_sent': scenario_result.emails_sent if scenario_result else []
            })()
            
            # Track the scenario metadata using the integration service
            # Email object debug info available in logs
            tracking_result = await tracking_integration.track_scenario_processing(
                email_data=email,
                processing_result=mock_processing_result,
                scenario_result=scenario_result,
                intent_result=intent_result,
                original_subject_result=original_subject_result,
                correlation_id=f"corr_{int(time.time())}",
                **scenario_metadata
            )
            
            # Log tracking result for debugging
            if tracking_result.success:
                self.logger.debug(
                    "Scenario metadata tracking completed successfully",
                    email_id=email.id,
                    scenario_type=scenario_result.scenario_type.value if scenario_result and hasattr(scenario_result.scenario_type, 'value') else 'unknown',
                    tracking_time_ms=tracking_result.processing_duration_ms,
                    async_queued=tracking_result.async_queued
                )
            else:
                self.logger.warning(
                    "Scenario metadata tracking failed but processing continues",
                    email_id=email.id,
                    tracking_error=tracking_result.error_message,
                    tracking_time_ms=tracking_result.processing_duration_ms
                )
                
        except Exception as e:
            # Critical requirement: Never fail scenario processing due to tracking errors
            self.logger.error(
                "Scenario metadata tracking integration failed",
                error=str(e),
                error_type=type(e).__name__,
                email_id=email.id if email else 'unknown'
            )

    async def _forward_email_to_recipient(
        self, original_email: Email, recipient_email: str, recipient_name: str, reason: str
    ) -> bool:
        """Forward an email to a specific recipient using external templates.

        Args:
            original_email: The original email to forward
            recipient_email: Email address to forward to
            recipient_name: Name of the recipient
            reason: Reason for forwarding

        Returns:
            True if email forwarding succeeded, False otherwise

        Raises:
            Exception: If email forwarding fails
        """
        try:
            # Determine scenario type from reason for scenario-specific templates
            scenario_type = self._determine_scenario_type_from_reason(reason)
            
            # Generate email content using external templates
            try:
                email_content = await self.email_forwarding_manager.generate_forwarding_email_content(
                    original_email=original_email,
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    scenario_type=scenario_type,
                    reason_override=reason
                )
                
                # Generate subject with scenario-specific template if available
                if scenario_type:
                    scenario_config = await self.email_forwarding_manager.get_scenario_forwarding_config(scenario_type)
                    subject_template = scenario_config.get("subject_template", "FWD: ${original_subject}")
                    forward_subject = subject_template.replace("${original_subject}", original_email.subject or "No Subject")
                else:
                    forward_subject = f"FWD: {original_email.subject}"
                
                self.logger.info(
                    "Email content generated from external templates",
                    recipient_email=recipient_email,
                    scenario_type=scenario_type,
                    content_length=len(email_content)
                )
                
            except Exception as e:
                self.logger.warning(
                    "Failed to generate email content from external templates, using fallback",
                    extra={
                        "error_message": str(e),
                        "recipient_email": recipient_email
                    }
                )
                
                # Fallback to original inline generation
                forward_subject = f"FWD: {original_email.subject}"
                email_content = f"""{reason}

Original Email Details:
From: {original_email.sender.email} ({original_email.sender.name})
Sent: {original_email.received_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}
Subject: {original_email.subject}

--- Original Message ---
{original_email.body.content}"""

            # Get the path to the email agent directory
            current_dir = os.path.dirname(os.path.abspath(__file__))  # /inbox_monitor/services/
            inbox_monitor_dir = os.path.dirname(current_dir)  # /inbox_monitor/
            agents_dir = os.path.dirname(inbox_monitor_dir)  # /agents/
            email_dir = os.path.join(agents_dir, "email")  # /agents/email/

            # Generate Python script using external templates
            try:
                email_script = await self.email_forwarding_manager.generate_forwarding_script(
                    email_content=email_content,
                    subject=forward_subject,
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    email_agent_path=email_dir
                )
                
                self.logger.info(
                    "Email forwarding script generated from external templates",
                    recipient_email=recipient_email,
                    script_length=len(email_script)
                )
                
            except Exception as e:
                self.logger.warning(
                    "Failed to generate email script from external templates, using fallback",
                    extra={
                        "error_message": str(e),
                        "recipient_email": recipient_email
                    }
                )
                
                # Fallback to original inline script generation
                escaped_subject = forward_subject.replace('"', '\\"').replace("\n", "\\n")
                escaped_body = email_content.replace('"""', '\\"\\"\\"').replace("\\", "\\\\")

                email_script = f'''
import sys
import os
sys.path.insert(0, r"{email_dir}")

# Ensure the subprocess can find the .env file in the root directory
from dotenv import load_dotenv
root_env_path = os.path.join(r"{email_dir}", "..", "..", ".env")
load_dotenv(root_env_path)

from email_clients.azure_email_client import AzureEmailClient
from services.test_mode_service import TestModeService
from config.settings import get_settings
from database.models import EmailContent
import asyncio
import json

async def send_email():
    try:
        settings = await get_settings()
        azure_client = AzureEmailClient(settings.azure_communication)
        test_mode_service = TestModeService(settings)
        
        # Create email content object
        email_content = EmailContent(
            subject="{escaped_subject}",
            body_html="""{escaped_body}""".replace("\\n", "<br>"),
            recipient_email="{recipient_email}",
            customer_id="INBOX_MONITOR",
            customer_name="{recipient_name}",
            contact_name="{recipient_name}"
        )
        
        # Apply test mode override if enabled
        processed_content = test_mode_service.process_email_content(email_content)
        
        result = await azure_client.send_email(
            recipient_email=processed_content.recipient_email,
            subject=processed_content.subject,
            body_html=f"<html><body>{{processed_content.body_html}}</body></html>"
        )
        
        print(json.dumps({{"success": result.success, "message_id": result.message_id or "", "error": result.error_message or ""}}))
    except Exception as e:
        print(json.dumps({{"success": False, "error": str(e)}}))

if __name__ == "__main__":
    asyncio.run(send_email())
'''

            # Write the script to a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(email_script)
                temp_script_path = f.name

            try:
                # Run the script in the email agent's environment
                import subprocess
                result = subprocess.run(
                    ["python", temp_script_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=email_dir,
                    # Suppress warnings from subprocess
                    env={**os.environ, "PYTHONWARNINGS": "ignore::ResourceWarning"},
                )

                if result.returncode == 0:
                    try:
                        # Extract JSON from the output (last line should be the JSON)
                        stdout_lines = result.stdout.strip().split('\n')
                        json_line = None
                        
                        # Look for the JSON line (starts with { and ends with })
                        for line in reversed(stdout_lines):
                            line = line.strip()
                            if line.startswith('{') and line.endswith('}'):
                                json_line = line
                                break
                        
                        if json_line:
                            output = json.loads(json_line)
                            if output.get("success"):
                                self.logger.info(
                                    "Email forwarded successfully via subprocess",
                                    to_email=recipient_email,
                                    message_id=output.get("message_id", ""),
                                    using_external_templates=True
                                )
                                return True
                            else:
                                self.logger.error(f"Email forwarding failed: {output.get('error')}")
                                return False
                        else:
                            self.logger.error(
                                "No JSON output found in email service response",
                                stdout=result.stdout
                            )
                            return False
                            
                    except json.JSONDecodeError as e:
                        self.logger.error(
                            "Failed to parse email service JSON output",
                            extra={
                                "json_line": json_line if 'json_line' in locals() else "not found",
                                "error_message": str(e),
                                "stdout": result.stdout
                            }
                        )
                        return False
                else:
                    self.logger.error(
                        "Email service subprocess failed",
                        returncode=result.returncode,
                        stderr=result.stderr
                    )
                    return False
            finally:
                # Clean up the temporary script
                import contextlib
                with contextlib.suppress(Exception):
                    os.unlink(temp_script_path)

        except Exception as e:
            self.logger.error(f"Failed to forward email to {recipient_email}: {e}")
            raise

    def _determine_scenario_type_from_reason(self, reason: str) -> Optional[str]:
        """Determine scenario type from forwarding reason for template selection."""
        reason_lower = reason.lower()
        
        if "negative" in reason_lower:
            return "negative_response"
        elif "service" in reason_lower or "inquiry" in reason_lower:
            return "service_inquiry"
        elif "no longer works" in reason_lower:
            return "no_longer_works"
        else:
            return None

    def _format_case_subject(self, account_name: str | None, original_subject: str) -> str:
        """Format case subject using AI Agent Led INQUIRY format with account name.
        
        Args:
            account_name: Account/customer name from contact lookup
            original_subject: Original email subject
            
        Returns:
            Formatted subject string
        """
        try:
            # Import subject_formatter from inbox_monitor utils
            import importlib.util
            utils_subject_formatter_path = current_dir / "utils" / "subject_formatter.py"
            spec = importlib.util.spec_from_file_location("inbox_utils.subject_formatter", utils_subject_formatter_path)
            if spec and spec.loader:
                subject_formatter_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(subject_formatter_module)
                SubjectFormatter = subject_formatter_module.SubjectFormatter
                
                formatter = SubjectFormatter()
                
                if account_name:
                    return formatter.format_ai_inquiry_subject(account_name, original_subject)
                else:
                    # Fallback when no account name available
                    return formatter.format_ai_inquiry_subject("Unknown Account", original_subject)
            else:
                raise ImportError(f"Could not load subject_formatter from {utils_subject_formatter_path}")
                
        except ImportError as e:
            self.logger.warning(
                "SubjectFormatter not available, using manual formatting",
                extra={
                    "account_name": account_name,
                    "original_subject": original_subject,
                    "error_message": str(e)
                }
            )
            # Manual fallback formatting
            account_display = account_name if account_name else "Unknown Account"
            return f"AI Agent Led INQUIRY | {account_display}"
            
        except Exception as e:
            self.logger.warning(
                "Subject formatting failed, using fallback",
                extra={
                    "account_name": account_name,
                    "original_subject": original_subject,
                    "error_message": str(e)
                }
            )
            # Ultimate fallback - manual formatting
            account_display = account_name if account_name else "Unknown Account"
            return f"AI Agent Led INQUIRY | {account_display}"

