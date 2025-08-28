# CLI package for inbox monitor
"""CLI utilities for enhanced argument parsing and environment detection."""

from .argument_parser import CLIArgumentParser, create_cli_parser
from .environment_detector import EnvironmentDetector, EnvironmentType, detect_current_environment, get_environment_type, is_production, is_containerized
from .config_manager import ConfigurationManager
from .verbosity_controller import VerbosityController  
from .cli_integration import initialize_cli_logging, parse_cli_args

__all__ = [
    'CLIArgumentParser',
    'create_cli_parser',
    'EnvironmentDetector', 
    'EnvironmentType',
    'detect_current_environment',
    'get_environment_type',
    'is_production',
    'is_containerized',
    'ConfigurationManager',
    'VerbosityController',
    'initialize_cli_logging',
    'parse_cli_args'
]