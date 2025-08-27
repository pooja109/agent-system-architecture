# ui/ui_manager.py
from typing import Dict, Any, Optional
from rich.console import Console
import json
import sys

from .progress.progress_manager import ProgressManager
from .formatting.rich_formatter import RichFormatter
from .formatting.theme_manager import ThemeManager, ThemeName
from .terminal.capability_detector import TerminalCapabilities
from .components.status_display import StatusDisplay
from utils.custom_logging.config import OutputFormat


class UIManager:
    """Central manager for all UI components and operations."""
    
    def __init__(self, ui_config: Dict[str, Any]):
        """Initialize UI manager with configuration."""
        self.config = ui_config
        
        # Initialize terminal capabilities
        self.terminal_caps = TerminalCapabilities()
        
        # Create console with appropriate settings
        self.console = Console(
            force_terminal=self.terminal_caps.should_use_colors(),
            force_interactive=self.terminal_caps.should_use_progress_indicators(),
            width=ui_config.get('terminal_width') or self.terminal_caps.get_optimal_width(),
            emoji=self.terminal_caps.should_use_emoji() and ui_config.get('emoji_enabled', True),
            color_system="auto" if ui_config.get('color_enabled', True) else None
        )
        
        # Initialize theme manager
        self.theme_manager = ThemeManager(self.console)
        self._setup_theme(ui_config.get('theme', 'auto'))
        
        # Initialize progress manager
        progress_enabled = (
            ui_config.get('progress_enabled', True) and 
            self.terminal_caps.should_use_progress_indicators()
        )
        self.progress_manager = ProgressManager(self.console, enabled=progress_enabled)
        
        # Initialize formatters and displays
        self.rich_formatter = RichFormatter(self.console, self.theme_manager)
        self.status_display = StatusDisplay(self.console, self.theme_manager)
    
    def _setup_theme(self, theme_name: str) -> None:
        """Set up the theme based on configuration."""
        if theme_name == 'auto':
            detected_theme = self.theme_manager.auto_detect_theme()
            self.theme_manager.set_theme(detected_theme)
        else:
            try:
                theme_enum = ThemeName(theme_name)
                self.theme_manager.set_theme(theme_enum)
            except ValueError:
                # Fall back to auto-detection if invalid theme
                detected_theme = self.theme_manager.auto_detect_theme()
                self.theme_manager.set_theme(detected_theme)
        
        # Apply accessibility adjustments
        self.theme_manager.apply_accessibility_adjustments()
    
    def show_welcome_message(self, version: Optional[str] = None) -> None:
        """Show application welcome message."""
        self.rich_formatter.show_welcome_message(version)
    
    def format_system_status(self, status_data: Dict[str, Any], detailed: bool = False) -> None:
        """Format and display system status."""
        # Get the console format from configuration
        format_type = self.config.get('console_format', OutputFormat.CLEAN)
        
        if format_type == OutputFormat.JSON:
            self._format_status_json(status_data)
        elif format_type == OutputFormat.MINIMAL:
            self._format_status_minimal(status_data)
        elif format_type == OutputFormat.TABLE:
            self._format_status_table(status_data)
        elif format_type == OutputFormat.TREE:
            self._format_status_tree(status_data)
        elif format_type == OutputFormat.COMPACT:
            self._format_status_compact(status_data)
        else:
            # Default to rich formatting (CLEAN, DETAILED, or unknown formats)
            self.rich_formatter.format_system_status(status_data, detailed)
    
    def format_inbox_results(self, processed_count: int, failed_count: int, 
                           duration: float, details: Optional[list] = None) -> None:
        """Format and display inbox check results."""
        self.rich_formatter.format_inbox_results(processed_count, failed_count, duration, details)
    
    def format_error_details(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                           correlation_id: Optional[str] = None) -> None:
        """Format and display error information."""
        self.rich_formatter.format_error_details(error, context, correlation_id)
    
    def get_progress_manager(self) -> ProgressManager:
        """Get the progress manager for operation tracking."""
        return self.progress_manager
    
    def print(self, *args, **kwargs) -> None:
        """Print to console using rich formatting."""
        self.console.print(*args, **kwargs)
    
    def print_json(self, data: Dict[str, Any]) -> None:
        """Print JSON data with syntax highlighting."""
        self.rich_formatter.format_json_output(data)
    
    def is_progress_enabled(self) -> bool:
        """Check if progress indicators are enabled."""
        return self.progress_manager.is_enabled()
    
    def get_capabilities_summary(self) -> Dict[str, Any]:
        """Get terminal capabilities summary."""
        return self.terminal_caps.get_capability_summary()
    
    def _format_status_json(self, status_data: Dict[str, Any]) -> None:
        """Format status as pure JSON output."""
        # Transform the status data to a clean JSON structure
        json_output = {
            "status": status_data.get('overall_status', 'UNKNOWN'),
            "timestamp": status_data.get('timestamp'),
            "response_time_ms": status_data.get('response_time_ms'),
            "components": []
        }
        
        # Add components
        for component in status_data.get('components', []):
            component_data = {
                "name": component.get('name'),
                "status": component.get('status'),
                "message": component.get('message'),
                "response_time_ms": component.get('response_time_ms')
            }
            if 'metrics' in component:
                component_data['metrics'] = component['metrics']
            json_output["components"].append(component_data)
        
        # Add summary
        healthy_count = sum(1 for comp in json_output["components"] if comp.get('status') == 'HEALTHY')
        json_output["summary"] = {
            "healthy_components": healthy_count,
            "total_components": len(json_output["components"])
        }
        
        # Print pure JSON without rich formatting
        print(json.dumps(json_output, indent=2, default=str))
    
    def _format_status_minimal(self, status_data: Dict[str, Any]) -> None:
        """Format status as minimal plain text."""
        components = status_data.get('components', [])
        healthy_count = sum(1 for comp in components if comp.get('status') == 'HEALTHY')
        total_count = len(components)
        overall_status = status_data.get('overall_status', 'UNKNOWN')
        colors = self._get_theme_colors()
        
        # Apply colors to overall status if enabled
        if colors['success']:
            status_color = colors['success'] if overall_status == 'HEALTHY' else colors['error']
            print(f"Status: {status_color}{overall_status}{colors['reset']} ({healthy_count}/{total_count} components)")
        else:
            print(f"Status: {overall_status} ({healthy_count}/{total_count} components)")
        
        for component in components:
            name = component.get('name', 'Unknown').replace('_', ' ').title()
            status = component.get('status', 'UNKNOWN')
            
            if colors['success']:
                status_color = colors['success'] if status == 'HEALTHY' else colors['error']
                print(f"{name}: {status_color}{status}{colors['reset']}")
            else:
                print(f"{name}: {status}")
    
    def _format_status_table(self, status_data: Dict[str, Any]) -> None:
        """Format status as ASCII table."""
        components = status_data.get('components', [])
        colors = self._get_theme_colors()
        unicode_chars = self._get_unicode_chars()
        
        # Calculate column widths
        max_name_len = max([len(comp.get('name', '').replace('_', ' ').title()) for comp in components] + [9])  # "Component"
        max_status_len = max([len(comp.get('status', '')) for comp in components] + [6])  # "Status"
        max_time_len = max([len(self._format_response_time(comp.get('response_time_ms'))) for comp in components] + [8])  # "Response"
        max_msg_len = min(40, max([len(comp.get('message', '')[:40]) for comp in components] + [7]))  # "Message"
        
        h = unicode_chars['box_horizontal']
        v = unicode_chars['box_vertical']
        tl = unicode_chars['box_top_left']
        tr = unicode_chars['box_top_right']
        bl = unicode_chars['box_bottom_left']
        br = unicode_chars['box_bottom_right']
        cross = unicode_chars['box_cross']
        tee_down = unicode_chars['box_tee_down']
        tee_up = unicode_chars['box_tee_up']
        tee_right = unicode_chars['box_tee_right']
        tee_left = unicode_chars['box_tee_left']
        
        # Print table header
        print(f"{tl}{h}{h * max_name_len}{h}{tee_down}{h}{h * max_status_len}{h}{tee_down}{h}{h * max_time_len}{h}{tee_down}{h}{h * max_msg_len}{h}{tr}")
        print(f"{v} {'Component'.ljust(max_name_len)} {v} {'Status'.ljust(max_status_len)} {v} {'Response'.ljust(max_time_len)} {v} {'Message'.ljust(max_msg_len)} {v}")
        print(f"{tee_right}{h}{h * max_name_len}{h}{cross}{h}{h * max_status_len}{h}{cross}{h}{h * max_time_len}{h}{cross}{h}{h * max_msg_len}{h}{tee_left}")
        
        # Print table rows
        for component in components:
            name = component.get('name', 'Unknown').replace('_', ' ').title()
            status = component.get('status', 'UNKNOWN')
            response_time = self._format_response_time(component.get('response_time_ms'))
            message = (component.get('message', '')[:max_msg_len-3] + "...") if len(component.get('message', '')) > max_msg_len else component.get('message', '')
            
            # Apply colors to status
            if colors['success']:
                status_color = colors['success'] if status == 'HEALTHY' else colors['error']
                colored_status = f"{status_color}{status}{colors['reset']}"
                # Account for color codes in padding
                status_display = colored_status.ljust(max_status_len + len(status_color) + len(colors['reset']))
            else:
                status_display = status.ljust(max_status_len)
            
            print(f"{v} {name.ljust(max_name_len)} {v} {status_display} {v} {response_time.ljust(max_time_len)} {v} {message.ljust(max_msg_len)} {v}")
        
        # Print table footer
        print(f"{bl}{h}{h * max_name_len}{h}{tee_up}{h}{h * max_status_len}{h}{tee_up}{h}{h * max_time_len}{h}{tee_up}{h}{h * max_msg_len}{h}{br}")
    
    def _format_status_tree(self, status_data: Dict[str, Any]) -> None:
        """Format status as hierarchical tree."""
        overall_status = status_data.get('overall_status', 'UNKNOWN')
        components = status_data.get('components', [])
        colors = self._get_theme_colors()
        unicode_chars = self._get_unicode_chars()
        
        # Tree drawing characters
        branch = unicode_chars['tree_branch']
        last = unicode_chars['tree_last']
        pipe = unicode_chars['tree_pipe']
        
        # System status with color and icon
        status_icon = self._get_component_icon('system') if self._should_use_emoji() else "[SYS]"
        if colors['success']:
            status_color = colors['success'] if overall_status == 'HEALTHY' else colors['error']
            print(f"{status_icon} System Status: {status_color}{overall_status}{colors['reset']}")
        else:
            print(f"{status_icon} System Status: {overall_status}")
        
        for i, component in enumerate(components):
            is_last = i == len(components) - 1
            prefix = last if is_last else branch
            
            name = component.get('name', 'Unknown').replace('_', ' ').title()
            status = component.get('status', 'UNKNOWN')
            
            # Choose icon based on component type and status
            if self._should_use_emoji():
                icon = self._get_component_icon(component.get('name', ''))
            else:
                icon = f"[{component.get('name', 'UNK')[:3].upper()}]"
            
            status_symbol = self._get_status_icon(status)
            
            print(f"{prefix}{icon} {name}")
            
            # Add details with proper indentation
            detail_prefix = "    " if is_last else pipe
            
            # Status line with color
            if colors['success']:
                status_color = colors['success'] if status == 'HEALTHY' else colors['error']
                print(f"{detail_prefix}{branch}Status: {status_symbol} {status_color}{status}{colors['reset']}")
            else:
                print(f"{detail_prefix}{branch}Status: {status_symbol} {status}")
            
            # Response time if available
            response_time = component.get('response_time_ms')
            has_message = bool(component.get('message', ''))
            
            if response_time is not None and response_time > 0:
                time_prefix = branch if has_message else last
                if colors['info']:
                    print(f"{detail_prefix}{time_prefix}Response Time: {colors['info']}{self._format_response_time(response_time)}{colors['reset']}")
                else:
                    print(f"{detail_prefix}{time_prefix}Response Time: {self._format_response_time(response_time)}")
            
            # Message if available
            message = component.get('message', '')
            if message:
                if colors['muted']:
                    print(f"{detail_prefix}{last}Message: {colors['muted']}{message}{colors['reset']}")
                else:
                    print(f"{detail_prefix}{last}Message: {message}")
    
    def _format_status_compact(self, status_data: Dict[str, Any]) -> None:
        """Format status as single-line compact format."""
        overall_status = status_data.get('overall_status', 'UNKNOWN')
        components = status_data.get('components', [])
        colors = self._get_theme_colors()
        
        # Create compact component status list
        comp_status = []
        for component in components:
            name_short = self._get_component_short_name(component.get('name', ''))
            status = "OK" if component.get('status') == 'HEALTHY' else "FAIL"
            response_time = component.get('response_time_ms')
            
            # Apply colors to individual component status
            if colors['success']:
                status_color = colors['success'] if status == 'OK' else colors['error']
                if response_time is not None and response_time > 0:
                    comp_status.append(f"{name_short}={status_color}{status}{colors['reset']}({int(response_time)}ms)")
                else:
                    comp_status.append(f"{name_short}={status_color}{status}{colors['reset']}")
            else:
                if response_time is not None and response_time > 0:
                    comp_status.append(f"{name_short}={status}({int(response_time)}ms)")
                else:
                    comp_status.append(f"{name_short}={status}")
        
        healthy_count = sum(1 for comp in components if comp.get('status') == 'HEALTHY')
        total_count = len(components)
        
        # Apply colors to overall status
        if colors['success']:
            overall_color = colors['success'] if overall_status == 'HEALTHY' else colors['error']
            summary_color = colors['accent'] if colors['accent'] else colors['info']
            print(f"{overall_color}{overall_status}{colors['reset']}: {' '.join(comp_status)} {summary_color}[{healthy_count}/{total_count}]{colors['reset']}")
        else:
            print(f"{overall_status}: {' '.join(comp_status)} [{healthy_count}/{total_count}]")
    
    def _format_response_time(self, response_time_ms: Optional[float]) -> str:
        """Format response time for display."""
        if response_time_ms is None or response_time_ms <= 0:
            return "-"
        if response_time_ms < 1000:
            return f"{int(response_time_ms)}ms"
        else:
            return f"{response_time_ms/1000:.1f}s"
    
    def _get_component_icon(self, component_name: str) -> str:
        """Get icon for component based on name."""
        icons = {
            'key_vault': '🔐',
            'oauth_authentication': '🔑',
            'connection_pool': '📁',
            'database_connectivity': '🗃️',
            'service_integration': '⚙️',
            'system': '📊'
        }
        return icons.get(component_name, '📊')
    
    def _get_component_short_name(self, component_name: str) -> str:
        """Get short name for component in compact format."""
        short_names = {
            'key_vault': 'KV',
            'oauth_authentication': 'OAuth',
            'connection_pool': 'Pool',
            'database_connectivity': 'ConnDB',
            'service_integration': 'Services'
        }
        return short_names.get(component_name, component_name[:6].upper())
    
    def _should_use_colors(self) -> bool:
        """Check if colors should be used based on configuration."""
        return self.config.get('color_enabled', True) and not self.config.get('no_color', False)
    
    def _should_use_unicode(self) -> bool:
        """Check if unicode characters should be used."""
        return self.config.get('unicode_enabled', True)
    
    def _should_use_emoji(self) -> bool:
        """Check if emoji characters should be used."""
        return self.config.get('emoji_enabled', True)
    
    def _get_theme_colors(self) -> dict:
        """Get color scheme based on current theme."""
        if not self._should_use_colors():
            return {
                'success': '', 'error': '', 'warning': '', 'info': '', 
                'muted': '', 'accent': '', 'reset': ''
            }
        
        theme_name = self.config.get('theme', 'auto')
        theme_colors = {
            'dark': {
                'success': '\033[92m',   # Bright green
                'error': '\033[91m',     # Bright red
                'warning': '\033[93m',   # Bright yellow
                'info': '\033[94m',      # Bright blue
                'muted': '\033[90m',     # Bright black (gray)
                'accent': '\033[96m',    # Bright cyan
                'reset': '\033[0m'       # Reset
            },
            'light': {
                'success': '\033[32m',   # Green
                'error': '\033[31m',     # Red
                'warning': '\033[33m',   # Yellow
                'info': '\033[34m',      # Blue
                'muted': '\033[37m',     # Light gray
                'accent': '\033[36m',    # Cyan
                'reset': '\033[0m'       # Reset
            },
            'professional': {
                'success': '\033[36m',   # Cyan (corporate blue-green)
                'error': '\033[31m',     # Red
                'warning': '\033[33m',   # Yellow
                'info': '\033[34m',      # Blue
                'muted': '\033[37m',     # Gray
                'accent': '\033[94m',    # Bright blue
                'reset': '\033[0m'       # Reset
            },
            'high_contrast': {
                'success': '\033[1;92m', # Bold bright green
                'error': '\033[1;91m',   # Bold bright red
                'warning': '\033[1;93m', # Bold bright yellow
                'info': '\033[1;96m',    # Bold bright cyan
                'muted': '\033[1;37m',   # Bold white
                'accent': '\033[1;95m',  # Bold bright magenta
                'reset': '\033[0m'       # Reset
            },
            'minimal': {
                'success': '', 'error': '', 'warning': '', 'info': '', 
                'muted': '', 'accent': '', 'reset': ''
            }
        }
        
        # Default to dark theme colors for auto and unknown themes
        return theme_colors.get(theme_name, theme_colors['dark'])
    
    def _get_status_icon(self, status: str, use_emoji: bool = True) -> str:
        """Get appropriate icon for status."""
        if not use_emoji:
            return "[OK]" if status == 'HEALTHY' else "[FAIL]"
        
        if not self._should_use_emoji():
            return "[OK]" if status == 'HEALTHY' else "[FAIL]"
        
        return "✅" if status == 'HEALTHY' else "❌"
    
    def _get_unicode_chars(self) -> dict:
        """Get unicode characters for drawing, with ASCII fallbacks."""
        if not self._should_use_unicode():
            return {
                'box_horizontal': '-', 'box_vertical': '|', 
                'box_top_left': '+', 'box_top_right': '+',
                'box_bottom_left': '+', 'box_bottom_right': '+',
                'box_cross': '+', 'box_tee_down': '+', 'box_tee_up': '+',
                'box_tee_right': '+', 'box_tee_left': '+',
                'tree_branch': '├── ', 'tree_last': '└── ', 'tree_pipe': '│   '
            }
        
        return {
            'box_horizontal': '─', 'box_vertical': '│',
            'box_top_left': '┌', 'box_top_right': '┐',
            'box_bottom_left': '└', 'box_bottom_right': '┘',
            'box_cross': '┼', 'box_tee_down': '┬', 'box_tee_up': '┴',
            'box_tee_right': '├', 'box_tee_left': '┤',
            'tree_branch': '├── ', 'tree_last': '└── ', 'tree_pipe': '│   '
        }