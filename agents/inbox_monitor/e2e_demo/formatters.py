"""
Output Formatters - Professional presentation of results with color support
"""

import json
from enum import Enum
from typing import List, Optional
from datetime import datetime
from .scenario_loader import ScenarioResult

try:
    import colorama
    from colorama import Fore, Back, Style
    colorama.init()
    COLOR_AVAILABLE = True
except ImportError:
    COLOR_AVAILABLE = False
    # Fallback color codes
    class _ForeColors:
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
    
    class _Styles:
        BRIGHT = ""
        DIM = ""
        RESET_ALL = ""
    
    Fore = _ForeColors()
    Style = _Styles()

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False


class OutputFormat(Enum):
    """Available output formats."""
    DASHBOARD = "dashboard"
    SIMPLE = "simple"
    JSON = "json"
    TABLE = "table"
    MARKDOWN = "markdown"


class BaseFormatter:
    """Base class for output formatters."""
    
    def __init__(self, use_color: bool = True):
        self.use_color = use_color and COLOR_AVAILABLE
    
    def _colorize(self, text: str, color: str = "", style: str = "") -> str:
        """Apply color and style to text if colors are enabled."""
        if not self.use_color:
            return text
        return f"{color}{style}{text}{Style.RESET_ALL}"
    
    def show_progress(self, message: str):
        """Show progress update."""
        colored_msg = self._colorize("⏳", Fore.YELLOW) + f" {message}"
        print(colored_msg)
    
    def start_scenario(self, scenario):
        """Start a scenario - default implementation does nothing."""
        pass
    
    def show_result(self, result: ScenarioResult):
        """Show individual result."""
        if result.success:
            status = self._colorize("✅", Fore.GREEN)
            print(f"{status} {result.scenario.name}: {result.business_outcome}")
        else:
            status = self._colorize("❌", Fore.RED)
            print(f"{status} {result.scenario.name}: Failed - {result.error}")
    
    def display_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Display summary of all results."""
        raise NotImplementedError


class DashboardFormatter(BaseFormatter):
    """Rich dashboard formatter with live updates."""
    
    def __init__(self, use_color: bool = True):
        super().__init__(use_color)
        self.dashboard = None
        self.progress_tracker = None
        self.terminal_detector = None
        
        # Try to import and initialize dashboard components
        try:
            from .terminal_detector import TerminalDetector
            from .dashboard_integration import DashboardIntegration
            from .progress_tracker import ProgressTracker, ProgressStage
            from .config import DemoConfig
            
            self.terminal_detector = TerminalDetector()
            
            # Check if we can use dashboard - requires dashboard format to be requested
            # This will be set properly when the formatter is created with config
            self.fallback_formatter = SimpleFormatter(use_color)
            
        except ImportError as e:
            # Fallback to simple formatter if components not available
            self.fallback_formatter = SimpleFormatter(use_color)
            print(f"Dashboard components not available: {e}")
    
    def initialize_dashboard(self, config):
        """Initialize dashboard with config (called by runner)."""
        if self.terminal_detector and self.terminal_detector.supports_rich():
            try:
                from .dashboard_integration import DashboardIntegration
                from .progress_tracker import ProgressTracker, ProgressStage
                
                self.dashboard = DashboardIntegration(config)
                self.progress_tracker = ProgressTracker(
                    callback=self._progress_callback
                )
                return True
            except Exception as e:
                print(f"Failed to initialize dashboard: {e}")
                return False
        return False
    
    def _progress_callback(self, event):
        """Handle progress events."""
        if self.dashboard and self.dashboard.is_active():
            # Convert progress event to dashboard update
            if event.scenario_id:
                self.dashboard.update_scenario_progress(
                    event.scenario_id,
                    event.progress
                )
            
            # Update service status based on stage
            from .progress_tracker import ProgressStage
            if event.stage == ProgressStage.CLASSIFYING:
                self.dashboard.update_service('ai_foundry', 1.2)
            elif event.stage == ProgressStage.PROCESSING:
                self.dashboard.update_service('email_service', 0.8)
    
    async def initialize(self, scenarios=None):
        """Initialize dashboard display."""
        if self.dashboard:
            if scenarios:
                self.dashboard.initialize_scenarios(scenarios)
            await self.dashboard.start()
            self.dashboard.set_testing_phase()
            self.progress_tracker.start_execution()
        elif self.fallback_formatter:
            print("🚀 Starting E2E Demo")
    
    async def finalize(self):
        """Finalize dashboard display."""
        if self.dashboard:
            # Show summary
            if self.progress_tracker:
                summary = self.progress_tracker.get_summary()
                self.dashboard.add_message(
                    f"Completed: {summary['scenarios_passed']}/{summary['scenarios_run']} scenarios",
                    'success' if summary['success_rate'] >= 100 else 'info'
                )
            
            await self.dashboard.stop()
        elif self.fallback_formatter:
            print("✅ E2E Demo Complete")
    
    def show_progress(self, message: str):
        """Show progress message."""
        if self.dashboard and self.dashboard.is_active():
            self.dashboard.add_message(message, 'info')
        elif self.fallback_formatter:
            self.fallback_formatter.show_progress(message)
    
    def start_scenario(self, scenario):
        """Start a scenario in the dashboard."""
        if self.dashboard and self.dashboard.is_active():
            self.dashboard.start_scenario(scenario)
        elif self.fallback_formatter:
            # Fallback formatters don't need scenario start tracking
            pass
    
    def show_result(self, result: ScenarioResult):
        """Show scenario result."""
        if self.dashboard and self.dashboard.is_active():
            # Clean the business outcome for consistent dashboard display
            if result.business_outcome:
                cleaned_outcome = self._clean_business_outcome_for_dashboard_display(result.business_outcome)
                # Temporarily modify the result's business outcome
                original_outcome = result.business_outcome
                result.business_outcome = cleaned_outcome
                
                self.dashboard.end_scenario(result)
                
                # Restore original outcome
                result.business_outcome = original_outcome
            else:
                self.dashboard.end_scenario(result)
            
            # Update progress tracker
            if self.progress_tracker:
                self.progress_tracker.complete_scenario(
                    result.scenario.id,
                    result.success
                )
        elif self.fallback_formatter:
            self.fallback_formatter.show_result(result)
    
    def _clean_business_outcome_for_dashboard_display(self, outcome: str) -> str:
        """Clean business outcome for dashboard display - same logic as runner."""
        if not outcome:
            return "Process completed"
        
        # Handle complex outcomes with multiple parts
        if "Victoria Grant notified" in outcome and "Contact updated" in outcome:
            return "Customer status updated and account manager notified"
        elif "Contact removed" in outcome and "Victoria Grant notified" in outcome:
            return "Customer removed from outreach list and account manager notified"
        elif "Account team notified" in outcome:
            return "Customer inquiry forwarded to specialist support team"
        elif "Contact marked as temporarily away" in outcome:
            return "Customer marked as out of office - follow-up scheduled"
        elif "Email marked as invalid" in outcome:
            return "Invalid email address identified and contact updated"
        elif "Positive engagement created" in outcome:
            return "New sales opportunity identified and assigned to expert"
        
        # Handle simple outcomes with technical codes
        elif "REAL_ENG_" in outcome:
            return "New sales opportunity identified and assigned to expert"
        elif "REAL_REMOVE_" in outcome:
            return "Customer removed from outreach list"
        elif "REAL_TEAM_EMAIL_" in outcome:
            return "Customer inquiry forwarded to specialist support team"
        elif "REAL_STATUS_temporary_away" in outcome:
            return "Customer marked as out of office - follow-up scheduled"
        elif "REAL_INVALID_SF_" in outcome:
            return "Invalid email address identified and contact updated"
        elif "REAL_STATUS_no_longer_works" in outcome:
            return "Customer status updated and account manager notified"
        
        # If no pattern matches, return the original but cleaned of technical codes
        import re
        cleaned = re.sub(r'REAL_[A-Z_]+_[a-zA-Z0-9_]+', '', outcome)
        cleaned = re.sub(r'[a-f0-9]{8,}', '', cleaned)  # Remove hex IDs
        cleaned = cleaned.replace('_', ' ').strip(', ')
        
        return cleaned if cleaned else "Process completed"
    
    def display_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Display execution summary."""
        if self.dashboard:
            # Dashboard handles its own summary during finalize()
            pass
        elif self.fallback_formatter:
            self.fallback_formatter.display_summary(results, email_count)
    
    def update_service_status(self, service: str, status: str):
        """Update service status in dashboard."""
        if self.dashboard and self.dashboard.is_active():
            # Convert status string to duration for service metric
            duration = 0.5 if status == 'healthy' else 2.0
            success = status in ['healthy', 'connecting']
            self.dashboard.update_service(service, duration, success)


class SimpleFormatter(BaseFormatter):
    """Simple text output for basic terminals."""
    
    def show_progress(self, message: str):
        """Show simple progress message."""
        print(f"Running: {message}")
    
    def show_result(self, result: ScenarioResult):
        """Show simple result."""
        if result.success:
            print(f"  OK - {result.scenario.name}")
        else:
            print(f"  FAILED - {result.scenario.name}: {result.error}")
    
    def display_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Display simple text summary."""
        total = len(results)
        successful = sum(1 for r in results if r.success)
        
        print(f"\nResults: {successful}/{total} scenarios passed")
        
        # Email compliance check
        if email_count is not None:
            expected_emails = 4
            compliance = "PASS" if email_count == expected_emails else "FAIL"
            print(f"Email Operations: {email_count}/{expected_emails} - {compliance}")
        
        if successful < total:
            print("\nFailed scenarios:")
            for result in results:
                if not result.success:
                    print(f"  - {result.scenario.name}: {result.error}")


class JSONFormatter(BaseFormatter):
    """JSON output for data export."""
    
    def show_progress(self, message: str):
        """Minimal progress for JSON mode."""
        pass  # Silent in JSON mode
    
    def show_result(self, result: ScenarioResult):
        """Minimal result display for JSON mode."""
        pass  # Silent in JSON mode
    
    def display_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Display JSON-ready summary."""
        import json
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_scenarios': len(results),
            'successful': sum(1 for r in results if r.success),
            'failed': sum(1 for r in results if not r.success),
            'total_duration': sum(r.duration for r in results),
            'scenarios': [r.to_dict() for r in results]
        }
        
        # Add email compliance data
        if email_count is not None:
            summary['email_operations'] = {
                'performed': email_count,
                'expected': 4,
                'compliant': email_count == 4
            }
        
        print(json.dumps(summary, indent=2))


class TableFormatter(BaseFormatter):
    """Table output using tabulate library."""
    
    def show_progress(self, message: str):
        """Show simple progress for table mode."""
        print(f"Running: {message}")
    
    def show_result(self, result: ScenarioResult):
        """Collect results for table display."""
        pass  # Results shown in summary table
    
    def display_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Display results as formatted table."""
        if not TABULATE_AVAILABLE:
            print("Warning: tabulate library not available, falling back to simple format")
            SimpleFormatter().display_summary(results, email_count)
            return
        
        # Prepare table data
        headers = ["ID", "Name", "Status", "Duration", "Business Outcome"]
        table_data = []
        
        for result in results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            outcome = result.business_outcome if result.success else result.error[:50] + "..."
            table_data.append([
                result.scenario.id,
                result.scenario.name[:25] + "..." if len(result.scenario.name) > 25 else result.scenario.name,
                status,
                f"{result.duration:.2f}s",
                outcome[:40] + "..." if len(outcome) > 40 else outcome
            ])
        
        # Print table
        print(f"\n{self._colorize('E2E Demo Results', Fore.CYAN, Style.BRIGHT)}")
        print("=" * 80)
        
        table_style = "grid" if self.use_color else "simple"
        print(tabulate(table_data, headers=headers, tablefmt=table_style))
        
        # Summary statistics
        total = len(results)
        successful = sum(1 for r in results if r.success)
        success_rate = (successful / total) * 100 if total > 0 else 0
        total_duration = sum(r.duration for r in results)
        
        print(f"\nSummary: {successful}/{total} passed ({success_rate:.0f}%) in {total_duration:.2f}s")
        
        # Email compliance
        if email_count is not None:
            expected_emails = 4
            compliance = self._colorize("✅ COMPLIANT", Fore.GREEN) if email_count == expected_emails else self._colorize("❌ NON-COMPLIANT", Fore.RED)
            print(f"Email Operations: {email_count}/{expected_emails} - {compliance}")


class MarkdownFormatter(BaseFormatter):
    """Markdown output for documentation."""
    
    def __init__(self, use_color: bool = True):
        super().__init__(use_color=False)  # No colors in markdown
    
    def show_progress(self, message: str):
        """Show progress for markdown mode."""
        print(f"*Running: {message}*")
    
    def show_result(self, result: ScenarioResult):
        """Collect results for markdown display."""
        pass  # Results shown in summary
    
    def display_summary(self, results: List[ScenarioResult], email_count: Optional[int] = None):
        """Display results as markdown report."""
        print("# E2E Demo Results Report\n")
        print(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Summary table
        total = len(results)
        successful = sum(1 for r in results if r.success)
        success_rate = (successful / total) * 100 if total > 0 else 0
        total_duration = sum(r.duration for r in results)
        
        print("## Summary\n")
        print("| Metric | Value |")
        print("|--------|-------|")
        print(f"| Total Scenarios | {total} |")
        print(f"| Successful | {successful} |")
        print(f"| Success Rate | {success_rate:.0f}% |")
        print(f"| Total Duration | {total_duration:.2f}s |")
        
        # Email compliance
        if email_count is not None:
            expected_emails = 4
            compliance = "✅ Compliant" if email_count == expected_emails else "❌ Non-compliant"
            print(f"| Email Operations | {email_count}/{expected_emails} {compliance} |")
        
        print("\n## Detailed Results\n")
        
        # Individual scenario results
        for result in results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"### Scenario {result.scenario.id}: {result.scenario.name}\n")
            print(f"**Status:** {status}  ")
            print(f"**Category:** {result.scenario.category}  ")
            print(f"**Duration:** {result.duration:.2f}s  ")
            
            if result.success:
                print(f"**Outcome:** {result.business_outcome}\n")
                
                if result.technical_details:
                    print("**Technical Details:**")
                    for key, value in result.technical_details.items():
                        print(f"- {key}: {value}")
                    print()
            else:
                print(f"**Error:** {result.error}\n")
            
            print("---\n")


class FormatterFactory:
    """Factory for creating formatters."""
    
    @staticmethod
    def create(format_type: OutputFormat, use_color: bool = True) -> BaseFormatter:
        """Create appropriate formatter based on type."""
        formatters = {
            OutputFormat.DASHBOARD: DashboardFormatter,
            OutputFormat.SIMPLE: SimpleFormatter,
            OutputFormat.JSON: JSONFormatter,
            OutputFormat.TABLE: TableFormatter,
            OutputFormat.MARKDOWN: MarkdownFormatter
        }
        
        formatter_class = formatters.get(format_type, DashboardFormatter)
        return formatter_class(use_color=use_color)