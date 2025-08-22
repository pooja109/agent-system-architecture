"""
Response Handler Service
========================

Service for handling email responses, including scenario processing and logging.
Simplified version without scheduling dependencies.

This service provides:
- Email response processing
- Scenario classification integration
- Comprehensive error handling
- Structured logging
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

# Simplified imports without sys.path manipulation

from config.settings import AppSettings
from services.scenario_processor import ScenarioProcessor
from services.logging.business_logic_logger import BusinessLogicLoggerMixin


class CustomerLookupError(Exception):
    """Exception raised when customer lookup fails."""

    pass


class ResponseHandlerError(Exception):
    """Exception raised when response handler operations fail."""

    pass


class SchedulingAPIError(Exception):
    """Exception raised when scheduling API operations fail."""
    
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class ResponseHandler(BusinessLogicLoggerMixin):
    """
    Simplified response handler for processing email responses.

    Handles email scenario processing and provides comprehensive logging.
    No longer dependent on scheduling service.
    """

    def __init__(
        self,
        settings: AppSettings,
        scenario_processor: ScenarioProcessor,
    ) -> None:
        """Initialize response handler.

        Args:
            settings: Application settings
            scenario_processor: Scenario processor for handling email scenarios

        Raises:
            ValueError: If required settings are missing
        """
        if not settings:
            raise ValueError("AppSettings instance is required")
        if not scenario_processor:
            raise ValueError("ScenarioProcessor instance is required")

        # Initialize logging mixin
        self.__init_logging__("response_handler")

        self.settings = settings
        self.scenario_processor = scenario_processor
        self.logger = structlog.get_logger(__name__)

        self.log_user_message("ResponseHandler initialized", "info")

    async def process_customer_response(self, email_message: dict[str, Any], scenario: int) -> None:
        """
        Process customer response by forwarding to scenario processor.

        Args:
            email_message: Email message from Graph API
            scenario: Scenario number (5-11) from classification

        Raises:
            ResponseHandlerError: If processing fails
            ValueError: If email_message is invalid
        """
        if not email_message:
            raise ValueError("email_message cannot be empty")
        if not isinstance(scenario, int) or scenario < 5 or scenario > 11:
            raise ValueError("scenario must be an integer between 5 and 11")

        try:
            # Extract customer information from email
            from_field = email_message.get("from") or {}
            sender_info = from_field.get("emailAddress", {}) if from_field else {}
            sender_email = sender_info.get("address") if sender_info else None
            conversation_id = email_message.get("conversationId")
            received_time = email_message.get("receivedDateTime")

            if not sender_email:
                raise ValueError("No sender email found in response")

            self.logger.info(
                "Processing customer response",
                sender_email=sender_email,
                scenario=scenario,
                conversation_id=conversation_id,
                received_time=received_time,
            )

            # Log the response for tracking purposes
            await self._log_response(
                sender_email=sender_email,
                conversation_id=conversation_id,
                scenario=scenario,
                received_time=received_time,
            )

            # Process through scenario processor
            await self.scenario_processor.process_scenario(email_message, scenario)

            self.logger.info(
                "Customer response processed successfully",
                sender_email=sender_email,
                scenario=scenario,
            )

        except (ResponseHandlerError, ValueError) as e:
            # Re-raise known exceptions
            self.logger.error(
                "Error processing customer response",
                error=str(e),
                error_type=type(e).__name__,
                scenario=scenario,
                sender_email=self._safe_get_sender_email(email_message),
            )
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            self.logger.error(
                "Unexpected error processing customer response",
                error=str(e),
                error_type=type(e).__name__,
                scenario=scenario,
            )
            raise ResponseHandlerError(f"Unexpected error processing customer response: {e}") from e

    def _safe_get_sender_email(self, email_message: dict) -> str | None:
        """Safely extract sender email from email message.
        
        Args:
            email_message: Email message from Graph API
            
        Returns:
            Sender email address or None if not found
        """
        try:
            from_field = email_message.get("from")
            if not from_field:
                return None
            
            sender_info = from_field.get("emailAddress") if from_field else None
            if not sender_info:
                return None
                
            return sender_info.get("address")
        except (AttributeError, TypeError):
            return None

    async def _log_response(
        self,
        sender_email: str,
        conversation_id: str | None,
        scenario: int,
        received_time: str | None,
    ) -> None:
        """
        Log the response for tracking purposes.

        Args:
            sender_email: Email address of the sender
            conversation_id: Conversation ID from email
            scenario: Response scenario number
            received_time: When the response was received

        Raises:
            ValueError: If required parameters are missing
        """
        if not sender_email:
            raise ValueError("sender_email cannot be empty")
        if not isinstance(scenario, int):
            raise ValueError("scenario must be an integer")

        response_id = str(uuid4())

        try:
            # Parse received_time to datetime for structured logging
            received_datetime = datetime.now(timezone.utc)
            if received_time:
                try:
                    # Try parsing ISO format from Graph API
                    if isinstance(received_time, str):
                        # Remove 'Z' and parse
                        received_time_clean = received_time.replace("Z", "+00:00")
                        received_datetime = datetime.fromisoformat(
                            received_time_clean.replace("+00:00", "")
                        )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse received_time: {e}, using current time"
                    )

            # Log the response for tracking and auditing
            self.logger.info(
                "Customer response logged",
                response_id=response_id,
                sender_email=sender_email,
                scenario=scenario,
                conversation_id=conversation_id,
                received_time=received_time,
                received_datetime=received_datetime.isoformat(),
                processed_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to log response", 
                error=str(e), 
                sender_email=sender_email, 
                scenario=scenario
            )
            # Don't raise here as logging failure shouldn't stop processing
