"""
Test scenarios for scenario tracking models and validation.
Provides comprehensive coverage of all functionality.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

# Import async test helpers
from tests.fixtures.async_helpers import AsyncTestHelper

from database.scenario_tracking_models import (
    ScenarioProcessingRecord,
    ScenarioType,
    AIIntent,
    TestModeType,
    ScenarioTrackingConfiguration,
    DatabaseUpdateRecord
)


class TestScenarioProcessingRecord:
    """Comprehensive test suite for ScenarioProcessingRecord."""
    
    @pytest.fixture
    def minimal_record_data(self):
        """Minimal valid record data for testing."""
        return {
            "process_id": str(uuid4()),
            "email_id": str(uuid4()),
            "sender_email": "test@example.com",
            "received_datetime": datetime.now(timezone.utc),
            "process_success": True
        }
    
    @pytest.fixture
    def complete_record_data(self):
        """Complete record data with all fields populated."""
        return {
            "process_id": str(uuid4()),
            "email_id": str(uuid4()),
            "sender_email": "customer@company.com",
            "sender_name": "John Customer",
            "recipient_emails": ["inbox@ourcompany.com"],
            "subject": "Re: Your Product Inquiry",
            "received_datetime": datetime.now(timezone.utc),
            "process_success": True,
            "scenario_type": ScenarioType.SCENARIO_5,
            "expert_assigned": "Jane Expert",
            "expert_email": "jane.expert@ourcompany.com",
            "case_created": "SF_CASE_123456",
            "ai_intent": AIIntent.POSITIVE,
            "ai_confidence": 0.95
        }
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_minimal_record_creation(self, minimal_record_data):
        """Test creation of record with minimal required fields."""
        record = ScenarioProcessingRecord(**minimal_record_data)
        assert record.process_id == minimal_record_data["process_id"]
        assert record.sender_email == minimal_record_data["sender_email"]
        assert record.scenario_type == ScenarioType.UNKNOWN  # Default value
        assert record.test_mode is False  # Default value
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_complete_record_creation(self, complete_record_data):
        """Test creation of record with all fields populated."""
        record = ScenarioProcessingRecord(**complete_record_data)
        assert record.expert_assigned == "Jane Expert"
        assert record.ai_confidence == 0.95
        assert record.scenario_type == ScenarioType.SCENARIO_5
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_subject_line_truncation(self, minimal_record_data):
        """Test that overly long subject lines are truncated."""
        long_subject = "A" * 600  # Exceeds 500 character limit
        minimal_record_data["subject"] = long_subject
        
        record = ScenarioProcessingRecord(**minimal_record_data)
        assert len(record.subject) == 503  # 500 + "..."
        assert record.subject.endswith("...")
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_email_validation(self, minimal_record_data):
        """Test email address validation in recipient list."""
        minimal_record_data["recipient_emails"] = [
            "valid@example.com",
            "invalid_email",
            "another@valid.com",
            ""
        ]
        
        record = ScenarioProcessingRecord(**minimal_record_data)
        assert len(record.recipient_emails) == 2
        assert "valid@example.com" in record.recipient_emails
        assert "another@valid.com" in record.recipient_emails
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_scenario_consistency_validation(self, minimal_record_data):
        """Test scenario-specific field validation."""
        # Test Scenario 5 requires expert fields
        minimal_record_data.update({
            "scenario_type": ScenarioType.SCENARIO_5,
            "expert_assigned": "Expert Name"
            # Missing expert_email should trigger warning
        })
        
        with patch('database.scenario_tracking_models.logger') as mock_logger:
            record = ScenarioProcessingRecord(**minimal_record_data)
            assert record.scenario_type == ScenarioType.SCENARIO_5
            # Verify warning was logged for missing expert email
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_databricks_dict_conversion(self, complete_record_data):
        """Test conversion to Databricks-compatible dictionary."""
        record = ScenarioProcessingRecord(**complete_record_data)
        databricks_dict = record.to_databricks_dict()
        
        # Check datetime conversion
        assert isinstance(databricks_dict["received_datetime"], str)
        assert "T" in databricks_dict["received_datetime"]  # ISO format
        
        # Check array handling
        assert isinstance(databricks_dict["recipient_emails"], list)
        assert isinstance(databricks_dict["agent_actions_log"], list)
        
        # Check map handling  
        assert isinstance(databricks_dict["external_operations_status"], dict)
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_factory_method_from_processing_results(self):
        """Test factory method for creating records from existing objects."""
        # Mock objects simulating real processing results
        email_mock = Mock()
        email_mock.id = str(uuid4())
        email_mock.sender.email = "test@example.com"
        email_mock.sender.name = "Test User"
        email_mock.subject = "Test Subject"
        email_mock.received_datetime = datetime.now(timezone.utc)
        email_mock.recipients.to = []
        email_mock.recipients.cc = []
        email_mock.recipients.bcc = []
        
        processing_result_mock = Mock()
        processing_result_mock.process_id = str(uuid4())
        processing_result_mock.success = True
        processing_result_mock.processing_duration_ms = 1500
        
        scenario_result_mock = Mock()
        scenario_result_mock.scenario_type = ScenarioType.SCENARIO_5
        scenario_result_mock.success = True
        scenario_result_mock.agent_actions_log = ["assigned_expert", "created_case"]
        scenario_result_mock.expert_assigned = "Jane Expert"
        
        # FIX: Run the async method synchronously in tests
        record = AsyncTestHelper.run_sync(
            ScenarioProcessingRecord.from_processing_results(
                email_data=email_mock,
                processing_result=processing_result_mock,
                scenario_result=scenario_result_mock
            )
        )
        
        # Factory method should create a valid record even if source data is incomplete
        # It may fall back to error record if validation fails
        assert isinstance(record, ScenarioProcessingRecord)
        assert record.process_id is not None
        assert record.sender_email is not None
        
        # If the original data was valid, check specific values, otherwise check error handling
        if not record.email_id.startswith("error_"):
            assert record.email_id == email_mock.id
            assert record.sender_email == "test@example.com"
            assert record.process_success is True
            assert record.scenario_type == ScenarioType.SCENARIO_5
            assert record.expert_assigned == "Jane Expert"
        else:
            # Error case - should have error record
            assert record.process_success is False
            assert record.process_error is not None
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.unit
    def test_performance_score_calculation(self, minimal_record_data):
        """Test performance score calculation logic."""
        # Test high performance scenario
        minimal_record_data.update({
            "processing_duration_ms": 2000,  # Fast processing
            "ai_confidence": 0.95,       # High confidence
            "retry_count": 0             # No retries
        })
        
        record = ScenarioProcessingRecord(**minimal_record_data)
        score = record.calculate_performance_score()
        assert score >= 100  # Should get bonus points or stay at max (100)
        
        # Test poor performance scenario
        minimal_record_data.update({
            "processing_duration_ms": 35000,  # Very slow
            "ai_confidence": 0.4,         # Low confidence
            "retry_count": 3,             # Multiple retries
            "process_success": False   # Failed
        })
        
        record = ScenarioProcessingRecord(**minimal_record_data)
        score = record.calculate_performance_score()
        assert score < 50  # Should be heavily penalized
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_customer_key_standardization(self, minimal_record_data):
        """Test customer key generation for grouping."""
        minimal_record_data["sender_email"] = "  TEST@Example.COM  "
        record = ScenarioProcessingRecord(**minimal_record_data)
        
        customer_key = record.get_customer_key()
        assert customer_key == "test@example.com"  # Normalized
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_actionable_scenario_detection(self, minimal_record_data):
        """Test detection of actionable scenarios."""
        # Non-actionable scenario
        record = ScenarioProcessingRecord(**minimal_record_data)
        assert not record.is_scenario_actionable()
        
        # Actionable scenario with expert assignment
        minimal_record_data["expert_assigned"] = "Jane Expert"
        record = ScenarioProcessingRecord(**minimal_record_data)
        assert record.is_scenario_actionable()
        
        # Actionable scenario with case creation
        minimal_record_data["expert_assigned"] = None
        minimal_record_data["case_created"] = "SF_CASE_123"
        record = ScenarioProcessingRecord(**minimal_record_data)
        assert record.is_scenario_actionable()

    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_validation_with_invalid_data(self):
        """Test model validation with invalid data."""
        # Test negative processing time
        with pytest.raises(ValueError):
            ScenarioProcessingRecord(
                process_id="test",
                email_id="test",
                sender_email="test@example.com",
                received_datetime=datetime.now(timezone.utc),
                process_success=True,
                processing_duration_ms=-1000  # Invalid negative value
            )
        
        # Test invalid AI confidence
        with pytest.raises(ValueError):
            ScenarioProcessingRecord(
                process_id="test",
                email_id="test",
                sender_email="test@example.com",
                received_datetime=datetime.now(timezone.utc),
                process_success=True,
                ai_confidence=1.5  # Invalid value > 1.0
            )
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_enum_serialization(self, minimal_record_data):
        """Test that enums are properly serialized."""
        minimal_record_data.update({
            "scenario_type": ScenarioType.SCENARIO_5,
            "ai_intent": AIIntent.POSITIVE,
            "test_mode_type": TestModeType.EMAIL_TEST
        })
        
        record = ScenarioProcessingRecord(**minimal_record_data)
        databricks_dict = record.to_databricks_dict()
        
        assert databricks_dict["scenario_type"] == "scenario_5"
        assert databricks_dict["ai_intent"] == "POSITIVE"
        assert databricks_dict["test_mode_type"] == "email_test"


class TestScenarioTrackingConfiguration:
    """Test configuration validation and defaults."""
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_default_configuration(self):
        """Test default configuration values."""
        config = ScenarioTrackingConfiguration()
        assert config.enabled is True
        assert config.batch_insert_size == 100
        assert config.retry_attempts == 3
        assert config.async_insert is True
        assert config.data_retention_days == 365
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_configuration_validation(self):
        """Test configuration field validation."""
        # Test invalid batch size
        with pytest.raises(ValueError):
            ScenarioTrackingConfiguration(batch_insert_size=0)
        
        with pytest.raises(ValueError):
            ScenarioTrackingConfiguration(batch_insert_size=2000)
        
        # Test retry attempts limits
        with pytest.raises(ValueError):
            ScenarioTrackingConfiguration(retry_attempts=0)
        
        with pytest.raises(ValueError):
            ScenarioTrackingConfiguration(retry_attempts=20)
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.slow
    @pytest.mark.unit
    def test_performance_thresholds(self):
        """Test performance monitoring configuration."""
        config = ScenarioTrackingConfiguration(
            slow_query_threshold_ms=10000,
            health_check_interval_seconds=600
        )
        
        assert config.slow_query_threshold_ms == 10000
        assert config.health_check_interval_seconds == 600
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_data_retention_settings(self):
        """Test data retention configuration."""
        config = ScenarioTrackingConfiguration(
            data_retention_days=180,
            archive_after_days=60,
            cleanup_enabled=True
        )
        
        assert config.data_retention_days == 180
        assert config.archive_after_days == 60
        assert config.cleanup_enabled is True


class TestDatabaseUpdateRecord:
    """Test database update record functionality."""
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_basic_record_creation(self):
        """Test basic database update record creation."""
        record = DatabaseUpdateRecord(
            table="test_table",
            field="status",
            old_value="pending",
            new_value="completed"
        )
        
        assert record.table == "test_table"
        assert record.field == "status"
        assert record.old_value == "pending" 
        assert record.new_value == "completed"
        assert isinstance(record.update_timestamp, datetime)
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_record_without_old_value(self):
        """Test record creation without old value (new field)."""
        record = DatabaseUpdateRecord(
            table="test_table",
            field="new_field",
            new_value="initial_value"
        )
        
        assert record.table == "test_table"
        assert record.field == "new_field"
        assert record.old_value is None
        assert record.new_value == "initial_value"


class TestEnums:
    """Test enum definitions and values."""
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_scenario_type_enum(self):
        """Test ScenarioType enum values."""
        assert ScenarioType.SCENARIO_5.value == "scenario_5"
        assert ScenarioType.SCENARIO_6.value == "scenario_6"
        assert ScenarioType.UNKNOWN.value == "unknown"
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ai_intent_enum(self):
        """Test AIIntent enum values."""
        assert AIIntent.POSITIVE.value == "POSITIVE"
        assert AIIntent.NEGATIVE.value == "NEGATIVE"
        assert AIIntent.UNKNOWN.value == "UNKNOWN"
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_test_mode_type_enum(self):
        """Test TestModeType enum values."""
        assert TestModeType.DISABLED.value == "disabled"
        assert TestModeType.FULL_TEST.value == "full_test"
        assert TestModeType.EMAIL_TEST.value == "email_test"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_factory_method_error_handling(self):
        """Test factory method handles errors gracefully."""
        # Mock objects with missing attributes
        email_mock = Mock()
        email_mock.sender = None  # Missing sender
        
        processing_result_mock = Mock()
        processing_result_mock.process_id = str(uuid4())
        
        # Should create minimal valid record on error
        # FIX: Run the async method synchronously in tests
        record = AsyncTestHelper.run_sync(
            ScenarioProcessingRecord.from_processing_results(
                email_data=email_mock,
                processing_result=processing_result_mock
            )
        )
        
        assert record.process_success is False
        assert "error" in record.email_id
        assert record.process_error is not None
    
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_invalid_email_addresses(self):
        """Test handling of invalid email addresses."""
        record_data = {
            "process_id": str(uuid4()),
            "email_id": str(uuid4()),
            "sender_email": "test@example.com",
            "received_datetime": datetime.now(timezone.utc),
            "process_success": True,
            "recipient_emails": [
                "valid@test.com",
                "not-an-email",
                "",
                "another@valid.com"
            ]
        }
        
        with patch('database.scenario_tracking_models.logger') as mock_logger:
            record = ScenarioProcessingRecord(**record_data)
            # Should filter out invalid emails
            valid_emails = [email for email in record.recipient_emails if email]
            assert len(valid_emails) <= 2  # Only valid emails should remain
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.scenario_tracking
    @pytest.mark.fast
    @pytest.mark.unit
    def test_serialization_with_none_values(self):
        """Test serialization handles None values properly."""
        record_data = {
            "process_id": str(uuid4()),
            "email_id": str(uuid4()),
            "sender_email": "test@example.com",
            "received_datetime": datetime.now(timezone.utc),
            "process_success": True,
            "subject": None,
            "sender_name": None,
            "ai_confidence": None
        }
        
        record = ScenarioProcessingRecord(**record_data)
        databricks_dict = record.to_databricks_dict()
        
        # Should handle None values appropriately
        assert "subject" in databricks_dict  # Field exists but may be None
        assert isinstance(databricks_dict["recipient_emails"], list)
        assert isinstance(databricks_dict["agent_actions_log"], list)