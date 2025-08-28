# config/cli_defaults.py
"""
CLI Default Configurations
==========================

This module provides CLI-specific default configurations for different environments
and verbosity levels. It implements the specifications from Phase 2 of the
inbox monitor logging cleanup implementation.
"""

from typing import Dict, Any
from utils.custom_logging import LogLevel, OutputFormat
from cli.environment_detector import EnvironmentType


# CLI verbosity defaults for different environment types
CLI_VERBOSITY_DEFAULTS: Dict[EnvironmentType, Dict[str, Any]] = {
    EnvironmentType.DEVELOPMENT: {
        "console_level": LogLevel.INFO,
        "console_format": OutputFormat.CLEAN,
        "structured_level": LogLevel.DEBUG,
        "console_enabled": True,
        "structured_enabled": True,
        "color_enabled": True,
        "timestamp_enabled": False,
        "show_logger_name": False,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "disable_http_logging": True
    },
    EnvironmentType.PRODUCTION: {
        "console_level": LogLevel.WARNING,
        "console_format": OutputFormat.MINIMAL,
        "structured_level": LogLevel.INFO,
        "console_enabled": False,  # Disabled by default in production
        "structured_enabled": True,
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "disable_http_logging": True
    },
    EnvironmentType.TESTING: {
        "console_level": LogLevel.WARNING,
        "console_format": OutputFormat.MINIMAL,
        "structured_level": LogLevel.DEBUG,
        "console_enabled": True,
        "structured_enabled": False,  # Reduce noise in tests
        "color_enabled": False,
        "timestamp_enabled": False,
        "show_logger_name": False,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "disable_http_logging": True
    },
    EnvironmentType.CONTAINERIZED: {
        "console_level": LogLevel.INFO,
        "console_format": OutputFormat.CLEAN,
        "structured_level": LogLevel.INFO,
        "console_enabled": False,  # Structured only in containers
        "structured_enabled": True,
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "disable_http_logging": True
    },
    EnvironmentType.KUBERNETES: {
        "console_level": LogLevel.INFO,
        "console_format": OutputFormat.JSON,
        "structured_level": LogLevel.INFO,
        "console_enabled": False,  # Structured only in K8s
        "structured_enabled": True,
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "disable_http_logging": True
    }
}

# CLI verbosity flag mappings
CLI_VERBOSITY_FLAG_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "quiet": {
        "console_level": LogLevel.WARNING,
        "console_format": OutputFormat.MINIMAL,
        "console_enabled": True,
        "color_enabled": False,
        "timestamp_enabled": False,
        "show_logger_name": False
    },
    "verbose": {
        "console_level": LogLevel.INFO,
        "console_format": OutputFormat.CLEAN,
        "console_enabled": True,
        "structured_enabled": True,
        "color_enabled": True,
        "timestamp_enabled": False,
        "show_logger_name": False
    },
    "debug": {
        "console_level": LogLevel.DEBUG,
        "console_format": OutputFormat.DETAILED,
        "structured_level": LogLevel.DEBUG,
        "console_enabled": True,
        "structured_enabled": True,
        "color_enabled": True,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "suppress_azure_sdk": False,
        "suppress_urllib3": False,
        "disable_http_logging": False
    }
}

# Output format specific defaults
OUTPUT_FORMAT_DEFAULTS: Dict[OutputFormat, Dict[str, Any]] = {
    OutputFormat.CLEAN: {
        "color_enabled": True,
        "timestamp_enabled": False,
        "show_logger_name": False,
        "include_thread_info": False
    },
    OutputFormat.JSON: {
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "include_thread_info": False,
        "structured_enabled": True
    },
    OutputFormat.DETAILED: {
        "color_enabled": True,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "include_thread_info": True,
        "include_process_info": True
    },
    OutputFormat.MINIMAL: {
        "color_enabled": False,
        "timestamp_enabled": False,
        "show_logger_name": False,
        "include_thread_info": False
    }
}

# Production safety overrides
PRODUCTION_SAFETY_OVERRIDES: Dict[str, Any] = {
    "force_structured_logging": True,
    "minimum_log_level": LogLevel.INFO,
    "require_log_retention": True,
    "disable_debug_flags_in_production": True,
    "enforce_structured_format": True
}

# Default CLI argument mappings
DEFAULT_CLI_CONFIG: Dict[str, Any] = {
    "console": {
        "enabled": True,
        "level": LogLevel.INFO.value,
        "format": OutputFormat.CLEAN.value,
        "color_enabled": True,
        "timestamp_enabled": False,
        "show_logger_name": False
    },
    "structured": {
        "enabled": True,
        "level": LogLevel.DEBUG.value,
        "format": "json",
        "include_timestamp": True,
        "include_logger_name": True,
        "include_thread_info": False,
        "include_process_info": False
    },
    "file": {
        "enabled": False,
        "level": LogLevel.DEBUG.value,
        "max_size_mb": 100,
        "backup_count": 5,
        "rotation_enabled": True
    },
    "environment": "development",
    "disable_http_logging": True,
    "suppress_azure_sdk": True,
    "suppress_urllib3": True,
    "async_logging": False,
    "buffer_size": 1000,
    "flush_interval_seconds": 1.0
}


def get_cli_defaults_for_environment(environment_type: EnvironmentType) -> Dict[str, Any]:
    """
    Get CLI default configuration for a specific environment type.
    
    Args:
        environment_type: The detected or specified environment type
        
    Returns:
        Dict containing the default configuration for the environment
    """
    return CLI_VERBOSITY_DEFAULTS.get(environment_type, CLI_VERBOSITY_DEFAULTS[EnvironmentType.DEVELOPMENT])


def get_verbosity_flag_overrides(verbosity_flag: str) -> Dict[str, Any]:
    """
    Get configuration overrides for a specific verbosity flag.
    
    Args:
        verbosity_flag: The verbosity flag ('quiet', 'verbose', 'debug')
        
    Returns:
        Dict containing the configuration overrides for the flag
    """
    return CLI_VERBOSITY_FLAG_OVERRIDES.get(verbosity_flag, {})


def get_output_format_defaults(output_format: OutputFormat) -> Dict[str, Any]:
    """
    Get default configuration for a specific output format.
    
    Args:
        output_format: The requested output format
        
    Returns:
        Dict containing the default configuration for the format
    """
    return OUTPUT_FORMAT_DEFAULTS.get(output_format, OUTPUT_FORMAT_DEFAULTS[OutputFormat.CLEAN])


def apply_production_safety_overrides(config: Dict[str, Any], is_production: bool) -> Dict[str, Any]:
    """
    Apply production safety overrides to configuration if in production.
    
    Args:
        config: The base configuration
        is_production: Whether we're in a production environment
        
    Returns:
        Configuration with production safety overrides applied
    """
    if not is_production:
        return config
    
    # Apply production safety overrides
    production_config = config.copy()
    
    # Ensure structured logging is enabled
    if PRODUCTION_SAFETY_OVERRIDES["force_structured_logging"]:
        production_config.setdefault("structured", {})["enabled"] = True
    
    # Enforce minimum log level
    min_level = PRODUCTION_SAFETY_OVERRIDES["minimum_log_level"]
    for handler in ["console", "structured", "file"]:
        if handler in production_config:
            current_level = LogLevel(production_config[handler].get("level", LogLevel.INFO.value))
            if current_level.value < min_level.value:
                production_config[handler]["level"] = min_level.value
    
    # Disable debug flags in production
    if PRODUCTION_SAFETY_OVERRIDES["disable_debug_flags_in_production"]:
        production_config["disable_http_logging"] = True
        production_config["suppress_azure_sdk"] = True
        production_config["suppress_urllib3"] = True
    
    return production_config


def get_help_examples() -> Dict[str, str]:
    """
    Get CLI help examples for different use cases.
    
    Returns:
        Dict mapping use case names to example commands
    """
    return {
        "quick_check": "python main.py check --quiet",
        "verbose_run": "python main.py run --verbose",
        "debug_status": "python main.py status --debug",
        "json_output": "python main.py check --format json",
        "minimal_output": "python main.py status --format minimal",
        "production_override": "python main.py run --environment production",
        "force_console": "python main.py check --force-console-logging",
        "custom_config": "python main.py run --config-file /path/to/config.yaml"
    }