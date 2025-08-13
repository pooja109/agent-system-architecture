# cli/cli_integration.py
import argparse
from typing import Dict, Any, Optional
import sys
from pathlib import Path

from utils.custom_logging import LoggingConfig, initialize_logging, LoggerFactory
from .argument_parser import CLIArgumentParser, create_cli_parser
from .environment_detector import EnvironmentDetector
from .config_manager import ConfigurationManager
from .verbosity_controller import VerbosityController


def parse_cli_args(args: Optional[list] = None) -> argparse.Namespace:
    """Parse CLI arguments with enhanced verbosity controls."""
    parser = create_cli_parser()
    return parser.parse_args(args)


def initialize_cli_logging(args: argparse.Namespace) -> LoggingConfig:
    """Initialize logging system based on CLI arguments and environment detection."""
    
    # Create configuration manager
    config_manager = ConfigurationManager()
    
    # Convert args to dictionary format for config manager
    cli_args_dict = vars(args)
    
    # Extract config file path if provided
    config_file_path = getattr(args, 'config_file', None)
    environment_override = getattr(args, 'environment', None)
    
    try:
        # Load and merge configuration from all sources
        logging_config = config_manager.load_configuration(
            cli_args=cli_args_dict,
            config_file_path=config_file_path,
            environment_override=environment_override
        )
        
        # Initialize the logging system
        initialize_logging(logging_config)
        
        # Log configuration summary if in debug mode
        if getattr(args, 'debug', False):
            summary = config_manager.get_configuration_summary()
            logger = LoggerFactory().get_logger(__name__)
            logger.debug("Configuration loaded from sources", extra={
                'config_summary': summary,
                'final_config': logging_config.dict()
            })
        
        return logging_config
        
    except Exception as e:
        # Fallback to basic logging if configuration fails
        print(f"Warning: Failed to initialize enhanced logging: {e}", file=sys.stderr)
        print("Falling back to basic logging configuration.", file=sys.stderr)
        
        # Create minimal fallback configuration
        fallback_config = LoggingConfig()
        initialize_logging(fallback_config)
        return fallback_config


def get_environment_info(verbose: bool = False) -> Dict[str, Any]:
    """Get current environment information for debugging."""
    detector = EnvironmentDetector()
    env_info = detector.detect_environment()
    
    if not verbose:
        # Return simplified version for normal use
        return {
            'environment_type': env_info['environment_type'],
            'is_containerized': env_info['is_containerized'],
            'is_production': env_info['is_production'],
            'detection_confidence': env_info['detection_confidence']
        }
    
    # Return full environment information
    return env_info


def validate_cli_environment() -> bool:
    """Validate that the CLI environment is properly set up."""
    try:
        # Test environment detection
        detector = EnvironmentDetector()
        env_info = detector.detect_environment()
        
        if env_info['detection_confidence'] < 0.3:
            print("Warning: Low confidence in environment detection", file=sys.stderr)
            return False
        
        # Test configuration management
        config_manager = ConfigurationManager()
        test_config = config_manager.load_configuration()
        
        if not isinstance(test_config, LoggingConfig):
            print("Error: Configuration management failed", file=sys.stderr)
            return False
        
        return True
        
    except Exception as e:
        print(f"Error: CLI environment validation failed: {e}", file=sys.stderr)
        return False


def create_enhanced_argument_parser() -> argparse.ArgumentParser:
    """Create an enhanced argument parser that integrates with existing main.py structure."""
    
    # Create the base parser with existing structure
    parser = argparse.ArgumentParser(
        description="Inbox Monitor - Email Processing Service with Enhanced CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Detection:
  The tool automatically detects development, production, and containerized
  environments and adjusts logging behavior accordingly.

Verbosity Levels:
  --quiet     Minimal output - only essential results and errors
  --verbose   Detailed output - comprehensive progress information  
  --debug     Full diagnostic output - all information including HTTP requests

Output Formats:
  --format clean     Clean, user-friendly output (default)
  --format json      Machine-readable JSON output
  --format detailed  Comprehensive diagnostic output
  --format minimal   Minimal essential information only

Examples:
  python main.py check --quiet                    # Quick check with minimal output
  python main.py run --verbose --format json     # Run with structured output
  python main.py status --debug                   # Full diagnostic system status
  python main.py check --format minimal          # Just the essential results
        """,
    )

    # Add verbosity options
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output - show only essential results and errors'
    )
    verbosity_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Detailed output - show progress and diagnostic information'
    )
    verbosity_group.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Full debug output - show all diagnostic info including HTTP requests'
    )

    # Add output format options
    parser.add_argument(
        '--format',
        choices=['clean', 'json', 'detailed', 'minimal'],
        default='clean',
        help='Output format (default: clean)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    parser.add_argument(
        '--no-timestamps',
        action='store_true',
        help='Disable timestamps in output'
    )

    # Add environment options
    parser.add_argument(
        '--environment',
        choices=['development', 'production', 'testing'],
        help='Override automatic environment detection'
    )
    
    parser.add_argument(
        '--config-file',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--force-console-logging',
        action='store_true',
        help='Force console logging even in production environments'
    )

    # Keep existing options for backward compatibility
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Set specific logging level (overrides verbosity flags)'
    )

    parser.add_argument(
        '--log-format',
        choices=['standard', 'json'],
        help='Legacy logging format option'
    )

    # Add command as positional argument (simpler structure)
    parser.add_argument(
        'command', 
        choices=['check', 'run', 'status', 'test', 'setup'],
        help='Command to execute'
    )
    
    # Add command-specific options
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Limit number of messages to process for check command (default: 10)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds for run command (default: 60)'
    )
    
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed status information for status command'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force setup even if tables exist for setup command'
    )

    return parser


def print_environment_summary(args: argparse.Namespace) -> None:
    """Print a summary of the detected environment and configuration."""
    if not (getattr(args, 'verbose', False) or getattr(args, 'debug', False)):
        return
    
    detector = EnvironmentDetector()
    env_info = detector.detect_environment()
    verbosity_controller = VerbosityController()
    
    print("\n=== Environment Detection Summary ===")
    print(f"Environment Type: {env_info['environment_type']}")
    print(f"Containerized: {env_info['is_containerized']}")
    print(f"Production: {env_info['is_production']}")
    print(f"Detection Confidence: {env_info['detection_confidence']:.2f}")
    
    if getattr(args, 'debug', False):
        print(f"Platform: {env_info['platform_info']['system']}")
        print(f"Container Info: {env_info['container_info']}")
        print(f"Cloud Info: {env_info['cloud_info']['detected_platforms']}")
        
    verbosity_level = verbosity_controller.determine_verbosity_from_args(args)
    print(f"Verbosity Level: {verbosity_level}")
    print(f"Description: {verbosity_controller.get_verbosity_description(verbosity_level)}")
    print("=" * 40)


def handle_configuration_errors(func):
    """Decorator to handle configuration errors gracefully."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Configuration Error: {e}", file=sys.stderr)
            print("Falling back to default configuration.", file=sys.stderr)
            
            # Initialize basic fallback configuration
            fallback_config = LoggingConfig()
            initialize_logging(fallback_config)
            return fallback_config
    
    return wrapper


@handle_configuration_errors
def setup_enhanced_logging(args: argparse.Namespace) -> LoggingConfig:
    """Set up enhanced logging with full error handling."""
    return initialize_cli_logging(args)


def get_cli_usage_examples() -> str:
    """Get formatted CLI usage examples."""
    return """
CLI Usage Examples:

Basic Operations:
  python main.py check                           # Standard inbox check
  python main.py run                             # Start continuous monitoring
  python main.py status                          # Show system status

Verbosity Control:
  python main.py check --quiet                   # Minimal output
  python main.py run --verbose                   # Detailed progress info
  python main.py status --debug                  # Full diagnostic output

Output Formatting:
  python main.py check --format json             # Machine-readable output
  python main.py status --format detailed        # Comprehensive diagnostics
  python main.py check --format minimal --no-color  # Clean minimal output

Environment Overrides:
  python main.py run --environment production    # Force production mode
  python main.py check --force-console-logging   # Enable console in production
  python main.py status --config-file config.yaml  # Use custom config

Advanced Usage:
  python main.py run --debug --no-timestamps     # Debug without timestamps
  python main.py check --verbose --format json --no-color  # Verbose JSON output
"""