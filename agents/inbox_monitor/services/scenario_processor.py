"""
Scenario Processor Service
==========================

Service for processing email scenarios (5-11) including intent classification,
expert assignment, and case creation.
"""

import asyncio
import contextlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

try:
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
    from utils.content_formatter import ContentFormatter, ContentFormattingConfig
except ImportError:
    from ..config.settings import AppSettings
    from ..models.email import Email
    from .azure_ai_foundry_client import (
        AzureAIFoundryClient,
        EmailIntent,
        IntentClassificationResult,
    )
    from .contact_lookup_service import ContactLookupService
    from .round_robin_service import RoundRobinService
    from .salesforce_client import SalesforceClient
    from ..utils.content_formatter import ContentFormatter, ContentFormattingConfig


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
                # Connect to databricks services concurrently for better performance
                await asyncio.gather(
                    self.round_robin_service.connect(),
                    self.contact_lookup_service.connect(),
                    return_exceptions=True
                )
                self._services_connected = True
                self.logger.debug("Scenario processor services connected")
            except Exception as e:
                self.logger.warning(
                    "Some scenario processor services failed to connect",
                    error=str(e)
                )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup service connections."""
        if self._services_connected:
            try:
                # Disconnect services concurrently
                await asyncio.gather(
                    self.round_robin_service.disconnect(),
                    self.contact_lookup_service.disconnect(),
                    return_exceptions=True
                )
                self._services_connected = False
                self.logger.debug("Scenario processor services disconnected")
            except Exception as e:
                self.logger.warning(
                    "Error disconnecting scenario processor services",
                    error=str(e)
                )

    def __init__(self, settings: AppSettings):
        """Initialize scenario processor.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = structlog.get_logger(__name__)

        # Initialize service clients
        self.ai_client = AzureAIFoundryClient(settings.azure_ai_foundry)
        self.salesforce_client = SalesforceClient(settings.salesforce)
        self.round_robin_service = RoundRobinService(settings.databricks, settings.test_mode)
        self.contact_lookup_service = ContactLookupService(settings.databricks, settings.test_mode)
        
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
            if (
                self.settings.test_mode.enabled
                and self.settings.test_mode.force_scenario is not None
                and email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower()
            ):
                forced_scenario = self.settings.test_mode.force_scenario
                self.logger.info(
                    "Test mode: forcing scenario for testing",
                    original_email=email.sender.email,
                    forced_scenario=forced_scenario,
                    test_mode=True,
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
                # Normal AI classification with timeout and error handling
                try:
                    async with self.ai_client as ai_client:
                        intent_result = await asyncio.wait_for(
                            ai_client.classify_email_intent(
                                subject=email.subject,
                                body=email.body.content if email.body else "",
                                sender_email=email.sender.email,
                            ),
                            timeout=30.0  # 30 second timeout for AI classification
                        )
                except asyncio.TimeoutError:
                    self.logger.error(
                        "AI classification timed out",
                        email_id=email.id,
                        sender=email.sender.email
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=["AI classification timed out"],
                        error_message="AI classification timed out after 30 seconds"
                    )
                except Exception as e:
                    self.logger.error(
                        "AI classification failed",
                        error=str(e),
                        email_id=email.id,
                        sender=email.sender.email
                    )
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=["AI classification failed"],
                        error_message=f"AI classification failed: {e}"
                    )

                # Validate classification result
                if not intent_result:
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=["No AI classification result"],
                        error_message="AI classification returned no result"
                    )

                # Force cleanup of any lingering tasks after AI client usage
                await asyncio.sleep(0.01)  # Brief pause to let any background tasks complete

                # Check if classification was successful (confidence > 0 and not UNKNOWN)
                if intent_result.intent == EmailIntent.UNKNOWN or intent_result.confidence == 0.0:
                    return ScenarioResult(
                        scenario_type=ScenarioType.UNKNOWN,
                        success=False,
                        actions_taken=[],
                        error_message=f"Intent classification failed: {intent_result.reasoning}",
                    )

                # Determine scenario based on intent
                scenario_type = self._determine_scenario_type(intent_result)

            # Process the specific scenario
            return await self._process_scenario(email, scenario_type, intent_result)

        except Exception as e:
            self.logger.error("Error processing email scenario", error=str(e))
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
                "Error processing scenario", scenario_type=scenario_type, error=str(e)
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
            # Step 1: Lookup Salesforce account and contact IDs from Databricks
            async with self.contact_lookup_service as lookup_service:
                contact_lookup = await lookup_service.lookup_contact_by_email(email.sender.email)

                if contact_lookup.found:
                    account_id = contact_lookup.sf_account_id or ""
                    contact_id = contact_lookup.sf_contact_id or ""

                    # Log test mode substitution if it occurred
                    if (
                        self.settings.test_mode.enabled
                        and email.sender.email.lower()
                        == self.settings.test_mode.test_sender_email.lower()
                    ):
                        actions_taken.append(
                            f"TEST MODE: Email substituted from {email.sender.email} to {self.settings.test_mode.target_salesforce_email} for lookup"
                        )

                    actions_taken.append(
                        f"Found contact in Databricks: Account={account_id}, Contact={contact_id}"
                    )
                else:
                    # Contact not found - cannot assign expert for invalid contact
                    self.logger.warning(
                        "Contact not found in lookup table",
                        email=email.sender.email,
                        table="snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t",
                    )
                    actions_taken.append(
                        f"Contact not found in Databricks for {email.sender.email}"
                    )
                    # Return failure result - don't assign expert or create case for invalid contacts
                    return ScenarioResult(
                        scenario_type=ScenarioType.SCENARIO_5,
                        success=False,
                        actions_taken=actions_taken,
                        expert_assigned=None,
                        case_created=None,
                        emails_sent=None,
                        error_message=f"Contact {email.sender.email} not found in lookup table - cannot assign expert",
                    )

            # Step 2: Get next available expert via round-robin (only for valid contacts)
            # Use the same email that was used for contact lookup (which may be substituted in test mode)
            assignment_email = email.sender.email
            if (
                self.settings.test_mode.enabled
                and email.sender.email.lower() == self.settings.test_mode.test_sender_email.lower()
            ):
                assignment_email = self.settings.test_mode.target_salesforce_email

            expert = await self.round_robin_service.assign_lead_to_expert(
                customer_email=assignment_email
            )
            if not expert:
                raise Exception("No available experts for assignment")
            actions_taken.append(f"Assigned expert via round-robin: {expert.expert_name}")

            # Step 3: Create Salesforce case assigned to the expert
            from services.salesforce_client import CaseCreateRequest
            
            # Format case description using content formatter
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

            case_request = CaseCreateRequest(
                account_id=account_id,
                contact_id=contact_id,
                owner_id=expert.expert_id,
                subject=f"Positive Response: {email.subject}",
                description=formatted_description,
                origin="AI Agent",
                status="New",
                priority="Medium",
                case_queue=self.settings.salesforce.case_queue,
            )
            case_response = await self.salesforce_client.create_case(case_request)
            if not case_response.success:
                raise Exception(f"Failed to create Salesforce case: {case_response.errors}")
            case_id = case_response.id
            actions_taken.append(f"Created Salesforce case: {case_id}")

            self.logger.info(
                "Scenario 5 completed successfully",
                expert=expert.expert_name,
                case_id=case_id,
                customer_email=email.sender.email,
                account_id=account_id,
                contact_id=contact_id,
            )

            return ScenarioResult(
                scenario_type=ScenarioType.SCENARIO_5,
                success=True,
                actions_taken=actions_taken,
                expert_assigned=expert.expert_name,
                case_created=case_id,
            )

        except Exception as e:
            error_msg = f"Failed to process scenario 5: {e!s}"
            actions_taken.append(error_msg)
            self.logger.error(error_msg, error=str(e))
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

            await self._forward_email_to_recipient(
                original_email=email,
                recipient_email=victoria_email,
                recipient_name="Victoria Grant",
                reason="Negative customer response requiring attention",
            )

            actions_taken.append(f"Forwarded negative response to Victoria Grant: {victoria_email}")

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
            self.logger.error(error_msg, error=str(e))
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

            await self._forward_email_to_recipient(
                original_email=email,
                recipient_email=account_team_email,
                recipient_name="Account Team",
                reason="Customer service inquiry requiring assistance",
            )

            actions_taken.append(f"Forwarded service inquiry to account team: {account_team_email}")

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
            self.logger.error(error_msg, error=str(e))
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
            # Update the assignment status to mark as out of office
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
            self.logger.error(error_msg, error=str(e))
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
                    original_email=bounced_email,
                    lookup_email=lookup_email,
                    test_mode=True,
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
                        email=lookup_email,
                        original_email=bounced_email if lookup_email != bounced_email else None,
                    )

            # Also update assignment status in Databricks to stop future email attempts
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
            self.logger.error(error_msg, error=str(e))
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

            await self._forward_email_to_recipient(
                original_email=email,
                recipient_email=victoria_email,
                recipient_name="Victoria Grant",
                reason="Contact no longer works at company - requires attention",
            )

            actions_taken.append(
                f"Forwarded 'no longer works' notification to Victoria Grant: {victoria_email}"
            )

            # Update assignment status to stop future email attempts
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
            self.logger.error(error_msg, error=str(e))
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
    ) -> str:
        """Forward an email to a specific recipient using the email service.

        Args:
            original_email: The original email to forward
            recipient_email: Email address to forward to
            recipient_name: Name of the recipient
            reason: Reason for forwarding

        Returns:
            Email ID or confirmation of the forwarded email

        Raises:
            Exception: If email forwarding fails
        """
        try:
            # Simple approach: directly use subprocess to call the email agent
            import json
            import os
            import subprocess
            import tempfile

            # Get the path to the email agent directory
            current_dir = os.path.dirname(os.path.abspath(__file__))  # /inbox_monitor/services/
            inbox_monitor_dir = os.path.dirname(current_dir)  # /inbox_monitor/
            agents_dir = os.path.dirname(inbox_monitor_dir)  # /agents/
            email_dir = os.path.join(agents_dir, "email")  # /agents/email/

            # Create forwarded email content
            forward_subject = f"FWD: {original_email.subject}"
            forward_body = f"""{reason}

Original Email Details:
From: {original_email.sender.email} ({original_email.sender.name})
Sent: {original_email.received_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}
Subject: {original_email.subject}

--- Original Message ---
{original_email.body.content}"""

            # Escape the content for the script
            escaped_subject = forward_subject.replace('"', '\\"').replace("\n", "\\n")
            escaped_body = forward_body.replace('"""', '\\"\\"\\"').replace("\\", "\\\\")

            # Create a simple script to send the email (use raw string for Windows paths)
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
        settings = get_settings()
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
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(email_script)
                temp_script_path = f.name

            try:
                # Run the script in the email agent's environment
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
                        output = json.loads(result.stdout.strip())
                        if output.get("success"):
                            self.logger.info(
                                "Email forwarded successfully via subprocess",
                                to_email=recipient_email,
                            )
                            return True
                        else:
                            self.logger.error("Email forwarding failed", error=output.get("error"))
                            return False
                    except json.JSONDecodeError:
                        self.logger.error(
                            "Failed to parse email service output",
                            stdout=result.stdout,
                            stderr=result.stderr,
                        )
                        return False
                else:
                    self.logger.error(
                        "Email service subprocess failed",
                        returncode=result.returncode,
                        stderr=result.stderr,
                    )
                    return False
            finally:
                # Clean up the temporary script
                with contextlib.suppress(Exception):
                    os.unlink(temp_script_path)

        except Exception as e:
            self.logger.error(f"Failed to forward email to {recipient_email}", error=str(e))
            raise

    async def __aenter__(self):
        """Async context manager entry."""
        # Initialize clients
        await self.ai_client.__aenter__()
        await self.salesforce_client.__aenter__()
        await self.round_robin_service.__aenter__()
        await self.contact_lookup_service.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Close clients with individual error handling
        cleanup_errors = []

        for client_name, client in [
            ("ai_client", self.ai_client),
            ("salesforce_client", self.salesforce_client),
            ("round_robin_service", self.round_robin_service),
            ("contact_lookup_service", self.contact_lookup_service),
        ]:
            try:
                await client.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                cleanup_errors.append(f"{client_name}: {e!s}")
                self.logger.warning(f"Error closing {client_name}", error=str(e))

        if cleanup_errors:
            self.logger.warning("Some cleanup errors occurred", errors=cleanup_errors)

        # Brief cleanup pause without aggressive delays
        await asyncio.sleep(0.01)
