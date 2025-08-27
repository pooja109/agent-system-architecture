# utils/logging/message_formatter.py
"""
Message formatting utilities for logging system.

This module provides utility classes for message formatting and styling,
allowing for consistent and extensible message formatting across different
logging handlers and output formats.
"""

import re
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, List
from datetime import datetime
from enum import Enum


class MessageSensitivity(str, Enum):
    """Sensitivity levels for message content."""
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class MessageFormatter(ABC):
    """
    Abstract base class for message formatters.
    
    This class provides the interface for all message formatters,
    ensuring consistent behavior across different formatting strategies.
    """
    
    @abstractmethod
    def format_message(self, message: str, **kwargs: Any) -> str:
        """
        Format a message according to the formatter's strategy.
        
        Args:
            message: The raw message to format
            **kwargs: Additional formatting parameters
            
        Returns:
            The formatted message string
        """
        pass
    
    @abstractmethod
    def supports_format(self, format_type: str) -> bool:
        """
        Check if this formatter supports the given format type.
        
        Args:
            format_type: The format type to check
            
        Returns:
            True if the format is supported, False otherwise
        """
        pass


class SensitiveDataRedactor:
    """
    Utility class for redacting sensitive information from log messages.
    
    This class provides methods to identify and redact common patterns
    of sensitive data such as passwords, API keys, email addresses, etc.
    """
    
    # Default patterns for sensitive data detection
    DEFAULT_PATTERNS = {
        'password': re.compile(r'(password|pwd|pass)[\s=:]+[^\s\n]+', re.IGNORECASE),
        'api_key': re.compile(r'(api[_-]?key|apikey|key)[\s=:]+[A-Za-z0-9+/=]{16,}', re.IGNORECASE),
        'token': re.compile(r'(token|bearer)[\s=:]+[A-Za-z0-9+/=]{16,}', re.IGNORECASE),
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
        'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
        'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
        'ip_address': re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    }
    
    def __init__(self, custom_patterns: Optional[Dict[str, re.Pattern]] = None) -> None:
        """
        Initialize the redactor with patterns.
        
        Args:
            custom_patterns: Additional patterns to use for redaction
        """
        self.patterns = self.DEFAULT_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)
    
    def redact_message(self, message: str, sensitivity: MessageSensitivity = MessageSensitivity.INTERNAL) -> str:
        """
        Redact sensitive information from a message.
        
        Args:
            message: The message to redact
            sensitivity: The sensitivity level determining what to redact
            
        Returns:
            The message with sensitive information redacted
        """
        if sensitivity == MessageSensitivity.PUBLIC:
            # Redact everything sensitive
            patterns_to_use = self.patterns
        elif sensitivity == MessageSensitivity.INTERNAL:
            # Redact secrets but keep internal info
            patterns_to_use = {k: v for k, v in self.patterns.items() 
                             if k in ['password', 'api_key', 'token']}
        elif sensitivity == MessageSensitivity.SENSITIVE:
            # Redact only high-sensitivity items
            patterns_to_use = {k: v for k, v in self.patterns.items() 
                             if k in ['password', 'api_key', 'token', 'credit_card', 'ssn']}
        else:  # SECRET
            # No redaction for secret level (internal debugging)
            return message
        
        result = message
        for pattern_name, pattern in patterns_to_use.items():
            result = pattern.sub(f'[REDACTED_{pattern_name.upper()}]', result)
        
        return result
    
    def add_pattern(self, name: str, pattern: re.Pattern) -> None:
        """
        Add a custom redaction pattern.
        
        Args:
            name: Name of the pattern
            pattern: Compiled regular expression pattern
        """
        self.patterns[name] = pattern


class ConsoleMessageFormatter(MessageFormatter):
    """
    Formatter for console/terminal output with styling and color support.
    
    This formatter provides clean, readable output suitable for human
    consumption with optional color coding and icons.
    """
    
    def __init__(self, 
                 use_colors: bool = True, 
                 use_icons: bool = True,
                 line_length: int = 120,
                 redactor: Optional[SensitiveDataRedactor] = None) -> None:
        """
        Initialize the console formatter.
        
        Args:
            use_colors: Whether to use ANSI color codes
            use_icons: Whether to use Unicode icons
            line_length: Maximum line length before wrapping
            redactor: Sensitive data redactor instance
        """
        self.use_colors = use_colors
        self.use_icons = use_icons
        self.line_length = line_length
        self.redactor = redactor or SensitiveDataRedactor()
    
    def format_message(self, message: str, **kwargs: Any) -> str:
        """
        Format a message for console output.
        
        Args:
            message: The message to format
            **kwargs: Additional parameters:
                - level: Log level string
                - timestamp: Timestamp string
                - logger_name: Logger name
                - sensitivity: Message sensitivity level
                
        Returns:
            Formatted message for console display
        """
        level = kwargs.get('level', 'info').lower()
        timestamp = kwargs.get('timestamp', '')
        logger_name = kwargs.get('logger_name', '')
        sensitivity = kwargs.get('sensitivity', MessageSensitivity.INTERNAL)
        
        # Redact sensitive information
        if isinstance(sensitivity, str):
            sensitivity = MessageSensitivity(sensitivity)
        
        formatted_message = self.redactor.redact_message(message, sensitivity)
        
        # Wrap long messages
        if len(formatted_message) > self.line_length:
            formatted_message = self._wrap_message(formatted_message)
        
        return formatted_message
    
    def supports_format(self, format_type: str) -> bool:
        """Check if this formatter supports the given format."""
        return format_type.lower() in ['console', 'terminal', 'clean', 'minimal', 'detailed']
    
    def _wrap_message(self, message: str) -> str:
        """
        Wrap long messages for better readability.
        
        Args:
            message: Message to wrap
            
        Returns:
            Wrapped message
        """
        lines = []
        current_line = ""
        words = message.split()
        
        for word in words:
            if len(current_line) + len(word) + 1 <= self.line_length:
                if current_line:
                    current_line += " "
                current_line += word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return '\n'.join(lines)


class StructuredMessageFormatter(MessageFormatter):
    """
    Formatter for structured JSON output with metadata enrichment.
    
    This formatter creates structured, machine-readable output suitable
    for log aggregation and analysis systems.
    """
    
    def __init__(self, 
                 include_metadata: bool = True,
                 redactor: Optional[SensitiveDataRedactor] = None) -> None:
        """
        Initialize the structured formatter.
        
        Args:
            include_metadata: Whether to include additional metadata
            redactor: Sensitive data redactor instance
        """
        self.include_metadata = include_metadata
        self.redactor = redactor or SensitiveDataRedactor()
    
    def format_message(self, message: str, **kwargs: Any) -> str:
        """
        Format a message as structured JSON.
        
        Args:
            message: The message to format
            **kwargs: Additional parameters for structured output
                
        Returns:
            JSON-formatted message string
        """
        sensitivity = kwargs.get('sensitivity', MessageSensitivity.INTERNAL)
        if isinstance(sensitivity, str):
            sensitivity = MessageSensitivity(sensitivity)
        
        # Redact sensitive information
        formatted_message = self.redactor.redact_message(message, sensitivity)
        
        # Build structured data
        structured_data = {
            'message': formatted_message,
            'formatted_at': datetime.now().isoformat(),
            'formatter': 'structured'
        }
        
        # Add metadata if requested
        if self.include_metadata:
            structured_data.update({
                'sensitivity_level': sensitivity.value,
                'original_length': len(message),
                'redacted': message != formatted_message
            })
        
        # Add any additional fields from kwargs
        for key, value in kwargs.items():
            if key not in ['sensitivity'] and self._is_json_serializable(value):
                structured_data[key] = value
        
        return json.dumps(structured_data, ensure_ascii=False, separators=(',', ':'))
    
    def supports_format(self, format_type: str) -> bool:
        """Check if this formatter supports the given format."""
        return format_type.lower() in ['json', 'structured', 'machine']
    
    def _is_json_serializable(self, value: Any) -> bool:
        """Check if a value is JSON serializable."""
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False


class MessageFormatterFactory:
    """
    Factory class for creating message formatters.
    
    This factory provides a centralized way to create and configure
    message formatters based on output requirements.
    """
    
    _formatters: Dict[str, type] = {
        'console': ConsoleMessageFormatter,
        'structured': StructuredMessageFormatter,
    }
    
    @classmethod
    def create_formatter(self, 
                        formatter_type: str, 
                        **kwargs: Any) -> MessageFormatter:
        """
        Create a message formatter of the specified type.
        
        Args:
            formatter_type: Type of formatter to create
            **kwargs: Configuration parameters for the formatter
            
        Returns:
            Configured message formatter instance
            
        Raises:
            ValueError: If formatter type is not supported
        """
        if formatter_type not in self._formatters:
            available = ', '.join(self._formatters.keys())
            raise ValueError(f"Unsupported formatter type '{formatter_type}'. "
                           f"Available types: {available}")
        
        formatter_class = self._formatters[formatter_type]
        return formatter_class(**kwargs)
    
    @classmethod
    def register_formatter(cls, name: str, formatter_class: type) -> None:
        """
        Register a custom formatter type.
        
        Args:
            name: Name to register the formatter under
            formatter_class: Formatter class to register
            
        Raises:
            TypeError: If formatter_class doesn't inherit from MessageFormatter
        """
        if not issubclass(formatter_class, MessageFormatter):
            raise TypeError("Formatter class must inherit from MessageFormatter")
        
        cls._formatters[name] = formatter_class
    
    @classmethod
    def get_available_formatters(cls) -> List[str]:
        """
        Get a list of available formatter types.
        
        Returns:
            List of available formatter type names
        """
        return list(cls._formatters.keys())


class MessageStyler:
    """
    Utility class for applying styling to messages.
    
    This class provides methods for applying consistent styling
    such as truncation, padding, and emphasis to messages.
    """
    
    @staticmethod
    def truncate(message: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate a message to a maximum length.
        
        Args:
            message: Message to truncate
            max_length: Maximum allowed length
            suffix: Suffix to add to truncated messages
            
        Returns:
            Truncated message
        """
        if len(message) <= max_length:
            return message
        
        if len(suffix) >= max_length:
            return suffix[:max_length]
        
        return message[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def pad(message: str, width: int, align: str = 'left', fill_char: str = ' ') -> str:
        """
        Pad a message to a specific width.
        
        Args:
            message: Message to pad
            width: Target width
            align: Alignment ('left', 'right', 'center')
            fill_char: Character to use for padding
            
        Returns:
            Padded message
        """
        if align == 'left':
            return message.ljust(width, fill_char)
        elif align == 'right':
            return message.rjust(width, fill_char)
        elif align == 'center':
            return message.center(width, fill_char)
        else:
            raise ValueError(f"Invalid alignment '{align}'. Use 'left', 'right', or 'center'.")
    
    @staticmethod
    def emphasize(message: str, emphasis_type: str = 'bold') -> str:
        """
        Apply emphasis styling to a message.
        
        Args:
            message: Message to emphasize
            emphasis_type: Type of emphasis ('bold', 'italic', 'underline')
            
        Returns:
            Message with emphasis applied
        """
        if emphasis_type == 'bold':
            return f"**{message}**"
        elif emphasis_type == 'italic':
            return f"*{message}*"
        elif emphasis_type == 'underline':
            return f"_{message}_"
        else:
            return message
    
    @staticmethod
    def highlight_keywords(message: str, keywords: List[str], marker: str = "**") -> str:
        """
        Highlight specific keywords in a message.
        
        Args:
            message: Message to process
            keywords: Keywords to highlight
            marker: Marker to use for highlighting
            
        Returns:
            Message with keywords highlighted
        """
        result = message
        for keyword in keywords:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            result = pattern.sub(f"{marker}{keyword}{marker}", result)
        return result


# Convenience functions for easy access
def create_console_formatter(**kwargs) -> ConsoleMessageFormatter:
    """Create a console message formatter with the given configuration."""
    return ConsoleMessageFormatter(**kwargs)


def create_structured_formatter(**kwargs) -> StructuredMessageFormatter:
    """Create a structured message formatter with the given configuration."""
    return StructuredMessageFormatter(**kwargs)


def create_redactor(custom_patterns: Optional[Dict[str, re.Pattern]] = None) -> SensitiveDataRedactor:
    """Create a sensitive data redactor with optional custom patterns."""
    return SensitiveDataRedactor(custom_patterns)