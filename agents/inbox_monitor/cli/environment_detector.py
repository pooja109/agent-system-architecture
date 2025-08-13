# cli/environment_detector.py
import os
import sys
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import platform
import threading
import time


class EnvironmentType(str, Enum):
    """Types of deployment environments."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    CONTAINERIZED = "containerized"
    KUBERNETES = "kubernetes"


class ContainerType(str, Enum):
    """Types of containerized environments."""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    PODMAN = "podman"
    UNKNOWN_CONTAINER = "unknown_container"


class EnvironmentDetector:
    """Intelligent environment detection with caching and validation."""
    
    _detection_cache: Optional[Dict[str, Any]] = None
    _cache_timestamp: Optional[float] = None
    _cache_ttl: float = 300.0  # 5 minutes cache TTL
    _lock = threading.Lock()
    
    def __init__(self):
        self.platform_info = self._get_platform_info()
    
    def detect_environment(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Detect the current deployment environment with caching."""
        with self._lock:
            # Check cache validity
            if (not force_refresh and 
                self._detection_cache is not None and 
                self._cache_timestamp is not None and
                time.time() - self._cache_timestamp < self._cache_ttl):
                return self._detection_cache.copy()
            
            # Perform fresh detection
            detection_result = self._perform_detection()
            
            # Update cache
            self._detection_cache = detection_result
            self._cache_timestamp = time.time()
            
            return detection_result.copy()
    
    def _perform_detection(self) -> Dict[str, Any]:
        """Perform comprehensive environment detection."""
        result = {
            'environment_type': self._detect_environment_type(),
            'container_info': self._detect_container_environment(),
            'platform_info': self.platform_info,
            'runtime_info': self._get_runtime_info(),
            'ci_cd_info': self._detect_ci_cd_environment(),
            'cloud_info': self._detect_cloud_environment(),
            'is_containerized': self._is_containerized(),
            'is_kubernetes': self._is_kubernetes(),
            'is_production': self._is_production_environment(),
            'detection_confidence': self._calculate_confidence(),
            'detection_timestamp': time.time()
        }
        
        return result
    
    def _detect_environment_type(self) -> EnvironmentType:
        """Determine the primary environment type."""
        # Check for explicit environment specification
        env_type = os.getenv('ENVIRONMENT', '').lower()
        if env_type in [e.value for e in EnvironmentType]:
            return EnvironmentType(env_type)
        
        # Check for Kubernetes
        if self._is_kubernetes():
            return EnvironmentType.KUBERNETES
        
        # Check for containerized environment
        if self._is_containerized():
            return EnvironmentType.CONTAINERIZED
        
        # Check for production indicators
        if self._is_production_environment():
            return EnvironmentType.PRODUCTION
        
        # Check for testing environment
        if self._is_testing_environment():
            return EnvironmentType.TESTING
        
        # Default to development
        return EnvironmentType.DEVELOPMENT
    
    def _detect_container_environment(self) -> Dict[str, Any]:
        """Detect container-specific information."""
        container_info = {
            'type': None,
            'runtime': None,
            'image_info': {},
            'orchestrator': None
        }
        
        if not self._is_containerized():
            return container_info
        
        # Detect container type
        if self._is_kubernetes():
            container_info['type'] = ContainerType.KUBERNETES
            container_info['orchestrator'] = 'kubernetes'
            container_info['runtime'] = os.getenv('CONTAINER_RUNTIME', 'unknown')
        elif os.path.exists('/.dockerenv'):
            container_info['type'] = ContainerType.DOCKER
            container_info['runtime'] = 'docker'
        elif os.getenv('PODMAN_SYSTEMD_UNIT'):
            container_info['type'] = ContainerType.PODMAN
            container_info['runtime'] = 'podman'
        else:
            container_info['type'] = ContainerType.UNKNOWN_CONTAINER
        
        # Collect container image information
        container_info['image_info'] = {
            'name': os.getenv('CONTAINER_IMAGE', 'unknown'),
            'tag': os.getenv('CONTAINER_TAG', 'unknown'),
            'id': os.getenv('CONTAINER_ID', 'unknown')
        }
        
        return container_info
    
    def _is_containerized(self) -> bool:
        """Check if running in a containerized environment."""
        return any([
            os.path.exists('/.dockerenv'),
            os.path.exists('/run/.containerenv'),
            os.getenv('KUBERNETES_SERVICE_HOST'),
            os.getenv('DOCKER_CONTAINER'),
            os.getenv('CONTAINER_NAME'),
            self._check_cgroup_container_indicators()
        ])
    
    def _is_kubernetes(self) -> bool:
        """Check if running in Kubernetes."""
        return any([
            os.getenv('KUBERNETES_SERVICE_HOST'),
            os.getenv('KUBERNETES_PORT'),
            os.path.exists('/var/run/secrets/kubernetes.io'),
            os.getenv('KUBE_POD_NAME')
        ])
    
    def _is_production_environment(self) -> bool:
        """Detect production environment indicators."""
        production_indicators = [
            os.getenv('ENVIRONMENT', '').lower() == 'production',
            os.getenv('NODE_ENV', '').lower() == 'production',
            os.getenv('FLASK_ENV', '').lower() == 'production',
            os.getenv('PYTHON_ENV', '').lower() == 'production',
            os.getenv('DEPLOYMENT_STAGE', '').lower() == 'production',
            # Cloud platform indicators
            bool(os.getenv('AWS_EXECUTION_ENV')),
            bool(os.getenv('GOOGLE_CLOUD_PROJECT')),
            bool(os.getenv('AZURE_FUNCTIONS_ENVIRONMENT')),
            # Production domain patterns
            self._check_production_domain_patterns()
        ]
        
        return any(production_indicators)
    
    def _is_testing_environment(self) -> bool:
        """Detect testing environment indicators."""
        testing_indicators = [
            'pytest' in sys.modules,
            'unittest' in sys.modules,
            os.getenv('ENVIRONMENT', '').lower() in ['test', 'testing'],
            os.getenv('NODE_ENV', '').lower() == 'test',
            os.getenv('PYTEST_CURRENT_TEST') is not None,
            'test' in sys.argv[0].lower(),
            any('test' in arg.lower() for arg in sys.argv)
        ]
        
        return any(testing_indicators)
    
    def _check_cgroup_container_indicators(self) -> bool:
        """Check cgroup indicators for containerization."""
        try:
            cgroup_paths = ['/proc/1/cgroup', '/proc/self/cgroup']
            
            for path in cgroup_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        content = f.read()
                        if any(indicator in content.lower() for indicator in 
                               ['docker', 'containerd', 'kubepods', 'lxc']):
                            return True
            return False
        except Exception:
            return False
    
    def _check_production_domain_patterns(self) -> bool:
        """Check for production domain patterns in environment."""
        hostname = platform.node().lower()
        domain_indicators = ['prod', 'production', 'live', 'staging']
        
        return any(indicator in hostname for indicator in domain_indicators)
    
    def _detect_ci_cd_environment(self) -> Dict[str, Any]:
        """Detect CI/CD environment information."""
        ci_systems = {
            'github_actions': bool(os.getenv('GITHUB_ACTIONS')),
            'azure_devops': bool(os.getenv('AZURE_HTTP_USER_AGENT')),
            'jenkins': bool(os.getenv('JENKINS_URL')),
            'gitlab_ci': bool(os.getenv('GITLAB_CI')),
            'travis_ci': bool(os.getenv('TRAVIS')),
            'circleci': bool(os.getenv('CIRCLECI')),
        }
        
        return {
            'detected_systems': [k for k, v in ci_systems.items() if v],
            'is_ci_environment': any(ci_systems.values()),
            'build_info': {
                'build_id': os.getenv('BUILD_ID') or os.getenv('GITHUB_RUN_ID'),
                'build_number': os.getenv('BUILD_NUMBER') or os.getenv('GITHUB_RUN_NUMBER'),
                'commit_sha': os.getenv('GIT_COMMIT') or os.getenv('GITHUB_SHA')
            }
        }
    
    def _detect_cloud_environment(self) -> Dict[str, Any]:
        """Detect cloud platform information."""
        cloud_platforms = {
            'aws': {
                'detected': bool(os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION')),
                'region': os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION'),
                'execution_env': os.getenv('AWS_EXECUTION_ENV')
            },
            'azure': {
                'detected': bool(os.getenv('AZURE_CLIENT_ID') or os.getenv('WEBSITE_SITE_NAME')),
                'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID'),
                'resource_group': os.getenv('AZURE_RESOURCE_GROUP')
            },
            'gcp': {
                'detected': bool(os.getenv('GOOGLE_CLOUD_PROJECT')),
                'project': os.getenv('GOOGLE_CLOUD_PROJECT'),
                'region': os.getenv('GOOGLE_CLOUD_REGION')
            }
        }
        
        detected_platforms = [k for k, v in cloud_platforms.items() if v['detected']]
        
        return {
            'platforms': cloud_platforms,
            'detected_platforms': detected_platforms,
            'is_cloud_environment': len(detected_platforms) > 0,
            'primary_platform': detected_platforms[0] if detected_platforms else None
        }
    
    def _get_platform_info(self) -> Dict[str, Any]:
        """Get platform and system information."""
        return {
            'system': platform.system(),
            'platform': platform.platform(),
            'architecture': platform.architecture(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'python_implementation': platform.python_implementation()
        }
    
    def _get_runtime_info(self) -> Dict[str, Any]:
        """Get runtime information."""
        return {
            'python_executable': sys.executable,
            'python_path': sys.path[:3],  # First 3 entries only
            'working_directory': os.getcwd(),
            'process_id': os.getpid(),
            'parent_process_id': os.getppid(),
            'user_id': os.getuid() if hasattr(os, 'getuid') else None,
            'group_id': os.getgid() if hasattr(os, 'getgid') else None
        }
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence level in environment detection."""
        # This is a simplified confidence calculation
        # In practice, you might weight different indicators
        confidence_factors = []
        
        # Environment variable confidence
        if os.getenv('ENVIRONMENT'):
            confidence_factors.append(0.9)
        
        # Container detection confidence
        if self._is_containerized():
            confidence_factors.append(0.8)
        
        # Cloud platform confidence
        cloud_info = self._detect_cloud_environment()
        if cloud_info['is_cloud_environment']:
            confidence_factors.append(0.7)
        
        # Default confidence if no strong indicators
        if not confidence_factors:
            confidence_factors.append(0.5)
        
        return max(confidence_factors)
    
    def get_recommended_logging_config(self, 
                                     environment_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get recommended logging configuration based on environment."""
        if environment_info is None:
            environment_info = self.detect_environment()
        
        env_type = environment_info['environment_type']
        is_containerized = environment_info['is_containerized']
        
        # Base configuration
        config = {
            'console_enabled': True,
            'structured_enabled': True,
            'suppress_azure_sdk': True,
            'suppress_urllib3': True,
            'disable_http_logging': True
        }
        
        # Environment-specific adjustments
        if env_type == EnvironmentType.PRODUCTION or is_containerized:
            config.update({
                'console_enabled': False,  # Only structured logging in production
                'structured_enabled': True,
                'console_level': 'WARNING',
                'structured_level': 'INFO',
                'include_timestamp': True,
                'include_logger_name': True,
                'include_thread_info': True
            })
        
        elif env_type == EnvironmentType.DEVELOPMENT:
            config.update({
                'console_enabled': True,
                'structured_enabled': True,
                'console_level': 'INFO',
                'structured_level': 'DEBUG',
                'color_enabled': True,
                'include_timestamp': False
            })
        
        elif env_type == EnvironmentType.TESTING:
            config.update({
                'console_enabled': True,
                'structured_enabled': False,  # Reduce noise in tests
                'console_level': 'WARNING',
                'color_enabled': False,
                'include_timestamp': False
            })
        
        return config


# Convenience functions
def detect_current_environment() -> Dict[str, Any]:
    """Detect the current environment with caching."""
    detector = EnvironmentDetector()
    return detector.detect_environment()


def get_environment_type() -> EnvironmentType:
    """Get just the environment type."""
    detector = EnvironmentDetector()
    env_info = detector.detect_environment()
    return env_info['environment_type']


def is_production() -> bool:
    """Quick check if running in production."""
    detector = EnvironmentDetector()
    env_info = detector.detect_environment()
    return env_info['is_production']


def is_containerized() -> bool:
    """Quick check if running in a container."""
    detector = EnvironmentDetector()
    env_info = detector.detect_environment()
    return env_info['is_containerized']