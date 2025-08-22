"""
Inbox Monitor Service
====================

Email monitoring and processing service for automated inbox management.
"""

__version__ = "2.0.0"
__service__ = "inbox-monitor"
__author__ = "Your Organization"

import os
from pathlib import Path

# Service root directory (computed once and cached)
SERVICE_ROOT = Path(__file__).parent.resolve()

# Ensure service root is in Python path for imports
import sys
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

# Export commonly used paths (computed once for performance)
PROMPTS_DIR = SERVICE_ROOT / "prompts"
CONFIG_DIR = SERVICE_ROOT / "config"
UTILS_DIR = SERVICE_ROOT / "utils"
SERVICES_DIR = SERVICE_ROOT / "services"
MODELS_DIR = SERVICE_ROOT / "models"

__all__ = [
    "__version__",
    "__service__",
    "SERVICE_ROOT",
    "PROMPTS_DIR",
    "CONFIG_DIR",
    "UTILS_DIR",
    "SERVICES_DIR",
    "MODELS_DIR",
]