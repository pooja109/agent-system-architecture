#!/usr/bin/env python3
"""
Test Runner Wrapper
===================

Backward compatibility wrapper for the test runner that was moved to scripts/.
This allows running tests from the root directory while maintaining the new structure.

Usage:
    python run_tests.py --fast
    python run_tests.py --all-except-slow
    python run_tests.py --help
"""

import sys
import os
import subprocess
from pathlib import Path

# Add scripts to the path
scripts_path = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_path))

# Import and run the actual test runner
if __name__ == "__main__":
    try:
        # Store original directory and get paths
        original_dir = os.getcwd()
        project_root = Path(__file__).parent
        scripts_dir = project_root / "scripts"
        
        # Set up environment with proper Python path
        env = os.environ.copy()
        python_paths = [
            str(scripts_dir),  # For the scripts themselves
            str(project_root),  # For the main project
        ]
        
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = ":".join(python_paths) + ":" + env['PYTHONPATH']
        else:
            env['PYTHONPATH'] = ":".join(python_paths)
        
        # Run the test runner from the project root (where pytest.ini and tests/ are)
        # But use the script from the scripts directory
        result = subprocess.run(
            [sys.executable, str(scripts_dir / "test_runner.py")] + sys.argv[1:], 
            cwd=str(project_root),  # Run from project root for pytest.ini and tests/
            env=env
        )
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Error running test runner: {e}")
        print(f"Make sure all dependencies are installed and paths are correct.")
        sys.exit(1)