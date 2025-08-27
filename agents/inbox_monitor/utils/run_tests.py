#!/usr/bin/env python3
"""
Test runner for inbox monitor
"""

import os
import sys

import pytest

# Add parent directory to path to avoid import issues
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if __name__ == "__main__":
    # Run tests with appropriate settings
    exit_code = pytest.main(
        [
            "tests/",
            "-v",
            "--tb=short",
            "-p",
            "no:warnings",  # Disable warnings for cleaner output
        ]
    )

    sys.exit(exit_code)
