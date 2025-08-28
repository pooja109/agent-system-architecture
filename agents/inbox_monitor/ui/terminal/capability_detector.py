# ui/terminal/capability_detector.py
import os
import sys
import time
from typing import Dict, Any, Optional, ClassVar
from rich.console import Console


class TerminalCapabilities:
    """Detected terminal capabilities with caching for performance."""
    
    # Class-level cache for terminal capabilities
    _capabilities_cache: ClassVar[Optional[Dict[str, Any]]] = None
    _cache_timestamp: ClassVar[float] = 0
    _cache_duration: ClassVar[float] = 300  # 5 minutes cache
    
    def __init__(self):
        self.console = Console()
        self.capabilities = self._get_cached_capabilities()
    
    def _get_cached_capabilities(self) -> Dict[str, Any]:
        """Get capabilities with caching for performance optimization."""
        current_time = time.time()
        
        # Check if cache is valid
        if (TerminalCapabilities._capabilities_cache is not None and 
            current_time - TerminalCapabilities._cache_timestamp < TerminalCapabilities._cache_duration):
            return TerminalCapabilities._capabilities_cache
        
        # Detect capabilities and cache them
        capabilities = self._detect_capabilities()
        TerminalCapabilities._capabilities_cache = capabilities
        TerminalCapabilities._cache_timestamp = current_time
        
        return capabilities
    
    def _detect_capabilities(self) -> Dict[str, Any]:
        """Detect terminal capabilities."""
        caps = {
            'is_terminal': self.console.is_terminal,
            'color_support': self.console.color_system is not None,
            'color_system': str(self.console.color_system) if self.console.color_system else 'none',
            'unicode_support': self._detect_unicode_support(),
            'width': self.console.width if self.console.is_terminal else 80,
            'height': self.console.height if self.console.is_terminal else 24,
            'supports_ansi': self._detect_ansi_support(),
            'supports_emoji': self._detect_emoji_support(),
            'terminal_type': self._detect_terminal_type(),
            'accessibility_mode': self._detect_accessibility_mode(),
            'ci_environment': self._detect_ci_environment()
        }
        
        return caps
    
    def _detect_unicode_support(self) -> bool:
        """Detect if terminal supports Unicode characters."""
        # Check encoding
        encoding = getattr(sys.stdout, 'encoding', 'ascii')
        if encoding.lower() in ['utf-8', 'utf8']:
            return True
        
        # Check environment variables
        lang = os.getenv('LANG', '')
        lc_all = os.getenv('LC_ALL', '')
        
        return any('utf' in var.lower() for var in [lang, lc_all])
    
    def _detect_ansi_support(self) -> bool:
        """Detect ANSI escape sequence support."""
        if not self.console.is_terminal:
            return False
        
        # Windows Command Prompt historically had poor ANSI support
        if os.name == 'nt':
            # Modern Windows Terminal and PowerShell support ANSI
            term = os.getenv('TERM', '').lower()
            wt_session = os.getenv('WT_SESSION')
            
            return bool(wt_session or 'xterm' in term or 'color' in term)
        
        return True
    
    def _detect_emoji_support(self) -> bool:
        """Detect emoji support in terminal."""
        # Basic heuristics for emoji support
        if not self._detect_unicode_support():
            return False
        
        # Check terminal type
        term = os.getenv('TERM', '').lower()
        terminal_program = os.getenv('TERMINAL_PROGRAM', '').lower()
        
        # Known terminals with good emoji support
        emoji_friendly_terms = [
            'xterm-256color', 'screen-256color', 'tmux-256color',
            'alacritty', 'kitty', 'wezterm'
        ]
        
        emoji_friendly_programs = [
            'vscode', 'hyper', 'iterm', 'terminal', 'wezterm'
        ]
        
        return (
            any(friendly in term for friendly in emoji_friendly_terms) or
            any(friendly in terminal_program for friendly in emoji_friendly_programs)
        )
    
    def _detect_terminal_type(self) -> str:
        """Detect terminal type/program."""
        # Check common environment variables
        terminal_program = os.getenv('TERMINAL_PROGRAM', '')
        term_program = os.getenv('TERM_PROGRAM', '')
        term = os.getenv('TERM', '')
        
        if terminal_program:
            return terminal_program.lower()
        elif term_program:
            return term_program.lower()
        elif 'vscode' in os.getenv('TERM_PROGRAM', '').lower():
            return 'vscode'
        elif os.getenv('WT_SESSION'):
            return 'windows_terminal'
        elif term:
            return term.lower()
        else:
            return 'unknown'
    
    def _detect_accessibility_mode(self) -> bool:
        """Detect if accessibility mode should be enabled."""
        # Check for accessibility environment variables
        accessibility_vars = [
            'NO_COLOR', 'MONOCHROME', 'HIGH_CONTRAST',
            'ACCESSIBILITY_MODE', 'SCREEN_READER'
        ]
        
        return any(os.getenv(var) for var in accessibility_vars)
    
    def _detect_ci_environment(self) -> bool:
        """Detect if running in CI/CD environment."""
        ci_vars = [
            'CI', 'CONTINUOUS_INTEGRATION', 'BUILD_ID', 'BUILD_NUMBER',
            'GITHUB_ACTIONS', 'GITLAB_CI', 'TRAVIS', 'CIRCLECI',
            'JENKINS_URL', 'TEAMCITY_VERSION'
        ]
        
        return any(os.getenv(var) for var in ci_vars)
    
    def should_use_progress_indicators(self) -> bool:
        """Determine if progress indicators should be used."""
        return (
            self.capabilities['is_terminal'] and
            not self.capabilities['ci_environment'] and
            not self.capabilities['accessibility_mode']
        )
    
    def should_use_colors(self) -> bool:
        """Determine if colors should be used."""
        return (
            self.capabilities['color_support'] and
            not os.getenv('NO_COLOR') and
            not os.getenv('MONOCHROME')
        )
    
    def should_use_unicode(self) -> bool:
        """Determine if Unicode characters should be used."""
        return (
            self.capabilities['unicode_support'] and
            not self.capabilities['accessibility_mode']
        )
    
    def should_use_emoji(self) -> bool:
        """Determine if emoji should be used."""
        return (
            self.capabilities['supports_emoji'] and
            self.should_use_unicode() and
            not self.capabilities['accessibility_mode']
        )
    
    def get_optimal_width(self) -> int:
        """Get optimal display width for content."""
        terminal_width = self.capabilities['width']
        
        # Ensure minimum width and account for margins
        min_width = 40
        max_width = 120
        margin = 4
        
        optimal_width = min(max(terminal_width - margin, min_width), max_width)
        return optimal_width
    
    def get_capability_summary(self) -> Dict[str, Any]:
        """Get summary of detected capabilities."""
        return self.capabilities.copy()
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the capabilities cache (useful for testing or environment changes)."""
        cls._capabilities_cache = None
        cls._cache_timestamp = 0
    
    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """Get information about the capabilities cache."""
        current_time = time.time()
        cache_age = current_time - cls._cache_timestamp if cls._cache_timestamp > 0 else None
        
        return {
            'cache_exists': cls._capabilities_cache is not None,
            'cache_age_seconds': cache_age,
            'cache_duration': cls._cache_duration,
            'cache_valid': (cls._capabilities_cache is not None and 
                           cache_age is not None and 
                           cache_age < cls._cache_duration),
            'cache_size_estimate': len(cls._capabilities_cache) if cls._capabilities_cache else 0
        }