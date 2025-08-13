"""
Terminal Capability Detection - Ensures Dashboard Compatibility
"""

import os
import sys
import platform
from typing import Optional, Dict, Any


class TerminalDetector:
    """Detects terminal capabilities and environment."""
    
    def __init__(self):
        self.platform = platform.system()
        self.terminal = self._detect_terminal()
        self.ci_environment = self._detect_ci()
        self.color_support = self._detect_color_support()
        self.width = self._get_terminal_width()
        self.height = self._get_terminal_height()
    
    def _detect_terminal(self) -> Optional[str]:
        """Detect terminal type."""
        # Check common terminal environment variables
        term = os.environ.get('TERM', '')
        term_program = os.environ.get('TERM_PROGRAM', '')
        
        if 'vscode' in term_program.lower():
            return 'vscode'
        elif 'iterm' in term_program.lower():
            return 'iterm2'
        elif os.environ.get('WT_SESSION'):
            return 'windows_terminal'
        elif os.environ.get('KONSOLE_VERSION'):
            return 'konsole'
        elif os.environ.get('GNOME_TERMINAL_SERVICE'):
            return 'gnome_terminal'
        elif 'xterm' in term:
            return 'xterm'
        else:
            return 'unknown'
    
    def _detect_ci(self) -> bool:
        """Detect if running in CI/CD environment."""
        ci_vars = [
            'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS',
            'GITLAB_CI', 'JENKINS', 'TRAVIS', 'CIRCLECI',
            'AZURE_PIPELINES', 'BITBUCKET_PIPELINES'
        ]
        
        return any(os.environ.get(var) for var in ci_vars)
    
    def _detect_color_support(self) -> bool:
        """Detect if terminal supports colors."""
        # CI environments often don't support colors well
        if self.ci_environment:
            return False
        
        # Check if output is to a terminal
        if not sys.stdout.isatty():
            return False
        
        # Windows color support
        if self.platform == 'Windows':
            # Windows 10+ with proper terminal
            if self.terminal == 'windows_terminal':
                return True
            # Check for legacy Windows console
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                mode = ctypes.c_ulong()
                handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    # Enable virtual terminal processing
                    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                    mode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
                    kernel32.SetConsoleMode(handle, mode)
                    return True
            except:
                pass
            return False
        
        # Unix-like systems usually support colors
        term = os.environ.get('TERM', '')
        return term != 'dumb' and ('256color' in term or 'color' in term)
    
    def _get_terminal_width(self) -> int:
        """Get terminal width."""
        try:
            import shutil
            return shutil.get_terminal_size().columns
        except:
            return 80  # Default width
    
    def _get_terminal_height(self) -> int:
        """Get terminal height."""
        try:
            import shutil
            return shutil.get_terminal_size().lines
        except:
            return 24  # Default height
    
    def supports_rich(self) -> bool:
        """Check if terminal supports Rich library features."""
        # Need reasonable size
        if self.width < 80 or self.height < 20:
            return False
        
        # CI environments often have issues
        if self.ci_environment:
            return False
        
        # Check for known good terminals
        good_terminals = {
            'vscode', 'iterm2', 'windows_terminal',
            'konsole', 'gnome_terminal', 'xterm'
        }
        
        if self.terminal in good_terminals:
            return True
        
        # Conservative default
        return self.color_support and sys.stdout.isatty()
    
    def supports_unicode(self) -> bool:
        """Check if terminal supports Unicode characters."""
        if self.platform == 'Windows' and self.terminal != 'windows_terminal':
            return False
        
        # Check locale
        import locale
        try:
            encoding = locale.getpreferredencoding()
            return 'utf' in encoding.lower()
        except:
            return False
    
    def is_ci_environment(self) -> bool:
        """Check if running in CI/CD."""
        return self.ci_environment
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get all terminal capabilities."""
        return {
            'platform': self.platform,
            'terminal': self.terminal,
            'ci_environment': self.ci_environment,
            'color_support': self.color_support,
            'rich_support': self.supports_rich(),
            'unicode_support': self.supports_unicode(),
            'width': self.width,
            'height': self.height
        }