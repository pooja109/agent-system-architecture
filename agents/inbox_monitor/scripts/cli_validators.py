"""
CLI Validators for Test Runner CLI
=================================

Provides input validation and error handling utilities.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode


@dataclass
class CLIOptions:
    """Configuration options parsed from command line arguments."""
    execution_mode: ExecutionMode
    verbose: bool = False
    quiet: bool = False
    fail_fast: bool = False
    parallel: bool = False
    output_file: Optional[str] = None
    custom_markers: Optional[str] = None
    max_failures: Optional[int] = None
    timeout: Optional[int] = None
    dry_run: bool = False
    
    # Advanced options
    profile: Optional[str] = None
    generate_report: Optional[str] = None
    analyze: bool = False
    trends: bool = False
    ci_mode: Optional[str] = None
    watch: bool = False
    bisect: bool = False
    benchmark: bool = False
    coverage: bool = False
    coverage_report: Optional[str] = None
    export_formats: Optional[List[str]] = None
    monitoring: bool = False
    plugins: Optional[List[str]] = None
    
    # Phase 5 Integration options
    validate_complete_recovery: bool = False
    validate_infrastructure: bool = False
    generate_recovery_report: bool = False


class CLIValidator:
    """Validates CLI options and provides helpful error messages."""
    
    def __init__(self):
        # Use current working directory, but if we're in scripts/, go up to project root
        current_path = Path.cwd()
        if current_path.name == "scripts":
            self.base_path = current_path.parent
        else:
            self.base_path = current_path
    
    def validate_options(self, options: CLIOptions) -> List[str]:
        """Validate CLI options and return list of validation errors."""
        errors = []
        
        # Validate execution mode
        errors.extend(self._validate_execution_mode(options))
        
        # Validate output options
        errors.extend(self._validate_output_options(options))
        
        # Validate timing and failure options
        errors.extend(self._validate_execution_options(options))
        
        # Validate custom markers if provided
        errors.extend(self._validate_custom_markers(options))
        
        # Validate environment
        errors.extend(self._validate_environment())
        
        return errors
    
    def _validate_execution_mode(self, options: CLIOptions) -> List[str]:
        """Validate execution mode options."""
        errors = []
        
        # Basic mode validation (should be caught by enum, but double-check)
        if options.execution_mode not in ExecutionMode:
            errors.append(f"Invalid execution mode: {options.execution_mode}")
        
        # Custom mode specific validation
        if options.execution_mode == ExecutionMode.CUSTOM:
            if not options.custom_markers:
                errors.append("Custom execution mode requires --custom option with marker expression")
        
        return errors
    
    def _validate_output_options(self, options: CLIOptions) -> List[str]:
        """Validate output-related options."""
        errors = []
        
        # Validate verbose/quiet conflict
        if options.verbose and options.quiet:
            errors.append("Cannot specify both --verbose and --quiet options\n  Suggestion: Use either --verbose for detailed output or --quiet for minimal output, but not both")
        
        # Validate output file
        if options.output_file:
            # Check if directory exists
            output_path = Path(options.output_file)
            if output_path.parent != Path('.') and not output_path.parent.exists():
                errors.append(f"Output directory does not exist: {output_path.parent}")
            
            # Check if file already exists and is writable
            if output_path.exists():
                if not os.access(output_path, os.W_OK):
                    errors.append(f"Output file is not writable: {options.output_file}")
            else:
                # Check if parent directory is writable
                parent_dir = output_path.parent if output_path.parent != Path('.') else Path.cwd()
                if not os.access(parent_dir, os.W_OK):
                    errors.append(f"Cannot write to output directory: {parent_dir}")
        
        return errors
    
    def _validate_execution_options(self, options: CLIOptions) -> List[str]:
        """Validate execution-related options."""
        errors = []
        
        # Validate max_failures
        if options.max_failures is not None:
            if options.max_failures <= 0:
                errors.append("--max-failures must be a positive integer")
            if options.fail_fast and options.max_failures != 1:
                errors.append("--fail-fast and --max-failures are mutually exclusive")
        
        # Validate timeout
        if options.timeout is not None:
            if options.timeout <= 0:
                errors.append("--timeout must be a positive integer (seconds)")
            if options.timeout < 10:
                errors.append("--timeout should be at least 10 seconds for meaningful test execution\n  Suggestion: Use --timeout with at least 10 seconds, e.g., --timeout 60")
            if options.timeout > 7200:  # 2 hours
                errors.append("--timeout should not exceed 7200 seconds (2 hours)")
        
        # Validate parallel execution
        if options.parallel:
            # Check if pytest-xdist is available for parallel execution
            try:
                import xdist
            except ImportError:
                errors.append("Parallel execution requires pytest-xdist: pip install pytest-xdist")
        
        return errors
    
    def _validate_custom_markers(self, options: CLIOptions) -> List[str]:
        """Validate custom marker expressions."""
        errors = []
        
        if not options.custom_markers:
            return errors
        
        # Basic syntax validation
        marker_expr = options.custom_markers.strip()
        
        # Check for empty expression
        if not marker_expr:
            errors.append("Custom marker expression cannot be empty")
            return errors
        
        # Validate marker syntax (pytest marker expressions)
        validation_errors = self._validate_marker_expression(marker_expr)
        errors.extend(validation_errors)
        
        return errors
    
    def _validate_marker_expression(self, expression: str) -> List[str]:
        """Validate pytest marker expression syntax."""
        errors = []
        
        # Check for balanced parentheses
        if not self._check_balanced_parentheses(expression):
            errors.append("Unbalanced parentheses in marker expression")
        
        # Check for valid operators
        valid_operators = ['and', 'or', 'not']
        tokens = re.findall(r'\b(?:and|or|not)\b', expression)
        
        # Check for invalid characters
        # Allow alphanumeric, underscores, spaces, parentheses, and logical operators
        if not re.match(r'^[a-zA-Z0-9_\s\(\)]+$', re.sub(r'\b(?:and|or|not)\b', '', expression)):
            errors.append("Invalid characters in marker expression")
        
        # Check for known markers (basic validation)
        known_markers = {
            'fast', 'medium', 'slow', 'unit', 'integration', 'edge_case',
            'azure', 'email', 'retry', 'performance', 'smoke', 'ci_safe',
            'salesforce', 'databricks', 'prompt', 'monitoring'
        }
        
        # Extract potential marker names
        marker_candidates = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expression)
        marker_candidates = [m for m in marker_candidates if m not in valid_operators]
        
        unknown_markers = set(marker_candidates) - known_markers
        if unknown_markers:
            errors.append(f"Unknown markers in expression: {', '.join(unknown_markers)}")
        
        return errors
    
    def _check_balanced_parentheses(self, expression: str) -> bool:
        """Check if parentheses are balanced in the expression."""
        count = 0
        for char in expression:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False
        return count == 0
    
    def _validate_environment(self) -> List[str]:
        """Validate the test runner environment."""
        errors = []
        
        # Check if we're in the correct directory
        if not (self.base_path / 'pytest.ini').exists():
            errors.append("pytest.ini not found - ensure you're in the agents/inbox_monitor directory")
        
        # Check if tests directory exists
        if not (self.base_path / 'tests').exists():
            errors.append("tests/ directory not found")
        
        # Check Python version compatibility
        import sys
        if sys.version_info < (3, 7):
            errors.append("Python 3.7 or higher is required")
        
        # Check for pytest availability
        try:
            import pytest
            if hasattr(pytest, '__version__'):
                version_parts = pytest.__version__.split('.')
                major, minor = int(version_parts[0]), int(version_parts[1])
                if major < 6:
                    errors.append(f"pytest 6.0 or higher is required (found {pytest.__version__})")
        except ImportError:
            errors.append("pytest is not installed")
        
        return errors
    
    def suggest_fixes(self, errors: List[str]) -> Dict[str, str]:
        """Provide suggested fixes for common validation errors."""
        suggestions = {}
        
        for error in errors:
            if "pytest.ini not found" in error:
                suggestions[error] = "Run: cd agents/inbox_monitor"
            
            elif "tests/ directory not found" in error:
                suggestions[error] = "Ensure you're in the correct project directory"
            
            elif "pytest is not installed" in error:
                suggestions[error] = "Run: pip install pytest"
            
            elif "pytest-xdist" in error:
                suggestions[error] = "Run: pip install pytest-xdist"
            
            elif "Python 3.7" in error:
                suggestions[error] = "Upgrade Python to version 3.7 or higher"
            
            elif "verbose and quiet" in error:
                suggestions[error] = "Choose either --verbose OR --quiet, not both"
            
            elif "max-failures must be positive" in error:
                suggestions[error] = "Use --max-failures with a positive number, e.g., --max-failures 5"
            
            elif "timeout should be at least 10" in error:
                suggestions[error] = "Use --timeout with at least 10 seconds, e.g., --timeout 60"
            
            elif "Unknown markers" in error:
                suggestions[error] = "Use --list-markers to see available markers"
            
            elif "Custom marker expression cannot be empty" in error:
                suggestions[error] = 'Use --custom with a marker expression, e.g., --custom "fast and azure"'
        
        return suggestions