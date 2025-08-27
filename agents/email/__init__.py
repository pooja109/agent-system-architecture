"""
Email Agent Service
===================

Email processing and sending service for automated communications.
"""

__version__ = "2.0.0"
__service__ = "email-agent"
__author__ = "Your Organization"

import os
import sys
from pathlib import Path

# Service root directory
SERVICE_ROOT = Path(__file__).parent.resolve()

# Ensure service root is in Python path for imports
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

# Export commonly used paths
CONFIG_DIR = SERVICE_ROOT / "config"
SERVICES_DIR = SERVICE_ROOT / "services"
DATABASE_DIR = SERVICE_ROOT / "database"

__all__ = [
    "__version__",
    "__service__",
    "SERVICE_ROOT",
    "CONFIG_DIR",
    "SERVICES_DIR",
    "DATABASE_DIR",
]