"""
Data extraction utilities for replacing hardcoded values in scenario tracking.
Provides intelligent extraction of real data from email processing pipeline.
"""

from typing import Dict, Any, Optional
import os
import socket
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)


def extract_sender_info(email_data: Optional[Any]) -> Dict[str, str]:
    """
    Extract sender information from email data, replacing hardcoded "Customer" values.
    
    Args:
        email_data: Email data object from processing pipeline
        
    Returns:
        Dict containing sender_name, sender_email, customer_name with intelligent defaults
    """
    
    result = {
        'name': 'Unknown Sender',
        'email': 'unknown@unknown.com', 
        'customer_name': 'Unknown Customer'
    }
    
    if not email_data:
        logger.debug("No email data available for sender extraction, using defaults")
        return result
    
    try:
        # Extract from email_data.sender if available
        if hasattr(email_data, 'sender') and email_data.sender:
            sender = email_data.sender
            
            # Handle dictionary format first
            if isinstance(sender, dict):
                result['name'] = sender.get('name', result['name'])
                result['email'] = sender.get('email_address', sender.get('email', result['email']))
                result['customer_name'] = sender.get('name', result['name'])
            
            # Handle EmailAddress object
            elif hasattr(sender, 'name') and sender.name:
                name_str = str(sender.name).strip()
                # Skip Mock objects that don't have real string content
                if not name_str.startswith('<Mock') and name_str != 'Mock':
                    result['name'] = name_str
                    result['customer_name'] = name_str
                
                if hasattr(sender, 'email_address'):
                    email_str = str(sender.email_address)
                    if not email_str.startswith('<Mock') and email_str != 'Mock':
                        result['email'] = email_str
                elif hasattr(sender, 'email'):
                    email_str = str(sender.email)
                    if not email_str.startswith('<Mock') and email_str != 'Mock':
                        result['email'] = email_str
                    
            elif hasattr(sender, 'email_address') and sender.email_address:
                # Extract name from email if display name not available
                email_str = str(sender.email_address)
                if not email_str.startswith('<Mock') and email_str != 'Mock' and '@' in email_str:
                    email_local = email_str.split('@')[0]
                    result['name'] = email_local.replace('.', ' ').title()
                    result['customer_name'] = result['name']
                    result['email'] = email_str
                
            elif hasattr(sender, 'email') and sender.email:
                # Handle direct email attribute
                email_str = str(sender.email)
                if not email_str.startswith('<Mock') and email_str != 'Mock' and '@' in email_str:
                    email_local = email_str.split('@')[0]
                    result['name'] = email_local.replace('.', ' ').title()
                    result['customer_name'] = result['name']
                    result['email'] = email_str
        
        # Extract from direct email attributes
        elif hasattr(email_data, 'sender_email') and email_data.sender_email:
            result['email'] = email_data.sender_email
            email_local = email_data.sender_email.split('@')[0]
            result['name'] = email_local.replace('.', ' ').title()
            result['customer_name'] = result['name']
        
        # Extract sender from email headers as fallback
        elif hasattr(email_data, 'from_email') and email_data.from_email:
            result['email'] = email_data.from_email
            email_local = email_data.from_email.split('@')[0]
            result['name'] = email_local.replace('.', ' ').title()
            result['customer_name'] = result['name']
        
        logger.debug(f"Extracted sender info: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error extracting sender info: {e}")
        return result


def detect_environment() -> str:
    """
    Detect actual deployment environment, replacing hardcoded "development".
    
    Returns:
        String indicating actual environment: "production", "test", "development"
    """
    
    # Check environment variables in order of priority
    env_indicators = [
        os.environ.get('ENVIRONMENT'),
        os.environ.get('ENV'),
        os.environ.get('DEPLOYMENT_ENV'),
        os.environ.get('AZURE_ENV'),
        os.environ.get('NODE_ENV')
    ]
    
    for env in env_indicators:
        if env:
            env_lower = env.lower()
            if 'prod' in env_lower:
                return 'production'
            elif 'test' in env_lower or 'staging' in env_lower:
                return 'test'
            elif 'dev' in env_lower:
                return 'development'
            else:
                return env_lower
    
    # Detect from hostname patterns
    try:
        hostname = socket.gethostname().lower()
        if 'prod' in hostname:
            return 'production'
        elif 'test' in hostname or 'staging' in hostname:
            return 'test'
        elif 'dev' in hostname:
            return 'development'
    except Exception:
        pass
    
    # Default fallback with logging
    logger.warning("Could not detect environment, defaulting to development")
    return 'development'


def extract_assignment_reasoning(scenario_result: Optional[Any]) -> str:
    """
    Extract actual expert assignment reasoning, replacing generic text.
    
    Args:
        scenario_result: Scenario result object from processing pipeline
        
    Returns:
        String with actual assignment reasoning or intelligent default
    """
    
    if not scenario_result:
        return 'No scenario result available'
    
    try:
        # Extract from expert assignment if available
        if hasattr(scenario_result, 'expert_assignment') and scenario_result.expert_assignment:
            assignment = scenario_result.expert_assignment
            
            if hasattr(assignment, 'reason') and assignment.reason:
                reason_str = str(assignment.reason)
                if not reason_str.startswith('<Mock') and reason_str != 'Mock':
                    return reason_str
            
            if hasattr(assignment, 'assignment_method'):
                method_str = str(assignment.assignment_method)
                expert_name = str(getattr(assignment, 'expert_name', 'expert'))
                if not method_str.startswith('<Mock') and not expert_name.startswith('<Mock'):
                    return f"Assigned to {expert_name} via {method_str} method"
        
        # Extract reasoning from assignment method
        if hasattr(scenario_result, 'assignment_method') and scenario_result.assignment_method:
            method_str = str(scenario_result.assignment_method)
            if not method_str.startswith('<Mock') and method_str != 'Mock':
                expert_name = str(getattr(scenario_result, 'expert_assigned', 'expert'))
                if not expert_name.startswith('<Mock'):
                    return f"Assigned to {expert_name} via {method_str} method"
        
        # Fallback to scenario type
        if hasattr(scenario_result, 'scenario_type') and scenario_result.scenario_type:
            scenario_str = str(scenario_result.scenario_type)
            if not scenario_str.startswith('<Mock') and scenario_str != 'Mock':
                return f"Automatic assignment based on {scenario_str} scenario"
        
        return 'Automatic assignment via system rules'
        
    except Exception as e:
        logger.error(f"Error extracting assignment reasoning: {e}")
        return f'Assignment completed (extraction error: {str(e)[:50]})'


def validate_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean extracted data to ensure quality.
    
    Args:
        data: Dictionary of extracted data to validate
        
    Returns:
        Cleaned and validated data dictionary
    """
    
    # Clean and validate sender name
    if data.get('sender_name'):
        name = data['sender_name'].strip()
        # Remove common email artifacts
        name = name.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
        if len(name) > 100:  # Truncate very long names
            name = name[:100] + '...'
        data['sender_name'] = name
    
    # Clean and validate customer name  
    if data.get('customer_name'):
        customer = data['customer_name'].strip()
        customer = customer.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
        if len(customer) > 100:
            customer = customer[:100] + '...'
        data['customer_name'] = customer
    
    # Validate environment
    if data.get('environment'):
        env = data['environment'].lower()
        valid_environments = ['production', 'test', 'development', 'staging']
        if env not in valid_environments:
            logger.warning(f"Invalid environment '{env}', defaulting to development")
            data['environment'] = 'development'
    
    # Validate assignment reasoning
    if data.get('assignment_reasoning'):
        reasoning = data['assignment_reasoning'].strip()
        if len(reasoning) > 500:  # Prevent extremely long reasoning
            reasoning = reasoning[:500] + '...'
        data['assignment_reasoning'] = reasoning
    
    return data


def extract_customer_name(email_data: Optional[Any], processing_result: Optional[Any] = None) -> str:
    """
    Extract customer name from available data sources, replacing hardcoded "Customer".
    
    Args:
        email_data: Email data object
        processing_result: Processing result object (optional)
        
    Returns:
        Extracted customer name or intelligent default
    """
    
    try:
        # First try sender info extraction
        sender_info = extract_sender_info(email_data)
        if sender_info['name'] != 'Unknown Sender':
            return sender_info['name']
        
        # Try processing result if available
        if processing_result and hasattr(processing_result, 'customer_name'):
            customer_name = processing_result.customer_name
            if customer_name and customer_name != 'Customer':
                return customer_name
        
        # Try to extract from email headers
        if email_data and hasattr(email_data, 'headers'):
            headers = email_data.headers
            if isinstance(headers, dict):
                from_header = headers.get('From', '')
                if from_header and '<' in from_header:
                    # Extract name from "Name <email@domain.com>" format
                    name_part = from_header.split('<')[0].strip()
                    if name_part and name_part != from_header:
                        return name_part
        
        # Fallback to email local part if available
        if email_data and hasattr(email_data, 'sender'):
            sender = email_data.sender
            email_addr = None
            
            if hasattr(sender, 'email'):
                email_addr = sender.email
            elif hasattr(sender, 'email_address'):
                email_addr = sender.email_address
            
            if email_addr and '@' in email_addr:
                local_part = email_addr.split('@')[0]
                return local_part.replace('.', ' ').replace('_', ' ').title()
        
        return 'Unknown Customer'
        
    except Exception as e:
        logger.error(f"Error extracting customer name: {e}")
        return 'Unknown Customer'


def get_expert_assignment_method(scenario_result: Optional[Any], processing_result: Optional[Any] = None) -> str:
    """
    Extract the actual expert assignment method used, replacing hardcoded "round_robin".
    
    Args:
        scenario_result: Scenario result object
        processing_result: Processing result object (optional)
        
    Returns:
        Actual assignment method or intelligent default
    """
    
    try:
        # Check scenario result first
        if scenario_result:
            if hasattr(scenario_result, 'assignment_method') and scenario_result.assignment_method:
                return scenario_result.assignment_method
            
            if hasattr(scenario_result, 'expert_assignment') and scenario_result.expert_assignment:
                assignment = scenario_result.expert_assignment
                if hasattr(assignment, 'method') and assignment.method:
                    return assignment.method
                elif hasattr(assignment, 'assignment_type') and assignment.assignment_type:
                    return assignment.assignment_type
        
        # Check processing result
        if processing_result and hasattr(processing_result, 'assignment_method'):
            return processing_result.assignment_method
        
        # Default based on context
        if scenario_result and hasattr(scenario_result, 'scenario_type'):
            scenario_type = scenario_result.scenario_type
            if hasattr(scenario_type, 'value'):
                scenario_str = scenario_type.value
            else:
                scenario_str = str(scenario_type)
            
            # Scenario-specific defaults
            if 'scenario_5' in scenario_str:
                return 'availability_based'  # Sales scenarios typically use availability
            else:
                return 'round_robin'  # Default for other scenarios
        
        return 'round_robin'  # Ultimate fallback
        
    except Exception as e:
        logger.error(f"Error extracting assignment method: {e}")
        return 'round_robin'