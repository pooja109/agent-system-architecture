# tests/logging/fixtures/log_samples.py
"""Sample log data for testing."""

import logging
from typing import Dict, Any

# Sample log messages for testing
SAMPLE_MESSAGES = [
    "Simple info message",
    "Debug message with details",
    "Warning about potential issue",
    "Error occurred during processing",
    "Critical system failure",
    "Message with unicode: 🔍 ℹ️ ⚠️ ❌ 🚨",
    "Very long message " + "x" * 500 + " that might cause formatting issues",
    "Message\nwith\nmultiple\nlines",
    "Message with special chars: @#$%^&*()[]{}|\\:;\"'<>,.?/~`+=",
]

# Sample structured log data
SAMPLE_STRUCTURED_DATA = {
    "user_id": 12345,
    "request_id": "req-abc123",
    "duration_ms": 250,
    "metadata": {
        "service": "inbox_monitor",
        "version": "1.0.0"
    },
    "tags": ["important", "performance"]
}

# Sample exception for testing
def create_sample_exception() -> Exception:
    """Create a sample exception for testing."""
    try:
        raise ValueError("Sample error for testing")
    except ValueError as e:
        return e

def create_nested_exception() -> Exception:
    """Create a nested exception for testing."""
    try:
        try:
            raise ValueError("Inner error")
        except ValueError:
            raise RuntimeError("Outer error") from ValueError("Inner error")
    except RuntimeError as e:
        return e