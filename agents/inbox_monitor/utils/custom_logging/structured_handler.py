# utils/logging/structured_handler.py
import logging
import json
import sys
import threading
from datetime import datetime
from typing import Dict, Any, Optional, TextIO, List
import traceback

from .config import StructuredConfig
from .exceptions import LogHandlerError


class StructuredFormatter(logging.Formatter):
    """Formatter for structured JSON logging."""
    
    def __init__(self, config: StructuredConfig) -> None:
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        try:
            with self._lock:
                return self._format_safe(record)
        except Exception as e:
            # Fallback to basic JSON if formatting fails
            fallback = {
                "level": record.levelname,
                "message": record.getMessage(),
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "logger": record.name,
                "formatting_error": str(e)
            }
            return json.dumps(fallback)
    
    def _format_safe(self, record: logging.LogRecord) -> str:
        """Thread-safe structured formatting."""
        log_data = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        
        # Add timestamp if configured
        if self.config.include_timestamp:
            log_data["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
        
        # Add logger name if configured
        if self.config.include_logger_name:
            log_data["logger"] = record.name
        
        # Add thread info if configured
        if self.config.include_thread_info:
            log_data["thread_id"] = record.thread
            log_data["thread_name"] = record.threadName
        
        # Add process info if configured
        if self.config.include_process_info:
            log_data["process_id"] = record.process
            log_data["process_name"] = record.processName
        
        # Add source location info
        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from LogRecord
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'message'):
                if self._is_json_serializable(value):
                    extra_fields[key] = value
                else:
                    extra_fields[key] = str(value)
        
        if extra_fields:
            log_data["extra"] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
    
    def _is_json_serializable(self, value: Any) -> bool:
        """Check if a value is JSON serializable."""
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False


class StructuredHandler(logging.Handler):
    """Handler for structured JSON logging output."""
    
    def __init__(self, config: StructuredConfig, stream: Optional[TextIO] = None) -> None:
        super().__init__()
        self.config = config
        self.stream = stream or sys.stdout
        self.formatter = StructuredFormatter(config)
        self._lock = threading.Lock()
        
        # Set the logging level
        if hasattr(config.level, 'value'):
            self.setLevel(config.level.value)
        else:
            self.setLevel(config.level)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a structured log record."""
        # Check if this record should be processed by this handler
        if record.levelno < self.level:
            return
            
        try:
            with self._lock:
                msg = self.format(record)
                self.stream.write(msg + '\n')
                self.stream.flush()
        except Exception as e:
            try:
                self.handleError(record)
            except:
                # Last resort fallback
                fallback_msg = json.dumps({
                    "level": "error",
                    "message": "Structured logging error",
                    "error": str(e),
                    "original_message": getattr(record, 'getMessage', lambda: 'Unknown')(),
                    "timestamp": datetime.now().isoformat()
                })
                sys.stderr.write(fallback_msg + '\n')
                sys.stderr.flush()
    
    def handleError(self, record: logging.LogRecord) -> None:
        """Handle errors that occur during structured logging."""
        try:
            ei = sys.exc_info()
            if ei and ei[1]:
                error_data = {
                    "level": "error",
                    "message": "Structured handler error",
                    "error_type": ei[0].__name__ if ei[0] else "Unknown",
                    "error_message": str(ei[1]) if ei[1] else "Unknown error",
                    "timestamp": datetime.now().isoformat(),
                    "logger": "structured_handler"
                }
                sys.stderr.write(json.dumps(error_data) + '\n')
                sys.stderr.flush()
        except:
            pass  # Ultimate fallback - don't create cascading errors
    
    def close(self) -> None:
        """Close the handler and release resources."""
        try:
            if hasattr(self.stream, 'close') and self.stream != sys.stdout and self.stream != sys.stderr:
                self.stream.close()
        finally:
            super().close()