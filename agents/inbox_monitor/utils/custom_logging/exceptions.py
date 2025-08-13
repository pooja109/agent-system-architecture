# utils/logging/exceptions.py
"""Custom exceptions for logging system."""


class LoggingException(Exception):
    """Base exception for all logging-related errors."""
    pass


class LoggingConfigurationError(LoggingException):
    """Raised when logging configuration is invalid."""
    pass


class LogHandlerError(LoggingException):
    """Raised when a log handler encounters an error."""
    pass


class LogFormatterError(LoggingException):
    """Raised when log formatting fails."""
    pass


class LoggerInitializationError(LoggingException):
    """Raised when logger initialization fails."""
    pass