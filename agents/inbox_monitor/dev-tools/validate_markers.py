#!/usr/bin/env python3
"""
Comprehensive marker validation script for Phase X test categorization.
Usage: python validate_markers.py
"""

import os
import sys
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# Required markers
PERFORMANCE_MARKERS = {'fast', 'medium', 'slow'}
FUNCTIONAL_MARKERS = {'unit', 'integration', 'edge_case'}
DESCRIPTIVE_MARKERS = {'azure', 'email', 'retry', 'prompt', 'ci_safe', 'salesforce', 'databricks', 'monitoring'}

class MarkerValidator:
    """Validates test marker assignments and compliance."""
    
    def __init__(self):
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
        self.test_markers: Dict[str, Set[str]] = {}
    
    def run_comprehensive_validation(self) -> Dict[str, any]:
        """Run complete marker validation suite."""
        print("🔍 PHASE X MARKER VALIDATION: Running comprehensive validation...")
        
        results = {
            'collection_validation': self.validate_test_collection(),
            'marker_presence': self.validate_marker_presence(),
            'marker_consistency': self.validate_marker_consistency(),
            'marker_logic': self.validate_marker_logic(),
            'performance_validation': self.validate_performance_categories(),
            'functional_validation': self.validate_functional_categories(),
            'errors': self.validation_errors,
            'warnings': self.validation_warnings,
            'compliance_score': 0.0
        }
        
        # Calculate compliance score
        total_checks = 6
        passed_checks = sum(1 for key, value in results.items() 
                           if key.endswith('_validation') and value.get('status') == 'PASS')
        results['compliance_score'] = (passed_checks / total_checks) * 100
        
        return results
    
    def validate_test_collection(self) -> Dict[str, any]:
        """Validate that all tests can be collected properly."""
        print("📋 Validating test collection...")
        
        cmd = ["python", "-m", "pytest", "--collect-only", "-q", "tests/"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse collection output
                lines = result.stdout.strip().split('\n')
                test_count = 0
                for line in lines:
                    if 'selected' in line or 'collected' in line:
                        # Extract number from line like "428 tests collected"
                        match = re.search(r'(\d+)', line)
                        if match:
                            test_count = int(match.group(1))
                
                return {
                    'status': 'PASS',
                    'test_count': test_count,
                    'message': f"Successfully collected {test_count} tests"
                }
            else:
                error_msg = f"Collection failed: {result.stderr}"
                self.validation_errors.append(error_msg)
                return {
                    'status': 'FAIL',
                    'test_count': 0,
                    'message': error_msg
                }
                
        except subprocess.TimeoutExpired:
            error_msg = "Test collection timed out"
            self.validation_errors.append(error_msg)
            return {'status': 'FAIL', 'test_count': 0, 'message': error_msg}
        except Exception as e:
            error_msg = f"Error during collection: {e}"
            self.validation_errors.append(error_msg)
            return {'status': 'FAIL', 'test_count': 0, 'message': error_msg}
    
    def validate_marker_presence(self) -> Dict[str, any]:
        """Validate that all tests have required markers."""
        print("🏷️ Validating marker presence...")
        
        test_files = list(Path('tests').glob('test_*.py'))
        unmarked_tests = []
        total_tests = 0
        marked_tests = 0
        
        for test_file in test_files:
            try:
                content = test_file.read_text()
                test_functions = self._extract_test_functions(content, test_file)
                total_tests += len(test_functions)
                
                for test_func in test_functions:
                    markers = self._extract_markers_from_function(content, test_func)
                    self.test_markers[f"{test_file}::{test_func}"] = markers
                    
                    # Check for required markers
                    has_performance = bool(markers.intersection(PERFORMANCE_MARKERS))
                    has_functional = bool(markers.intersection(FUNCTIONAL_MARKERS))
                    
                    if has_performance and has_functional:
                        marked_tests += 1
                    else:
                        unmarked_tests.append({
                            'test': f"{test_file}::{test_func}",
                            'missing_performance': not has_performance,
                            'missing_functional': not has_functional,
                            'current_markers': list(markers)
                        })
                        
            except Exception as e:
                self.validation_warnings.append(f"Could not analyze {test_file}: {e}")
        
        compliance_rate = (marked_tests / total_tests * 100) if total_tests > 0 else 0
        
        if compliance_rate >= 95:
            status = 'PASS'
        elif compliance_rate >= 80:
            status = 'WARN'
        else:
            status = 'FAIL'
            self.validation_errors.append(f"Low marker compliance: {compliance_rate:.1f}%")
        
        return {
            'status': status,
            'total_tests': total_tests,
            'marked_tests': marked_tests,
            'unmarked_tests': unmarked_tests,
            'compliance_rate': compliance_rate,
            'message': f"Marker compliance: {compliance_rate:.1f}% ({marked_tests}/{total_tests})"
        }
    
    def validate_marker_consistency(self) -> Dict[str, any]:
        """Validate marker consistency and detect conflicts."""
        print("⚖️ Validating marker consistency...")
        
        conflicts = []
        inconsistencies = []
        
        for test_name, markers in self.test_markers.items():
            # Check for conflicting performance markers
            performance_markers = markers.intersection(PERFORMANCE_MARKERS)
            if len(performance_markers) > 1:
                conflicts.append({
                    'test': test_name,
                    'type': 'performance_conflict',
                    'markers': list(performance_markers)
                })
            
            # Check for conflicting functional markers
            functional_markers = markers.intersection(FUNCTIONAL_MARKERS)
            if len(functional_markers) > 1:
                conflicts.append({
                    'test': test_name,
                    'type': 'functional_conflict',
                    'markers': list(functional_markers)
                })
            
            # Check for logical inconsistencies
            if 'unit' in markers and any(svc in markers for svc in ['azure', 'salesforce', 'databricks']):
                inconsistencies.append({
                    'test': test_name,
                    'type': 'unit_service_conflict',
                    'issue': 'Unit test should not depend on external services'
                })
            
            if 'fast' in markers and 'retry' in markers:
                inconsistencies.append({
                    'test': test_name,
                    'type': 'fast_retry_conflict',
                    'issue': 'Retry tests are typically not fast'
                })
        
        total_issues = len(conflicts) + len(inconsistencies)
        
        if total_issues == 0:
            status = 'PASS'
        elif total_issues <= 5:
            status = 'WARN'
        else:
            status = 'FAIL'
            self.validation_errors.append(f"Too many marker conflicts: {total_issues}")
        
        return {
            'status': status,
            'conflicts': conflicts,
            'inconsistencies': inconsistencies,
            'total_issues': total_issues,
            'message': f"Found {total_issues} marker issues"
        }
    
    def validate_marker_logic(self) -> Dict[str, any]:
        """Validate logical relationships between markers."""
        print("🧠 Validating marker logic...")
        
        logic_errors = []
        
        # Define expected relationships
        expected_relationships = {
            'retry': ['slow', 'edge_case'],  # Retry tests should be slow edge cases
            'performance': ['medium', 'slow'],  # Performance tests shouldn't be fast
            'azure': ['integration'],  # Azure tests should be integration
            'salesforce': ['integration'],  # Salesforce tests should be integration
            'databricks': ['integration'],  # Databricks tests should be integration
        }
        
        for test_name, markers in self.test_markers.items():
            for trigger_marker, expected_markers in expected_relationships.items():
                if trigger_marker in markers:
                    # Check if at least one expected marker is present
                    if not any(expected in markers for expected in expected_markers):
                        logic_errors.append({
                            'test': test_name,
                            'issue': f"Test has '{trigger_marker}' but missing expected markers: {expected_markers}",
                            'current_markers': list(markers)
                        })
        
        if len(logic_errors) == 0:
            status = 'PASS'
        elif len(logic_errors) <= 10:
            status = 'WARN'
        else:
            status = 'FAIL'
            self.validation_errors.append(f"Too many logic errors: {len(logic_errors)}")
        
        return {
            'status': status,
            'logic_errors': logic_errors,
            'message': f"Found {len(logic_errors)} marker logic issues"
        }
    
    def validate_performance_categories(self) -> Dict[str, any]:
        """Validate performance category assignments."""
        print("⏱️ Validating performance categories...")
        
        performance_stats = {
            'fast': {'count': 0, 'tests': []},
            'medium': {'count': 0, 'tests': []},
            'slow': {'count': 0, 'tests': []}
        }
        
        for test_name, markers in self.test_markers.items():
            for category in ['fast', 'medium', 'slow']:
                if category in markers:
                    performance_stats[category]['count'] += 1
                    performance_stats[category]['tests'].append(test_name)
        
        total_performance_tests = sum(stats['count'] for stats in performance_stats.values())
        
        # Validate distribution (should not be heavily skewed)
        fast_ratio = performance_stats['fast']['count'] / total_performance_tests if total_performance_tests > 0 else 0
        medium_ratio = performance_stats['medium']['count'] / total_performance_tests if total_performance_tests > 0 else 0
        slow_ratio = performance_stats['slow']['count'] / total_performance_tests if total_performance_tests > 0 else 0
        
        distribution_issues = []
        if fast_ratio > 0.8:
            distribution_issues.append("Too many tests marked as 'fast' (>80%)")
        if slow_ratio > 0.5:
            distribution_issues.append("Too many tests marked as 'slow' (>50%)")
        if medium_ratio < 0.1 and total_performance_tests > 20:
            distribution_issues.append("Too few tests marked as 'medium' (<10%)")
        
        if len(distribution_issues) == 0:
            status = 'PASS'
        else:
            status = 'WARN'
            self.validation_warnings.extend(distribution_issues)
        
        return {
            'status': status,
            'statistics': performance_stats,
            'distribution': {'fast': fast_ratio, 'medium': medium_ratio, 'slow': slow_ratio},
            'distribution_issues': distribution_issues,
            'message': f"Performance distribution - Fast: {fast_ratio:.1%}, Medium: {medium_ratio:.1%}, Slow: {slow_ratio:.1%}"
        }
    
    def validate_functional_categories(self) -> Dict[str, any]:
        """Validate functional category assignments."""
        print("🔧 Validating functional categories...")
        
        functional_stats = {
            'unit': {'count': 0, 'tests': []},
            'integration': {'count': 0, 'tests': []},
            'edge_case': {'count': 0, 'tests': []}
        }
        
        for test_name, markers in self.test_markers.items():
            for category in ['unit', 'integration', 'edge_case']:
                if category in markers:
                    functional_stats[category]['count'] += 1
                    functional_stats[category]['tests'].append(test_name)
        
        total_functional_tests = sum(stats['count'] for stats in functional_stats.values())
        
        # Validate that we have a reasonable mix
        unit_ratio = functional_stats['unit']['count'] / total_functional_tests if total_functional_tests > 0 else 0
        integration_ratio = functional_stats['integration']['count'] / total_functional_tests if total_functional_tests > 0 else 0
        edge_case_ratio = functional_stats['edge_case']['count'] / total_functional_tests if total_functional_tests > 0 else 0
        
        balance_issues = []
        if unit_ratio < 0.2:
            balance_issues.append("Too few unit tests (<20%)")
        if integration_ratio < 0.3:
            balance_issues.append("Too few integration tests (<30%)")
        if edge_case_ratio > 0.4:
            balance_issues.append("Too many edge case tests (>40%)")
        
        if len(balance_issues) == 0:
            status = 'PASS'
        else:
            status = 'WARN'
            self.validation_warnings.extend(balance_issues)
        
        return {
            'status': status,
            'statistics': functional_stats,
            'distribution': {'unit': unit_ratio, 'integration': integration_ratio, 'edge_case': edge_case_ratio},
            'balance_issues': balance_issues,
            'message': f"Functional distribution - Unit: {unit_ratio:.1%}, Integration: {integration_ratio:.1%}, Edge: {edge_case_ratio:.1%}"
        }
    
    def _extract_test_functions(self, content: str, file_path: Path) -> List[str]:
        """Extract test function names from file content."""
        functions = []
        
        # Find standalone test functions
        test_func_pattern = r'def (test_[a-zA-Z_0-9]+)'
        functions.extend(re.findall(test_func_pattern, content))
        
        # Find test class methods  
        class_pattern = r'class (Test[a-zA-Z_0-9]+).*?(?=class|\Z)'
        class_matches = re.finditer(class_pattern, content, re.DOTALL)
        
        for class_match in class_matches:
            class_name = class_match.group(1)
            class_content = class_match.group(0)
            
            # Find methods in this class
            method_matches = re.findall(test_func_pattern, class_content)
            for method in method_matches:
                functions.append(f"{class_name}::{method}")
        
        return functions
    
    def _extract_markers_from_function(self, content: str, function_name: str) -> Set[str]:
        """Extract pytest markers for a specific function."""
        markers = set()
        
        # Handle class methods
        if '::' in function_name:
            class_name, method_name = function_name.split('::', 1)
            
            # Find class-level markers
            class_pattern = rf'(?:@pytest\.mark\.\w+\s*\n)*\s*class {re.escape(class_name)}'
            class_match = re.search(class_pattern, content, re.MULTILINE)
            if class_match:
                class_markers = re.findall(r'@pytest\.mark\.(\w+)', class_match.group(0))
                markers.update(class_markers)
            
            # Find method-level markers
            method_pattern = rf'(?:@pytest\.mark\.\w+\s*\n)*\s*def {re.escape(method_name)}'
            method_match = re.search(method_pattern, content, re.MULTILINE)
            if method_match:
                method_markers = re.findall(r'@pytest\.mark\.(\w+)', method_match.group(0))
                markers.update(method_markers)
        else:
            # Standalone function
            func_pattern = rf'(?:@pytest\.mark\.\w+\s*\n)*\s*def {re.escape(function_name)}'
            func_match = re.search(func_pattern, content, re.MULTILINE)
            if func_match:
                func_markers = re.findall(r'@pytest\.mark\.(\w+)', func_match.group(0))
                markers.update(func_markers)
        
        return markers
    
    def generate_validation_report(self, results: Dict[str, any]) -> str:
        """Generate comprehensive validation report."""
        lines = [
            "=" * 80,
            "PHASE X TEST MARKER VALIDATION REPORT",
            "=" * 80,
            f"Overall Compliance Score: {results['compliance_score']:.1f}%",
            "",
        ]
        
        # Collection validation
        collection = results['collection_validation']
        lines.extend([
            f"📋 Test Collection: {collection['status']}",
            f"   Tests collected: {collection['test_count']}",
            f"   Message: {collection['message']}",
            "",
        ])
        
        # Marker presence
        presence = results['marker_presence']
        lines.extend([
            f"🏷️ Marker Presence: {presence['status']}",
            f"   Compliance rate: {presence['compliance_rate']:.1f}%",
            f"   Marked tests: {presence['marked_tests']}/{presence['total_tests']}",
            "",
        ])
        
        # Marker consistency
        consistency = results['marker_consistency']
        lines.extend([
            f"⚖️ Marker Consistency: {consistency['status']}",
            f"   Issues found: {consistency['total_issues']}",
            f"   Conflicts: {len(consistency['conflicts'])}",
            f"   Inconsistencies: {len(consistency['inconsistencies'])}",
            "",
        ])
        
        # Performance validation
        performance = results['performance_validation']
        lines.extend([
            f"⏱️ Performance Categories: {performance['status']}",
            f"   Distribution: {performance['message']}",
            "",
        ])
        
        # Functional validation
        functional = results['functional_validation']
        lines.extend([
            f"🔧 Functional Categories: {functional['status']}",
            f"   Distribution: {functional['message']}",
            "",
        ])
        
        # Errors and warnings
        if results['errors']:
            lines.extend([
                "❌ ERRORS:",
                *[f"   - {error}" for error in results['errors']],
                "",
            ])
        
        if results['warnings']:
            lines.extend([
                "⚠️ WARNINGS:",
                *[f"   - {warning}" for warning in results['warnings']],
                "",
            ])
        
        # Recommendations
        lines.extend([
            "RECOMMENDATIONS:",
            "✅ All tests should have both performance and functional markers",
            "✅ Avoid conflicting markers on the same test",
            "✅ Ensure logical consistency between markers",
            "✅ Balance test distribution across categories",
            "=" * 80
        ])
        
        return "\n".join(lines)
    
    def save_validation_report(self, results: Dict[str, any], filename: str = 'marker_validation_report.txt'):
        """Save validation report to file."""
        report = self.generate_validation_report(results)
        
        try:
            Path(filename).write_text(report)
            print(f"Validation report saved to {filename}")
        except Exception as e:
            print(f"Error saving report: {e}")


def main():
    """Main validation function."""
    validator = MarkerValidator()
    results = validator.run_comprehensive_validation()
    
    # Print summary
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Overall Compliance Score: {results['compliance_score']:.1f}%")
    print(f"Errors: {len(results['errors'])}")
    print(f"Warnings: {len(results['warnings'])}")
    
    # Save detailed report
    validator.save_validation_report(results)
    
    # Save JSON results for programmatic access
    with open('marker_validation_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("Detailed results saved to marker_validation_report.txt and marker_validation_results.json")
    
    # Return appropriate exit code
    if results['compliance_score'] >= 95:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())