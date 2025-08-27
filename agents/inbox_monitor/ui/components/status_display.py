# ui/components/status_display.py
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..formatting.theme_manager import ThemeManager


class StatusDisplay:
    """Component for displaying system status information."""
    
    def __init__(self, console: Console, theme_manager: ThemeManager):
        self.console = console
        self.theme_manager = theme_manager
    
    def show_system_health(self, health_data: Dict[str, Any], detailed: bool = False) -> None:
        """Display system health status."""
        theme = self.theme_manager.get_current_theme()
        
        if detailed:
            self._show_detailed_health(health_data, theme)
        else:
            self._show_summary_health(health_data, theme)
    
    def _show_summary_health(self, health_data: Dict[str, Any], theme) -> None:
        """Show summary health status."""
        components = health_data.get('components', {})
        healthy_count = sum(1 for c in components.values() if c.get('healthy', False))
        total_count = len(components)
        
        overall_status = health_data.get('overall_status', 'UNKNOWN')
        status_icon = "✅" if overall_status == 'HEALTHY' else "⚠️"
        status_color = theme.success_color if overall_status == 'HEALTHY' else theme.warning_color
        
        summary_text = Text()
        summary_text.append(f"{status_icon} ", style=status_color)
        summary_text.append(f"System Health: {healthy_count}/{total_count} components healthy")
        
        panel = Panel(
            summary_text,
            title="[bold]System Status[/bold]",
            border_style=theme.border_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def _show_detailed_health(self, health_data: Dict[str, Any], theme) -> None:
        """Show detailed health status."""
        components = health_data.get('components', {})
        
        if not components:
            self.console.print("No component health data available.", style=theme.muted_color)
            return
        
        table = Table(
            title="System Component Health",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color,
            box=box.ROUNDED
        )
        
        table.add_column("Component", style=theme.text_color, min_width=20)
        table.add_column("Status", justify="center", min_width=10)
        table.add_column("Details", style=theme.muted_color)
        table.add_column("Last Check", style=theme.muted_color, min_width=15)
        
        for component_name, component_data in components.items():
            is_healthy = component_data.get('healthy', False)
            status_icon = "✅" if is_healthy else "❌"
            status_color = theme.success_color if is_healthy else theme.error_color
            
            status_text = component_data.get('status', 'Unknown')
            details = component_data.get('details', '')
            last_check = component_data.get('last_check', 'Unknown')
            
            table.add_row(
                component_name.replace('_', ' ').title(),
                f"{status_icon} {status_text}",
                details[:50] + "..." if len(details) > 50 else details,
                last_check
            )
        
        self.console.print(table)
    
    def show_service_metrics(self, metrics: Dict[str, Any]) -> None:
        """Display service performance metrics."""
        theme = self.theme_manager.get_current_theme()
        
        if not metrics:
            self.console.print("No metrics available.", style=theme.muted_color)
            return
        
        metrics_table = Table(
            title="Service Metrics",
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color,
            box=box.MINIMAL_DOUBLE_HEAD
        )
        
        metrics_table.add_column("Metric", style=theme.text_color)
        metrics_table.add_column("Value", justify="right", style=theme.accent_color)
        metrics_table.add_column("Status", justify="center")
        
        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict):
                value = metric_data.get('value', 'N/A')
                status = metric_data.get('status', 'unknown')
                
                status_icon = {
                    'good': '✅',
                    'warning': '⚠️',
                    'critical': '❌',
                    'unknown': '❓'
                }.get(status, '❓')
                
                metrics_table.add_row(
                    metric_name.replace('_', ' ').title(),
                    str(value),
                    status_icon
                )
            else:
                metrics_table.add_row(
                    metric_name.replace('_', ' ').title(),
                    str(metric_data),
                    '✅'
                )
        
        self.console.print(metrics_table)