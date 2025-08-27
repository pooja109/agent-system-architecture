"""
Advanced State Management Architecture for sophisticated state isolation and management.

This framework provides comprehensive state management solutions for preventing cross-test
pollution and managing complex state dependencies in test execution.
"""
import pytest
import weakref
import threading
import copy
import sys
import os
from typing import Dict, List, Optional, Any, Callable, Set, Type, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections import defaultdict
from unittest import mock
import importlib
import gc


@dataclass
class StateSnapshot:
    """Represents a snapshot of system state at a point in time."""
    global_vars: Dict[str, Any]
    module_states: Dict[str, Dict[str, Any]]
    mock_states: Dict[str, Any]
    singleton_instances: Dict[str, Any]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateDependency:
    """Represents a state dependency between tests or components."""
    source: str
    target: str
    dependency_type: str  # 'global', 'module', 'singleton', 'mock'
    description: str
    critical: bool = False


class StateTracker:
    """Tracks state changes and dependencies across test execution."""
    
    def __init__(self):
        self.state_history: List[StateSnapshot] = []
        self.dependencies: List[StateDependency] = []
        self.watched_globals: Set[str] = set()
        self.watched_modules: Set[str] = set()
        self.singleton_registry: Dict[str, weakref.ref] = {}
        self.lock = threading.RLock()
    
    def register_global_watch(self, global_name: str):
        """Register a global variable for state tracking."""
        with self.lock:
            self.watched_globals.add(global_name)
    
    def register_module_watch(self, module_name: str):
        """Register a module for state tracking."""
        with self.lock:
            self.watched_modules.add(module_name)
    
    def register_singleton(self, class_name: str, instance: Any):
        """Register a singleton instance for tracking."""
        with self.lock:
            self.singleton_registry[class_name] = weakref.ref(instance)
    
    def capture_state_snapshot(self, metadata: Dict[str, Any] = None) -> StateSnapshot:
        """Capture current state snapshot."""
        with self.lock:
            import time
            
            # Capture global variables
            global_vars = {}
            for var_name in self.watched_globals:
                if hasattr(sys.modules['__main__'], var_name):
                    global_vars[var_name] = copy.deepcopy(
                        getattr(sys.modules['__main__'], var_name)
                    )
            
            # Capture module states
            module_states = {}
            for module_name in self.watched_modules:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    module_state = {}
                    for attr_name in dir(module):
                        if not attr_name.startswith('_'):
                            try:
                                attr_value = getattr(module, attr_name)
                                if not callable(attr_value):
                                    module_state[attr_name] = copy.deepcopy(attr_value)
                            except Exception:
                                pass  # Skip attributes that can't be copied
                    module_states[module_name] = module_state
            
            # Capture singleton states
            singleton_instances = {}
            for class_name, weak_ref in list(self.singleton_registry.items()):
                instance = weak_ref()
                if instance is not None:
                    try:
                        singleton_instances[class_name] = copy.deepcopy(instance.__dict__)
                    except Exception:
                        singleton_instances[class_name] = {'error': 'Cannot serialize singleton state'}
                else:
                    # Remove dead references
                    del self.singleton_registry[class_name]
            
            # Capture mock states (current mock configurations)
            mock_states = {}
            for module_name in list(sys.modules):
                module = sys.modules[module_name]
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, mock.MagicMock):
                        mock_states[f"{module_name}.{attr_name}"] = {
                            'call_count': attr.call_count,
                            'called': attr.called,
                            'call_args': str(attr.call_args) if attr.call_args else None
                        }
            
            snapshot = StateSnapshot(
                global_vars=global_vars,
                module_states=module_states,
                mock_states=mock_states,
                singleton_instances=singleton_instances,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self.state_history.append(snapshot)
            return snapshot
    
    def detect_state_changes(self, before_snapshot: StateSnapshot, 
                           after_snapshot: StateSnapshot) -> Dict[str, List[str]]:
        """Detect changes between two state snapshots."""
        changes = {
            'global_vars': [],
            'module_states': [],
            'mock_states': [],
            'singleton_instances': []
        }
        
        # Check global variable changes
        for var_name in set(before_snapshot.global_vars.keys()) | set(after_snapshot.global_vars.keys()):
            before_val = before_snapshot.global_vars.get(var_name, '<missing>')
            after_val = after_snapshot.global_vars.get(var_name, '<missing>')
            if before_val != after_val:
                changes['global_vars'].append(f"{var_name}: {before_val} -> {after_val}")
        
        # Check module state changes
        for module_name in set(before_snapshot.module_states.keys()) | set(after_snapshot.module_states.keys()):
            before_state = before_snapshot.module_states.get(module_name, {})
            after_state = after_snapshot.module_states.get(module_name, {})
            
            for attr_name in set(before_state.keys()) | set(after_state.keys()):
                before_val = before_state.get(attr_name, '<missing>')
                after_val = after_state.get(attr_name, '<missing>')
                if before_val != after_val:
                    changes['module_states'].append(f"{module_name}.{attr_name}: {before_val} -> {after_val}")
        
        # Check mock state changes
        for mock_name in set(before_snapshot.mock_states.keys()) | set(after_snapshot.mock_states.keys()):
            before_mock = before_snapshot.mock_states.get(mock_name, {})
            after_mock = after_snapshot.mock_states.get(mock_name, {})
            if before_mock != after_mock:
                changes['mock_states'].append(f"{mock_name}: {before_mock} -> {after_mock}")
        
        # Check singleton instance changes
        for class_name in set(before_snapshot.singleton_instances.keys()) | set(after_snapshot.singleton_instances.keys()):
            before_singleton = before_snapshot.singleton_instances.get(class_name, {})
            after_singleton = after_snapshot.singleton_instances.get(class_name, {})
            if before_singleton != after_singleton:
                changes['singleton_instances'].append(f"{class_name}: {before_singleton} -> {after_singleton}")
        
        return changes


class StateManagementFramework:
    """
    Advanced state management framework for sophisticated state isolation and management.
    
    This framework provides:
    - Comprehensive state isolation between tests
    - Cross-test pollution prevention
    - State dependency tracking
    - Automatic state restoration
    - Sophisticated state management patterns
    """
    
    def __init__(self):
        self.state_tracker = StateTracker()
        self.isolation_contexts: Dict[str, Any] = {}
        self.restoration_stack: List[StateSnapshot] = []
        self.protected_modules: Set[str] = set()
        self.state_validators: Dict[str, Callable] = {}
        self.pollution_detectors: List[Callable] = []
        
        # Default protected modules
        self.protected_modules.update([
            'services.azure_ai_foundry_client',
            'services.graph_api_client', 
            'services.monitor',
            'models.email',
            'config.settings'
        ])
    
    def register_state_validator(self, name: str, validator: Callable[[StateSnapshot], bool]):
        """Register a state validator function."""
        self.state_validators[name] = validator
    
    def register_pollution_detector(self, detector: Callable[[StateSnapshot, StateSnapshot], List[str]]):
        """Register a pollution detector function."""
        self.pollution_detectors.append(detector)
    
    def add_protected_module(self, module_name: str):
        """Add a module to the protected modules list."""
        self.protected_modules.add(module_name)
        self.state_tracker.register_module_watch(module_name)
    
    @contextmanager
    def isolated_state_context(self, context_name: str = None, 
                              restore_on_exit: bool = True,
                              validate_state: bool = True):
        """
        Context manager for isolated state execution.
        
        Provides complete state isolation with optional restoration and validation.
        """
        context_name = context_name or f"context_{id(self)}"
        
        # Capture initial state
        initial_snapshot = self.state_tracker.capture_state_snapshot({
            'context': context_name,
            'phase': 'enter'
        })
        
        if restore_on_exit:
            self.restoration_stack.append(initial_snapshot)
        
        try:
            # Set up isolated context
            isolated_context = self._create_isolated_context(context_name)
            self.isolation_contexts[context_name] = isolated_context
            
            yield isolated_context
            
        except Exception as e:
            # Capture error state for analysis
            error_snapshot = self.state_tracker.capture_state_snapshot({
                'context': context_name,
                'phase': 'error',
                'error': str(e)
            })
            
            # Detect pollution during error
            changes = self.state_tracker.detect_state_changes(initial_snapshot, error_snapshot)
            if any(changes.values()):
                self._report_state_pollution(context_name, changes, during_error=True)
            
            raise
            
        finally:
            # Capture final state
            final_snapshot = self.state_tracker.capture_state_snapshot({
                'context': context_name,
                'phase': 'exit'
            })
            
            # Validate state if requested
            if validate_state:
                self._validate_state(final_snapshot, context_name)
            
            # Detect and report pollution
            changes = self.state_tracker.detect_state_changes(initial_snapshot, final_snapshot)
            if any(changes.values()):
                self._report_state_pollution(context_name, changes)
            
            # Restore state if requested
            if restore_on_exit and self.restoration_stack:
                restoration_snapshot = self.restoration_stack.pop()
                self._restore_state(restoration_snapshot, context_name)
            
            # Clean up context
            if context_name in self.isolation_contexts:
                del self.isolation_contexts[context_name]
    
    def _create_isolated_context(self, context_name: str) -> Dict[str, Any]:
        """Create an isolated execution context."""
        context = {
            'name': context_name,
            'protected_globals': {},
            'module_backups': {},
            'mock_patches': {},
            'singleton_backups': {}
        }
        
        # Protect global variables
        for global_name in self.state_tracker.watched_globals:
            if hasattr(sys.modules['__main__'], global_name):
                context['protected_globals'][global_name] = copy.deepcopy(
                    getattr(sys.modules['__main__'], global_name)
                )
        
        # Backup protected module states
        for module_name in self.protected_modules:
            if module_name in sys.modules:
                module = sys.modules[module_name]
                module_backup = {}
                for attr_name in dir(module):
                    if not attr_name.startswith('_'):
                        try:
                            attr_value = getattr(module, attr_name)
                            if not callable(attr_value):
                                module_backup[attr_name] = copy.deepcopy(attr_value)
                        except Exception:
                            pass
                context['module_backups'][module_name] = module_backup
        
        return context
    
    def _restore_state(self, snapshot: StateSnapshot, context_name: str):
        """Restore state from a snapshot."""
        try:
            # Restore global variables
            for var_name, var_value in snapshot.global_vars.items():
                if hasattr(sys.modules['__main__'], var_name):
                    setattr(sys.modules['__main__'], var_name, copy.deepcopy(var_value))
            
            # Restore module states
            for module_name, module_state in snapshot.module_states.items():
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    for attr_name, attr_value in module_state.items():
                        if hasattr(module, attr_name):
                            try:
                                setattr(module, attr_name, copy.deepcopy(attr_value))
                            except Exception:
                                pass  # Best effort restoration
            
            # Force garbage collection to clean up any lingering references
            gc.collect()
            
        except Exception as e:
            # State restoration failure is logged but not raised to avoid masking test errors
            print(f"Warning: State restoration failed for context {context_name}: {e}")
    
    def _validate_state(self, snapshot: StateSnapshot, context_name: str):
        """Validate state using registered validators."""
        validation_errors = []
        
        for validator_name, validator_func in self.state_validators.items():
            try:
                if not validator_func(snapshot):
                    validation_errors.append(f"State validation failed: {validator_name}")
            except Exception as e:
                validation_errors.append(f"State validator error ({validator_name}): {e}")
        
        if validation_errors:
            error_msg = f"State validation failures in context {context_name}:\n" + "\n".join(validation_errors)
            raise AssertionError(error_msg)
    
    def _report_state_pollution(self, context_name: str, changes: Dict[str, List[str]], 
                               during_error: bool = False):
        """Report detected state pollution."""
        if not any(changes.values()):
            return
        
        pollution_report = [
            f"State pollution detected in context: {context_name}",
            f"During error: {during_error}"
        ]
        
        for category, change_list in changes.items():
            if change_list:
                pollution_report.append(f"\n{category.upper()}:")
                for change in change_list:
                    pollution_report.append(f"  - {change}")
        
        # Use pollution detectors for additional analysis
        for detector in self.pollution_detectors:
            try:
                additional_issues = detector(
                    self.state_tracker.state_history[-2] if len(self.state_tracker.state_history) >= 2 else None,
                    self.state_tracker.state_history[-1] if self.state_tracker.state_history else None
                )
                if additional_issues:
                    pollution_report.append(f"\nADDITIONAL ISSUES:")
                    for issue in additional_issues:
                        pollution_report.append(f"  - {issue}")
            except Exception:
                pass  # Detector errors don't prevent reporting
        
        pollution_message = "\n".join(pollution_report)
        
        # In test environment, raise assertion error
        # In production, just log the warning
        if 'pytest' in sys.modules:
            pytest.fail(pollution_message)
        else:
            print(f"WARNING: {pollution_message}")
    
    def prevent_cross_test_pollution(self, test_modules: List[str] = None):
        """Set up comprehensive cross-test pollution prevention."""
        if test_modules:
            for module in test_modules:
                self.add_protected_module(module)
        
        # Register common pollution detectors
        self.register_pollution_detector(self._detect_singleton_pollution)
        self.register_pollution_detector(self._detect_mock_pollution)
        self.register_pollution_detector(self._detect_global_pollution)
        
        # Register common state validators
        self.register_state_validator('no_leaked_mocks', self._validate_no_leaked_mocks)
        self.register_state_validator('singleton_consistency', self._validate_singleton_consistency)
    
    def _detect_singleton_pollution(self, before: StateSnapshot, after: StateSnapshot) -> List[str]:
        """Detect singleton instance pollution between tests."""
        if not before or not after:
            return []
        
        issues = []
        for class_name in set(before.singleton_instances.keys()) | set(after.singleton_instances.keys()):
            before_state = before.singleton_instances.get(class_name, {})
            after_state = after.singleton_instances.get(class_name, {})
            
            if before_state != after_state:
                issues.append(f"Singleton pollution detected in {class_name}")
        
        return issues
    
    def _detect_mock_pollution(self, before: StateSnapshot, after: StateSnapshot) -> List[str]:
        """Detect mock pollution between tests."""
        if not before or not after:
            return []
        
        issues = []
        
        # Check for mocks that weren't cleaned up
        new_mocks = set(after.mock_states.keys()) - set(before.mock_states.keys())
        if new_mocks:
            issues.extend([f"Uncleaned mock detected: {mock_name}" for mock_name in new_mocks])
        
        # Check for mock state changes
        for mock_name in set(before.mock_states.keys()) & set(after.mock_states.keys()):
            before_mock = before.mock_states[mock_name]
            after_mock = after.mock_states[mock_name]
            
            # Check if mock was called but not reset
            if (before_mock.get('call_count', 0) != after_mock.get('call_count', 0) and 
                after_mock.get('call_count', 0) > 0):
                issues.append(f"Mock not reset after test: {mock_name}")
        
        return issues
    
    def _detect_global_pollution(self, before: StateSnapshot, after: StateSnapshot) -> List[str]:
        """Detect global variable pollution between tests."""
        if not before or not after:
            return []
        
        issues = []
        for var_name in set(before.global_vars.keys()) | set(after.global_vars.keys()):
            before_val = before.global_vars.get(var_name)
            after_val = after.global_vars.get(var_name)
            
            if before_val != after_val:
                issues.append(f"Global variable pollution: {var_name}")
        
        return issues
    
    def _validate_no_leaked_mocks(self, snapshot: StateSnapshot) -> bool:
        """Validate that no mocks are leaking between tests."""
        # This is a simple check - in practice you might have more sophisticated validation
        return len(snapshot.mock_states) == 0 or all(
            mock_state.get('call_count', 0) == 0 for mock_state in snapshot.mock_states.values()
        )
    
    def _validate_singleton_consistency(self, snapshot: StateSnapshot) -> bool:
        """Validate singleton consistency."""
        # Check that singleton instances are in expected states
        for class_name, instance_state in snapshot.singleton_instances.items():
            if isinstance(instance_state, dict) and 'error' in instance_state:
                return False  # Singleton serialization error indicates problem
        return True


# Integration fixtures for use in tests
@pytest.fixture(scope="function")
def state_management():
    """Provide state management framework for sophisticated state isolation."""
    framework = StateManagementFramework()
    framework.prevent_cross_test_pollution([
        'services.azure_ai_foundry_client',
        'services.graph_api_client',
        'services.monitor',
        'models.email',
        'config.settings'
    ])
    return framework


@pytest.fixture(scope="function")
def isolated_state(state_management):
    """Provide isolated state context for test execution."""
    with state_management.isolated_state_context("test_isolation", restore_on_exit=True, validate_state=True) as context:
        yield context


@contextmanager
def advanced_state_isolation(modules_to_protect: List[str] = None,
                           custom_validators: Dict[str, Callable] = None,
                           pollution_detection: bool = True):
    """
    Context manager for advanced state isolation with custom configuration.
    
    Args:
        modules_to_protect: List of module names to protect from state pollution
        custom_validators: Dict of validator name -> validator function
        pollution_detection: Whether to enable automatic pollution detection
    """
    framework = StateManagementFramework()
    
    # Configure framework
    if modules_to_protect:
        for module in modules_to_protect:
            framework.add_protected_module(module)
    
    if custom_validators:
        for name, validator in custom_validators.items():
            framework.register_state_validator(name, validator)
    
    if pollution_detection:
        framework.prevent_cross_test_pollution()
    
    with framework.isolated_state_context("advanced_isolation") as context:
        yield context


# Utility functions for state management
def detect_state_pollution_between_tests():
    """Decorator to detect state pollution between test methods."""
    def decorator(test_class):
        original_setup = getattr(test_class, 'setUp', None)
        original_teardown = getattr(test_class, 'tearDown', None)
        
        framework = StateManagementFramework()
        framework.prevent_cross_test_pollution()
        
        def setUp(self):
            self._state_snapshot = framework.state_tracker.capture_state_snapshot({
                'test': f"{test_class.__name__}.setUp"
            })
            if original_setup:
                original_setup(self)
        
        def tearDown(self):
            if original_teardown:
                original_teardown(self)
            
            final_snapshot = framework.state_tracker.capture_state_snapshot({
                'test': f"{test_class.__name__}.tearDown"
            })
            
            changes = framework.state_tracker.detect_state_changes(
                self._state_snapshot, final_snapshot
            )
            
            if any(changes.values()):
                framework._report_state_pollution(
                    f"{test_class.__name__}.test_method", changes
                )
        
        test_class.setUp = setUp
        test_class.tearDown = tearDown
        
        return test_class
    
    return decorator