# ui/terminal/terminal_abstraction.py
import os
import sys
from typing import Optional, Dict, Any
from rich.console import Console

from .capability_detector import TerminalCapabilities


class TerminalAbstraction:
    """Cross-platform terminal abstraction layer."""
    
    def __init__(self):
        self.capabilities = TerminalCapabilities()
        self.console = Console()
    
    def get_width(self) -> int:
        """Get terminal width with fallback."""
        return self.capabilities.get_optimal_width()
    
    def get_height(self) -> int:
        """Get terminal height with fallback."""
        return self.capabilities.capabilities.get('height', 24)
    
    def supports_colors(self) -> bool:
        """Check if terminal supports colors."""
        return self.capabilities.should_use_colors()
    
    def supports_unicode(self) -> bool:
        """Check if terminal supports Unicode."""
        return self.capabilities.should_use_unicode()
    
    def supports_emoji(self) -> bool:
        """Check if terminal supports emoji."""
        return self.capabilities.should_use_emoji()
    
    def is_interactive(self) -> bool:
        """Check if terminal is interactive."""
        return (
            self.capabilities.capabilities.get('is_terminal', False) and
            not self.capabilities.capabilities.get('ci_environment', False)
        )
    
    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform-specific terminal information."""
        return {
            'platform': sys.platform,
            'terminal_type': self.capabilities.capabilities.get('terminal_type', 'unknown'),
            'color_system': self.capabilities.capabilities.get('color_system', 'none'),
            'width': self.get_width(),
            'height': self.get_height(),
            'supports_ansi': self.capabilities.capabilities.get('supports_ansi', False),
            'interactive': self.is_interactive()
        }
    
    def clear_screen(self) -> None:
        """Clear the terminal screen if supported."""
        if self.is_interactive():
            if os.name == 'nt':  # Windows
                os.system('cls')
            else:  # Unix-like
                os.system('clear')
    
    def set_title(self, title: str) -> None:
        """Set terminal window title if supported."""
        if self.is_interactive() and self.supports_unicode():
            # ANSI escape sequence for setting title
            sys.stdout.write(f'\033]0;{title}\007')
            sys.stdout.flush()