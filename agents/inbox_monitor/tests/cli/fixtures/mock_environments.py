# tests/cli/fixtures/mock_environments.py
"""
Mock Environment Scenarios for Testing
=====================================

This module provides pre-configured mock environment scenarios for testing
environment detection logic across various deployment contexts.
"""

from typing import Dict, Any
from unittest.mock import MagicMock, patch
import os


# Mock environment scenarios
MOCK_ENVIRONMENTS = {
    "development": {
        "description": "Local development environment",
        "env_vars": {
            "ENVIRONMENT": "",
            "NODE_ENV": "",
            "KUBERNETES_SERVICE_HOST": None,
            "DOCKER_CONTAINER": None,
            "AWS_REGION": None,
            "AZURE_CLIENT_ID": None,
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": None
        },
        "file_system": {
            "/.dockerenv": False,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": False,
            "/proc/1/cgroup": "1:name=systemd:/init.scope\n"
        },
        "platform": {
            "system": "Linux",
            "node": "dev-machine",
            "platform": "Linux-5.15.0-dev"
        },
        "expected": {
            "environment_type": "development",
            "is_containerized": False,
            "is_kubernetes": False,
            "is_production": False,
            "detection_confidence": 0.5
        }
    },
    
    "production": {
        "description": "Production environment with cloud indicators",
        "env_vars": {
            "ENVIRONMENT": "production",
            "NODE_ENV": "production",
            "KUBERNETES_SERVICE_HOST": None,
            "DOCKER_CONTAINER": None,
            "AWS_REGION": "us-east-1",
            "AZURE_CLIENT_ID": "12345-67890",
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": None
        },
        "file_system": {
            "/.dockerenv": False,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": False,
            "/proc/1/cgroup": "1:name=systemd:/system.slice\n"
        },
        "platform": {
            "system": "Linux",
            "node": "prod-server-001",
            "platform": "Linux-5.4.0-production"
        },
        "expected": {
            "environment_type": "production",
            "is_containerized": False,
            "is_kubernetes": False,
            "is_production": True,
            "detection_confidence": 0.9
        }
    },
    
    "testing": {
        "description": "Testing environment with pytest indicators",
        "env_vars": {
            "ENVIRONMENT": "test",
            "NODE_ENV": "test",
            "PYTEST_CURRENT_TEST": "tests/test_something.py::test_function",
            "KUBERNETES_SERVICE_HOST": None,
            "DOCKER_CONTAINER": None,
            "AWS_REGION": None,
            "AZURE_CLIENT_ID": None,
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": None
        },
        "file_system": {
            "/.dockerenv": False,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": False,
            "/proc/1/cgroup": "1:name=systemd:/test.scope\n"
        },
        "platform": {
            "system": "Linux",
            "node": "test-runner",
            "platform": "Linux-5.15.0-test"
        },
        "modules": {
            "pytest": True,
            "unittest": True
        },
        "expected": {
            "environment_type": "testing",
            "is_containerized": False,
            "is_kubernetes": False,
            "is_production": False,
            "detection_confidence": 0.8
        }
    },
    
    "docker": {
        "description": "Docker containerized environment",
        "env_vars": {
            "ENVIRONMENT": "",
            "NODE_ENV": "",
            "KUBERNETES_SERVICE_HOST": None,
            "DOCKER_CONTAINER": "container-123",
            "CONTAINER_NAME": "inbox-monitor",
            "AWS_REGION": None,
            "AZURE_CLIENT_ID": None,
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": None
        },
        "file_system": {
            "/.dockerenv": True,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": False,
            "/proc/1/cgroup": "12:pids:/docker/abc123def456\n11:freezer:/docker/abc123def456\n"
        },
        "platform": {
            "system": "Linux",
            "node": "docker-container",
            "platform": "Linux-5.4.0-container"
        },
        "expected": {
            "environment_type": "containerized",
            "is_containerized": True,
            "is_kubernetes": False,
            "is_production": False,
            "detection_confidence": 0.8
        }
    },
    
    "kubernetes": {
        "description": "Kubernetes pod environment",
        "env_vars": {
            "ENVIRONMENT": "",
            "NODE_ENV": "",
            "KUBERNETES_SERVICE_HOST": "10.96.0.1",
            "KUBERNETES_PORT": "443",
            "KUBE_POD_NAME": "inbox-monitor-pod-abc123",
            "CONTAINER_RUNTIME": "containerd",
            "AWS_REGION": None,
            "AZURE_CLIENT_ID": None,
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": None
        },
        "file_system": {
            "/.dockerenv": False,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": True,
            "/proc/1/cgroup": "12:pids:/kubepods/besteffort/pod123/container456\n"
        },
        "platform": {
            "system": "Linux",
            "node": "k8s-worker-node",
            "platform": "Linux-5.4.0-k8s"
        },
        "expected": {
            "environment_type": "kubernetes",
            "is_containerized": True,
            "is_kubernetes": True,
            "is_production": False,
            "detection_confidence": 0.9
        }
    },
    
    "github_actions": {
        "description": "GitHub Actions CI environment",
        "env_vars": {
            "ENVIRONMENT": "",
            "NODE_ENV": "",
            "KUBERNETES_SERVICE_HOST": None,
            "DOCKER_CONTAINER": None,
            "AWS_REGION": None,
            "AZURE_CLIENT_ID": None,
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": "12345",
            "GITHUB_SHA": "abc123def456"
        },
        "file_system": {
            "/.dockerenv": False,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": False,
            "/proc/1/cgroup": "1:name=systemd:/github-runner\n"
        },
        "platform": {
            "system": "Linux",
            "node": "github-runner",
            "platform": "Linux-5.15.0-runner"
        },
        "expected": {
            "environment_type": "testing",
            "is_containerized": False,
            "is_kubernetes": False,
            "is_production": False,
            "detection_confidence": 0.7
        }
    },
    
    "aws_lambda": {
        "description": "AWS Lambda production environment",
        "env_vars": {
            "ENVIRONMENT": "production",
            "NODE_ENV": "production",
            "KUBERNETES_SERVICE_HOST": None,
            "DOCKER_CONTAINER": None,
            "AWS_REGION": "us-east-1",
            "AWS_EXECUTION_ENV": "AWS_Lambda_python3.9",
            "AWS_LAMBDA_FUNCTION_NAME": "inbox-monitor",
            "AZURE_CLIENT_ID": None,
            "GOOGLE_CLOUD_PROJECT": None,
            "JENKINS_URL": None,
            "GITHUB_ACTIONS": None
        },
        "file_system": {
            "/.dockerenv": False,
            "/run/.containerenv": False,
            "/var/run/secrets/kubernetes.io": False,
            "/proc/1/cgroup": "1:name=systemd:/aws-lambda\n"
        },
        "platform": {
            "system": "Linux",
            "node": "lambda-container",
            "platform": "Linux-4.14.0-aws"
        },
        "expected": {
            "environment_type": "production",
            "is_containerized": False,
            "is_kubernetes": False,
            "is_production": True,
            "detection_confidence": 0.9
        }
    }
}


class MockEnvironment:
    """Context manager for mocking environment scenarios."""
    
    def __init__(self, scenario_name: str):
        if scenario_name not in MOCK_ENVIRONMENTS:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        self.scenario = MOCK_ENVIRONMENTS[scenario_name]
        self.patches = []
        self.original_modules = {}
    
    def __enter__(self):
        """Set up the mock environment."""
        scenario = self.scenario
        
        # Mock environment variables
        env_patch = patch.dict(os.environ, scenario["env_vars"], clear=False)
        self.patches.append(env_patch)
        env_patch.start()
        
        # Mock file system
        def mock_path_exists(path):
            return scenario["file_system"].get(path, os.path.exists(path))
        
        exists_patch = patch("os.path.exists", side_effect=mock_path_exists)
        self.patches.append(exists_patch)
        exists_patch.start()
        
        # Mock platform information
        if "platform" in scenario:
            platform_patch = patch("platform.node", return_value=scenario["platform"]["node"])
            self.patches.append(platform_patch)
            platform_patch.start()
            
            system_patch = patch("platform.system", return_value=scenario["platform"]["system"])
            self.patches.append(system_patch)
            system_patch.start()
            
            platform_info_patch = patch("platform.platform", return_value=scenario["platform"]["platform"])
            self.patches.append(platform_info_patch)
            platform_info_patch.start()
        
        # Mock cgroup file reading
        if "/proc/1/cgroup" in scenario["file_system"]:
            cgroup_content = scenario["file_system"]["/proc/1/cgroup"]
            
            def mock_open_cgroup(*args, **kwargs):
                if args[0] in ["/proc/1/cgroup", "/proc/self/cgroup"]:
                    mock_file = MagicMock()
                    mock_file.read.return_value = cgroup_content
                    mock_file.__enter__.return_value = mock_file
                    return mock_file
                return open(*args, **kwargs)
            
            open_patch = patch("builtins.open", side_effect=mock_open_cgroup)
            self.patches.append(open_patch)
            open_patch.start()
        
        # Mock modules (for testing environment)
        if "modules" in scenario:
            import sys
            for module_name, present in scenario["modules"].items():
                if present and module_name not in sys.modules:
                    sys.modules[module_name] = MagicMock()
                    self.original_modules[module_name] = None
                elif not present and module_name in sys.modules:
                    self.original_modules[module_name] = sys.modules[module_name]
                    del sys.modules[module_name]
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up the mock environment."""
        # Restore modules
        import sys
        for module_name, original_module in self.original_modules.items():
            if original_module is None:
                if module_name in sys.modules:
                    del sys.modules[module_name]
            else:
                sys.modules[module_name] = original_module
        
        # Stop all patches in reverse order
        for patch_obj in reversed(self.patches):
            patch_obj.stop()
        
        self.patches.clear()
        self.original_modules.clear()
    
    def get_expected_results(self) -> Dict[str, Any]:
        """Get expected detection results for this scenario."""
        return self.scenario["expected"].copy()


# Convenience functions for common test scenarios
def mock_development_environment():
    """Mock a development environment."""
    return MockEnvironment("development")


def mock_production_environment():
    """Mock a production environment."""
    return MockEnvironment("production")


def mock_testing_environment():
    """Mock a testing environment."""
    return MockEnvironment("testing")


def mock_docker_environment():
    """Mock a Docker containerized environment."""
    return MockEnvironment("docker")


def mock_kubernetes_environment():
    """Mock a Kubernetes environment."""
    return MockEnvironment("kubernetes")


def mock_github_actions_environment():
    """Mock a GitHub Actions CI environment."""
    return MockEnvironment("github_actions")


def mock_aws_lambda_environment():
    """Mock an AWS Lambda environment."""
    return MockEnvironment("aws_lambda")


# Test utility functions
def get_all_scenario_names():
    """Get names of all available mock scenarios."""
    return list(MOCK_ENVIRONMENTS.keys())


def get_scenario_description(scenario_name: str) -> str:
    """Get description of a specific scenario."""
    if scenario_name not in MOCK_ENVIRONMENTS:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    return MOCK_ENVIRONMENTS[scenario_name]["description"]


def validate_scenario_expectations(scenario_name: str, actual_results: Dict[str, Any]) -> Dict[str, Any]:
    """Validate actual detection results against expected results for a scenario."""
    if scenario_name not in MOCK_ENVIRONMENTS:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    
    expected = MOCK_ENVIRONMENTS[scenario_name]["expected"]
    validation_results = {
        "scenario": scenario_name,
        "passed": True,
        "failures": []
    }
    
    for key, expected_value in expected.items():
        if key not in actual_results:
            validation_results["passed"] = False
            validation_results["failures"].append(f"Missing key: {key}")
        elif actual_results[key] != expected_value:
            validation_results["passed"] = False
            validation_results["failures"].append(
                f"Key '{key}': expected {expected_value}, got {actual_results[key]}"
            )
    
    return validation_results