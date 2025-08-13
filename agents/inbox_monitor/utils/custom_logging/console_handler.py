# utils/logging/console_handler.py
import logging
import sys
from typing import Dict, Optional, Any, TextIO, List
from io import StringIO
import threading
from datetime import datetime

from .config import ConsoleConfig, OutputFormat
from .exceptions import LogHandlerError


class ColorCodes:
    """ANSI color codes for console output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'


class ConsoleFormatter(logging.Formatter):
    """Custom formatter for clean console output."""
    
    LEVEL_COLORS = {
        logging.DEBUG: ColorCodes.CYAN,
        logging.INFO: ColorCodes.GREEN,
        logging.WARNING: ColorCodes.YELLOW,
        logging.ERROR: ColorCodes.RED,
        logging.CRITICAL: ColorCodes.BRIGHT_RED + ColorCodes.BOLD,
    }
    
    LEVEL_ICONS = {
        logging.DEBUG: '🔍',
        logging.INFO: 'ℹ️ ',
        logging.WARNING: '⚠️ ',
        logging.ERROR: '❌',
        logging.CRITICAL: '🚨',
    }
    
    def __init__(self, config: ConsoleConfig) -> None:
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output."""
        try:
            with self._lock:
                return self._format_safe(record)
        except Exception as e:
            # Fallback to basic formatting if custom formatting fails
            return f"[LOGGING ERROR] {record.getMessage()}"
    
    def _format_safe(self, record: logging.LogRecord) -> str:
        """Thread-safe formatting implementation."""
        if self.config.format == OutputFormat.MINIMAL:
            return self._format_minimal(record)
        elif self.config.format == OutputFormat.CLEAN:
            return self._format_clean(record)
        elif self.config.format == OutputFormat.DETAILED:
            return self._format_detailed(record)
        else:
            return self._format_clean(record)  # Default fallback
    
    def _format_minimal(self, record: logging.LogRecord) -> str:
        """Ultra-minimal output - just the message."""
        return record.getMessage()
    
    def _format_clean(self, record: logging.LogRecord) -> str:
        """Clean, user-friendly formatting."""
        parts = []
        
        # Add timestamp if enabled
        if self.config.timestamp_enabled:
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            parts.append(f'[{timestamp}]')
        
        # Add level icon
        if record.levelno in self.LEVEL_ICONS:
            parts.append(self.LEVEL_ICONS[record.levelno])
        
        # Add logger name if enabled and not root logger
        if self.config.show_logger_name and record.name != 'root':
            logger_name = record.name.split('.')[-1]  # Just the last part
            parts.append(f'({logger_name})')
        
        # Add the main message
        message = record.getMessage()
        
        # Apply color if enabled
        if self.config.color_enabled and sys.stdout.isatty():
            if record.levelno in self.LEVEL_COLORS:
                color = self.LEVEL_COLORS[record.levelno]
                message = f"{color}{message}{ColorCodes.RESET}"
        
        parts.append(message)
        
        return ' '.join(parts)
    
    def _format_detailed(self, record: logging.LogRecord) -> str:
        """Detailed formatting for debugging."""
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        parts = [
            f'[{timestamp}]',
            f'[{record.levelname}]',
            f'[{record.name}]',
            f'[{record.filename}:{record.lineno}]',
            record.getMessage()
        ]
        
        # Add exception info if present
        if record.exc_info:
            parts.append('\n' + self.formatException(record.exc_info))
        
        return ' '.join(parts)


class ConsoleHandler(logging.Handler):
    """Custom console handler with clean output formatting."""
    
    def __init__(self, config: ConsoleConfig, stream: Optional[TextIO] = None) -> None:
        super().__init__()
        self.config = config
        self.stream = stream or sys.stdout
        self.formatter = ConsoleFormatter(config)
        self._lock = threading.Lock()
        
        # Set the logging level
        if hasattr(config.level, 'value'):
            self.setLevel(config.level.value)
        else:
            self.setLevel(config.level)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the console."""
        # Check if this record should be processed by this handler
        if record.levelno < self.level:
            return
            
        try:
            with self._lock:
                msg = self.format(record)
                self.stream.write(msg + '\n')
                self.stream.flush()
        except Exception as e:
            # Handle logging errors gracefully
            try:
                self.handleError(record)
            except:
                # Last resort - at least try to indicate something went wrong
                sys.stderr.write(f"[CONSOLE LOGGING ERROR] {str(e)}\n")
                sys.stderr.flush()
    
    def handleError(self, record: logging.LogRecord) -> None:
        """Handle errors that occur during logging."""
        # Override parent's handleError to avoid recursive issues
        try:
            ei = sys.exc_info()
            if ei and ei[1]:
                sys.stderr.write(f"[CONSOLE HANDLER ERROR] {ei[1]}\n")
                sys.stderr.flush()
        except:
            pass  # Give up - don't create more problems
    
    def close(self) -> None:
        """Close the handler and release resources."""
        try:
            if hasattr(self.stream, 'close') and self.stream != sys.stdout and self.stream != sys.stderr:
                self.stream.close()
        finally:
            super().close()