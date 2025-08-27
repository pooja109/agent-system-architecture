"""
Test Utilities for Scenario Tracking
===================================

Separates test-specific data and utilities from production code.
This module provides test helpers that were previously embedded in production models.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class TestModeType(str, Enum):
    """Test mode configuration for test scenarios."""
    DISABLED = "disabled"
    FULL_TEST = "full_test"
    EMAIL_TEST = "email_test"
    MOCK_MODE = "mock_mode"


@dataclass
class TestScenarioData:
    """Test data container for scenario testing."""
    
    # Expert assignment test data
    expert_id: str = "0053t00000AvcSuAAJ"  # Madelyn Locascio's ID
    expert_email: str = "madelyn.locascio@staples.com"
    
    # Account test data
    account_name: str = "Ps Bakery Inc"
    sf_contact_id: str = "0033t00003txInQAAU"
    sf_account_id: str = "0013t00002NHELMAA5"
    
    # Email test data
    default_recipients: List[str] = None
    test_substitutions: Dict[str, str] = None
    
    def __post_init__(self):
        if self.default_recipients is None:
            self.default_recipients = ["support@company.com"]
        if self.test_substitutions is None:
            self.test_substitutions = {"email_substitution": "sgeorge@psbakeryinc.com"}


# Global test data instance
TEST_DATA = TestScenarioData()


def get_test_expert_assignment() -> Dict[str, str]:
    """Get test expert assignment data."""
    return {
        "expert_id": TEST_DATA.expert_id,
        "expert_email": TEST_DATA.expert_email,
        "assignment_method": "round_robin_with_availability_check",
        "case_subject": f"AI Agent Led INQUIRY | Test Customer",
        "case_status": "New",
    }


def get_test_account_data() -> Dict[str, str]:
    """Get test Salesforce account data."""
    return {
        "sf_contact_id": TEST_DATA.sf_contact_id,
        "sf_account_id": TEST_DATA.sf_account_id,
        "account_name": TEST_DATA.account_name,
    }


def get_test_recipients() -> List[str]:
    """Get default test recipients."""
    return TEST_DATA.default_recipients.copy()


def get_test_substitutions() -> Dict[str, str]:
    """Get test mode email substitutions."""
    return TEST_DATA.test_substitutions.copy()


def create_test_record_data(base_data: Dict[str, Any], test_mode: bool = False) -> Dict[str, Any]:
    """
    Create test record data by merging base data with test-specific overrides.
    
    This replaces the hardcoded test data that was embedded in production extractors.
    """
    if not test_mode:
        return base_data
    
    test_data = base_data.copy()
    
    # Add test-specific overrides
    test_data.update(get_test_expert_assignment())
    test_data.update(get_test_account_data())
    
    # Override recipients if empty
    if not test_data.get("recipient_emails"):
        test_data["recipient_emails"] = get_test_recipients()
    
    # Add test environment info
    test_data["environment"] = "test;test_mode=True;type=test_scenario_data;version=1.0.0"
    
    # Add test mode metadata
    test_data["test_mode"] = True
    test_data["test_mode_type"] = TestModeType.FULL_TEST
    test_data["test_email_substitutions"] = get_test_substitutions()
    
    return test_data


def is_test_environment() -> bool:
    """Check if running in test environment."""
    import os
    return os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("TEST_MODE", "false").lower() == "true"


def get_clean_production_recipients() -> List[str]:
    """
    Get clean production-appropriate recipients without hardcoded test data.
    This replaces hardcoded demo emails in production extractors.
    """
    return ["support@company.com"]  # Generic support email


def get_clean_production_defaults() -> Dict[str, Any]:
    """
    Get clean production defaults without hardcoded test data.
    This replaces hardcoded demo data in production extractors.
    """
    return {
        "expert_assigned": None,  # Should be determined by business logic
        "expert_email": None,     # Should be determined by assignment logic
        "expert_id": None,        # Should be determined by assignment logic  
        "account_name": None,     # Should be extracted from actual data
        "case_subject": None,     # Should be generated from actual customer data
        "sf_contact_id": None,  # Should be looked up
        "sf_account_id": None,  # Should be looked up
    }


class TestScenarioRecordBuilder:
    """Builder for test scenario records that keeps test logic separate from production."""
    
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.test_data = TEST_DATA
    
    def build_test_record(self, base_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a complete test record with test-specific data."""
        if not self.test_mode:
            return base_data
        
        return create_test_record_data(base_data, test_mode=True)
    
    def get_test_processing_time(self) -> int:
        """Get test processing time with realistic variance."""
        import random
        base_time = 25000  # 25 seconds base
        variance = random.randint(-5000, 8000)  # ±5-8 seconds variance
        return max(10000, base_time + variance)  # Min 10 seconds
    
    def get_test_scenario_time(self) -> int:
        """Get test scenario processing time with realistic variance."""
        import random
        base_time = 15000  # 15 seconds base
        variance = random.randint(-3000, 5000)  # ±3-5 seconds variance
        return max(8000, base_time + variance)  # Min 8 seconds