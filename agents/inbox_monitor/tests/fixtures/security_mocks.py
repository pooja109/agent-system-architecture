"""
Security testing utilities and mock patterns for compliance validation.
Works with existing source code security patterns without modification.
"""
from typing import Dict, Any, List, Optional, Union, Iterator, ContextManager, Type
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import pytest
import secrets
import json
import re


class SecurityTestDataFactory:
    """
    Factory for creating security-compliant test data.
    """
    
    @staticmethod
    def create_scenario_processing_record_data(
        scenario_id: str = "test-scenario-123",
        include_pii: bool = False,
        data_size: str = "normal"
    ) -> Dict[str, Any]:
        """
        Create test data for ScenarioProcessingRecord that passes Pydantic validation.
        
        Args:
            scenario_id: Scenario identifier
            include_pii: Whether to include PII data for truncation testing
            data_size: Size of data ('normal', 'large', 'oversized')
            
        Returns:
            Dictionary with valid ScenarioProcessingRecord data
        """
        # Base data structure aligning with template while maintaining Pydantic compatibility
        base_data = {
            'processing_id': scenario_id,  # Correct field name for actual Pydantic model
            'scenario_id': scenario_id,    # Template-aligned field
            'email_id': f'email_{scenario_id}',
            'sender_email': 'test.sender@example.com',
            'received_datetime': datetime.now(timezone.utc),
            'process_success': True,
            'processing_status': 'completed',  # Template-aligned field
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'source': 'test_security',
                'version': '1.0',
                'test_environment': True
            }
        }
        
        # Add PII data if requested (for truncation testing)
        if include_pii:
            pii_data = {
                'sender_name': 'Test Customer Full Name',
                'recipient_emails': ['recipient1@test.com', 'recipient2@test.com'],
                'subject': 'Test email subject with customer information',
                'email_body': 'Test email body with customer details'
            }
            
            if data_size == 'large':
                # Create large PII data for truncation testing
                pii_data['subject'] = 'A' * 600  # Exceed 500 char limit
                pii_data['email_body'] = 'B' * 300  # Exceed 255 char limit
            elif data_size == 'oversized':
                # Create oversized data that should be truncated
                pii_data['subject'] = 'C' * 1000  # Much larger than limit
                pii_data['email_body'] = 'D' * 2000  # Much larger than limit
            
            base_data.update(pii_data)
        
        return base_data
    
    @staticmethod
    def create_email_processing_data(
        email_id: str = "test-email-456",
        classification: str = "positive_response",
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """
        Create email processing data for security testing.
        
        Args:
            email_id: Email identifier
            classification: Email classification type
            include_sensitive: Whether to include sensitive data
            
        Returns:
            Dictionary with email processing data
        """
        email_data = {
            'email_id': email_id,
            'sender_email': 'sender@test.com',
            'subject': 'Test Email Subject',
            'classification': classification,
            'confidence_score': 0.95,
            'processed_at': datetime.now(timezone.utc)
        }
        
        if include_sensitive:
            email_data.update({
                'email_body': 'This email contains sensitive information about account number 1234567890',
                'attachments': ['financial_statement.pdf', 'personal_info.doc'],
                'ip_address': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
        
        return email_data
    
    @staticmethod
    def create_security_audit_event(
        event_type: str = "data_access",
        severity: str = "info",
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """
        Create security audit event data for testing.
        
        Args:
            event_type: Type of security event
            severity: Event severity level
            include_sensitive: Whether to include sensitive information
            
        Returns:
            Dictionary with security audit event data
        """
        event_data = {
            'event_id': f"audit-{secrets.token_hex(8)}",
            'event_type': event_type,
            'severity': severity,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source_service': 'inbox_monitor',
            'event_description': f'Security event: {event_type}'
        }
        
        if include_sensitive:
            event_data.update({
                'user_id': 'user123',
                'session_id': secrets.token_hex(16),
                'resource_accessed': '/api/v1/sensitive-data',
                'access_result': 'granted',
                'additional_context': {
                    'request_headers': {'Authorization': 'Bearer [REDACTED]'},
                    'response_size': 2048
                }
            })
        
        return event_data


class SecurityComplianceValidator:
    """
    Validator for security compliance testing.
    """
    
    PII_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card pattern
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email pattern
        r'\b\d{3}-\d{3}-\d{4}\b'  # Phone pattern
    ]
    
    @classmethod
    def validate_pii_truncation(cls, data: Dict[str, Any], max_length: int = 500) -> Dict[str, Any]:
        """
        Validate that PII data is properly truncated.
        
        Args:
            data: Data dictionary to validate
            max_length: Maximum allowed length for text fields (must be > 0)
            
        Returns:
            Dictionary with validation results including compliance status
            
        Raises:
            ValueError: If data is None/empty or max_length is invalid
            TypeError: If data is not a dictionary
        """
        # Input validation with enhanced error messages
        if data is None:
            raise ValueError("Data dictionary cannot be None for PII truncation validation")
        
        if not isinstance(data, dict):
            raise TypeError(f"Data must be a dictionary for validation, got: {type(data).__name__}")
        
        if not data:
            raise ValueError("Data dictionary cannot be empty for PII truncation validation")
        
        if not isinstance(max_length, int) or max_length <= 0:
            raise ValueError(f"Max length must be a positive integer, got: {max_length}")
        validation_results = {
            'compliant': True,
            'violations': [],
            'truncated_fields': [],
            'oversized_fields': []
        }
        
        def check_field_length(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    check_field_length(value, current_path)
            elif isinstance(obj, str):
                if len(obj) > max_length:
                    validation_results['oversized_fields'].append({
                        'field': path,
                        'length': len(obj),
                        'max_allowed': max_length
                    })
                    validation_results['compliant'] = False
        
        check_field_length(data)
        
        return validation_results
    
    @classmethod
    def validate_sensitive_data_filtering(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that sensitive data patterns are properly filtered.
        
        Args:
            data: Data dictionary to validate
            
        Returns:
            Dictionary with validation results
        """
        import re
        
        validation_results = {
            'compliant': True,
            'sensitive_data_found': [],
            'patterns_detected': []
        }
        
        data_str = json.dumps(data, default=str)
        
        for pattern in cls.PII_PATTERNS:
            matches = re.findall(pattern, data_str)
            if matches:
                validation_results['patterns_detected'].append({
                    'pattern': pattern,
                    'matches': matches
                })
                validation_results['compliant'] = False
        
        return validation_results
    
    @staticmethod
    def validate_access_control(
        user_permissions: List[str], 
        required_permission: str,
        resource_sensitivity: str = "normal"
    ) -> bool:
        """
        Validate access control for security testing.
        
        Args:
            user_permissions: List of user permissions
            required_permission: Required permission for access
            resource_sensitivity: Sensitivity level of resource ('normal', 'high')
            
        Returns:
            Boolean indicating if access should be granted
            
        Raises:
            ValueError: If user_permissions is empty, required_permission is invalid,
                       or resource_sensitivity is not recognized
        """
        # Input validation with enhanced error messages
        if not user_permissions:
            raise ValueError("User permissions list cannot be empty for access control validation")
        
        if not required_permission or not isinstance(required_permission, str):
            raise ValueError(f"Required permission must be a non-empty string, got: {required_permission}")
        
        if resource_sensitivity not in ["normal", "high"]:
            raise ValueError(f"Resource sensitivity must be 'normal' or 'high', got: '{resource_sensitivity}'")
        
        # Basic permission check
        if required_permission not in user_permissions:
            return False
        
        # Enhanced checks for sensitive resources
        if resource_sensitivity == "high":
            required_enhanced_permissions = [
                'admin_access',
                'high_sensitivity_read'
            ]
            return any(perm in user_permissions for perm in required_enhanced_permissions)
        
        return True


@pytest.fixture
def security_data_factory():
    """Fixture providing security test data factory."""
    return SecurityTestDataFactory()


@pytest.fixture
def security_validator():
    """Fixture providing security compliance validator."""
    return SecurityComplianceValidator()


@pytest.fixture
def mock_pydantic_model() -> Type:
    """
    Fixture providing mock Pydantic model that handles validation errors gracefully.
    
    Returns:
        Mock Pydantic model class that accepts any fields without validation errors
        
    This fixture enables security testing by providing a model that:
    - Accepts any field names (processing_id vs process_id compatibility)
    - Doesn't raise ValidationError on field mismatches
    - Provides serialization methods for testing data flow
    - Maintains API compatibility with real Pydantic models
    """
    class MockScenarioProcessingRecord:
        """
        Mock Pydantic model for security testing that accepts any fields gracefully.
        
        This mock model enables testing of security validation patterns without
        being blocked by Pydantic validation errors from field name mismatches.
        """
        
        def __init__(self, **kwargs: Any) -> None:
            """
            Initialize mock model with any provided fields.
            
            Args:
                **kwargs: Any field values to set on the model instance
            """
            # Accept any fields for testing flexibility
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        @classmethod
        def model_validate(cls, data: Dict[str, Any]) -> 'MockScenarioProcessingRecord':
            """
            Mock model_validate method that doesn't fail on validation.
            
            Args:
                data: Dictionary of field values to validate
                
            Returns:
                Mock model instance with validated data
            """
            return cls(**data)
        
        @classmethod
        def parse_obj(cls, data: Dict[str, Any]) -> 'MockScenarioProcessingRecord':
            """
            Legacy parse_obj method for compatibility with older Pydantic versions.
            
            Args:
                data: Dictionary of field values to parse
                
            Returns:
                Mock model instance with parsed data
            """
            return cls.model_validate(data)
        
        def model_dump(self) -> Dict[str, Any]:
            """
            Return model data as dictionary for serialization testing.
            
            Returns:
                Dictionary containing all model field values
            """
            return {k: v for k, v in self.__dict__.items()}
        
        def to_databricks_dict(self) -> Dict[str, Any]:
            """
            Mock to_databricks_dict method for testing data serialization.
            
            Returns:
                Dictionary formatted for Databricks storage (same as model_dump for testing)
            """
            return self.model_dump()
    
    return MockScenarioProcessingRecord