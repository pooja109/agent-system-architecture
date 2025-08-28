"""
Utilities for systematic test marker application and validation.

This module provides tools for analyzing test functions and applying
appropriate pytest markers based on code patterns, file locations,
and naming conventions.
"""
import ast
import inspect
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Union
import pytest


class TestMarkerAnalyzer:
    """
    Analyzes test functions to recommend appropriate markers based on
    code patterns, dependencies, and naming conventions.
    """
    
    # Performance classification patterns
    FAST_INDICATORS = [
        'mock', 'Mock', 'patch', 'monkeypatch',  # Heavy mocking indicates fast test
        'unit', 'Unit',  # Unit tests should be fast
        'validate', 'parse', 'format', 'transform',  # Simple operations
        'config', 'Config', 'setting', 'Setting',  # Configuration tests
        'argument', 'Argument', 'cli', 'CLI',  # CLI parsing tests
    ]
    
    MEDIUM_INDICATORS = [
        'integration', 'Integration',  # Integration tests
        'database', 'db', 'Database',  # Database operations
        'service', 'Service',  # Service integration
        'async', 'await',  # Async operations may be slower
        'client', 'Client',  # Client integration
        'connection', 'Connection',  # Connection handling
        'pool', 'Pool',  # Connection pooling
    ]
    
    SLOW_INDICATORS = [
        'end_to_end', 'e2e', 'E2E',  # End-to-end tests
        'performance', 'Performance', 'load', 'Load',  # Performance tests
        'external', 'api', 'API',  # External API calls
        'timeout', 'sleep', 'delay',  # Tests with explicit delays
        'scenario', 'workflow', 'pipeline',  # Complex workflows
        'real_database', 'production',  # Real infrastructure
    ]
    
    # Functional classification patterns
    UNIT_INDICATORS = [
        'test_init', 'test_constructor', 'test_method',
        'Mock', 'mock', 'patch',  # Heavy mocking
        'validate', 'parse', 'format', 'transform',  # Simple functions
        'property', 'Property', 'getter', 'setter',  # Property tests
    ]
    
    INTEGRATION_INDICATORS = [
        'integration', 'Integration',
        'service', 'Service', 'client', 'Client',
        'database', 'Database', 'db',
        'workflow', 'pipeline', 'chain',
        'manager', 'Manager', 'handler', 'Handler',
        'connection', 'Connection', 'pool', 'Pool',
    ]
    
    EDGE_CASE_INDICATORS = [
        'error', 'Error', 'exception', 'Exception',
        'invalid', 'Invalid', 'malformed', 'corrupt',
        'edge', 'Edge', 'boundary', 'Boundary',
        'timeout', 'Timeout', 'failure', 'Failure',
        'empty', 'Empty', 'null', 'None',
        'limit', 'Limit', 'max', 'Max', 'overflow',
    ]
    
    # Descriptive marker patterns
    DESCRIPTIVE_PATTERNS = {
        'azure': ['azure', 'Azure', 'graph', 'Graph', 'keyvault', 'KeyVault', 'ai_foundry', 'AIFoundry'],
        'email': ['email', 'Email', 'inbox', 'Inbox', 'message', 'Message', 'processing'],
        'retry': ['retry', 'Retry', 'circuit', 'Circuit', 'resilience', 'backoff'],
        'performance': ['performance', 'Performance', 'benchmark', 'Benchmark', 'load', 'Load'],
        'security': ['security', 'Security', 'auth', 'Auth', 'permission', 'Permission', 'pii', 'PII'],
        'cli': ['cli', 'CLI', 'argument', 'Argument', 'command', 'Command', 'parser'],
        'salesforce': ['salesforce', 'Salesforce', 'sfdc', 'SFDC'],
        'databricks': ['databricks', 'Databricks', 'spark', 'Spark', 'warehouse'],
        'prompt': ['prompt', 'Prompt', 'template', 'Template'],
        'monitoring': ['monitor', 'Monitor', 'health', 'Health', 'metrics', 'Metrics'],
        'database': ['database', 'Database', 'db', 'DB', 'sql', 'SQL'],
        'scenario_tracking': ['scenario', 'Scenario', 'tracking', 'Tracking'],
    }
    
    # File path patterns for classification
    FILE_PATTERNS = {
        'cli/': ['fast', 'unit', 'cli'],
        'unit/': ['fast', 'unit'],
        'integration/': ['medium', 'integration'], 
        'load_testing/': ['slow', 'performance', 'load'],
        'security/': ['fast', 'unit', 'security'],
        'logging/': ['fast', 'unit'],
        'ui/': ['fast', 'unit'],
        'scenario_tracking/': ['medium', 'integration', 'scenario_tracking'],
    }
    
    @classmethod
    def analyze_test_function(cls, func_name: str, func_source: str, file_path: str) -> Dict[str, List[str]]:
        """
        Analyze a test function and recommend markers.
        
        Args:
            func_name: Name of the test function
            func_source: Source code of the test function
            file_path: Path to the test file
            
        Returns:
            Dict with 'performance', 'functional', and 'descriptive' marker recommendations
        """
        recommendations = {
            'performance': [],
            'functional': [],
            'descriptive': []
        }
        
        # Combine function name, source, and file path for analysis
        analysis_text = f"{func_name} {func_source} {file_path}".lower()
        
        # File path based classification
        for pattern, markers in cls.FILE_PATTERNS.items():
            if pattern in file_path.lower():
                for marker in markers:
                    category = cls._get_marker_category(marker)
                    if category and marker not in recommendations[category]:
                        recommendations[category].append(marker)
        
        # Performance marker analysis - prioritize slow, then medium, then fast
        if any(indicator.lower() in analysis_text for indicator in cls.SLOW_INDICATORS):
            if 'slow' not in recommendations['performance']:
                recommendations['performance'].append('slow')
        elif any(indicator.lower() in analysis_text for indicator in cls.MEDIUM_INDICATORS):
            if 'medium' not in recommendations['performance']:
                recommendations['performance'].append('medium')
        
        # Default to fast if no performance marker yet
        if not recommendations['performance']:
            recommendations['performance'].append('fast')
        
        # Functional marker analysis - prioritize integration, then edge_case, then unit
        if any(indicator.lower() in analysis_text for indicator in cls.INTEGRATION_INDICATORS):
            if 'integration' not in recommendations['functional']:
                recommendations['functional'].append('integration')
        elif any(indicator.lower() in analysis_text for indicator in cls.EDGE_CASE_INDICATORS):
            if 'edge_case' not in recommendations['functional']:
                recommendations['functional'].append('edge_case')
        
        # Default to unit if no functional marker yet
        if not recommendations['functional']:
            recommendations['functional'].append('unit')
        
        # Descriptive marker analysis
        for marker, indicators in cls.DESCRIPTIVE_PATTERNS.items():
            if any(indicator.lower() in analysis_text for indicator in indicators):
                recommendations['descriptive'].append(marker)
        
        return recommendations
    
    @classmethod
    def _get_marker_category(cls, marker: str) -> Optional[str]:
        """Get the category (performance/functional/descriptive) for a marker."""
        performance_markers = {'fast', 'medium', 'slow'}
        functional_markers = {'unit', 'integration', 'edge_case'}
        
        if marker in performance_markers:
            return 'performance'
        elif marker in functional_markers:
            return 'functional'
        else:
            return 'descriptive'


class MarkerApplicationHelper:
    """
    Helper for applying markers to test files systematically.
    """
    
    @staticmethod
    def get_current_markers(test_file_path: Path) -> Dict[str, Set[str]]:
        """
        Parse existing markers from a test file.
        
        Args:
            test_file_path: Path to the test file
            
        Returns:
            Dict mapping function names to their current markers
        """
        current_markers = {}
        
        try:
            with open(test_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find test functions and their decorators using regex
            # This is more reliable than AST for complex decorator patterns
            function_pattern = r'(@pytest\.mark\.[^\n]+\s*)*\s*def\s+(test_\w+)'
            matches = re.finditer(function_pattern, content, re.MULTILINE)
            
            for match in matches:
                decorators_text = match.group(1) or ""
                func_name = match.group(2)
                
                # Extract marker names from decorators
                marker_pattern = r'@pytest\.mark\.(\w+)'
                markers = set(re.findall(marker_pattern, decorators_text))
                current_markers[func_name] = markers
                    
        except Exception as e:
            print(f"Error parsing {test_file_path}: {e}")
            
        return current_markers
    
    @staticmethod
    def generate_marker_decorators(recommendations: Dict[str, List[str]]) -> List[str]:
        """
        Generate pytest marker decorator strings from recommendations.
        
        Args:
            recommendations: Dict with marker recommendations by category
            
        Returns:
            List of decorator strings to add to test functions
        """
        decorators = []
        
        # Add performance marker (only one)
        if recommendations['performance']:
            decorators.append(f"@pytest.mark.{recommendations['performance'][0]}")
        
        # Add functional marker (only one)
        if recommendations['functional']:
            decorators.append(f"@pytest.mark.{recommendations['functional'][0]}")
        
        # Add descriptive markers (can be multiple)
        for marker in recommendations['descriptive']:
            decorators.append(f"@pytest.mark.{marker}")
        
        return decorators
    
    @staticmethod
    def analyze_test_file_for_missing_markers(file_path: Path) -> Dict[str, Dict[str, List[str]]]:
        """
        Analyze a test file and identify functions missing required markers.
        
        Args:
            file_path: Path to the test file
            
        Returns:
            Dict mapping function names to missing marker recommendations
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}
        
        current_markers = MarkerApplicationHelper.get_current_markers(file_path)
        missing_markers = {}
        
        # Find all test functions
        function_pattern = r'def\s+(test_\w+)\s*\([^)]*\):'
        functions = re.findall(function_pattern, content)
        
        for func_name in functions:
            # Get function source (approximate)
            func_start = content.find(f"def {func_name}")
            if func_start == -1:
                continue
                
            # Find next function or end of file
            next_func = content.find("def test_", func_start + 1)
            if next_func == -1:
                next_func = content.find("def ", func_start + 1)
            if next_func == -1:
                next_func = len(content)
                
            func_source = content[func_start:next_func]
            
            # Get recommendations
            recommendations = TestMarkerAnalyzer.analyze_test_function(
                func_name, func_source, str(file_path)
            )
            
            # Check what's missing
            current = current_markers.get(func_name, set())
            missing = {
                'performance': [],
                'functional': [],
                'descriptive': []
            }
            
            # Check performance markers
            has_performance = any(marker in current for marker in ['fast', 'medium', 'slow'])
            if not has_performance and recommendations['performance']:
                missing['performance'] = recommendations['performance']
            
            # Check functional markers  
            has_functional = any(marker in current for marker in ['unit', 'integration', 'edge_case'])
            if not has_functional and recommendations['functional']:
                missing['functional'] = recommendations['functional']
            
            # Check descriptive markers (less critical)
            for marker in recommendations['descriptive']:
                if marker not in current:
                    missing['descriptive'].append(marker)
            
            # Only include if there are missing markers
            if any(missing.values()):
                missing_markers[func_name] = missing
        
        return missing_markers


class MarkerValidator:
    """
    Validates marker application and consistency across the test suite.
    """
    
    @staticmethod
    def validate_test_file_markers(file_path: Path) -> Dict[str, List[str]]:
        """
        Validate marker usage in a test file.
        
        Args:
            file_path: Path to the test file
            
        Returns:
            Dict with validation issues by category
        """
        issues = {
            'missing_performance': [],
            'missing_functional': [],
            'conflicting_markers': [],
            'invalid_combinations': []
        }
        
        current_markers = MarkerApplicationHelper.get_current_markers(file_path)
        
        for func_name, markers in current_markers.items():
            # Check for missing performance markers
            performance_markers = markers & {'fast', 'medium', 'slow'}
            if not performance_markers:
                issues['missing_performance'].append(func_name)
            elif len(performance_markers) > 1:
                issues['conflicting_markers'].append(f"{func_name}: multiple performance markers {performance_markers}")
            
            # Check for missing functional markers
            functional_markers = markers & {'unit', 'integration', 'edge_case'}
            if not functional_markers:
                issues['missing_functional'].append(func_name)
            elif len(functional_markers) > 1:
                issues['conflicting_markers'].append(f"{func_name}: multiple functional markers {functional_markers}")
            
            # Check for invalid combinations
            if 'unit' in markers and 'integration' in markers:
                issues['invalid_combinations'].append(f"{func_name}: unit and integration markers")
            
            if 'fast' in markers and 'slow' in markers:
                issues['invalid_combinations'].append(f"{func_name}: fast and slow markers")
        
        return issues
    
    @staticmethod
    def get_test_suite_marker_stats() -> Dict[str, int]:
        """Get marker statistics across the entire test suite."""
        stats = {}
        test_dir = Path("tests/")
        
        if not test_dir.exists():
            return stats
        
        for test_file in test_dir.rglob("test_*.py"):
            current_markers = MarkerApplicationHelper.get_current_markers(test_file)
            
            for func_name, markers in current_markers.items():
                for marker in markers:
                    stats[marker] = stats.get(marker, 0) + 1
        
        return stats


# Pytest fixtures for marker utilities
@pytest.fixture
def marker_analyzer():
    """Fixture providing marker analysis utilities."""
    return TestMarkerAnalyzer()


@pytest.fixture  
def marker_helper():
    """Fixture providing marker application utilities."""
    return MarkerApplicationHelper()


@pytest.fixture
def marker_validator():
    """Fixture providing marker validation utilities."""
    return MarkerValidator()


# CLI integration for marker analysis
def main():
    """Command-line interface for marker analysis and application."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test marker analysis and application utility")
    parser.add_argument('--analyze', type=str, help='Analyze test file for marker recommendations')
    parser.add_argument('--validate', type=str, help='Validate marker usage in test file')
    parser.add_argument('--stats', action='store_true', help='Show test suite marker statistics')
    
    args = parser.parse_args()
    
    if args.analyze:
        file_path = Path(args.analyze)
        missing = MarkerApplicationHelper.analyze_test_file_for_missing_markers(file_path)
        print(f"Missing markers analysis for {file_path}:")
        for func, markers in missing.items():
            print(f"  {func}: {markers}")
    
    elif args.validate:
        file_path = Path(args.validate)
        issues = MarkerValidator.validate_test_file_markers(file_path)
        print(f"Marker validation for {file_path}:")
        for category, items in issues.items():
            if items:
                print(f"  {category}: {items}")
    
    elif args.stats:
        stats = MarkerValidator.get_test_suite_marker_stats()
        print("Test suite marker statistics:")
        for marker, count in sorted(stats.items()):
            print(f"  {marker}: {count}")


if __name__ == '__main__':
    main()