# ui/formatting/table_formatter.py
from typing import List, Dict, Any, Optional
from rich.table import Table
from rich.console import Console
from rich import box

from .theme_manager import ThemeManager


class TableFormatter:
    """Formats data into rich tables."""
    
    def __init__(self, console: Console, theme_manager: ThemeManager):
        self.console = console
        self.theme_manager = theme_manager
    
    def create_data_table(self, data: List[Dict[str, Any]], 
                         title: Optional[str] = None,
                         headers: Optional[List[str]] = None) -> Table:
        """Create a formatted table from data."""
        theme = self.theme_manager.get_current_theme()
        
        table = Table(
            title=title,
            show_header=True,
            header_style=f"bold {theme.header_color}",
            border_style=theme.border_color,
            box=box.ROUNDED
        )
        
        if not data:
            return table
        
        # Determine columns
        if headers:
            columns = headers
        else:
            columns = list(data[0].keys()) if data else []
        
        # Add columns
        for col in columns:
            table.add_column(col.replace('_', ' ').title(), style=theme.text_color)
        
        # Add rows
        for row in data:
            table.add_row(*[str(row.get(col, '')) for col in columns])
        
        return table
    
    def format_key_value_table(self, data: Dict[str, Any], 
                              title: Optional[str] = None) -> Table:
        """Format key-value data as a table."""
        theme = self.theme_manager.get_current_theme()
        
        table = Table(
            title=title,
            show_header=False,
            border_style=theme.border_color,
            box=box.MINIMAL_DOUBLE_HEAD
        )
        
        table.add_column("Key", style=f"bold {theme.text_color}")
        table.add_column("Value", style=theme.accent_color)
        
        for key, value in data.items():
            table.add_row(key.replace('_', ' ').title(), str(value))
        
        return table