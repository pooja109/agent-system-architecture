"""
Simple, Clean Configuration for Scenario Tracking
================================================

Replaces the complex enhancement system with a straightforward dataclass configuration.
Follows the KISS principle - Keep It Simple, Stupid.

This consolidates all the scattered configuration complexity into 4 essential settings.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ScenarioTrackingConfig(BaseModel):
    """
    Simple configuration for scenario tracking.
    
    Replaces the complex ScenarioTrackingConfiguration with essential settings only.
    """
    
    enabled: bool = Field(default=True, description="Enable scenario tracking")
    batch_size: int = Field(default=100, ge=1, description="Batch size for processing")
    retry_attempts: int = Field(default=3, ge=0, description="Number of retry attempts")
    timeout_seconds: int = Field(default=30, gt=0, description="Timeout in seconds")
    async_insert: bool = Field(default=True, description="Use async inserts")
    table_suffix: str = Field(default="", description="Table suffix for environments")
    
    model_config = {
        "extra": "ignore",  # Ignore unknown fields for forward compatibility
        "validate_assignment": True
    }
    
    def __init__(self, **data):
        # Handle legacy field names
        if 'batch_insert_size' in data:
            data['batch_size'] = data.pop('batch_insert_size')
        
        super().__init__(**data)

    @property
    def batch_insert_size(self) -> int:
        """Compatibility property for old field name."""
        return self.batch_size
    
    @batch_insert_size.setter
    def batch_insert_size(self, value: int):
        """Compatibility setter for old field name."""
        self.batch_size = value

    @classmethod
    def from_environment(cls) -> "ScenarioTrackingConfig":
        """Create configuration from environment variables."""
        import os
        
        return cls(
            enabled=os.getenv("SCENARIO_TRACKING_ENABLED", "true").lower() == "true",
            batch_size=int(os.getenv("SCENARIO_TRACKING_BATCH_SIZE", "100")),
            retry_attempts=int(os.getenv("SCENARIO_TRACKING_RETRY_ATTEMPTS", "3")),
            timeout_seconds=int(os.getenv("SCENARIO_TRACKING_TIMEOUT_SECONDS", "30")),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for backward compatibility."""
        return {
            "enabled": self.enabled,
            "batch_insert_size": self.batch_size,  # Map to old field name
            "retry_attempts": self.retry_attempts,
            "connection_timeout_seconds": self.timeout_seconds,  # Map to old field name
            "async_insert": self.async_insert,
            "table_suffix": self.table_suffix,
        }

    @classmethod
    def from_legacy_config(cls, legacy_config: dict) -> "ScenarioTrackingConfig":
        """Create from legacy ScenarioTrackingConfiguration dict."""
        return cls(
            enabled=legacy_config.get("enabled", True),
            batch_size=legacy_config.get("batch_insert_size", 100),
            retry_attempts=legacy_config.get("retry_attempts", 3),
            timeout_seconds=legacy_config.get("connection_timeout_seconds", 30),
            async_insert=legacy_config.get("async_insert", True),
            table_suffix=legacy_config.get("table_suffix", ""),
        )


# Default global configuration instance
DEFAULT_CONFIG = ScenarioTrackingConfig()


def get_config() -> ScenarioTrackingConfig:
    """Get the current scenario tracking configuration."""
    try:
        return ScenarioTrackingConfig.from_environment()
    except (ValueError, TypeError):
        # Fall back to defaults if environment variables are invalid
        return DEFAULT_CONFIG