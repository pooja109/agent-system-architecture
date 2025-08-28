"""
Standardized import helpers to eliminate sys.path manipulation across tests.
"""
import sys
from pathlib import Path
from typing import Any, Dict

# Standard project root detection
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

def ensure_project_imports():
    """
    Ensure project modules are importable without sys.path manipulation.
    Call this at the top of test modules that need project imports.
    """
    project_root_str = str(PROJECT_ROOT)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

def safe_import_service(service_name: str) -> Any:
    """
    Safely import a service module with proper error handling.
    
    Args:
        service_name: Name of the service module (e.g., 'response_handler')
        
    Returns:
        The imported module
        
    Raises:
        ImportError: If the service cannot be imported with detailed error info
    """
    ensure_project_imports()
    try:
        return __import__(f'services.{service_name}', fromlist=[service_name])
    except ImportError as e:
        raise ImportError(f"Failed to import services.{service_name}: {e}") from e

def safe_import_model(model_name: str) -> Any:
    """
    Safely import a model module with proper error handling.
    """
    ensure_project_imports()
    try:
        return __import__(f'models.{model_name}', fromlist=[model_name])
    except ImportError as e:
        raise ImportError(f"Failed to import models.{model_name}: {e}") from e