#!/usr/bin/env python3
"""
Comprehensive Marker Validation Testing for Phase X Compliance
==============================================================

This module implements the marker validation testing templates as required 
by Phase X prompt (lines 244-305).

Usage:
    pytest tests/test_marker_validation.py -v
    
    # Run as part of test suite validation
    python -m pytest tests/test_marker_validation.py::TestMarkerValidation::test_no_marker_conflicts
"""

import pytest
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

# Import our marker classification system
import sys
from pathlib import Path

# Add dev-tools to the path for imports (hyphenated folder names need special handling)
dev_tools_path = Path(__file__).parent.parent / "dev-tools"
sys.path.insert(0, str(dev_tools_path))

from marker_classification import MarkerClassifier, MarkerValidator, validate_markers


@dataclass  
class FileAnalysisResult:
    """Results of analyzing a test file for markers."""
    file_path: Path
    test_functions: List[str]
    marker_issues: List[str]
    missing_performance: List[str]
    conflicting_markers: List[str]


class TestMarkerValidation:
    """Template for validating marker consistency across test suite."""
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_no_marker_conflicts(self):
        """Validate no conflicting markers exist across all test files."""
        conflicts = self._find_marker_conflicts()
        assert len(conflicts) == 0, f"Found marker conflicts: {conflicts}"
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.slow
    @pytest.mark.unit
    def test_all_tests_have_performance_markers(self):
        """Ensure all tests have exactly one performance marker."""
        missing_performance = self._find_tests_missing_performance_markers()
        assert len(missing_performance) == 0, f"Tests missing performance markers: {missing_performance}"
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_functional_marker_consistency(self):
        """Ensure tests don't have conflicting functional markers."""
        functional_conflicts = self._find_functional_marker_conflicts()
        assert len(functional_conflicts) == 0, f"Functional marker conflicts: {functional_conflicts}"
    
    @pytest.mark.retry
    @pytest.mark.database
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_retry_tests_not_marked_fast(self):
        """Ensure retry tests are not marked as fast (they involve delays)."""
        retry_fast_conflicts = self._find_retry_fast_conflicts()
        assert len(retry_fast_conflicts) == 0, f"Retry tests incorrectly marked as fast: {retry_fast_conflicts}"
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.medium
    @pytest.mark.integration
    def test_unit_tests_no_service_dependencies(self):
        """Ensure unit tests don't have service dependency markers."""
        unit_service_conflicts = self._find_unit_service_conflicts()
        assert len(unit_service_conflicts) == 0, f"Unit tests with service markers: {unit_service_conflicts}"
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_marker_classification_system(self):
        """Test the marker classification system itself."""
        classifier = MarkerClassifier()
        validator = MarkerValidator()
        
        # Test classification logic
        test_cases = [
            # (function_name, expected_markers_subset)
            ("test_basic_initialization", ["fast", "unit"]),
            ("test_retry_with_backoff", ["medium", "retry"]),
            ("test_azure_integration", ["integration"]),
            ("test_edge_case_invalid_input", ["edge_case"]),
        ]
        
        for func_name, expected_subset in test_cases:
            markers = classifier.classify_test_markers(func_name)
            for expected in expected_subset:
                assert expected in markers, f"Expected {expected} in {markers} for {func_name}"
            
            # Validate no conflicts
            is_valid, issues = validator.validate_marker_set(markers)
            assert is_valid, f"Generated markers {markers} have issues: {issues}"
    
    @pytest.mark.database
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_comprehensive_test_file_analysis(self):
        """Comprehensive analysis of all test files."""
        analysis_results = self._analyze_all_test_files()
        
        total_issues = sum(len(result.marker_issues) for result in analysis_results)
        assert total_issues == 0, f"Found {total_issues} marker issues across test files"
        
        # Report summary
        total_functions = sum(len(result.test_functions) for result in analysis_results)
        print(f"\nMarker validation summary:")
        print(f"  Test files analyzed: {len(analysis_results)}")
        print(f"  Test functions analyzed: {total_functions}")
        print(f"  Marker issues found: {total_issues}")
    
    def _find_marker_conflicts(self) -> List[str]:
        """Find tests with known conflicting marker combinations."""
        conflicts = []
        validator = MarkerValidator()
        
        test_files = list(Path("tests").glob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST to find test functions and their markers
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        markers = self._extract_markers_from_node(node, content)
                        
                        # Validate markers
                        is_valid, issues = validator.validate_marker_set(markers)
                        if not is_valid:
                            for issue in issues:
                                conflicts.append(f"{test_file.name}::{node.name}: {issue}")
                
            except Exception as e:
                conflicts.append(f"Error analyzing {test_file}: {e}")
        
        return conflicts
    
    def _find_tests_missing_performance_markers(self) -> List[str]:
        """Find tests missing performance markers (fast/medium/slow)."""
        missing = []
        performance_markers = {'fast', 'medium', 'slow'}
        
        test_files = list(Path("tests").glob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        markers = self._extract_markers_from_node(node, content)
                        marker_set = set(markers)
                        
                        # Check if any performance marker is present
                        if not marker_set.intersection(performance_markers):
                            missing.append(f"{test_file.name}::{node.name}")
                
            except Exception as e:
                missing.append(f"Error analyzing {test_file}: {e}")
        
        return missing
    
    def _find_functional_marker_conflicts(self) -> List[str]:
        """Find tests with conflicting functional markers."""
        conflicts = []
        functional_markers = {'unit', 'integration', 'e2e'}
        
        test_files = list(Path("tests").glob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        markers = self._extract_markers_from_node(node, content)
                        marker_set = set(markers)
                        
                        # Check for multiple functional markers
                        functional_present = marker_set.intersection(functional_markers)
                        if len(functional_present) > 1:
                            conflicts.append(
                                f"{test_file.name}::{node.name}: multiple functional markers {functional_present}"
                            )
                
            except Exception as e:
                conflicts.append(f"Error analyzing {test_file}: {e}")
        
        return conflicts
    
    def _find_retry_fast_conflicts(self) -> List[str]:
        """Find retry tests incorrectly marked as fast."""
        conflicts = []
        
        test_files = list(Path("tests").glob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        markers = self._extract_markers_from_node(node, content)
                        marker_set = set(markers)
                        
                        # Check for fast + retry conflict
                        if 'fast' in marker_set and 'retry' in marker_set:
                            conflicts.append(f"{test_file.name}::{node.name}")
                
            except Exception as e:
                conflicts.append(f"Error analyzing {test_file}: {e}")
        
        return conflicts
    
    def _find_unit_service_conflicts(self) -> List[str]:
        """Find unit tests with service dependency markers."""
        conflicts = []
        service_markers = {'azure', 'database', 'salesforce', 'databricks'}
        
        test_files = list(Path("tests").glob("test_*.py"))
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        markers = self._extract_markers_from_node(node, content)
                        marker_set = set(markers)
                        
                        # Check for unit + service markers conflict
                        if 'unit' in marker_set:
                            service_present = marker_set.intersection(service_markers)
                            if service_present:
                                conflicts.append(
                                    f"{test_file.name}::{node.name}: unit test with service markers {service_present}"
                                )
                
            except Exception as e:
                conflicts.append(f"Error analyzing {test_file}: {e}")
        
        return conflicts
    
    def _analyze_all_test_files(self) -> List[FileAnalysisResult]:
        """Comprehensive analysis of all test files."""
        results = []
        validator = MarkerValidator()
        
        test_files = list(Path("tests").glob("test_*.py"))
        
        for test_file in test_files:
            analysis = FileAnalysisResult(
                file_path=test_file,
                test_functions=[],
                marker_issues=[],
                missing_performance=[],
                conflicting_markers=[]
            )
            
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        analysis.test_functions.append(node.name)
                        
                        markers = self._extract_markers_from_node(node, content)
                        
                        # Validate markers
                        is_valid, issues = validator.validate_marker_set(markers)
                        if not is_valid:
                            for issue in issues:
                                analysis.marker_issues.append(f"{node.name}: {issue}")
                
            except Exception as e:
                analysis.marker_issues.append(f"Error analyzing file: {e}")
            
            results.append(analysis)
        
        return results
    
    def _extract_markers_from_node(self, node: ast.FunctionDef, content: str) -> List[str]:
        """
        Extract pytest markers from a test function node.
        
        This handles both decorator-style and class-level markers.
        """
        markers = []
        
        # Extract markers from decorators
        for decorator in node.decorator_list:
            marker = self._extract_marker_from_decorator(decorator)
            if marker:
                markers.append(marker)
        
        # If this is a method, check for class-level markers too
        if hasattr(node, 'lineno'):
            class_markers = self._extract_class_level_markers(content, node.lineno)
            markers.extend(class_markers)
        
        return markers
    
    def _extract_marker_from_decorator(self, decorator) -> Optional[str]:
        """Extract marker name from a decorator AST node."""
        try:
            # Handle @pytest.mark.marker_name
            if (hasattr(decorator, 'attr') and decorator.attr == 'mark' and
                hasattr(decorator, 'value') and hasattr(decorator.value, 'attr') and
                decorator.value.attr == 'pytest'):
                return None  # This is @pytest.mark, need the attribute
            
            # Handle @pytest.mark.marker_name()
            if (hasattr(decorator, 'func') and hasattr(decorator.func, 'attr') and
                hasattr(decorator.func, 'value') and hasattr(decorator.func.value, 'attr') and
                decorator.func.value.attr == 'pytest' and decorator.func.attr == 'mark'):
                # This is a call to pytest.mark.something()
                return None  # Need to parse differently
            
            # Try to parse marker name from different AST structures
            if hasattr(decorator, 'attr'):
                return decorator.attr
            elif hasattr(decorator, 'id'):
                return decorator.id
            
        except AttributeError:
            pass
        
        return None
    
    def _extract_class_level_markers(self, content: str, function_line: int) -> List[str]:
        """Extract class-level markers that apply to a test function."""
        lines = content.split('\n')
        markers = []
        
        # Look backwards from the function to find class definition
        for i in range(function_line - 1, -1, -1):
            line = lines[i].strip()
            
            # Stop at class definition
            if line.startswith('class ') and 'Test' in line:
                # Look for markers before this class
                for j in range(i - 1, max(0, i - 10), -1):
                    marker_line = lines[j].strip()
                    if marker_line.startswith('@pytest.mark.'):
                        marker_name = marker_line.replace('@pytest.mark.', '').split('(')[0]
                        markers.append(marker_name)
                    elif marker_line and not marker_line.startswith('@'):
                        break
                break
        
        return markers


class TestMarkerClassificationSystem:
    """Test the marker classification system components."""
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.slow
    @pytest.mark.unit
    def test_performance_classification(self):
        """Test performance marker classification logic."""
        classifier = MarkerClassifier()
        
        # Fast tests
        assert classifier._classify_performance("test_basic", 0.5) == "fast"
        assert classifier._classify_performance("test_simple", 0.9) == "fast"
        
        # Medium tests
        assert classifier._classify_performance("test_complex", 5.0) == "medium"
        assert classifier._classify_performance("test_retry_logic", 1.0) == "medium"  # retry = medium
        
        # Slow tests
        assert classifier._classify_performance("test_e2e", 15.0) == "slow"
        
        # Special case: retry tests are always at least medium
        assert classifier._classify_performance("test_retry_operation", 0.1) == "medium"
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_functional_classification(self):
        """Test functional marker classification logic."""
        classifier = MarkerClassifier()
        
        from marker_classification import TestDependencies
        
        # Unit test
        unit_deps = TestDependencies(has_mocks=True)
        assert classifier._classify_functional(unit_deps) == "unit"
        
        # Integration test
        integration_deps = TestDependencies(
            has_mocks=True, 
            azure_services={"azure_ai"}
        )
        assert classifier._classify_functional(integration_deps) == "integration"
        
        # E2E test
        e2e_deps = TestDependencies(
            has_mocks=False,
            external_services={"database"}
        )
        assert classifier._classify_functional(e2e_deps) == "e2e"
    
    @pytest.mark.database
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.salesforce
    @pytest.mark.databricks
    @pytest.mark.fast
    @pytest.mark.unit
    def test_marker_validation_logic(self):
        """Test marker validation logic."""
        validator = MarkerValidator()
        
        # Valid marker sets
        valid_markers = [
            ["fast", "unit", "smoke"],
            ["medium", "integration", "azure"],
            ["slow", "e2e", "database"]
        ]
        
        for markers in valid_markers:
            is_valid, issues = validator.validate_marker_set(markers)
            assert is_valid, f"Markers {markers} should be valid, but got issues: {issues}"
        
        # Invalid marker sets
        invalid_markers = [
            ["fast", "retry"],  # fast + retry conflict
            ["unit", "azure"],  # unit + azure conflict
            ["unit", "integration"],  # multiple functional markers
            ["fast", "slow"],  # multiple performance markers
            []  # missing required markers
        ]
        
        for markers in invalid_markers:
            is_valid, issues = validator.validate_marker_set(markers)
            assert not is_valid, f"Markers {markers} should be invalid but was considered valid"


# Performance-based test measurement decorator (from Phase X prompt)
import time
from functools import wraps

def measure_and_classify_test(test_func):
    """Decorator to measure test execution and suggest appropriate markers."""
    @wraps(test_func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = test_func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Suggest appropriate performance marker
        if execution_time < 1.0:
            suggested_marker = "fast"
        elif execution_time < 10.0:
            suggested_marker = "medium"
        else:
            suggested_marker = "slow"
        
        # Log suggestion for manual review
        print(f"Test {test_func.__name__} took {execution_time:.2f}s - suggest @pytest.mark.{suggested_marker}")
        
        return result
    return wrapper


if __name__ == "__main__":
    # Run validation tests manually
    validator = TestMarkerValidation()
    
    print("Running Phase X marker validation tests...")
    
    try:
        validator.test_no_marker_conflicts()
        print("✅ No marker conflicts found")
    except AssertionError as e:
        print(f"❌ Marker conflicts: {e}")
    
    try:
        validator.test_all_tests_have_performance_markers()
        print("✅ All tests have performance markers")
    except AssertionError as e:
        print(f"❌ Missing performance markers: {e}")
    
    try:
        validator.test_functional_marker_consistency()
        print("✅ Functional markers are consistent")
    except AssertionError as e:
        print(f"❌ Functional marker conflicts: {e}")
    
    print("\nPhase X marker validation complete!")