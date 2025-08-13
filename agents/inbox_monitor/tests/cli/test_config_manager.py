# tests/cli/test_config_manager.py
import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from cli.config_manager import (
    ConfigurationManager, ConfigSource, ConfigurationLayer
)
from cli.environment_detector import EnvironmentType
from utils.custom_logging import LoggingConfig, LogLevel, OutputFormat


class TestConfigurationManager:
    """Test suite for configuration management."""
    
    @pytest.fixture
    def config_manager(self):
        """Create configuration manager for testing."""
        return ConfigurationManager()
    
    def test_initialization(self, config_manager):
        """Test configuration manager initializes correctly."""
        assert config_manager is not None
        assert config_manager.environment_detector is not None
        assert len(config_manager.layers) == 0
        assert config_manager._merged_config is None
    
    def test_system_defaults_loading(self, config_manager):
        """Test system defaults are loaded correctly."""
        config_manager._load_system_defaults()
        
        assert len(config_manager.layers) == 1
        layer = config_manager.layers[0]
        assert layer.source == ConfigSource.SYSTEM_DEFAULTS
        assert layer.loaded is True
        assert 'console' in layer.data
        assert 'structured' in layer.data
    
    def test_environment_defaults_development(self, config_manager):
        """Test environment defaults for development."""
        mock_env_info = {
            'environment_type': EnvironmentType.DEVELOPMENT,
            'is_containerized': False
        }
        
        config_manager._load_environment_defaults(mock_env_info)
        
        assert len(config_manager.layers) == 1
        layer = config_manager.layers[0]
        assert layer.source == ConfigSource.ENVIRONMENT_DEFAULTS
        assert layer.loaded is True
    
    def test_environment_defaults_production(self, config_manager):
        """Test environment defaults for production."""
        mock_env_info = {
            'environment_type': EnvironmentType.PRODUCTION,
            'is_containerized': True
        }
        
        config_manager._load_environment_defaults(mock_env_info)
        
        layer = config_manager.layers[0]
        assert layer.data['console']['enabled'] is False
        assert layer.data['structured']['enabled'] is True
    
    def test_config_file_loading_yaml(self, config_manager):
        """Test loading configuration from YAML file."""
        yaml_content = """
logging:
  console:
    level: INFO
    enabled: true
  structured:
    level: DEBUG
    enabled: true
"""
        test_path = Path('test_config.yaml')
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=yaml_content)), \
             patch('yaml.safe_load', return_value={'logging': {
                 'console': {'level': 'INFO', 'enabled': True},
                 'structured': {'level': 'DEBUG', 'enabled': True}
             }}):
            
            config_manager._load_config_file(test_path)
            
            layer = config_manager.layers[0]
            assert layer.source == ConfigSource.CONFIG_FILE
            assert layer.loaded is True
            assert 'console' in layer.data
    
    def test_config_file_loading_json(self, config_manager):
        """Test loading configuration from JSON file."""
        json_content = {
            "logging": {
                "console": {"level": "INFO", "enabled": True},
                "structured": {"level": "DEBUG", "enabled": True}
            }
        }
        test_path = Path('test_config.json')
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('json.load', return_value=json_content):
            
            config_manager._load_config_file(test_path)
            
            layer = config_manager.layers[0]
            assert layer.source == ConfigSource.CONFIG_FILE
            assert layer.loaded is True
            assert layer.data['console']['level'] == 'INFO'
    
    def test_config_file_error_handling(self, config_manager):
        """Test error handling for config file loading."""
        test_path = Path('invalid_config.yaml')
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', side_effect=IOError("File not readable")):
            
            config_manager._load_config_file(test_path)
            
            layer = config_manager.layers[0]
            assert layer.source == ConfigSource.CONFIG_FILE
            assert layer.loaded is False
            assert len(layer.errors) > 0
    
    def test_environment_variables_loading(self, config_manager):
        """Test loading configuration from environment variables."""
        env_vars = {
            'LOG_LEVEL': 'DEBUG',
            'CONSOLE_LOGGING_ENABLED': 'true',
            'DISABLE_HTTP_LOGGING': 'false'
        }
        
        with patch.dict(os.environ, env_vars):
            config_manager._load_environment_variables()
            
            layer = config_manager.layers[0]
            assert layer.source == ConfigSource.ENVIRONMENT_VARS
            assert layer.loaded is True
            assert layer.data['console']['level'] == 'DEBUG'
    
    def test_cli_arguments_loading(self, config_manager):
        """Test loading configuration from CLI arguments."""
        cli_args = {
            'quiet': True,
            'format': 'json',
            'no_color': True,
            'debug': False
        }
        
        config_manager._load_cli_arguments(cli_args)
        
        layer = config_manager.layers[0]
        assert layer.source == ConfigSource.CLI_ARGS
        assert layer.loaded is True
        assert layer.data['console']['level'] == LogLevel.WARNING.value
        assert layer.data['console']['format'] == OutputFormat.MINIMAL.value
        assert layer.data['console']['color_enabled'] is False
    
    def test_verbose_cli_arguments(self, config_manager):
        """Test verbose CLI arguments loading."""
        cli_args = {'verbose': True, 'show_logger_names': True}
        
        config_manager._load_cli_arguments(cli_args)
        
        layer = config_manager.layers[0]
        assert layer.data['console']['level'] == LogLevel.INFO.value
        assert layer.data['console']['format'] == OutputFormat.CLEAN.value
        assert layer.data['console']['show_logger_name'] is True
    
    def test_debug_cli_arguments(self, config_manager):
        """Test debug CLI arguments loading."""
        cli_args = {'debug': True}
        
        config_manager._load_cli_arguments(cli_args)
        
        layer = config_manager.layers[0]
        assert layer.data['console']['level'] == LogLevel.DEBUG.value
        assert layer.data['console']['format'] == OutputFormat.DETAILED.value
        assert layer.data['disable_http_logging'] is False
        assert layer.data['suppress_azure_sdk'] is False
    
    def test_configuration_merging(self, config_manager):
        """Test configuration layer merging."""
        # Add multiple layers
        config_manager.layers = [
            ConfigurationLayer(
                source=ConfigSource.SYSTEM_DEFAULTS,
                data={'console': {'level': 'INFO', 'enabled': True}},
                priority=0,
                description="System defaults",
                loaded=True
            ),
            ConfigurationLayer(
                source=ConfigSource.CLI_ARGS,
                data={'console': {'level': 'DEBUG'}},
                priority=4,
                description="CLI args",
                loaded=True
            )
        ]
        
        merged = config_manager._merge_configuration()
        
        # CLI args should override system defaults
        assert merged['console']['level'] == 'DEBUG'
        assert merged['console']['enabled'] is True  # From system defaults
    
    def test_deep_merge_functionality(self, config_manager):
        """Test deep merge of nested dictionaries."""
        base = {
            'console': {'level': 'INFO', 'enabled': True},
            'structured': {'level': 'DEBUG'}
        }
        update = {
            'console': {'level': 'WARNING', 'color': True},
            'file': {'enabled': True}
        }
        
        result = config_manager._deep_merge(base, update)
        
        assert result['console']['level'] == 'WARNING'  # Updated
        assert result['console']['enabled'] is True  # Preserved
        assert result['console']['color'] is True  # Added
        assert result['structured']['level'] == 'DEBUG'  # Preserved
        assert result['file']['enabled'] is True  # Added
    
    def test_complete_configuration_loading(self, config_manager):
        """Test complete configuration loading process."""
        cli_args = {'verbose': True, 'format': 'json'}
        
        with patch.object(config_manager.environment_detector, 'detect_environment',
                         return_value={'environment_type': EnvironmentType.DEVELOPMENT,
                                     'is_containerized': False}):
            
            logging_config = config_manager.load_configuration(cli_args=cli_args)
            
            assert isinstance(logging_config, LoggingConfig)
            assert logging_config.console.level == LogLevel.INFO
            assert logging_config.console.format == OutputFormat.JSON
    
    def test_configuration_validation(self, config_manager):
        """Test configuration validation."""
        # Mock a production environment
        mock_env_info = {
            'is_production': True,
            'is_containerized': True,
            'force_console_logging': False
        }
        
        mock_logging_config = MagicMock()
        mock_logging_config.console.enabled = True
        mock_logging_config.console.level = LogLevel.DEBUG
        mock_logging_config.disable_http_logging = False
        
        # This should print warnings but not raise errors
        config_manager._validate_configuration(mock_logging_config, mock_env_info)
    
    def test_environment_variable_type_conversion(self, config_manager):
        """Test environment variable type conversion."""
        # Test boolean conversion
        assert config_manager._convert_env_value('true') is True
        assert config_manager._convert_env_value('false') is False
        assert config_manager._convert_env_value('1') is True
        assert config_manager._convert_env_value('0') is False
        
        # Test integer conversion
        assert config_manager._convert_env_value('123') == 123
        
        # Test float conversion
        assert config_manager._convert_env_value('1.5') == 1.5
        
        # Test string passthrough
        assert config_manager._convert_env_value('hello') == 'hello'
    
    def test_nested_value_setting(self, config_manager):
        """Test setting nested configuration values."""
        config = {}
        config_manager._set_nested_value(config, 'console.level', 'DEBUG')
        config_manager._set_nested_value(config, 'structured.enabled', True)
        
        assert config['console']['level'] == 'DEBUG'
        assert config['structured']['enabled'] is True
    
    def test_configuration_summary(self, config_manager):
        """Test configuration summary generation."""
        # Add a test layer
        config_manager.layers.append(
            ConfigurationLayer(
                source=ConfigSource.SYSTEM_DEFAULTS,
                data={'test': 'value'},
                priority=0,
                description="Test layer",
                loaded=True
            )
        )
        
        summary = config_manager.get_configuration_summary()
        
        assert 'layers' in summary
        assert len(summary['layers']) == 1
        assert summary['layers'][0]['source'] == 'system_defaults'
        assert summary['layers'][0]['loaded'] is True
    
    def test_layer_priority_sorting(self, config_manager):
        """Test that configuration layers are sorted by priority."""
        # Add layers in wrong order
        config_manager.layers = [
            ConfigurationLayer(
                source=ConfigSource.CLI_ARGS,
                data={'cli': True},
                priority=4,
                description="CLI",
                loaded=True
            ),
            ConfigurationLayer(
                source=ConfigSource.SYSTEM_DEFAULTS,
                data={'system': True},
                priority=0,
                description="System",
                loaded=True
            ),
            ConfigurationLayer(
                source=ConfigSource.ENVIRONMENT_VARS,
                data={'env': True},
                priority=3,
                description="Environment",
                loaded=True
            )
        ]
        
        merged = config_manager._merge_configuration()
        
        # Should merge in priority order: system (0) -> env (3) -> cli (4)
        # CLI should override everything
        assert 'cli' in merged
        assert 'system' in merged
        assert 'env' in merged
    
    def test_configuration_cache_management(self, config_manager):
        """Test configuration cache management."""
        assert config_manager._config_cache_valid is False
        assert config_manager._merged_config is None
        
        # Load configuration
        with patch.object(config_manager.environment_detector, 'detect_environment',
                         return_value={'environment_type': EnvironmentType.DEVELOPMENT,
                                     'is_containerized': False}):
            config_manager.load_configuration()
        
        assert config_manager._config_cache_valid is True
        assert config_manager._merged_config is not None
        
        # Clear configuration
        config_manager._clear_configuration()
        
        assert config_manager._config_cache_valid is False
        assert config_manager._merged_config is None
        assert len(config_manager.layers) == 0


@pytest.mark.parametrize("cli_args,expected_level", [
    ({'quiet': True}, LogLevel.WARNING),
    ({'verbose': True}, LogLevel.INFO),
    ({'debug': True}, LogLevel.DEBUG),
    ({}, LogLevel.INFO)  # Default
])
def test_cli_verbosity_mappings(cli_args, expected_level):
    """Test CLI verbosity to log level mappings."""
    config_manager = ConfigurationManager()
    config_manager._load_cli_arguments(cli_args)
    
    if cli_args:
        layer = config_manager.layers[0]
        if 'console' in layer.data:
            assert LogLevel(layer.data['console']['level']) == expected_level


@pytest.mark.parametrize("env_vars,expected_config", [
    ({'LOG_LEVEL': 'ERROR'}, {'console': {'level': 'ERROR'}}),
    ({'CONSOLE_LOGGING_ENABLED': 'false'}, {'console': {'enabled': False}}),
    ({'DISABLE_HTTP_LOGGING': 'true'}, {'disable_http_logging': True})
])
def test_environment_variable_mappings(env_vars, expected_config):
    """Test environment variable to configuration mappings."""
    config_manager = ConfigurationManager()
    
    with patch.dict(os.environ, env_vars):
        config_manager._load_environment_variables()
        
        if config_manager.layers:
            layer = config_manager.layers[0]
            for key, value in expected_config.items():
                if isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        assert layer.data[key][nested_key] == nested_value
                else:
                    assert layer.data[key] == value