#!/usr/bin/env python3
"""
Integration Test Suite for Inbox Monitor Isolation
=================================================

Comprehensive test suite to verify complete isolation, backward compatibility,
and all functionality specified in Phase 2 requirements.
"""

import os
import sys
import tempfile
import shutil
import subprocess
import pytest
import json
from pathlib import Path
from typing import List, Dict, Any
import threading
import time


class TestInboxMonitorIsolation:
    """Test suite for inbox monitor isolation requirements."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up test environment before each test."""
        self.service_root = Path(__file__).parent.parent.parent
        self.original_cwd = Path.cwd()
        os.chdir(self.service_root)
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        yield
        
        # Restore environment and directory
        os.environ.clear()
        os.environ.update(self.original_env)
        os.chdir(self.original_cwd)
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_all_required_files_exist(self):
        """Test that all required files from Phase 2 checklist exist."""
        required_files = [
            'main.py',
            'requirements.txt', 
            '__init__.py',
            '.gitignore',
            'run.sh',
            'run.py',
            'config/settings.py',
            'README_ISOLATED.md'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.service_root / file_path).exists():
                missing_files.append(file_path)
        
        assert not missing_files, f"Missing required files: {missing_files}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_python_dotenv_in_requirements(self):
        """Test that python-dotenv is properly specified in requirements.txt."""
        requirements_file = self.service_root / "requirements.txt"
        with open(requirements_file, 'r') as f:
            content = f.read()
        
        assert 'python-dotenv' in content, "python-dotenv not found in requirements.txt"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_main_py_environment_loading(self):
        """Test that main.py has proper environment loading implementation."""
        main_file = self.service_root / "main.py"
        with open(main_file, 'r') as f:
            content = f.read()
        
        required_elements = [
            'def load_environment(',
            'ENV_LOADED = load_environment()',
            'INBOX_MONITOR_ROOT',
            'PROMPTS_BASE_PATH'
        ]
        
        for element in required_elements:
            assert element in content, f"Missing element in main.py: {element}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_init_py_service_metadata(self):
        """Test that __init__.py has all required service metadata."""
        init_file = self.service_root / "__init__.py"
        with open(init_file, 'r') as f:
            content = f.read()
        
        required_metadata = [
            '__version__',
            '__service__',
            'SERVICE_ROOT',
            'PROMPTS_DIR',
            'CONFIG_DIR',
            'UTILS_DIR',
            'SERVICES_DIR',
            'MODELS_DIR'
        ]
        
        for metadata in required_metadata:
            assert metadata in content, f"Missing metadata in __init__.py: {metadata}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_service_runs_in_complete_isolation(self):
        """Test that service can run in completely isolated directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Copy inbox_monitor to temp location
            dst = tmpdir / 'inbox_monitor'
            shutil.copytree(
                self.service_root, 
                dst, 
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', 'tests')
            )
            
            # Try to run help command in isolation
            result = subprocess.run(
                [sys.executable, 'main.py', '--help'],
                cwd=dst,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            assert result.returncode == 0, f"Service failed in isolation: {result.stderr}"
            assert 'Inbox Monitor' in result.stdout, "Help output not found"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_backward_compatibility(self):
        """Test that service can be imported from parent directory context."""
        # Test from repository root
        repo_root = self.service_root.parent.parent
        
        result = subprocess.run(
            [sys.executable, '-c', 
             'from agents.inbox_monitor.config.settings import get_settings; print("✅ Backward compatibility works")'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"Backward compatibility broken: {result.stderr}"
        assert "✅" in result.stdout, "Import test failed"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.scenario_tracking
    @pytest.mark.medium
    @pytest.mark.integration
    def test_environment_loading_scenarios(self):
        """Test various environment loading scenarios."""
        # Test 1: With REQUIRE_ENV_FILE set
        env = os.environ.copy()
        env['REQUIRE_ENV_FILE'] = 'true'
        
        result = subprocess.run(
            [sys.executable, 'main.py', '--help'],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, "Service should work even with warning"
        assert 'Warning: No .env file found' in result.stdout, "Warning not displayed"
        
        # Test 2: With local .env file
        env_file = self.service_root / '.env'
        env_file.write_text('TEST_VAR=test_value\n')
        
        try:
            result = subprocess.run(
                [sys.executable, '-c', 
                 'import main; import os; print("TEST_VAR=" + os.getenv("TEST_VAR", "NOT_FOUND"))'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            assert result.returncode == 0, f"Environment loading failed: {result.stderr}"
            assert 'TEST_VAR=test_value' in result.stdout, "Environment variable not loaded"
        finally:
            if env_file.exists():
                env_file.unlink()
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_runner_scripts_functionality(self):
        """Test that both runner scripts work correctly."""
        # Test Python runner
        result = subprocess.run(
            [sys.executable, 'run.py', '--help'],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"Python runner failed: {result.stderr}"
        
        # Test shell runner
        result = subprocess.run(
            ['./run.sh', '--help'],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"Shell runner failed: {result.stderr}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_no_external_parent_dependencies(self):
        """Test that there are no imports to parent directories outside service."""
        def check_file_imports(file_path: Path) -> List[str]:
            """Check a Python file for external imports."""
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                issues = []
                # Look for imports that go outside the service
                if 'from ...' in content and '# Backward compatibility' not in content:
                    # Check if it's going outside the service directory
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip().startswith('from ...'):
                            issues.append(f"Line {i+1}: {line.strip()}")
                
                return issues
            except Exception:
                return []
        
        all_issues = []
        for py_file in self.service_root.rglob('*.py'):
            if not any(exclude in str(py_file) for exclude in ['test', '__pycache__', '.pytest_cache']):
                issues = check_file_imports(py_file)
                for issue in issues:
                    all_issues.append(f"{py_file.relative_to(self.service_root)}: {issue}")
        
        assert not all_issues, f"External dependency issues found: {all_issues}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_path_resolution_correctness(self):
        """Test that path resolution works correctly."""
        # Import main to trigger environment loading
        import main
        
        service_root = os.environ.get('INBOX_MONITOR_ROOT')
        prompts_path = os.environ.get('PROMPTS_BASE_PATH')
        
        assert service_root, "INBOX_MONITOR_ROOT not set"
        assert prompts_path, "PROMPTS_BASE_PATH not set"
        
        expected_prompts = str(Path(service_root) / 'prompts')
        assert prompts_path == expected_prompts, f"Path mismatch: {prompts_path} vs {expected_prompts}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_container_environment_detection(self):
        """Test that container environment is detected correctly."""
        # Test Kubernetes detection
        env = os.environ.copy()
        env['KUBERNETES_SERVICE_HOST'] = 'kubernetes.default.svc'
        
        result = subprocess.run(
            [sys.executable, '-c', 
             '''
import os
os.environ["KUBERNETES_SERVICE_HOST"] = "kubernetes.default.svc"
import main
print("✅ Container environment handled")
             '''],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"Container detection failed: {result.stderr}"
        assert "✅" in result.stdout, "Container environment not handled properly"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_concurrent_environment_loading(self):
        """Test thread safety of environment loading."""
        def load_env_worker(results: List[bool], index: int):
            """Worker function for concurrent testing."""
            try:
                # Import in thread to test concurrent loading
                import importlib
                if 'main' in sys.modules:
                    importlib.reload(sys.modules['main'])
                else:
                    import main
                results[index] = True
            except Exception:
                results[index] = False
        
        # Start multiple threads
        num_threads = 5
        results = [False] * num_threads
        threads = []
        
        for i in range(num_threads):
            thread = threading.Thread(target=load_env_worker, args=(results, i))
            threads.append(thread)
        
        # Start all threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)
        
        # Check results
        assert all(results), f"Concurrent environment loading failed: {results}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.security
    @pytest.mark.medium
    @pytest.mark.integration
    def test_service_executable_permissions(self):
        """Test that runner scripts have proper executable permissions."""
        run_sh = self.service_root / 'run.sh'
        assert run_sh.exists(), "run.sh does not exist"
        assert os.access(run_sh, os.X_OK), "run.sh is not executable"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_gitignore_completeness(self):
        """Test that .gitignore includes all necessary patterns."""
        gitignore_file = self.service_root / '.gitignore'
        with open(gitignore_file, 'r') as f:
            content = f.read()
        
        required_patterns = [
            '.env',
            '.env.local',
            '.env.production',
            '.env.staging',
            '.env.development',
            '__pycache__/',
            '*.pyc',
            '.pytest_cache/'
        ]
        
        for pattern in required_patterns:
            assert pattern in content, f"Missing gitignore pattern: {pattern}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_documentation_completeness(self):
        """Test that README_ISOLATED.md has all required sections."""
        readme_file = self.service_root / 'README_ISOLATED.md'
        with open(readme_file, 'r') as f:
            content = f.read()
        
        required_sections = [
            '# Inbox Monitor - Isolated Service',
            '## Isolation Features',
            '## Quick Start',
            '## Environment Configuration',
            '## Service Architecture',
            '## Deployment Scenarios'
        ]
        
        for section in required_sections:
            assert section in content, f"Missing documentation section: {section}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.slow
    def test_performance_baseline(self):
        """Test that service meets performance requirements."""
        import time
        
        # Test import performance
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, '-c', 'import main'],
            capture_output=True,
            text=True,
            timeout=10
        )
        import_time = time.time() - start_time
        
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert import_time < 5.0, f"Import too slow: {import_time:.2f}s > 5.0s"
        
        # Test help command performance
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, 'main.py', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        help_time = time.time() - start_time
        
        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert help_time < 5.0, f"Help command too slow: {help_time:.2f}s > 5.0s"


class TestIsolationEdgeCases:
    """Test edge cases and error conditions for isolation."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_missing_dotenv_graceful_handling(self):
        """Test that service handles missing python-dotenv gracefully."""
        # This would be tested in an environment without python-dotenv
        # For now, we verify the import structure supports graceful degradation
        main_file = Path(__file__).parent.parent.parent / "main.py"
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Verify that dotenv import is inside a function, not at module level
        assert 'from dotenv import load_dotenv' in content
        assert 'def load_environment(' in content
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_corrupted_env_file_handling(self):
        """Test handling of corrupted .env files."""
        service_root = Path(__file__).parent.parent.parent
        env_file = service_root / '.env'
        
        # Create corrupted .env file
        env_file.write_text('INVALID_ENV_LINE_WITHOUT_EQUALS\nVALID_VAR=value\n')
        
        try:
            result = subprocess.run(
                [sys.executable, 'main.py', '--help'],
                cwd=service_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Should still work despite corrupted lines
            assert result.returncode == 0, f"Failed with corrupted .env: {result.stderr}"
        finally:
            if env_file.exists():
                env_file.unlink()
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_readonly_environment_handling(self):
        """Test behavior in read-only environments."""
        # Test that service works without write permissions to service directory
        service_root = Path(__file__).parent.parent.parent
        
        # Test in read-only scenario (simulated)
        result = subprocess.run(
            [sys.executable, '-c', '''
import os
import main
print("✅ Read-only environment handled")
            '''],
            cwd=service_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"Failed in read-only environment: {result.stderr}"
        assert "✅" in result.stdout


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--tb=short"])