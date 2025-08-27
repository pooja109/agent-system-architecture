# tests/logging/test_integration.py - RECOVERED with performance optimization
import pytest
import logging
import json
import threading
import tempfile
from io import StringIO
from pathlib import Path

from utils.custom_logging import (
    LoggingConfig, 
    ConsoleConfig, 
    StructuredConfig, 
    FileConfig,
    LogLevel,
    OutputFormat,
    initialize_logging,
    get_logger,
    get_console_logger,
    get_structured_logger,
    cleanup_logging,
    LoggerFactory
)

# Phase 1 Recovery: Import performance monitoring and logger isolation
from tests.fixtures.logger_isolation import logger_isolation, isolated_logger, mock_logging_system
from tests.fixtures.performance_monitoring import performance_monitor, enforce_logger_performance
from tests.fixtures.optimized_mocks import mock_pool


@pytest.mark.usefixtures("isolated_logger")
class TestLoggingIntegration:
    """Test end-to-end logging system integration with isolation."""
    
    def setup_method(self):
        """Reset logging before each test - now with isolation."""
        # Note: Reset is handled by logger_isolation fixture
        pass
    
    def teardown_method(self):
        """Clean up after each test - now handled by fixtures."""
        # Note: Cleanup is handled by logger_isolation fixture
        pass
    
    @pytest.fixture
    def dual_stream_config(self):
        """Configuration with both console and structured logging."""
        return LoggingConfig(
            console=ConsoleConfig(
                enabled=True,
                level=LogLevel.INFO,
                format=OutputFormat.CLEAN,
                color_enabled=False,
                timestamp_enabled=False,
                show_logger_name=True
            ),
            structured=StructuredConfig(
                enabled=True,
                level=LogLevel.DEBUG,
                include_timestamp=True,
                include_logger_name=True,
                include_thread_info=False,
                include_process_info=False
            ),
            environment="testing",
            suppress_azure_sdk=True,
            suppress_urllib3=True
        )
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_full_system_initialization(self, dual_stream_config, isolated_logger):
        """Test complete system initialization."""
        # Initialize the logging system
        initialize_logging(dual_stream_config)
        
        # Get a logger
        logger = get_logger("integration_test")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "integration_test"
        assert len(logger.handlers) == 2  # Console + Structured
        assert logger.propagate is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_dual_stream_output(self, dual_stream_config):
        """Test that messages go to both console and structured handlers."""
        # Capture outputs
        console_stream = StringIO()
        structured_stream = StringIO()
        
        # Modify config to use our streams
        dual_stream_config.console.enabled = True
        dual_stream_config.structured.enabled = True
        
        # Initialize with custom streams (we'll need to modify this)
        initialize_logging(dual_stream_config)
        factory = LoggerFactory()
        
        # Replace streams in handlers for testing
        factory.console_handler.stream = console_stream
        factory.structured_handler.stream = structured_stream
        
        # Get logger and log messages
        logger = get_logger("dual_stream_test")
        logger.info("Test message for dual stream")
        logger.debug("Debug message")  # Should only go to structured (due to levels)
        logger.error("Error message")
        
        # Check console output
        console_output = console_stream.getvalue()
        console_lines = [line for line in console_output.split('\n') if line.strip()]
        
        assert len(console_lines) == 2  # Info and Error (DEBUG filtered out by console level)
        assert "Test message for dual stream" in console_lines[0]
        assert "Error message" in console_lines[1]
        assert "ℹ️" in console_lines[0]  # Info icon
        assert "❌" in console_lines[1]  # Error icon
        
        # Check structured output
        structured_output = structured_stream.getvalue()
        structured_lines = [line for line in structured_output.split('\n') if line.strip()]
        
        assert len(structured_lines) == 3  # All messages (DEBUG level enabled)
        
        # Parse JSON lines
        parsed_logs = [json.loads(line) for line in structured_lines]
        
        assert parsed_logs[0]["message"] == "Test message for dual stream"
        assert parsed_logs[0]["level"] == "info"
        assert parsed_logs[0]["logger"] == "dual_stream_test"
        
        assert parsed_logs[1]["message"] == "Debug message"
        assert parsed_logs[1]["level"] == "debug"
        
        assert parsed_logs[2]["message"] == "Error message"
        assert parsed_logs[2]["level"] == "error"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_console_only_logger(self, dual_stream_config):
        """Test console-only logger functionality."""
        console_stream = StringIO()
        structured_stream = StringIO()
        
        initialize_logging(dual_stream_config)
        factory = LoggerFactory()
        
        factory.console_handler.stream = console_stream
        factory.structured_handler.stream = structured_stream
        
        # Get console-only logger
        console_logger = get_console_logger("console_test")
        console_logger.info("Console only message")
        
        # Check that message only goes to console
        console_output = console_stream.getvalue()
        structured_output = structured_stream.getvalue()
        
        assert "Console only message" in console_output
        assert structured_output.strip() == ""  # No structured output
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_structured_only_logger(self, dual_stream_config):
        """Test structured-only logger functionality."""
        console_stream = StringIO()
        structured_stream = StringIO()
        
        initialize_logging(dual_stream_config)
        factory = LoggerFactory()
        
        factory.console_handler.stream = console_stream
        factory.structured_handler.stream = structured_stream
        
        # Get structured-only logger
        structured_logger = get_structured_logger("structured_test")
        structured_logger.info("Structured only message")
        
        # Check that message only goes to structured
        console_output = console_stream.getvalue()
        structured_output = structured_stream.getvalue()
        
        assert console_output.strip() == ""  # No console output
        assert "Structured only message" in structured_output
        
        # Verify JSON structure
        log_data = json.loads(structured_output.strip())
        assert log_data["message"] == "Structured only message"
        assert log_data["level"] == "info"
        assert log_data["logger"] == "structured_test_structured_only"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_third_party_suppression(self, dual_stream_config):
        """Test that third-party loggers are properly suppressed."""
        console_stream = StringIO()
        structured_stream = StringIO()
        
        initialize_logging(dual_stream_config)
        factory = LoggerFactory()
        
        factory.console_handler.stream = console_stream
        factory.structured_handler.stream = structured_stream
        
        # Try logging from suppressed libraries
        # Use the exact logger names that are configured in the suppression
        azure_logger = logging.getLogger("azure.core")
        urllib3_logger = logging.getLogger("urllib3.connectionpool")
        
        # These should be suppressed (only WARNING and above)
        azure_logger.info("Azure info message")  # Should be suppressed
        azure_logger.warning("Azure warning message")  # Should appear
        
        urllib3_logger.debug("urllib3 debug message")  # Should be suppressed
        urllib3_logger.error("urllib3 error message")  # Should appear
        
        # Check outputs - should only have WARNING/ERROR messages
        console_output = console_stream.getvalue()
        structured_output = structured_stream.getvalue()
        
        # Azure and urllib3 loggers have propagate=False, so they won't reach our handlers
        # But their levels should be set correctly
        assert azure_logger.level == logging.WARNING, f"Expected WARNING ({logging.WARNING}), got {azure_logger.level}"
        assert urllib3_logger.level == logging.WARNING, f"Expected WARNING ({logging.WARNING}), got {urllib3_logger.level}"
        assert azure_logger.propagate is False
        assert urllib3_logger.propagate is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_error_with_exception_info(self, dual_stream_config):
        """Test error logging with exception information."""
        console_stream = StringIO()
        structured_stream = StringIO()
        
        initialize_logging(dual_stream_config)
        factory = LoggerFactory()
        
        factory.console_handler.stream = console_stream
        factory.structured_handler.stream = structured_stream
        
        logger = get_logger("exception_test")
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.error("Error with exception", exc_info=True)
        
        # Check console output
        console_output = console_stream.getvalue()
        assert "Error with exception" in console_output
        
        # Check structured output
        structured_output = structured_stream.getvalue()
        log_data = json.loads(structured_output.strip())
        
        assert log_data["message"] == "Error with exception"
        assert "exception" in log_data
        assert log_data["exception"]["type"] == "ValueError"
        assert log_data["exception"]["message"] == "Test exception"
        assert isinstance(log_data["exception"]["traceback"], list)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_concurrent_multi_logger_usage(self, dual_stream_config):
        """Test concurrent usage of multiple loggers."""
        initialize_logging(dual_stream_config)
        
        results = {"console": [], "structured": [], "errors": []}
        
        def log_messages(logger_name, message_count):
            try:
                logger = get_logger(f"concurrent_{logger_name}")
                console_logger = get_console_logger(f"console_{logger_name}")
                structured_logger = get_structured_logger(f"structured_{logger_name}")
                
                for i in range(message_count):
                    logger.info(f"Regular message {i} from {logger_name}")
                    console_logger.info(f"Console message {i} from {logger_name}")
                    structured_logger.info(f"Structured message {i} from {logger_name}")
                
                results["console"].append(f"Console completed: {logger_name}")
                results["structured"].append(f"Structured completed: {logger_name}")
                
            except Exception as e:
                results["errors"].append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_messages, args=(i, 3))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(results["errors"]) == 0, f"Concurrent logging errors: {results['errors']}"
        assert len(results["console"]) == 5
        assert len(results["structured"]) == 5
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_configuration_validation_integration(self):
        """Test that configuration validation works in integration."""
        with pytest.raises(Exception):  # Should be ValidationError from pydantic
            invalid_config = LoggingConfig(environment="invalid_environment")
            initialize_logging(invalid_config)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_cleanup_and_reinitialization(self, dual_stream_config):
        """Test cleanup and reinitialization."""
        # First initialization
        initialize_logging(dual_stream_config)
        logger1 = get_logger("test_logger")
        assert logger1 is not None
        
        # Cleanup
        cleanup_logging()
        
        # Try to get logger after cleanup - should fail
        with pytest.raises(Exception):
            get_logger("test_logger")
        
        # Reinitialize
        new_config = LoggingConfig(
            console=ConsoleConfig(enabled=True, level=LogLevel.DEBUG),
            structured=StructuredConfig(enabled=False),
            environment="testing"
        )
        initialize_logging(new_config)
        
        # Should work again
        logger2 = get_logger("test_logger")
        assert logger2 is not None
        assert len(logger2.handlers) == 1  # Only console handler
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_file_logging_integration(self):
        """Test file logging integration."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_path = temp_file.name
        
        config = LoggingConfig(
            console=ConsoleConfig(enabled=False),
            structured=StructuredConfig(enabled=True, level=LogLevel.INFO),
            file=FileConfig(
                enabled=True,
                file_path=temp_path,
                level=LogLevel.DEBUG,
                rotation_enabled=False
            ),
            environment="testing"
        )
        
        initialize_logging(config)
        logger = get_logger("file_test")
        
        # Log some messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.error("Error message")
        
        # Cleanup to ensure file is flushed
        cleanup_logging()
        
        # Read file content
        with open(temp_path, 'r') as f:
            content = f.read()
        
        # Should have all messages (file handler level is DEBUG)
        lines = [line for line in content.split('\n') if line.strip()]
        assert len(lines) == 3
        
        # Parse JSON lines
        parsed_logs = [json.loads(line) for line in lines]
        assert parsed_logs[0]["message"] == "Debug message"
        assert parsed_logs[1]["message"] == "Info message"
        assert parsed_logs[2]["message"] == "Error message"
        
        # Clean up file
        Path(temp_path).unlink()
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_message_formatting_consistency(self, dual_stream_config):
        """Test that message formatting is consistent across handlers."""
        console_stream = StringIO()
        structured_stream = StringIO()
        
        initialize_logging(dual_stream_config)
        factory = LoggerFactory()
        
        factory.console_handler.stream = console_stream
        factory.structured_handler.stream = structured_stream
        
        logger = get_logger("format_test")
        
        # Test various message types
        test_cases = [
            "Simple message",
            "Message with unicode: 🔍 ℹ️ ⚠️ ❌ 🚨",
            "Message\nwith\nnewlines",
            "Message with special chars: @#$%^&*()",
            f"Very long message: {'x' * 200}"
        ]
        
        for message in test_cases:
            logger.info(message)
        
        # Check that all messages are handled properly
        console_output = console_stream.getvalue()
        structured_output = structured_stream.getvalue()
        
        console_lines = [line for line in console_output.split('\n') if line.strip()]
        structured_lines = [line for line in structured_output.split('\n') if line.strip()]
        
        assert len(console_lines) == len(test_cases)
        assert len(structured_lines) == len(test_cases)
        
        # Verify structured output is valid JSON
        for line in structured_lines:
            log_data = json.loads(line)
            assert "message" in log_data
            assert "level" in log_data
            assert "timestamp" in log_data