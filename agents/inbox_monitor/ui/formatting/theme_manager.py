# ui/formatting/theme_manager.py
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from rich.console import Console


class ThemeName(str, Enum):
    """Available theme names."""
    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    MINIMAL = "minimal"
    PROFESSIONAL = "professional"
    HIGH_CONTRAST = "high_contrast"


@dataclass
class Theme:
    """Color theme definition."""
    name: str
    header_color: str = "bright_blue"
    text_color: str = "white"
    muted_color: str = "bright_black"
    success_color: str = "bright_green"
    warning_color: str = "bright_yellow"
    error_color: str = "bright_red"
    accent_color: str = "bright_cyan"
    border_color: str = "blue"
    background_color: str = "black"


class ThemeManager:
    """Manages color themes and visual styling."""
    
    def __init__(self, console: Console):
        self.console = console
        self.current_theme = ThemeName.DEFAULT
        self.themes = self._initialize_themes()
    
    def _initialize_themes(self) -> Dict[ThemeName, Theme]:
        """Initialize available themes."""
        return {
            ThemeName.DEFAULT: Theme(
                name="default",
                header_color="bright_blue",
                text_color="white",
                muted_color="bright_black",
                success_color="bright_green",
                warning_color="bright_yellow",
                error_color="bright_red",
                accent_color="bright_cyan",
                border_color="blue"
            ),
            ThemeName.DARK: Theme(
                name="dark",
                header_color="cyan",
                text_color="white",
                muted_color="bright_black",
                success_color="green",
                warning_color="yellow",
                error_color="red",
                accent_color="magenta",
                border_color="bright_black"
            ),
            ThemeName.LIGHT: Theme(
                name="light",
                header_color="blue",
                text_color="black",
                muted_color="bright_black",
                success_color="green",
                warning_color="orange3",
                error_color="red",
                accent_color="purple",
                border_color="blue"
            ),
            ThemeName.MINIMAL: Theme(
                name="minimal",
                header_color="white",
                text_color="white",
                muted_color="bright_black",
                success_color="white",
                warning_color="white",
                error_color="white",
                accent_color="white",
                border_color="bright_black"
            ),
            ThemeName.PROFESSIONAL: Theme(
                name="professional",
                header_color="bright_blue",
                text_color="white",
                muted_color="blue",
                success_color="green",
                warning_color="orange3",
                error_color="red",
                accent_color="cyan",
                border_color="blue"
            ),
            ThemeName.HIGH_CONTRAST: Theme(
                name="high_contrast",
                header_color="bright_white",
                text_color="bright_white",
                muted_color="bright_yellow",
                success_color="bright_green",
                warning_color="bright_yellow",
                error_color="bright_red",
                accent_color="bright_cyan",
                border_color="bright_white"
            )
        }
    
    def set_theme(self, theme_name: ThemeName) -> None:
        """Set the current theme."""
        if theme_name in self.themes:
            self.current_theme = theme_name
    
    def get_current_theme(self) -> Theme:
        """Get the currently active theme."""
        return self.themes[self.current_theme]
    
    def get_available_themes(self) -> List[str]:
        """Get list of available theme names."""
        return [theme.value for theme in ThemeName]
    
    def auto_detect_theme(self) -> ThemeName:
        """Auto-detect appropriate theme based on terminal capabilities."""
        # Basic theme detection based on terminal capabilities
        if not self.console.is_terminal:
            return ThemeName.MINIMAL
        
        # Check if terminal supports colors
        if not self.console.color_system:
            return ThemeName.MINIMAL
        
        # Check for high contrast needs (this could be enhanced with environment variables)
        import os
        if os.getenv('HIGH_CONTRAST') or os.getenv('ACCESSIBILITY_MODE'):
            return ThemeName.HIGH_CONTRAST
        
        # Default to professional theme for good balance
        return ThemeName.PROFESSIONAL
    
    def apply_accessibility_adjustments(self) -> None:
        """Apply accessibility-focused adjustments to current theme."""
        current = self.get_current_theme()
        
        # Check for accessibility environment variables
        import os
        if os.getenv('NO_COLOR') or os.getenv('MONOCHROME'):
            # Override to minimal theme for no-color environments
            self.set_theme(ThemeName.MINIMAL)
        elif os.getenv('HIGH_CONTRAST'):
            # Override to high contrast theme
            self.set_theme(ThemeName.HIGH_CONTRAST)