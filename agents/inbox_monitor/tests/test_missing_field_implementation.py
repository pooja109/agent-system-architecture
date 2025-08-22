"""
Test Missing Field Implementation
=================================

Comprehensive tests for the 7 critical missing field implementations:
1. ai_model_version & ai_*_tokens (AI metadata extraction)
2. customer_id & customer_organization (Customer identification)
3. attachment_count & email_thread_id (Email metadata extraction)  
4. processing_node (System metadata extraction)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from utils.ai_metadata_extractor import (
    extract_ai_metadata,
    extract_model_version_from_intent
)
from utils.customer_identification import (
    extract_customer_metadata,
    generate_customer_id,
    extract_organization_from_email
)
from utils.system_metadata import (
    extract_system_metadata,
    get_processing_node_id
)
from utils.email_metadata_extractor import (
    extract_email_metadata,
    count_email_attachments,
    extract_thread_id
)


class TestAIMetadataExtraction:
    """Test AI model version and token usage extraction."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_model_version_from_intent_response(self):
        """Test model version extraction from intent result."""
        intent_result = Mock()
        intent_result.response_metadata = Mock()
        intent_result.response_metadata.model = "gpt-4-turbo-2024-04"
        
        version = extract_model_version_from_intent(intent_result)
        
        assert version == "gpt-4-turbo-2024-04"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_ai_model_version_from_intent(self):
        """Test ai_model_version extraction from intent result."""
        intent_result = Mock()
        intent_result.model = "gpt-4o-2024-08-06"
        
        processing_result = None
        
        metadata = extract_ai_metadata(intent_result, processing_result)
        
        assert metadata['ai_model_version'] == "gpt-4o-2024-08-06"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_ai_model_version_from_processing(self):
        """Test ai_model_version extraction from processing result."""
        intent_result = None
        
        processing_result = Mock()
        processing_result.model = "gpt-4-turbo"
        
        metadata = extract_ai_metadata(intent_result, processing_result)
        
        assert metadata['ai_model_version'] == "gpt-4-turbo"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_ai_metadata_fallback_when_no_model_data(self):
        """Test fallback behavior when no model data available."""
        intent_result = Mock()
        processing_result = Mock()
        
        # No model attributes - will return None
        metadata = extract_ai_metadata(intent_result, processing_result)
        
        assert metadata['ai_model_version'] is None


class TestCustomerIdentification:
    """Test customer ID generation and organization extraction."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_generate_consistent_customer_id(self):
        """Test that same email always generates same customer ID."""
        email = "john.smith@company.com"
        
        id1 = generate_customer_id(email)
        id2 = generate_customer_id(email)
        
        assert id1 == id2
        assert "company_com" in id1
        assert len(id1) <= 50
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_generate_different_ids_for_different_emails(self):
        """Test that different emails generate different customer IDs."""
        email1 = "john@company.com"
        email2 = "jane@company.com"
        
        id1 = generate_customer_id(email1)
        id2 = generate_customer_id(email2)
        
        assert id1 != id2
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_organization_from_business_email(self):
        """Test organization extraction from business email domain."""
        email = "employee@acmecorp.com"
        
        org = extract_organization_from_email(email)
        
        assert org == "Acmecorp"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_detect_personal_email_provider(self):
        """Test detection of personal email providers."""
        email = "user@gmail.com"
        
        org = extract_organization_from_email(email)
        
        assert "Personal Email" in org
        assert "Gmail" in org
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_customer_metadata_complete(self):
        """Test complete customer metadata extraction."""
        email_data = Mock()
        sender = Mock()
        sender.email_address = "alice@businesscorp.com"
        email_data.sender = sender
        
        metadata = extract_customer_metadata(email_data)
        
        assert metadata['customer_id'] is not None
        assert "businesscorp_com" in metadata['customer_id']
        assert metadata['customer_organization'] == "Businesscorp"


class TestSystemMetadata:
    """Test system metadata and processing node extraction."""
    
    @patch('utils.system_metadata.socket.gethostname')
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_processing_node_id_with_hostname(self, mock_hostname):
        """Test processing node ID generation with hostname."""
        mock_hostname.return_value = "worker-node-01"
        
        # Clear the LRU cache to ensure mock is used
        get_processing_node_id.cache_clear()
        
        with patch('utils.system_metadata.get_container_id', return_value=None):
            with patch('utils.system_metadata.get_cloud_instance_id', return_value=None):
                node_id = get_processing_node_id()
        
        assert node_id.startswith("worker-node-01-pid")
    
    @patch('utils.system_metadata.socket.gethostname')
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_processing_node_id_with_container(self, mock_hostname):
        """Test processing node ID generation in container environment."""
        mock_hostname.return_value = "container-host"
        
        # Clear the LRU cache to ensure mock is used
        get_processing_node_id.cache_clear()
        
        with patch('utils.system_metadata.get_container_id', return_value='abcd1234567890abcdef'):
            node_id = get_processing_node_id()
        
        assert node_id == "container-host-abcd12345678"  # First 12 chars (16 - 4 = 12)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_system_metadata_complete(self):
        """Test complete system metadata extraction."""
        with patch('utils.system_metadata.get_processing_node_id', return_value='test-node-123'):
            metadata = extract_system_metadata()
        
        assert metadata['processing_node'] == 'test-node-123'
        assert 'system_info' in metadata
        assert isinstance(metadata['system_info'], dict)


class TestEmailMetadata:
    """Test email attachment and thread ID extraction."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_count_attachments_from_list(self):
        """Test attachment counting from attachments list."""
        email_data = Mock()
        email_data.attachments = ['file1.pdf', 'file2.docx', 'image.png']
        
        count = count_email_attachments(email_data)
        
        assert count == 3
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_count_attachments_from_boolean(self):
        """Test attachment counting from has_attachments boolean."""
        email_data = Mock()
        email_data.has_attachments = True
        email_data.attachments = None  # List not available
        
        count = count_email_attachments(email_data)
        
        assert count == 1
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_no_attachments(self):
        """Test handling of emails with no attachments."""
        email_data = Mock()
        email_data.attachments = []
        
        count = count_email_attachments(email_data)
        
        assert count == 0
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_thread_id_from_conversation_id(self):
        """Test thread ID extraction from conversation ID."""
        email_data = Mock()
        email_data.conversationId = "AAQkADAwATM0MDAAMS1iOTYwLWI2NjEtMDA"
        
        thread_id = extract_thread_id(email_data)
        
        assert thread_id == "AAQkADAwATM0MDAAMS1iOTYwLWI2NjEtMDA"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_thread_id_from_headers(self):
        """Test thread ID extraction from email headers."""
        email_data = Mock()
        email_data.conversationId = None
        email_data.headers = {
            'Thread-Index': 'AQHWyxYGvYzF8mGKdUGAs5K4WgAA'
        }
        
        thread_id = extract_thread_id(email_data)
        
        assert thread_id == 'AQHWyxYGvYzF8mGKdUGAs5K4WgAA'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extract_email_metadata_complete(self):
        """Test complete email metadata extraction."""
        email_data = Mock()
        email_data.attachments = ['doc1.pdf', 'doc2.xlsx']
        email_data.conversationId = "thread-12345"
        
        metadata = extract_email_metadata(email_data)
        
        assert metadata['attachment_count'] == 2
        assert metadata['email_thread_id'] == "thread-12345"


class TestIntegrationScenarios:
    """Test integration scenarios and error handling."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_partial_data_availability(self):
        """Test handling when only some data sources are available."""
        # AI metadata available, but customer data missing
        intent_result = Mock()
        intent_result.usage = Mock()
        intent_result.usage.total_tokens = 100
        
        email_data = None  # Missing
        
        ai_metadata = extract_ai_metadata(intent_result, None)
        customer_metadata = extract_customer_metadata(email_data)
        
        assert ai_metadata['ai_total_tokens'] == 100
        assert customer_metadata['customer_id'] is None
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_error_handling_in_extraction(self):
        """Test error handling when extraction functions fail."""
        # Malformed data that causes extraction errors
        intent_result = Mock()
        intent_result.usage = Mock()
        intent_result.usage.prompt_tokens = "invalid"  # Wrong type
        
        # Should handle gracefully and return defaults
        ai_metadata = extract_ai_metadata(intent_result, None)
        
        assert ai_metadata['ai_prompt_tokens'] == 0
        assert ai_metadata['ai_completion_tokens'] == 0
        assert ai_metadata['ai_total_tokens'] == 0

    @pytest.mark.medium
    @pytest.mark.integration
    def test_factory_method_integration(self):
        """Test that factory method integrates all missing field extractors."""
        from database.scenario_tracking_models import ScenarioProcessingRecord
        
        # Create mock data
        email_data = Mock()
        email_data.sender = Mock()
        email_data.sender.email_address = "test@company.com"
        email_data.attachments = ['file1.pdf']
        email_data.conversationId = "thread-123"
        
        intent_result = Mock()
        intent_result.usage = Mock()
        intent_result.usage.prompt_tokens = 100
        intent_result.usage.completion_tokens = 50
        intent_result.usage.total_tokens = 150
        intent_result.response_metadata = Mock()
        intent_result.response_metadata.model = "gpt-4-test"
        
        processing_result = Mock()
        processing_result.process_id = "test-id"
        processing_result.success = True
        processing_result.processing_duration_ms = 5000
        
        # Create record using factory method
        with patch('utils.system_metadata.get_processing_node_id', return_value='test-node'):
            record = ScenarioProcessingRecord.from_processing_results(
                email_data=email_data,
                processing_result=processing_result,
                intent_result=intent_result
            )
        
        # Verify missing critical fields are populated
        assert record.customer_id is not None
        assert "company_com" in record.customer_id
        assert record.customer_organization == "Company"
        assert record.ai_model_version == "gpt-4-test"
        assert record.ai_prompt_tokens == 100
        assert record.ai_completion_tokens == 50
        assert record.attachment_count == 1
        assert record.email_thread_id == "thread-123"
        assert record.processing_node == "test-node"


class TestDataQualityValidation:
    """Test data quality and consistency of extracted fields."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_customer_id_consistency(self):
        """Test customer ID generation is deterministic."""
        email = "test@example.com"
        
        # Generate ID multiple times
        ids = [generate_customer_id(email) for _ in range(10)]
        
        # All IDs should be identical
        assert len(set(ids)) == 1
        assert all(id == ids[0] for id in ids)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_customer_id_uniqueness(self):
        """Test different emails generate different customer IDs."""
        emails = [
            "alice@company.com",
            "bob@company.com", 
            "charlie@othercorp.com"
        ]
        
        ids = [generate_customer_id(email) for email in emails]
        
        # All IDs should be different
        assert len(set(ids)) == len(ids)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_field_data_types(self):
        """Test extracted fields match expected data types."""
        # Test AI metadata
        intent_result = Mock()
        intent_result.usage = Mock()
        intent_result.usage.prompt_tokens = 100
        intent_result.usage.completion_tokens = 50
        
        ai_metadata = extract_ai_metadata(intent_result, None)
        
        assert isinstance(ai_metadata['ai_prompt_tokens'], int)
        assert isinstance(ai_metadata['ai_completion_tokens'], int)
        assert isinstance(ai_metadata['ai_total_tokens'], int)
        
        # Test customer metadata
        email_data = Mock()
        email_data.sender = Mock()
        email_data.sender.email_address = "test@company.com"
        
        customer_metadata = extract_customer_metadata(email_data)
        
        assert isinstance(customer_metadata['customer_id'], str)
        assert isinstance(customer_metadata['customer_organization'], str)
        
        # Test system metadata
        with patch('utils.system_metadata.get_processing_node_id', return_value='node-123'):
            system_metadata = extract_system_metadata()
        
        assert isinstance(system_metadata['processing_node'], str)
        
        # Test email metadata  
        email_data = Mock()
        email_data.attachments = ['file.pdf']
        email_data.conversationId = "thread-456"
        
        email_metadata = extract_email_metadata(email_data)
        
        assert isinstance(email_metadata['attachment_count'], int)
        assert isinstance(email_metadata['email_thread_id'], str)


class TestIntegrationResilience:
    """Test integration resilience and Mock object handling (Audit Issue Fix)."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_mock_object_detection(self):
        """Test Mock object detection function."""
        from database.scenario_tracking_models import is_mock_object
        
        # Test Mock objects are detected
        mock_obj = Mock()
        magic_mock_obj = MagicMock()
        
        assert is_mock_object(mock_obj) == True
        assert is_mock_object(magic_mock_obj) == True
        
        # Test regular objects are not detected as mocks
        assert is_mock_object("string") == False
        assert is_mock_object(123) == False
        assert is_mock_object(None) == False
        assert is_mock_object([1, 2, 3]) == False
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_factory_method_with_mock_objects(self):
        """Test factory method handles Mock objects gracefully."""
        from database.scenario_tracking_models import ScenarioProcessingRecord
        
        # Create data with Mock objects (simulating test environment leakage)
        email_data = Mock()
        email_data.sender = Mock() 
        email_data.sender.email_address = "test@company.com"
        email_data.attachments = Mock()  # This will cause issues in original code
        email_data.conversationId = "thread-123"
        
        intent_result = Mock()
        intent_result.usage = Mock()
        # Mock object in numeric field - should be filtered out
        intent_result.usage.prompt_tokens = Mock()  
        intent_result.usage.completion_tokens = 50
        intent_result.usage.total_tokens = 150
        
        processing_result = Mock()
        processing_result.process_id = "test-id"
        processing_result.success = True
        processing_result.processing_duration_ms = 5000
        
        # This should NOT fail due to Mock objects
        with patch('utils.system_metadata.get_processing_node_id', return_value='test-node'):
            record = ScenarioProcessingRecord.from_processing_results(
                email_data=email_data,
                processing_result=processing_result,
                intent_result=intent_result
            )
        
        # Record should be created successfully
        assert record is not None
        assert record.process_success == True
        # Email ID comes from processing_result.process_id, which gets mapped to record.process_id
        assert record.process_id == "test-id"
        
        # Fields with Mock values should be filtered out or use defaults, not Mock objects
        # ai_prompt_tokens Mock was filtered out, so field may be None (acceptable)
        assert record.ai_prompt_tokens is None or isinstance(record.ai_prompt_tokens, int)
        assert record.ai_completion_tokens == 50  # Real value preserved
        
        # Most importantly: ensure no Mock objects made it into the final record
        record_dict = record.model_dump()
        for field_name, field_value in record_dict.items():
            if field_value is not None:
                assert not str(field_value).startswith('<Mock'), f"Mock object found in field {field_name}: {field_value}"
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_validation_error_recovery(self):
        """Test validation error recovery mechanism."""
        from database.scenario_tracking_models import ScenarioProcessingRecord
        
        # Create data that will cause validation errors
        email_data = Mock()
        email_data.sender = Mock()
        email_data.sender.email_address = "test@company.com"
        
        processing_result = Mock()
        processing_result.process_id = "test-id"
        processing_result.success = True
        
        # Add invalid field that would cause validation failure
        kwargs = {
            'invalid_field': 'this_should_be_filtered_out',  # Not in model
            'email_importance': 'INVALID_ENUM_VALUE',  # Invalid enum
            'ai_confidence': 1.5,  # Out of range (should be 0.0-1.0)
            'attachment_count': -1,  # Negative value not allowed
        }
        
        # This should handle validation errors gracefully
        record = ScenarioProcessingRecord.from_processing_results(
            email_data=email_data,
            processing_result=processing_result,
            **kwargs
        )
        
        # Record should still be created
        assert record is not None
        assert record.process_success == True
        # Processing ID is correctly set from processing_result
        assert record.process_id == "test-id"
        
        # Processing error should indicate validation recovery
        if record.process_error:
            assert "Validation recovery" in record.process_error
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_minimal_record_creation(self):
        """Test minimal record creation for extreme error cases."""
        from database.scenario_tracking_models import ScenarioProcessingRecord, get_minimal_record_data
        
        # Test get_minimal_record_data helper
        original_data = {
            "process_id": "test-123",
            "email_id": "email-456", 
            "sender_email": "user@test.com",
            "process_success": True,
            "extra_field": "should_be_ignored"
        }
        
        minimal = get_minimal_record_data(original_data, include_error=True, error_msg="Test error")
        
        # Should contain only essential fields
        assert minimal["process_id"] == "test-123"
        assert minimal["email_id"] == "email-456"
        assert minimal["sender_email"] == "user@test.com"
        assert minimal["process_success"] == True
        assert minimal["process_error"] == "Test error"
        assert "extra_field" not in minimal
        
        # Should be able to create valid record from minimal data
        record = ScenarioProcessingRecord(**minimal)
        assert record is not None


class TestPerformanceValidation:
    """Test performance characteristics of field extraction."""
    
    @pytest.mark.fast
    @pytest.mark.performance
    def test_extraction_performance(self):
        """Test field extraction completes within reasonable time."""
        import time
        
        # Create test data
        email_data = Mock()
        email_data.sender = Mock()
        email_data.sender.email_address = "performance@test.com"
        email_data.attachments = ['file1.pdf', 'file2.docx']
        email_data.conversationId = "perf-thread-123"
        
        intent_result = Mock()
        intent_result.usage = Mock()
        intent_result.usage.prompt_tokens = 200
        intent_result.usage.completion_tokens = 100
        intent_result.usage.total_tokens = 300
        
        # Measure extraction time
        start_time = time.time()
        
        ai_metadata = extract_ai_metadata(intent_result, None)
        customer_metadata = extract_customer_metadata(email_data)
        system_metadata = extract_system_metadata()
        email_metadata = extract_email_metadata(email_data)
        
        end_time = time.time()
        extraction_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within 50ms as per requirements
        assert extraction_time < 50, f"Extraction took {extraction_time}ms, exceeds 50ms limit"
        
        # Verify extraction worked
        assert ai_metadata['ai_total_tokens'] == 300
        assert customer_metadata['customer_id'] is not None
        assert system_metadata['processing_node'] is not None
        assert email_metadata['attachment_count'] == 2
    
    @pytest.mark.fast
    @pytest.mark.performance
    def test_system_metadata_caching_performance(self):
        """Test system metadata LRU caching improves performance."""
        import time
        
        # First call (should be slower due to actual system calls)
        start_time = time.time()
        metadata1 = extract_system_metadata()
        first_call_time = (time.time() - start_time) * 1000
        
        # Second call (should be much faster due to caching)
        start_time = time.time()
        metadata2 = extract_system_metadata()
        second_call_time = (time.time() - start_time) * 1000
        
        # Cached results should be identical
        assert metadata1['processing_node'] == metadata2['processing_node']
        
        # Second call should be significantly faster (cached)
        # Allow for some variation but expect substantial improvement
        assert second_call_time < first_call_time / 2, f"Caching not effective: first={first_call_time}ms, second={second_call_time}ms"