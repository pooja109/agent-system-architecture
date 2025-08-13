# tests/cli/test_environment_detector.py
import pytest
import os
import sys
import platform
from unittest.mock import patch, mock_open, MagicMock
import threading
import time

from cli.environment_detector import (
    EnvironmentDetector, EnvironmentType, ContainerType,
    detect_current_environment, get_environment_type,
    is_production, is_containerized
)


class TestEnvironmentDetector:
    """Test suite for environment detection."""
    
    @pytest.fixture
    def detector(self):
        """Create environment detector for testing."""
        return EnvironmentDetector()
    
    def test_detector_initialization(self, detector):
        """Test detector initializes correctly."""
        assert detector is not None
        assert detector.platform_info is not None
        assert 'system' in detector.platform_info
        assert 'python_version' in detector.platform_info
    
    def test_environment_detection_caching(self, detector):
        """Test that environment detection results are cached."""
        # First call
        result1 = detector.detect_environment()
        timestamp1 = result1['detection_timestamp']
        
        # Second call (should use cache)
        result2 = detector.detect_environment()
        timestamp2 = result2['detection_timestamp']
        
        # Should be same timestamp (cached result)
        assert timestamp1 == timestamp2
        
        # Force refresh should give new timestamp
        time.sleep(0.01)  # Small delay to ensure different timestamp
        result3 = detector.detect_environment(force_refresh=True)
        timestamp3 = result3['detection_timestamp']
        
        assert timestamp3 > timestamp1
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'production'})
    def test_explicit_environment_detection(self, detector):
        """Test explicit environment variable detection."""
        env_info = detector.detect_environment(force_refresh=True)
        assert env_info['environment_type'] == EnvironmentType.PRODUCTION
    
    @patch.dict(os.environ, {'KUBERNETES_SERVICE_HOST': 'kubernetes.default.svc'})
    def test_kubernetes_detection(self, detector):
        """Test Kubernetes environment detection."""
        env_info = detector.detect_environment(force_refresh=True)
        assert env_info['is_kubernetes'] is True
        assert env_info['environment_type'] == EnvironmentType.KUBERNETES
    
    @patch('os.path.exists')
    def test_docker_detection(self, mock_exists, detector):
        """Test Docker environment detection."""
        mock_exists.side_effect = lambda path: path == '/.dockerenv'
        
        env_info = detector.detect_environment(force_refresh=True)
        assert env_info['is_containerized'] is True
        assert env_info['container_info']['type'] == ContainerType.DOCKER
    
    def test_cgroup_container_detection(self, detector):
        """Test cgroup-based container detection."""
        mock_cgroup_content = "1:name=systemd:/docker/abc123"
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_cgroup_content)):
            
            result = detector._check_cgroup_container_indicators()
            assert result is True
    
    def test_production_environment_indicators(self, detector):
        """Test various production environment indicators."""
        production_env_vars = [
            {'ENVIRONMENT': 'production'},
            {'NODE_ENV': 'production'},
            {'AWS_EXECUTION_ENV': 'AWS_Lambda_python3.9'},
            {'GOOGLE_CLOUD_PROJECT': 'my-production-project'}
        ]
        
        for env_vars in production_env_vars:
            with patch.dict(os.environ, env_vars, clear=True):
                env_info = detector.detect_environment(force_refresh=True)
                assert env_info['is_production'] is True
    
    def test_testing_environment_detection(self, detector):
        """Test testing environment detection."""
        # Mock pytest being in sys.modules
        original_modules = sys.modules.copy()
        sys.modules['pytest'] = MagicMock()
        
        try:
            env_info = detector.detect_environment(force_refresh=True)
            assert env_info['environment_type'] == EnvironmentType.TESTING
        finally:
            sys.modules = original_modules
    
    def test_ci_cd_environment_detection(self, detector):
        """Test CI/CD environment detection."""
        ci_environments = [
            {'GITHUB_ACTIONS': 'true'},
            {'JENKINS_URL': 'http://jenkins.example.com'},
            {'GITLAB_CI': 'true'},
            {'CIRCLECI': 'true'}
        ]
        
        for env_vars in ci_environments:
            with patch.dict(os.environ, env_vars, clear=True):
                env_info = detector.detect_environment(force_refresh=True)
                ci_info = env_info['ci_cd_info']
                assert ci_info['is_ci_environment'] is True
                assert len(ci_info['detected_systems']) > 0
    
    def test_cloud_platform_detection(self, detector):
        """Test cloud platform detection."""
        cloud_environments = [
            ({'AWS_REGION': 'us-east-1'}, 'aws'),
            ({'AZURE_CLIENT_ID': 'abc123'}, 'azure'),
            ({'GOOGLE_CLOUD_PROJECT': 'my-project'}, 'gcp')
        ]
        
        for env_vars, expected_platform in cloud_environments:
            with patch.dict(os.environ, env_vars, clear=True):
                env_info = detector.detect_environment(force_refresh=True)
                cloud_info = env_info['cloud_info']
                assert cloud_info['is_cloud_environment'] is True
                assert expected_platform in cloud_info['detected_platforms']
    
    def test_platform_info_collection(self, detector):
        """Test platform information collection."""
        platform_info = detector.platform_info
        
        required_keys = [
            'system', 'platform', 'architecture', 'machine',
            'python_version', 'python_implementation'
        ]
        
        for key in required_keys:
            assert key in platform_info
            assert platform_info[key] is not None
    
    def test_runtime_info_collection(self, detector):
        """Test runtime information collection."""
        runtime_info = detector._get_runtime_info()
        
        required_keys = [
            'python_executable', 'python_path', 'working_directory',
            'process_id', 'parent_process_id'
        ]
        
        for key in required_keys:
            assert key in runtime_info
    
    def test_confidence_calculation(self, detector):
        """Test detection confidence calculation."""
        env_info = detector.detect_environment(force_refresh=True)
        confidence = env_info['detection_confidence']
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
    
    def test_recommended_logging_config(self, detector):
        """Test recommended logging configuration."""
        # Test development environment
        with patch.dict(os.environ, {}, clear=True):
            config = detector.get_recommended_logging_config()
            assert config['console_enabled'] is True
            assert config['structured_enabled'] is True
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'production'})
    def test_production_logging_config(self, detector):
        """Test production environment logging configuration."""
        config = detector.get_recommended_logging_config()
        # Production should disable console logging by default
        assert config['console_enabled'] is False
        assert config['structured_enabled'] is True
    
    def test_container_environment_info(self, detector):
        """Test container environment information collection."""
        with patch('os.path.exists', return_value=True), \
             patch.dict(os.environ, {'CONTAINER_IMAGE': 'myapp:latest'}):
            
            container_info = detector._detect_container_environment()
            assert container_info['type'] == ContainerType.DOCKER
            assert container_info['image_info']['name'] == 'myapp:latest'
    
    def test_production_domain_patterns(self, detector):
        """Test production domain pattern detection."""
        with patch('platform.node', return_value='prod-server-01.example.com'):
            result = detector._check_production_domain_patterns()
            assert result is True
        
        with patch('platform.node', return_value='dev-machine.local'):
            result = detector._check_production_domain_patterns()
            assert result is False
    
    def test_thread_safety(self, detector):
        """Test that environment detection is thread-safe."""
        results = []
        
        def detect_in_thread():
            result = detector.detect_environment()
            results.append(result['detection_timestamp'])
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=detect_in_thread)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All threads should get the same cached result
        assert len(set(results)) == 1
    
    def test_cache_ttl_expiration(self, detector):
        """Test cache TTL expiration."""
        # Set a very short TTL for testing
        original_ttl = detector._cache_ttl
        detector._cache_ttl = 0.1  # 100ms
        
        try:
            # First detection
            result1 = detector.detect_environment(force_refresh=True)
            timestamp1 = result1['detection_timestamp']
            
            # Wait for cache to expire
            time.sleep(0.2)
            
            # Second detection should refresh cache
            result2 = detector.detect_environment()
            timestamp2 = result2['detection_timestamp']
            
            assert timestamp2 > timestamp1
        finally:
            detector._cache_ttl = original_ttl


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_detect_current_environment(self):
        """Test detect_current_environment function."""
        result = detect_current_environment()
        assert isinstance(result, dict)
        assert 'environment_type' in result
        assert 'is_containerized' in result
        assert 'detection_timestamp' in result
    
    def test_get_environment_type(self):
        """Test get_environment_type function."""
        env_type = get_environment_type()
        assert isinstance(env_type, EnvironmentType)
    
    def test_is_production_function(self):
        """Test is_production function."""
        result = is_production()
        assert isinstance(result, bool)
    
    def test_is_containerized_function(self):
        """Test is_containerized function."""
        result = is_containerized()
        assert isinstance(result, bool)


@pytest.mark.parametrize("env_var,env_value,expected_type", [
    ('ENVIRONMENT', 'development', EnvironmentType.DEVELOPMENT),
    ('ENVIRONMENT', 'production', EnvironmentType.PRODUCTION),
    ('ENVIRONMENT', 'testing', EnvironmentType.TESTING),
])
def test_environment_variable_mapping(env_var, env_value, expected_type):
    """Test environment variable to environment type mapping."""
    with patch.dict(os.environ, {env_var: env_value}):
        detector = EnvironmentDetector()
        env_info = detector.detect_environment(force_refresh=True)
        assert env_info['environment_type'] == expected_type


@pytest.mark.parametrize("container_indicator", [
    '/.dockerenv',
    '/run/.containerenv'
])
def test_container_file_indicators(container_indicator):
    """Test container file indicators."""
    with patch('os.path.exists', side_effect=lambda path: path == container_indicator):
        detector = EnvironmentDetector()
        env_info = detector.detect_environment(force_refresh=True)
        assert env_info['is_containerized'] is True


@pytest.mark.parametrize("cgroup_content,should_detect", [
    ("1:name=systemd:/docker/abc123", True),
    ("1:name=systemd:/kubepods/pod123", True),
    ("1:name=systemd:/init.scope", False),
    ("", False)
])
def test_cgroup_detection_patterns(cgroup_content, should_detect):
    """Test cgroup detection patterns."""
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=cgroup_content)):
        
        detector = EnvironmentDetector()
        result = detector._check_cgroup_container_indicators()
        assert result == should_detect