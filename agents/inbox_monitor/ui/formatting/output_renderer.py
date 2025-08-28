# ui/formatting/output_renderer.py
import json
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.json import JSON

from utils.custom_logging import OutputFormat
from .rich_formatter import RichFormatter
from .table_formatter import TableFormatter
from .theme_manager import ThemeManager


class RenderMode(str, Enum):
    """Available rendering modes."""
    TABLE = "table"
    TREE = "tree" 
    COMPACT = "compact"
    LIST = "list"
    GRID = "grid"


class OutputRenderer:
    """Advanced output rendering with format selection and layout management."""
    
    def __init__(self, console: Console, theme_manager: ThemeManager):
        self.console = console
        self.theme_manager = theme_manager
        self.rich_formatter = RichFormatter(console, theme_manager)
        self.table_formatter = TableFormatter(console, theme_manager)
    
    def render(self, data: Any, format_type: str = 'clean', **options) -> None:
        """Render data in the specified format."""
        if format_type == 'json':
            self._render_json(data)
        elif format_type == 'table':
            self._render_table(data, **options)
        elif format_type == 'compact':
            self._render_compact(data)
        elif format_type == 'tree':
            self._render_tree(data)
        else:
            # Default to rich formatting
            self._render_rich(data, **options)
    
    def render_data(self, data: Union[Dict, List], 
                   output_format: OutputFormat,
                   render_mode: Optional[RenderMode] = None,
                   title: Optional[str] = None) -> None:
        """Render data in the specified format and mode."""
        
        if output_format == OutputFormat.JSON:
            self._render_json_advanced(data)
        elif output_format == OutputFormat.CLEAN:
            self._render_clean(data, render_mode, title)
        elif output_format == OutputFormat.DETAILED:
            self._render_detailed(data, render_mode, title)
        elif output_format == OutputFormat.MINIMAL:
            self._render_minimal(data)
        else:
            # Handle extended formats
            if hasattr(output_format, 'value'):
                format_value = output_format.value
            else:
                format_value = str(output_format)
            
            if format_value == "table":
                self._render_table_advanced(data, title)
            elif format_value == "tree":
                self._render_tree_advanced(data, title)
            elif format_value == "compact":
                self._render_compact_advanced(data)
            else:
                # Fallback to clean format
                self._render_clean(data, render_mode, title)
    
    def _render_json(self, data: Any) -> None:
        """Render as JSON."""
        if isinstance(data, dict):
            json_obj = JSON.from_data(data)
            self.console.print(json_obj)
        else:
            self.console.print_json(str(data))
    
    def _render_table(self, data: Any, title: Optional[str] = None, **options) -> None:
        """Render as table."""
        if isinstance(data, list) and data and isinstance(data[0], dict):
            table = self.table_formatter.create_data_table(data, title=title)
            self.console.print(table)
        elif isinstance(data, dict):
            table = self.table_formatter.format_key_value_table(data, title=title)
            self.console.print(table)
        else:
            # Fallback to rich formatting
            self.rich_formatter.format_json_output({'data': data})
    
    def _render_compact(self, data: Any) -> None:
        """Render in compact format."""
        if isinstance(data, dict):
            # One-line key-value format
            items = [f"{k}={v}" for k, v in data.items()]
            self.console.print(" | ".join(items))
        else:
            self.console.print(str(data))
    
    def _render_tree(self, data: Any) -> None:
        """Render as tree structure."""
        from rich.tree import Tree
        
        if isinstance(data, dict):
            tree = Tree("Data")
            self._add_dict_to_tree(tree, data)
            self.console.print(tree)
        else:
            # Fallback to rich formatting
            self.rich_formatter.format_json_output({'data': data})
    
    def _render_rich(self, data: Any, **options) -> None:
        """Render using rich formatting."""
        if isinstance(data, dict):
            self.rich_formatter.format_json_output(data)
        else:
            self.console.print(data)
    
    def _add_dict_to_tree(self, tree, data: dict) -> None:
        """Recursively add dictionary data to tree."""
        for key, value in data.items():
            if isinstance(value, dict):
                branch = tree.add(str(key))
                self._add_dict_to_tree(branch, value)
            elif isinstance(value, list):
                branch = tree.add(f"{key} [{len(value)} items]")
                for i, item in enumerate(value[:5]):  # Limit to first 5 items
                    branch.add(f"[{i}]: {str(item)[:50]}...")
                if len(value) > 5:
                    branch.add("...")
            else:
                tree.add(f"{key}: {str(value)}")