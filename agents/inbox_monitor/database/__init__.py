"""
Database module for inbox monitor scenario tracking.

Provides database schema definitions and Pydantic models for tracking
comprehensive scenario processing data in Databricks Delta tables.
"""

from .scenario_tracking_models import (
    ScenarioProcessingRecord,
    ScenarioType,
    AIIntent,
    EmailImportanceLevel,
    TestModeType,
    DatabaseUpdateRecord,
    ScenarioTrackingConfiguration,
)

__all__ = [
    "ScenarioProcessingRecord",
    "ScenarioType", 
    "AIIntent",
    "EmailImportanceLevel",
    "TestModeType",
    "DatabaseUpdateRecord",
    "ScenarioTrackingConfiguration",
]