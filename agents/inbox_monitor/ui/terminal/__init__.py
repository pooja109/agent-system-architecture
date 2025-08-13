# ui/terminal/__init__.py
"""Terminal capability detection and abstraction."""

from .capability_detector import TerminalCapabilities
from .terminal_abstraction import TerminalAbstraction
from .accessibility import AccessibilityManager

__all__ = [
    'TerminalCapabilities', 'TerminalAbstraction', 'AccessibilityManager'
]