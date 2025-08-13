"""
Output Manager - Coordinated Display for Multiple Audiences
"""

import sys
import json
import psutil
import os
from typing import Any, Dict, List, Optional, TextIO
from datetime import datetime
from pathlib import Path
from enum import Enum

from .config import DemoConfig, OutputMode
from .scenario_loader import ScenarioResult


class OutputManager:
    """Manages all output operations with audience-aware formatting."""
    
    def __init__(self, config: DemoConfig):
        self.config = config
        self.output_file = self._setup_output_file()
        self.metrics = {
            'start_time': datetime.now(),
            'scenarios_run': 0,
            'scenarios_passed': 0,
            'total_duration': 0.0
        }
        
        # Memory tracking for verbose mode
        if self.config.detail_level.value == 'verbose':
            try:
                self.process = psutil.Process(os.getpid())
                self.metrics['start_memory_mb'] = self.process.memory_info().rss / 1024 / 1024
            except (ImportError, Exception):
                # Fallback if psutil not available
                self.process = None
                self.metrics['start_memory_mb'] = None
    
    def _setup_output_file(self) -> Optional[TextIO]:
        """Set up output file if specified."""
        if not self.config.output_file:
            return None
        
        try:
            path = Path(self.config.output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            return open(path, 'w', encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not open output file: {e}")
            return None
    
    def write(self, content: str, file_only: bool = False):
        """Write content to console and/or file."""
        # Only print if not file_only, not quiet, and content is not empty
        if not file_only and not self.config.quiet_mode and content.strip():
            print(content)
        
        if self.output_file:
            self.output_file.write(content + '\n')
            self.output_file.flush()
    
    def write_header(self):
        """Write execution header based on output format and detail level."""
        if self.config.quiet_mode:
            return
        
        # Special formats get minimal or no headers
        if self.config.output_format == 'json':
            return  # No header for JSON
        elif self.config.output_format == 'markdown':
            return  # Markdown formatter handles its own headers
        elif self.config.output_format == 'table':
            # Simple header for table format
            self.write("Running E2E Demo scenarios...")
            return
        
        # Standard header for dashboard/business modes
        if self.config.detail_level == OutputMode.BUSINESS:
            self.write(self._get_business_header())
        elif self.config.detail_level == OutputMode.TECHNICAL:
            self.write(self._get_technical_header())
        else:  # VERBOSE
            self.write(self._get_verbose_header())
    
    def _get_business_header(self) -> str:
        """Get business-friendly header."""
        mode = "Demo Mode" if self.config.mock_mode else "Live System"
        return f"""
╔══════════════════════════════════════════════════════════════╗
║           Email Processing Demonstration                     ║
║                    {mode:^26}                    ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def _get_technical_header(self) -> str:
        """Get technical header with system info."""
        mode = "Mock Services" if self.config.mock_mode else "Production APIs"
        return f"""
================================================================================
E2E Integration Test Runner
Mode: {mode} | Format: {self.config.output_format} | Timeout: {self.config.timeout}s
================================================================================
"""
    
    def _get_verbose_header(self) -> str:
        """Get verbose header with full configuration."""
        return f"""
################################################################################
# E2E Demo Execution
# Configuration Source: {self.config.config_source}
# Mode: {'Mock' if self.config.mock_mode else 'Live'}
# Output Format: {self.config.output_format}
# Detail Level: {self.config.detail_level.value}
# Timestamp: {datetime.now().isoformat()}
################################################################################
"""
    
    def format_scenario_result(self, result: ScenarioResult) -> str:
        """Format scenario result based on output format and detail level."""
        # Special formats suppress individual results during execution
        if self.config.output_format in ['table', 'markdown', 'json']:
            return ""  # Results shown only in summary
        
        # Standard formatting for other modes
        if self.config.detail_level == OutputMode.BUSINESS:
            return self._format_business_result(result)
        elif self.config.detail_level == OutputMode.TECHNICAL:
            return self._format_technical_result(result)
        else:  # VERBOSE
            return self._format_verbose_result(result)
    
    def _format_business_result(self, result: ScenarioResult) -> str:
        """Format result for business audience."""
        status = "✅" if result.success else "❌"
        
        output = f"\n{status} Scenario {result.scenario.id}: {result.scenario.name}\n"
        output += f"   Result: {result.business_outcome}\n"
        
        if self.config.show_timing:
            output += f"   Time: {result.duration:.1f} seconds\n"
        
        if not result.success and result.error:
            output += f"   Issue: {self._simplify_error(result.error)}\n"
        
        return output
    
    def _format_technical_result(self, result: ScenarioResult) -> str:
        """Format result for technical audience."""
        status = "PASS" if result.success else "FAIL"
        
        output = f"\n[{status}] Scenario {result.scenario.id}: {result.scenario.name}\n"
        output += f"  Category: {result.scenario.category}\n"
        output += f"  Outcome: {result.business_outcome}\n"
        output += f"  Duration: {result.duration:.3f}s\n"
        
        if result.technical_details:
            output += "  Technical Details:\n"
            for key, value in result.technical_details.items():
                output += f"    - {key}: {value}\n"
        
        if not result.success and result.error:
            # Use enhanced technical error messages
            enhanced_error = self._enhance_technical_error(result.error, result.scenario.id)
            output += f"  Error: {enhanced_error}\n"
        
        return output
    
    def _format_verbose_result(self, result: ScenarioResult) -> str:
        """Format result with all available information."""
        status = "SUCCESS" if result.success else "FAILURE"
        
        output = f"\n{'='*60}\n"
        output += f"Scenario {result.scenario.id}: {result.scenario.name}\n"
        output += f"Status: {status}\n"
        output += f"Category: {result.scenario.category}\n"
        output += f"Description: {result.scenario.description}\n"
        output += f"Duration: {result.duration:.3f} seconds\n"
        output += f"Business Outcome: {result.business_outcome}\n"
        
        if result.technical_details:
            output += "\nTechnical Details:\n"
            output += json.dumps(result.technical_details, indent=2)
        
        if result.scenario.email_data:
            output += "\n\nEmail Data:\n"
            output += json.dumps(result.scenario.email_data, indent=2)
        
        if not result.success and result.error:
            output += f"\n\nError Details:\n{result.error}\n"
        
        output += f"{'='*60}\n"
        
        return output
    
    def _simplify_error(self, error: str) -> str:
        """Simplify technical error for business users."""
        # Common error simplifications
        if "timeout" in error.lower():
            return "Operation took too long"
        elif "connection" in error.lower():
            return "Could not connect to service"
        elif "authentication" in error.lower():
            return "Access denied"
        elif "not found" in error.lower():
            return "Resource not available"
        else:
            # Return first line only
            return error.split('\n')[0][:100]
    
    def _enhance_technical_error(self, error: str, scenario_id: int) -> str:
        """Enhance error with technical details for technical mode."""
        # Map scenarios to service names
        service_mapping = {
            5: "EngagementService",
            6: "ContactService + NotificationService", 
            7: "AccountTeamService",
            8: "ContactStatusService",
            9: "EmailValidationService",
            10: "ContactService + NotificationService + DatabaseService"
        }
        
        service_name = service_mapping.get(scenario_id, "UnknownService")
        
        # Add service context and error codes
        if "timeout" in error.lower():
            return f"[{service_name}] Timeout error (E001): {error}"
        elif "connection" in error.lower():
            return f"[{service_name}] Connection error (E002): {error}"
        elif "authentication" in error.lower():
            return f"[{service_name}] Authentication error (E003): {error}"
        elif "validation" in error.lower():
            return f"[{service_name}] Validation error (E004): {error}"
        elif "not found" in error.lower():
            return f"[{service_name}] Resource error (E005): {error}"
        else:
            return f"[{service_name}] Runtime error (E999): {error}"
    
    def write_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Write execution summary using appropriate format."""
        if self.config.quiet_mode and not self.output_file:
            return
        
        self.metrics['scenarios_run'] = len(results)
        self.metrics['scenarios_passed'] = sum(1 for r in results if r.success)
        self.metrics['total_duration'] = sum(r.duration for r in results)
        
        # Use specialized formatters for special output formats
        if self.config.output_format in ['table', 'markdown', 'json']:
            from .formatters import FormatterFactory, OutputFormat
            formatter = FormatterFactory.create(OutputFormat(self.config.output_format), self.config.use_color)
            
            # Capture formatter output for file writing
            if self.output_file:
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                
                try:
                    formatter.display_summary(results, email_count)
                    output = sys.stdout.getvalue()
                    self.output_file.write(output)
                    self.output_file.flush()
                finally:
                    sys.stdout = old_stdout
            
            # Display to console if not quiet
            if not self.config.quiet_mode:
                formatter.display_summary(results, email_count)
            elif self.output_file:
                # If quiet mode but file output, just write to file (already captured above)
                pass
                
        else:
            # Use traditional OutputManager formatting for dashboard/business modes
            if self.config.detail_level == OutputMode.BUSINESS:
                self.write(self._get_business_summary())
            else:
                self.write(self._get_technical_summary())
    
    def _get_business_summary(self) -> str:
        """Get business-friendly summary."""
        success_rate = (self.metrics['scenarios_passed'] / self.metrics['scenarios_run'] * 100) if self.metrics['scenarios_run'] > 0 else 0
        
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                      Summary                                 ║
╠══════════════════════════════════════════════════════════════╣
║  Scenarios Run: {self.metrics['scenarios_run']:2}                                           ║
║  Success Rate:  {success_rate:.0f}%                                         ║
║  Total Time:    {self.metrics['total_duration']:.1f} seconds                                ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def _get_technical_summary(self) -> str:
        """Get technical summary with metrics."""
        elapsed = (datetime.now() - self.metrics['start_time']).total_seconds()
        avg_duration = self.metrics['total_duration'] / max(self.metrics['scenarios_run'], 1)
        
        summary = f"""
================================================================================
Execution Summary
================================================================================
Scenarios:      {self.metrics['scenarios_passed']}/{self.metrics['scenarios_run']} passed
Success Rate:   {self.metrics['scenarios_passed']/max(self.metrics['scenarios_run'], 1)*100:.1f}%
Total Duration: {self.metrics['total_duration']:.3f}s
Avg Duration:   {avg_duration:.3f}s per scenario
Wall Time:      {elapsed:.3f}s"""
        
        # Add memory usage for verbose mode
        if self.config.detail_level.value == 'verbose' and hasattr(self, 'process') and self.process:
            try:
                current_memory = self.process.memory_info().rss / 1024 / 1024
                start_memory = self.metrics.get('start_memory_mb', 0)
                memory_delta = current_memory - start_memory if start_memory else 0
                
                summary += f"""
Memory Usage:   {current_memory:.1f} MB current, {memory_delta:+.1f} MB change"""
            except Exception:
                summary += f"""
Memory Usage:   Unable to track (psutil error)"""
        
        summary += f"""
================================================================================
"""
        return summary
    
    def close(self):
        """Close output file if open."""
        if self.output_file:
            self.output_file.close()