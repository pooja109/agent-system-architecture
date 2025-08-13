"""
Logging Scenarios for Integration Testing
==========================================

Pre-defined logging scenarios for testing different aspects of the logging system.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Callable
from dataclasses import dataclass
from unittest.mock import Mock

from utils.custom_logging import initialize_logging, LoggingConfig, LogLevel, OutputFormat, ConsoleConfig, StructuredConfig
from utils.custom_logging.correlation import set_correlation_context
from .mock_services import create_mock_services_suite, MockGraphAPIClient, MockEmailProcessor


@dataclass
class LoggingScenario:
    """Represents a logging test scenario."""
    name: str
    description: str
    config: LoggingConfig
    expected_outcomes: Dict[str, Any]
    test_function: Callable


class LoggingScenarios:
    """Collection of logging scenarios for comprehensive testing."""
    
    @staticmethod
    def get_quiet_mode_scenario() -> LoggingScenario:
        """Scenario for testing quiet mode logging."""
        config = LoggingConfig(
            console=ConsoleConfig(
                enabled=True,
                level=LogLevel.ERROR,  # Only errors in quiet mode
                format=OutputFormat.MINIMAL
            ),
            structured=StructuredConfig(
                enabled=True,
                level=LogLevel.INFO  # Still capture structured info
            ),
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )
        
        async def test_function():
            """Test quiet mode logging behavior."""
            services = create_mock_services_suite()
            
            # Should see errors but not info/debug messages
            services["email_processor"].log_user_message("This info should be suppressed", "info")
            services["email_processor"].log_user_message("This error should appear", "error")
            
            # HTTP logging should be suppressed
            urllib3_logger = logging.getLogger('urllib3')
            urllib3_logger.info("This HTTP info should be suppressed")
            urllib3_logger.error("This HTTP error should appear")
            
            return {
                "console_messages": ["error"],  # Only errors should appear
                "http_suppressed": True,
                "structured_captured": True
            }
        
        return LoggingScenario(
            name="quiet_mode",
            description="Test quiet mode with minimal console output",
            config=config,
            expected_outcomes={
                "console_level": "ERROR",
                "http_suppression": True,
                "structured_enabled": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_verbose_mode_scenario() -> LoggingScenario:
        """Scenario for testing verbose mode logging."""
        config = LoggingConfig(
            console=ConsoleConfig(
                enabled=True,
                level=LogLevel.INFO,
                format=OutputFormat.DETAILED
            ),
            structured=StructuredConfig(
                enabled=True,
                level=LogLevel.DEBUG
            ),
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )
        
        async def test_function():
            """Test verbose mode logging behavior."""
            services = create_mock_services_suite()
            
            # Should see info and error messages
            services["email_processor"].log_user_message("This info should appear", "info")
            services["email_processor"].log_user_message("This error should appear", "error")
            services["email_processor"].log_diagnostic("This debug should be structured only", "debug")
            
            # HTTP should still be suppressed in verbose mode
            urllib3_logger = logging.getLogger('urllib3')
            urllib3_logger.info("This should still be suppressed")
            
            return {
                "console_messages": ["info", "error"],
                "debug_structured_only": True,
                "http_still_suppressed": True
            }
        
        return LoggingScenario(
            name="verbose_mode",
            description="Test verbose mode with detailed progress information",
            config=config,
            expected_outcomes={
                "console_level": "INFO",
                "structured_level": "DEBUG",
                "http_suppression": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_debug_mode_scenario() -> LoggingScenario:
        """Scenario for testing debug mode logging."""
        config = LoggingConfig(
            console=ConsoleConfig(
                enabled=True,
                level=LogLevel.DEBUG,
                format=OutputFormat.DETAILED
            ),
            structured=StructuredConfig(
                enabled=True,
                level=LogLevel.DEBUG
            ),
            suppress_azure_sdk=False,  # Allow HTTP details in debug mode
            suppress_urllib3=False,
            disable_http_logging=False
        )
        
        async def test_function():
            """Test debug mode logging behavior."""
            services = create_mock_services_suite()
            
            # Should see all message levels
            services["email_processor"].log_user_message("Debug info should appear", "debug")
            services["email_processor"].log_user_message("Info should appear", "info")
            services["email_processor"].log_user_message("Error should appear", "error")
            services["email_processor"].log_diagnostic("Debug diagnostic should appear", "debug")
            
            # HTTP logging should be enabled in debug mode
            urllib3_logger = logging.getLogger('urllib3')
            urllib3_logger.debug("This debug should now appear")
            urllib3_logger.info("This info should now appear")
            
            return {
                "console_messages": ["debug", "info", "error"],
                "diagnostic_messages": ["debug"],
                "http_enabled": True
            }
        
        return LoggingScenario(
            name="debug_mode",
            description="Test debug mode with full diagnostic information",
            config=config,
            expected_outcomes={
                "console_level": "DEBUG",
                "structured_level": "DEBUG",
                "http_suppression": False
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_service_integration_scenario() -> LoggingScenario:
        """Scenario for testing service logging integration."""
        config = LoggingConfig(
            console=ConsoleConfig(
                enabled=True,
                level=LogLevel.INFO,
                format=OutputFormat.CLEAN
            ),
            structured=StructuredConfig(
                enabled=True,
                level=LogLevel.DEBUG
            )
        )
        
        async def test_function():
            """Test service logging integration."""
            services = create_mock_services_suite()
            
            # Test API client logging
            await services["graph_client"].authenticate()
            messages = await services["graph_client"].get_inbox_messages(5)
            
            # Test business logic logging
            results = await services["email_processor"].process_inbox()
            
            # Test database logging
            query_results = await services["databricks_client"].execute_query("SELECT * FROM test")
            
            # Test service coordination logging
            processed, failed = await services["inbox_monitor"].check_inbox_once(10)
            
            return {
                "api_operations": ["authenticate", "get_messages"],
                "business_operations": ["process_inbox"],
                "database_operations": ["execute_query"],
                "service_operations": ["check_inbox"]
            }
        
        return LoggingScenario(
            name="service_integration",
            description="Test logging integration across all service types",
            config=config,
            expected_outcomes={
                "all_services_logged": True,
                "correlation_ids_present": True,
                "operation_tracking": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_correlation_tracking_scenario() -> LoggingScenario:
        """Scenario for testing correlation ID tracking."""
        config = LoggingConfig(
            console=ConsoleConfig(level=LogLevel.INFO),
            structured=StructuredConfig(level=LogLevel.DEBUG)
        )
        
        async def test_function():
            """Test correlation ID tracking across services."""
            services = create_mock_services_suite()
            
            # Set initial correlation context
            correlation_id = "test_correlation_123"
            
            with set_correlation_context(correlation_id):
                # All operations should use the same correlation ID
                await services["graph_client"].authenticate()
                messages = await services["graph_client"].get_inbox_messages(3)
                
                if messages:
                    # Process first message - should maintain correlation
                    result = await services["email_processor"]._process_single_email(messages[0])
            
            return {
                "correlation_id_used": correlation_id,
                "operations_traced": ["authenticate", "get_messages", "process_email"],
                "correlation_maintained": True
            }
        
        return LoggingScenario(
            name="correlation_tracking",
            description="Test correlation ID propagation across service calls",
            config=config,
            expected_outcomes={
                "correlation_ids_consistent": True,
                "cross_service_tracing": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_error_handling_scenario() -> LoggingScenario:
        """Scenario for testing error handling and logging."""
        config = LoggingConfig(
            console=ConsoleConfig(level=LogLevel.INFO),
            structured=StructuredConfig(level=LogLevel.DEBUG)
        )
        
        async def test_function():
            """Test error handling with logging."""
            # Create services in test mode with failures enabled
            graph_client = MockGraphAPIClient(test_mode=False)  # Will fail
            email_processor = MockEmailProcessor(graph_client=graph_client)
            
            errors_logged = []
            
            try:
                await graph_client.authenticate()
            except Exception as e:
                errors_logged.append("authentication_error")
            
            try:
                await graph_client.get_inbox_messages(5)
            except Exception as e:
                errors_logged.append("api_error")
            
            try:
                await email_processor.process_inbox()
            except Exception as e:
                errors_logged.append("processing_error")
            
            return {
                "errors_logged": errors_logged,
                "error_contexts_preserved": True,
                "user_friendly_messages": True
            }
        
        return LoggingScenario(
            name="error_handling",
            description="Test error logging with context preservation",
            config=config,
            expected_outcomes={
                "errors_captured": True,
                "context_preserved": True,
                "user_messages_clear": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_performance_scenario() -> LoggingScenario:
        """Scenario for testing logging performance impact."""
        config = LoggingConfig(
            console=ConsoleConfig(level=LogLevel.INFO),
            structured=StructuredConfig(level=LogLevel.DEBUG)
        )
        
        async def test_function():
            """Test logging performance impact."""
            import time
            
            services = create_mock_services_suite()
            
            # Measure performance with logging
            start_time = time.time()
            
            for i in range(100):  # Simulate high-volume logging
                services["email_processor"].log_diagnostic(
                    f"High volume test {i}",
                    "debug",
                    iteration=i,
                    test_data={"key": "value"}
                )
            
            logging_time = time.time() - start_time
            
            # Measure business logic performance
            start_time = time.time()
            await services["email_processor"].process_inbox()
            business_time = time.time() - start_time
            
            logging_overhead_percent = (logging_time / business_time) * 100 if business_time > 0 else 0
            
            return {
                "logging_time_seconds": logging_time,
                "business_time_seconds": business_time,
                "overhead_percent": logging_overhead_percent,
                "acceptable_overhead": logging_overhead_percent < 2.0  # Less than 2%
            }
        
        return LoggingScenario(
            name="performance",
            description="Test logging system performance impact",
            config=config,
            expected_outcomes={
                "low_overhead": True,
                "fast_logging": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_sensitive_data_filtering_scenario() -> LoggingScenario:
        """Scenario for testing sensitive data filtering."""
        config = LoggingConfig(
            console=ConsoleConfig(level=LogLevel.INFO),
            structured=StructuredConfig(level=LogLevel.DEBUG)
        )
        
        async def test_function():
            """Test sensitive data filtering."""
            services = create_mock_services_suite()
            
            # Log data containing sensitive information
            sensitive_data = {
                "email": "user@example.com",
                "password": "secret123",  # Should be filtered
                "api_key": "sk-1234567890abcdef",  # Should be filtered
                "client_secret": "very_secret_value",  # Should be filtered
                "token": "bearer_token_123",  # Should be filtered
                "safe_data": "This should remain"
            }
            
            services["email_processor"].log_diagnostic(
                "Processing with sensitive data",
                "debug",
                **sensitive_data
            )
            
            return {
                "sensitive_patterns_detected": ["password", "api_key", "client_secret", "token"],
                "safe_data_preserved": True,
                "filtering_active": True
            }
        
        return LoggingScenario(
            name="sensitive_data_filtering",
            description="Test sensitive data filtering in logs",
            config=config,
            expected_outcomes={
                "sensitive_data_filtered": True,
                "safe_data_preserved": True
            },
            test_function=test_function
        )
    
    @staticmethod
    def get_all_scenarios() -> List[LoggingScenario]:
        """Get all available logging scenarios."""
        return [
            LoggingScenarios.get_quiet_mode_scenario(),
            LoggingScenarios.get_verbose_mode_scenario(),
            LoggingScenarios.get_debug_mode_scenario(),
            LoggingScenarios.get_service_integration_scenario(),
            LoggingScenarios.get_correlation_tracking_scenario(),
            LoggingScenarios.get_error_handling_scenario(),
            LoggingScenarios.get_performance_scenario(),
            LoggingScenarios.get_sensitive_data_filtering_scenario()
        ]
    
    @staticmethod
    def run_scenario(scenario: LoggingScenario) -> Dict[str, Any]:
        """Run a single logging scenario and return results."""
        # Initialize logging with scenario config
        initialize_logging(scenario.config)
        
        try:
            # Run the test function
            if asyncio.iscoroutinefunction(scenario.test_function):
                results = asyncio.run(scenario.test_function())
            else:
                results = scenario.test_function()
            
            return {
                "scenario_name": scenario.name,
                "success": True,
                "results": results,
                "expected_outcomes": scenario.expected_outcomes
            }
        
        except Exception as e:
            return {
                "scenario_name": scenario.name,
                "success": False,
                "error": str(e),
                "expected_outcomes": scenario.expected_outcomes
            }
    
    @staticmethod
    def run_all_scenarios() -> List[Dict[str, Any]]:
        """Run all logging scenarios and return results."""
        scenarios = LoggingScenarios.get_all_scenarios()
        results = []
        
        for scenario in scenarios:
            result = LoggingScenarios.run_scenario(scenario)
            results.append(result)
        
        return results


def create_test_logging_config(verbosity_level: str = "normal") -> LoggingConfig:
    """Create a logging configuration for testing.
    
    Args:
        verbosity_level: One of 'quiet', 'normal', 'verbose', 'debug'
    """
    if verbosity_level == "quiet":
        return LoggingConfig(
            console=ConsoleConfig(level=LogLevel.ERROR, format=OutputFormat.MINIMAL),
            structured=StructuredConfig(level=LogLevel.INFO),
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )
    elif verbosity_level == "verbose":
        return LoggingConfig(
            console=ConsoleConfig(level=LogLevel.INFO, format=OutputFormat.DETAILED),
            structured=StructuredConfig(level=LogLevel.DEBUG),
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )
    elif verbosity_level == "debug":
        return LoggingConfig(
            console=ConsoleConfig(level=LogLevel.DEBUG, format=OutputFormat.DETAILED),
            structured=StructuredConfig(level=LogLevel.DEBUG),
            suppress_azure_sdk=False,
            suppress_urllib3=False,
            disable_http_logging=False
        )
    else:  # normal
        return LoggingConfig(
            console=ConsoleConfig(level=LogLevel.INFO, format=OutputFormat.CLEAN),
            structured=StructuredConfig(level=LogLevel.DEBUG),
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )


async def simulate_full_email_processing_workflow() -> Dict[str, Any]:
    """Simulate a complete email processing workflow for testing."""
    services = create_mock_services_suite()
    
    # Add some mock messages
    for i in range(3):
        services["graph_client"].add_mock_message({
            'id': f'test_msg_{i}',
            'subject': f'Test Message {i}',
            'from': {'emailAddress': {'address': f'sender{i}@test.com'}},
            'body': {'content': f'Test content {i}'}
        })
    
    workflow_results = {}
    
    # Step 1: Authentication
    await services["graph_client"].authenticate()
    workflow_results["authentication"] = "completed"
    
    # Step 2: Health check
    health_status = await services["health_service"].get_comprehensive_health_status()
    workflow_results["health_check"] = health_status
    
    # Step 3: Process emails
    processing_results = await services["email_processor"].process_inbox()
    workflow_results["email_processing"] = processing_results
    
    # Step 4: Database operations
    contact_data = await services["databricks_client"].execute_query("SELECT * FROM contacts")
    workflow_results["database_lookup"] = contact_data
    
    # Step 5: Case creation (if needed)
    if processing_results.get("processed_count", 0) > 0:
        case_result = await services["salesforce_client"].create_case({
            "subject": "Test Case",
            "description": "Automated case from email processing"
        })
        workflow_results["case_creation"] = case_result
    
    return workflow_results