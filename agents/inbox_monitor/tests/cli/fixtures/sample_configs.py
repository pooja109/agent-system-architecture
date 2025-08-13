# tests/cli/fixtures/sample_configs.py
"""
Sample Configuration Examples for Testing
========================================

This module provides pre-configured sample configurations for testing
configuration management, precedence, and validation logic.
"""

from typing import Dict, Any
from pathlib import Path
import tempfile
import yaml
import json


# Sample configuration examples
SAMPLE_CONFIGS = {
    "basic": {
        "description": "Basic configuration with minimal settings",
        "config": {
            "console": {
                "enabled": True,
                "level": "INFO",
                "format": "clean",
                "color_enabled": True,
                "timestamp_enabled": False,
                "show_logger_name": False
            },
            "structured": {
                "enabled": True,
                "level": "DEBUG",
                "format": "json",
                "include_timestamp": True,
                "include_logger_name": True,
                "include_thread_info": False,
                "include_process_info": False
            },
            "file": {
                "enabled": False
            },
            "environment": "development",
            "disable_http_logging": True,
            "suppress_azure_sdk": True,
            "suppress_urllib3": True
        }
    },
    
    "advanced": {
        "description": "Advanced configuration with all options specified",
        "config": {
            "console": {
                "enabled": True,
                "level": "DEBUG",
                "format": "detailed",
                "color_enabled": True,
                "timestamp_enabled": True,
                "show_logger_name": True
            },
            "structured": {
                "enabled": True,
                "level": "DEBUG",
                "format": "json",
                "include_timestamp": True,
                "include_logger_name": True,
                "include_thread_info": True,
                "include_process_info": True,
                "include_source_info": True
            },
            "file": {
                "enabled": True,
                "level": "DEBUG",
                "file_path": "logs/inbox_monitor.log",
                "max_size_mb": 100,
                "backup_count": 5,
                "rotation_enabled": True
            },
            "environment": "development",
            "disable_http_logging": False,
            "suppress_azure_sdk": False,
            "suppress_urllib3": False,
            "async_logging": True,
            "buffer_size": 1000,
            "flush_interval_seconds": 1.0
        }
    },
    
    "production": {
        "description": "Production-optimized configuration",
        "config": {
            "console": {
                "enabled": False,
                "level": "WARNING",
                "format": "minimal"
            },
            "structured": {
                "enabled": True,
                "level": "INFO",
                "format": "json",
                "include_timestamp": True,
                "include_logger_name": True,
                "include_thread_info": True,
                "include_process_info": True,
                "include_correlation_id": True
            },
            "file": {
                "enabled": True,
                "level": "INFO",
                "file_path": "/var/log/inbox_monitor/app.log",
                "max_size_mb": 500,
                "backup_count": 10,
                "rotation_enabled": True,
                "compression_enabled": True
            },
            "environment": "production",
            "disable_http_logging": True,
            "suppress_azure_sdk": True,
            "suppress_urllib3": True,
            "async_logging": True,
            "buffer_size": 1000,
            "flush_interval_seconds": 2.0,
            "performance_monitoring": True,
            "error_aggregation": True,
            "alert_on_errors": True
        }
    },
    
    "testing": {
        "description": "Testing environment configuration with minimal noise",
        "config": {
            "console": {
                "enabled": True,
                "level": "WARNING",
                "format": "minimal",
                "color_enabled": False,
                "timestamp_enabled": False,
                "show_logger_name": False
            },
            "structured": {
                "enabled": False,
                "level": "DEBUG"
            },
            "file": {
                "enabled": False
            },
            "environment": "testing",
            "disable_http_logging": True,
            "suppress_azure_sdk": True,
            "suppress_urllib3": True,
            "test_mode": True
        }
    },
    
    "containerized": {
        "description": "Container-optimized configuration for Docker/K8s",
        "config": {
            "console": {
                "enabled": False
            },
            "structured": {
                "enabled": True,
                "level": "INFO",
                "format": "json",
                "include_timestamp": True,
                "include_logger_name": True,
                "include_thread_info": True,
                "include_process_info": False,
                "include_container_info": True
            },
            "file": {
                "enabled": False
            },
            "environment": "production",
            "disable_http_logging": True,
            "suppress_azure_sdk": True,
            "suppress_urllib3": True,
            "async_logging": True,
            "buffer_size": 500,
            "flush_interval_seconds": 1.0,
            "container_optimized": True
        }
    },
    
    "kubernetes": {
        "description": "Kubernetes-specific configuration with pod information",
        "config": {
            "console": {
                "enabled": False
            },
            "structured": {
                "enabled": True,
                "level": "INFO",
                "format": "json",
                "include_timestamp": True,
                "include_logger_name": True,
                "include_thread_info": True,
                "include_process_info": False,
                "include_container_info": True,
                "include_pod_info": True,
                "include_namespace_info": True
            },
            "file": {
                "enabled": False
            },
            "environment": "production",
            "disable_http_logging": True,
            "suppress_azure_sdk": True,
            "suppress_urllib3": True,
            "async_logging": True,
            "buffer_size": 1000,
            "flush_interval_seconds": 1.0,
            "kubernetes_optimized": True,
            "cloud_native_logging": True
        }
    },
    
    "minimal": {
        "description": "Minimal configuration for resource-constrained environments",
        "config": {
            "console": {
                "enabled": True,
                "level": "ERROR",
                "format": "minimal",
                "color_enabled": False,
                "timestamp_enabled": False,
                "show_logger_name": False
            },
            "structured": {
                "enabled": False
            },
            "file": {
                "enabled": False
            },
            "environment": "production",
            "disable_http_logging": True,
            "suppress_azure_sdk": True,
            "suppress_urllib3": True,
            "async_logging": False
        }
    },
    
    "debug": {
        "description": "Debug configuration with maximum verbosity",
        "config": {
            "console": {
                "enabled": True,
                "level": "DEBUG",
                "format": "detailed",
                "color_enabled": True,
                "timestamp_enabled": True,
                "show_logger_name": True
            },
            "structured": {
                "enabled": True,
                "level": "DEBUG",
                "format": "json",
                "include_timestamp": True,
                "include_logger_name": True,
                "include_thread_info": True,
                "include_process_info": True,
                "include_source_info": True
            },
            "file": {
                "enabled": True,
                "level": "DEBUG",
                "file_path": "debug.log",
                "max_size_mb": 50,
                "backup_count": 3,
                "rotation_enabled": True
            },
            "environment": "development",
            "disable_http_logging": False,
            "suppress_azure_sdk": False,
            "suppress_urllib3": False,
            "async_logging": False,
            "performance_monitoring": False
        }
    }
}

# CLI argument combinations for testing
CLI_ARGUMENT_COMBINATIONS = {
    "quiet_mode": {
        "description": "CLI arguments for quiet mode",
        "args": {
            "quiet": True,
            "verbose": False,
            "debug": False,
            "format": "minimal",
            "no_color": True,
            "no_timestamps": True,
            "show_logger_names": False
        },
        "expected_config_overrides": {
            "console": {
                "level": "WARNING",
                "format": "minimal",
                "color_enabled": False,
                "timestamp_enabled": False
            }
        }
    },
    
    "verbose_mode": {
        "description": "CLI arguments for verbose mode",
        "args": {
            "quiet": False,
            "verbose": True,
            "debug": False,
            "format": "clean",
            "no_color": False,
            "no_timestamps": False,
            "show_logger_names": False
        },
        "expected_config_overrides": {
            "console": {
                "level": "INFO",
                "format": "clean",
                "color_enabled": True,
                "timestamp_enabled": True
            }
        }
    },
    
    "debug_mode": {
        "description": "CLI arguments for debug mode",
        "args": {
            "quiet": False,
            "verbose": False,
            "debug": True,
            "format": "detailed",
            "no_color": False,
            "no_timestamps": False,
            "show_logger_names": True
        },
        "expected_config_overrides": {
            "console": {
                "level": "DEBUG",
                "format": "detailed",
                "color_enabled": True,
                "timestamp_enabled": True,
                "show_logger_name": True
            },
            "disable_http_logging": False,
            "suppress_azure_sdk": False,
            "suppress_urllib3": False
        }
    },
    
    "json_output": {
        "description": "CLI arguments for JSON output format",
        "args": {
            "quiet": False,
            "verbose": False,
            "debug": False,
            "format": "json",
            "no_color": True,
            "no_timestamps": False,
            "show_logger_names": True
        },
        "expected_config_overrides": {
            "console": {
                "format": "json",
                "color_enabled": False,
                "timestamp_enabled": True,
                "show_logger_name": True
            },
            "structured": {
                "enabled": True
            }
        }
    },
    
    "force_console": {
        "description": "CLI arguments for forcing console logging",
        "args": {
            "quiet": False,
            "verbose": False,
            "debug": False,
            "format": "clean",
            "force_console_logging": True,
            "environment": "production"
        },
        "expected_config_overrides": {
            "console": {
                "enabled": True
            }
        }
    }
}

# Environment variable configurations for testing
ENVIRONMENT_VARIABLE_CONFIGS = {
    "env_vars_basic": {
        "description": "Basic environment variable configuration",
        "env_vars": {
            "LOG_LEVEL": "WARNING",
            "LOG_FORMAT": "json",
            "CONSOLE_LOGGING_ENABLED": "true",
            "STRUCTURED_LOGGING_ENABLED": "true",
            "DISABLE_HTTP_LOGGING": "true",
            "ENVIRONMENT": "production"
        },
        "expected_config": {
            "console": {
                "level": "WARNING",
                "format": "json",
                "enabled": True
            },
            "structured": {
                "enabled": True
            },
            "disable_http_logging": True,
            "environment": "production"
        }
    },
    
    "env_vars_disabled": {
        "description": "Environment variables disabling features",
        "env_vars": {
            "CONSOLE_LOGGING_ENABLED": "false",
            "STRUCTURED_LOGGING_ENABLED": "false",
            "DISABLE_HTTP_LOGGING": "false",
            "SUPPRESS_AZURE_SDK": "false"
        },
        "expected_config": {
            "console": {
                "enabled": False
            },
            "structured": {
                "enabled": False
            },
            "disable_http_logging": False,
            "suppress_azure_sdk": False
        }
    }
}

# Configuration precedence test scenarios
PRECEDENCE_TEST_SCENARIOS = {
    "cli_overrides_env": {
        "description": "CLI arguments should override environment variables",
        "layers": {
            "environment_vars": {
                "LOG_LEVEL": "ERROR",
                "CONSOLE_LOGGING_ENABLED": "false"
            },
            "cli_args": {
                "verbose": True,
                "force_console_logging": True
            }
        },
        "expected_final_config": {
            "console": {
                "level": "INFO",  # From CLI verbose mode
                "enabled": True   # From CLI force_console_logging
            }
        }
    },
    
    "env_overrides_defaults": {
        "description": "Environment variables should override defaults",
        "layers": {
            "environment_vars": {
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "detailed"
            }
        },
        "expected_final_config": {
            "console": {
                "level": "DEBUG",
                "format": "detailed"
            }
        }
    },
    
    "config_file_overrides_defaults": {
        "description": "Configuration file should override defaults",
        "config_file": {
            "console": {
                "level": "WARNING",
                "format": "json",
                "color_enabled": False
            },
            "async_logging": True
        },
        "expected_final_config": {
            "console": {
                "level": "WARNING",
                "format": "json",
                "color_enabled": False
            },
            "async_logging": True
        }
    }
}


class SampleConfigManager:
    """Helper class for managing sample configurations in tests."""
    
    def __init__(self):
        self.temp_files = []
    
    def create_config_file(self, config_name: str, file_format: str = "yaml") -> Path:
        """Create a temporary configuration file with sample config."""
        if config_name not in SAMPLE_CONFIGS:
            raise ValueError(f"Unknown config: {config_name}")
        
        config = SAMPLE_CONFIGS[config_name]["config"]
        
        if file_format.lower() in ["yaml", "yml"]:
            suffix = ".yaml"
            content = yaml.dump(config, default_flow_style=False)
        elif file_format.lower() == "json":
            suffix = ".json"
            content = json.dumps(config, indent=2)
        else:
            raise ValueError(f"Unsupported format: {file_format}")
        
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=suffix, 
            delete=False,
            prefix=f"test_config_{config_name}_"
        )
        
        temp_file.write(content)
        temp_file.close()
        
        temp_path = Path(temp_file.name)
        self.temp_files.append(temp_path)
        
        return temp_path
    
    def create_logging_config_file(self, config_name: str, file_format: str = "yaml") -> Path:
        """Create a configuration file with logging section wrapper."""
        if config_name not in SAMPLE_CONFIGS:
            raise ValueError(f"Unknown config: {config_name}")
        
        # Wrap config in logging section
        wrapped_config = {
            "logging": SAMPLE_CONFIGS[config_name]["config"],
            "application": {
                "name": "inbox_monitor",
                "version": "1.0.0"
            }
        }
        
        if file_format.lower() in ["yaml", "yml"]:
            suffix = ".yaml"
            content = yaml.dump(wrapped_config, default_flow_style=False)
        elif file_format.lower() == "json":
            suffix = ".json"
            content = json.dumps(wrapped_config, indent=2)
        else:
            raise ValueError(f"Unsupported format: {file_format}")
        
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=suffix, 
            delete=False,
            prefix=f"test_app_config_{config_name}_"
        )
        
        temp_file.write(content)
        temp_file.close()
        
        temp_path = Path(temp_file.name)
        self.temp_files.append(temp_path)
        
        return temp_path
    
    def cleanup(self):
        """Clean up all temporary files."""
        for temp_path in self.temp_files:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        self.temp_files.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Convenience functions for common test scenarios
def get_sample_config(config_name: str) -> Dict[str, Any]:
    """Get a sample configuration by name."""
    if config_name not in SAMPLE_CONFIGS:
        raise ValueError(f"Unknown config: {config_name}")
    return SAMPLE_CONFIGS[config_name]["config"].copy()


def get_cli_args(combination_name: str) -> Dict[str, Any]:
    """Get CLI argument combination by name."""
    if combination_name not in CLI_ARGUMENT_COMBINATIONS:
        raise ValueError(f"Unknown combination: {combination_name}")
    return CLI_ARGUMENT_COMBINATIONS[combination_name]["args"].copy()


def get_env_vars(config_name: str) -> Dict[str, str]:
    """Get environment variable configuration by name."""
    if config_name not in ENVIRONMENT_VARIABLE_CONFIGS:
        raise ValueError(f"Unknown config: {config_name}")
    return ENVIRONMENT_VARIABLE_CONFIGS[config_name]["env_vars"].copy()


def get_all_config_names():
    """Get names of all available sample configurations."""
    return list(SAMPLE_CONFIGS.keys())


def get_all_cli_combinations():
    """Get names of all available CLI argument combinations."""
    return list(CLI_ARGUMENT_COMBINATIONS.keys())


def get_all_env_var_configs():
    """Get names of all available environment variable configurations."""
    return list(ENVIRONMENT_VARIABLE_CONFIGS.keys())


def validate_config_structure(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that a configuration has the expected structure."""
    validation_result = {
        "valid": True,
        "missing_sections": [],
        "unexpected_sections": [],
        "missing_fields": []
    }
    
    expected_sections = ["console", "structured", "file"]
    required_fields = {
        "console": ["enabled", "level"],
        "structured": ["enabled", "level"],
        "file": ["enabled"]
    }
    
    # Check for required sections
    for section in expected_sections:
        if section not in config:
            validation_result["valid"] = False
            validation_result["missing_sections"].append(section)
        else:
            # Check required fields in each section
            for field in required_fields[section]:
                if field not in config[section]:
                    validation_result["valid"] = False
                    validation_result["missing_fields"].append(f"{section}.{field}")
    
    return validation_result