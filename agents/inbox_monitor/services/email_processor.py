"""
Email Processor Service
=======================

Service for processing emails from the inbox, including retrieval,
storage, and folder management.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import structlog

try:
    # Try absolute imports first (for direct script execution)
    from config.settings import AppSettings
    from models.email import Email, ProcessingResult
    from services.graph_api_client import GraphAPIClient
    from services.response_handler import ResponseHandler
    from services.scenario_processor import ScenarioProcessor

    from utils.retry import retry_operation
except ImportError:
    # Fall back to relative imports (for module execution)
    from ..config.settings import AppSettings
    from ..models.email import Email, ProcessingResult
    from ..utils.retry import retry_operation
    from .graph_api_client import GraphAPIClient
    from .response_handler import ResponseHandler
    from .scenario_processor import ScenarioProcessor


class EmailProcessor:
    """Process emails from inbox and manage their lifecycle."""

    def __init__(self, settings: AppSettings, graph_client: GraphAPIClient):
        """Initialize email processor.

        Args:
            settings: Application settings
            graph_client: Graph API client instance
        """
        self.settings = settings
        self.graph_client = graph_client
        self.logger = structlog.get_logger(__name__)
        self.version = "2.1.0"  # Updated version for response integration

        # Initialize scenario processor
        self.scenario_processor = ScenarioProcessor(settings)

        # Initialize response handler
        self.response_handler = ResponseHandler(
            settings=settings,
            scenario_processor=self.scenario_processor,
        )

        # Ensure output directory exists if using file storage
        if self.settings.output.storage_type == "file":
            Path(self.settings.output.output_directory).mkdir(parents=True, exist_ok=True)

    async def process_inbox(self) -> dict[str, Any]:
        """Process emails from the inbox.

        Returns:
            Dictionary with processing results
        """
        start_time = datetime.utcnow()
        results: dict[str, Any] = {
            "success": True,
            "processed_count": 0,
            "failed_count": 0,
            "errors": [],
            "processing_results": [],
        }

        try:
            # Get emails from inbox
            messages = await self.graph_client.get_inbox_messages(
                limit=self.settings.processing.batch_size
            )

            if not messages:
                self.logger.info("No new messages in inbox")
                return results

            self.logger.info(f"Processing {len(messages)} emails from inbox", count=len(messages))

            # Get or create processed folder
            folder_name = self._get_processed_folder_name()
            folder = await self._ensure_processed_folder(folder_name)

            if not folder:
                error_msg = f"Failed to create/get processed folder: {folder_name}"
                self.logger.error(error_msg)
                results["success"] = False
                results["errors"].append(error_msg)
                return results

            # Process each email
            for message in messages:
                result = await self._process_single_email(message, folder["id"], folder_name)

                results["processing_results"].append(result)

                if result.success:
                    results["processed_count"] += 1
                else:
                    results["failed_count"] += 1
                    results["errors"].append(f"Email {result.email_id}: {result.error}")

            # Set overall success based on any failures
            if results["failed_count"] > 0:
                results["success"] = False

        except Exception as e:
            self.logger.error("Error processing inbox", error=str(e))
            results["success"] = False
            results["errors"].append(str(e))

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        results["processing_time_seconds"] = processing_time

        self.logger.info(
            "Inbox processing completed",
            processed=results["processed_count"],
            failed=results["failed_count"],
            time_seconds=processing_time,
        )

        return results

    async def _process_single_email(
        self, message: dict[str, Any], folder_id: str, folder_name: str
    ) -> ProcessingResult:
        """Process a single email.

        Args:
            message: Email message from Graph API
            folder_id: ID of the processed folder
            folder_name: Name of the processed folder

        Returns:
            ProcessingResult instance
        """
        start_time = datetime.utcnow()
        processing_id = str(uuid.uuid4())
        email_id = message["id"]

        try:
            self.logger.info(
                "Processing email",
                email_id=email_id,
                subject=message.get("subject", ""),
            )

            # Convert to Email model
            email = self.graph_client.convert_to_email_model(message, processing_id, self.version)

            # Store the email
            output_location = await self._store_email(email)

            # Process email through scenarios
            async with self.scenario_processor:
                scenario_result = await self.scenario_processor.process_email_scenario(email)

                # If this is a customer response scenario (5-11), handle response processing
                if scenario_result and scenario_result.scenario_type.value.startswith("scenario_"):
                    scenario_num = self._extract_scenario_number(
                        scenario_result.scenario_type.value
                    )
                    if scenario_num and 5 <= scenario_num <= 11:
                        try:
                            # Convert email back to message format for response handler
                            email_message = self._convert_email_to_message(message, email)
                            await self.response_handler.process_customer_response(
                                email_message=email_message, scenario=scenario_num
                            )
                        except Exception as e:
                            self.logger.error(
                                "Failed to process customer response",
                                error=str(e),
                                email_id=email_id,
                                scenario=scenario_num,
                            )
                            # Don't fail the entire email processing due to response handling errors

            # Move email to processed folder (unless in dry-run mode)
            if not self.settings.dry_run:
                success, _, error = await retry_operation(
                    self.graph_client.move_message,
                    "Move email to processed folder",
                    self.settings.processing.max_retry_attempts,
                    self.settings.processing.retry_delay_seconds,
                    email_id,
                    folder_id,
                )

                if not success:
                    raise Exception(f"Failed to move email: {error}")
            else:
                self.logger.info(
                    "Dry-run mode: Email would be moved to folder",
                    email_id=email_id,
                    folder=folder_name,
                )

            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            return ProcessingResult(
                success=True,
                email_id=email_id,
                processing_id=processing_id,
                error=None,
                moved_to_folder=folder_name if not self.settings.dry_run else None,
                output_location=output_location,
                processing_time_ms=processing_time_ms,
                scenario_type=scenario_result.scenario_type.value if scenario_result else None,
                scenario_success=scenario_result.success if scenario_result else None,
                actions_taken=scenario_result.actions_taken if scenario_result else [],
                expert_assigned=scenario_result.expert_assigned if scenario_result else None,
                case_created=scenario_result.case_created if scenario_result else None,
                emails_sent=scenario_result.emails_sent
                if scenario_result and scenario_result.emails_sent
                else [],
            )

        except Exception as e:
            self.logger.error("Failed to process email", email_id=email_id, error=str(e))

            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            return ProcessingResult(
                success=False,
                email_id=email_id,
                processing_id=processing_id,
                error=str(e),
                moved_to_folder=None,
                output_location=None,
                processing_time_ms=processing_time_ms,
                scenario_type=None,
                scenario_success=False,
                actions_taken=[],
                expert_assigned=None,
                case_created=None,
                emails_sent=[],
            )

    async def _store_email(self, email: Email) -> str:
        """Store the processed email based on output configuration.

        Args:
            email: Email model to store

        Returns:
            Storage location/identifier

        Raises:
            Exception: If storage fails
        """
        if self.settings.output.storage_type == "file":
            return await self._store_email_file(email)
        elif self.settings.output.storage_type == "api":
            return await self._store_email_api(email)
        else:
            raise ValueError(f"Unsupported storage type: {self.settings.output.storage_type}")

    async def _store_email_file(self, email: Email) -> str:
        """Store email as JSON file.

        Args:
            email: Email to store

        Returns:
            File path where email was stored
        """
        filename = f"email_{email.processing_metadata.processing_id}.json"
        filepath = Path(self.settings.output.output_directory) / filename

        # Convert to AI format and save
        email_data = email.to_ai_format()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(email_data, f, indent=2, ensure_ascii=False)

        self.logger.info("Email stored to file", filepath=str(filepath), email_id=email.id)

        return str(filepath)

    async def _store_email_api(self, email: Email) -> str:
        """Store email via API call.

        Args:
            email: Email to store

        Returns:
            API response identifier

        Raises:
            Exception: If API call fails
        """
        if not self.settings.output.api_endpoint:
            raise ValueError("API endpoint not configured")

        # Convert to AI format
        email_data = email.to_ai_format()

        headers = {"Content-Type": "application/json"}

        if self.settings.output.api_key:
            headers["Authorization"] = f"Bearer {self.settings.output.api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.settings.output.api_endpoint, json=email_data, headers=headers
            )
            if response.status_code >= 400:
                response_text = response.text
                raise Exception(f"API request failed: {response.status_code} - {response_text}")

            result = response.json()

            self.logger.info(
                "Email sent to API",
                email_id=email.id,
                response_id=result.get("id", "unknown"),
            )

            return result.get("id", email.processing_metadata.processing_id)

    def _get_processed_folder_name(self) -> str:
        """Get the name for the processed folder based on current date.

        Returns:
            Folder name like "Processed_01_2024"
        """
        now = datetime.utcnow()
        month = now.strftime("%m")
        year = now.strftime("%Y")

        return f"{self.settings.processing.processed_folder_prefix}_{month}_{year}"

    async def _ensure_processed_folder(self, folder_name: str) -> dict[str, Any] | None:
        """Ensure the processed folder exists.

        Args:
            folder_name: Name of the folder to create/get

        Returns:
            Folder information or None if failed
        """
        # First try to get existing folder
        folder = await self.graph_client.get_folder_by_name(folder_name)

        if folder and folder.get("id"):
            self.logger.info(
                "Using existing processed folder",
                folder_name=folder_name,
                folder_id=folder.get("id"),
            )
            return folder

        # Create new folder with retry
        self.logger.info("Creating new processed folder", folder_name=folder_name)

        success, folder_result, error = await retry_operation(
            self.graph_client.create_folder,
            "Create processed folder",
            max_attempts=self.settings.processing.max_retry_attempts,
            delay_seconds=self.settings.processing.retry_delay_seconds,
            folder_name=folder_name,
        )

        folder: dict[str, Any] = folder_result if folder_result else {}

        if success:
            return folder

        self.logger.error("Failed to create processed folder", folder_name=folder_name, error=error)
        return None

    def _extract_scenario_number(self, scenario_type: str) -> int | None:
        """
        Extract scenario number from scenario type string.

        Args:
            scenario_type: Scenario type like 'scenario_5'

        Returns:
            Integer scenario number or None if invalid
        """
        try:
            if scenario_type.startswith("scenario_"):
                return int(scenario_type.split("_")[1])
        except (IndexError, ValueError):
            pass
        return None

    def _convert_email_to_message(
        self, original_message: dict[str, Any], email: Email
    ) -> dict[str, Any]:
        """
        Convert email model back to message format for response handler.

        Args:
            original_message: Original message from Graph API
            email: Processed email model

        Returns:
            Dictionary in Graph API message format
        """
        # Use the original message as base and ensure required fields are present
        return {
            "id": original_message.get("id", email.message_id),
            "from": original_message.get("from", {}),
            "conversationId": original_message.get("conversationId"),
            "receivedDateTime": original_message.get(
                "receivedDateTime", email.received_time.isoformat() if email.received_time else None
            ),
            "subject": original_message.get("subject", email.subject),
            "body": original_message.get("body", {"content": email.body_preview or ""}),
            "sender": original_message.get("sender", {}),
        }
