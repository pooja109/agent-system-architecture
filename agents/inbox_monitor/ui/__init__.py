# ui/__init__.py
"""
UI Package for Inbox Monitor
============================

Provides progress indicators, rich formatting, and user interface components
for the inbox monitor CLI application.
"""

from .progress.progress_manager import ProgressManager, ProgressType, OperationType
from .formatting.rich_formatter import RichFormatter
from .formatting.theme_manager import ThemeManager, ThemeName
from .terminal.capability_detector import TerminalCapabilities
from .ui_manager import UIManager

__all__ = [
    'ProgressManager', 'ProgressType', 'OperationType',
    'RichFormatter', 'ThemeManager', 'ThemeName',
    'TerminalCapabilities', 'UIManager'
]