# cli/theme_config.py
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ui.formatting.theme_manager import ThemeManager, ThemeName, Theme


@dataclass
class CLIThemeConfig:
    """Configuration for CLI theming and visual customization."""
    theme_name: str = "auto"
    color_enabled: bool = True
    unicode_enabled: bool = True
    emoji_enabled: bool = True
    progress_enabled: bool = True
    compact_mode: bool = False
    terminal_width: Optional[int] = None
    accessibility_mode: bool = False
    high_contrast: bool = False


class CLIThemeConfigurator:
    """Manages CLI theme configuration and customization."""
    
    def __init__(self, theme_manager: ThemeManager):
        self.theme_manager = theme_manager
        self._config_cache: Dict[str, Any] = {}
    
    def apply_cli_args(self, cli_args) -> CLIThemeConfig:
        """Apply CLI arguments to create theme configuration."""
        config = CLIThemeConfig()
        
        # Apply CLI argument overrides
        if hasattr(cli_args, 'theme') and cli_args.theme:
            config.theme_name = cli_args.theme
        
        if hasattr(cli_args, 'no_color') and cli_args.no_color:
            config.color_enabled = False
        
        if hasattr(cli_args, 'no_unicode') and cli_args.no_unicode:
            config.unicode_enabled = False
        
        if hasattr(cli_args, 'no_emoji') and cli_args.no_emoji:
            config.emoji_enabled = False
        
        if hasattr(cli_args, 'no_progress') and cli_args.no_progress:
            config.progress_enabled = False
        
        if hasattr(cli_args, 'compact') and cli_args.compact:
            config.compact_mode = True
        
        if hasattr(cli_args, 'width') and cli_args.width:
            config.terminal_width = cli_args.width
        
        # Apply environment variable overrides
        self._apply_environment_overrides(config)
        
        # Apply accessibility settings
        self._apply_accessibility_settings(config)
        
        # Configure theme manager based on final config
        self._configure_theme_manager(config)
        
        return config
    
    def _apply_environment_overrides(self, config: CLIThemeConfig) -> None:
        """Apply environment variable overrides."""
        # NO_COLOR standard environment variable
        if os.getenv('NO_COLOR'):
            config.color_enabled = False
        
        # MONOCHROME mode
        if os.getenv('MONOCHROME'):
            config.color_enabled = False
            config.emoji_enabled = False
            config.unicode_enabled = False
        
        # Force theme selection
        if os.getenv('INBOX_MONITOR_THEME'):
            config.theme_name = os.getenv('INBOX_MONITOR_THEME')
        
        # Terminal width override
        if os.getenv('COLUMNS'):
            try:
                config.terminal_width = int(os.getenv('COLUMNS'))
            except ValueError:
                pass
        
        # Compact mode
        if os.getenv('INBOX_MONITOR_COMPACT'):
            config.compact_mode = True
        
        # Progress indicators
        if os.getenv('INBOX_MONITOR_NO_PROGRESS'):
            config.progress_enabled = False
    
    def _apply_accessibility_settings(self, config: CLIThemeConfig) -> None:
        """Apply accessibility-related settings."""
        # Check for accessibility environment variables
        accessibility_vars = [
            'HIGH_CONTRAST', 'ACCESSIBILITY_MODE', 'SCREEN_READER'
        ]
        
        if any(os.getenv(var) for var in accessibility_vars):
            config.accessibility_mode = True
            config.high_contrast = True
            
            # Accessibility-friendly defaults
            if config.theme_name == "auto":
                config.theme_name = "high_contrast"
        
        # High contrast mode
        if os.getenv('HIGH_CONTRAST'):
            config.high_contrast = True
            if config.theme_name == "auto":
                config.theme_name = "high_contrast"
        
        # Screen reader support
        if os.getenv('SCREEN_READER'):
            config.emoji_enabled = False
            config.unicode_enabled = False
            config.progress_enabled = False
    
    def _configure_theme_manager(self, config: CLIThemeConfig) -> None:
        """Configure theme manager based on configuration."""
        # Set theme
        if config.theme_name == "auto":
            detected_theme = self.theme_manager.auto_detect_theme()
            self.theme_manager.set_theme(detected_theme)
        else:
            try:
                theme_enum = ThemeName(config.theme_name)
                self.theme_manager.set_theme(theme_enum)
            except ValueError:
                # Fallback to auto-detection for invalid themes
                detected_theme = self.theme_manager.auto_detect_theme()
                self.theme_manager.set_theme(detected_theme)
        
        # Apply accessibility adjustments
        if config.accessibility_mode:
            self.theme_manager.apply_accessibility_adjustments()
    
    def get_ui_config_dict(self, config: CLIThemeConfig) -> Dict[str, Any]:
        """Convert theme config to UI manager configuration dictionary."""
        return {
            'theme': config.theme_name,
            'color_enabled': config.color_enabled,
            'unicode_enabled': config.unicode_enabled,
            'emoji_enabled': config.emoji_enabled,
            'progress_enabled': config.progress_enabled,
            'compact_mode': config.compact_mode,
            'terminal_width': config.terminal_width,
            'accessibility_mode': config.accessibility_mode,
            'high_contrast': config.high_contrast
        }
    
    def create_custom_theme(self, name: str, theme_definition: Dict[str, str]) -> Theme:
        """Create a custom theme from definition."""
        return Theme(
            name=name,
            header_color=theme_definition.get('header_color', 'bright_blue'),
            text_color=theme_definition.get('text_color', 'white'),
            muted_color=theme_definition.get('muted_color', 'bright_black'),
            success_color=theme_definition.get('success_color', 'bright_green'),
            warning_color=theme_definition.get('warning_color', 'bright_yellow'),
            error_color=theme_definition.get('error_color', 'bright_red'),
            accent_color=theme_definition.get('accent_color', 'bright_cyan'),
            border_color=theme_definition.get('border_color', 'blue'),
            background_color=theme_definition.get('background_color', 'black')
        )
    
    def register_custom_theme(self, theme: Theme) -> None:
        """Register a custom theme with the theme manager."""
        # This would extend the theme manager to support custom themes
        # For now, we'll add it to the themes dictionary
        theme_name = ThemeName(theme.name) if hasattr(ThemeName, theme.name.upper()) else theme.name
        self.theme_manager.themes[theme_name] = theme
    
    def load_theme_from_file(self, theme_file_path: str) -> Optional[Theme]:
        """Load theme definition from a file."""
        try:
            import json
            with open(theme_file_path, 'r') as f:
                theme_data = json.load(f)
            
            theme_name = theme_data.get('name', 'custom')
            colors = theme_data.get('colors', {})
            
            return self.create_custom_theme(theme_name, colors)
        except Exception as e:
            # Log error but don't fail
            print(f"Warning: Could not load theme from {theme_file_path}: {e}")
            return None
    
    def save_theme_preferences(self, config: CLIThemeConfig, 
                             preferences_file: str = "~/.inbox_monitor_theme.json") -> None:
        """Save theme preferences to file for persistence."""
        try:
            import json
            from pathlib import Path
            
            prefs_path = Path(preferences_file).expanduser()
            
            preferences = {
                'theme_name': config.theme_name,
                'color_enabled': config.color_enabled,
                'unicode_enabled': config.unicode_enabled,
                'emoji_enabled': config.emoji_enabled,
                'compact_mode': config.compact_mode,
                'accessibility_mode': config.accessibility_mode
            }
            
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(prefs_path, 'w') as f:
                json.dump(preferences, f, indent=2)
                
        except Exception as e:
            # Non-critical error, just warn
            print(f"Warning: Could not save theme preferences: {e}")
    
    def load_theme_preferences(self, 
                             preferences_file: str = "~/.inbox_monitor_theme.json") -> Optional[CLIThemeConfig]:
        """Load theme preferences from file."""
        try:
            import json
            from pathlib import Path
            
            prefs_path = Path(preferences_file).expanduser()
            
            if not prefs_path.exists():
                return None
            
            with open(prefs_path, 'r') as f:
                preferences = json.load(f)
            
            config = CLIThemeConfig()
            config.theme_name = preferences.get('theme_name', 'auto')
            config.color_enabled = preferences.get('color_enabled', True)
            config.unicode_enabled = preferences.get('unicode_enabled', True)
            config.emoji_enabled = preferences.get('emoji_enabled', True)
            config.compact_mode = preferences.get('compact_mode', False)
            config.accessibility_mode = preferences.get('accessibility_mode', False)
            
            return config
            
        except Exception as e:
            print(f"Warning: Could not load theme preferences: {e}")
            return None
    
    def get_theme_preview(self, theme_name: str) -> str:
        """Get a preview of what a theme looks like."""
        try:
            # Temporarily switch to the theme
            current_theme = self.theme_manager.current_theme
            
            if theme_name == "auto":
                preview_theme = self.theme_manager.auto_detect_theme()
            else:
                preview_theme = ThemeName(theme_name)
            
            self.theme_manager.set_theme(preview_theme)
            theme = self.theme_manager.get_current_theme()
            
            # Generate preview text
            preview_lines = [
                f"Theme: {theme.name}",
                f"Header: [{theme.header_color}]Sample Header Text[/{theme.header_color}]",
                f"Text: [{theme.text_color}]Normal text content[/{theme.text_color}]",
                f"Success: [{theme.success_color}]✅ Operation completed[/{theme.success_color}]",
                f"Warning: [{theme.warning_color}]⚠️  Warning message[/{theme.warning_color}]",
                f"Error: [{theme.error_color}]❌ Error occurred[/{theme.error_color}]",
                f"Accent: [{theme.accent_color}]🔗 Links and highlights[/{theme.accent_color}]",
                f"Muted: [{theme.muted_color}]Secondary information[/{theme.muted_color}]"
            ]
            
            preview = "\n".join(preview_lines)
            
            # Restore original theme
            self.theme_manager.set_theme(current_theme)
            
            return preview
            
        except Exception as e:
            return f"Error generating preview for theme '{theme_name}': {e}"
    
    def list_available_themes(self) -> Dict[str, str]:
        """Get list of available themes with descriptions."""
        theme_descriptions = {
            'auto': 'Automatically detect appropriate theme based on terminal',
            'default': 'Standard blue theme with good contrast',
            'dark': 'Dark theme for dark terminals',
            'light': 'Light theme for light terminals',
            'minimal': 'No colors, minimal formatting',
            'professional': 'Professional blue theme with enhanced contrast',
            'high_contrast': 'High contrast theme for accessibility'
        }
        
        return theme_descriptions
    
    def validate_theme_config(self, config: CLIThemeConfig) -> bool:
        """Validate theme configuration for consistency."""
        # Check for conflicting settings
        if config.accessibility_mode and config.emoji_enabled:
            print("Warning: Emoji enabled in accessibility mode - this may cause issues with screen readers")
        
        if not config.color_enabled and config.theme_name not in ['minimal', 'auto']:
            print(f"Warning: Colors disabled but theme '{config.theme_name}' requires color support")
        
        if config.compact_mode and config.progress_enabled:
            print("Info: Progress indicators will be simplified in compact mode")
        
        return True