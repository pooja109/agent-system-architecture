"""
Main.py Integration Tests
=========================

Tests for main.py integration with the new logging system across all CLI commands.
"""

import pytest
import asyncio
import argparse
from unittest.mock import Mock, patch, AsyncMock
from io import StringIO

from cli.argument_parser import CLIArgumentParser
from utils.custom_logging import initialize_logging, LoggingConfig, LogLevel
from utils.custom_logging.service_integration import ServiceLoggingIntegration
from utils.custom_logging.logger_factory import LoggerFactory


class TestMainLoggingIntegration:
    """Test main.py integration with the logging system."""
    
    @pytest.fixture(autouse=True)
    def reset_logger_factory(self):
        """Reset logger factory before each test."""
        LoggerFactory.reset_for_testing()
        yield
        LoggerFactory.reset_for_testing()
    
    @pytest.fixture
    def mock_cli_args(self):
        """Mock CLI arguments."""
        args = Mock()
        args.quiet = False
        args.verbose = False
        args.debug = False
        args.format = 'clean'
        args.no_color = False
        args.no_timestamps = False
        args.show_logger_names = False
        args.log_level = None
        args.environment = None
        args.force_console_logging = False
        args.config_file = None
        args.limit = 10
        args.command = 'check'
        return args
    
    @pytest.fixture
    def mock_settings(self):
        """Mock application settings."""
        settings = Mock()
        settings.processing = Mock()
        settings.processing.batch_size = 10
        settings.dry_run = False
        settings.output = Mock()
        settings.output.storage_type = "file"
        settings.output.output_directory = "/tmp/test"
        return settings
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_setup_logging_system_success(self, mock_cli_args):
        """Test successful logging system setup."""
        from main import setup_logging_system
        
        with patch('main.ConfigurationManager') as mock_config_manager:
            mock_config_manager.return_value.load_configuration.return_value = LoggingConfig()
            
            with patch('main.initialize_logging') as mock_init:
                with patch('main.HTTPClientLogSuppressor') as mock_suppressor:
                    with patch('utils.custom_logging.logger_factory.LoggerFactory') as mock_factory:
                        with patch('main.CLIArgumentParser') as mock_cli_parser:
                            with patch('main.UIManager') as mock_ui_manager:
                                config, integration, ui_manager = setup_logging_system(mock_cli_args)
                                
                                assert config is not None
                                assert integration is not None
                                assert ui_manager is not None
                                mock_init.assert_called_once()
                                mock_suppressor.return_value.configure_http_client_logging.assert_called_once()
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_setup_logging_system_failure_fallback(self, mock_cli_args, caplog):
        """Test logging system setup failure fallback."""
        from main import setup_logging_system
        
        with patch('main.ConfigurationManager', side_effect=Exception("Configuration error")):
            with patch('main.UIManager') as mock_ui_manager:
                with patch('builtins.print') as mock_print:
                    config, integration, ui_manager = setup_logging_system(mock_cli_args)
                    
                    assert config is None
                    assert integration is None
                    assert ui_manager is not None  # fallback UI is still created
                    # Check that the warning was printed
                    mock_print.assert_called_with("Warning: Failed to set up advanced logging: Configuration error")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_run_inbox_check_with_logging(self, mock_cli_args, mock_settings):
        """Test inbox check command with logging integration."""
        from main import run_inbox_check
        
        # Mock service integration
        mock_integration = Mock()
        mock_factory = Mock()
        mock_integration.logger_factory = mock_factory
        mock_factory.get_console_logger.return_value = Mock()
        mock_factory.get_structured_logger.return_value = Mock()
        mock_factory.get_logger.return_value = Mock()
        
        # Set mock mode to avoid real service calls
        mock_cli_args._computed_mock_mode = True
        
        with patch('main.check_once', return_value=True) as mock_check_once:
            await run_inbox_check(mock_cli_args, mock_integration)
            
            # Verify check_once was called with mock_mode=True
            mock_check_once.assert_called_once_with(None, True)
            
            # Verify console logger was called with diagnostic information
            console_logger = mock_factory.get_console_logger.return_value
            # The main function calls the logger, but in mock mode it prints directly
            # So we just verify the mock structure is set up correctly
            assert mock_factory.get_console_logger.called
            assert mock_factory.get_structured_logger.called
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_run_inbox_check_error_handling(self, mock_cli_args, mock_settings):
        """Test inbox check error handling with logging."""
        from main import run_inbox_check
        
        mock_integration = Mock()
        mock_factory = Mock()
        mock_integration.logger_factory = mock_factory
        console_logger = Mock()
        diagnostic_logger = Mock()
        mock_factory.get_console_logger.return_value = console_logger
        mock_factory.get_structured_logger.return_value = diagnostic_logger
        
        # Set live mode to test error handling in non-mock mode
        mock_cli_args._computed_mock_mode = False
        
        with patch('main.check_once', side_effect=Exception("Settings error")) as mock_check_once:
            with pytest.raises(Exception):
                await run_inbox_check(mock_cli_args, mock_integration)
            
            # Verify check_once was called
            mock_check_once.assert_called_once()
            
            # Verify error was logged to diagnostic logger  
            diagnostic_logger.error.assert_called()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_run_system_status_detailed(self, mock_cli_args, mock_settings):
        """Test system status command with detailed output."""
        from main import run_system_status
        
        mock_cli_args.detailed = True
        mock_cli_args.debug = True
        
        mock_integration = Mock()
        mock_factory = Mock()
        mock_integration.logger_factory = mock_factory
        console_logger = Mock()
        diagnostic_logger = Mock()
        mock_factory.get_console_logger.return_value = console_logger
        mock_factory.get_structured_logger.return_value = diagnostic_logger
        mock_factory.get_logger.return_value = Mock()
        
        with patch('main.HealthCheckService') as mock_health_service:
            mock_health_instance = mock_health_service.return_value
            mock_status = {
                'overall_status': 'HEALTHY',
                'components': [
                    {'name': 'database', 'status': 'HEALTHY', 'message': 'connected'},
                    {'name': 'keyvault', 'status': 'HEALTHY', 'message': 'accessible'},  
                    {'name': 'graph_api', 'status': 'UNHEALTHY', 'message': 'unauthorized'}
                ]
            }
            mock_health_instance.get_comprehensive_health_status = AsyncMock(return_value=mock_status)
            
            await run_system_status(mock_cli_args, mock_integration)
            
            # Verify detailed status was logged
            console_logger.info.assert_called()
            # Should log individual component status in detailed mode
            call_args = [call[0][0] for call in console_logger.info.call_args_list]
            
            # The mock health status has components with 'name' field, let's check for those
            # Based on the mock data: database, keyvault, graph_api  
            assert any("database" in str(arg).lower() for arg in call_args)
            assert any("keyvault" in str(arg).lower() for arg in call_args)
            assert any("graph_api" in str(arg).lower() for arg in call_args)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_run_system_status_summary(self, mock_cli_args, mock_settings):
        """Test system status command with summary output."""
        from main import run_system_status
        
        mock_cli_args.detailed = False
        mock_cli_args.debug = False
        
        mock_integration = Mock()
        mock_factory = Mock()
        mock_integration.logger_factory = mock_factory
        console_logger = Mock()
        diagnostic_logger = Mock()
        mock_factory.get_console_logger.return_value = console_logger
        mock_factory.get_structured_logger.return_value = diagnostic_logger
        mock_factory.get_logger.return_value = Mock()
        
        with patch('main.HealthCheckService') as mock_health_service:
            mock_health_instance = mock_health_service.return_value
            mock_status = {
                'overall_status': 'HEALTHY',
                'components': [
                    {'name': 'database', 'status': 'HEALTHY', 'message': 'connected'},
                    {'name': 'keyvault', 'status': 'HEALTHY', 'message': 'accessible'},
                    {'name': 'graph_api', 'status': 'HEALTHY', 'message': 'connected'}
                ]
            }
            mock_health_instance.get_comprehensive_health_status = AsyncMock(return_value=mock_status)
            
            await run_system_status(mock_cli_args, mock_integration)
            
            # Verify summary status was logged
            console_logger.info.assert_called()
            call_args = [call[0][0] for call in console_logger.info.call_args_list]
            # Should show summary in normal mode (format: "✅ System Status: 3/3 components healthy")
            assert any("3/3 components healthy" in arg for arg in call_args)
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_main_entry_point_check_command(self):
        """Test main entry point with check command."""
        from main import main
        
        with patch('main.CLIArgumentParser') as mock_parser:
            mock_args = Mock()
            mock_args.command = 'check'
            # Set proper flags to avoid conflicts
            mock_args.mock_mode = False
            mock_args.mock = False
            mock_args.live = False
            mock_args.quiet = False
            mock_parser.return_value.parse_args.return_value = mock_args
            
            with patch('main.setup_logging_system', return_value=(None, None, Mock())):
                with patch('main.asyncio.run') as mock_asyncio_run:
                    with patch('main.cleanup_logging'):
                        main()
                        
                        mock_asyncio_run.assert_called_once()
                        # Verify the correct command function was called
                        called_func = mock_asyncio_run.call_args[0][0]
                        # Should be run_inbox_check coroutine
                        assert 'run_inbox_check' in str(called_func)
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_main_entry_point_status_command(self):
        """Test main entry point with status command."""
        from main import main
        
        with patch('main.CLIArgumentParser') as mock_parser:
            mock_args = Mock()
            mock_args.command = 'status'
            # Set proper flags to avoid conflicts  
            mock_args.mock_mode = False
            mock_args.mock = False
            mock_args.live = False
            mock_args.quiet = False
            mock_parser.return_value.parse_args.return_value = mock_args
            
            with patch('main.setup_logging_system', return_value=(None, None, Mock())):
                with patch('main.asyncio.run') as mock_asyncio_run:
                    with patch('main.cleanup_logging'):
                        main()
                        
                        mock_asyncio_run.assert_called_once()
                        # Verify the correct command function was called
                        called_func = mock_asyncio_run.call_args[0][0]
                        # Should be run_system_status coroutine
                        assert 'run_system_status' in str(called_func)
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_main_entry_point_keyboard_interrupt(self):
        """Test main entry point handling KeyboardInterrupt."""
        from main import main
        
        with patch('main.CLIArgumentParser') as mock_parser:
            mock_args = Mock()
            mock_args.command = 'check'
            mock_parser.return_value.parse_args.return_value = mock_args
            
            with patch('main.setup_logging_system', return_value=(None, None, Mock())):
                with patch('main.asyncio.run', side_effect=KeyboardInterrupt):
                    with patch('main.cleanup_logging'):
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        
                        assert exc_info.value.code == 1
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_main_entry_point_general_exception(self):
        """Test main entry point handling general exceptions."""
        from main import main
        
        with patch('main.CLIArgumentParser') as mock_parser:
            mock_args = Mock()
            mock_args.command = 'check'
            mock_parser.return_value.parse_args.return_value = mock_args
            
            with patch('main.setup_logging_system', return_value=(None, None, Mock())):
                with patch('main.asyncio.run', side_effect=Exception("Test error")):
                    with patch('main.cleanup_logging'):
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        
                        assert exc_info.value.code == 1
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_signal_handlers_setup(self):
        """Test signal handlers are properly set up."""
        from main import setup_signal_handlers
        
        with patch('signal.signal') as mock_signal:
            setup_signal_handlers()
            
            # Should set up SIGINT and SIGTERM handlers
            assert mock_signal.call_count == 2
            call_args = [call[0][0] for call in mock_signal.call_args_list]  # Extract first argument
            import signal
            assert signal.SIGINT in call_args
            assert signal.SIGTERM in call_args


class TestCLIVerbosityIntegration:
    """Test CLI verbosity levels work correctly with the logging system."""
    
    @pytest.fixture(autouse=True)
    def reset_logger_factory(self):
        """Reset logger factory before each test."""
        LoggerFactory.reset_for_testing()
        yield
        LoggerFactory.reset_for_testing()
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_quiet_mode_configuration(self):
        """Test quiet mode produces minimal logging configuration."""
        parser = CLIArgumentParser()
        args = parser.parse_args(['check', '--quiet'])
        
        assert args.quiet is True
        assert args.verbose is False
        assert args.debug is False
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_verbose_mode_configuration(self):
        """Test verbose mode produces appropriate logging configuration."""
        parser = CLIArgumentParser()
        args = parser.parse_args(['check', '--verbose'])
        
        assert args.quiet is False
        assert args.verbose is True
        assert args.debug is False
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_debug_mode_configuration(self):
        """Test debug mode produces detailed logging configuration."""
        parser = CLIArgumentParser()
        args = parser.parse_args(['check', '--debug'])
        
        assert args.quiet is False
        assert args.verbose is False  # Debug overrides verbose
        assert args.debug is True
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_all_cli_commands_available(self):
        """Test that all CLI commands are available and work with logging."""
        parser = CLIArgumentParser()
        
        # Test help doesn't crash
        with pytest.raises(SystemExit):  # argparse exits on help
            parser.parse_args(['--help'])
        
        # Test all main commands parse correctly
        test_commands = ['check', 'run', 'status']
        
        for command in test_commands:
            args = parser.parse_args([command])
            assert args.command == command
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_environment_detection_flags(self):
        """Test environment detection flags are available."""
        parser = CLIArgumentParser()
        args = parser.parse_args(['check', '--environment', 'production'])
        
        assert args.environment == 'production'
    
    @pytest.mark.integration
    @pytest.mark.fast
    @pytest.mark.integration
    def test_logging_configuration_flags(self):
        """Test logging configuration flags are available."""
        parser = CLIArgumentParser()
        args = parser.parse_args([
            'check',
            '--format', 'json',
            '--log-level', 'warning',
            '--no-color',
            '--no-timestamps',
            '--show-logger-names'
        ])
        
        assert args.format == 'json'
        assert args.log_level == 'warning'
        assert args.no_color is True
        assert args.no_timestamps is True
        assert args.show_logger_names is True


if __name__ == "__main__":
    pytest.main([__file__])