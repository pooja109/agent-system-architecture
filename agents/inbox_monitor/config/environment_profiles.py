# config/environment_profiles.py
"""
Environment-Specific Configuration Profiles
===========================================

This module provides pre-configured logging profiles for different deployment
environments. Each profile is optimized for the specific characteristics and
requirements of its target environment.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from utils.custom_logging import LoggingConfig, LogLevel, OutputFormat
from cli.environment_detector import EnvironmentType, ContainerType


@dataclass
class EnvironmentProfile:
    """Represents a complete environment-specific configuration profile."""
    name: str
    description: str
    console_config: Dict[str, Any]
    structured_config: Dict[str, Any]
    file_config: Dict[str, Any]
    global_config: Dict[str, Any]
    production_ready: bool = False
    requires_validation: bool = True


# Development Environment Profile
DEVELOPMENT_PROFILE = EnvironmentProfile(
    name="development",
    description="Optimized for local development with rich console output and debugging capabilities",
    console_config={
        "enabled": True,
        "level": LogLevel.INFO.value,
        "format": OutputFormat.CLEAN.value,
        "color_enabled": True,
        "timestamp_enabled": False,
        "show_logger_name": False,
        "show_thread_info": False,
        "show_process_info": False
    },
    structured_config={
        "enabled": True,
        "level": LogLevel.DEBUG.value,
        "format": "json",
        "include_timestamp": True,
        "include_logger_name": True,
        "include_thread_info": False,
        "include_process_info": False,
        "include_source_info": True
    },
    file_config={
        "enabled": False,
        "level": LogLevel.DEBUG.value,
        "file_path": "logs/inbox_monitor_dev.log",
        "max_size_mb": 50,
        "backup_count": 3,
        "rotation_enabled": True
    },
    global_config={
        "disable_http_logging": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "async_logging": False,
        "buffer_size": 100,
        "flush_interval_seconds": 0.5,
        "performance_monitoring": True
    },
    production_ready=False,
    requires_validation=False
)

# Production Environment Profile
PRODUCTION_PROFILE = EnvironmentProfile(
    name="production",
    description="Optimized for production deployments with structured logging and performance focus",
    console_config={
        "enabled": False,  # Console disabled by default in production
        "level": LogLevel.WARNING.value,
        "format": OutputFormat.MINIMAL.value,
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "show_thread_info": True,
        "show_process_info": True
    },
    structured_config={
        "enabled": True,
        "level": LogLevel.INFO.value,
        "format": "json",
        "include_timestamp": True,
        "include_logger_name": True,
        "include_thread_info": True,
        "include_process_info": True,
        "include_source_info": False,  # Reduce overhead in production
        "include_correlation_id": True
    },
    file_config={
        "enabled": True,
        "level": LogLevel.INFO.value,
        "file_path": "/var/log/inbox_monitor/app.log",
        "max_size_mb": 500,
        "backup_count": 10,
        "rotation_enabled": True,
        "compression_enabled": True
    },
    global_config={
        "disable_http_logging": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "async_logging": True,
        "buffer_size": 1000,
        "flush_interval_seconds": 2.0,
        "performance_monitoring": True,
        "error_aggregation": True,
        "alert_on_errors": True
    },
    production_ready=True,
    requires_validation=True
)

# Testing Environment Profile
TESTING_PROFILE = EnvironmentProfile(
    name="testing",
    description="Optimized for test environments with minimal noise and fast execution",
    console_config={
        "enabled": True,
        "level": LogLevel.WARNING.value,
        "format": OutputFormat.MINIMAL.value,
        "color_enabled": False,
        "timestamp_enabled": False,
        "show_logger_name": False,
        "show_thread_info": False,
        "show_process_info": False
    },
    structured_config={
        "enabled": False,  # Reduce test noise
        "level": LogLevel.DEBUG.value,
        "format": "json",
        "include_timestamp": False,
        "include_logger_name": False,
        "include_thread_info": False,
        "include_process_info": False,
        "include_source_info": False
    },
    file_config={
        "enabled": False,  # No file logging in tests by default
        "level": LogLevel.DEBUG.value,
        "file_path": "/tmp/test_inbox_monitor.log",
        "max_size_mb": 10,
        "backup_count": 1,
        "rotation_enabled": False
    },
    global_config={
        "disable_http_logging": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "async_logging": False,
        "buffer_size": 10,
        "flush_interval_seconds": 0.1,
        "performance_monitoring": False,
        "test_mode": True
    },
    production_ready=False,
    requires_validation=False
)

# Containerized Environment Profile (Docker)
CONTAINERIZED_PROFILE = EnvironmentProfile(
    name="containerized",
    description="Optimized for containerized deployments with stdout/stderr focus",
    console_config={
        "enabled": False,  # Use structured logging to stdout
        "level": LogLevel.INFO.value,
        "format": OutputFormat.JSON.value,
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "show_thread_info": True,
        "show_process_info": False  # Less relevant in containers
    },
    structured_config={
        "enabled": True,
        "level": LogLevel.INFO.value,
        "format": "json",
        "include_timestamp": True,
        "include_logger_name": True,
        "include_thread_info": True,
        "include_process_info": False,
        "include_source_info": False,
        "include_container_info": True
    },
    file_config={
        "enabled": False,  # Use container logging instead
        "level": LogLevel.INFO.value,
        "file_path": "/dev/null",
        "max_size_mb": 0,
        "backup_count": 0,
        "rotation_enabled": False
    },
    global_config={
        "disable_http_logging": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "async_logging": True,
        "buffer_size": 500,
        "flush_interval_seconds": 1.0,
        "performance_monitoring": True,
        "container_optimized": True
    },
    production_ready=True,
    requires_validation=True
)

# Kubernetes Environment Profile
KUBERNETES_PROFILE = EnvironmentProfile(
    name="kubernetes",
    description="Optimized for Kubernetes deployments with cloud-native logging practices",
    console_config={
        "enabled": False,  # Use structured logging to stdout
        "level": LogLevel.INFO.value,
        "format": OutputFormat.JSON.value,
        "color_enabled": False,
        "timestamp_enabled": True,
        "show_logger_name": True,
        "show_thread_info": True,
        "show_process_info": False
    },
    structured_config={
        "enabled": True,
        "level": LogLevel.INFO.value,
        "format": "json",
        "include_timestamp": True,
        "include_logger_name": True,
        "include_thread_info": True,
        "include_process_info": False,
        "include_source_info": False,
        "include_container_info": True,
        "include_pod_info": True,
        "include_namespace_info": True
    },
    file_config={
        "enabled": False,  # Kubernetes handles log collection
        "level": LogLevel.INFO.value,
        "file_path": "/dev/null",
        "max_size_mb": 0,
        "backup_count": 0,
        "rotation_enabled": False
    },
    global_config={
        "disable_http_logging": True,
        "suppress_azure_sdk": True,
        "suppress_urllib3": True,
        "async_logging": True,
        "buffer_size": 1000,
        "flush_interval_seconds": 1.0,
        "performance_monitoring": True,
        "kubernetes_optimized": True,
        "cloud_native_logging": True
    },
    production_ready=True,
    requires_validation=True
)


# Profile registry
ENVIRONMENT_PROFILES: Dict[EnvironmentType, EnvironmentProfile] = {
    EnvironmentType.DEVELOPMENT: DEVELOPMENT_PROFILE,
    EnvironmentType.PRODUCTION: PRODUCTION_PROFILE,
    EnvironmentType.TESTING: TESTING_PROFILE,
    EnvironmentType.CONTAINERIZED: CONTAINERIZED_PROFILE,
    EnvironmentType.KUBERNETES: KUBERNETES_PROFILE
}

# Container-specific profile mappings
CONTAINER_PROFILES: Dict[ContainerType, EnvironmentProfile] = {
    ContainerType.DOCKER: CONTAINERIZED_PROFILE,
    ContainerType.KUBERNETES: KUBERNETES_PROFILE,
    ContainerType.PODMAN: CONTAINERIZED_PROFILE,
    ContainerType.UNKNOWN_CONTAINER: CONTAINERIZED_PROFILE
}


def get_profile_for_environment(environment_type: EnvironmentType) -> EnvironmentProfile:
    """
    Get the configuration profile for a specific environment type.
    
    Args:
        environment_type: The detected or specified environment type
        
    Returns:
        EnvironmentProfile for the specified environment
    """
    return ENVIRONMENT_PROFILES.get(environment_type, DEVELOPMENT_PROFILE)


def get_profile_for_container(container_type: ContainerType) -> EnvironmentProfile:
    """
    Get the configuration profile for a specific container type.
    
    Args:
        container_type: The detected container type
        
    Returns:
        EnvironmentProfile for the specified container type
    """
    return CONTAINER_PROFILES.get(container_type, CONTAINERIZED_PROFILE)


def create_logging_config_from_profile(profile: EnvironmentProfile, 
                                     overrides: Optional[Dict[str, Any]] = None) -> LoggingConfig:
    """
    Create a LoggingConfig from an environment profile with optional overrides.
    
    Args:
        profile: The environment profile to use as base
        overrides: Optional configuration overrides
        
    Returns:
        LoggingConfig instance configured for the environment
    """
    # Build the complete configuration
    config_dict = {
        "console": profile.console_config,
        "structured": profile.structured_config,
        "file": profile.file_config,
        **profile.global_config
    }
    
    # Apply overrides if provided
    if overrides:
        config_dict = _deep_merge(config_dict, overrides)
    
    return LoggingConfig.parse_obj(config_dict)


def get_profile_summary() -> Dict[str, Dict[str, Any]]:
    """
    Get a summary of all available environment profiles.
    
    Returns:
        Dict mapping environment names to profile summaries
    """
    return {
        env_type.value: {
            "name": profile.name,
            "description": profile.description,
            "production_ready": profile.production_ready,
            "console_enabled": profile.console_config.get("enabled", False),
            "structured_enabled": profile.structured_config.get("enabled", False),
            "file_enabled": profile.file_config.get("enabled", False)
        }
        for env_type, profile in ENVIRONMENT_PROFILES.items()
    }


def validate_profile_for_environment(profile: EnvironmentProfile, 
                                   environment_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that a profile is appropriate for the detected environment.
    
    Args:
        profile: The profile to validate
        environment_info: Information about the detected environment
        
    Returns:
        Dict containing validation results and recommendations
    """
    validation_result = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "recommendations": []
    }
    
    is_production = environment_info.get("is_production", False)
    is_containerized = environment_info.get("is_containerized", False)
    
    # Production environment validations
    if is_production and not profile.production_ready:
        validation_result["warnings"].append(
            f"Profile '{profile.name}' may not be suitable for production environments"
        )
    
    if is_production and profile.console_config.get("enabled", False):
        validation_result["warnings"].append(
            "Console logging enabled in production may impact performance"
        )
    
    # Container environment validations
    if is_containerized and profile.file_config.get("enabled", False):
        validation_result["recommendations"].append(
            "Consider disabling file logging in containerized environments"
        )
    
    # Performance validations
    if profile.global_config.get("async_logging", False) and environment_info.get("is_testing", False):
        validation_result["warnings"].append(
            "Async logging may cause test timing issues"
        )
    
    return validation_result


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deeply merge two dictionaries.
    
    Args:
        base: Base dictionary
        update: Dictionary with updates
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def get_recommended_profile(environment_info: Dict[str, Any]) -> EnvironmentProfile:
    """
    Get the recommended profile based on environment detection information.
    
    Args:
        environment_info: Information from environment detection
        
    Returns:
        Recommended EnvironmentProfile
    """
    env_type = environment_info.get("environment_type", EnvironmentType.DEVELOPMENT)
    container_info = environment_info.get("container_info", {})
    container_type = container_info.get("type")
    
    # Use container-specific profile if available
    if container_type and container_type in CONTAINER_PROFILES:
        return get_profile_for_container(container_type)
    
    # Otherwise use environment-based profile
    return get_profile_for_environment(env_type)