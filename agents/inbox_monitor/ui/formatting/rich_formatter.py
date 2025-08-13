# ui/formatting/rich_formatter.py
from typing import Dict, Any, List, Optional, Union
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.syntax import Syntax
from rich.json import JSON
from rich import box
from rich.text import Text
from rich.columns import Columns
from datetime import datetime
import json

from .theme_manager import ThemeManager, Theme


class RichFormatter:
    """Rich text formatting for enhanced CLI output."""
    
    def __init__(self, console: Console, theme_manager: ThemeManager):
        self.console = console
        self.theme_manager = theme_manager
    
    def format_system_status(self, status_data: Dict[str, Any], 
                           detailed: bool = False) -> None:
        """Format and display system status information."""
        theme = self.theme_manager.get_current_theme()
        
        # Handle the health check response structure
        # The status_data has 'components' array and 'overall_status'
        components = status_data.get('components', [])
        overall_status = status_data.get('overall_status', 'UNKNOWN')
        
        # Create main status panel
        overall_healthy = overall_status == 'HEALTHY'
        
        status_icon = "✅" if overall_healthy else "⚠️"
        status_color = theme.success_color if overall_healthy else theme.warning_color
        
        title = Text("System Status", style=f"bold {theme.header_color}")
        
        if detailed:
            self._format_detailed_status(status_data, theme)
        else:
            self._format_summary_status(status_data, theme, status_icon, status_color)
    
    def _format_summary_status(self, status_data: Dict[str, Any], 
                             theme: Theme, status_icon: str, status_color: str) -> None:
        """Format summary status display."""
        components = status_data.get('components', [])
        healthy_count = sum(1 for comp in components if comp.get('status') == 'HEALTHY')
        total_count = len(components)
        
        # Create main status text
        summary_text = Text()
        summary_text.append(f"{status_icon} ", style=status_color)
        summary_text.append(f"System Status: {healthy_count}/{total_count} components healthy\n\n")
        
        # Add component summary list
        for component_data in components:
            component_name = component_data.get('name', 'Unknown')
            component_status = component_data.get('status', 'UNKNOWN')
            is_healthy = component_status == 'HEALTHY'
            comp_icon = "✅" if is_healthy else "❌"
            comp_color = theme.success_color if is_healthy else theme.error_color
            
            summary_text.append(f"  {comp_icon} ", style=comp_color)
            summary_text.append(f"{component_name.replace('_', ' ').title()}: ")
            summary_text.append(f"{component_status}", style=comp_color)
            
            # Add brief message for failed components
            if not is_healthy:
                message = component_data.get('message', '')
                if message:
                    # Get first line of error message
                    brief_message = message.split('.')[0][:40]
                    if len(brief_message) < len(message):
                        brief_message += "..."
                    summary_text.append(f" - {brief_message}", style=theme.muted_color)
            
            summary_text.append("\n")
        
        # Add help text
        summary_text.append(f"\n💡 Use ", style=theme.muted_color)
        summary_text.append("--detailed", style=theme.accent_color)
        summary_text.append(" for full diagnostic information", style=theme.muted_color)
        
        panel = Panel(
            summary_text,
            title="[bold]System Health[/bold]",
            border_style=theme.border_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def _format_detailed_status(self, status_data: Dict[str, Any], theme: Theme) -> None:
        """Format detailed status display with component breakdown."""
        # Get components from the status response
        components = status_data.get('components', [])
        overall_status = status_data.get('overall_status', 'UNKNOWN')
        response_time = status_data.get('response_time_ms', 0)
        
        # Create status table
        table = Table(
            title="System Component Status",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color,
            box=box.ROUNDED
        )
        
        table.add_column("Component", style=theme.text_color, min_width=20)
        table.add_column("Status", justify="center", min_width=10)
        table.add_column("Message", style=theme.muted_color)
        table.add_column("Response Time", style=theme.muted_color, min_width=12)
        
        for component_data in components:
            component_name = component_data.get('name', 'Unknown')
            component_status = component_data.get('status', 'UNKNOWN')
            is_healthy = component_status == 'HEALTHY'
            status_icon = "✅" if is_healthy else "❌"
            status_color = theme.success_color if is_healthy else theme.error_color
            
            status_text = Text(component_status, style=status_color)
            message = component_data.get('message', '')
            comp_response_time = component_data.get('response_time_ms', 0)
            response_time_text = f"{comp_response_time:.1f}ms" if comp_response_time else "-"
            
            table.add_row(
                component_name.replace('_', ' ').title(),
                f"{status_icon} {status_text}",
                message[:60] + "..." if len(message) > 60 else message,
                response_time_text
            )
        
        # Add overall status summary
        summary_panel = Panel(
            f"Overall Status: {overall_status} | Total Response Time: {response_time:.1f}ms",
            title="[bold]System Summary[/bold]",
            border_style=theme.border_color,
            padding=(0, 1)
        )
        
        self.console.print(summary_panel)
        self.console.print(table)
    
    def format_inbox_results(self, processed_count: int, 
                           failed_count: int, 
                           duration: float,
                           details: Optional[List[Dict[str, Any]]] = None) -> None:
        """Format inbox check results."""
        theme = self.theme_manager.get_current_theme()
        
        # Create results summary
        results_table = Table(
            title="Inbox Check Results",
            show_header=False,
            border_style=theme.border_color,
            box=box.MINIMAL_DOUBLE_HEAD
        )
        
        results_table.add_column("Metric", style=f"bold {theme.text_color}")
        results_table.add_column("Value", justify="right")
        
        # Add result rows with appropriate styling
        results_table.add_row(
            "📊 Processed", 
            Text(str(processed_count), style=theme.success_color)
        )
        
        if failed_count > 0:
            results_table.add_row(
                "❌ Failed", 
                Text(str(failed_count), style=theme.error_color)
            )
        
        results_table.add_row(
            "⏱️ Duration", 
            Text(f"{duration:.2f}s", style=theme.muted_color)
        )
        
        # Performance indicator
        if duration > 0:
            emails_per_second = processed_count / duration
            perf_color = theme.success_color if emails_per_second > 1 else theme.warning_color
            results_table.add_row(
                "⚡ Rate",
                Text(f"{emails_per_second:.1f}/s", style=perf_color)
            )
        
        self.console.print(results_table)
        
        # Show detailed results if provided
        if details and len(details) > 0:
            self._format_email_details(details, theme)
    
    def _format_email_details(self, details: List[Dict[str, Any]], theme: Theme) -> None:
        """Format detailed email processing results."""
        if not details:
            return
        
        details_table = Table(
            title="Email Processing Details",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color,
            box=box.ROUNDED
        )
        
        details_table.add_column("Subject", style=theme.text_color, max_width=40)
        details_table.add_column("From", style=theme.muted_color, max_width=25)
        details_table.add_column("Status", justify="center")
        details_table.add_column("Action", style=theme.accent_color)
        
        for email_result in details[:10]:  # Limit to 10 most recent
            # Handle both dict and ProcessingResult objects
            if hasattr(email_result, 'success'):  # It's a ProcessingResult
                subject = email_result.subject[:40] if email_result.subject else f"Email {email_result.email_id[:8]}..."[:40]
                # Always use email address for From column, not display name
                if email_result.sender_email:
                    sender = email_result.sender_email[:25]
                else:
                    sender = "Unknown"[:25]
                status = 'processed' if email_result.success else 'failed'
                action = email_result.scenario_type or 'processed'
            else:  # It's a dict
                subject = email_result.get('subject', 'No Subject')[:40]
                sender = email_result.get('from', 'Unknown')[:25]
                status = email_result.get('status', 'unknown')
                action = email_result.get('action', 'none')
            
            status_color = {
                'processed': theme.success_color,
                'failed': theme.error_color,
                'skipped': theme.warning_color
            }.get(status, theme.muted_color)
            
            status_icon = {
                'processed': '✅',
                'failed': '❌',
                'skipped': '⏭️'
            }.get(status, '❓')
            
            details_table.add_row(
                subject,
                sender,
                f"{status_icon} {status}",
                action
            )
        
        if len(details) > 10:
            details_table.add_row(
                "...", 
                f"and {len(details) - 10} more", 
                "", 
                "",
                style=theme.muted_color
            )
        
        self.console.print(details_table)
    
    def format_error_details(self, error: Exception, 
                           context: Optional[Dict[str, Any]] = None,
                           correlation_id: Optional[str] = None) -> None:
        """Format error information with rich styling."""
        theme = self.theme_manager.get_current_theme()
        
        # Error header
        error_text = Text()
        error_text.append("❌ Error: ", style=f"bold {theme.error_color}")
        error_text.append(str(error), style=theme.error_color)
        
        # Create error panel with context
        error_content = [error_text]
        
        if context:
            error_content.append(Text())  # Empty line
            error_content.append(Text("Context:", style=f"bold {theme.text_color}"))
            
            for key, value in context.items():
                if key not in ['correlation_id']:  # Skip correlation_id as we show it separately
                    context_line = Text()
                    context_line.append(f"  {key}: ", style=theme.muted_color)
                    context_line.append(str(value), style=theme.text_color)
                    error_content.append(context_line)
        
        if correlation_id:
            error_content.append(Text())  # Empty line
            correlation_text = Text()
            correlation_text.append("Correlation ID: ", style=f"bold {theme.muted_color}")
            correlation_text.append(correlation_id, style=theme.accent_color)
            error_content.append(correlation_text)
        
        # Combine all content
        combined_content = Text()
        for i, content in enumerate(error_content):
            if i > 0:
                combined_content.append("\n")
            combined_content.append(content)
        
        panel = Panel(
            combined_content,
            title="[bold red]Error Details[/bold red]",
            border_style=theme.error_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def format_json_output(self, data: Dict[str, Any]) -> None:
        """Format JSON output with syntax highlighting."""
        json_obj = JSON.from_data(data)
        self.console.print(json_obj)
    
    def format_operation_summary(self, operations: List[Dict[str, Any]]) -> None:
        """Format a summary of completed operations."""
        theme = self.theme_manager.get_current_theme()
        
        if not operations:
            self.console.print("No operations to display.", style=theme.muted_color)
            return
        
        summary_table = Table(
            title="Operation Summary",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color,
            box=box.ROUNDED
        )
        
        summary_table.add_column("Operation", style=theme.text_color)
        summary_table.add_column("Status", justify="center")
        summary_table.add_column("Duration", justify="right", style=theme.muted_color)
        summary_table.add_column("Details", style=theme.muted_color)
        
        for op in operations:
            status = op.get('status', 'unknown')
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'running': '🔄'
            }.get(status, '❓')
            
            status_color = {
                'completed': theme.success_color,
                'failed': theme.error_color,
                'running': theme.warning_color
            }.get(status, theme.muted_color)
            
            duration = op.get('duration_seconds', 0)
            duration_text = f"{duration:.2f}s" if duration > 0 else "-"
            
            details = op.get('metadata', {}).get('result_summary', '')
            
            summary_table.add_row(
                op.get('description', 'Unknown Operation'),
                Text(f"{status_icon} {status}", style=status_color),
                duration_text,
                details[:50] + "..." if len(details) > 50 else details
            )
        
        self.console.print(summary_table)
    
    def show_welcome_message(self, version: Optional[str] = None) -> None:
        """Show a welcoming application header."""
        theme = self.theme_manager.get_current_theme()
        
        title_text = Text()
        title_text.append("📧 ", style=theme.accent_color)
        title_text.append("Inbox Monitor", style=f"bold {theme.header_color}")
        if version:
            title_text.append(f" v{version}", style=theme.muted_color)
        
        subtitle = Text(
            "AI-powered email monitoring and response system",
            style=theme.muted_color
        )
        
        welcome_content = Text()
        welcome_content.append(title_text)
        welcome_content.append("\n")
        welcome_content.append(subtitle)
        
        panel = Panel(
            welcome_content,
            border_style=theme.border_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()  # Add spacing