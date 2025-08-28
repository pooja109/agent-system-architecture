# cli/output_formats.py
from typing import Dict, Any, Optional, List, Union
from enum import Enum

from utils.custom_logging import OutputFormat
from ui.formatting.output_renderer import OutputRenderer, RenderMode


class ExtendedOutputFormat(str, Enum):
    """Extended output formats beyond basic logging formats."""
    TABLE = "table"
    TREE = "tree"
    COMPACT = "compact"
    GRID = "grid"
    CSV = "csv"
    MARKDOWN = "markdown"


class OutputFormatManager:
    """Manages extended output format implementations."""
    
    def __init__(self, output_renderer: OutputRenderer):
        self.renderer = output_renderer
    
    def format_system_status(self, status_data: Dict[str, Any], 
                           format_type: str,
                           detailed: bool = False) -> None:
        """Format system status in specified format."""
        
        if format_type == ExtendedOutputFormat.TABLE:
            self._format_status_as_table(status_data, detailed)
        elif format_type == ExtendedOutputFormat.TREE:
            self._format_status_as_tree(status_data)
        elif format_type == ExtendedOutputFormat.COMPACT:
            self._format_status_compact(status_data)
        elif format_type == ExtendedOutputFormat.CSV:
            self._format_status_as_csv(status_data)
        elif format_type == ExtendedOutputFormat.MARKDOWN:
            self._format_status_as_markdown(status_data, detailed)
        else:
            # Use standard rich formatting
            self.renderer.rich_formatter.format_system_status(status_data, detailed)
    
    def format_inbox_results(self, processed_count: int, failed_count: int,
                           duration: float, details: Optional[List[Dict[str, Any]]] = None,
                           format_type: str = "clean") -> None:
        """Format inbox results in specified format."""
        
        if format_type == ExtendedOutputFormat.TABLE and details:
            self._format_inbox_as_table(processed_count, failed_count, duration, details)
        elif format_type == ExtendedOutputFormat.COMPACT:
            self._format_inbox_compact(processed_count, failed_count, duration)
        elif format_type == ExtendedOutputFormat.CSV and details:
            self._format_inbox_as_csv(details)
        elif format_type == ExtendedOutputFormat.MARKDOWN:
            self._format_inbox_as_markdown(processed_count, failed_count, duration, details)
        else:
            # Use standard rich formatting
            self.renderer.rich_formatter.format_inbox_results(
                processed_count, failed_count, duration, details
            )
    
    def format_operation_summary(self, operations: List[Dict[str, Any]],
                               format_type: str = "clean") -> None:
        """Format operation summary in specified format."""
        
        if format_type == ExtendedOutputFormat.TABLE:
            self._format_operations_as_table(operations)
        elif format_type == ExtendedOutputFormat.COMPACT:
            self._format_operations_compact(operations)
        elif format_type == ExtendedOutputFormat.CSV:
            self._format_operations_as_csv(operations)
        elif format_type == ExtendedOutputFormat.MARKDOWN:
            self._format_operations_as_markdown(operations)
        else:
            # Use standard rich formatting
            self.renderer.rich_formatter.format_operation_summary(operations)
    
    def _format_status_as_table(self, status_data: Dict[str, Any], detailed: bool) -> None:
        """Format system status as table."""
        from rich.table import Table
        
        theme = self.renderer.theme_manager.get_current_theme()
        table = Table(
            title="System Status",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color
        )
        
        table.add_column("Component", style=theme.text_color)
        table.add_column("Status", justify="center")
        table.add_column("Health", justify="center")
        
        if detailed:
            table.add_column("Details", style=theme.muted_color)
            table.add_column("Last Check", style=theme.muted_color)
        
        for component, data in status_data.items():
            is_healthy = data.get('healthy', False)
            status_icon = "✅" if is_healthy else "❌"
            health_color = theme.success_color if is_healthy else theme.error_color
            
            row_data = [
                component.title(),
                data.get('status', 'Unknown'),
                f"[{health_color}]{status_icon}[/{health_color}]"
            ]
            
            if detailed:
                row_data.extend([
                    data.get('details', '')[:50],
                    data.get('last_check', 'Unknown')
                ])
            
            table.add_row(*row_data)
        
        self.renderer.console.print(table)
    
    def _format_status_as_tree(self, status_data: Dict[str, Any]) -> None:
        """Format system status as tree."""
        from rich.tree import Tree
        
        theme = self.renderer.theme_manager.get_current_theme()
        tree = Tree("System Status", style=f"bold {theme.header_color}")
        
        for component, data in status_data.items():
            is_healthy = data.get('healthy', False)
            status_icon = "✅" if is_healthy else "❌"
            
            component_node = tree.add(f"{status_icon} {component.title()}")
            component_node.add(f"Status: {data.get('status', 'Unknown')}")
            
            if 'details' in data and data['details']:
                component_node.add(f"Details: {data['details']}")
            
            if 'last_check' in data:
                component_node.add(f"Last Check: {data['last_check']}")
        
        self.renderer.console.print(tree)
    
    def _format_status_compact(self, status_data: Dict[str, Any]) -> None:
        """Format system status in compact format."""
        components_status = []
        
        for component, data in status_data.items():
            is_healthy = data.get('healthy', False)
            status_icon = "✅" if is_healthy else "❌"
            components_status.append(f"{status_icon}{component}")
        
        compact_status = " | ".join(components_status)
        self.renderer.console.print(f"System: {compact_status}")
    
    def _format_status_as_csv(self, status_data: Dict[str, Any]) -> None:
        """Format system status as CSV."""
        # Print CSV header
        self.renderer.console.print("Component,Status,Healthy,Details,LastCheck")
        
        for component, data in status_data.items():
            is_healthy = data.get('healthy', False)
            status = data.get('status', 'Unknown')
            details = data.get('details', '').replace(',', ';')  # Escape commas
            last_check = data.get('last_check', 'Unknown')
            
            self.renderer.console.print(
                f"{component},{status},{is_healthy},{details},{last_check}"
            )
    
    def _format_status_as_markdown(self, status_data: Dict[str, Any], detailed: bool) -> None:
        """Format system status as Markdown."""
        self.renderer.console.print("# System Status\n")
        
        if detailed:
            # Detailed markdown table
            self.renderer.console.print("| Component | Status | Health | Details | Last Check |")
            self.renderer.console.print("|-----------|--------|--------|---------|------------|")
            
            for component, data in status_data.items():
                is_healthy = data.get('healthy', False)
                health_emoji = "✅" if is_healthy else "❌"
                status = data.get('status', 'Unknown')
                details = data.get('details', '')
                last_check = data.get('last_check', 'Unknown')
                
                self.renderer.console.print(
                    f"| {component} | {status} | {health_emoji} | {details} | {last_check} |"
                )
        else:
            # Simple list format
            for component, data in status_data.items():
                is_healthy = data.get('healthy', False)
                health_emoji = "✅" if is_healthy else "❌"
                status = data.get('status', 'Unknown')
                
                self.renderer.console.print(f"- **{component}**: {health_emoji} {status}")
    
    def _format_inbox_as_table(self, processed: int, failed: int, duration: float,
                             details: List[Dict[str, Any]]) -> None:
        """Format inbox results as table."""
        from rich.table import Table
        
        theme = self.renderer.theme_manager.get_current_theme()
        
        # Summary table first
        summary_table = Table(
            title="Inbox Check Summary",
            show_header=False,
            border_style=theme.border_color
        )
        summary_table.add_column("Metric", style=f"bold {theme.text_color}")
        summary_table.add_column("Value", justify="right")
        
        summary_table.add_row("Processed", str(processed))
        summary_table.add_row("Failed", str(failed))
        summary_table.add_row("Duration", f"{duration:.2f}s")
        
        self.renderer.console.print(summary_table)
        
        # Details table if available
        if details:
            details_table = Table(
                title="Email Details",
                show_header=True,
                header_style=f"bold {theme.header_color}",
                border_style=theme.border_color
            )
            
            details_table.add_column("Subject", style=theme.text_color, max_width=40)
            details_table.add_column("From", style=theme.muted_color, max_width=25)
            details_table.add_column("Status", justify="center")
            details_table.add_column("Action", style=theme.accent_color)
            
            for email in details:
                subject = email.get('subject', 'No Subject')[:40]
                sender = email.get('from', 'Unknown')[:25]
                status = email.get('status', 'unknown')
                action = email.get('action', 'none')
                
                details_table.add_row(subject, sender, status, action)
            
            self.renderer.console.print(details_table)
    
    def _format_inbox_compact(self, processed: int, failed: int, duration: float) -> None:
        """Format inbox results in compact format."""
        success_rate = ((processed - failed) / processed * 100) if processed > 0 else 0
        self.renderer.console.print(
            f"Inbox: {processed} processed, {failed} failed, "
            f"{duration:.1f}s, {success_rate:.0f}% success"
        )
    
    def _format_inbox_as_csv(self, details: List[Dict[str, Any]]) -> None:
        """Format inbox details as CSV."""
        if not details:
            return
        
        # Print CSV header based on available fields
        fields = ['subject', 'from', 'status', 'action', 'timestamp']
        available_fields = [f for f in fields if any(f in email for email in details)]
        
        self.renderer.console.print(",".join(available_fields))
        
        for email in details:
            values = []
            for field in available_fields:
                value = str(email.get(field, '')).replace(',', ';')  # Escape commas
                values.append(value)
            self.renderer.console.print(",".join(values))
    
    def _format_inbox_as_markdown(self, processed: int, failed: int, duration: float,
                                details: Optional[List[Dict[str, Any]]]) -> None:
        """Format inbox results as Markdown."""
        self.renderer.console.print("# Inbox Check Results\n")
        
        # Summary
        success_rate = ((processed - failed) / processed * 100) if processed > 0 else 0
        self.renderer.console.print(f"- **Processed**: {processed}")
        self.renderer.console.print(f"- **Failed**: {failed}")
        self.renderer.console.print(f"- **Duration**: {duration:.2f}s")
        self.renderer.console.print(f"- **Success Rate**: {success_rate:.0f}%\n")
        
        # Details if available
        if details:
            self.renderer.console.print("## Email Details\n")
            for i, email in enumerate(details[:10], 1):
                subject = email.get('subject', 'No Subject')
                sender = email.get('from', 'Unknown')
                status = email.get('status', 'unknown')
                
                self.renderer.console.print(f"{i}. **{subject}**")
                self.renderer.console.print(f"   - From: {sender}")
                self.renderer.console.print(f"   - Status: {status}\n")
    
    def _format_operations_as_table(self, operations: List[Dict[str, Any]]) -> None:
        """Format operations as table."""
        if not operations:
            return
        
        from rich.table import Table
        
        theme = self.renderer.theme_manager.get_current_theme()
        table = Table(
            title="Operations Summary",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color
        )
        
        table.add_column("Operation", style=theme.text_color)
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Result", style=theme.muted_color)
        
        for op in operations:
            status = op.get('status', 'unknown')
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'running': '🔄'
            }.get(status, '❓')
            
            duration = op.get('duration_seconds', 0)
            duration_text = f"{duration:.2f}s" if duration > 0 else "-"
            
            result = op.get('metadata', {}).get('result_summary', '')
            
            table.add_row(
                op.get('description', 'Unknown'),
                f"{status_icon} {status}",
                duration_text,
                result[:50] + "..." if len(result) > 50 else result
            )
        
        self.renderer.console.print(table)
    
    def _format_operations_compact(self, operations: List[Dict[str, Any]]) -> None:
        """Format operations in compact format."""
        if not operations:
            return
        
        completed = sum(1 for op in operations if op.get('status') == 'completed')
        failed = sum(1 for op in operations if op.get('status') == 'failed')
        total_duration = sum(op.get('duration_seconds', 0) for op in operations)
        
        self.renderer.console.print(
            f"Operations: {len(operations)} total, {completed} completed, "
            f"{failed} failed, {total_duration:.1f}s total"
        )
    
    def _format_operations_as_csv(self, operations: List[Dict[str, Any]]) -> None:
        """Format operations as CSV."""
        if not operations:
            return
        
        self.renderer.console.print("Operation,Status,Duration,Result")
        
        for op in operations:
            operation = op.get('description', 'Unknown').replace(',', ';')
            status = op.get('status', 'unknown')
            duration = op.get('duration_seconds', 0)
            result = op.get('metadata', {}).get('result_summary', '').replace(',', ';')
            
            self.renderer.console.print(f"{operation},{status},{duration},{result}")
    
    def _format_operations_as_markdown(self, operations: List[Dict[str, Any]]) -> None:
        """Format operations as Markdown."""
        if not operations:
            return
        
        self.renderer.console.print("# Operations Summary\n")
        
        for i, op in enumerate(operations, 1):
            status = op.get('status', 'unknown')
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'running': '🔄'
            }.get(status, '❓')
            
            duration = op.get('duration_seconds', 0)
            result = op.get('metadata', {}).get('result_summary', '')
            
            self.renderer.console.print(f"{i}. {status_icon} **{op.get('description', 'Unknown')}**")
            self.renderer.console.print(f"   - Status: {status}")
            if duration > 0:
                self.renderer.console.print(f"   - Duration: {duration:.2f}s")
            if result:
                self.renderer.console.print(f"   - Result: {result}")
            self.renderer.console.print()