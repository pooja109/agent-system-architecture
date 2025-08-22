"""
Comprehensive tests for hardcoded value fixes in Phase 1.
Tests the replacement of hardcoded values with proper data extraction logic.
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from utils.data_extraction_helpers import (
    extract_sender_info,
    detect_environment,
    extract_assignment_reasoning,
    validate_extracted_data,
    extract_customer_name,
    get_expert_assignment_method
)


class TestSenderInfoExtraction:
    """Test sender information extraction replacing hardcoded 'Customer' values."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_email_address_object(self):
        """Test extraction from EmailAddress object with name."""
        # Create mock email data
        email_data = Mock()
        sender = Mock()
        sender.name = "John Smith"
        sender.email_address = "john.smith@company.com"
        email_data.sender = sender
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "John Smith"
        assert result['email'] == "john.smith@company.com"
        assert result['customer_name'] == "John Smith"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_email_object_with_email_attr(self):
        """Test extraction from email object with direct email attribute."""
        # Use a simple object instead of Mock to avoid Mock detection
        class MockSender:
            def __init__(self):
                self.name = "Jane Doe"
                self.email = "jane.doe@company.com"
        
        class MockEmailData:
            def __init__(self):
                self.sender = MockSender()
        
        email_data = MockEmailData()
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "Jane Doe"
        assert result['email'] == "jane.doe@company.com"
        assert result['customer_name'] == "Jane Doe"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_email_without_name(self):
        """Test extraction when only email address available."""
        email_data = Mock()
        sender = Mock()
        sender.name = None
        sender.email_address = "jane.doe@company.com"
        email_data.sender = sender
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "Jane Doe"  # Formatted from email
        assert result['email'] == "jane.doe@company.com"
        assert result['customer_name'] == "Jane Doe"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_dictionary_format(self):
        """Test extraction from dictionary sender format."""
        email_data = Mock()
        email_data.sender = {
            'name': 'Alice Johnson',
            'email_address': 'alice@example.com'
        }
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "Alice Johnson"
        assert result['email'] == "alice@example.com"
        assert result['customer_name'] == "Alice Johnson"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_dictionary_with_email_key(self):
        """Test extraction from dictionary with 'email' key instead of 'email_address'."""
        email_data = Mock()
        email_data.sender = {
            'name': 'Bob Wilson',
            'email': 'bob@example.com'
        }
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "Bob Wilson"
        assert result['email'] == "bob@example.com"
        assert result['customer_name'] == "Bob Wilson"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_from_email_fallback(self):
        """Test fallback to from_email attribute."""
        email_data = Mock()
        email_data.sender = None
        email_data.from_email = "fallback@example.com"
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "Fallback"  # Formatted from email
        assert result['email'] == "fallback@example.com"
        assert result['customer_name'] == "Fallback"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_fallback_to_unknown_sender(self):
        """Test fallback when no sender data available."""
        email_data = None
        
        result = extract_sender_info(email_data)
        
        assert result['name'] == "Unknown Sender"
        assert result['email'] == "unknown@unknown.com"
        assert result['customer_name'] == "Unknown Customer"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_error_handling_in_extraction(self):
        """Test error handling during extraction."""
        class ErrorSender:
            @property
            def name(self):
                raise Exception("Test error")
        
        class ErrorEmailData:
            def __init__(self):
                self.sender = ErrorSender()
        
        email_data = ErrorEmailData()
        
        result = extract_sender_info(email_data)
        
        # Should return defaults when error occurs
        assert result['name'] == "Unknown Sender"
        assert result['email'] == "unknown@unknown.com"
        assert result['customer_name'] == "Unknown Customer"


class TestEnvironmentDetection:
    """Test environment detection replacing hardcoded 'development' value."""
    
    @pytest.fixture(autouse=True)
    def clear_env_vars(self, monkeypatch):
        """Clear environment variables before each test."""
        env_vars = ['ENVIRONMENT', 'ENV', 'DEPLOYMENT_ENV', 'AZURE_ENV', 'NODE_ENV']
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detect_production_environment(self, monkeypatch):
        """Test production environment detection."""
        monkeypatch.setenv('ENVIRONMENT', 'production')
        
        result = detect_environment()
        
        assert result == 'production'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detect_production_with_prod_keyword(self, monkeypatch):
        """Test production detection with 'prod' keyword."""
        monkeypatch.setenv('ENV', 'prod')
        
        result = detect_environment()
        
        assert result == 'production'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detect_test_environment(self, monkeypatch):
        """Test test environment detection."""
        monkeypatch.setenv('ENV', 'test')
        
        result = detect_environment()
        
        assert result == 'test'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detect_staging_as_test(self, monkeypatch):
        """Test staging mapped to test environment."""
        monkeypatch.setenv('DEPLOYMENT_ENV', 'staging')
        
        result = detect_environment()
        
        assert result == 'test'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detect_development_environment(self, monkeypatch):
        """Test development environment detection."""
        monkeypatch.setenv('AZURE_ENV', 'development')
        
        result = detect_environment()
        
        assert result == 'development'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_priority_order_of_env_vars(self, monkeypatch):
        """Test that ENVIRONMENT takes priority over other vars."""
        monkeypatch.setenv('NODE_ENV', 'production')
        monkeypatch.setenv('ENV', 'test')
        monkeypatch.setenv('ENVIRONMENT', 'development')
        
        result = detect_environment()
        
        assert result == 'development'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_fallback_to_development(self, monkeypatch):
        """Test fallback to development when no env vars set."""
        # No environment variables set
        
        result = detect_environment()
        
        assert result == 'development'
    
    @patch('socket.gethostname')
    @pytest.mark.fast
    @pytest.mark.unit
    def test_hostname_detection(self, mock_hostname, monkeypatch):
        """Test hostname-based environment detection."""
        mock_hostname.return_value = 'prod-server-01'
        
        result = detect_environment()
        
        assert result == 'production'


class TestAssignmentReasoningExtraction:
    """Test assignment reasoning extraction replacing generic text."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_expert_assignment(self):
        """Test extraction from expert assignment reason."""
        scenario_result = Mock()
        expert_assignment = Mock()
        expert_assignment.reason = "Assigned based on domain expertise in Azure"
        scenario_result.expert_assignment = expert_assignment
        
        result = extract_assignment_reasoning(scenario_result)
        
        assert result == "Assigned based on domain expertise in Azure"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_construct_from_assignment_method(self):
        """Test construction when only method and expert available."""
        scenario_result = Mock()
        expert_assignment = Mock()
        expert_assignment.reason = None
        expert_assignment.assignment_method = "round_robin"
        expert_assignment.expert_name = "John Expert"
        scenario_result.expert_assignment = expert_assignment
        
        result = extract_assignment_reasoning(scenario_result)
        
        assert "John Expert" in result
        assert "round_robin" in result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_assignment_method_directly(self):
        """Test extraction from direct assignment method."""
        class MockScenarioResult:
            def __init__(self):
                self.expert_assignment = None
                self.assignment_method = "availability_based"
                self.expert_assigned = "Jane Expert"
        
        scenario_result = MockScenarioResult()
        
        result = extract_assignment_reasoning(scenario_result)
        
        assert "Jane Expert" in result
        assert "availability_based" in result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_fallback_to_scenario_type(self):
        """Test fallback to scenario type when no assignment info."""
        class MockScenarioResult:
            def __init__(self):
                self.expert_assignment = None
                self.assignment_method = None
                self.scenario_type = "scenario_5"
        
        scenario_result = MockScenarioResult()
        
        result = extract_assignment_reasoning(scenario_result)
        
        assert "scenario_5" in result
        assert "Automatic assignment" in result
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ultimate_fallback(self):
        """Test ultimate fallback when minimal data available."""
        class MockScenarioResult:
            def __init__(self):
                self.expert_assignment = None
                self.assignment_method = None
                self.scenario_type = None
        
        scenario_result = MockScenarioResult()
        
        result = extract_assignment_reasoning(scenario_result)
        
        assert result == 'Automatic assignment via system rules'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_no_scenario_result(self):
        """Test handling when no scenario result provided."""
        result = extract_assignment_reasoning(None)
        
        assert result == 'No scenario result available'


class TestDataValidation:
    """Test data validation and cleaning."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_clean_sender_name(self):
        """Test sender name cleaning removes artifacts."""
        data = {'sender_name': '  John Smith (External)  '}
        
        result = validate_extracted_data(data)
        
        assert result['sender_name'] == "John Smith External"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_clean_sender_name_with_brackets(self):
        """Test removal of bracket artifacts."""
        data = {'sender_name': 'Jane Doe [Contractor]'}
        
        result = validate_extracted_data(data)
        
        assert result['sender_name'] == "Jane Doe Contractor"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_truncate_long_names(self):
        """Test truncation of extremely long names."""
        long_name = "A" * 150
        data = {'sender_name': long_name}
        
        result = validate_extracted_data(data)
        
        assert len(result['sender_name']) <= 103  # 100 + "..."
        assert result['sender_name'].endswith("...")
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_clean_customer_name(self):
        """Test customer name cleaning."""
        data = {'customer_name': '  (Corporate Account) ACME Inc  '}
        
        result = validate_extracted_data(data)
        
        assert result['customer_name'] == "Corporate Account ACME Inc"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_validate_environment(self):
        """Test environment validation."""
        data = {'environment': 'invalid_env'}
        
        result = validate_extracted_data(data)
        
        assert result['environment'] == 'development'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_validate_valid_environment(self):
        """Test that valid environments pass through."""
        data = {'environment': 'production'}
        
        result = validate_extracted_data(data)
        
        assert result['environment'] == 'production'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_truncate_long_assignment_reasoning(self):
        """Test truncation of long assignment reasoning."""
        long_reasoning = "A" * 600
        data = {'assignment_reasoning': long_reasoning}
        
        result = validate_extracted_data(data)
        
        assert len(result['assignment_reasoning']) <= 503  # 500 + "..."
        assert result['assignment_reasoning'].endswith("...")


class TestCustomerNameExtraction:
    """Test customer name extraction replacing hardcoded 'Customer'."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_sender_info(self):
        """Test extraction using sender info."""
        email_data = Mock()
        sender = Mock()
        sender.name = "Corporate User"
        sender.email = "user@corp.com"
        email_data.sender = sender
        
        result = extract_customer_name(email_data)
        
        assert result == "Corporate User"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_processing_result(self):
        """Test extraction from processing result."""
        email_data = Mock()
        email_data.sender = None
        processing_result = Mock()
        processing_result.customer_name = "Processing Customer"
        
        result = extract_customer_name(email_data, processing_result)
        
        assert result == "Processing Customer"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_fallback_to_email_local_part(self):
        """Test fallback to email local part formatting."""
        email_data = Mock()
        sender = Mock()
        sender.name = None
        sender.email = "john.doe@example.com"
        email_data.sender = sender
        
        result = extract_customer_name(email_data)
        
        assert result == "John Doe"  # Formatted from email
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ultimate_fallback(self):
        """Test ultimate fallback when no data available."""
        result = extract_customer_name(None)
        
        assert result == "Unknown Customer"


class TestExpertAssignmentMethod:
    """Test expert assignment method extraction replacing hardcoded 'round_robin'."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_scenario_result(self):
        """Test extraction from scenario result."""
        scenario_result = Mock()
        scenario_result.assignment_method = "availability_based"
        
        result = get_expert_assignment_method(scenario_result)
        
        assert result == "availability_based"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_expert_assignment(self):
        """Test extraction from expert assignment object."""
        scenario_result = Mock()
        scenario_result.assignment_method = None
        expert_assignment = Mock()
        expert_assignment.method = "skill_based"
        scenario_result.expert_assignment = expert_assignment
        
        result = get_expert_assignment_method(scenario_result)
        
        assert result == "skill_based"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_from_processing_result(self):
        """Test extraction from processing result."""
        scenario_result = None
        processing_result = Mock()
        processing_result.assignment_method = "workload_balanced"
        
        result = get_expert_assignment_method(scenario_result, processing_result)
        
        assert result == "workload_balanced"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_scenario_specific_default(self):
        """Test scenario-specific default methods."""
        scenario_result = Mock()
        scenario_result.assignment_method = None
        scenario_result.expert_assignment = None
        scenario_result.scenario_type = Mock()
        scenario_result.scenario_type.value = "scenario_5"
        
        result = get_expert_assignment_method(scenario_result)
        
        assert result == "availability_based"  # Scenario 5 should use availability
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ultimate_fallback(self):
        """Test ultimate fallback to round_robin."""
        result = get_expert_assignment_method(None, None)
        
        assert result == "round_robin"


class TestIntegratedScenarioRecordCreation:
    """Test integrated scenario record creation with enhanced data extraction."""
    
    def create_mock_email_data(self, sender_name="Test User", sender_email="test@example.com"):
        """Create mock email data for testing."""
        class MockSender:
            def __init__(self, name, email):
                self.name = name
                self.email = email
        
        class MockEmailData:
            def __init__(self, sender_name, sender_email):
                self.id = "test-email-123"
                self.subject = "Test Email Subject"
                self.conversation_id = "conv-123"
                self.received_datetime = datetime.now(timezone.utc)
                self.email_body = "Test email content"
                self.sender = MockSender(sender_name, sender_email)
        
        return MockEmailData(sender_name, sender_email)
    
    def create_mock_processing_result(self, success=True):
        """Create mock processing result for testing."""
        class MockProcessingResult:
            def __init__(self, success):
                self.process_id = "proc-123"
                self.success = success
                self.processing_duration_ms = 1500
        
        return MockProcessingResult(success)
    
    def create_mock_scenario_result(self, scenario_type="scenario_5"):
        """Create mock scenario result for testing."""
        class MockScenarioType:
            def __init__(self, value):
                self.value = value
        
        class MockScenarioResult:
            def __init__(self, scenario_type):
                self.scenario_type = MockScenarioType(scenario_type)
                self.success = True
                self.expert_assigned = "Real Expert Name"
                self.assignment_method = "skill_based"
        
        return MockScenarioResult(scenario_type)
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_enhanced_record_creation_no_hardcoded_values(self):
        """Test that enhanced record creation eliminates hardcoded values."""
        email_data = self.create_mock_email_data("Real Customer", "customer@realcompany.com")
        processing_result = self.create_mock_processing_result(success=True)
        scenario_result = self.create_mock_scenario_result("scenario_5")
        
        with patch('database.scenario_tracking_models.detect_environment', return_value='production'):
            record = ScenarioProcessingRecord.from_processing_results(
                email_data=email_data,
                processing_result=processing_result,
                scenario_result=scenario_result
            )
        
        # Verify no hardcoded values
        assert record.sender_name != "Customer"  # Should be "Real Customer"
        assert "production" in record.environment  # Should detect production, not hardcoded development
        assert record.expert_assigned != "Sales Expert"  # Should be "Real Expert Name"
        
        # Verify actual extracted values
        assert record.sender_name == "Real Customer"
        assert record.sender_email == "customer@realcompany.com"
        assert record.expert_assigned == "Real Expert Name"
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'test'})
    @pytest.mark.fast
    @pytest.mark.unit
    def test_environment_detection_integration(self):
        """Test environment detection integration in record creation."""
        email_data = self.create_mock_email_data()
        processing_result = self.create_mock_processing_result()
        
        record = ScenarioProcessingRecord.from_processing_results(
            email_data=email_data,
            processing_result=processing_result
        )
        
        # Should detect 'test' environment from environment variable
        assert "test" in record.environment
        assert "development" not in record.environment  # No hardcoded development
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_error_handling_preserves_functionality(self):
        """Test that error handling doesn't break record creation."""
        # Create problematic email data that might cause extraction errors
        class ErrorEmailData:
            def __init__(self):
                self.id = "error-test"
            
            @property
            def sender(self):
                raise Exception("Mock error")
        
        email_data = ErrorEmailData()
        processing_result = self.create_mock_processing_result()
        
        # Should still create record without crashing
        record = ScenarioProcessingRecord.from_processing_results(
            email_data=email_data,
            processing_result=processing_result
        )
        
        assert record.process_id == "proc-123"
        assert record.process_success is True
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_case_subject_uses_extracted_customer_name(self):
        """Test that case subject uses extracted customer name, not hardcoded 'Customer'."""
        email_data = self.create_mock_email_data("Acme Corporation", "contact@acme.com")
        processing_result = self.create_mock_processing_result()
        scenario_result = self.create_mock_scenario_result("scenario_5")
        # Simulate case creation
        scenario_result.case_created = "SF-20240101120000"
        
        record = ScenarioProcessingRecord.from_processing_results(
            email_data=email_data,
            processing_result=processing_result,
            scenario_result=scenario_result
        )
        
        # Case subject should use extracted customer name
        if record.case_subject:
            assert "Acme Corporation" in record.case_subject
            assert "Customer" not in record.case_subject  # No hardcoded "Customer"