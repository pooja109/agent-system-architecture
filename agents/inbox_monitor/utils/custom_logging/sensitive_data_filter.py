# utils/logging/sensitive_data_filter.py
"""Sensitive data filtering system for secure logging."""

import re
import json
from typing import Any, Dict, List, Optional, Pattern, Union


class SensitiveDataFilter:
    """Filters sensitive information from log messages and data structures."""
    
    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize the sensitive data filter.
        
        Args:
            custom_patterns: Additional regex patterns for sensitive data detection
        """
        self._patterns: List[Pattern] = []
        self._setup_default_patterns()
        
        if custom_patterns:
            for pattern in custom_patterns:
                self._patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def _setup_default_patterns(self) -> None:
        """Set up default patterns for common sensitive data types."""
        default_patterns = [
            # API Keys and tokens
            r'(?i)(api[_-]?key|access[_-]?token|secret[_-]?key|bearer[_-]?token)[\s]*[:=][\s]*[\'"]?([a-zA-Z0-9_\-]{16,})[\'"]?',
            
            # Azure-specific secrets
            r'(?i)(client[_-]?secret|subscription[_-]?key|storage[_-]?key)[\s]*[:=][\s]*[\'"]?([a-zA-Z0-9_\-/+]{20,})[\'"]?',
            
            # OAuth and JWT tokens
            r'(?i)(oauth[_-]?token|jwt[_-]?token|refresh[_-]?token)[\s]*[:=][\s]*[\'"]?([a-zA-Z0-9_\-\.]{20,})[\'"]?',
            
            # Database connection strings
            r'(?i)(connection[_-]?string|database[_-]?url)[\s]*[:=][\s]*[\'"]?([^\'"\s]{20,})[\'"]?',
            
            # Passwords
            r'(?i)(password|passwd|pwd)[\s]*[:=][\s]*[\'"]?([^\s\'"]{3,})[\'"]?',
            
            # Email addresses (partial redaction)
            r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            
            # Credit card numbers
            r'(?i)(card[_-]?number|cc[_-]?number|credit[_-]?card)[\s]*[:=][\s]*[\'"]?(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})[\'"]?',
            
            # Phone numbers
            r'(?i)(phone|telephone|mobile)[\s]*[:=][\s]*[\'"]?(\+?1?[\s\-\.]?\(?[0-9]{3}\)?[\s\-\.]?[0-9]{3}[\s\-\.]?[0-9]{4})[\'"]?',
            
            # Social Security Numbers
            r'(?i)(ssn|social[_-]?security)[\s]*[:=][\s]*[\'"]?(\d{3}[\s\-]?\d{2}[\s\-]?\d{4})[\'"]?',
            
            # IP Addresses (in sensitive contexts)
            r'(?i)(private[_-]?ip|internal[_-]?ip)[\s]*[:=][\s]*[\'"]?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\'"]?'
        ]
        
        for pattern in default_patterns:
            self._patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def filter_string(self, text: str) -> str:
        """
        Filter sensitive data from a string.
        
        Args:
            text: The text to filter
            
        Returns:
            Text with sensitive data redacted
        """
        if not isinstance(text, str):
            return str(text)
        
        filtered_text = text
        
        for pattern in self._patterns:
            if pattern.groups >= 2:
                # Pattern has capture groups - redact the sensitive value
                def redact_match(match):
                    groups = match.groups()
                    if len(groups) >= 2:
                        key = groups[0]  # The field name
                        value = groups[1]  # The sensitive value
                        # Keep first and last few characters for debugging
                        if len(value) > 8:
                            redacted = value[:2] + '*' * (len(value) - 4) + value[-2:]
                        elif len(value) > 4:
                            redacted = value[0] + '*' * (len(value) - 2) + value[-1]
                        else:
                            redacted = '*' * len(value)
                        
                        # Reconstruct the match with redacted value
                        prefix = match.group(0)[:match.start(2) - match.start(0)]
                        suffix = match.group(0)[match.end(2) - match.start(0):]
                        return prefix + redacted + suffix
                    return match.group(0)
                
                filtered_text = pattern.sub(redact_match, filtered_text)
            else:
                # Simple pattern - replace entire match
                filtered_text = pattern.sub('[REDACTED]', filtered_text)
        
        return filtered_text
    
    def filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive data from a dictionary.
        
        Args:
            data: Dictionary to filter
            
        Returns:
            Dictionary with sensitive data redacted
        """
        if not isinstance(data, dict):
            return data
        
        filtered_data = {}
        
        for key, value in data.items():
            # Check if the key itself indicates sensitive data
            if self._is_sensitive_key(key):
                if isinstance(value, str) and len(value) > 4:
                    filtered_data[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    filtered_data[key] = '[REDACTED]'
            elif isinstance(value, str):
                filtered_data[key] = self.filter_string(value)
            elif isinstance(value, dict):
                filtered_data[key] = self.filter_dict(value)
            elif isinstance(value, (list, tuple)):
                filtered_data[key] = self.filter_list(value)
            else:
                filtered_data[key] = value
        
        return filtered_data
    
    def filter_list(self, data: List[Any]) -> List[Any]:
        """
        Filter sensitive data from a list.
        
        Args:
            data: List to filter
            
        Returns:
            List with sensitive data redacted
        """
        if not isinstance(data, (list, tuple)):
            return data
        
        filtered_data = []
        
        for item in data:
            if isinstance(item, str):
                filtered_data.append(self.filter_string(item))
            elif isinstance(item, dict):
                filtered_data.append(self.filter_dict(item))
            elif isinstance(item, (list, tuple)):
                filtered_data.append(self.filter_list(item))
            else:
                filtered_data.append(item)
        
        return filtered_data
    
    def filter_any(self, data: Any) -> Any:
        """
        Filter sensitive data from any data structure.
        
        Args:
            data: Data to filter
            
        Returns:
            Data with sensitive data redacted
        """
        if isinstance(data, str):
            return self.filter_string(data)
        elif isinstance(data, dict):
            return self.filter_dict(data)
        elif isinstance(data, (list, tuple)):
            return self.filter_list(data)
        else:
            return data
    
    def _is_sensitive_key(self, key: str) -> bool:
        """
        Check if a dictionary key indicates sensitive data.
        
        Args:
            key: The key to check
            
        Returns:
            True if the key indicates sensitive data
        """
        sensitive_keys = {
            'password', 'passwd', 'pwd', 'secret', 'key', 'token', 'auth',
            'credential', 'api_key', 'access_token', 'refresh_token',
            'client_secret', 'connection_string', 'database_url',
            'private_key', 'public_key', 'certificate', 'ssn', 
            'social_security', 'credit_card', 'cc_number', 'card_number'
        }
        
        key_lower = key.lower()
        return any(sensitive_key in key_lower for sensitive_key in sensitive_keys)
    
    def add_pattern(self, pattern: str) -> None:
        """
        Add a custom sensitive data pattern.
        
        Args:
            pattern: Regex pattern for sensitive data
        """
        self._patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def filter_json_string(self, json_string: str) -> str:
        """
        Filter sensitive data from a JSON string.
        
        Args:
            json_string: JSON string to filter
            
        Returns:
            JSON string with sensitive data redacted
        """
        try:
            data = json.loads(json_string)
            filtered_data = self.filter_any(data)
            return json.dumps(filtered_data)
        except json.JSONDecodeError:
            # If it's not valid JSON, treat as regular string
            return self.filter_string(json_string)


class LogMessageFilter:
    """Filter for log messages that automatically redacts sensitive data."""
    
    def __init__(self, sensitive_filter: Optional[SensitiveDataFilter] = None):
        """
        Initialize the log message filter.
        
        Args:
            sensitive_filter: Optional SensitiveDataFilter instance
        """
        self.sensitive_filter = sensitive_filter or SensitiveDataFilter()
    
    def filter(self, record):
        """
        Filter log record to redact sensitive data.
        
        Args:
            record: LogRecord to filter
            
        Returns:
            True to allow the record through
        """
        # Filter the main message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.sensitive_filter.filter_string(record.msg)
        
        # Filter any extra data
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key.startswith('_') or key in ['name', 'levelno', 'levelname', 'pathname', 
                                                 'filename', 'module', 'lineno', 'funcName',
                                                 'created', 'msecs', 'relativeCreated', 'thread',
                                                 'threadName', 'processName', 'process', 'getMessage']:
                    continue  # Skip built-in log record attributes
                
                if isinstance(value, str):
                    setattr(record, key, self.sensitive_filter.filter_string(value))
                elif isinstance(value, dict):
                    setattr(record, key, self.sensitive_filter.filter_dict(value))
                elif isinstance(value, (list, tuple)):
                    setattr(record, key, self.sensitive_filter.filter_list(value))
        
        return True


# Global sensitive data filter instance
_global_filter = SensitiveDataFilter()


def get_global_filter() -> SensitiveDataFilter:
    """Get the global sensitive data filter instance."""
    return _global_filter


def filter_sensitive_data(data: Any) -> Any:
    """
    Convenience function to filter sensitive data using the global filter.
    
    Args:
        data: Data to filter
        
    Returns:
        Data with sensitive data redacted
    """
    return _global_filter.filter_any(data)


def add_sensitive_pattern(pattern: str) -> None:
    """
    Add a pattern to the global sensitive data filter.
    
    Args:
        pattern: Regex pattern for sensitive data detection
    """
    _global_filter.add_pattern(pattern)


def create_log_message_filter(custom_patterns: Optional[List[str]] = None) -> LogMessageFilter:
    """
    Create a log message filter for use with Python logging.
    
    Args:
        custom_patterns: Optional custom patterns for sensitive data
        
    Returns:
        LogMessageFilter instance for use with logger.addFilter()
        
    Example:
        import logging
        logger = logging.getLogger('my_service')
        message_filter = create_log_message_filter()
        logger.addFilter(message_filter.filter)
    """
    sensitive_filter = SensitiveDataFilter(custom_patterns) if custom_patterns else _global_filter
    return LogMessageFilter(sensitive_filter)