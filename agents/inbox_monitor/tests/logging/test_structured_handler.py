# tests/logging/test_structured_handler.py
import pytest
import logging
import json
import sys
from io import StringIO
from datetime import datetime

from utils.custom_logging.structured_handler import StructuredHandler, StructuredFormatter
from utils.custom_logging.config import StructuredConfig, LogLevel
from .fixtures.log_samples import SAMPLE_MESSAGES, SAMPLE_STRUCTURED_DATA


class TestStructuredFormatter:
    """Test StructuredFormatter functionality."""
    
    @pytest.fixture
    def basic_config(self):
        """Basic structured configuration for testing."""
        return StructuredConfig(
            enabled=True,
            level=LogLevel.DEBUG,
            include_timestamp=True,
            include_logger_name=True,
            include_thread_info=False,
            include_process_info=False
        )
    
    @pytest.fixture
    def detailed_config(self):
        """Detailed structured configuration for testing."""
        return StructuredConfig(
            enabled=True,
            level=LogLevel.DEBUG,
            include_timestamp=True,
            include_logger_name=True,
            include_thread_info=True,
            include_process_info=True
        )
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_basic_json_formatting(self, basic_config):
        """Test basic JSON formatting."""
        formatter = StructuredFormatter(basic_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/path/test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        
        # Parse the JSON result
        log_data = json.loads(result)
        
        assert log_data["level"] == "info"
        assert log_data["message"] == "Test message"
        assert log_data["logger"] == "test_logger"
        assert "timestamp" in log_data
        assert log_data["source"]["file"] == "test.py"
        assert log_data["source"]["line"] == 10
        assert log_data["source"]["function"] == "test_function"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_timestamp_inclusion(self, basic_config):
        """Test timestamp inclusion/exclusion."""
        # Test with timestamp enabled
        formatter_with_ts = StructuredFormatter(basic_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        result = formatter_with_ts.format(record)
        log_data = json.loads(result)
        assert "timestamp" in log_data
        
        # Validate timestamp format
        timestamp = log_data["timestamp"]
        parsed_ts = datetime.fromisoformat(timestamp)
        assert isinstance(parsed_ts, datetime)
        
        # Test with timestamp disabled
        config_no_ts = StructuredConfig(include_timestamp=False)
        formatter_no_ts = StructuredFormatter(config_no_ts)
        
        result = formatter_no_ts.format(record)
        log_data = json.loads(result)
        assert "timestamp" not in log_data
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_logger_name_inclusion(self):
        """Test logger name inclusion/exclusion."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        # Test with logger name enabled
        config_with_name = StructuredConfig(include_logger_name=True)
        formatter_with_name = StructuredFormatter(config_with_name)
        
        result = formatter_with_name.format(record)
        log_data = json.loads(result)
        assert log_data["logger"] == "test_logger"
        
        # Test with logger name disabled
        config_no_name = StructuredConfig(include_logger_name=False)
        formatter_no_name = StructuredFormatter(config_no_name)
        
        result = formatter_no_name.format(record)
        log_data = json.loads(result)
        assert "logger" not in log_data
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_thread_info_inclusion(self, detailed_config):
        """Test thread info inclusion."""
        formatter = StructuredFormatter(detailed_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert "thread_id" in log_data
        assert "thread_name" in log_data
        assert isinstance(log_data["thread_id"], int)
        assert isinstance(log_data["thread_name"], str)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_process_info_inclusion(self, detailed_config):
        """Test process info inclusion."""
        formatter = StructuredFormatter(detailed_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert "process_id" in log_data
        assert "process_name" in log_data
        assert isinstance(log_data["process_id"], int)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_exception_formatting(self, basic_config):
        """Test exception information formatting."""
        formatter = StructuredFormatter(basic_config)
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
            record.filename = "test.py"
            record.funcName = "test_function"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert "exception" in log_data
        exception_data = log_data["exception"]
        assert exception_data["type"] == "ValueError"
        assert exception_data["message"] == "Test exception"
        assert isinstance(exception_data["traceback"], list)
        assert len(exception_data["traceback"]) > 0
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_extra_fields_handling(self, basic_config):
        """Test handling of extra fields in log records."""
        formatter = StructuredFormatter(basic_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        # Add extra fields
        record.user_id = 12345
        record.request_id = "req-abc123"
        record.metadata = {"key": "value"}
        record.non_serializable = set([1, 2, 3])  # Non-JSON serializable
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert "extra" in log_data
        extra_data = log_data["extra"]
        assert extra_data["user_id"] == 12345
        assert extra_data["request_id"] == "req-abc123"
        assert extra_data["metadata"] == {"key": "value"}
        assert extra_data["non_serializable"] == "{1, 2, 3}"  # Should be stringified
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_different_log_levels(self, basic_config):
        """Test formatting for different log levels."""
        formatter = StructuredFormatter(basic_config)
        
        levels = [
            (logging.DEBUG, "debug"),
            (logging.INFO, "info"),
            (logging.WARNING, "warning"),
            (logging.ERROR, "error"),
            (logging.CRITICAL, "critical")
        ]
        
        for python_level, expected_level in levels:
            record = logging.LogRecord(
                name="test_logger",
                level=python_level,
                pathname="test.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None
            )
            record.filename = "test.py"
            record.funcName = "test_function"
            
            result = formatter.format(record)
            log_data = json.loads(result)
            
            assert log_data["level"] == expected_level
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_formatting_error_handling(self, basic_config):
        """Test error handling when formatting fails."""
        formatter = StructuredFormatter(basic_config)
        
        # Create a problematic record that might cause formatting issues
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        # Mock the _format_safe method to raise an exception
        original_format_safe = formatter._format_safe
        
        def failing_format_safe(record):
            raise RuntimeError("Formatting failed")
        
        formatter._format_safe = failing_format_safe
        
        result = formatter.format(record)
        
        # Should fall back to basic JSON
        log_data = json.loads(result)
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert "formatting_error" in log_data
        
        # Restore original method
        formatter._format_safe = original_format_safe
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_json_serialization_check(self, basic_config):
        """Test JSON serialization checking."""
        formatter = StructuredFormatter(basic_config)
        
        # Test serializable values
        assert formatter._is_json_serializable("string") is True
        assert formatter._is_json_serializable(123) is True
        assert formatter._is_json_serializable([1, 2, 3]) is True
        assert formatter._is_json_serializable({"key": "value"}) is True
        assert formatter._is_json_serializable(None) is True
        assert formatter._is_json_serializable(True) is True
        
        # Test non-serializable values
        assert formatter._is_json_serializable(set([1, 2, 3])) is False
        assert formatter._is_json_serializable(lambda x: x) is False
        assert formatter._is_json_serializable(object()) is False


class TestStructuredHandler:
    """Test StructuredHandler functionality."""
    
    @pytest.fixture
    def structured_config(self):
        """Basic structured configuration for testing."""
        return StructuredConfig(
            enabled=True,
            level=LogLevel.DEBUG,
            include_timestamp=True,
            include_logger_name=True
        )
    
    @pytest.fixture
    def mock_stream(self):
        """Mock output stream for capturing output."""
        return StringIO()
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_handler_initialization(self, structured_config, mock_stream):
        """Test handler initialization."""
        handler = StructuredHandler(structured_config, stream=mock_stream)
        
        assert handler.config == structured_config
        assert handler.stream == mock_stream
        assert isinstance(handler.formatter, StructuredFormatter)
        assert handler.level == logging.DEBUG
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_basic_structured_output(self, structured_config, mock_stream):
        """Test basic structured output."""
        handler = StructuredHandler(structured_config, stream=mock_stream)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        handler.emit(record)
        
        output = mock_stream.getvalue()
        assert output.endswith('\n')  # Should end with newline
        
        # Parse the JSON output
        log_data = json.loads(output.strip())
        assert log_data["level"] == "info"
        assert log_data["message"] == "Test message"
        assert log_data["logger"] == "test_logger"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_multiple_structured_messages(self, structured_config, mock_stream):
        """Test multiple structured message output."""
        handler = StructuredHandler(structured_config, stream=mock_stream)
        
        for i, message in enumerate(SAMPLE_MESSAGES[:3]):
            record = logging.LogRecord(
                name=f"logger_{i}",
                level=logging.INFO,
                pathname="test.py",
                lineno=10 + i,
                msg=message,
                args=(),
                exc_info=None
            )
            record.filename = "test.py"
            record.funcName = f"function_{i}"
            handler.emit(record)
        
        output = mock_stream.getvalue()
        lines = [line for line in output.strip().split('\n') if line.strip()]
        
        assert len(lines) == 3
        
        for i, line in enumerate(lines):
            log_data = json.loads(line)
            assert log_data["message"] == SAMPLE_MESSAGES[i]
            assert log_data["logger"] == f"logger_{i}"
            assert log_data["source"]["line"] == 10 + i
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_error_handling(self, structured_config):
        """Test handler behavior when errors occur."""
        # Use a mock stream that raises an exception
        class FailingStream:
            def write(self, data):
                raise IOError("Stream write failed")
            def flush(self):
                pass
        
        handler = StructuredHandler(structured_config, stream=FailingStream())
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.filename = "test.py"
        record.funcName = "test_function"
        
        # This should not raise an exception
        handler.emit(record)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_level_filtering(self, mock_stream):
        """Test log level filtering."""
        config = StructuredConfig(level=LogLevel.WARNING)
        handler = StructuredHandler(config, stream=mock_stream)
        
        levels_and_messages = [
            (logging.DEBUG, "Debug message"),
            (logging.INFO, "Info message"),
            (logging.WARNING, "Warning message"),
            (logging.ERROR, "Error message")
        ]
        
        for level, message in levels_and_messages:
            record = logging.LogRecord(
                name="test_logger",
                level=level,
                pathname="test.py",
                lineno=10,
                msg=message,
                args=(),
                exc_info=None
            )
            record.filename = "test.py"
            record.funcName = "test_function"
            handler.emit(record)
        
        output = mock_stream.getvalue()
        lines = [line for line in output.split('\n') if line.strip()]
        
        # Should only have WARNING and ERROR messages (2 lines)
        assert len(lines) == 2
        
        warning_data = json.loads(lines[0])
        error_data = json.loads(lines[1])
        
        assert warning_data["message"] == "Warning message"
        assert warning_data["level"] == "warning"
        assert error_data["message"] == "Error message"
        assert error_data["level"] == "error"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_handler_cleanup(self, structured_config, mock_stream):
        """Test handler cleanup."""
        handler = StructuredHandler(structured_config, stream=mock_stream)
        
        # Test close method
        handler.close()
        
        # Should not raise an exception
        assert True
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_concurrent_structured_logging(self, structured_config, mock_stream):
        """Test concurrent logging to the same handler."""
        import threading
        
        handler = StructuredHandler(structured_config, stream=mock_stream)
        errors = []
        
        def log_messages(thread_id):
            try:
                for i in range(3):
                    record = logging.LogRecord(
                        name="test_logger",
                        level=logging.INFO,
                        pathname="test.py",
                        lineno=10,
                        msg=f"Thread {thread_id} message {i}",
                        args=(),
                        exc_info=None
                    )
                    record.filename = "test.py"
                    record.funcName = "test_function"
                    handler.emit(record)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=log_messages, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check for errors
        assert len(errors) == 0, f"Concurrent logging errors: {errors}"
        
        # Check output
        output = mock_stream.getvalue()
        lines = [line for line in output.split('\n') if line.strip()]
        
        # Should have 9 lines (3 threads × 3 messages)
        assert len(lines) == 9
        
        # Parse all lines and verify content
        parsed_lines = [json.loads(line) for line in lines]
        
        # Each thread's messages should be present
        for thread_id in range(3):
            for msg_id in range(3):
                expected_message = f"Thread {thread_id} message {msg_id}"
                assert any(log["message"] == expected_message for log in parsed_lines)