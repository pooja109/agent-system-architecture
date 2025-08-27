# tests/fixtures/config_mocks.py
"""
Configuration mocking utilities for testing CLI and environment functionality.
Works with existing source code patterns without modification.
"""
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest


class ConfigurationMocker:
    """
    Utilities for mocking configuration-related functionality in tests.
    """
    
    @staticmethod
    def create_temp_config_file(config_content: str, suffix: str = '.yaml') -> Path:
        """
        Create a temporary configuration file for testing.
        
        Args:
            config_content: YAML or JSON content for the config file
            suffix: File extension (.yaml, .json, etc.)
            
        Returns:
            Path to the temporary file
        """
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
        temp_file.write(config_content)
        temp_file.close()
        return Path(temp_file.name)
    
    @staticmethod
    def mock_environment_variables(env_vars: Dict[str, str]):
        """
        Context manager for mocking environment variables.
        
        Args:
            env_vars: Dictionary of environment variables to set
        """
        return patch.dict(os.environ, env_vars, clear=False)
    
    @staticmethod  
    def mock_file_exists(existing_files: List[str]):
        """
        Mock pathlib.Path.exists() to simulate file existence.
        
        Args:
            existing_files: List of file paths that should exist
        """
        def exists_mock(self):
            return str(self) in existing_files
        
        return patch('pathlib.Path.exists', exists_mock)


class EnvironmentMocker:
    """
    Utilities for mocking environment detection functionality.
    """
    
    ENVIRONMENT_SCENARIOS = {
        'development': {
            'env_vars': {'ENVIRONMENT': 'development'},
            'files': [],
            'hostname': 'dev-machine',
            'kubernetes': False,
            'container': False
        },
        'production': {
            'env_vars': {'ENVIRONMENT': 'production', 'NODE_ENV': 'production'},
            'files': ['/etc/production.conf'],
            'hostname': 'prod-server',
            'kubernetes': False,
            'container': False
        },
        'kubernetes': {
            'env_vars': {'KUBERNETES_SERVICE_HOST': '10.0.0.1'},
            'files': ['/var/run/secrets/kubernetes.io/serviceaccount/token'],
            'hostname': 'pod-12345',
            'kubernetes': True,
            'container': True
        },
        'testing': {
            'env_vars': {'ENVIRONMENT': 'testing', 'CI': 'true'},
            'files': ['/tmp/test-marker'],
            'hostname': 'test-runner',
            'kubernetes': False,
            'container': False
        },
        'docker': {
            'env_vars': {'CONTAINER_NAME': 'myapp'},
            'files': ['/.dockerenv'],
            'hostname': 'container-12345',
            'kubernetes': False,
            'container': True
        }
    }
    
    @classmethod
    def mock_environment_scenario(cls, scenario: str) -> List:
        """
        Mock a complete environment scenario.
        
        Args:
            scenario: One of 'development', 'production', 'kubernetes', 'testing', 'docker'
            
        Returns:
            List of patch objects that can be started/stopped
        """
        if scenario not in cls.ENVIRONMENT_SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}. Available: {list(cls.ENVIRONMENT_SCENARIOS.keys())}")
        
        scenario_config = cls.ENVIRONMENT_SCENARIOS[scenario]
        patches = []
        
        # Mock environment variables
        if scenario_config['env_vars']:
            patches.append(patch.dict(os.environ, scenario_config['env_vars'], clear=False))
        
        # Mock file existence - need to handle both os.path.exists and Path.exists
        if scenario_config['files']:
            def os_path_exists_mock(path):
                return path in scenario_config['files']
            def path_exists_mock(self):
                return str(self) in scenario_config['files']
            patches.append(patch('os.path.exists', os_path_exists_mock))
            patches.append(patch('pathlib.Path.exists', path_exists_mock))
        
        # Mock hostname
        patches.append(patch('platform.node', return_value=scenario_config['hostname']))
        patches.append(patch('socket.gethostname', return_value=scenario_config['hostname']))
        
        # Mock cgroup content for container detection
        if scenario_config['container']:
            if scenario == 'kubernetes':
                cgroup_content = "1:name=systemd:/kubepods/pod123/container456"
            else:
                cgroup_content = "1:name=systemd:/docker/container123"
            patches.append(patch('builtins.open', mock_open(read_data=cgroup_content)))
        
        return patches
    
    @classmethod
    def create_complete_environment_info(cls, scenario: str) -> Dict[str, Any]:
        """
        Create complete environment info structure for configuration manager testing.
        
        Args:
            scenario: Environment scenario name
            
        Returns:
            Complete environment info dictionary with all required keys
        """
        from cli.environment_detector import EnvironmentType, ContainerType
        
        base_info = {
            'environment_type': EnvironmentType.DEVELOPMENT,
            'is_containerized': False,
            'is_production': False,
            'is_kubernetes': False,
            'force_console_logging': False,
            'detection_confidence': 0.8,
            'detection_timestamp': '2025-08-23T17:45:00Z',
            'platform_info': {
                'system': 'Linux',
                'platform': 'linux',
                'architecture': 'x86_64',
                'python_version': '3.13.2'
            },
            'container_info': {
                'type': None,
                'detected_indicators': [],
                'image_info': {}
            },
            'ci_cd_info': {
                'is_ci_environment': False,
                'detected_systems': []
            },
            'cloud_info': {
                'is_cloud_environment': False,
                'detected_platforms': []
            }
        }
        
        # Customize based on scenario
        if scenario == 'production':
            base_info['environment_type'] = EnvironmentType.PRODUCTION
            base_info['is_production'] = True
        elif scenario == 'kubernetes':
            base_info['environment_type'] = EnvironmentType.KUBERNETES
            base_info['is_kubernetes'] = True
            base_info['is_containerized'] = True
            base_info['container_info']['type'] = ContainerType.KUBERNETES
        elif scenario == 'testing':
            base_info['environment_type'] = EnvironmentType.TESTING
            base_info['ci_cd_info']['is_ci_environment'] = True
            base_info['ci_cd_info']['detected_systems'] = ['ci']
        elif scenario == 'docker':
            base_info['is_containerized'] = True
            base_info['container_info']['type'] = ContainerType.DOCKER
            base_info['container_info']['detected_indicators'] = ['/.dockerenv']
        
        return base_info


class CLITestHelpers:
    """Helper utilities for CLI testing scenarios."""
    
    @staticmethod
    def create_mock_args(**kwargs):
        """Create mock argument namespace with default values."""
        default_args = {
            'command': 'check',
            'quiet': False,
            'verbose': False,
            'debug': False,
            'format': 'clean',
            'no_color': False,
            'no_timestamps': False,
            'show_logger_names': False,
            'config_file': None,
            'environment': None,
            'force_console_logging': False
        }
        default_args.update(kwargs)
        
        mock_args = Mock()
        for key, value in default_args.items():
            setattr(mock_args, key, value)
        
        return mock_args
    
    @staticmethod
    def verify_config_structure(config: Dict[str, Any]) -> bool:
        """Verify that configuration has required structure."""
        required_keys = [
            'console_enabled', 'structured_enabled', 'console_level',
            'structured_level', 'console_format', 'color_enabled',
            'timestamps_enabled', 'show_logger_names'
        ]
        return all(key in config for key in required_keys)


# Pytest Fixtures
@pytest.fixture
def config_mocker():
    """Fixture providing configuration mocking utilities."""
    return ConfigurationMocker()


@pytest.fixture
def environment_mocker():
    """Fixture providing environment mocking utilities."""
    return EnvironmentMocker()


@pytest.fixture
def cli_helpers():
    """Fixture providing CLI testing helpers."""
    return CLITestHelpers()


@pytest.fixture
def temp_config_file():
    """
    Fixture providing a temporary configuration file with cleanup.
    """
    temp_files = []
    
    def create_file(content: str, suffix: str = '.yaml') -> Path:
        temp_file = ConfigurationMocker.create_temp_config_file(content, suffix)
        temp_files.append(temp_file)
        return temp_file
    
    yield create_file
    
    # Cleanup
    for temp_file in temp_files:
        try:
            temp_file.unlink()
        except FileNotFoundError:
            pass


@pytest.fixture
def mock_cli_environment():
    """
    Fixture providing consistent CLI environment for testing.
    """
    with patch.dict(os.environ, {
        'ENVIRONMENT': 'testing',
        'LOG_LEVEL': 'INFO',
        'CLI_CONFIG_DIR': '/tmp/test-config'
    }, clear=False):
        yield


@pytest.fixture
def mock_development_environment(environment_mocker):
    """Fixture for development environment testing."""
    patches = environment_mocker.mock_environment_scenario('development')
    
    # Apply all patches
    active_patches = []
    for patch_obj in patches:
        active_patches.append(patch_obj.start())
    
    yield
    
    # Stop all patches
    for patch_obj in patches:
        patch_obj.stop()


@pytest.fixture
def mock_production_environment(environment_mocker):
    """Fixture for production environment testing."""
    patches = environment_mocker.mock_environment_scenario('production')
    
    active_patches = []
    for patch_obj in patches:
        active_patches.append(patch_obj.start())
    
    yield
    
    for patch_obj in patches:
        patch_obj.stop()


@pytest.fixture
def mock_kubernetes_environment(environment_mocker):
    """Fixture for kubernetes environment testing."""
    patches = environment_mocker.mock_environment_scenario('kubernetes')
    
    active_patches = []
    for patch_obj in patches:
        active_patches.append(patch_obj.start())
    
    yield
    
    for patch_obj in patches:
        patch_obj.stop()


@pytest.fixture
def mock_testing_environment(environment_mocker):
    """Fixture for testing environment detection."""
    patches = environment_mocker.mock_environment_scenario('testing')
    
    active_patches = []
    for patch_obj in patches:
        active_patches.append(patch_obj.start())
    
    yield
    
    for patch_obj in patches:
        patch_obj.stop()