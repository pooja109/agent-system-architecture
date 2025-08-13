# tests/cli/test_argument_parser.py
import pytest
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

from cli.argument_parser import CLIArgumentParser, create_cli_parser
from utils.custom_logging import LogLevel, OutputFormat


class TestCLIArgumentParser:
    """Test suite for CLI argument parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create CLI parser for testing."""
        return CLIArgumentParser()
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_basic_command_parsing(self, parser):
        """Test basic command parsing works correctly."""
        args = parser.parse_args(['check'])
        assert args.command == 'check'
        assert not getattr(args, 'quiet', False)
        assert not getattr(args, 'verbose', False)
        assert not getattr(args, 'debug', False)
    
    def test_verbosity_flags_mutually_exclusive(self, parser):
        """Test that verbosity flags are mutually exclusive."""
        with pytest.raises(SystemExit):
            parser.parse_args(['check', '--quiet', '--verbose'])
        
        with pytest.raises(SystemExit):
            parser.parse_args(['check', '--verbose', '--debug'])
        
        with pytest.raises(SystemExit):
            parser.parse_args(['check', '--quiet', '--debug'])
    
    def test_quiet_mode_configuration(self, parser):
        """Test quiet mode produces correct configuration."""
        args = parser.parse_args(['check', '--quiet'])
        config = parser.get_verbosity_config(args)
        
        assert config['console_level'] == LogLevel.WARNING
        assert config['console_format'] == OutputFormat.MINIMAL
    
    def test_verbose_mode_configuration(self, parser):
        """Test verbose mode produces correct configuration."""
        args = parser.parse_args(['check', '--verbose'])
        config = parser.get_verbosity_config(args)
        
        assert config['console_level'] == LogLevel.INFO
        assert config['console_format'] == OutputFormat.CLEAN
    
    def test_debug_mode_configuration(self, parser):
        """Test debug mode enables full diagnostics."""
        args = parser.parse_args(['check', '--debug'])
        config = parser.get_verbosity_config(args)
        
        assert config['console_level'] == LogLevel.DEBUG
        assert config['console_format'] == OutputFormat.DETAILED
    
    def test_output_format_options(self, parser):
        """Test output format options."""
        for fmt in ['clean', 'json', 'detailed', 'minimal']:
            args = parser.parse_args(['check', '--format', fmt])
            assert args.format == fmt
            
            config = parser.get_verbosity_config(args)
            assert config['console_format'] == OutputFormat(fmt)
    
    def test_color_and_timestamp_options(self, parser):
        """Test color and timestamp options."""
        args = parser.parse_args(['check', '--no-color', '--no-timestamps'])
        config = parser.get_verbosity_config(args)
        
        assert config['color_enabled'] is False
        assert config['timestamps_enabled'] is False
        
        # Test defaults
        args = parser.parse_args(['check'])
        config = parser.get_verbosity_config(args)
        
        assert config['color_enabled'] is True
        assert config['timestamps_enabled'] is True
    
    def test_log_level_override(self, parser):
        """Test that --log-level overrides verbosity flags."""
        args = parser.parse_args(['check', '--verbose', '--log-level', 'error'])
        config = parser.get_verbosity_config(args)
        
        # log-level should override verbose
        assert config['console_level'] == LogLevel.ERROR
    
    def test_environment_override(self, parser):
        """Test environment override option."""
        for env in ['development', 'production', 'testing']:
            args = parser.parse_args(['check', '--environment', env])
            assert args.environment == env
    
    def test_config_file_option(self, parser, tmp_path):
        """Test config file option."""
        test_path = tmp_path / 'test_config.yaml'
        test_path.write_text("# Test config")  # Create the test file
        args = parser.parse_args(['check', '--config-file', str(test_path)])
        assert args.config_file == test_path
    
    def test_force_console_logging(self, parser):
        """Test force console logging option."""
        args = parser.parse_args(['check', '--force-console-logging'])
        assert getattr(args, 'force_console_logging', False) is True
    
    def test_command_specific_options(self, parser):
        """Test command-specific options."""
        # Test check command with limit
        args = parser.parse_args(['check', '--limit', '20'])
        assert args.limit == 20
        
        # Test run command with interval
        args = parser.parse_args(['run', '--interval', '30'])
        assert args.interval == 30
        
        # Test status command with detailed
        args = parser.parse_args(['status', '--detailed'])
        assert args.detailed is True
        
        # Test setup command with force
        args = parser.parse_args(['setup', '--force'])
        assert args.force is True
    
    def test_invalid_argument_combinations(self, parser):
        """Test validation of invalid argument combinations."""
        # This should raise an error during parsing validation
        with pytest.raises(SystemExit):
            parser.parse_args(['check', '--quiet', '--format', 'json'])
        
        with pytest.raises(SystemExit):
            parser.parse_args(['check', '--debug', '--format', 'minimal'])
    
    def test_default_command_assignment(self, parser):
        """Test that default command is assigned when none provided."""
        args = parser.parse_args(['check'])
        assert args.command == 'check'
    
    def test_help_information(self, parser):
        """Test that help information is comprehensive."""
        # This tests that help doesn't crash and contains key information
        with pytest.raises(SystemExit):
            parser.parse_args(['--help'])
    
    def test_create_cli_parser_factory(self):
        """Test the factory function."""
        parser = create_cli_parser()
        assert isinstance(parser, CLIArgumentParser)
        
        # Test it can parse basic arguments
        args = parser.parse_args(['check', '--verbose'])
        assert args.command == 'check'
        assert args.verbose is True
    
    def test_show_logger_names_option(self, parser):
        """Test show logger names option."""
        args = parser.parse_args(['check', '--show-logger-names'])
        config = parser.get_verbosity_config(args)
        assert config['show_logger_names'] is True
        
        # Test default
        args = parser.parse_args(['check'])
        config = parser.get_verbosity_config(args)
        assert config['show_logger_names'] is False
    
    @patch('pathlib.Path.exists')
    def test_config_file_validation(self, mock_exists, parser):
        """Test config file path validation."""
        # Test with non-existent file
        mock_exists.return_value = False
        
        with pytest.raises(SystemExit):
            parser.parse_args(['check', '--config-file', 'nonexistent.yaml'])
        
        # Test with existing file
        mock_exists.return_value = True
        args = parser.parse_args(['check', '--config-file', 'existing.yaml'])
        assert args.config_file == Path('existing.yaml')
    
    def test_verbosity_config_structure(self, parser):
        """Test that verbosity config has all required keys."""
        args = parser.parse_args(['check'])
        config = parser.get_verbosity_config(args)
        
        required_keys = [
            'console_enabled', 'structured_enabled', 'console_level',
            'structured_level', 'console_format', 'color_enabled',
            'timestamps_enabled', 'show_logger_names'
        ]
        
        for key in required_keys:
            assert key in config
    
    def test_log_level_case_handling(self, parser):
        """Test that log level accepts valid lowercase values."""
        for level in ['debug', 'info', 'warning', 'error', 'critical']:
            args = parser.parse_args(['check', '--log-level', level])
            config = parser.get_verbosity_config(args)
            # Convert the level string to the appropriate LogLevel enum
            expected_level = LogLevel(level.upper())
            assert config['console_level'] == expected_level


@pytest.mark.parametrize("command", ["run", "check", "setup", "test", "status"])
def test_all_commands_parse_correctly(command):
    """Test that all commands parse correctly."""
    parser = create_cli_parser()
    args = parser.parse_args([command])
    assert args.command == command


@pytest.mark.parametrize("verbosity_flag,expected_level", [
    ("--quiet", LogLevel.WARNING),
    ("--verbose", LogLevel.INFO), 
    ("--debug", LogLevel.DEBUG)
])
def test_verbosity_flag_mappings(verbosity_flag, expected_level):
    """Test verbosity flag to log level mappings."""
    parser = create_cli_parser()
    args = parser.parse_args(['check', verbosity_flag])
    config = parser.get_verbosity_config(args)
    assert config['console_level'] == expected_level


@pytest.mark.parametrize("format_option", ["clean", "json", "detailed", "minimal"])
def test_format_options(format_option):
    """Test all format options."""
    parser = create_cli_parser()
    args = parser.parse_args(['check', '--format', format_option])
    assert args.format == format_option
    
    config = parser.get_verbosity_config(args)
    assert config['console_format'] == OutputFormat(format_option)