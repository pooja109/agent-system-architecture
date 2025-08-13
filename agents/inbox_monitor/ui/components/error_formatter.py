# ui/components/error_formatter.py
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
import traceback

from ..formatting.theme_manager import ThemeManager


class ErrorFormatter:
    """Component for formatting and displaying errors with rich context."""
    
    def __init__(self, console: Console, theme_manager: ThemeManager):
        self.console = console
        self.theme_manager = theme_manager
    
    def format_error(self, error: Exception, 
                    context: Optional[Dict[str, Any]] = None,
                    correlation_id: Optional[str] = None,
                    show_traceback: bool = False) -> None:
        """Format and display an error with full context."""
        theme = self.theme_manager.get_current_theme()
        
        # Create error content
        error_content = []
        
        # Main error message
        error_header = Text()
        error_header.append("❌ ", style=theme.error_color)
        error_header.append(type(error).__name__, style=f"bold {theme.error_color}")
        error_header.append(": ", style=theme.error_color)
        error_header.append(str(error), style=theme.text_color)
        error_content.append(error_header)
        
        # Context information
        if context:
            error_content.append(Text())  # Empty line
            context_header = Text("Context:", style=f"bold {theme.text_color}")
            error_content.append(context_header)
            
            for key, value in context.items():
                if key != 'correlation_id':  # Handle correlation ID separately
                    context_line = Text()
                    context_line.append(f"  {key}: ", style=theme.muted_color)
                    context_line.append(str(value), style=theme.text_color)
                    error_content.append(context_line)
        
        # Correlation ID
        if correlation_id:
            error_content.append(Text())  # Empty line
            corr_text = Text()
            corr_text.append("Correlation ID: ", style=f"bold {theme.muted_color}")
            corr_text.append(correlation_id, style=theme.accent_color)
            error_content.append(corr_text)
        
        # Traceback if requested
        if show_traceback:
            error_content.append(Text())  # Empty line
            tb_header = Text("Traceback:", style=f"bold {theme.text_color}")
            error_content.append(tb_header)
            
            # Format traceback
            tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
            tb_text = ''.join(tb_lines)
            
            # Use syntax highlighting for traceback
            try:
                syntax = Syntax(tb_text, "python", theme="monokai", line_numbers=True)
                error_content.append(syntax)
            except:
                # Fallback to plain text if syntax highlighting fails
                tb_plain = Text(tb_text, style=theme.muted_color)
                error_content.append(tb_plain)
        
        # Combine all content
        combined_content = Text()
        for i, content in enumerate(error_content):
            if i > 0 and isinstance(content, Text):
                combined_content.append("\n")
            if isinstance(content, Text):
                combined_content.append(content)
        
        # Create panel for non-syntax content
        if show_traceback:
            # Show content without panel for traceback
            for content in error_content[:-1]:  # All except traceback
                if isinstance(content, Text):
                    self.console.print(content)
            
            # Show traceback syntax separately
            if error_content and not isinstance(error_content[-1], Text):
                self.console.print(error_content[-1])
        else:
            # Show everything in a panel
            panel = Panel(
                combined_content,
                title="[bold red]Error Details[/bold red]",
                border_style=theme.error_color,
                padding=(1, 2)
            )
            self.console.print(panel)
    
    def format_warning(self, message: str, 
                      context: Optional[Dict[str, Any]] = None) -> None:
        """Format and display a warning message."""
        theme = self.theme_manager.get_current_theme()
        
        warning_content = []
        
        # Warning message
        warning_header = Text()
        warning_header.append("⚠️ ", style=theme.warning_color)
        warning_header.append("Warning: ", style=f"bold {theme.warning_color}")
        warning_header.append(message, style=theme.text_color)
        warning_content.append(warning_header)
        
        # Context if provided
        if context:
            warning_content.append(Text())  # Empty line
            for key, value in context.items():
                context_line = Text()
                context_line.append(f"  {key}: ", style=theme.muted_color)
                context_line.append(str(value), style=theme.text_color)
                warning_content.append(context_line)
        
        # Combine content
        combined_content = Text()
        for i, content in enumerate(warning_content):
            if i > 0:
                combined_content.append("\n")
            combined_content.append(content)
        
        panel = Panel(
            combined_content,
            title="[bold yellow]Warning[/bold yellow]",
            border_style=theme.warning_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def format_validation_errors(self, errors: List[Dict[str, Any]],
                               title: str = "Validation Errors") -> None:
        """Format and display validation errors."""
        theme = self.theme_manager.get_current_theme()
        
        if not errors:
            return
        
        error_content = []
        
        for i, error in enumerate(errors):
            if i > 0:
                error_content.append(Text())  # Empty line between errors
            
            error_line = Text()
            error_line.append(f"{i+1}. ", style=theme.muted_color)
            error_line.append("❌ ", style=theme.error_color)
            
            field = error.get('field', 'unknown')
            message = error.get('message', 'Validation failed')
            value = error.get('value')
            
            error_line.append(f"{field}: ", style=f"bold {theme.text_color}")
            error_line.append(message, style=theme.error_color)
            
            if value is not None:
                error_line.append(f" (value: {value})", style=theme.muted_color)
            
            error_content.append(error_line)
        
        # Combine content
        combined_content = Text()
        for i, content in enumerate(error_content):
            if i > 0:
                combined_content.append("\n")
            combined_content.append(content)
        
        panel = Panel(
            combined_content,
            title=f"[bold red]{title}[/bold red] ({len(errors)} errors)",
            border_style=theme.error_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def format_suggestion(self, message: str, 
                         suggestions: List[str]) -> None:
        """Format and display helpful suggestions."""
        theme = self.theme_manager.get_current_theme()
        
        content = []
        
        # Main message
        main_text = Text()
        main_text.append("💡 ", style=theme.accent_color)
        main_text.append(message, style=theme.text_color)
        content.append(main_text)
        
        if suggestions:
            content.append(Text())  # Empty line
            suggestions_header = Text("Suggestions:", style=f"bold {theme.text_color}")
            content.append(suggestions_header)
            
            for suggestion in suggestions:
                suggestion_line = Text()
                suggestion_line.append("  • ", style=theme.accent_color)
                suggestion_line.append(suggestion, style=theme.text_color)
                content.append(suggestion_line)
        
        # Combine content
        combined_content = Text()
        for i, text in enumerate(content):
            if i > 0:
                combined_content.append("\n")
            combined_content.append(text)
        
        panel = Panel(
            combined_content,
            title="[bold cyan]Suggestion[/bold cyan]",
            border_style=theme.accent_color,
            padding=(1, 2)
        )
        
        self.console.print(panel)