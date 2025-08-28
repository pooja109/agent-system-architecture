"""
Salesforce Field Validator Utility
===================================

Validates Salesforce Support Request fields with fallback strategies for Phase 5 requirements.
Ensures required picklist fields are properly set with error handling.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FieldValidationResult:
    """Result of field validation with corrected values"""
    is_valid: bool
    original_value: Any
    corrected_value: Any
    used_fallback: bool = False
    validation_message: str = ""

class SalesforceFieldValidator:
    """Validates Salesforce Support Request fields with fallback strategies"""
    
    def __init__(self):
        # Required field configurations with fallback values
        # These are based on common Salesforce picklist values
        self.field_configurations = {
            'Type': {
                'required_value': 'Digital Outreach',
                'fallback_values': ['Other', 'Email', 'Phone', 'Web'],
                'is_required': True
            },
            'Status': {
                'required_value': 'Assigned',
                'fallback_values': ['New', 'Open', 'In Progress', 'Working'],
                'is_required': True
            },
            'Request_Case_Category__c': {
                'required_value': 'AI Agent',
                'fallback_values': ['General', 'Technical', 'Support', 'Other'],
                'is_required': False  # Custom field may not be required
            }
        }
    
    def validate_support_request_fields(self, field_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate all Support Request fields and provide corrected values
        Returns dict with corrected field values and validation results
        """
        
        validation_results = {
            'corrected_fields': {},
            'validation_details': {},
            'has_errors': False,
            'has_warnings': False,
            'messages': []
        }
        
        # Validate each configured field
        for field_name, config in self.field_configurations.items():
            
            # Get the field value (use required value if not provided)
            field_value = field_values.get(field_name, config['required_value'])
            
            # Validate the field
            field_result = self._validate_single_field(field_name, field_value, config)
            
            # Store the corrected value
            validation_results['corrected_fields'][field_name] = field_result.corrected_value
            validation_results['validation_details'][field_name] = field_result
            
            # Track validation status
            if not field_result.is_valid:
                if config['is_required']:
                    validation_results['has_errors'] = True
                else:
                    validation_results['has_warnings'] = True
            
            if field_result.used_fallback:
                validation_results['has_warnings'] = True
                validation_results['messages'].append(
                    f"Field {field_name}: {field_result.validation_message}"
                )
        
        # Add non-validated fields directly
        for field_name, field_value in field_values.items():
            if field_name not in self.field_configurations:
                validation_results['corrected_fields'][field_name] = field_value
        
        return validation_results
    
    def _validate_single_field(
        self, 
        field_name: str, 
        field_value: Any, 
        config: Dict[str, Any]
    ) -> FieldValidationResult:
        """Validate a single field with fallback logic"""
        
        result = FieldValidationResult(
            is_valid=True,
            original_value=field_value,
            corrected_value=field_value
        )
        
        try:
            # For picklist fields, we'll use the required value if provided value seems invalid
            # In a full implementation, this would check against actual Salesforce metadata
            
            # If no value provided, use required value
            if not field_value:
                result.corrected_value = config['required_value']
                result.used_fallback = True
                result.validation_message = f"Used required value '{config['required_value']}' for empty field"
                logger.info("Field %s: %s", field_name, result.validation_message)
                return result
            
            # For Type field, ensure it's a reasonable value
            if field_name == 'Type':
                if field_value not in ['Digital Outreach', 'Phone', 'Email', 'Web', 'Other']:
                    result.corrected_value = config['required_value']
                    result.used_fallback = True
                    result.validation_message = f"Used '{config['required_value']}' instead of unrecognized value '{field_value}'"
            
            # For Status field, ensure it's a reasonable value  
            elif field_name == 'Status':
                if field_value not in ['New', 'Assigned', 'Open', 'In Progress', 'Working', 'Closed']:
                    result.corrected_value = config['required_value']
                    result.used_fallback = True
                    result.validation_message = f"Used '{config['required_value']}' instead of unrecognized value '{field_value}'"
            
            # For custom Request Category field, be more lenient
            elif field_name == 'Request_Case_Category__c':
                if not isinstance(field_value, str) or len(str(field_value).strip()) == 0:
                    result.corrected_value = config['required_value']
                    result.used_fallback = True
                    result.validation_message = f"Used '{config['required_value']}' for invalid custom field value"
            
            if result.used_fallback:
                logger.warning("Field validation fallback for %s: %s", field_name, result.validation_message)
            
        except Exception as e:
            # If validation fails, use fallback
            result.corrected_value = config['required_value']
            result.used_fallback = True
            result.validation_message = f"Validation error, used fallback: {str(e)}"
            logger.error("Field validation error for %s: %s", field_name, e)
        
        return result
    
    def get_required_field_values(self) -> Dict[str, str]:
        """Get the required values for all configured fields"""
        return {
            field_name: config['required_value']
            for field_name, config in self.field_configurations.items()
        }