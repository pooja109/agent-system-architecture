"""
Performance Tests for Prompt Manager - Focused Test Suite
=========================================================
Actual performance test methods separated from utility classes.
"""
import pytest

# Phase 4 Architectural Solutions - Performance Testing Architecture Integration
from tests.fixtures.performance_architecture import (
    performance_framework, PerformanceTestingFramework
)


class TestPerformanceBenchmarks:
    """
    Performance test suite for PromptManager - RECOVERED with Performance Testing Architecture.
    Focused on actual performance test execution.
    """
    
    @pytest.mark.slow
    @pytest.mark.performance  
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.integration
    def test_performance_regression_detection_integrated(self, performance_framework):
        """Test integrated performance regression detection - RECOVERED."""
        # Run all registered performance benchmarks
        results = performance_framework.run_all_benchmarks()
        
        # Check for performance regressions against baselines
        regressions = []
        for result in results:
            comparison = performance_framework.compare_with_baseline(result)
            
            if 'mean_time_ratio' in comparison:
                # Consider >25% slower as regression for performance tests
                if comparison['mean_time_ratio'] > 1.25:
                    regressions.append({
                        'benchmark': result.benchmark_name,
                        'regression_percent': (comparison['mean_time_ratio'] - 1.0) * 100,
                        'current_time': result.mean_time,
                        'baseline_time': result.mean_time / comparison['mean_time_ratio']
                    })
        
        # Report any regressions
        if regressions:
            regression_details = []
            for r in regressions:
                regression_details.append(
                    f"{r['benchmark']}: {r['current_time']:.3f}s vs baseline {r['baseline_time']:.3f}s "
                    f"(+{r['regression_percent']:.1f}%)"
                )
            pytest.fail(f"Performance regressions detected:\n" + "\n".join(regression_details))
        
        # Verify at least some benchmarks ran successfully  
        successful_benchmarks = sum(1 for r in results if r.success)
        assert successful_benchmarks > 0, "No performance benchmarks executed successfully"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    def test_performance_architecture_integration(self, performance_framework):
        """Test that performance architecture is properly integrated - RECOVERED."""
        # Verify framework is configured
        assert isinstance(performance_framework, PerformanceTestingFramework)
        
        # Verify default benchmarks are registered
        default_benchmarks = performance_framework.benchmarks
        assert 'import_performance' in default_benchmarks
        
        # Test framework functionality
        assert hasattr(performance_framework, 'run_benchmark')
        assert hasattr(performance_framework, 'compare_with_baseline')
        assert hasattr(performance_framework, 'generate_performance_report')
        
        # Verify baseline functionality
        performance_framework.save_baseline_results()
        performance_framework.load_baseline_results()
        
        # Test baseline management utilities
        performance_framework.initialize_default_baselines()
        validation = performance_framework.validate_baseline_consistency()
        assert validation['validation_passed'] or len(validation['missing_baselines']) == 0
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    def test_baseline_management_utilities(self, performance_framework):
        """Test baseline management utilities for CI/CD consistency - ADDED for 100% compliance."""
        # Test default baseline initialization
        initial_count = len(performance_framework.baseline_results)
        performance_framework.initialize_default_baselines()
        
        # Should have at least the default baselines
        assert len(performance_framework.baseline_results) >= 5  # 5 default baselines
        
        # Test baseline validation
        validation = performance_framework.validate_baseline_consistency()
        assert 'validation_passed' in validation
        assert 'missing_baselines' in validation
        assert 'inconsistent_baselines' in validation
        
        # Test that baseline results are properly structured
        assert len(performance_framework.baseline_results) > 0
        for baseline_name, baseline_data in performance_framework.baseline_results.items():
            assert isinstance(baseline_name, str)
            assert baseline_data is not None