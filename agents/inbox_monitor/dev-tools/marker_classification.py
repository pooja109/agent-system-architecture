#!/usr/bin/env python3
"""
Marker Classification Decision Tree for Test Phase X Compliance
==============================================================

This module provides templates and utilities for consistent test marker
classification as required by Phase X prompt (lines 143-192).

Usage:
    from marker_classification import classify_test_markers, MarkerClassifier
    
    markers = classify_test_markers(test_function, test_dependencies, execution_time_seconds)
"""

import ast
import inspect
import re
from typing import Dict, List, Optional, Set, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class PerformanceCategory(Enum):
    """Performance categories for test classification."""
    FAST = "fast"      # < 1 second
    MEDIUM = "medium"  # 1-10 seconds
    SLOW = "slow"      # > 10 seconds


class FunctionalCategory(Enum):
    """Functional categories for test classification (mutually exclusive)."""
    UNIT = "unit"              # Single component, mocked dependencies
    INTEGRATION = "integration"  # Multiple components, service mocks
    E2E = "e2e"               # End-to-end with real services


@dataclass
class TestDependencies:
    """Container for test dependencies analysis."""
    has_mocks: bool = False
    external_services: Set[str] = None
    azure_services: Set[str] = None
    database_dependencies: bool = False
    api_dependencies: Set[str] = None
    
    def __post_init__(self):
        if self.external_services is None:
            self.external_services = set()
        if self.azure_services is None:
            self.azure_services = set()
        if self.api_dependencies is None:
            self.api_dependencies = set()


class MarkerClassifier:
    """
    Template for consistent test marker classification.
    Implements Phase X decision tree logic (lines 143-192 from prompt).
    """
    
    # Known service types and their markers
    AZURE_SERVICES = {
        "graph_api", "azure_ai", "ai_foundry", "key_vault", "azure"
    }
    
    EXTERNAL_SERVICES = {
        "salesforce", "databricks", "email", "database"
    }
    
    RETRY_INDICATORS = {
        "retry", "backoff", "timeout", "delay"
    }
    
    EDGE_CASE_INDICATORS = {
        "edge", "boundary", "invalid", "error", "exception", "failure"
    }

    def classify_test_markers(
        self, 
        test_function: Union[callable, str], 
        test_dependencies: Optional[TestDependencies] = None,
        execution_time_seconds: float = 0.5
    ) -> List[str]:
        """
        Template for consistent test marker classification.
        Use this logic to determine appropriate markers for any test.
        
        Args:
            test_function: Test function or function name
            test_dependencies: Dependencies analysis
            execution_time_seconds: Expected execution time
            
        Returns:
            List of appropriate markers
        """
        markers = []
        
        # Get function name for analysis
        func_name = test_function.__name__ if callable(test_function) else str(test_function)
        func_name_lower = func_name.lower()
        
        # Default dependencies if not provided
        if test_dependencies is None:
            test_dependencies = self._analyze_function_dependencies(test_function)
        
        # 1. Performance Classification (required - exactly one)
        performance_marker = self._classify_performance(func_name_lower, execution_time_seconds)
        markers.append(performance_marker)
        
        # 2. Functional Classification (required - exactly one)
        functional_marker = self._classify_functional(test_dependencies, func_name_lower)
        markers.append(functional_marker)
        
        # 3. Service Dependency Classification (as needed)
        service_markers = self._classify_service_dependencies(test_dependencies)
        markers.extend(service_markers)
        
        # 4. Special Category Classification (as appropriate)
        special_markers = self._classify_special_categories(func_name_lower, test_dependencies)
        markers.extend(special_markers)
        
        return list(set(markers))  # Remove duplicates
    
    def _classify_performance(self, func_name: str, execution_time: float) -> str:
        """Classify performance marker based on function name and execution time."""
        
        # Special case: retry tests are never fast due to built-in delays
        if any(indicator in func_name for indicator in self.RETRY_INDICATORS):
            return PerformanceCategory.MEDIUM.value
        
        # Standard performance classification
        if execution_time < 1.0:
            return PerformanceCategory.FAST.value
        elif execution_time < 10.0:
            return PerformanceCategory.MEDIUM.value
        else:
            return PerformanceCategory.SLOW.value
    
    def _classify_functional(self, dependencies: TestDependencies, func_name: str = "") -> str:
        """Classify functional marker (unit/integration/e2e)."""
        
        # Special case: detect from function name for string-based analysis
        if func_name:
            func_name_lower = func_name.lower()
            if "integration" in func_name_lower:
                return FunctionalCategory.INTEGRATION.value
            if "e2e" in func_name_lower or "end_to_end" in func_name_lower:
                return FunctionalCategory.E2E.value
        
        # E2E: Real external services without mocks
        if (dependencies.external_services or dependencies.database_dependencies) and not dependencies.has_mocks:
            return FunctionalCategory.E2E.value
        
        # Integration: Multiple services or service mocks
        if (dependencies.external_services or dependencies.azure_services or 
            dependencies.api_dependencies) and dependencies.has_mocks:
            return FunctionalCategory.INTEGRATION.value
        
        # Unit: Single component with mocks or no external dependencies
        return FunctionalCategory.UNIT.value
    
    def _classify_service_dependencies(self, dependencies: TestDependencies) -> List[str]:
        """Classify service dependency markers."""
        markers = []
        
        # Azure services
        if dependencies.azure_services:
            markers.append("azure")
        
        # Database dependencies
        if dependencies.database_dependencies:
            markers.append("database")
        
        # Specific service markers
        for service in dependencies.external_services:
            if service in self.EXTERNAL_SERVICES:
                markers.append(service)
        
        # Email-related tests
        if any("email" in service for service in dependencies.external_services):
            markers.append("email")
            
        return markers
    
    def _classify_special_categories(self, func_name: str, dependencies: TestDependencies) -> List[str]:
        """Classify special category markers."""
        markers = []
        
        # Retry tests
        if any(indicator in func_name for indicator in self.RETRY_INDICATORS):
            markers.append("retry")
        
        # Edge case tests
        if any(indicator in func_name for indicator in self.EDGE_CASE_INDICATORS):
            markers.append("edge_case")
        
        # Smoke tests (basic functionality validation)
        if "init" in func_name or "basic" in func_name or "smoke" in func_name:
            markers.append("smoke")
        
        # CI-safe tests (suitable for automation)
        if dependencies.has_mocks and not any(dependencies.external_services):
            markers.append("ci_safe")
            
        return markers
    
    def _analyze_function_dependencies(self, test_function: Union[callable, str]) -> TestDependencies:
        """Analyze function dependencies from source code."""
        dependencies = TestDependencies()
        
        if not callable(test_function):
            return dependencies
        
        try:
            # Get source code
            source = inspect.getsource(test_function)
            
            # Look for mock usage
            dependencies.has_mocks = bool(re.search(r'mock|Mock|patch|MagicMock', source, re.IGNORECASE))
            
            # Look for Azure services
            for service in self.AZURE_SERVICES:
                if service in source.lower():
                    dependencies.azure_services.add(service)
            
            # Look for external services
            for service in self.EXTERNAL_SERVICES:
                if service in source.lower():
                    dependencies.external_services.add(service)
            
            # Look for database usage
            dependencies.database_dependencies = bool(
                re.search(r'databricks|sql|query|connection|cursor', source, re.IGNORECASE)
            )
            
        except (OSError, TypeError):
            # Can't analyze source, return defaults
            pass
            
        return dependencies


class MarkerValidator:
    """Validates marker consistency and detects conflicts."""
    
    # Known marker conflicts (first marker conflicts with second)
    MARKER_CONFLICTS = {
        'fast': ['retry', 'slow'],
        'unit': ['azure', 'integration', 'e2e', 'database'],
        'integration': ['unit', 'e2e'],
        'e2e': ['unit', 'integration', 'ci_safe']
    }
    
    # Required marker categories (exactly one from each group)
    REQUIRED_CATEGORIES = {
        'performance': ['fast', 'medium', 'slow'],
        'functional': ['unit', 'integration', 'e2e']
    }
    
    def validate_marker_set(self, markers: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate a set of markers for conflicts and completeness.
        
        Args:
            markers: List of marker names
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for marker conflicts
        conflict_issues = self._check_conflicts(markers)
        issues.extend(conflict_issues)
        
        # Check for required categories
        category_issues = self._check_required_categories(markers)
        issues.extend(category_issues)
        
        return len(issues) == 0, issues
    
    def _check_conflicts(self, markers: List[str]) -> List[str]:
        """Check for marker conflicts."""
        issues = []
        marker_set = set(markers)
        
        for primary, conflicting in self.MARKER_CONFLICTS.items():
            if primary in marker_set:
                for conflict in conflicting:
                    if conflict in marker_set:
                        issues.append(f"Conflict: '{primary}' cannot be used with '{conflict}'")
        
        return issues
    
    def _check_required_categories(self, markers: List[str]) -> List[str]:
        """Check for required marker categories."""
        issues = []
        marker_set = set(markers)
        
        for category, required_markers in self.REQUIRED_CATEGORIES.items():
            matching = [m for m in required_markers if m in marker_set]
            
            if len(matching) == 0:
                issues.append(f"Missing {category} marker: must have one of {required_markers}")
            elif len(matching) > 1:
                issues.append(f"Multiple {category} markers: {matching} (should be exactly one)")
                
        return issues


def classify_test_markers(
    test_function: Union[callable, str], 
    test_dependencies: Optional[TestDependencies] = None,
    execution_time_seconds: float = 0.5
) -> List[str]:
    """
    Convenience function for marker classification.
    
    This is the main entry point for the Phase X marker classification system.
    """
    classifier = MarkerClassifier()
    return classifier.classify_test_markers(test_function, test_dependencies, execution_time_seconds)


def validate_markers(markers: List[str]) -> Tuple[bool, List[str]]:
    """
    Convenience function for marker validation.
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    validator = MarkerValidator()
    return validator.validate_marker_set(markers)


# Template examples as shown in Phase X prompt
def example_unit_test_markers():
    """Example: Unit test with mocked dependencies."""
    dependencies = TestDependencies(
        has_mocks=True,
        external_services=set(),
        azure_services=set()
    )
    return classify_test_markers("test_client_initialization", dependencies, 0.5)


def example_integration_test_markers():
    """Example: Integration test with service mocks."""
    dependencies = TestDependencies(
        has_mocks=True,
        azure_services={"azure_ai"},
        external_services=set()
    )
    return classify_test_markers("test_service_integration", dependencies, 5.0)


def example_retry_test_markers():
    """Example: Retry test (inherently medium due to delays)."""
    dependencies = TestDependencies(
        has_mocks=True,
        external_services=set()
    )
    return classify_test_markers("test_retry_behavior", dependencies, 3.0)


if __name__ == "__main__":
    # Example usage and validation
    print("Phase X Marker Classification Examples:")
    print("=" * 50)
    
    print("Unit test markers:", example_unit_test_markers())
    print("Integration test markers:", example_integration_test_markers())  
    print("Retry test markers:", example_retry_test_markers())
    
    # Validation example
    test_markers = ["fast", "unit", "smoke"]
    is_valid, issues = validate_markers(test_markers)
    print(f"\nMarker validation for {test_markers}:")
    print(f"Valid: {is_valid}")
    if issues:
        for issue in issues:
            print(f"Issue: {issue}")