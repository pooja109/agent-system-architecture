# tests/ui/test_terminal_compatibility.py
import pytest
import os
import sys
from unittest.mock import Mock, patch
from io import StringIO

from ui.terminal.capability_detector import TerminalCapabilities
from ui.terminal.accessibility import AccessibilityManager
from rich.console import Console


class TestTerminalCompatibility:
    """Test terminal capability detection and compatibility."""
    
    @pytest.fixture
    def mock_console(self):
        """Mock console for testing."""
        return Console(file=StringIO(), force_terminal=True, width=80)
    
    @pytest.fixture
    def terminal_caps(self):
        """Terminal capabilities for testing."""
        return TerminalCapabilities()
    
    @pytest.fixture
    def accessibility_manager(self, mock_console):
        """Accessibility manager for testing."""
        return AccessibilityManager(mock_console)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_terminal_capabilities_initialization(self, terminal_caps):
        """Test terminal capabilities initialization."""
        assert terminal_caps.capabilities is not None
        assert 'is_terminal' in terminal_caps.capabilities
        assert 'color_support' in terminal_caps.capabilities
        assert 'unicode_support' in terminal_caps.capabilities
        assert 'width' in terminal_caps.capabilities
        assert 'height' in terminal_caps.capabilities
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_unicode_support_detection_utf8(self, terminal_caps):
        """Test Unicode support detection with UTF-8."""
        with patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = 'utf-8'
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['unicode_support'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_unicode_support_detection_ascii(self, terminal_caps):
        """Test Unicode support detection with ASCII."""
        with patch('sys.stdout') as mock_stdout, \
             patch.dict(os.environ, {}, clear=True):
            mock_stdout.encoding = 'ascii'
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['unicode_support'] is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_unicode_support_from_environment(self, terminal_caps):
        """Test Unicode support from environment variables."""
        with patch('sys.stdout') as mock_stdout, \
             patch.dict(os.environ, {'LANG': 'en_US.UTF-8'}):
            mock_stdout.encoding = 'ascii'
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['unicode_support'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_emoji_support_depends_on_unicode(self, terminal_caps):
        """Test emoji support depends on unicode support."""
        if terminal_caps.capabilities['unicode_support']:
            # If unicode is supported, emoji support depends on terminal type
            assert 'supports_emoji' in terminal_caps.capabilities
        else:
            # If unicode is not supported, emoji should also not be supported
            assert terminal_caps.capabilities['supports_emoji'] is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_emoji_support_friendly_terminal(self, terminal_caps):
        """Test emoji support detection in emoji-friendly terminals."""
        with patch.dict(os.environ, {'TERM_PROGRAM': 'vscode'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            # VS Code supports emoji if unicode is supported
            if caps.capabilities['unicode_support']:
                assert caps.capabilities['supports_emoji'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_terminal_type_detection_vscode(self, terminal_caps):
        """Test terminal type detection for VS Code."""
        with patch.dict(os.environ, {'TERM_PROGRAM': 'vscode'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['terminal_type'] == 'vscode'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_terminal_type_detection_windows_terminal(self, terminal_caps):
        """Test terminal type detection for Windows Terminal."""
        with patch.dict(os.environ, {'WT_SESSION': 'some-session-id'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['terminal_type'] == 'windows_terminal'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_terminal_type_detection_fallback(self, terminal_caps):
        """Test terminal type detection fallback."""
        with patch.dict(os.environ, {}, clear=True):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['terminal_type'] in ['unknown', 'generic', 'dumb']
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_accessibility_mode_no_color(self, terminal_caps):
        """Test accessibility mode detection with NO_COLOR."""
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['accessibility_mode'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_accessibility_mode_high_contrast(self, terminal_caps):
        """Test accessibility mode detection with HIGH_CONTRAST."""
        with patch.dict(os.environ, {'HIGH_CONTRAST': '1'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['accessibility_mode'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_accessibility_mode_screen_reader(self, terminal_caps):
        """Test accessibility mode detection with SCREEN_READER."""
        with patch.dict(os.environ, {'SCREEN_READER': '1'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['accessibility_mode'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ci_environment_detection_ci(self, terminal_caps):
        """Test CI environment detection with CI variable."""
        with patch.dict(os.environ, {'CI': 'true'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['ci_environment'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ci_environment_detection_github_actions(self, terminal_caps):
        """Test CI environment detection for GitHub Actions."""
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['ci_environment'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ci_environment_detection_gitlab_ci(self, terminal_caps):
        """Test CI environment detection for GitLab CI."""
        with patch.dict(os.environ, {'GITLAB_CI': 'true'}):
            # Force re-detection
            TerminalCapabilities.clear_cache()
            caps = TerminalCapabilities()
            assert caps.capabilities['ci_environment'] is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_should_use_progress_indicators(self, terminal_caps):
        """Test progress indicator usage decision."""
        should_use = terminal_caps.should_use_progress_indicators()
        assert isinstance(should_use, bool)
        
        # If in CI environment, should not use progress
        if terminal_caps.capabilities['ci_environment']:
            assert should_use is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_should_use_colors_no_color_env(self, terminal_caps):
        """Test color usage with NO_COLOR environment."""
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            should_use = terminal_caps.should_use_colors()
            assert should_use is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_should_use_colors_monochrome_env(self, terminal_caps):
        """Test color usage with MONOCHROME environment."""
        with patch.dict(os.environ, {'MONOCHROME': '1'}):
            should_use = terminal_caps.should_use_colors()
            assert should_use is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_should_use_colors_normal(self, terminal_caps):
        """Test color usage in normal conditions."""
        with patch.dict(os.environ, {}, clear=True):
            should_use = terminal_caps.should_use_colors()
            # Should match color support capability
            assert should_use == terminal_caps.capabilities['color_support']
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_optimal_width_normal(self, terminal_caps):
        """Test optimal width calculation for normal terminal."""
        optimal_width = terminal_caps.get_optimal_width()
        
        assert isinstance(optimal_width, int)
        assert 40 <= optimal_width <= 120  # Within expected bounds
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_optimal_width_narrow_terminal(self, terminal_caps):
        """Test optimal width calculation for narrow terminal."""
        with patch.object(terminal_caps, 'capabilities', {'width': 30}):
            optimal_width = terminal_caps.get_optimal_width()
            assert optimal_width >= 40  # Should enforce minimum
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_optimal_width_wide_terminal(self, terminal_caps):
        """Test optimal width calculation for wide terminal."""
        with patch.object(terminal_caps, 'capabilities', {'width': 200}):
            optimal_width = terminal_caps.get_optimal_width()
            assert optimal_width <= 120  # Should enforce maximum
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_capability_summary(self, terminal_caps):
        """Test getting capability summary."""
        summary = terminal_caps.get_capability_summary()
        
        assert isinstance(summary, dict)
        assert len(summary) > 0
        
        # Should be a copy, not the original
        assert summary is not terminal_caps.capabilities
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_cache_functionality(self):
        """Test terminal capability caching."""
        # Clear cache first
        TerminalCapabilities.clear_cache()
        
        # First instance should populate cache
        caps1 = TerminalCapabilities()
        cache_info = TerminalCapabilities.get_cache_info()
        assert cache_info['cache_exists'] is True
        assert cache_info['cache_valid'] is True
        
        # Second instance should use cache
        caps2 = TerminalCapabilities()
        # Both should have same capabilities (from cache)
        assert caps1.capabilities == caps2.capabilities
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_accessibility_manager_initialization(self, accessibility_manager):
        """Test accessibility manager initialization."""
        assert accessibility_manager.console is not None
        assert accessibility_manager.capabilities is not None
        assert isinstance(accessibility_manager.accessibility_mode, bool)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_accessibility_settings(self, accessibility_manager):
        """Test accessibility settings detection."""
        settings = accessibility_manager.get_accessibility_settings()
        
        assert isinstance(settings, dict)
        expected_keys = ['high_contrast', 'no_color', 'screen_reader', 'accessibility_mode', 'large_text', 'reduced_motion']
        
        for key in expected_keys:
            assert key in settings
            assert isinstance(settings[key], bool)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_screen_reader_format_detection(self, accessibility_manager):
        """Test screen reader format detection."""
        should_use_sr = accessibility_manager.should_use_screen_reader_format()
        assert isinstance(should_use_sr, bool)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_accessibility_text_formatting(self, accessibility_manager):
        """Test accessibility text formatting."""
        test_text = "✅ Success: Operation completed 📊"
        formatted_text = accessibility_manager.format_for_accessibility(test_text)
        
        assert isinstance(formatted_text, str)
        # If accessibility mode, should replace symbols
        if accessibility_manager.should_use_screen_reader_format():
            assert '[SUCCESS]' in formatted_text
            assert '[STATS]' in formatted_text
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_safe_characters(self, accessibility_manager):
        """Test safe character alternatives."""
        safe_chars = accessibility_manager.get_safe_characters()
        
        assert isinstance(safe_chars, dict)
        expected_keys = ['checkmark', 'cross', 'warning', 'info', 'arrow_right', 'bullet']
        
        for key in expected_keys:
            assert key in safe_chars
            assert isinstance(safe_chars[key], str)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_color_alternatives(self, accessibility_manager):
        """Test color alternatives for accessibility."""
        color_alts = accessibility_manager.get_color_alternatives()
        
        assert isinstance(color_alts, dict)
        expected_keys = ['success', 'error', 'warning', 'info', 'accent', 'muted']
        
        for key in expected_keys:
            assert key in color_alts
            assert isinstance(color_alts[key], str)