"""
Enhanced CLI Parser - Professional, Intuitive, Self-Documenting
"""

import argparse
import sys
from typing import Optional, List, Dict, Any
from pathlib import Path


class CLIParser:
    """Professional CLI parser for E2E demos."""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            prog='e2e_demo',
            description=self._get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_epilog(),
            add_help=False  # Custom help
        )
        
        # Custom help to appear first
        parser.add_argument(
            '-h', '--help',
            action='help',
            help='Show this help message and exit'
        )
        
        # Execution modes
        mode_group = parser.add_argument_group('Execution Modes')
        mode_group.add_argument(
            '--live',
            action='store_true',
            help='Use real services (requires confirmation)'
        )
        mode_group.add_argument(
            '--mock',
            action='store_true',
            help='Use mock services for safe demos (default)'
        )
        
        # Scenario selection
        scenario_group = parser.add_argument_group('Scenario Selection')
        scenario_group.add_argument(
            '--scenario',
            type=int,
            metavar='N',
            help='Run specific scenario (5-10 built-in, 15+ custom YAML)'
        )
        scenario_group.add_argument(
            '--filter',
            type=str,
            metavar='TAGS',
            help='Filter scenarios by tags (support,inquiry,no_longer_works)'
        )
        
        # Output control
        output_group = parser.add_argument_group('Output Control')
        output_group.add_argument(
            '--format',
            choices=['dashboard', 'simple', 'json', 'table', 'markdown'],
            default='dashboard',
            help='Output format (default: dashboard)'
        )
        output_group.add_argument(
            '--output',
            type=str,
            metavar='FILE',
            help='Save output to file'
        )
        output_group.add_argument(
            '--no-color',
            action='store_true',
            help='Disable colored output'
        )
        output_group.add_argument(
            '--quiet',
            action='store_true',
            help='Minimal output (suppress headers/footers)'
        )
        
        # Detail levels
        detail_group = parser.add_argument_group('Detail Levels')
        detail_group.add_argument(
            '--business',
            action='store_true',
            help='Business-friendly output (default)'
        )
        detail_group.add_argument(
            '--technical',
            action='store_true',
            help='Include technical details'
        )
        detail_group.add_argument(
            '--verbose',
            action='store_true',
            help='Show all available information'
        )
        detail_group.add_argument(
            '--timing',
            action='store_true',
            help='Show detailed timing metrics'
        )
        
        # Configuration
        config_group = parser.add_argument_group('Configuration')
        config_group.add_argument(
            '--config',
            type=str,
            metavar='FILE',
            help='Load configuration from YAML file'
        )
        config_group.add_argument(
            '--save-config',
            type=str,
            metavar='FILE',
            help='Save current configuration to file'
        )
        
        # Safety and confirmation
        safety_group = parser.add_argument_group('Safety Options')
        safety_group.add_argument(
            '--yes', '-y',
            action='store_true',
            help='Skip confirmation prompts'
        )
        safety_group.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be executed without running'
        )
        
        # Phase 4: Export and reporting options
        export_group = parser.add_argument_group('Export & Reporting (Phase 4)')
        export_group.add_argument(
            '--export',
            type=str,
            choices=['json', 'csv', 'html', 'markdown', 'excel', 'all'],
            help='Export results in specified format'
        )
        export_group.add_argument(
            '--export-dir',
            type=str,
            default='exports',
            help='Directory for exported files (default: exports)'
        )
        export_group.add_argument(
            '--executive-summary',
            action='store_true',
            help='Generate executive summary report'
        )
        export_group.add_argument(
            '--performance-report',
            action='store_true',
            help='Generate performance analysis report'
        )
        
        # Advanced options
        advanced_group = parser.add_argument_group('Advanced Options')
        advanced_group.add_argument(
            '--timeout',
            type=int,
            default=30,
            metavar='SECONDS',
            help='Timeout for service calls (default: 30s)'
        )
        advanced_group.add_argument(
            '--retries',
            type=int,
            default=3,
            metavar='N',
            help='Number of retries for failed operations (default: 3)'
        )
        
        return parser
    
    def _get_description(self) -> str:
        """Get formatted description for help."""
        return """
╔══════════════════════════════════════════════════════════════╗
║          E2E Demo - Enterprise Email Processing              ║
╠══════════════════════════════════════════════════════════════╣
║  Professional demonstration of inbox monitoring capabilities  ║
║  Showcases AI-powered email classification and routing       ║
╚══════════════════════════════════════════════════════════════╝
        """
    
    def _get_epilog(self) -> str:
        """Get formatted epilog with examples."""
        return """
Examples:
  %(prog)s                           # Run all scenarios with dashboard
  %(prog)s --scenario 7              # Run specific scenario
  %(prog)s --filter support          # Run only support scenarios
  %(prog)s --format table --quiet    # Table output, no headers
  %(prog)s --technical --timing      # Technical view with metrics
  %(prog)s --live --yes              # Live mode, skip confirmation
  %(prog)s --config demo.yaml        # Use configuration file
  %(prog)s --dry-run                 # Preview without execution

Scenario Categories:
  5-7:  Support Request Processing
  8-9:  Service Inquiry Handling  
  10:   Contact Status Updates

Output Formats:
  dashboard : Rich terminal UI with progress (default)
  simple    : Plain text output
  json      : Structured JSON export
  table     : Formatted table view
  markdown  : Markdown-formatted report
        """
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """Parse command line arguments."""
        parsed = self.parser.parse_args(args)
        
        # Post-processing and validation
        self._validate_args(parsed)
        self._set_defaults(parsed)
        
        return parsed
    
    def _validate_args(self, args: argparse.Namespace):
        """Validate argument combinations."""
        # Check for conflicting options - only if both are explicitly set
        if args.live and args.mock:
            self.parser.error("Cannot use both --live and --mock")
        
        if args.business and args.technical:
            self.parser.error("Choose either --business or --technical, not both")
        
        if args.quiet and args.verbose:
            self.parser.error("Cannot use both --quiet and --verbose")
        
        # Validate file paths
        if args.config and not Path(args.config).exists():
            self.parser.error(f"Configuration file not found: {args.config}")
    
    def _set_defaults(self, args: argparse.Namespace):
        """Set intelligent defaults based on arguments."""
        # Set mode based on flags
        args.mode = 'live' if args.live else 'mock'
        
        # Set detail level
        if args.verbose:
            args.detail_level = 'verbose'
        elif args.technical:
            args.detail_level = 'technical'
        else:
            args.detail_level = 'business'
        
        # Enable color by default unless disabled or outputting to file
        args.use_color = not getattr(args, 'no_color', False) and not args.output