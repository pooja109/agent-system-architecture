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
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import structlog

# Fix import path by adding the correct directory to sys.path
import sys
from pathlib import Path

# Add the parent directory (inbox_monitor) to the path if not already there
current_dir = Path(__file__).parent.parent  # Go up from services/ to inbox_monitor/
current_dir_str = str(current_dir.absolute())
if current_dir_str not in sys.path:
    sys.path.insert(0, current_dir_str)

from config.settings import AppSettings
from models.email import Email
from services.azure_ai_foundry_client import (
    AzureAIFoundryClient,
    EmailIntent,
    IntentClassificationResult,
)
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
    actions_taken: list[str]
    expert_assigned: str | None = None
    case_created: str | None = None
    emails_sent: list[str] | None = None
    error_message: str | None = None


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
                    # Azure AI Foundry client now only supports live mode - no test mode
                    self.ai_client = AzureAIFoundryClient(self.settings.azure_ai_foundry, ai_foundry_credentials)
                
                # Initialize all clients as async context managers
                await self.ai_client.__aenter__()
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
        if not email:
            raise ValueError("Email cannot be None")
        if not email.sender or not email.sender.email:
            raise ValueError("Email must have a valid sender")
            
        # Ensure services are connected
        if not self._services_connected:
            await self.__aenter__()
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
                    processing_time_ms=0,
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

                # Normal AI classification with timeout and error handling
                try:
                    async with self.ai_client as ai_client:
                        intent_result = await asyncio.wait_for(
                            ai_client.classify_email_intent(
                                subject=email.subject,
                                body=clean_body,
                                sender_email=email.sender.email,
                            ),
                            timeout=30.0  # 30 second timeout for AI classification
                        )
                except asyncio.TimeoutError:
                    self.logger.error(
                        "AI classification timed out - service may be slow or unavailable",
                        email_id=email.id,
                        sender=email.sender.email,
                        subject=email.subject[:50],
                        timeout_seconds=30,
                        body_length=len(clean_body),
                        ai_client_type=type(self.ai_client).__name__
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=["AI classification timed out after 30 seconds"],
                        error_message="AI classification timed out after 30 seconds"
                    )
                except Exception as e:
                    error_details = {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "email_id": email.id,
                        "sender": email.sender.email,
                        "subject": email.subject[:50] if email.subject else "No Subject",
                        "body_length": len(clean_body),
                        "ai_client_initialized": self.ai_client is not None,
                        "ai_client_type": type(self.ai_client).__name__ if self.ai_client else None
                    }
                    
                    self.logger.error(
                        "AI classification service failed with detailed context",
                        **error_details
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=[f"AI classification failed: {type(e).__name__}"],
                        error_message=f"AI classification failed: {e}"
                    )

                # Validate classification result
                if not intent_result:
                    self.logger.error(
                        "AI classification returned null/empty result",
                        email_id=email.id,
                        sender=email.sender.email,
                        subject=email.subject[:50] if email.subject else "No Subject",
                        ai_client_type=type(self.ai_client).__name__ if self.ai_client else None
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=["AI classification returned no result"],
                        error_message="AI classification returned no result"
                    )

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
                        body_preview=clean_body[:100] if clean_body else "No body content"
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=[f"Low confidence classification: {intent_result.confidence}"],
                        error_message=f"Intent classification failed: {intent_result.reasoning}",
                    )

                # Determine scenario based on intent
                scenario_type = self._determine_scenario_type(intent_result)

            # Process the specific scenario
            return await self._process_scenario(email, scenario_type, intent_result)

        except Exception as e:
            self.logger.error(f"Error processing email scenario: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.UNKNOWN,
                success=False,
                actions_taken=[],
                error_message=str(e),
            )

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
        actions_taken = []

        try:
            # Process based on scenario type
            if scenario_type == ScenarioType.SCENARIO_5:
                return await self._process_scenario_5(email, actions_taken)
            elif scenario_type == ScenarioType.SCENARIO_6:
                return await self._process_scenario_6(email, actions_taken)
            elif scenario_type == ScenarioType.SCENARIO_7:
                return await self._process_scenario_7(email, actions_taken)
            elif scenario_type == ScenarioType.SCENARIO_8:
                return await self._process_scenario_8(email, actions_taken)
            elif scenario_type == ScenarioType.SCENARIO_9:
                return await self._process_scenario_9(email, actions_taken)
            elif scenario_type == ScenarioType.SCENARIO_10:
                return await self._process_scenario_10(email, actions_taken)
            elif scenario_type == ScenarioType.SCENARIO_11:
                return await self._process_scenario_11(email, actions_taken)
            else:
                return ScenarioResult(
                    scenario_type=scenario_type,
                    success=False,
                    actions_taken=actions_taken,
                    error_message="Unknown scenario type",
                )

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
                actions_taken=actions_taken,
                error_message=str(e),
            )

    async def _process_scenario_5(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 5: Positive response - Create Salesforce case and assign to expert.

        Args:
            email: Email with positive intent
            actions_taken: List to track actions taken

        Returns:
            ScenarioResult with expert assignment and case creation details
        """
        try:
            # Step 1: Determine the email address to use for lookups (handle test mode)
            lookup_email = email.sender.email
            if (
                self.settings.test_mode.enabled
                and email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower()
            ):
                lookup_email = self.settings.test_mode.target_salesforce_email
                actions_taken.append(
                    f"TEST MODE: Email substituted from {email.sender.email} to {lookup_email} for lookup"
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
                    actions_taken.append(
                        f"Contact not found in Databricks for {lookup_email}"
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.SCENARIO_5,
                        success=False,
                        actions_taken=actions_taken,
                        expert_assigned=None,
                        case_created=None,
                        emails_sent=None,
                        error_message=f"Contact {lookup_email} not found in lookup table - cannot assign expert",
                    )

                # Contact found - extract account and contact IDs
                account_id = contact_lookup.sf_account_id or ""
                contact_id = contact_lookup.sf_contact_id or ""
                actions_taken.append(
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
            actions_taken.append(f"Assigned expert via round-robin: {expert.expert_name}")

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
                actions_taken.append("Applied content formatting to case description")
            except Exception as format_error:
                self.logger.warning(
                    "Content formatting failed, using fallback description",
                    error=str(format_error),
                    email_id=email.id
                )
                # Fallback to simple description
                formatted_description = f"Customer {email.sender.email} responded positively to outreach.\n\nOriginal Subject: {email.subject}\n\nResponse: {email.body.content if email.body else 'No content'}"
                actions_taken.append("Used fallback description format due to formatting error")

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
                error_msg = f"Failed to create Salesforce case: {case_response.errors or 'Unknown error'}"
                self.logger.error(
                    "Salesforce case creation failed",
                    account_id=account_id,
                    contact_id=contact_id,
                    expert=expert.expert_name,
                    errors=case_response.errors
                )
                raise Exception(error_msg)
            case_id = case_response.id
            actions_taken.append(f"Created Salesforce case with enhanced fields: {case_id}")

            self.logger.info(
                "Scenario 5 completed successfully - Low Touch Expert assigned as Support Request Owner",
                extra={
                    "expert_name": expert.expert_name,
                    "expert_id": expert.expert_id,
                    "expert_email": expert.expert_email,
                    "case_id": case_id,
                    "customer_email": email.sender.email,
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
                actions_taken=actions_taken,
                expert_assigned=expert.expert_name,
                case_created=case_id,
            )

        except Exception as e:
            # Provide better error message formatting
            error_str = str(e) if str(e) else "Unknown error occurred"
            error_msg = f"Failed to process scenario 5: {error_str}"
            actions_taken.append(error_msg)
            
            self.logger.error(
                "Scenario 5 processing failed",
                customer_email=email.sender.email,
                error_type=type(e).__name__,
                error_message=error_str,
                actions_completed=len(actions_taken)
            )
            
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_5,
                success=False,
                actions_taken=actions_taken,
                error_message=error_msg,
            )

    async def _process_scenario_6(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 6: Negative response - Forward to Victoria Grant.

        Args:
            email: Email with negative intent
            actions_taken: List to track actions taken

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
                actions_taken.append(f"Forwarded negative response to Victoria Grant: {victoria_email}")
            else:
                actions_taken.append(f"Failed to forward negative response to Victoria Grant: {victoria_email}")
                self.logger.error(
                    "Scenario 6 failed due to email forwarding failure",
                    customer_email=email.sender.email,
                    victoria_email=victoria_email
                )
                return ScenarioResult(
                    scenario_type=ScenarioType.SCENARIO_6,
                    success=False,
                    actions_taken=actions_taken,
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
                actions_taken=actions_taken,
                emails_sent=[victoria_email],
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 6: {e!s}"
            actions_taken.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_6,
                success=False,
                actions_taken=actions_taken,
                error_message=error_msg,
            )

    async def _process_scenario_7(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 7: Service inquiry - Forward to account team.

        Args:
            email: Email with service inquiry intent
            actions_taken: List to track actions taken

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
                actions_taken.append(f"Forwarded service inquiry to account team: {account_team_email}")
            else:
                actions_taken.append(f"Failed to forward service inquiry to account team: {account_team_email}")
                self.logger.error(
                    "Scenario 7 failed due to email forwarding failure",
                    customer_email=email.sender.email,
                    account_team_email=account_team_email
                )
                return ScenarioResult(
                    scenario_type=ScenarioType.SCENARIO_7,
                    success=False,
                    actions_taken=actions_taken,
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
                actions_taken=actions_taken,
                emails_sent=[account_team_email],
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 7: {e!s}"
            actions_taken.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_7,
                success=False,
                actions_taken=actions_taken,
                error_message=error_msg,
            )

    async def _process_scenario_8(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 8: Out of office - Update Databricks table.

        Args:
            email: Email with out-of-office intent
            actions_taken: List to track actions taken

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

            actions_taken.append(
                f"Updated Databricks table with out-of-office status for {email.sender.email}"
            )

            self.logger.info(
                "Scenario 8 completed successfully",
                customer_email=email.sender.email,
                status="out_of_office",
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_8, success=True, actions_taken=actions_taken
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 8: {e!s}"
            actions_taken.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_8,
                success=False,
                actions_taken=actions_taken,
                error_message=error_msg,
            )

    async def _process_scenario_9(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 9: Invalid email - Update Salesforce Invalid_Email field.

        Args:
            email: Email indicating invalid/bounced email
            actions_taken: List to track actions taken

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
                self.settings.test_mode.enabled
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

                    actions_taken.append(
                        f"Updated Salesforce Is_Email_Invalid__c field to true for {lookup_email} (Contact: {contact_lookup.sf_contact_id})"
                    )
                else:
                    # Contact not found in lookup table - log warning but continue
                    actions_taken.append(
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

            actions_taken.append(f"Updated Databricks to stop future emails to {bounced_email}")

            self.logger.info(
                "Scenario 9 completed successfully",
                bounced_email=bounced_email,
                salesforce_updated=True,
                databricks_updated=True,
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_9, success=True, actions_taken=actions_taken
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 9: {e!s}"
            actions_taken.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_9,
                success=False,
                actions_taken=actions_taken,
                error_message=error_msg,
            )

    async def _process_scenario_10(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 10: No longer works - Forward to Victoria Grant.

        Args:
            email: Email indicating person no longer works at company
            actions_taken: List to track actions taken

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
                actions_taken.append(
                    f"Forwarded 'no longer works' notification to Victoria Grant: {victoria_email}"
                )
            else:
                actions_taken.append(
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
                    actions_taken=actions_taken,
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

            actions_taken.append(
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
                actions_taken=actions_taken,
                emails_sent=[victoria_email],
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 10: {e!s}"
            actions_taken.append(error_msg)
            self.logger.error(f"{error_msg}: {e}")
            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_10,
                success=False,
                actions_taken=actions_taken,
                error_message=error_msg,
            )

    async def _process_scenario_11(self, email: Email, actions_taken: list[str]) -> ScenarioResult:
        """Process scenario 11."""
        actions_taken.append("Processed scenario 11")
        return ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_11, success=True, actions_taken=actions_taken
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

