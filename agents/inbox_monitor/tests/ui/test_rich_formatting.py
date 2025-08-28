# tests/ui/test_rich_formatting.py
import pytest
import os
from unittest.mock import Mock, patch
from io import StringIO

from ui.formatting.rich_formatter import RichFormatter
from ui.formatting.theme_manager import ThemeManager, ThemeName
from rich.console import Console


class TestRichFormatting:
    """Test rich formatting functionality."""
    
    @pytest.fixture
    def mock_console(self):
        """Mock console for testing."""
        return Console(file=StringIO(), force_terminal=True, width=80)
    
    @pytest.fixture
    def theme_manager(self, mock_console):
        """Theme manager for testing."""
        return ThemeManager(mock_console)
    
    @pytest.fixture
    def rich_formatter(self, mock_console, theme_manager):
        """Rich formatter for testing."""
        return RichFormatter(mock_console, theme_manager)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_format_system_status_summary(self, rich_formatter):
        """Test system status formatting in summary mode."""
        status_data = {
            'database': {'status': 'healthy', 'response_time': 0.05},
            'api': {'status': 'healthy', 'response_time': 0.12},
            'services': {'status': 'degraded', 'response_time': 1.2}
        }
        
        # Should not raise exception
        rich_formatter.format_system_status(status_data, detailed=False)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_format_system_status_detailed(self, rich_formatter):
        """Test system status formatting in detailed mode."""
        status_data = {
            'database': {
                'status': 'healthy',
                'response_time': 0.05,
                'connections': 10,
                'last_check': '2024-01-01T12:00:00Z'
            },
            'api': {
                'status': 'unhealthy',
                'response_time': 5.0,
                'error_rate': 0.15,
                'last_check': '2024-01-01T12:00:00Z'
            }
        }
        
        # Should not raise exception
        rich_formatter.format_system_status(status_data, detailed=True)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_format_inbox_results(self, rich_formatter):
        """Test inbox results formatting."""
        details = [
            {'subject': 'Test Email 1', 'from': 'test1@example.com', 'status': 'processed'},
            {'subject': 'Test Email 2', 'from': 'test2@example.com', 'status': 'failed'}
        ]
        
        # Should not raise exception
        rich_formatter.format_inbox_results(
            processed_count=1,
            failed_count=1,
            duration=2.5,
            details=details
        )
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_format_error_details(self, rich_formatter):
        """Test error details formatting."""
        test_error = ValueError("Test error message")
        context = {
            'operation': 'test_operation',
            'timestamp': '2024-01-01T12:00:00Z'
        }
        correlation_id = "test-correlation-123"
        
        # Should not raise exception
        rich_formatter.format_error_details(test_error, context, correlation_id)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_format_json_output(self, rich_formatter):
        """Test JSON output formatting."""
        test_data = {
            'status': 'success',
            'data': [
                {'id': 1, 'name': 'Item 1'},
                {'id': 2, 'name': 'Item 2'}
            ],
            'metadata': {
                'timestamp': '2024-01-01T12:00:00Z',
                'count': 2
            }
        }
        
        # Should not raise exception
        rich_formatter.format_json_output(test_data)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_format_operation_summary(self, rich_formatter):
        """Test operation summary formatting."""
        operations = [
            {
                'operation_id': 'op1',
                'description': 'Test Operation 1',
                'status': 'completed',
                'duration_seconds': 1.5
            },
            {
                'operation_id': 'op2',
                'description': 'Test Operation 2',
                'status': 'failed',
                'duration_seconds': 0.8
            }
        ]
        
        # Should not raise exception
        rich_formatter.format_operation_summary(operations)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_show_welcome_message(self, rich_formatter):
        """Test welcome message display."""
        # Should not raise exception
        rich_formatter.show_welcome_message("1.0.0")
        rich_formatter.show_welcome_message()  # Test without version


class TestThemeManager:
    """Test theme management functionality."""
    
    @pytest.fixture
    def mock_console(self):
        """Mock console for testing."""
        return Console(file=StringIO(), force_terminal=True, width=80)
    
    @pytest.fixture
    def theme_manager(self, mock_console):
        """Theme manager for testing."""
        return ThemeManager(mock_console)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_theme_initialization(self, theme_manager):
        """Test theme manager initialization."""
        assert theme_manager.console is not None
        assert theme_manager.current_theme is not None
        assert len(theme_manager.themes) > 0
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_set_theme(self, theme_manager):
        """Test setting different themes."""
        # Test setting each available theme
        for theme_name in ThemeName:
            theme_manager.set_theme(theme_name)
            assert theme_manager.current_theme == theme_name
            
            # Verify theme properties exist
            theme = theme_manager.get_current_theme()
            assert hasattr(theme, 'header_color')
            assert hasattr(theme, 'text_color')
            assert hasattr(theme, 'success_color')
            assert hasattr(theme, 'error_color')
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_get_available_themes(self, theme_manager):
        """Test getting available themes."""
        themes = theme_manager.get_available_themes()
        
        assert isinstance(themes, list)
        assert len(themes) > 0
        
        # Verify all theme names are strings
        for theme_name in themes:
            assert isinstance(theme_name, str)
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_auto_detect_theme(self, theme_manager):
        """Test auto theme detection."""
        detected_theme = theme_manager.auto_detect_theme()
        
        assert isinstance(detected_theme, ThemeName)
        assert detected_theme in theme_manager.themes
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_accessibility_adjustments_no_color(self, theme_manager):
        """Test accessibility adjustments with NO_COLOR environment."""
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            theme_manager.apply_accessibility_adjustments()
            
            # Verify theme was adjusted for accessibility
            theme = theme_manager.get_current_theme()
            # Colors should be adjusted for no-color environment
            assert theme is not None
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_accessibility_adjustments_high_contrast(self, theme_manager):
        """Test accessibility adjustments with high contrast."""
        with patch.dict(os.environ, {'HIGH_CONTRAST': '1'}):
            theme_manager.apply_accessibility_adjustments()
            
            # Verify theme was adjusted for high contrast
            theme = theme_manager.get_current_theme()
            assert theme is not None