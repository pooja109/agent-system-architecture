# cli/argument_parser.py
import argparse
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path

from utils.custom_logging import LogLevel, OutputFormat
from .environment_detector import EnvironmentType


class CLIArgumentParser:
    """Enhanced argument parser with verbosity controls and intelligent help."""
    
    def __init__(self):
        self.parser = self._create_parser()
        self._setup_verbosity_options()
        self._setup_output_options()
        self._setup_environment_options()
        self._setup_existing_commands()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser with enhanced help."""
        return argparse.ArgumentParser(
            prog='inbox_monitor',
            description='''
            Inbox Monitor - Email Processing and Response System
            
            This tool monitors email inboxes, processes messages using AI classification,
            and generates appropriate responses through integration with various services.
            
            VERBOSITY LEVELS:
              --quiet     Show only essential results and errors
              --verbose   Show structured progress information with progress indicators
              --debug     Show all diagnostic information including HTTP requests
              
            OUTPUT FORMATS:
              --format clean     Clean, user-friendly output with rich formatting (default)
              --format json      Machine-readable JSON output
              --format detailed  Comprehensive diagnostic output
              --format minimal   Minimal essential information only
              --format table     Tabular data presentation
              --format compact   Compact single-line format
              
            THEMES AND STYLING:
              --theme auto           Auto-detect appropriate theme (default)
              --theme professional   Professional blue theme
              --theme dark           Dark terminal theme  
              --theme light          Light terminal theme
              --theme minimal        No colors, minimal formatting
              --theme high_contrast  High contrast for accessibility
              
            UI CONTROLS:
              --no-color      Disable all colors
              --no-unicode    Use ASCII characters only
              --no-emoji      Disable emoji icons
              --no-progress   Disable progress indicators
              --compact       Use compact output layout
              
            ADVANCED FEATURES (Phase 4):
              --scenario 5,6  Run only specific test scenarios
              --exclude 9     Exclude specific scenarios from execution
              --tag positive  Filter tests by tags
              --parallel      Enable parallel test execution
              --max-workers 3 Set maximum parallel workers
              --export-json results.json    Export results to JSON
              --export-xml junit.xml        Export to JUnit XML format
              --export-csv results.csv      Export to CSV format
              --export-html report.html     Export to HTML report
              --profile dev   Use saved configuration profile
              --save-profile dev     Save current config as profile
              --list-profiles        List available profiles
              --watch         Watch for file changes and re-run tests
              --ci-mode       CI/CD optimized mode with structured output
              --fail-fast     Stop on first test failure
              --retry-failed 2       Retry failed tests N times
            ''',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
            EXAMPLES:
              %(prog)s check --quiet                    # Quick inbox check with minimal output
              %(prog)s run --verbose --format json     # Run with structured output
              %(prog)s status --debug                   # Full diagnostic system status
              %(prog)s check --format minimal          # Just the essential results
              %(prog)s test --scenario 5,6 --parallel  # Run specific tests in parallel
              %(prog)s test --export-json results.json # Export test results to JSON
              %(prog)s test --profile production        # Use saved production profile
            
            ENVIRONMENT DETECTION:
              The tool automatically detects whether it's running in development,
              production, or containerized environments and adjusts default
              behavior accordingly. Use --environment to override detection.
            '''
        )
    
    def _setup_verbosity_options(self) -> None:
        """Set up verbosity control options - now handled by parent parser."""
        pass  # Options are now defined in the parent parser within _setup_existing_commands
    
    def _setup_output_options(self) -> None:
        """Set up output format options - now handled by parent parser."""
        pass  # Options are now defined in the parent parser within _setup_existing_commands
    
    def _setup_environment_options(self) -> None:
        """Set up environment and configuration options - now handled by parent parser."""
        pass  # Options are now defined in the parent parser within _setup_existing_commands
    
    def _setup_existing_commands(self) -> None:
        """Set up existing command structure with subparsers."""
        subparsers = self.parser.add_subparsers(
            dest='command',
            help='Available commands',
            metavar='COMMAND'
        )
        
        # Create parent parser with common arguments
        parent_parser = argparse.ArgumentParser(add_help=False)
        
        # Add verbosity options to parent parser
        verbosity_group = parent_parser.add_mutually_exclusive_group()
        verbosity_group.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Minimal output - show only essential results and errors'
        )
        verbosity_group.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Structured verbose output - show progress and diagnostic information'
        )
        verbosity_group.add_argument(
            '--debug', '-d',
            action='store_true',
            help='Full debug output - show all diagnostic info including HTTP requests'
        )
        
        # Add other common options to parent parser
        parent_parser.add_argument(
            '--log-level',
            choices=[level.value.lower() for level in LogLevel],
            help='Set specific logging level (overrides verbosity flags)'
        )
        parent_parser.add_argument(
            '--format',
            choices=[fmt.value for fmt in OutputFormat],
            default=OutputFormat.CLEAN.value,
            help='Output format (default: clean)'
        )
        parent_parser.add_argument(
            '--theme',
            choices=['default', 'dark', 'light', 'minimal', 'professional', 'high_contrast', 'auto'],
            default='auto',
            help='Color theme (default: auto-detect)'
        )
        parent_parser.add_argument(
            '--no-color',
            action='store_true',
            help='Disable colored output'
        )
        parent_parser.add_argument(
            '--ui-logging',
            choices=['minimal', 'normal', 'full'],
            default='normal',
            help='Control logging output during UI execution (default: normal)'
        )
        parent_parser.add_argument(
            '--no-unicode',
            action='store_true',
            help='Disable Unicode characters (use ASCII only)'
        )
        parent_parser.add_argument(
            '--yes', '-y',
            action='store_true',
            help='Skip safety confirmation prompts (auto-confirm)'
        )
        parent_parser.add_argument(
            '--no-emoji',
            action='store_true',
            help='Disable emoji in output'
        )
        parent_parser.add_argument(
            '--no-progress',
            action='store_true',
            help='Disable progress indicators'
        )
        parent_parser.add_argument(
            '--compact',
            action='store_true',
            help='Use compact output format'
        )
        parent_parser.add_argument(
            '--width',
            type=int,
            help='Override terminal width for output formatting'
        )
        parent_parser.add_argument(
            '--no-timestamps',
            action='store_true',
            help='Disable timestamps in output'
        )
        parent_parser.add_argument(
            '--show-logger-names',
            action='store_true',
            help='Show logger names in output'
        )
        parent_parser.add_argument(
            '--environment',
            choices=['development', 'production', 'testing'],
            help='Override automatic environment detection'
        )
        parent_parser.add_argument(
            '--config-file',
            type=Path,
            help='Path to configuration file'
        )
        parent_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without executing'
        )
        parent_parser.add_argument(
            '--force-console-logging',
            action='store_true',
            help='Force console logging even in production environments'
        )
        # Execution mode options
        mode_group = parent_parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            '--mock-mode', '--mock',
            action='store_true',
            help='Use mock services for development and testing (bypasses live services)'
        )
        mode_group.add_argument(
            '--live',
            action='store_true',
            help='Use real services (requires confirmation)'
        )
        
        # Advanced Phase 4 Features - Test Filtering
        parent_parser.add_argument(
            '--scenario', '--scenarios',
            type=str,
            help='Comma-separated list of scenarios to run (e.g., "5,6,7" or "positive,negative")'
        )
        parent_parser.add_argument(
            '--exclude', '--exclude-scenarios',
            type=str,
            help='Comma-separated list of scenarios to exclude'
        )
        parent_parser.add_argument(
            '--tag', '--tags',
            type=str,
            help='Run tests with specific tags (e.g., "real,integration")'
        )
        
        # Advanced Phase 4 Features - Parallel Execution
        parent_parser.add_argument(
            '--parallel', '-p',
            action='store_true',
            help='Run tests in parallel'
        )
        parent_parser.add_argument(
            '--max-workers',
            type=int,
            default=3,
            help='Maximum number of parallel workers (default: 3)'
        )
        parent_parser.add_argument(
            '--parallel-timeout',
            type=int,
            default=300,
            help='Timeout for individual test in parallel mode (seconds)'
        )
        
        # Advanced Phase 4 Features - Export Options
        parent_parser.add_argument(
            '--export-json',
            type=str,
            metavar='FILE',
            help='Export results to JSON file'
        )
        parent_parser.add_argument(
            '--export-xml',
            type=str,
            metavar='FILE',
            help='Export results to XML file (JUnit format)'
        )
        parent_parser.add_argument(
            '--export-csv',
            type=str,
            metavar='FILE',
            help='Export results to CSV file'
        )
        parent_parser.add_argument(
            '--export-html',
            type=str,
            metavar='FILE',
            help='Export results to HTML report'
        )
        
        # Advanced Phase 4 Features - Configuration Profiles
        parent_parser.add_argument(
            '--profile',
            type=str,
            help='Use saved configuration profile'
        )
        parent_parser.add_argument(
            '--save-profile',
            type=str,
            help='Save current configuration as profile'
        )
        parent_parser.add_argument(
            '--list-profiles',
            action='store_true',
            help='List available configuration profiles'
        )
        
        # Advanced Phase 4 Features - Watch Mode
        parent_parser.add_argument(
            '--watch',
            action='store_true',
            help='Watch for changes and re-run tests automatically'
        )
        parent_parser.add_argument(
            '--watch-path',
            type=str,
            default='.',
            help='Path to watch for changes (default: current directory)'
        )
        parent_parser.add_argument(
            '--watch-pattern',
            type=str,
            default='*.py',
            help='File pattern to watch (default: *.py)'
        )
        
        # Advanced Phase 4 Features - CI/CD Integration
        parent_parser.add_argument(
            '--ci-mode',
            action='store_true',
            help='Enable CI/CD mode with optimized output and exit codes'
        )
        parent_parser.add_argument(
            '--fail-fast',
            action='store_true',
            help='Stop execution on first test failure'
        )
        parent_parser.add_argument(
            '--retry-failed',
            type=int,
            default=0,
            help='Retry failed tests N times'
        )
        
        # Check command
        check_parser = subparsers.add_parser(
            'check',
            help='Check inbox once and exit',
            description='Perform a one-time inbox check and display results',
            parents=[parent_parser]
        )
        check_parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit number of messages to process (default: 10)'
        )
        
        # Run command
        run_parser = subparsers.add_parser(
            'run',
            help='Run continuous monitor',
            description='Start continuous inbox monitoring',
            parents=[parent_parser]
        )
        run_parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Check interval in seconds (default: 60)'
        )
        
        # Status command
        status_parser = subparsers.add_parser(
            'status',
            help='Show system status',
            description='Display current system status and health information',
            parents=[parent_parser]
        )
        status_parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed status information'
        )
        
        # Test command
        test_parser = subparsers.add_parser(
            'test',
            help='Test Graph API connection',
            description='Test connectivity to Microsoft Graph API',
            parents=[parent_parser]
        )
        
        # Setup command
        setup_parser = subparsers.add_parser(
            'setup',
            help='Setup Databricks tables',
            description='Initialize required Databricks database tables',
            parents=[parent_parser]
        )
        setup_parser.add_argument(
            '--force',
            action='store_true',
            help='Force setup even if tables exist'
        )
        
        # Setup scenario tracking command
        setup_scenario_parser = subparsers.add_parser(
            'setup-scenario-tracking',
            help='Setup scenario tracking table only',
            description='Initialize the scenario processing tracking table in Databricks',
            parents=[parent_parser]
        )
        setup_scenario_parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify table structure and run tests after creation'
        )
        
        # Recreate scenario tracking table command
        recreate_scenario_parser = subparsers.add_parser(
            'recreate-scenario-table',
            help='Drop and recreate scenario tracking table with new schema',
            description='Drop existing scenario tracking table and recreate with updated schema (replaces ai_* fields with email_intent_* fields)',
            parents=[parent_parser]
        )
        recreate_scenario_parser.add_argument(
            '--auto-confirm',
            action='store_true',
            help='Skip confirmation prompt (use with caution - will permanently delete existing data)'
        )
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """Parse command line arguments with validation."""
        parsed_args = self.parser.parse_args(args)
        
        # Validate argument combinations
        self._validate_arguments(parsed_args)
        
        # Set default command if none provided
        if not parsed_args.command:
            parsed_args.command = 'check'
        
        return parsed_args
    
    def _validate_arguments(self, args: argparse.Namespace) -> None:
        """Validate argument combinations and provide helpful errors."""
        # Only validate if we have the required attributes (i.e., a command was specified)
        if not hasattr(args, 'format'):
            return  # No subcommand specified, skip validation
            
        # Validate format and verbosity combinations
        # Note: --quiet with --format json is allowed for automation scenarios
        
        if hasattr(args, 'format') and hasattr(args, 'debug') and args.format == 'minimal' and args.debug:
            self.parser.error("--debug and --format minimal are incompatible")
        
        # Validate file paths
        if hasattr(args, 'config_file') and args.config_file and not args.config_file.exists():
            self.parser.error(f"Configuration file not found: {args.config_file}")
        
        # Validate environment-specific options
        if hasattr(args, 'force_console_logging') and hasattr(args, 'quiet') and args.force_console_logging and args.quiet:
            print("Warning: --force-console-logging may override --quiet in production environments")
    
    def get_verbosity_config(self, args: argparse.Namespace) -> Dict[str, Any]:
        """Extract verbosity configuration from parsed arguments."""
        config = {
            'console_enabled': True,
            'structured_enabled': True,
            'console_level': LogLevel.INFO,
            'structured_level': LogLevel.DEBUG,
            'console_format': OutputFormat(getattr(args, 'format', 'clean')),
            'color_enabled': not getattr(args, 'no_color', False),
            'timestamps_enabled': not getattr(args, 'no_timestamps', False),
            'show_logger_names': getattr(args, 'show_logger_names', False),
            # New UI options
            'theme': getattr(args, 'theme', 'auto'),
            'unicode_enabled': not getattr(args, 'no_unicode', False),
            'emoji_enabled': not getattr(args, 'no_emoji', False),
            'progress_enabled': not getattr(args, 'no_progress', False),
            'compact_mode': getattr(args, 'compact', False),
            'terminal_width': getattr(args, 'width', None),
            'extended_format': None  # All formats now handled by OutputFormat enum
        }
        
        # Apply verbosity flags
        if getattr(args, 'quiet', False):
            config['console_level'] = LogLevel.WARNING
            # Only override format if user didn't specify one explicitly
            if not hasattr(args, 'format') or not args.format:
                config['console_format'] = OutputFormat.MINIMAL
            config['progress_enabled'] = False  # Disable progress in quiet mode
        elif getattr(args, 'verbose', False):
            config['console_level'] = LogLevel.INFO
            config['console_format'] = OutputFormat.CLEAN
            config['progress_enabled'] = True   # Enable progress in verbose mode
        elif getattr(args, 'debug', False):
            config['console_level'] = LogLevel.DEBUG
            config['console_format'] = OutputFormat.DETAILED
        
        # Override with specific log level if provided
        if hasattr(args, 'log_level') and args.log_level:
            level = LogLevel(args.log_level.upper())
            config['console_level'] = level
            if level == LogLevel.DEBUG:
                config['console_format'] = OutputFormat.DETAILED
        
        return config
    
    def print_help(self) -> None:
        """Print enhanced help information."""
        self.parser.print_help()
    
    def print_usage(self) -> None:
        """Print usage information."""
        self.parser.print_usage()


def create_cli_parser() -> CLIArgumentParser:
    """Factory function to create configured CLI parser."""
    return CLIArgumentParser()