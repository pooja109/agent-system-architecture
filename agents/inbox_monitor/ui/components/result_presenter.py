# ui/components/result_presenter.py
from typing import Dict, Any, List, Optional, Union
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

from ..formatting.theme_manager import ThemeManager
from ..formatting.table_formatter import TableFormatter


class ResultPresenter:
    """Component for presenting operation results and data."""
    
    def __init__(self, console: Console, theme_manager: ThemeManager):
        self.console = console
        self.theme_manager = theme_manager
        self.table_formatter = TableFormatter(console, theme_manager)
    
    def present_operation_result(self, result: Dict[str, Any], 
                               title: Optional[str] = None,
                               detailed: bool = False) -> None:
        """Present the result of an operation."""
        theme = self.theme_manager.get_current_theme()
        
        if not title:
            title = "Operation Result"
        
        if detailed:
            self._present_detailed_result(result, title, theme)
        else:
            self._present_summary_result(result, title, theme)
    
    def _present_summary_result(self, result: Dict[str, Any], 
                              title: str, theme) -> None:
        """Present a summary of the operation result."""
        success = result.get('success', False)
        status_icon = "✅" if success else "❌"
        status_color = theme.success_color if success else theme.error_color
        
        summary_text = Text()
        summary_text.append(f"{status_icon} ", style=status_color)
        
        if success:
            summary_text.append("Operation completed successfully", style=status_color)
            if 'count' in result:
                summary_text.append(f" ({result['count']} items processed)")
        else:
            summary_text.append("Operation failed", style=status_color)
            if 'error' in result:
                summary_text.append(f": {result['error']}")
        
        panel = Panel(
            summary_text,
            title=f"[bold]{title}[/bold]",
            border_style=theme.border_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def _present_detailed_result(self, result: Dict[str, Any], 
                               title: str, theme) -> None:
        """Present detailed operation result."""
        # Create detailed breakdown
        details = []
        
        # Status section
        success = result.get('success', False)
        status_text = Text()
        status_icon = "✅" if success else "❌"
        status_color = theme.success_color if success else theme.error_color
        
        status_text.append("Status: ", style=theme.text_color)
        status_text.append(f"{status_icon} {'Success' if success else 'Failed'}", 
                          style=status_color)
        details.append(status_text)
        
        # Metrics section
        if any(key in result for key in ['count', 'duration', 'processed', 'failed']):
            metrics_text = Text()
            metrics_text.append("Metrics: ", style=theme.text_color)
            
            metrics = []
            if 'processed' in result:
                metrics.append(f"Processed: {result['processed']}")
            if 'failed' in result:
                metrics.append(f"Failed: {result['failed']}")
            if 'count' in result:
                metrics.append(f"Total: {result['count']}")
            if 'duration' in result:
                metrics.append(f"Duration: {result['duration']:.2f}s")
            
            metrics_text.append(" | ".join(metrics), style=theme.accent_color)
            details.append(metrics_text)
        
        # Error details
        if not success and 'error' in result:
            error_text = Text()
            error_text.append("Error: ", style=theme.text_color)
            error_text.append(str(result['error']), style=theme.error_color)
            details.append(error_text)
        
        # Additional data
        if 'data' in result and result['data']:
            data_text = Text()
            data_text.append("Data: ", style=theme.text_color)
            
            data = result['data']
            if isinstance(data, dict):
                data_items = [f"{k}: {v}" for k, v in data.items()]
                data_text.append(" | ".join(data_items[:3]), style=theme.muted_color)
                if len(data_items) > 3:
                    data_text.append(f" (and {len(data_items) - 3} more)", 
                                   style=theme.muted_color)
            else:
                data_text.append(str(data)[:100], style=theme.muted_color)
                if len(str(data)) > 100:
                    data_text.append("...", style=theme.muted_color)
            
            details.append(data_text)
        
        # Combine all details
        combined_content = Text()
        for i, detail in enumerate(details):
            if i > 0:
                combined_content.append("\n")
            combined_content.append(detail)
        
        panel = Panel(
            combined_content,
            title=f"[bold]{title}[/bold]",
            border_style=theme.border_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def present_data_table(self, data: List[Dict[str, Any]], 
                          title: Optional[str] = None,
                          max_rows: Optional[int] = None) -> None:
        """Present data in table format."""
        if not data:
            theme = self.theme_manager.get_current_theme()
            self.console.print("No data to display.", style=theme.muted_color)
            return
        
        # Limit rows if specified
        display_data = data[:max_rows] if max_rows else data
        
        table = self.table_formatter.create_data_table(display_data, title=title)
        self.console.print(table)
        
        # Show truncation notice if data was limited
        if max_rows and len(data) > max_rows:
            theme = self.theme_manager.get_current_theme()
            self.console.print(
                f"... and {len(data) - max_rows} more rows (use --detailed to see all)",
                style=theme.muted_color
            )
    
    def present_comparison(self, before: Dict[str, Any], after: Dict[str, Any],
                          title: Optional[str] = None) -> None:
        """Present before/after comparison."""
        theme = self.theme_manager.get_current_theme()
        
        if not title:
            title = "Comparison"
        
        # Create side-by-side comparison
        before_panel = Panel(
            self._format_dict_content(before, theme),
            title="Before",
            border_style=theme.warning_color
        )
        
        after_panel = Panel(
            self._format_dict_content(after, theme),
            title="After",
            border_style=theme.success_color
        )
        
        comparison = Columns([before_panel, after_panel])
        
        # Wrap in outer panel
        outer_panel = Panel(
            comparison,
            title=f"[bold]{title}[/bold]",
            border_style=theme.border_color
        )
        
        self.console.print(outer_panel)
    
    def _format_dict_content(self, data: Dict[str, Any], theme) -> Text:
        """Format dictionary content for display."""
        content = Text()
        
        for i, (key, value) in enumerate(data.items()):
            if i > 0:
                content.append("\n")
            
            content.append(f"{key}: ", style=theme.text_color)
            content.append(str(value), style=theme.accent_color)
        
        return content