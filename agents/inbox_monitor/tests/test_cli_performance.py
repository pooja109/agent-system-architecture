"""
CLI Performance Testing for Test Runner
=======================================

Performance validation tests for the CLI runner as specified in Phase X prompt.
These tests verify that CLI execution modes meet expected performance targets.
"""

import subprocess
import time
import pytest
from pathlib import Path


class TestCLIPerformance:
    """Performance validation tests for the CLI runner."""

    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.unit
    def test_cli_performance_fast_mode(self):
        """Verify fast mode completes within expected timeframe."""
        start_time = time.time()
        result = subprocess.run([
            'python', 'run_tests.py', '--fast', '--quiet'
        ], capture_output=True)
        
        duration = time.time() - start_time
        
        assert result.returncode == 0, "Fast tests should pass"
        assert duration < 300, f"Fast mode took {duration}s, expected < 300s (5 minutes)"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_performance_integration_mode(self):
        """Verify integration mode completes within expected timeframe."""
        start_time = time.time()
        result = subprocess.run([
            'python', 'run_tests.py', '--integration', '--quiet'
        ], capture_output=True)
        
        duration = time.time() - start_time
        
        # Integration mode allows failures but should complete within time limit
        assert duration < 600, f"Integration mode took {duration}s, expected < 600s (10 minutes)"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.smoke
    @pytest.mark.slow
    @pytest.mark.unit
    def test_cli_dry_run_functionality(self):
        """Test dry run mode provides accurate test collection."""
        result = subprocess.run([
            'python', 'run_tests.py', '--fast', '--dry-run'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, "Dry run should succeed"
        assert "Would execute" in result.stdout, "Should show test count"
        assert "DRY RUN" in result.stdout, "Should indicate dry run mode"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.smoke
    @pytest.mark.slow
    @pytest.mark.unit
    def test_cli_smoke_mode_performance(self):
        """Verify smoke mode completes within expected timeframe."""
        start_time = time.time()
        result = subprocess.run([
            'python', 'run_tests.py', '--smoke', '--quiet'
        ], capture_output=True)
        
        duration = time.time() - start_time
        
        assert result.returncode == 0, "Smoke tests should pass"
        assert duration < 180, f"Smoke mode took {duration}s, expected < 180s (3 minutes)"
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.slow
    def test_cli_list_markers_performance(self):
        """Verify --list-markers command executes quickly."""
        start_time = time.time()
        result = subprocess.run([
            'python', 'run_tests.py', '--list-markers'
        ], capture_output=True, text=True)
        
        duration = time.time() - start_time
        
        assert result.returncode == 0, "List markers should succeed"
        assert duration < 5, f"List markers took {duration}s, expected < 5s"
        assert "Available Test Markers:" in result.stdout, "Should show marker list"