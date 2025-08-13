# tests/logging/test_console_handler.py
import pytest
import logging
from io import StringIO
import sys

from utils.custom_logging.console_handler import ConsoleHandler, ConsoleFormatter, ColorCodes
from utils.custom_logging.config import ConsoleConfig, OutputFormat, LogLevel
from .fixtures.log_samples import SAMPLE_MESSAGES


class TestColorCodes:
    """Test ColorCodes class."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_color_code_values(self):
        """Test that color codes are properly defined."""
        assert ColorCodes.RESET == '\033[0m'
        assert ColorCodes.BOLD == '\033[1m'
        assert ColorCodes.RED == '\033[31m'
        assert ColorCodes.GREEN == '\033[32m'
        assert ColorCodes.YELLOW == '\033[33m'
        assert ColorCodes.BLUE == '\033[34m'


class TestConsoleFormatter:
    """Test ConsoleFormatter functionality."""
    
    @pytest.fixture
    def clean_config(self):
        """Clean console configuration for testing."""
        return ConsoleConfig(
            enabled=True,
            level=LogLevel.INFO,
            format=OutputFormat.CLEAN,
            color_enabled=False,  # Disable for predictable test output
            timestamp_enabled=False,
            show_logger_name=False
        )
    
    @pytest.fixture
    def detailed_config(self):
        """Detailed console configuration for testing."""
        return ConsoleConfig(
            enabled=True,
            level=LogLevel.DEBUG,
            format=OutputFormat.DETAILED,
            color_enabled=False,
            timestamp_enabled=True,
            show_logger_name=True
        )
    
    @pytest.fixture
    def minimal_config(self):
        """Minimal console configuration for testing."""
        return ConsoleConfig(
            enabled=True,
            level=LogLevel.INFO,
            format=OutputFormat.MINIMAL,
            color_enabled=False
        )
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_clean_format(self, clean_config):
        """Test clean formatting."""
        formatter = ConsoleFormatter(clean_config)
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        assert "Test message" in result
        assert "ℹ️" in result  # Info icon should be present
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_minimal_format(self, minimal_config):
        """Test minimal formatting."""
        formatter = ConsoleFormatter(minimal_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        assert result == "Test message"  # Just the message, nothing else
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detailed_format(self, detailed_config):
        """Test detailed formatting."""
        formatter = ConsoleFormatter(detailed_config)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        assert "Test message" in result
        assert "[DEBUG]" in result
        assert "[test_logger]" in result
        assert "[test.py:10]" in result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_different_log_levels(self, clean_config):
        """Test formatting for different log levels."""
        formatter = ConsoleFormatter(clean_config)
        
        levels = [
            (logging.DEBUG, "🔍"),
            (logging.INFO, "ℹ️"),
            (logging.WARNING, "⚠️"),
            (logging.ERROR, "❌"),
            (logging.CRITICAL, "🚨")
        ]
        
        for level, expected_icon in levels:
            record = logging.LogRecord(
                name="test_logger",
                level=level,
                pathname="test.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            result = formatter.format(record)
            assert expected_icon in result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_exception_formatting(self, clean_config):
        """Test exception formatting."""
        formatter = ConsoleFormatter(clean_config)
        
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
            
            result = formatter.format(record)
            assert "Error occurred" in result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_thread_safety(self, clean_config):
        """Test thread safety of formatter."""
        import threading
        import time
        
        formatter = ConsoleFormatter(clean_config)
        results = []
        errors = []
        
        def format_message(message_id):
            try:
                record = logging.LogRecord(
                    name="test_logger",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=10,
                    msg=f"Message {message_id}",
                    args=(),
                    exc_info=None
                )
                result = formatter.format(record)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=format_message, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Formatting errors: {errors}"
        assert len(results) == 10
        
        # Each result should contain the appropriate message
        for i, result in enumerate(results):
            assert f"Message" in result


class TestConsoleHandler:
    """Test ConsoleHandler functionality."""
    
    @pytest.fixture
    def console_config(self):
        """Default console configuration for testing."""
        return ConsoleConfig(
            enabled=True,
            level=LogLevel.INFO,
            format=OutputFormat.CLEAN,
            color_enabled=False  # Disable for predictable test output
        )
    
    @pytest.fixture
    def mock_stream(self):
        """Mock output stream for capturing output."""
        return StringIO()
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_handler_initialization(self, console_config, mock_stream):
        """Test handler initialization."""
        handler = ConsoleHandler(console_config, stream=mock_stream)
        
        assert handler.config == console_config
        assert handler.stream == mock_stream
        assert isinstance(handler.formatter, ConsoleFormatter)
        assert handler.level == logging.INFO
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_basic_message_output(self, console_config, mock_stream):
        """Test basic message output."""
        handler = ConsoleHandler(console_config, stream=mock_stream)
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        handler.emit(record)
        
        output = mock_stream.getvalue()
        assert "Test message" in output
        assert "ℹ️" in output
        assert output.endswith('\n')  # Should end with newline
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_multiple_messages(self, console_config, mock_stream):
        """Test multiple message output."""
        handler = ConsoleHandler(console_config, stream=mock_stream)
        
        for i, message in enumerate(SAMPLE_MESSAGES[:5]):  # Test first 5 messages
            record = logging.LogRecord(
                name="test_logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg=message,
                args=(),
                exc_info=None
            )
            handler.emit(record)
        
        output = mock_stream.getvalue()
        lines = output.strip().split('\n')
        
        assert len(lines) == 5
        for i, message in enumerate(SAMPLE_MESSAGES[:5]):
            assert message in lines[i]
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_error_handling(self, console_config):
        """Test handler behavior when errors occur."""
        # Use a mock stream that raises an exception
        class FailingStream:
            def write(self, data):
                raise IOError("Stream write failed")
            def flush(self):
                pass
        
        handler = ConsoleHandler(console_config, stream=FailingStream())
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # This should not raise an exception
        handler.emit(record)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_level_filtering(self, mock_stream):
        """Test log level filtering."""
        config = ConsoleConfig(level=LogLevel.WARNING, color_enabled=False)
        handler = ConsoleHandler(config, stream=mock_stream)
        
        # Create records at different levels
        levels = [
            (logging.DEBUG, "Debug message"),
            (logging.INFO, "Info message"),
            (logging.WARNING, "Warning message"),
            (logging.ERROR, "Error message")
        ]
        
        for level, message in levels:
            record = logging.LogRecord(
                name="test_logger",
                level=level,
                pathname="test.py",
                lineno=10,
                msg=message,
                args=(),
                exc_info=None
            )
            handler.emit(record)
        
        output = mock_stream.getvalue()
        lines = [line for line in output.split('\n') if line.strip()]
        
        # Should only have WARNING and ERROR messages (2 lines)
        assert len(lines) == 2
        assert "Warning message" in output
        assert "Error message" in output
        assert "Debug message" not in output
        assert "Info message" not in output
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_handler_cleanup(self, console_config, mock_stream):
        """Test handler cleanup."""
        handler = ConsoleHandler(console_config, stream=mock_stream)
        
        # Test close method
        handler.close()
        
        # Should not raise an exception
        assert True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_concurrent_logging(self, console_config, mock_stream):
        """Test concurrent logging to the same handler."""
        import threading
        
        handler = ConsoleHandler(console_config, stream=mock_stream)
        errors = []
        
        def log_messages(thread_id):
            try:
                for i in range(5):
                    record = logging.LogRecord(
                        name="test_logger",
                        level=logging.INFO,
                        pathname="test.py",
                        lineno=10,
                        msg=f"Thread {thread_id} message {i}",
                        args=(),
                        exc_info=None
                    )
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
        
        # Should have 15 lines (3 threads × 5 messages)
        assert len(lines) == 15
        
        # Each thread's messages should be present
        for thread_id in range(3):
            for msg_id in range(5):
                expected_message = f"Thread {thread_id} message {msg_id}"
                assert any(expected_message in line for line in lines)