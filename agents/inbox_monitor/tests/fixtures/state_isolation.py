"""
Global state isolation fixtures for preventing test interference.

This module provides fixtures and utilities to isolate global state between tests,
preventing shared mutable global state, singleton conflicts, and module-level variable pollution.
"""
import pytest
import sys
import copy
import importlib
from typing import Dict, Any, Set, Optional, List
from contextlib import contextmanager
from unittest import mock


class GlobalStateManager:
    """Manages global state isolation for test execution."""
    
    def __init__(self):
        self.original_modules: Dict[str, Dict[str, Any]] = {}
        self.original_attributes: Dict[str, Dict[str, Any]] = {}
        self.protected_modules: Set[str] = set()
        self.state_snapshots: Dict[str, Any] = {}
        self.singleton_backups: Dict[str, Any] = {}
        self.module_reloads: Set[str] = set()
    
    def register_module_for_isolation(self, module_name: str):
        """Register a module for state isolation."""
        if module_name in sys.modules:
            try:
                module = sys.modules[module_name]
                # Create deep copy of module variables (excluding built-ins and methods)
                module_vars = {}
                for name, value in vars(module).items():
                    if not name.startswith('__') and not callable(value):
                        try:
                            module_vars[name] = copy.deepcopy(value)
                        except (TypeError, AttributeError):
                            # Some objects can't be deep copied, use reference
                            module_vars[name] = value
                
                self.original_modules[module_name] = module_vars
                self.protected_modules.add(module_name)
            except Exception:
                # Module might not be importable or have issues, skip
                pass
    
    def backup_singleton_instances(self):
        """Backup common singleton instances."""
        singleton_patterns = [
            ('services.azure_ai_foundry_client', 'AzureAIFoundryClient', '_instance'),
            ('services.graph_api_client', 'GraphAPIClient', '_instance'),
            ('services.salesforce_client', 'SalesforceClient', '_instance'),
            ('utils.custom_logging.logger_factory', 'LoggerFactory', '_instance'),
            ('services.monitor', 'InboxMonitor', '_instance')
        ]
        
        for module_name, class_name, instance_attr in singleton_patterns:
            try:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        if hasattr(cls, instance_attr):
                            instance = getattr(cls, instance_attr)
                            if instance is not None:
                                key = f"{module_name}.{class_name}.{instance_attr}"
                                self.singleton_backups[key] = instance
                                setattr(cls, instance_attr, None)
            except (AttributeError, ImportError):
                continue
    
    def isolate_global_state(self, module_names: Optional[Set[str]] = None):
        """Create isolated global state for test execution."""
        # First backup singletons
        self.backup_singleton_instances()
        
        if module_names:
            for module_name in module_names:
                self.register_module_for_isolation(module_name)
        
        # Common modules that often have global state issues
        common_modules = [
            'services.monitor',
            'services.salesforce_client', 
            'services.graph_api_client',
            'services.azure_ai_foundry_client',
            'services.email_processor',
            'services.round_robin_service',
            'models.settings',
            'utils.retry',
            'config.settings'
        ]
        
        for module_name in common_modules:
            if module_name in sys.modules:
                self.register_module_for_isolation(module_name)
    
    def restore_global_state(self):
        """Restore original global state."""
        # Restore module state
        for module_name in self.protected_modules:
            if module_name in sys.modules:
                try:
                    module = sys.modules[module_name]
                    original_vars = self.original_modules.get(module_name, {})
                    
                    # Clear current module state (non-builtin variables)
                    current_vars = list(vars(module).keys())
                    for var_name in current_vars:
                        if not var_name.startswith('__') and not callable(getattr(module, var_name, None)):
                            try:
                                delattr(module, var_name)
                            except AttributeError:
                                pass
                    
                    # Restore original state
                    for var_name, var_value in original_vars.items():
                        try:
                            setattr(module, var_name, var_value)
                        except (TypeError, AttributeError):
                            pass
                except Exception:
                    # Module restoration failed, skip
                    pass
        
        # Restore singleton instances
        for singleton_key, instance in self.singleton_backups.items():
            try:
                module_name, class_name, instance_attr = singleton_key.rsplit('.', 2)
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        if hasattr(cls, instance_attr):
                            setattr(cls, instance_attr, instance)
            except (ValueError, AttributeError):
                continue
        
        # Clear tracking
        self.original_modules.clear()
        self.original_attributes.clear()
        self.protected_modules.clear()
        self.state_snapshots.clear()
        self.singleton_backups.clear()
        self.module_reloads.clear()
    
    def force_module_reload(self, module_name: str):
        """Force reload a module to clear its state."""
        if module_name in sys.modules:
            try:
                importlib.reload(sys.modules[module_name])
                self.module_reloads.add(module_name)
            except (ImportError, AttributeError):
                pass
    
    def get_isolation_stats(self) -> Dict[str, Any]:
        """Get statistics about current isolation state."""
        return {
            'protected_modules': len(self.protected_modules),
            'singleton_backups': len(self.singleton_backups),
            'module_reloads': len(self.module_reloads),
            'modules': list(self.protected_modules),
            'singletons': list(self.singleton_backups.keys())
        }


@pytest.fixture(scope="function")
def isolated_global_state():
    """Provide isolated global state for each test."""
    manager = GlobalStateManager()
    manager.isolate_global_state()
    
    try:
        yield manager
    finally:
        manager.restore_global_state()


@pytest.fixture(scope="function")
def no_singleton_conflicts():
    """Prevent singleton pattern conflicts in tests."""
    manager = GlobalStateManager()
    manager.backup_singleton_instances()
    
    try:
        yield manager
    finally:
        # Restore singleton instances
        for singleton_key, instance in manager.singleton_backups.items():
            try:
                module_name, class_name, instance_attr = singleton_key.rsplit('.', 2)
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        if hasattr(cls, instance_attr):
                            setattr(cls, instance_attr, instance)
            except (ValueError, AttributeError):
                continue


@pytest.fixture(scope="function")
def isolated_module_state():
    """Provide isolated module state with optional module reloading."""
    manager = GlobalStateManager()
    
    def isolate_modules(*module_names):
        """Isolate specific modules."""
        for module_name in module_names:
            manager.register_module_for_isolation(module_name)
    
    def reload_module(module_name):
        """Reload a module to clear its state."""
        manager.force_module_reload(module_name)
    
    manager.isolate_modules = isolate_modules
    manager.reload_module = reload_module
    
    try:
        yield manager
    finally:
        manager.restore_global_state()


@contextmanager
def temporary_global_state(module_name: str, **kwargs):
    """Temporarily modify global state for a specific module."""
    if module_name not in sys.modules:
        yield
        return
    
    module = sys.modules[module_name]
    original_values = {}
    
    # Backup original values
    for attr_name, new_value in kwargs.items():
        if hasattr(module, attr_name):
            original_values[attr_name] = getattr(module, attr_name)
        setattr(module, attr_name, new_value)
    
    try:
        yield module
    finally:
        # Restore original values
        for attr_name, original_value in original_values.items():
            setattr(module, attr_name, original_value)
        
        # Remove attributes that didn't exist before
        for attr_name in kwargs:
            if attr_name not in original_values:
                try:
                    delattr(module, attr_name)
                except AttributeError:
                    pass


class ConfigurationIsolationManager:
    """Manages configuration isolation between tests."""
    
    def __init__(self):
        self.original_env: Dict[str, str] = {}
        self.temp_env_vars: Set[str] = set()
    
    def isolate_environment(self, **env_vars):
        """Isolate environment variables for test."""
        import os
        
        # Backup original environment
        for key in env_vars:
            if key in os.environ:
                self.original_env[key] = os.environ[key]
            os.environ[key] = str(env_vars[key])
            self.temp_env_vars.add(key)
    
    def restore_environment(self):
        """Restore original environment."""
        import os
        
        # Restore original values
        for key, value in self.original_env.items():
            os.environ[key] = value
        
        # Remove temporary variables
        for key in self.temp_env_vars:
            if key not in self.original_env and key in os.environ:
                del os.environ[key]
        
        self.original_env.clear()
        self.temp_env_vars.clear()


@pytest.fixture(scope="function")
def isolated_config():
    """Provide isolated configuration environment for tests."""
    manager = ConfigurationIsolationManager()
    
    try:
        yield manager
    finally:
        manager.restore_environment()


# Performance validation for state isolation
def validate_isolation_performance(manager: GlobalStateManager) -> Dict[str, Any]:
    """Validate that state isolation doesn't significantly impact performance."""
    stats = manager.get_isolation_stats()
    
    # Isolation should be fast and not consume excessive resources
    assert stats['protected_modules'] < 50, f"Too many protected modules: {stats['protected_modules']}"
    assert stats['singleton_backups'] < 20, f"Too many singleton backups: {stats['singleton_backups']}"
    
    return stats


# Debug utilities
def debug_isolation_state(manager: GlobalStateManager):
    """Debug isolation state for troubleshooting."""
    stats = manager.get_isolation_stats()
    
    print(f"\n🔍 ISOLATION STATE DEBUG:")
    print(f"   Protected modules: {stats['protected_modules']}")
    print(f"   Singleton backups: {stats['singleton_backups']}")
    print(f"   Module reloads: {stats['module_reloads']}")
    
    if stats['modules']:
        print(f"   Modules: {', '.join(stats['modules'][:5])}{'...' if len(stats['modules']) > 5 else ''}")
    
    if stats['singletons']:
        print(f"   Singletons: {', '.join(stats['singletons'][:3])}{'...' if len(stats['singletons']) > 3 else ''}")


# Export commonly used fixtures and utilities
__all__ = [
    'GlobalStateManager', 'ConfigurationIsolationManager',
    'isolated_global_state', 'no_singleton_conflicts', 'isolated_module_state', 'isolated_config',
    'temporary_global_state', 'validate_isolation_performance', 'debug_isolation_state'
]