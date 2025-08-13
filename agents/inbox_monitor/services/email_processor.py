"""
Email Processor Service
=======================

Service for processing emails from the inbox, including retrieval,
storage, and folder management.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

import importlib.util
from pathlib import Path

from config.settings import AppSettings
from models.email import Email, ProcessingResult
from services.graph_api_client import GraphAPIClient
from services.response_handler import ResponseHandler
from services.scenario_processor import ScenarioProcessor
from services.logging.business_logic_logger import BusinessLogicLoggerMixin

# Import retry utilities
try:
    from utils.retry import retry_operation
except ImportError:
    # Fallback to direct import if module structure is different
    current_dir = Path(__file__).parent.parent
    utils_retry_path = current_dir / "utils" / "retry.py"
    spec = importlib.util.spec_from_file_location("inbox_utils.retry", utils_retry_path)
    if spec and spec.loader:
        retry_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(retry_module)
        retry_operation = retry_module.retry_operation
    else:
        raise ImportError(f"Could not load retry utilities")


class EmailProcessor(BusinessLogicLoggerMixin):
    """Process emails from inbox and manage their lifecycle."""

    def __init__(self, settings: AppSettings, graph_client: GraphAPIClient, 
                 progress_manager=None):
        """Initialize email processor.

        Args:
            settings: Application settings
            graph_client: Graph API client instance
            progress_manager: Optional progress manager for UI integration
        """
        self.settings = settings
        self.graph_client = graph_client
        self.progress_manager = progress_manager
        
        # Keep existing logger for backward compatibility
        self.logger = structlog.get_logger(__name__)
        
        # Initialize logging mixin after setting existing logger
        self.__init_logging__("email_processor")
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
        start_time = datetime.now(timezone.utc)
        results: dict[str, Any] = {
            "success": True,
            "processed_count": 0,
            "failed_count": 0,
            "errors": [],
            "processing_results": [],
        }

        # Initialize progress tracking
        operation_id = None
        if self.progress_manager:
            from ui.progress.progress_manager import OperationType, ProgressType
            operation_id = self.progress_manager.create_operation(
                OperationType.EMAIL_PROCESSING,
                "Processing inbox emails",
                ProgressType.SPINNER
            )

        # Log operation start
        correlation_id = self.log_processing_start("inbox", "batch")

        try:
            # Get emails from inbox
            messages = await self.graph_client.get_inbox_messages(
                limit=self.settings.processing.batch_size
            )

            if not messages:
                self.log_user_message("No new messages in inbox", "info")
                self.log_processing_result(correlation_id, "inbox", "no_messages", {"count": 0})
                
                # Complete progress tracking
                if operation_id:
                    self.progress_manager.complete_operation(operation_id, "completed", "No new messages")
                
                return results

            self.log_user_message(f"🔄 Processing {len(messages)} emails from inbox", "info")
            self.log_diagnostic("Starting inbox processing", "info", count=len(messages), batch_size=self.settings.processing.batch_size)

            # Update progress tracking to show count and switch to bar
            if operation_id:
                self.progress_manager.update_operation(
                    operation_id,
                    status=f"Found {len(messages)} emails to process"
                )
                # Create a new bar progress operation for individual emails
                from ui.progress.progress_manager import ProgressType
                bar_operation_id = self.progress_manager.create_operation(
                    OperationType.EMAIL_PROCESSING,
                    f"Processing {len(messages)} emails",
                    ProgressType.BAR,
                    total=len(messages)
                )
            else:
                bar_operation_id = None

            # Get or create processed folder
            folder_name = self._get_processed_folder_name()
            folder = await self._ensure_processed_folder(folder_name)

            if not folder:
                error_msg = f"Failed to create/get processed folder: {folder_name}"
                self.log_operation_error("inbox", correlation_id, Exception(error_msg), folder_name=folder_name)
                results["success"] = False
                results["errors"].append(error_msg)
                return results

            # Initialize scenario processor once for the entire batch
            async with self.scenario_processor:
                # Process each email
                for i, message in enumerate(messages):
                    result = await self._process_single_email(message, folder["id"], folder_name)

                    results["processing_results"].append(result)

                    if result.success:
                        results["processed_count"] += 1
                    else:
                        results["failed_count"] += 1
                        results["errors"].append(f"Email {result.email_id}: {result.error}")

                    # Update progress for each processed email
                    if bar_operation_id:
                        self.progress_manager.update_operation(
                            bar_operation_id,
                            current=i + 1,
                            status=f"Processed {i + 1}/{len(messages)} emails"
                        )

            # Set overall success based on any failures
            if results["failed_count"] > 0:
                results["success"] = False

        except Exception as e:
            self.log_operation_error("inbox", correlation_id, e)
            results["success"] = False
            results["errors"].append(str(e))
            
            # Handle progress tracking on error
            if operation_id:
                self.progress_manager.fail_operation(operation_id, e, "Email processing failed")
            if 'bar_operation_id' in locals() and bar_operation_id:
                self.progress_manager.fail_operation(bar_operation_id, e, "Email batch processing failed")

        # Calculate processing time
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        results["processing_time_seconds"] = processing_time

        if results["success"]:
            self.log_user_message(f"✅ Inbox processing completed: {results['processed_count']} processed, {results['failed_count']} failed", "info")
            self.log_processing_result(
                correlation_id, 
                "inbox", 
                "completed", 
                {
                    "processed_count": results["processed_count"],
                    "failed_count": results["failed_count"],
                    "processing_time_seconds": processing_time
                }
            )
            
            # Complete progress tracking on success
            if operation_id:
                self.progress_manager.complete_operation(
                    operation_id, 
                    "completed", 
                    f"Processed {results['processed_count']} emails"
                )
            if 'bar_operation_id' in locals() and bar_operation_id:
                self.progress_manager.complete_operation(
                    bar_operation_id,
                    "completed", 
                    f"All {results['processed_count']} emails processed"
                )
        else:
            self.log_user_message(f"❌ Inbox processing failed: {results['failed_count']} errors", "error")
            
            # Handle partial failure progress tracking
            if operation_id:
                self.progress_manager.complete_operation(
                    operation_id, 
                    "failed" if results['processed_count'] == 0 else "partial", 
                    f"Processed {results['processed_count']}, failed {results['failed_count']}"
                )
            if 'bar_operation_id' in locals() and bar_operation_id:
                self.progress_manager.complete_operation(
                    bar_operation_id,
                    "failed" if results['processed_count'] == 0 else "partial",
                    f"Processed {results['processed_count']}/{len(messages)} emails"
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
        start_time = datetime.now(timezone.utc)
        processing_id = str(uuid.uuid4())
        email_id = message["id"]

        try:
            # Validate input message
            if not message or not isinstance(message, dict):
                raise ValueError("Invalid message format")
            if not message.get("id"):
                raise ValueError("Message ID is required")
                
            subject = message.get("subject", "(No Subject)")
            sender_info = self._safe_get_sender_email(message) or "unknown"
            
            # Log single email processing
            email_correlation_id = self.log_processing_start(
                "email", 
                email_id
            )
            self.log_diagnostic(
                "Processing single email",
                "info",
                email_id=email_id,
                subject=subject,
                sender=sender_info,
                processing_id=processing_id
            )

            # Convert to Email model with error handling
            try:
                email = self.graph_client.convert_to_email_model(message, processing_id, self.version)
                if not email:
                    raise ValueError("Failed to convert message to email model")
            except Exception as e:
                self.logger.error(
                    "Failed to convert message to email model",
                    extra={
                        "error": str(e),
                        "email_id": email_id,
                        "message_keys": list(message.keys()) if message else []
                    }
                )
                raise ValueError(f"Email model conversion failed: {e}")

            # Store the email
            output_location = await self._store_email(email)

            # Process email through scenarios with timeout and error handling
            scenario_result = None
            try:
                # Use the scenario processor directly - it manages its own lifecycle
                # Add timeout to prevent hanging
                scenario_result = await asyncio.wait_for(
                    self.scenario_processor.process_email_scenario(email),
                    timeout=300.0  # 5 minute timeout (increased for warehouse startup scenarios)
                )
            except asyncio.TimeoutError:
                self.logger.error(
                    "Scenario processing timed out",
                    extra={
                        "email_id": email_id,
                        "timeout_seconds": 300
                    }
                )
                # Continue with email processing even if scenario processing fails
            except Exception as e:
                self.logger.error(
                    "Scenario processing failed",
                    extra={
                        "error": str(e),
                        "email_id": email_id,
                        "error_type": type(e).__name__
                    }
                )
                # Continue with email processing even if scenario processing fails

                # If this is a customer response scenario (5-11), handle response processing
                if scenario_result and scenario_result.scenario_type.value.startswith("scenario_"):
                    scenario_num = self._extract_scenario_number(
                        scenario_result.scenario_type.value
                    )
                    if scenario_num and 5 <= scenario_num <= 11:
                        # Convert email back to message format for response handler
                        try:
                            email_message = self._convert_email_to_message(message, email)
                            await self.response_handler.process_customer_response(
                                email_message=email_message, scenario=scenario_num
                            )
                            self.logger.info(
                                "Successfully processed customer response",
                                extra={
                                    "email_id": email_id,
                                    "scenario": scenario_num
                                }
                            )
                        except ValueError as ve:
                            self.logger.error(
                                "Invalid data for customer response processing",
                                extra={
                                    "error": str(ve),
                                    "email_id": email_id,
                                    "scenario": scenario_num,
                                }
                            )
                            # Don't fail the entire email processing due to validation errors
                        except Exception as e:
                            self.logger.error(
                                "Failed to process customer response",
                                extra={
                                    "error": str(e),
                                    "email_id": email_id,
                                    "scenario": scenario_num,
                                    "error_type": type(e).__name__
                                }
                            )
                            # Don't fail the entire email processing due to response handling errors

            # Only move email to processed folder if scenario processing succeeded
            should_move_email = False
            move_reason = "not moved - no valid scenario processing"
            
            if scenario_result:
                if scenario_result.success and scenario_result.scenario_type.value != "unknown":
                    should_move_email = True
                    move_reason = f"moved - successful {scenario_result.scenario_type.value}"
                else:
                    move_reason = f"not moved - {scenario_result.scenario_type.value} {'failed' if not scenario_result.success else 'with no action'}"
            
            # Move email to processed folder only if processing was successful
            if should_move_email and not self.settings.dry_run:
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
                    
                self.logger.info(
                    "Email moved to processed folder after successful scenario processing",
                    extra={
                        "email_id": email_id,
                        "folder": folder_name,
                        "scenario_type": scenario_result.scenario_type.value,
                        "scenario_success": scenario_result.success
                    }
                )
            elif should_move_email and self.settings.dry_run:
                self.logger.info(
                    "Dry-run mode: Email would be moved to folder",
                    extra={
                        "email_id": email_id,
                        "folder": folder_name,
                        "scenario_type": scenario_result.scenario_type.value,
                    }
                )
            else:
                self.logger.warning(
                    "Email left in inbox - scenario processing failed or resulted in unknown classification",
                    extra={
                        "email_id": email_id,
                        "reason": move_reason,
                        "scenario_type": scenario_result.scenario_type.value if scenario_result else "no_result",
                        "scenario_success": scenario_result.success if scenario_result else False
                    }
                )

            processing_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            return ProcessingResult(
                success=should_move_email,  # Only consider successful if email was moved
                email_id=email_id,
                processing_id=processing_id,
                sender_email=email.sender.email,
                sender_name=email.sender.name,
                subject=email.subject,
                error=None if should_move_email else f"Email not processed: {move_reason}",
                moved_to_folder=folder_name if should_move_email and not self.settings.dry_run else None,
                output_location=output_location,
                processing_time_ms=processing_time_ms,
                scenario_type=scenario_result.scenario_type.value if scenario_result else "no_scenario_result",
                scenario_success=scenario_result.success if scenario_result else False,
                actions_taken=scenario_result.actions_taken if scenario_result else [],
                expert_assigned=scenario_result.expert_assigned if scenario_result else None,
                case_created=scenario_result.case_created if scenario_result else None,
                emails_sent=scenario_result.emails_sent
                if scenario_result and scenario_result.emails_sent
                else [],
            )

        except Exception as e:
            self.logger.error(f"Failed to process email (email_id: {email_id}): {e}")

            processing_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

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

        self.logger.info("Email stored to file", extra={"filepath": str(filepath), "email_id": email.id})

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
                extra={
                    "email_id": email.id,
                    "response_id": result.get("id", "unknown"),
                }
            )

            return result.get("id", email.processing_metadata.processing_id)

    def _get_processed_folder_name(self) -> str:
        """Get the name for the processed folder based on current date.

        Returns:
            Folder name like "Processed_01_2024"
        """
        now = datetime.now(timezone.utc)
        month = now.strftime("%m")
        year = now.strftime("%Y")

        return f"{self.settings.processing.processed_folder_prefix}_{month}_{year}"

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
                extra={
                    "folder_name": folder_name,
                    "folder_id": folder.get("id"),
                }
            )
            return folder

        # Create new folder with retry
        self.logger.info("Creating new processed folder", extra={"folder_name": folder_name})

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

        self.logger.error(f"Failed to create processed folder (folder: {folder_name}): {error}")
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
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Validate inputs
            if not original_message:
                raise ValueError("Original message cannot be empty")
            if not email:
                raise ValueError("Email model cannot be None")
            if not email.id:
                raise ValueError("Email ID is required")
                
            # Build message with proper fallbacks and validation
            message = {
                "id": original_message.get("id") or email.id,
                "from": original_message.get("from", {}),
                "conversationId": original_message.get("conversationId"),
                "subject": original_message.get("subject") or email.subject or "(No Subject)",
                "sender": original_message.get("sender", {}),
            }
            
            # Handle receivedDateTime with proper error handling
            if "receivedDateTime" in original_message:
                message["receivedDateTime"] = original_message["receivedDateTime"]
            elif email.received_datetime:
                try:
                    message["receivedDateTime"] = email.received_datetime.isoformat()
                except (AttributeError, ValueError) as e:
                    self.logger.warning(
                        "Failed to format received datetime, using current time",
                        error=str(e),
                        email_id=email.id
                    )
                    message["receivedDateTime"] = datetime.now(timezone.utc).isoformat()
            else:
                message["receivedDateTime"] = datetime.now(timezone.utc).isoformat()
            
            # Handle body content with validation
            if "body" in original_message and original_message["body"]:
                message["body"] = original_message["body"]
            else:
                # Create proper body structure
                body_content = ""
                if hasattr(email, 'body') and email.body:
                    if hasattr(email.body, 'content'):
                        body_content = email.body.content or ""
                    else:
                        body_content = str(email.body)
                elif email.body_preview:
                    body_content = email.body_preview
                    
                message["body"] = {
                    "content": body_content,
                    "contentType": "text/plain"
                }
            
            return message
            
        except Exception as e:
            self.logger.error(
                "Failed to convert email to message format",
                error=str(e),
                email_id=getattr(email, 'id', 'unknown'),
                original_message_id=original_message.get('id', 'unknown') if original_message else 'unknown'
            )
            raise ValueError(f"Failed to convert email to message format: {e}")
