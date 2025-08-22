"""
Configuration Settings Integration for Scenario Tracking
======================================================

This module provides configuration integration for inbox monitor scenario tracking.
It bridges the scenario tracking models with the main settings system to ensure
seamless integration with existing configuration patterns.

Key Components:
- ScenarioTrackingConfiguration: Complete configuration model for tracking settings
- Environment variable integration for all tracking options
- Validation rules for configuration parameters
- Support for test mode and environment-specific configurations

Usage:
    from config.scenario_tracking_settings import ScenarioTrackingConfiguration
    
    # Create configuration with defaults
    config = ScenarioTrackingConfiguration()
    
    # Create configuration with custom settings
    config = ScenarioTrackingConfiguration(
        enabled=True,
        batch_insert_size=50,
        retry_attempts=5
    )

Environment Variables:
    SCENARIO_TRACKING_ENABLED: Enable/disable scenario tracking (default: True)
    SCENARIO_TRACKING_BATCH_SIZE: Batch size for inserts (default: 100)
    SCENARIO_TRACKING_RETRY_ATTEMPTS: Number of retry attempts (default: 3)
    SCENARIO_TRACKING_ASYNC_INSERT: Use async inserts (default: True)
    
Configuration Validation:
    All configuration parameters include validation rules to ensure:
    - Batch sizes are within reasonable limits (1-1000)
    - Retry attempts are bounded (1-10)
    - Timeout values are appropriate for production use
    - Performance thresholds are realistic for monitoring

Integration Notes:
    This module is imported by the main settings.py to provide scenario tracking
    configuration as part of the overall application settings. The configuration
    follows the same patterns as existing settings for consistency.
"""

from typing import TYPE_CHECKING

# Import with fallback handling for different execution contexts
try:
    from ..database.scenario_tracking_models import ScenarioTrackingConfiguration
except ImportError:
    try:
        from database.scenario_tracking_models import ScenarioTrackingConfiguration
    except ImportError:
        # Fallback for standalone usage or testing environments
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from database.scenario_tracking_models import ScenarioTrackingConfiguration

# Type checking import to avoid circular dependencies
if TYPE_CHECKING:
    from database.scenario_tracking_models import ScenarioTrackingConfiguration

# Export ScenarioTrackingConfiguration for use in main settings
__all__ = ["ScenarioTrackingConfiguration"]