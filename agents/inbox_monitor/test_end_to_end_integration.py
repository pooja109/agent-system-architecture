#!/usr/bin/env python3
"""
End-to-End Integration Test
===========================

CAUTION: This test performs REAL operations including:
- Sending actual emails via Azure Communication Services
- Creating real Salesforce cases and updating contacts
- Updating real Databricks tables
- Using real Azure AI Foundry for intent classification

Only run this test in a controlled environment with proper test data.
"""

# CRITICAL: Set environment variables BEFORE any imports to disable aiohttp warnings
import os
os.environ['AIOHTTP_NO_EXTENSIONS'] = '1'
os.environ['PYTHONWARNINGS'] = 'ignore::ResourceWarning'

# Monkey patch aiohttp to disable unclosed session warnings at the source
import sys
from io import StringIO

def disable_aiohttp_warnings():
    """Completely disable aiohttp unclosed session warnings."""
    try:
        import aiohttp.client
        import warnings
        
        # Monkey patch the ClientSession._del__ method to suppress warnings
        original_del = getattr(aiohttp.client.ClientSession, '__del__', None)
        
        def silent_del(self):
            """Silent destructor that doesn't print warnings."""
            try:
                if hasattr(self, '_connector') and self._connector is not None:
                    if not self._connector.closed:
                        # Force close without warnings
                        self._connector._close()
                if hasattr(self, '_connector_owner') and self._connector_owner:
                    self._connector = None
            except Exception:
                pass  # Silent cleanup
            
            # Call original destructor if it exists, but suppress any output
            if original_del:
                old_stderr = sys.stderr
                try:
                    sys.stderr = StringIO()  # Redirect stderr
                    original_del(self)
                except Exception:
                    pass
                finally:
                    sys.stderr = old_stderr
        
        # Apply the patch
        aiohttp.client.ClientSession.__del__ = silent_del
        
        # Also suppress at module level
        if hasattr(aiohttp.client, '_warn_unclosed_session'):
            aiohttp.client._warn_unclosed_session = lambda *args, **kwargs: None
            
    except ImportError:
        pass  # aiohttp not available yet

# Apply the patch before other imports
disable_aiohttp_warnings()

import asyncio
import gc
from datetime import UTC, datetime
from typing import Any

import structlog
from config.settings import get_settings, validate_settings
from models.email import Email, EmailAddress, EmailBody, EmailRecipients, ProcessingMetadata
from services.scenario_processor import ScenarioProcessor
from utils.async_cleanup import graceful_shutdown, suppress_future_warnings

# Configure logging for integration test
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class IntegrationTestRunner:
    """Manages end-to-end integration testing with real services."""

    def __init__(self):
        """Initialize the integration test runner."""
        self.settings = get_settings()
        self.results: list[dict[str, Any]] = []
        self.test_identifier = f"E2E_TEST_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

    async def setup_test_environment(self) -> bool:
        """Setup and validate test environment.

        Returns:
            True if environment is ready, False otherwise
        """
        logger.info("Setting up end-to-end integration test environment")

        # Validate all required settings
        try:
            if not validate_settings(self.settings):
                logger.error("Settings validation failed")
                return False
        except Exception as e:
            logger.error("Settings validation error", error=str(e))
            return False

        # Verify we're using test email addresses
        if not self.settings.scenarios.victoria_grant_email:
            logger.error("Victoria Grant email not configured")
            return False

        if not self.settings.scenarios.account_team_email:
            logger.error("Account team email not configured")
            return False

        # Warn about real operations
        logger.warning("⚠️  INTEGRATION TEST WILL PERFORM REAL OPERATIONS ⚠️")
        logger.warning("This test will:")
        logger.warning("  - Send real emails via Azure Communication Services")
        logger.warning("  - Create real Salesforce cases")
        logger.warning("  - Update real Salesforce contacts")
        logger.warning("  - Update real Databricks tables")
        logger.warning("  - Use real Azure AI Foundry tokens")
        logger.warning(f"Test identifier: {self.test_identifier}")

        return True

    def create_test_email(
        self, subject: str, body: str, sender_email: str, scenario_name: str
    ) -> Email:
        """Create a test email with integration test metadata.

        Args:
            subject: Email subject
            body: Email body content
            sender_email: Sender email address
            scenario_name: Name of the scenario being tested

        Returns:
            Email object for testing
        """
        test_subject = f"[{self.test_identifier}] {scenario_name}: {subject}"
        test_body = f"""
=== INTEGRATION TEST EMAIL ===
Test ID: {self.test_identifier}
Scenario: {scenario_name}
Timestamp: {datetime.now(UTC).isoformat()}

{body}

=== END TEST EMAIL ===
"""

        return Email(
            id=f"{self.test_identifier}_{scenario_name}_{datetime.now(UTC).strftime('%H%M%S')}",
            conversation_id=f"{self.test_identifier}_conversation",
            received_datetime=datetime.now(UTC),
            sender=EmailAddress(email=sender_email, name=f"Test Customer ({scenario_name})"),
            recipients=EmailRecipients(
                to=[EmailAddress(email=self.settings.graph_api.monitored_email, name="Test Inbox")]
            ),
            subject=test_subject,
            body=EmailBody(content_type="text/plain", content=test_body),
            body_preview=test_body[:255],
            processing_metadata=ProcessingMetadata(
                inbox_monitor_version="2.0.0-integration-test",
                processing_id=f"{self.test_identifier}_{scenario_name}",
            ),
        )

    async def test_scenario_5_positive_real(self) -> dict[str, Any]:
        """Test Scenario 5: Positive Response with real service calls."""
        logger.info("🟢 Starting real integration test for Scenario 5: Positive Response")

        email = self.create_test_email(
            subject="Re: Your services look very interesting",
            body="Hi there! I'm very interested in learning more about your solutions. Could you please have someone call me at 555-1234 to discuss this further? I think this could be exactly what we need for our company.",
            sender_email="reception@creativestonenc.com",
            scenario_name="Scenario_5_Positive",
        )

        start_time = datetime.now(UTC)

        try:
            async with ScenarioProcessor(self.settings) as processor:
                result = await processor.process_email_scenario(email)

                end_time = datetime.now(UTC)
                processing_time = (end_time - start_time).total_seconds()

                test_result = {
                    "scenario": "Scenario_5_Positive",
                    "success": result.success,
                    "scenario_type": result.scenario_type.value,
                    "expert_assigned": result.expert_assigned,
                    "case_created": result.case_created,
                    "actions_taken": result.actions_taken,
                    "error_message": result.error_message,
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat(),
                    "real_operations": {
                        "ai_classification": "✅ Real",
                        "salesforce_case": "✅ Real" if result.case_created else "❌ Failed",
                        "databricks_assignment": "✅ Real" if result.expert_assigned else "❌ Failed",
                        "email_sending": "N/A (no email forwarding in positive scenario)",
                    },
                }

                logger.info(
                    "Scenario 5 integration test completed",
                    success=result.success,
                    expert=result.expert_assigned,
                    case_id=result.case_created,
                    processing_time=processing_time,
                )

                return test_result

        except Exception as e:
            logger.error("Scenario 5 integration test failed", error=str(e))
            return {
                "scenario": "Scenario_5_Positive",
                "success": False,
                "error_message": str(e),
                "processing_time_seconds": (datetime.now(UTC) - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
                "real_operations": {"error": "Test failed before operations"},
            }

    async def test_scenario_6_negative_real(self) -> dict[str, Any]:
        """Test Scenario 6: Negative Response with real email forwarding."""
        logger.info("🔴 Starting real integration test for Scenario 6: Negative Response")

        email = self.create_test_email(
            subject="Stop contacting me immediately",
            body="I'm not interested in your services at all. Please remove me from your contact list immediately and don't contact me again. This is harassment.",
            sender_email="integration.negative@example.com",
            scenario_name="Scenario_6_Negative",
        )

        start_time = datetime.now(UTC)

        try:
            async with ScenarioProcessor(self.settings) as processor:
                result = await processor.process_email_scenario(email)

                end_time = datetime.now(UTC)
                processing_time = (end_time - start_time).total_seconds()

                test_result = {
                    "scenario": "Scenario_6_Negative",
                    "success": result.success,
                    "scenario_type": result.scenario_type.value,
                    "emails_sent": result.emails_sent,
                    "actions_taken": result.actions_taken,
                    "error_message": result.error_message,
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat(),
                    "real_operations": {
                        "ai_classification": "✅ Real",
                        "email_forwarding": "✅ Real" if result.emails_sent else "❌ Failed",
                        "victoria_grant_notified": "✅ Real" if result.emails_sent else "❌ Failed",
                    },
                }

                logger.info(
                    "Scenario 6 integration test completed",
                    success=result.success,
                    emails_sent=result.emails_sent,
                    processing_time=processing_time,
                )

                return test_result

        except Exception as e:
            logger.error("Scenario 6 integration test failed", error=str(e))
            return {
                "scenario": "Scenario_6_Negative",
                "success": False,
                "error_message": str(e),
                "processing_time_seconds": (datetime.now(UTC) - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
                "real_operations": {"error": "Test failed before operations"},
            }

    async def test_scenario_7_service_inquiry_real(self) -> dict[str, Any]:
        """Test Scenario 7: Service Inquiry with real email forwarding."""
        logger.info("🔵 Starting real integration test for Scenario 7: Service Inquiry")

        email = self.create_test_email(
            subject="Question about my recent order #12345",
            body="Hi, I have a question about my recent order. The tracking number you provided isn't working and I can't see the delivery status. Can you help me track my package?",
            sender_email="integration.service@example.com",
            scenario_name="Scenario_7_Service",
        )

        start_time = datetime.now(UTC)

        try:
            async with ScenarioProcessor(self.settings) as processor:
                result = await processor.process_email_scenario(email)

                end_time = datetime.now(UTC)
                processing_time = (end_time - start_time).total_seconds()

                test_result = {
                    "scenario": "Scenario_7_Service",
                    "success": result.success,
                    "scenario_type": result.scenario_type.value,
                    "emails_sent": result.emails_sent,
                    "actions_taken": result.actions_taken,
                    "error_message": result.error_message,
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat(),
                    "real_operations": {
                        "ai_classification": "✅ Real",
                        "email_forwarding": "✅ Real" if result.emails_sent else "❌ Failed",
                        "account_team_notified": "✅ Real" if result.emails_sent else "❌ Failed",
                    },
                }

                logger.info(
                    "Scenario 7 integration test completed",
                    success=result.success,
                    emails_sent=result.emails_sent,
                    processing_time=processing_time,
                )

                return test_result

        except Exception as e:
            logger.error("Scenario 7 integration test failed", error=str(e))
            return {
                "scenario": "Scenario_7_Service",
                "success": False,
                "error_message": str(e),
                "processing_time_seconds": (datetime.now(UTC) - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
                "real_operations": {"error": "Test failed before operations"},
            }

    async def test_scenario_8_out_of_office_real(self) -> dict[str, Any]:
        """Test Scenario 8: Out of Office with real database updates."""
        logger.info("🟡 Starting real integration test for Scenario 8: Out of Office")

        email = self.create_test_email(
            subject="Automatic reply: Out of Office",
            body="Thank you for your email. I am currently out of the office and will return on Monday, July 22nd. If this is urgent, please contact my assistant at assistant@company.com.",
            sender_email="integration.ooo@example.com",
            scenario_name="Scenario_8_OOO",
        )

        start_time = datetime.now(UTC)

        try:
            async with ScenarioProcessor(self.settings) as processor:
                result = await processor.process_email_scenario(email)

                end_time = datetime.now(UTC)
                processing_time = (end_time - start_time).total_seconds()

                test_result = {
                    "scenario": "Scenario_8_OOO",
                    "success": result.success,
                    "scenario_type": result.scenario_type.value,
                    "actions_taken": result.actions_taken,
                    "error_message": result.error_message,
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat(),
                    "real_operations": {
                        "ai_classification": "✅ Real",
                        "databricks_update": "✅ Real" if result.success else "❌ Failed",
                        "assignment_status_update": "✅ Real" if result.success else "❌ Failed",
                    },
                }

                logger.info(
                    "Scenario 8 integration test completed",
                    success=result.success,
                    processing_time=processing_time,
                )

                return test_result

        except Exception as e:
            logger.error("Scenario 8 integration test failed", error=str(e))
            return {
                "scenario": "Scenario_8_OOO",
                "success": False,
                "error_message": str(e),
                "processing_time_seconds": (datetime.now(UTC) - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
                "real_operations": {"error": "Test failed before operations"},
            }

    async def test_scenario_9_invalid_email_real(self) -> dict[str, Any]:
        """Test Scenario 9: Invalid Email with real Salesforce and Databricks updates."""
        logger.info("🟠 Starting real integration test for Scenario 9: Invalid Email")

        # Use test_sender_email for proper test mode substitution
        sender_email = self.settings.test_mode.test_sender_email if self.settings.test_mode.enabled else "integration.bounce@example.com"
        
        # Create bounce message that references the target Salesforce email
        bounce_body = f"""Your message could not be delivered to {self.settings.test_mode.target_salesforce_email if self.settings.test_mode.enabled else 'customer@example.com'}.

The email address may be invalid or the mailbox may be full. Please verify the email address and try again.

Original Message:
Subject: Your recent outreach
From: {self.settings.test_mode.target_salesforce_email if self.settings.test_mode.enabled else 'customer@example.com'}

This is an automated bounce notification generated for integration testing."""

        email = self.create_test_email(
            subject="Delivery Status Notification (Failure)",
            body=bounce_body,
            sender_email=sender_email,
            scenario_name="Scenario_9_Invalid",
        )

        start_time = datetime.now(UTC)

        try:
            async with ScenarioProcessor(self.settings) as processor:
                result = await processor.process_email_scenario(email)

                end_time = datetime.now(UTC)
                processing_time = (end_time - start_time).total_seconds()

                test_result = {
                    "scenario": "Scenario_9_Invalid",
                    "success": result.success,
                    "scenario_type": result.scenario_type.value,
                    "actions_taken": result.actions_taken,
                    "error_message": result.error_message,
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat(),
                    "test_config": {
                        "sender_email": sender_email,
                        "target_salesforce_email": self.settings.test_mode.target_salesforce_email if self.settings.test_mode.enabled else "customer@example.com",
                        "test_mode_enabled": self.settings.test_mode.enabled,
                    },
                    "real_operations": {
                        "ai_classification": "✅ Real",
                        "salesforce_invalid_email_update": "✅ Real"
                        if result.success
                        else "❌ Failed",
                        "databricks_assignment_update": "✅ Real" if result.success else "❌ Failed",
                    },
                }

                logger.info(
                    "Scenario 9 integration test completed",
                    success=result.success,
                    processing_time=processing_time,
                )

                return test_result

        except Exception as e:
            logger.error("Scenario 9 integration test failed", error=str(e))
            return {
                "scenario": "Scenario_9_Invalid",
                "success": False,
                "error_message": str(e),
                "processing_time_seconds": (datetime.now(UTC) - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
                "test_config": {
                    "sender_email": sender_email,
                    "target_salesforce_email": self.settings.test_mode.target_salesforce_email if self.settings.test_mode.enabled else "customer@example.com",
                    "test_mode_enabled": self.settings.test_mode.enabled,
                },
                "real_operations": {"error": "Test failed before operations"},
            }

    async def test_scenario_10_no_longer_works_real(self) -> dict[str, Any]:
        """Test Scenario 10: No Longer Works with real email forwarding and database updates."""
        logger.info("🟣 Starting real integration test for Scenario 10: No Longer Works")

        email = self.create_test_email(
            subject="Re: Your recent outreach",
            body="Hi, John no longer works at this company. He left last month to pursue other opportunities.",
            sender_email="integration.nolonger@example.com",
            scenario_name="Scenario_10_NoLonger",
        )

        start_time = datetime.now(UTC)

        try:
            async with ScenarioProcessor(self.settings) as processor:
                result = await processor.process_email_scenario(email)

                end_time = datetime.now(UTC)
                processing_time = (end_time - start_time).total_seconds()

                test_result = {
                    "scenario": "Scenario_10_NoLonger",
                    "success": result.success,
                    "scenario_type": result.scenario_type.value,
                    "emails_sent": result.emails_sent,
                    "actions_taken": result.actions_taken,
                    "error_message": result.error_message,
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat(),
                    "real_operations": {
                        "ai_classification": "✅ Real",
                        "email_forwarding": "✅ Real" if result.emails_sent else "❌ Failed",
                        "victoria_grant_notified": "✅ Real" if result.emails_sent else "❌ Failed",
                        "databricks_assignment_update": "✅ Real" if result.success else "❌ Failed",
                    },
                }

                logger.info(
                    "Scenario 10 integration test completed",
                    success=result.success,
                    emails_sent=result.emails_sent,
                    processing_time=processing_time,
                )

                return test_result

        except Exception as e:
            logger.error("Scenario 10 integration test failed", error=str(e))
            return {
                "scenario": "Scenario_10_NoLonger",
                "success": False,
                "error_message": str(e),
                "processing_time_seconds": (datetime.now(UTC) - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
                "real_operations": {"error": "Test failed before operations"},
            }

    async def cleanup_test_data(self) -> None:
        """Clean up any test data created during integration testing.

        Note: This is a placeholder. In a real environment, you would need to:
        - Delete any test Salesforce cases created
        - Revert any Salesforce contact updates made
        - Remove or mark test assignments in Databricks
        - Clean up any test email records
        """
        logger.info("Starting test data cleanup", test_id=self.test_identifier)

        # TODO: Implement real cleanup based on your environment
        # This might include:
        # - Querying Salesforce for cases with test identifier in description
        # - Reverting contact Is_Email_Invalid__c fields that were set during testing
        # - Updating Databricks assignment records to mark them as test data
        # - Removing any test email artifacts

        logger.warning("Test data cleanup not implemented - manual cleanup may be required")
        logger.info(
            "Search for test identifier in systems to find test data", test_id=self.test_identifier
        )

    def generate_integration_report(self) -> str:
        """Generate a comprehensive integration test report.

        Returns:
            Formatted test report string
        """
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.get("success", False)])
        failed_tests = total_tests - successful_tests

        total_processing_time = sum([r.get("processing_time_seconds", 0) for r in self.results])
        avg_processing_time = total_processing_time / total_tests if total_tests > 0 else 0

        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        END-TO-END INTEGRATION TEST REPORT                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Test ID: {self.test_identifier}                                              ║
║ Timestamp: {datetime.now(UTC).isoformat()}                         ║
║ Environment: {self.settings.environment}                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ SUMMARY                                                                      ║
║   Total Tests: {total_tests:2d}                                              ║
║   Successful:  {successful_tests:2d}                                         ║
║   Failed:      {failed_tests:2d}                                             ║
║   Success Rate: {(successful_tests/total_tests*100) if total_tests > 0 else 0:5.1f}%                                                        ║
║   Avg Processing Time: {avg_processing_time:5.2f}s                           ║
║   Total Processing Time: {total_processing_time:5.2f}s                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ DETAILED RESULTS                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""

        for result in self.results:
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            scenario = result.get("scenario", "Unknown")
            processing_time = result.get("processing_time_seconds", 0)

            report += f"\n{scenario}: {status} ({processing_time:.2f}s)\n"

            if result.get("real_operations"):
                report += "  Real Operations:\n"
                for operation, status in result["real_operations"].items():
                    report += f"    {operation}: {status}\n"

            if result.get("actions_taken"):
                report += "  Actions Taken:\n"
                for action in result["actions_taken"]:
                    report += f"    • {action}\n"

            if result.get("error_message"):
                report += f"  Error: {result['error_message']}\n"

            report += "\n" + "─" * 80 + "\n"

        report += f"""
CONFIGURATION USED:
  Azure AI Foundry: {self.settings.azure_ai_foundry.endpoint}
  Salesforce: {self.settings.salesforce.base_url}
  Databricks: {self.settings.databricks.server_hostname}
  Test Email: {self.settings.graph_api.monitored_email}
  Victoria Grant: {self.settings.scenarios.victoria_grant_email}
  Account Team: {self.settings.scenarios.account_team_email}

CLEANUP REQUIRED:
  Search for "{self.test_identifier}" in:
  • Salesforce cases (Subject/Description)
  • Salesforce contacts (Is_Email_Invalid__c updates)
  • Databricks assignment tables
  • Email system logs

⚠️  IMPORTANT: This test performed REAL operations on production systems.
    Manual verification and cleanup may be required.
"""

        return report

    async def run_all_integration_tests(self) -> str:
        """Run all integration tests and return a comprehensive report.

        Returns:
            Formatted test report string
        """
        logger.info("Starting comprehensive end-to-end integration tests")

        # Setup test environment
        if not await self.setup_test_environment():
            return "❌ Test environment setup failed. Integration tests aborted."

        # Run all scenario tests
        test_methods = [
            self.test_scenario_5_positive_real,
            self.test_scenario_6_negative_real,
            self.test_scenario_7_service_inquiry_real,
            self.test_scenario_8_out_of_office_real,
            self.test_scenario_9_invalid_email_real,
            self.test_scenario_10_no_longer_works_real,
        ]

        for test_method in test_methods:
            try:
                result = await test_method()
                self.results.append(result)
            except Exception as e:
                logger.error(f"Test method {test_method.__name__} failed", error=str(e))
                self.results.append(
                    {
                        "scenario": test_method.__name__,
                        "success": False,
                        "error_message": f"Test method exception: {e!s}",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        # Generate and return report
        report = self.generate_integration_report()

        # Cleanup test data
        await self.cleanup_test_data()

        # Add final delay to ensure all async cleanup completes
        await asyncio.sleep(1.0)

        # Force garbage collection to clean up any remaining resources
        gc.collect()

        # Give additional time for cleanup to complete
        await asyncio.sleep(0.5)

        return report


async def cleanup_async_resources():
    """Cleanup any remaining async resources and connections."""
    try:
        # Get current task to avoid cancelling ourselves
        current_task = asyncio.current_task()

        # Cancel any remaining tasks (except current task)
        tasks = [task for task in asyncio.all_tasks() if not task.done() and task != current_task]

        if tasks:
            # Cancel tasks safely
            for task in tasks:
                if not task.cancelled():
                    task.cancel()

            # Wait for cancelled tasks with timeout, but don't propagate exceptions
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Some tasks did not complete within timeout")
            except Exception as e:
                logger.debug(f"Error waiting for tasks: {e}")

    except Exception as e:
        logger.warning("Error during task cleanup", error=str(e))

    # Force close all aiohttp sessions
    try:
        import aiohttp

        # Get all objects in memory and close aiohttp sessions
        for obj in gc.get_objects():
            # Close any aiohttp.ClientSession objects
            if isinstance(obj, aiohttp.ClientSession):
                try:
                    if not obj.closed:
                        await obj.close()
                        logger.debug("Closed aiohttp session")
                except Exception as e:
                    logger.debug(f"Error closing aiohttp session: {e}")

            # Close any aiohttp.TCPConnector objects
            elif hasattr(obj, "__class__") and obj.__class__.__name__ == "TCPConnector":
                try:
                    if hasattr(obj, "close"):
                        await obj.close()
                        logger.debug("Closed TCP connector")
                except Exception as e:
                    logger.debug(f"Error closing TCP connector: {e}")

    except Exception as e:
        logger.warning("Error during aiohttp cleanup", error=str(e))

    # Force garbage collection multiple times
    for _ in range(3):
        gc.collect()
        await asyncio.sleep(0.1)


async def main():
    """Main entry point for end-to-end integration testing."""

    # Safety check - require explicit confirmation
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║                           ⚠️  DANGER ZONE ⚠️                                ║")
    print("║                                                                              ║")
    print("║  This integration test will perform REAL operations:                        ║")
    print("║  • Send actual emails via Azure Communication Services                      ║")
    print("║  • Create real Salesforce cases                                             ║")
    print("║  • Update real Salesforce contact records                                   ║")
    print("║  • Update real Databricks tables                                            ║")
    print("║  • Consume real Azure AI Foundry tokens                                     ║")
    print("║                                                                              ║")
    print("║  Only proceed if you understand the implications and have proper backups.   ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print()

    confirmation = input("Type 'I UNDERSTAND THE RISKS' to proceed with real integration testing: ")

    if confirmation != "I UNDERSTAND THE RISKS":
        print("❌ Integration test aborted for safety.")
        return

    print("\n🚀 Starting end-to-end integration tests...")

    try:
        # Run integration tests
        runner = IntegrationTestRunner()
        report = await runner.run_all_integration_tests()

        # Display report
        print(report)

        # Save report to file (use UTF-8 encoding for Unicode characters)
        report_filename = f"integration_test_report_{runner.test_identifier}.txt"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n📄 Report saved to: {report_filename}")
        print("✅ Integration testing completed.")

    finally:
        # Final cleanup to ensure all async resources are closed
        try:
            await cleanup_async_resources()
        except Exception as e:
            logger.warning("Error during final cleanup", error=str(e))

        # Give additional time for cleanup to complete
        await asyncio.sleep(0.5)


async def run_with_cleanup():
    """Run main with comprehensive cleanup."""
    try:
        await main()
    finally:
        # Extra cleanup and warning suppression
        import gc
        try:
            # Force garbage collection
            gc.collect()
            
            # Try to close any remaining aiohttp sessions
            try:
                import aiohttp
                closed_sessions = 0
                for obj in gc.get_objects():
                    if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                        try:
                            await obj.close()
                            closed_sessions += 1
                        except:
                            pass
                if closed_sessions > 0:
                    print(f"Closed {closed_sessions} remaining aiohttp sessions")
            except ImportError:
                pass
            
            # Brief delay for final cleanup
            await asyncio.sleep(0.2)
                
        except Exception:
            pass  # Silent cleanup


def apply_runtime_aiohttp_patches():
    """Apply aggressive runtime patches to completely suppress aiohttp warnings."""
    try:
        import aiohttp
        import aiohttp.client
        import aiohttp.connector
        import warnings
        import logging
        
        # Patch 1: Disable the __del__ method warnings
        def silent_client_del(self):
            try:
                if hasattr(self, '_connector') and self._connector is not None:
                    try:
                        if not self._connector.closed:
                            self._connector._close()
                    except:
                        pass
                    self._connector = None
            except:
                pass
        
        def silent_connector_del(self):
            try:
                if hasattr(self, '_close'):
                    self._close()
            except:
                pass
        
        # Apply patches to all aiohttp classes that might create warnings
        aiohttp.ClientSession.__del__ = silent_client_del
        
        if hasattr(aiohttp, 'TCPConnector'):
            aiohttp.TCPConnector.__del__ = silent_connector_del
        if hasattr(aiohttp.connector, 'TCPConnector'):
            aiohttp.connector.TCPConnector.__del__ = silent_connector_del
            
        # Patch 2: Suppress warnings at the module level
        if hasattr(aiohttp.client, '_warn_unclosed_session'):
            aiohttp.client._warn_unclosed_session = lambda *args, **kwargs: None
        if hasattr(aiohttp.connector, '_warn_unclosed_connector'):
            aiohttp.connector._warn_unclosed_connector = lambda *args, **kwargs: None
            
        # Patch 3: Disable all aiohttp loggers
        for logger_name in ['aiohttp', 'aiohttp.access', 'aiohttp.client', 'aiohttp.connector', 'aiohttp.server']:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.CRITICAL)
            logger.disabled = True
            
        # Patch 4: Silence resource warnings globally
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", message=".*unclosed.*", category=ResourceWarning)
        
        print("✅ Applied comprehensive aiohttp warning suppression")
        
    except Exception as e:
        print(f"Warning: Could not apply all aiohttp patches: {e}")


class AIOHTTPWarningFilter:
    """Context manager that filters only aiohttp warnings while preserving other output."""
    
    def __init__(self):
        self.original_stderr = None
        self.buffer = StringIO()
        
    def __enter__(self):
        self.original_stderr = sys.stderr
        sys.stderr = self
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self.original_stderr
        
        # Process buffered output and filter aiohttp warnings
        buffered_content = self.buffer.getvalue()
        if buffered_content:
            lines = buffered_content.split('\n')
            filtered_lines = []
            
            for line in lines:
                # Filter out aiohttp warnings but keep everything else
                if not any(warning in line for warning in [
                    "Unclosed client session",
                    "Unclosed connector", 
                    "client_session:",
                    "connector:"
                ]):
                    filtered_lines.append(line)
            
            # Output non-aiohttp warnings immediately
            filtered_content = '\n'.join(filtered_lines).strip()
            if filtered_content:
                print(filtered_content, file=self.original_stderr)
    
    def write(self, text):
        # Check if this is an aiohttp warning
        if any(warning in text for warning in [
            "Unclosed client session",
            "Unclosed connector",
            "client_session:",
            "connector:"
        ]):
            # Buffer aiohttp warnings (they'll be filtered out)
            self.buffer.write(text)
        else:
            # Immediately write non-aiohttp content to original stderr
            self.original_stderr.write(text)
            self.original_stderr.flush()
    
    def flush(self):
        if self.original_stderr:
            self.original_stderr.flush()


if __name__ == "__main__":
    # Apply all suppression methods
    suppress_future_warnings()
    apply_runtime_aiohttp_patches()
    
    # Additional environment setup
    os.environ.setdefault('PYTHONWARNINGS', 'ignore')
    
    print("🚀 Starting end-to-end integration tests with full aiohttp warning suppression...")
    
    try:
        # Run with selective stderr filtering for aiohttp warnings only
        with AIOHTTPWarningFilter():
            asyncio.run(run_with_cleanup())
    except Exception as e:
        # Re-enable stderr for actual errors
        print(f"Error during test execution: {e}", file=sys.stderr)
        raise
    finally:
        # Final cleanup with stderr suppressed only for aiohttp
        try:
            with AIOHTTPWarningFilter():
                import gc
                gc.collect()
                import time
                time.sleep(0.1)
        except Exception:
            pass
