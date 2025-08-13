# tests/cli/test_cli_integration.py
import pytest
import argparse
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from cli.cli_integration import (
    parse_cli_args, initialize_cli_logging, get_environment_info,
    validate_cli_environment, create_enhanced_argument_parser,
    print_environment_summary, setup_enhanced_logging
)
from utils.custom_logging import LoggingConfig, LogLevel, OutputFormat


class TestCLIIntegration:
    """Test suite for CLI integration functions."""
    
    def test_parse_cli_args_basic(self):
        """Test basic CLI argument parsing."""
        args = parse_cli_args(['check', '--verbose'])
        assert args.command == 'check'
        assert args.verbose is True
    
    def test_parse_cli_args_with_format(self):
        """Test CLI parsing with format options."""
        args = parse_cli_args(['run', '--format', 'json', '--no-color'])
        assert args.command == 'run'
        assert args.format == 'json'
        assert args.no_color is True
    
    def test_enhanced_argument_parser_creation(self):
        """Test enhanced argument parser creation."""
        parser = create_enhanced_argument_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        
        # Test it can parse enhanced arguments
        args = parser.parse_args(['check', '--debug', '--format', 'detailed'])
        assert args.command == 'check'
        assert args.debug is True
        assert args.format == 'detailed'
    
    def test_enhanced_parser_verbosity_options(self):
        """Test enhanced parser verbosity options."""
        parser = create_enhanced_argument_parser()
        
        # Test quiet mode
        args = parser.parse_args(['status', '--quiet'])
        assert args.quiet is True
        
        # Test verbose mode
        args = parser.parse_args(['status', '--verbose'])
        assert args.verbose is True
        
        # Test debug mode
        args = parser.parse_args(['status', '--debug'])
        assert args.debug is True
    
    def test_enhanced_parser_environment_options(self):
        """Test enhanced parser environment options."""
        parser = create_enhanced_argument_parser()
        
        args = parser.parse_args(['check', '--environment', 'production'])
        assert args.environment == 'production'
        
        args = parser.parse_args(['check', '--force-console-logging'])
        assert args.force_console_logging is True
    
    def test_enhanced_parser_output_options(self):
        """Test enhanced parser output options."""
        parser = create_enhanced_argument_parser()
        
        args = parser.parse_args(['check', '--no-color', '--no-timestamps'])
        assert args.no_color is True
        assert args.no_timestamps is True
    
    def test_enhanced_parser_command_specific_options(self):
        """Test command-specific options in enhanced parser."""
        parser = create_enhanced_argument_parser()
        
        # Check command
        args = parser.parse_args(['check', '--limit', '25'])
        assert args.limit == 25
        
        # Run command
        args = parser.parse_args(['run', '--interval', '45'])
        assert args.interval == 45
        
        # Status command
        args = parser.parse_args(['status', '--detailed'])
        assert args.detailed is True
        
        # Setup command
        args = parser.parse_args(['setup', '--force'])
        assert args.force is True
    
    def test_enhanced_parser_backward_compatibility(self):
        """Test backward compatibility with legacy options."""
        parser = create_enhanced_argument_parser()
        
        # Legacy log level option
        args = parser.parse_args(['check', '--log-level', 'DEBUG'])
        assert args.log_level == 'DEBUG'
        
        # Legacy log format option
        args = parser.parse_args(['check', '--log-format', 'json'])
        assert args.log_format == 'json'
    
    @patch('cli.cli_integration.ConfigurationManager')
    @patch('cli.cli_integration.initialize_logging')
    def test_initialize_cli_logging_success(self, mock_init_logging, mock_config_manager):
        """Test successful CLI logging initialization."""
        # Mock configuration manager
        mock_manager_instance = MagicMock()
        mock_config_manager.return_value = mock_manager_instance
        
        mock_logging_config = MagicMock(spec=LoggingConfig)
        mock_manager_instance.load_configuration.return_value = mock_logging_config
        
        # Test initialization
        args = argparse.Namespace(verbose=True, format='json')
        result = initialize_cli_logging(args)
        
        assert result == mock_logging_config
        mock_init_logging.assert_called_once_with(mock_logging_config)
        mock_manager_instance.load_configuration.assert_called_once()
    
    @patch('cli.cli_integration.ConfigurationManager')
    @patch('cli.cli_integration.initialize_logging')
    def test_initialize_cli_logging_fallback(self, mock_init_logging, mock_config_manager):
        """Test CLI logging initialization fallback on error."""
        # Mock configuration manager to raise an exception
        mock_config_manager.side_effect = Exception("Configuration failed")
        
        args = argparse.Namespace(verbose=True)
        result = initialize_cli_logging(args)
        
        # Should return fallback configuration
        assert isinstance(result, LoggingConfig)
        mock_init_logging.assert_called()
    
    @patch('cli.cli_integration.EnvironmentDetector')
    def test_get_environment_info_simple(self, mock_detector):
        """Test get_environment_info function (simple mode)."""
        # Mock environment detector
        mock_detector_instance = MagicMock()
        mock_detector.return_value = mock_detector_instance
        
        mock_env_info = {
            'environment_type': 'development',
            'is_containerized': False,
            'is_production': False,
            'detection_confidence': 0.8,
            'extra_detail': 'should_not_appear'
        }
        mock_detector_instance.detect_environment.return_value = mock_env_info
        
        result = get_environment_info(verbose=False)
        
        expected_keys = ['environment_type', 'is_containerized', 'is_production', 'detection_confidence']
        assert all(key in result for key in expected_keys)
        assert 'extra_detail' not in result
    
    @patch('cli.cli_integration.EnvironmentDetector')
    def test_get_environment_info_verbose(self, mock_detector):
        """Test get_environment_info function (verbose mode)."""
        mock_detector_instance = MagicMock()
        mock_detector.return_value = mock_detector_instance
        
        mock_env_info = {
            'environment_type': 'development',
            'is_containerized': False,
            'detection_confidence': 0.8,
            'platform_info': {'system': 'Linux'},
            'container_info': {'type': None}
        }
        mock_detector_instance.detect_environment.return_value = mock_env_info
        
        result = get_environment_info(verbose=True)
        
        # Should return full environment information
        assert result == mock_env_info
    
    @patch('cli.cli_integration.EnvironmentDetector')
    @patch('cli.cli_integration.ConfigurationManager')
    def test_validate_cli_environment_success(self, mock_config_manager, mock_detector):
        """Test successful CLI environment validation."""
        # Mock environment detector
        mock_detector_instance = MagicMock()
        mock_detector.return_value = mock_detector_instance
        mock_detector_instance.detect_environment.return_value = {
            'detection_confidence': 0.8
        }
        
        # Mock configuration manager
        mock_manager_instance = MagicMock()
        mock_config_manager.return_value = mock_manager_instance
        mock_manager_instance.load_configuration.return_value = MagicMock(spec=LoggingConfig)
        
        result = validate_cli_environment()
        assert result is True
    
    @patch('cli.cli_integration.EnvironmentDetector')
    def test_validate_cli_environment_low_confidence(self, mock_detector):
        """Test CLI environment validation with low confidence."""
        mock_detector_instance = MagicMock()
        mock_detector.return_value = mock_detector_instance
        mock_detector_instance.detect_environment.return_value = {
            'detection_confidence': 0.2  # Low confidence
        }
        
        result = validate_cli_environment()
        assert result is False
    
    @patch('cli.cli_integration.EnvironmentDetector')
    def test_validate_cli_environment_exception(self, mock_detector):
        """Test CLI environment validation with exception."""
        mock_detector.side_effect = Exception("Validation failed")
        
        result = validate_cli_environment()
        assert result is False
    
    @patch('builtins.print')
    @patch('cli.cli_integration.EnvironmentDetector')
    @patch('cli.cli_integration.VerbosityController')
    def test_print_environment_summary_verbose(self, mock_verbosity, mock_detector, mock_print):
        """Test environment summary printing in verbose mode."""
        # Mock environment detector
        mock_detector_instance = MagicMock()
        mock_detector.return_value = mock_detector_instance
        mock_detector_instance.detect_environment.return_value = {
            'environment_type': 'development',
            'is_containerized': False,
            'is_production': False,
            'detection_confidence': 0.8,
            'platform_info': {'system': 'Linux'},
            'container_info': {'type': None},
            'cloud_info': {'detected_platforms': []}
        }
        
        # Mock verbosity controller
        mock_verbosity_instance = MagicMock()
        mock_verbosity.return_value = mock_verbosity_instance
        mock_verbosity_instance.determine_verbosity_from_args.return_value = 'verbose'
        mock_verbosity_instance.get_verbosity_description.return_value = 'Verbose mode'
        
        args = argparse.Namespace(verbose=True, debug=False)
        print_environment_summary(args)
        
        # Should print environment summary
        assert mock_print.called
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any('Environment Detection Summary' in call for call in print_calls)
    
    @patch('builtins.print')
    def test_print_environment_summary_quiet(self, mock_print):
        """Test environment summary not printed in quiet mode."""
        args = argparse.Namespace(verbose=False, debug=False)
        print_environment_summary(args)
        
        # Should not print anything
        mock_print.assert_not_called()
    
    @patch('cli.cli_integration.initialize_cli_logging')
    def test_setup_enhanced_logging_success(self, mock_init_logging):
        """Test successful enhanced logging setup."""
        mock_config = MagicMock(spec=LoggingConfig)
        mock_init_logging.return_value = mock_config
        
        args = argparse.Namespace(verbose=True)
        result = setup_enhanced_logging(args)
        
        assert result == mock_config
        mock_init_logging.assert_called_once_with(args)
    
    @patch('cli.cli_integration.initialize_cli_logging')
    @patch('cli.cli_integration.initialize_logging')
    def test_setup_enhanced_logging_fallback(self, mock_init_logging_fallback, mock_init_logging):
        """Test enhanced logging setup fallback on error."""
        mock_init_logging.side_effect = Exception("Setup failed")
        
        args = argparse.Namespace(verbose=True)
        result = setup_enhanced_logging(args)
        
        # Should return fallback LoggingConfig
        assert isinstance(result, LoggingConfig)
        mock_init_logging_fallback.assert_called()
    
    def test_get_cli_usage_examples(self):
        """Test CLI usage examples generation."""
        examples = get_cli_usage_examples()
        
        assert isinstance(examples, str)
        assert 'python main.py check' in examples
        assert '--verbose' in examples
        assert '--format json' in examples
        assert '--debug' in examples
    
    @patch('cli.cli_integration.LoggerFactory')
    @patch('cli.cli_integration.ConfigurationManager')
    def test_initialize_cli_logging_debug_mode(self, mock_config_manager, mock_logger_factory):
        """Test CLI logging initialization in debug mode."""
        # Mock logger factory
        mock_factory_instance = MagicMock()
        mock_logger_factory.return_value = mock_factory_instance
        mock_logger = MagicMock()
        mock_factory_instance.get_logger.return_value = mock_logger
        
        # Mock configuration manager
        mock_manager_instance = MagicMock()
        mock_config_manager.return_value = mock_manager_instance
        mock_logging_config = MagicMock(spec=LoggingConfig)
        mock_manager_instance.load_configuration.return_value = mock_logging_config
        mock_manager_instance.get_configuration_summary.return_value = {'test': 'summary'}
        
        args = argparse.Namespace(debug=True)
        
        with patch('cli.cli_integration.initialize_logging'):
            result = initialize_cli_logging(args)
        
        # Should log configuration summary in debug mode
        mock_logger.debug.assert_called()
        assert result == mock_logging_config
    
    def test_parse_cli_args_with_config_file(self):
        """Test CLI parsing with config file option."""
        test_path = 'test_config.yaml'
        args = parse_cli_args(['check', '--config-file', test_path])
        assert args.config_file == Path(test_path)
    
    def test_parse_cli_args_environment_override(self):
        """Test CLI parsing with environment override."""
        args = parse_cli_args(['run', '--environment', 'testing'])
        assert args.environment == 'testing'
    
    @patch('builtins.print')
    @patch('cli.cli_integration.EnvironmentDetector')
    def test_print_environment_summary_debug_mode(self, mock_detector, mock_print):
        """Test environment summary printing in debug mode with extra details."""
        mock_detector_instance = MagicMock()
        mock_detector.return_value = mock_detector_instance
        mock_detector_instance.detect_environment.return_value = {
            'environment_type': 'development',
            'is_containerized': False,
            'is_production': False,
            'detection_confidence': 0.8,
            'platform_info': {'system': 'Linux'},
            'container_info': {'type': 'docker'},
            'cloud_info': {'detected_platforms': ['aws']}
        }
        
        args = argparse.Namespace(verbose=False, debug=True)
        
        with patch('cli.cli_integration.VerbosityController'):
            print_environment_summary(args)
        
        # Should print detailed information in debug mode
        assert mock_print.called
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any('Platform:' in call for call in print_calls)
        assert any('Container Info:' in call for call in print_calls)


@pytest.mark.parametrize("command,expected_args", [
    (['check'], {'command': 'check'}),
    (['run', '--verbose'], {'command': 'run', 'verbose': True}),
    (['status', '--debug', '--format', 'json'], 
     {'command': 'status', 'debug': True, 'format': 'json'}),
    (['setup', '--force', '--quiet'], 
     {'command': 'setup', 'force': True, 'quiet': True})
])
def test_parse_cli_args_parametrized(command, expected_args):
    """Test CLI argument parsing with various combinations."""
    args = parse_cli_args(command)
    
    for key, value in expected_args.items():
        assert getattr(args, key) == value