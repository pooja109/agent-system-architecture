#!/usr/bin/env python3
"""
Test Configuration Management
============================

Centralized configuration management for integration tests.
Eliminates hardcoded values and provides flexible test configuration.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for a service under test."""
    name: str
    url: str
    port: int
    health_endpoint: str = "/health"
    metrics_endpoint: str = "/metrics"
    api_version: str = "v1"
    timeout: int = 30
    retry_count: int = 3
    
    @property
    def health_url(self) -> str:
        return f"{self.url}{self.health_endpoint}"
    
    @property
    def metrics_url(self) -> str:
        return f"{self.url}{self.metrics_endpoint}"


@dataclass
class ContainerConfig:
    """Configuration for container testing."""
    registry: str = "docker.io"
    namespace: str = "email-agents"
    image_tag: str = "latest"
    dockerfile_path: str = "Dockerfile"
    build_context: str = "."
    resource_limits: Dict[str, str] = None
    environment_vars: Dict[str, str] = None
    
    def __post_init__(self):
        if self.resource_limits is None:
            self.resource_limits = {
                "memory": "512Mi",
                "cpu": "500m"
            }
        if self.environment_vars is None:
            self.environment_vars = {
                "LOG_LEVEL": "INFO",
                "ENVIRONMENT": "test"
            }


@dataclass
class KubernetesConfig:
    """Configuration for Kubernetes testing."""
    namespace: str = "email-agents-test"
    cluster_context: str = "default"
    kubeconfig_path: Optional[str] = None
    wait_timeout: int = 300
    manifest_dir: str = "k8s"
    service_account: str = "default"
    
    @property
    def kubectl_args(self) -> List[str]:
        args = ["kubectl"]
        if self.kubeconfig_path:
            args.extend(["--kubeconfig", self.kubeconfig_path])
        if self.cluster_context != "default":
            args.extend(["--context", self.cluster_context])
        return args


@dataclass
class MonitoringConfig:
    """Configuration for monitoring testing."""
    prometheus_url: str = "http://localhost:9090"
    grafana_url: str = "http://localhost:3000"
    alertmanager_url: str = "http://localhost:9093"
    loki_url: str = "http://localhost:3100"
    query_timeout: int = 30
    scrape_interval: str = "15s"
    retention_period: str = "7d"


@dataclass
class SecurityConfig:
    """Configuration for security testing."""
    vulnerability_scanners: List[str] = None
    security_policies: Dict[str, Any] = None
    allowed_registries: List[str] = None
    scan_timeout: int = 300
    
    def __post_init__(self):
        if self.vulnerability_scanners is None:
            self.vulnerability_scanners = ["trivy", "hadolint", "bandit", "semgrep"]
        if self.security_policies is None:
            self.security_policies = {
                "allow_root": False,
                "allow_privilege_escalation": False,
                "require_non_root_user": True,
                "require_read_only_filesystem": False
            }
        if self.allowed_registries is None:
            self.allowed_registries = ["docker.io", "ghcr.io", "mcr.microsoft.com"]


@dataclass
class PerformanceConfig:
    """Configuration for performance testing."""
    duration_seconds: int = 60
    concurrent_users: int = 10
    ramp_up_seconds: int = 10
    think_time_seconds: int = 1
    success_rate_threshold: float = 95.0
    response_time_threshold_ms: int = 2000
    error_rate_threshold: float = 5.0
    tools: List[str] = None
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = ["hey", "ab", "wrk", "curl"]


class TestConfiguration:
    """Central test configuration manager."""
    
    def __init__(self, config_file: Optional[str] = None, environment: str = "test"):
        self.environment = environment
        self.config_file = config_file
        self._config_data = {}
        self._load_configuration()
        
        # Initialize service configurations
        self.services = self._create_service_configs()
        self.container = self._create_container_config()
        self.kubernetes = self._create_kubernetes_config()
        self.monitoring = self._create_monitoring_config()
        self.security = self._create_security_config()
        self.performance = self._create_performance_config()
    
    def _load_configuration(self):
        """Load configuration from file and environment variables."""
        # Default configuration
        default_config = {
            "services": {
                "inbox_monitor": {
                    "name": "inbox-monitor",
                    "host": "localhost",
                    "port": 8080
                },
                "email_agent": {
                    "name": "email-agent", 
                    "host": "localhost",
                    "port": 8081
                }
            },
            "container": {
                "registry": "docker.io",
                "namespace": "email-agents"
            },
            "kubernetes": {
                "namespace": "email-agents-test"
            },
            "monitoring": {
                "prometheus": {
                    "host": "localhost",
                    "port": 9090
                },
                "grafana": {
                    "host": "localhost", 
                    "port": 3000
                }
            },
            "performance": {
                "duration": 60,
                "concurrent_users": 10
            },
            "security": {
                "scanners": ["trivy", "hadolint"]
            }
        }
        
        self._config_data = default_config
        
        # Load from file if specified
        if self.config_file:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    if config_path.suffix.lower() in ['.yaml', '.yml']:
                        file_config = yaml.safe_load(f)
                    else:
                        file_config = json.load(f)
                
                self._merge_config(self._config_data, file_config)
        
        # Override with environment variables
        self._load_env_overrides()
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _load_env_overrides(self):
        """Load configuration overrides from environment variables."""
        env_mappings = {
            # Service configurations
            "INBOX_MONITOR_HOST": ("services", "inbox_monitor", "host"),
            "INBOX_MONITOR_PORT": ("services", "inbox_monitor", "port"),
            "EMAIL_AGENT_HOST": ("services", "email_agent", "host"),
            "EMAIL_AGENT_PORT": ("services", "email_agent", "port"),
            
            # Kubernetes configuration
            "K8S_NAMESPACE": ("kubernetes", "namespace"),
            "K8S_CONTEXT": ("kubernetes", "context"),
            "KUBECONFIG": ("kubernetes", "kubeconfig_path"),
            
            # Monitoring configuration
            "PROMETHEUS_HOST": ("monitoring", "prometheus", "host"),
            "PROMETHEUS_PORT": ("monitoring", "prometheus", "port"),
            "GRAFANA_HOST": ("monitoring", "grafana", "host"),
            "GRAFANA_PORT": ("monitoring", "grafana", "port"),
            
            # Performance configuration
            "PERF_DURATION": ("performance", "duration"),
            "PERF_CONCURRENT_USERS": ("performance", "concurrent_users"),
            
            # Container configuration
            "CONTAINER_REGISTRY": ("container", "registry"),
            "CONTAINER_NAMESPACE": ("container", "namespace"),
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Navigate to the config location
                current = self._config_data
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Convert to appropriate type
                final_key = config_path[-1]
                if final_key in ["port", "duration", "concurrent_users"]:
                    value = int(value)
                elif final_key in ["timeout"]:
                    value = float(value)
                
                current[final_key] = value
    
    def _create_service_configs(self) -> Dict[str, ServiceConfig]:
        """Create service configurations."""
        services = {}
        
        for service_id, service_data in self._config_data.get("services", {}).items():
            host = service_data.get("host", "localhost")
            port = service_data.get("port", 8080)
            url = f"http://{host}:{port}"
            
            services[service_id] = ServiceConfig(
                name=service_data.get("name", service_id),
                url=url,
                port=port,
                health_endpoint=service_data.get("health_endpoint", "/health"),
                metrics_endpoint=service_data.get("metrics_endpoint", "/metrics"),
                timeout=service_data.get("timeout", 30),
                retry_count=service_data.get("retry_count", 3)
            )
        
        return services
    
    def _create_container_config(self) -> ContainerConfig:
        """Create container configuration."""
        container_data = self._config_data.get("container", {})
        
        return ContainerConfig(
            registry=container_data.get("registry", "docker.io"),
            namespace=container_data.get("namespace", "email-agents"),
            image_tag=container_data.get("tag", "latest"),
            dockerfile_path=container_data.get("dockerfile_path", "Dockerfile"),
            build_context=container_data.get("build_context", "."),
            resource_limits=container_data.get("resource_limits"),
            environment_vars=container_data.get("environment_vars")
        )
    
    def _create_kubernetes_config(self) -> KubernetesConfig:
        """Create Kubernetes configuration."""
        k8s_data = self._config_data.get("kubernetes", {})
        
        return KubernetesConfig(
            namespace=k8s_data.get("namespace", f"email-agents-{self.environment}"),
            cluster_context=k8s_data.get("context", "default"),
            kubeconfig_path=k8s_data.get("kubeconfig_path"),
            wait_timeout=k8s_data.get("wait_timeout", 300),
            manifest_dir=k8s_data.get("manifest_dir", "k8s"),
            service_account=k8s_data.get("service_account", "default")
        )
    
    def _create_monitoring_config(self) -> MonitoringConfig:
        """Create monitoring configuration."""
        monitoring_data = self._config_data.get("monitoring", {})
        
        prometheus_config = monitoring_data.get("prometheus", {})
        prometheus_host = prometheus_config.get("host", "localhost")
        prometheus_port = prometheus_config.get("port", 9090)
        
        grafana_config = monitoring_data.get("grafana", {})
        grafana_host = grafana_config.get("host", "localhost")
        grafana_port = grafana_config.get("port", 3000)
        
        alertmanager_config = monitoring_data.get("alertmanager", {})
        alertmanager_host = alertmanager_config.get("host", "localhost")
        alertmanager_port = alertmanager_config.get("port", 9093)
        
        return MonitoringConfig(
            prometheus_url=f"http://{prometheus_host}:{prometheus_port}",
            grafana_url=f"http://{grafana_host}:{grafana_port}",
            alertmanager_url=f"http://{alertmanager_host}:{alertmanager_port}",
            query_timeout=monitoring_data.get("query_timeout", 30),
            scrape_interval=monitoring_data.get("scrape_interval", "15s"),
            retention_period=monitoring_data.get("retention_period", "7d")
        )
    
    def _create_security_config(self) -> SecurityConfig:
        """Create security configuration."""
        security_data = self._config_data.get("security", {})
        
        return SecurityConfig(
            vulnerability_scanners=security_data.get("scanners"),
            security_policies=security_data.get("policies"),
            allowed_registries=security_data.get("allowed_registries"),
            scan_timeout=security_data.get("scan_timeout", 300)
        )
    
    def _create_performance_config(self) -> PerformanceConfig:
        """Create performance configuration."""
        perf_data = self._config_data.get("performance", {})
        
        return PerformanceConfig(
            duration_seconds=perf_data.get("duration", 60),
            concurrent_users=perf_data.get("concurrent_users", 10),
            ramp_up_seconds=perf_data.get("ramp_up", 10),
            success_rate_threshold=perf_data.get("success_rate_threshold", 95.0),
            response_time_threshold_ms=perf_data.get("response_time_threshold", 2000),
            error_rate_threshold=perf_data.get("error_rate_threshold", 5.0),
            tools=perf_data.get("tools")
        )
    
    def get_service_url(self, service_name: str) -> str:
        """Get URL for a service."""
        if service_name in self.services:
            return self.services[service_name].url
        raise ValueError(f"Unknown service: {service_name}")
    
    def get_service_port(self, service_name: str) -> int:
        """Get port for a service."""
        if service_name in self.services:
            return self.services[service_name].port
        raise ValueError(f"Unknown service: {service_name}")
    
    def is_environment(self, env: str) -> bool:
        """Check if running in specific environment."""
        return self.environment.lower() == env.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "environment": self.environment,
            "services": {name: {
                "name": config.name,
                "url": config.url,
                "port": config.port,
                "health_endpoint": config.health_endpoint,
                "metrics_endpoint": config.metrics_endpoint
            } for name, config in self.services.items()},
            "container": {
                "registry": self.container.registry,
                "namespace": self.container.namespace,
                "image_tag": self.container.image_tag
            },
            "kubernetes": {
                "namespace": self.kubernetes.namespace,
                "cluster_context": self.kubernetes.cluster_context
            },
            "monitoring": {
                "prometheus_url": self.monitoring.prometheus_url,
                "grafana_url": self.monitoring.grafana_url,
                "alertmanager_url": self.monitoring.alertmanager_url
            },
            "performance": {
                "duration_seconds": self.performance.duration_seconds,
                "concurrent_users": self.performance.concurrent_users
            },
            "security": {
                "vulnerability_scanners": self.security.vulnerability_scanners
            }
        }


# Global configuration instance
_config_instance: Optional[TestConfiguration] = None


def get_config(config_file: Optional[str] = None, environment: str = None) -> TestConfiguration:
    """Get the global configuration instance."""
    global _config_instance
    
    if _config_instance is None:
        if environment is None:
            environment = os.environ.get("TEST_ENVIRONMENT", "test")
        _config_instance = TestConfiguration(config_file=config_file, environment=environment)
    
    return _config_instance


def reset_config():
    """Reset the global configuration instance."""
    global _config_instance
    _config_instance = None


# Convenience functions
def get_service_config(service_name: str) -> ServiceConfig:
    """Get configuration for a specific service."""
    config = get_config()
    if service_name not in config.services:
        raise ValueError(f"Unknown service: {service_name}. Available: {list(config.services.keys())}")
    return config.services[service_name]


def get_inbox_monitor_url() -> str:
    """Get inbox monitor URL."""
    return get_service_config("inbox_monitor").url


def get_email_agent_url() -> str:
    """Get email agent URL."""
    return get_service_config("email_agent").url


def get_monitoring_config() -> MonitoringConfig:
    """Get monitoring configuration."""
    return get_config().monitoring


def get_kubernetes_config() -> KubernetesConfig:
    """Get Kubernetes configuration."""
    return get_config().kubernetes


def get_performance_config() -> PerformanceConfig:
    """Get performance configuration."""
    return get_config().performance


def get_security_config() -> SecurityConfig:
    """Get security configuration."""
    return get_config().security


def get_container_config() -> ContainerConfig:
    """Get container configuration."""
    return get_config().container