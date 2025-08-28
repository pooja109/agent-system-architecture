# cli/verbosity_controller.py
from typing import Dict, Any, Optional
from enum import Enum
import logging

from utils.custom_logging import LogLevel, OutputFormat, LoggingConfig


class VerbosityLevel(str, Enum):
    """Standard verbosity levels."""
    QUIET = "quiet"
    NORMAL = "normal" 
    VERBOSE = "verbose"
    DEBUG = "debug"


class VerbosityController:
    """Manages verbosity levels and dynamic logging configuration."""
    
    def __init__(self):
        self._current_level = VerbosityLevel.NORMAL
        self._verbosity_mappings = self._create_verbosity_mappings()
    
    def _create_verbosity_mappings(self) -> Dict[VerbosityLevel, Dict[str, Any]]:
        """Create mappings from verbosity levels to logging configurations."""
        return {
            VerbosityLevel.QUIET: {
                'console_level': LogLevel.WARNING,
                'console_format': OutputFormat.MINIMAL,
                'structured_level': LogLevel.ERROR,
                'console_enabled': True,
                'structured_enabled': True,
                'color_enabled': False,
                'timestamps_enabled': False,
                'show_logger_names': False,
                'suppress_azure_sdk': True,
                'suppress_urllib3': True,
                'disable_http_logging': True
            },
            VerbosityLevel.NORMAL: {
                'console_level': LogLevel.INFO,
                'console_format': OutputFormat.CLEAN,
                'structured_level': LogLevel.INFO,
                'console_enabled': True,
                'structured_enabled': True,
                'color_enabled': True,
                'timestamps_enabled': False,
                'show_logger_names': False,
                'suppress_azure_sdk': True,
                'suppress_urllib3': True,
                'disable_http_logging': True
            },
            VerbosityLevel.VERBOSE: {
                'console_level': LogLevel.INFO,
                'console_format': OutputFormat.CLEAN,
                'structured_level': LogLevel.DEBUG,
                'console_enabled': True,
                'structured_enabled': True,
                'color_enabled': True,
                'timestamps_enabled': True,
                'show_logger_names': True,
                'suppress_azure_sdk': True,
                'suppress_urllib3': True,
                'disable_http_logging': True
            },
            VerbosityLevel.DEBUG: {
                'console_level': LogLevel.DEBUG,
                'console_format': OutputFormat.DETAILED,
                'structured_level': LogLevel.DEBUG,
                'console_enabled': True,
                'structured_enabled': True,
                'color_enabled': True,
                'timestamps_enabled': True,
                'show_logger_names': True,
                'suppress_azure_sdk': False,
                'suppress_urllib3': False,
                'disable_http_logging': False
            }
        }
    
    def set_verbosity_level(self, level: VerbosityLevel) -> None:
        """Set the current verbosity level."""
        if not isinstance(level, VerbosityLevel):
            raise ValueError(f"Invalid verbosity level: {level}")
        self._current_level = level
    
    def get_current_level(self) -> VerbosityLevel:
        """Get the current verbosity level."""
        return self._current_level
    
    def get_logging_config_for_level(self, level: VerbosityLevel) -> Dict[str, Any]:
        """Get logging configuration for a specific verbosity level."""
        if level not in self._verbosity_mappings:
            raise ValueError(f"Unknown verbosity level: {level}")
        
        return self._verbosity_mappings[level].copy()
    
    def get_current_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration for current verbosity level."""
        return self.get_logging_config_for_level(self._current_level)
    
    def determine_verbosity_from_args(self, args: Any) -> VerbosityLevel:
        """Determine verbosity level from parsed CLI arguments."""
        if hasattr(args, 'quiet') and args.quiet:
            return VerbosityLevel.QUIET
        elif hasattr(args, 'debug') and args.debug:
            return VerbosityLevel.DEBUG
        elif hasattr(args, 'verbose') and args.verbose:
            return VerbosityLevel.VERBOSE
        else:
            return VerbosityLevel.NORMAL
    
    def apply_verbosity_to_config(self, 
                                config: LoggingConfig, 
                                level: Optional[VerbosityLevel] = None) -> LoggingConfig:
        """Apply verbosity settings to an existing logging configuration."""
        if level is None:
            level = self._current_level
        
        verbosity_config = self.get_logging_config_for_level(level)
        
        # Update console configuration
        if 'console_level' in verbosity_config:
            config.console.level = verbosity_config['console_level']
        if 'console_format' in verbosity_config:
            config.console.format = verbosity_config['console_format']
        if 'console_enabled' in verbosity_config:
            config.console.enabled = verbosity_config['console_enabled']
        if 'color_enabled' in verbosity_config:
            config.console.color_enabled = verbosity_config['color_enabled']
        if 'timestamps_enabled' in verbosity_config:
            config.console.timestamp_enabled = verbosity_config['timestamps_enabled']
        if 'show_logger_names' in verbosity_config:
            config.console.show_logger_name = verbosity_config['show_logger_names']
        
        # Update structured configuration
        if 'structured_level' in verbosity_config:
            config.structured.level = verbosity_config['structured_level']
        if 'structured_enabled' in verbosity_config:
            config.structured.enabled = verbosity_config['structured_enabled']
        
        # Update global settings
        if 'suppress_azure_sdk' in verbosity_config:
            config.suppress_azure_sdk = verbosity_config['suppress_azure_sdk']
        if 'suppress_urllib3' in verbosity_config:
            config.suppress_urllib3 = verbosity_config['suppress_urllib3']
        if 'disable_http_logging' in verbosity_config:
            config.disable_http_logging = verbosity_config['disable_http_logging']
        
        return config
    
    def get_verbosity_description(self, level: Optional[VerbosityLevel] = None) -> str:
        """Get a human-readable description of a verbosity level."""
        if level is None:
            level = self._current_level
        
        descriptions = {
            VerbosityLevel.QUIET: "Minimal output - only essential results and errors",
            VerbosityLevel.NORMAL: "Standard output - normal operational information", 
            VerbosityLevel.VERBOSE: "Detailed output - comprehensive progress information",
            VerbosityLevel.DEBUG: "Full diagnostic output - all available information including HTTP requests"
        }
        
        return descriptions.get(level, f"Unknown verbosity level: {level}")
    
    def is_output_level_appropriate(self, 
                                  message_level: LogLevel, 
                                  verbosity_level: Optional[VerbosityLevel] = None) -> bool:
        """Check if a message level is appropriate for current verbosity."""
        if verbosity_level is None:
            verbosity_level = self._current_level
        
        config = self.get_logging_config_for_level(verbosity_level)
        console_level = config['console_level']
        
        # Convert LogLevel enum to numeric values for comparison
        level_values = {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50
        }
        
        return level_values[message_level] >= level_values[console_level]
    
    def get_recommended_format_for_level(self, level: Optional[VerbosityLevel] = None) -> OutputFormat:
        """Get the recommended output format for a verbosity level."""
        if level is None:
            level = self._current_level
        
        config = self.get_logging_config_for_level(level)
        return config['console_format']