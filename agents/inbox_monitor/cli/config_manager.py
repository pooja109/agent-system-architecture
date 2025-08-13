# cli/config_manager.py
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
import json
import yaml
from enum import Enum

from utils.custom_logging import LoggingConfig, LogLevel, OutputFormat
from .environment_detector import EnvironmentDetector, EnvironmentType


class ConfigSource(str, Enum):
    """Configuration sources in order of precedence."""
    CLI_ARGS = "cli_args"
    ENVIRONMENT_VARS = "environment_vars"
    CONFIG_FILE = "config_file"
    ENVIRONMENT_DEFAULTS = "environment_defaults"
    SYSTEM_DEFAULTS = "system_defaults"


@dataclass
class ConfigurationLayer:
    """Represents a single layer of configuration."""
    source: ConfigSource
    data: Dict[str, Any]
    priority: int
    description: str
    loaded: bool = False
    errors: List[str] = field(default_factory=list)


class ConfigurationManager:
    """Manages configuration precedence and merging across multiple sources."""
    
    def __init__(self):
        self.environment_detector = EnvironmentDetector()
        self.layers: List[ConfigurationLayer] = []
        self._merged_config: Optional[Dict[str, Any]] = None
        self._config_cache_valid = False
    
    def load_configuration(self,
                         cli_args: Optional[Dict[str, Any]] = None,
                         config_file_path: Optional[Path] = None,
                         environment_override: Optional[str] = None) -> LoggingConfig:
        """Load and merge configuration from all sources."""
        
        # Clear previous configuration
        self._clear_configuration()
        
        # Detect environment
        env_info = self.environment_detector.detect_environment()
        if environment_override:
            env_info['environment_type'] = EnvironmentType(environment_override)
        
        # Load configuration layers in reverse priority order (lowest first)
        self._load_system_defaults()
        self._load_environment_defaults(env_info)
        self._load_config_file(config_file_path)
        self._load_environment_variables()
        self._load_cli_arguments(cli_args or {})
        
        # Merge and validate configuration
        merged_config = self._merge_configuration()
        self._merged_config = merged_config
        self._config_cache_valid = True
        
        # Create and validate LoggingConfig
        try:
            logging_config = self._create_logging_config(merged_config)
            self._validate_configuration(logging_config, env_info)
            return logging_config
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}")
    
    def _clear_configuration(self) -> None:
        """Clear current configuration state."""
        self.layers.clear()
        self._merged_config = None
        self._config_cache_valid = False
    
    def _load_system_defaults(self) -> None:
        """Load system-wide default configuration."""
        defaults = {
            'console': {
                'enabled': True,
                'level': LogLevel.INFO.value,
                'format': OutputFormat.CLEAN.value,
                'color_enabled': True,
                'timestamp_enabled': False,
                'show_logger_name': False
            },
            'structured': {
                'enabled': True,
                'level': LogLevel.DEBUG.value,
                'format': 'json',
                'include_timestamp': True,
                'include_logger_name': True,
                'include_thread_info': False,
                'include_process_info': False
            },
            'file': {
                'enabled': False,
                'level': LogLevel.DEBUG.value,
                'max_size_mb': 100,
                'backup_count': 5,
                'rotation_enabled': True
            },
            'environment': 'development',
            'disable_http_logging': True,
            'suppress_azure_sdk': True,
            'suppress_urllib3': True,
            'async_logging': False,
            'buffer_size': 1000,
            'flush_interval_seconds': 1.0
        }
        
        self.layers.append(ConfigurationLayer(
            source=ConfigSource.SYSTEM_DEFAULTS,
            data=defaults,
            priority=0,
            description="System default configuration",
            loaded=True
        ))
    
    def _load_environment_defaults(self, env_info: Dict[str, Any]) -> None:
        """Load environment-specific default configuration."""
        env_type = env_info['environment_type']
        is_containerized = env_info['is_containerized']
        
        # Get environment-specific defaults
        env_defaults = self.environment_detector.get_recommended_logging_config(env_info)
        
        # Convert to nested structure
        nested_defaults = self._flatten_to_nested(env_defaults)
        
        # Environment-specific overrides
        if env_type == EnvironmentType.PRODUCTION or is_containerized:
            nested_defaults.update({
                'console': {'enabled': False},
                'structured': {
                    'enabled': True,
                    'level': LogLevel.INFO.value,
                    'include_timestamp': True,
                    'include_logger_name': True,
                    'include_thread_info': True
                },
                'environment': 'production'
            })
        elif env_type == EnvironmentType.TESTING:
            nested_defaults.update({
                'console': {
                    'enabled': True,
                    'level': LogLevel.WARNING.value,
                    'color_enabled': False
                },
                'structured': {'enabled': False},
                'environment': 'testing'
            })
        elif env_type == EnvironmentType.DEVELOPMENT:
            # CLI/Development mode: clean console output, structured logs to files only
            nested_defaults.update({
                'console': {
                    'enabled': True,
                    'level': LogLevel.INFO.value,
                    'format': OutputFormat.CLEAN.value,
                    'color_enabled': True,
                    'timestamp_enabled': False,
                    'show_logger_name': False
                },
                'structured': {
                    'enabled': False,  # Disable structured logging to console in CLI mode
                    'level': LogLevel.DEBUG.value
                },
                'environment': 'development'
            })
        
        self.layers.append(ConfigurationLayer(
            source=ConfigSource.ENVIRONMENT_DEFAULTS,
            data=nested_defaults,
            priority=1,
            description=f"Environment defaults for {env_type}",
            loaded=True
        ))
    
    def _load_config_file(self, config_file_path: Optional[Path]) -> None:
        """Load configuration from file."""
        if not config_file_path or not config_file_path.exists():
            # Try default config file locations
            default_paths = [
                Path('config.yaml'),
                Path('config.yml'), 
                Path('config.json'),
                Path('logging_config.yaml'),
                Path('logging_config.yml')
            ]
            
            config_file_path = None
            for path in default_paths:
                if path.exists():
                    config_file_path = path
                    break
        
        if config_file_path and config_file_path.exists():
            try:
                with open(config_file_path, 'r') as f:
                    if config_file_path.suffix.lower() in ['.yaml', '.yml']:
                        try:
                            file_config = yaml.safe_load(f)
                        except ImportError:
                            # Fallback if yaml is not available
                            file_config = {}
                    else:
                        file_config = json.load(f)
                
                # Extract logging section if it exists
                if 'logging' in file_config:
                    file_config = file_config['logging']
                
                self.layers.append(ConfigurationLayer(
                    source=ConfigSource.CONFIG_FILE,
                    data=file_config,
                    priority=2,
                    description=f"Configuration file: {config_file_path}",
                    loaded=True
                ))
            except Exception as e:
                self.layers.append(ConfigurationLayer(
                    source=ConfigSource.CONFIG_FILE,
                    data={},
                    priority=2,
                    description=f"Configuration file: {config_file_path}",
                    loaded=False,
                    errors=[f"Failed to load config file: {e}"]
                ))
    
    def _load_environment_variables(self) -> None:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Define environment variable mappings
        env_mappings = {
            'LOG_LEVEL': 'console.level',
            'LOG_FORMAT': 'console.format',
            'CONSOLE_LOGGING_ENABLED': 'console.enabled',
            'STRUCTURED_LOGGING_ENABLED': 'structured.enabled',
            'DISABLE_HTTP_LOGGING': 'disable_http_logging',
            'SUPPRESS_AZURE_SDK': 'suppress_azure_sdk',
            'SUPPRESS_URLLIB3': 'suppress_urllib3',
            'LOG_FILE_PATH': 'file.file_path',
            'LOG_FILE_ENABLED': 'file.enabled',
            'ENVIRONMENT': 'environment'
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                value = self._convert_env_value(value)
                self._set_nested_value(env_config, config_path, value)
        
        if env_config:
            self.layers.append(ConfigurationLayer(
                source=ConfigSource.ENVIRONMENT_VARS,
                data=env_config,
                priority=3,
                description="Environment variables",
                loaded=True
            ))
    
    def _load_cli_arguments(self, cli_args: Dict[str, Any]) -> None:
        """Load configuration from CLI arguments."""
        if not cli_args:
            return
        
        # Convert CLI arguments to configuration structure
        cli_config = {}
        
        # Map CLI arguments to configuration
        if 'quiet' in cli_args and cli_args['quiet']:
            cli_config.update({
                'console': {
                    'level': LogLevel.WARNING.value,
                    'format': OutputFormat.MINIMAL.value
                }
            })
        elif 'verbose' in cli_args and cli_args['verbose']:
            cli_config.update({
                'console': {
                    'level': LogLevel.INFO.value,
                    'format': OutputFormat.CLEAN.value
                }
            })
        elif 'debug' in cli_args and cli_args['debug']:
            cli_config.update({
                'console': {
                    'level': LogLevel.DEBUG.value,
                    'format': OutputFormat.DETAILED.value
                },
                'disable_http_logging': False,
                'suppress_azure_sdk': False,
                'suppress_urllib3': False
            })
        
        # Direct CLI mappings
        cli_mappings = {
            'format': 'console.format',
            'no_color': 'console.color_enabled',  # Inverted
            'no_timestamps': 'console.timestamp_enabled',  # Inverted
            'show_logger_names': 'console.show_logger_name',
            'log_level': 'console.level',
            'environment': 'environment',
            'force_console_logging': 'console.enabled'  # Force enable
        }
        
        for cli_arg, config_path in cli_mappings.items():
            if cli_arg in cli_args and cli_args[cli_arg] is not None:
                value = cli_args[cli_arg]
                
                # Handle inverted boolean flags
                if cli_arg in ['no_color', 'no_timestamps']:
                    value = not value
                
                self._set_nested_value(cli_config, config_path, value)
        
        if cli_config:
            self.layers.append(ConfigurationLayer(
                source=ConfigSource.CLI_ARGS,
                data=cli_config,
                priority=4,
                description="CLI arguments",
                loaded=True
            ))
    
    def _merge_configuration(self) -> Dict[str, Any]:
        """Merge all configuration layers by priority."""
        merged = {}
        
        # Sort layers by priority (lowest first)
        sorted_layers = sorted(self.layers, key=lambda x: x.priority)
        
        for layer in sorted_layers:
            if layer.loaded and not layer.errors:
                merged = self._deep_merge(merged, layer.data)
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deeply merge two dictionaries."""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _create_logging_config(self, merged_config: Dict[str, Any]) -> LoggingConfig:
        """Create LoggingConfig from merged configuration."""
        # Normalize log level values to uppercase if they exist
        config = merged_config.copy()
        
        # Handle console.level
        if 'console' in config and isinstance(config['console'], dict):
            if 'level' in config['console'] and config['console']['level']:
                config['console']['level'] = str(config['console']['level']).upper()
        
        # Handle structured.level  
        if 'structured' in config and isinstance(config['structured'], dict):
            if 'level' in config['structured'] and config['structured']['level']:
                config['structured']['level'] = str(config['structured']['level']).upper()
        
        return LoggingConfig.parse_obj(config)
    
    def _validate_configuration(self, 
                              logging_config: LoggingConfig, 
                              env_info: Dict[str, Any]) -> None:
        """Validate configuration against environment constraints."""
        warnings = []
        
        # Production environment validations
        if env_info['is_production'] or env_info['is_containerized']:
            if logging_config.console.enabled and not env_info.get('force_console_logging'):
                warnings.append(
                    "Console logging enabled in production environment. "
                    "Consider using structured logging only for production deployments."
                )
        
        # Debug level validations
        if logging_config.console.level == LogLevel.DEBUG:
            if not logging_config.disable_http_logging:
                warnings.append(
                    "Debug level with HTTP logging enabled may produce very verbose output."
                )
        
        # Print warnings
        for warning in warnings:
            print(f"Configuration Warning: {warning}")
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean conversion
        if value.lower() in ['true', '1', 'yes', 'on']:
            return True
        elif value.lower() in ['false', '0', 'no', 'off']:
            return False
        
        # Try integer conversion
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested configuration value using dot notation."""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _flatten_to_nested(self, flat_config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert flat configuration to nested structure."""
        nested = {}
        
        # Define field mappings for environment detector flat config
        field_mappings = {
            # Console-specific fields
            'console_enabled': ('console', 'enabled'),
            'console_level': ('console', 'level'), 
            'console_format': ('console', 'format'),
            'color_enabled': ('console', 'color_enabled'),
            'timestamp_enabled': ('console', 'timestamp_enabled'),
            'show_logger_name': ('console', 'show_logger_name'),
            
            # Structured-specific fields
            'structured_enabled': ('structured', 'enabled'),
            'structured_level': ('structured', 'level'),
            'structured_format': ('structured', 'format'),
            'include_timestamp': ('structured', 'include_timestamp'),
            'include_logger_name': ('structured', 'include_logger_name'),
            'include_thread_info': ('structured', 'include_thread_info'),
            'include_process_info': ('structured', 'include_process_info'),
            
            # File-specific fields
            'file_enabled': ('file', 'enabled'),
            'file_level': ('file', 'level'),
            'file_path': ('file', 'file_path'),
        }
        
        for key, value in flat_config.items():
            # Check if key has a specific mapping
            if key in field_mappings:
                section, field = field_mappings[key]
                if section not in nested:
                    nested[section] = {}
                nested[section][field] = value
            elif 'console_' in key:
                # Handle console_ prefixed keys
                section = 'console'
                field = key.replace('console_', '')
                if section not in nested:
                    nested[section] = {}
                nested[section][field] = value
            elif 'structured_' in key:
                # Handle structured_ prefixed keys
                section = 'structured'
                field = key.replace('structured_', '')
                if section not in nested:
                    nested[section] = {}
                nested[section][field] = value
            elif 'file_' in key:
                # Handle file_ prefixed keys
                section = 'file'
                field = key.replace('file_', '')
                if section not in nested:
                    nested[section] = {}
                nested[section][field] = value
            else:
                # Top-level configuration fields
                nested[key] = value
        
        return nested
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of loaded configuration layers."""
        return {
            'layers': [
                {
                    'source': layer.source.value,
                    'description': layer.description,
                    'loaded': layer.loaded,
                    'errors': layer.errors,
                    'priority': layer.priority,
                    'data_keys': list(layer.data.keys()) if layer.loaded else []
                }
                for layer in sorted(self.layers, key=lambda x: x.priority)
            ],
            'merged_config_available': self._config_cache_valid,
            'final_config_keys': list(self._merged_config.keys()) if self._merged_config else []
        }