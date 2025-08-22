"""
Data transformation utilities for converting between model types.
Handles mapping from email processing models to scenario tracking models.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import ValidationError

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.email import Email, ProcessingResult
    from services.scenario_processor import ScenarioResult
    from services.azure_ai_foundry_client import IntentClassificationResult

# Import models directly
try:
    from database.scenario_tracking_models import (
        ScenarioProcessingRecord,
        ScenarioType,
        AIIntent,
        TestModeType,
        EmailImportanceLevel,
        DatabaseUpdateRecord
    )
except ImportError:
    from ..database.scenario_tracking_models import (
        ScenarioProcessingRecord,
        ScenarioType,
        AIIntent,
        TestModeType,
        EmailImportanceLevel,
        DatabaseUpdateRecord
    )

logger = structlog.get_logger(__name__)


class ScenarioDataTransformer:
    """Transforms data between email processing models and tracking models."""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        
        # Security patterns for data sanitization
        self._pii_patterns = [
            # SSN patterns
            r'\b(?:\d{3}-\d{2}-\d{4}|\d{9})\b',
            # Credit card patterns (basic)
            r'\b(?:\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b',
            # Phone number patterns
            r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            # Email addresses (but allow sender/recipient emails in proper fields)
            # r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ]
        
        # Security threat patterns
        self._security_patterns = [
            # SQL injection patterns
            r'(?i)\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b.*\b(from|where|into|values|table|database)\b',
            # Script injection patterns
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            # Command injection patterns
            r'[;&|`$(){}[\]\\]',
            # Path traversal
            r'\.\.[\\/]',
            # Null bytes
            r'%00',
            r'\x00',
        ]
        
        # Compiled regex patterns for performance
        self._compiled_pii_patterns = [re.compile(pattern) for pattern in self._pii_patterns]
        self._compiled_security_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self._security_patterns]
    
    def _sanitize_string(self, value: str, max_length: int = None, field_name: str = "unknown") -> str:
        """Comprehensive string sanitization for security and privacy.
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length (truncate if exceeded)
            field_name: Field name for logging context
            
        Returns:
            Sanitized string
        """
        if not value or not isinstance(value, str):
            return str(value) if value is not None else ""
        
        original_value = value
        suspicious_patterns = []
        
        # Step 1: Basic cleanup
        # Remove null bytes and control characters except newlines/tabs
        value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', value)
        
        # Step 2: Security threat detection and sanitization
        for i, pattern in enumerate(self._compiled_security_patterns):
            if pattern.search(value):
                suspicious_patterns.append(f"security_pattern_{i}")
                # Replace suspicious content with placeholder
                value = pattern.sub('[SANITIZED]', value)
        
        # Step 3: PII detection and redaction
        for i, pattern in enumerate(self._compiled_pii_patterns):
            matches = pattern.findall(value)
            if matches:
                suspicious_patterns.append(f"pii_pattern_{i}")
                # Replace PII with redacted placeholder
                value = pattern.sub('[PII_REDACTED]', value)
        
        # Step 4: Length truncation
        if max_length and len(value) > max_length:
            value = value[:max_length-3] + "..."
            
        # Log if sanitization occurred
        if suspicious_patterns or value != original_value:
            self.logger.warning(
                "Data sanitization applied",
                field_name=field_name,
                patterns_detected=suspicious_patterns,
                original_length=len(original_value),
                sanitized_length=len(value),
                truncated=max_length and len(original_value) > max_length
            )
        
        return value
    
    def _sanitize_email(self, email: str, field_name: str = "email") -> str:
        """Sanitize email addresses while preserving valid format.
        
        Args:
            email: Email address to sanitize
            field_name: Field name for logging
            
        Returns:
            Sanitized email address
        """
        if not email or not isinstance(email, str):
            return ""
        
        # Basic email validation pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        # Clean the email
        cleaned_email = email.strip().lower()
        
        # Check for suspicious patterns in email
        for pattern in self._compiled_security_patterns:
            if pattern.search(cleaned_email):
                self.logger.warning(
                    "Suspicious pattern detected in email",
                    field_name=field_name,
                    email_domain=cleaned_email.split('@')[-1] if '@' in cleaned_email else "unknown"
                )
                return "[SANITIZED_EMAIL]"
        
        # Validate email format
        if not re.match(email_pattern, cleaned_email):
            self.logger.debug(
                "Invalid email format",
                field_name=field_name,
                email_length=len(cleaned_email)
            )
            return "[INVALID_EMAIL]"
        
        # Limit email length
        if len(cleaned_email) > 254:  # RFC 5321 limit
            self.logger.warning(
                "Email address exceeds RFC limit",
                field_name=field_name,
                length=len(cleaned_email)
            )
            return "[OVERSIZED_EMAIL]"
        
        return cleaned_email
    
    def _sanitize_dict(self, data: dict, max_depth: int = 5, current_depth: int = 0) -> dict:
        """Recursively sanitize dictionary data.
        
        Args:
            data: Dictionary to sanitize
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            Sanitized dictionary
        """
        if current_depth >= max_depth:
            return {"error": "max_depth_exceeded"}
        
        if not isinstance(data, dict):
            return {}
        
        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            safe_key = self._sanitize_string(str(key), max_length=100, field_name=f"dict_key_{current_depth}")
            
            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[safe_key] = self._sanitize_string(value, max_length=1000, field_name=f"dict_value_{safe_key}")
            elif isinstance(value, dict):
                sanitized[safe_key] = self._sanitize_dict(value, max_depth, current_depth + 1)
            elif isinstance(value, list):
                sanitized[safe_key] = self._sanitize_list(value, max_depth, current_depth + 1)
            elif value is None:
                sanitized[safe_key] = None
            else:
                # For other types, convert to string and sanitize
                sanitized[safe_key] = self._sanitize_string(str(value), max_length=500, field_name=f"dict_value_{safe_key}")
        
        return sanitized
    
    def _sanitize_list(self, data: list, max_depth: int = 5, current_depth: int = 0) -> list:
        """Sanitize list data.
        
        Args:
            data: List to sanitize
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            Sanitized list
        """
        if current_depth >= max_depth:
            return ["max_depth_exceeded"]
        
        if not isinstance(data, list):
            return []
        
        # Limit list size to prevent abuse
        if len(data) > 100:
            self.logger.warning("Large list detected, truncating", size=len(data))
            data = data[:100]
        
        sanitized = []
        for i, item in enumerate(data):
            if isinstance(item, str):
                sanitized.append(self._sanitize_string(item, max_length=500, field_name=f"list_item_{i}"))
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item, max_depth, current_depth + 1))
            elif isinstance(item, list):
                sanitized.append(self._sanitize_list(item, max_depth, current_depth + 1))
            elif item is None:
                sanitized.append(None)
            else:
                sanitized.append(self._sanitize_string(str(item), max_length=500, field_name=f"list_item_{i}"))
        
        return sanitized
    
    async def create_tracking_record(
        self,
        email_data: Any,
        processing_result: Any,
        scenario_result: Any = None,
        intent_result: Any = None,
        original_subject_result: Any = None,
        correlation_id: str = None,
        **additional_context
    ) -> ScenarioProcessingRecord:
        """
        COMPREHENSIVE FIELD POPULATION: Create tracking record with ALL fields populated.
        
        Args:
            email_data: Email object from processing pipeline
            processing_result: ProcessingResult object
            scenario_result: ScenarioResult object (optional)
            intent_result: IntentClassificationResult object (optional)
            correlation_id: Correlation ID for tracing
            **additional_context: Additional context information
            
        Returns:
            ScenarioProcessingRecord ready for storage with ALL fields populated
            
        Raises:
            ValidationError: If required data is missing or invalid
        """
        try:
            # Log basic transformation info (reduced verbosity)
            self.logger.debug(f"Creating scenario record for correlation_id: {correlation_id}")
            
            # *** CRITICAL FIX: Use the working factory method that provides 100% field population ***
            # This restores the comprehensive field population that was previously working
            record = await ScenarioProcessingRecord.from_processing_results(
                email_data=email_data,
                processing_result=processing_result,
                scenario_result=scenario_result,
                intent_result=intent_result,
                original_subject_result=original_subject_result,
                correlation_id=correlation_id,
                **additional_context
            )
            
            self.logger.info("✅ Comprehensive record creation SUCCEEDED using factory method!")
            return record
            
        except Exception as e:
            # If comprehensive record creation fails, log detailed error information
            self.logger.error("❌ Comprehensive record creation FAILED!")
            self.logger.error(f"Error type: {type(e).__name__}")
            self.logger.error(f"Error message: {str(e)}")
            
            # Log detailed validation errors if available
            if hasattr(e, 'errors'):
                self.logger.error("Detailed validation errors:")
                for i, error in enumerate(e.errors()):
                    self.logger.error(f"  {i+1}. Field: {error.get('loc', 'unknown')}")
                    self.logger.error(f"     Type: {error.get('type', 'unknown')}")
                    self.logger.error(f"     Message: {error.get('msg', 'unknown')}")
                    self.logger.error(f"     Input: {error.get('input', 'unknown')}")
            
            # Use the minimal fallback to ensure SOMETHING gets stored
            self.logger.warning(f"Using minimal fallback record due to comprehensive failure: {e}")
            return self._create_minimal_fallback_record(email_data, processing_result, str(e))
    
    def _fast_extract_base_information(
        self, 
        email_data: Any, 
        processing_result: Any, 
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """PERFORMANCE OPTIMIZED: Fast extraction of base information."""
        
        # PERFORMANCE OPTIMIZATION: Direct attribute access with fallbacks
        processing_id = getattr(processing_result, 'processing_id', str(uuid.uuid4()))
        email_id = getattr(email_data, 'id', 'unknown')
        
        # PERFORMANCE OPTIMIZATION: Direct extraction without deep introspection
        sender_email = 'unknown@unknown.com'
        sender_name = None
        subject = None
        
        if hasattr(email_data, 'sender') and email_data.sender:
            sender_email = getattr(email_data.sender, 'email', sender_email)
            sender_name = getattr(email_data.sender, 'name', None)
        
        if hasattr(email_data, 'subject'):
            subject = email_data.subject
            if subject and len(subject) > 500:
                subject = subject[:497] + "..."
        
        # PERFORMANCE OPTIMIZATION: Use current time if not available
        received_datetime = getattr(email_data, 'received_datetime', datetime.now(timezone.utc))
        
        return {
            'processing_id': processing_id,
            'email_id': email_id,
            'correlation_id': correlation_id,
            'sender_email': sender_email,
            'sender_name': sender_name,
            'subject': subject,
            'received_datetime': received_datetime,
            'process_success': getattr(processing_result, 'success', False),
            'processing_duration_ms': getattr(processing_result, 'processing_duration_ms', None),
            'process_error': getattr(processing_result, 'error', None)
        }
    
    def _fast_extract_scenario_information(self, scenario_result: Any) -> Dict[str, Any]:
        """PERFORMANCE OPTIMIZED: Fast scenario information extraction."""
        return {
            'scenario_type': self._map_scenario_type(getattr(scenario_result, 'scenario_type', None)),
            'scenario_success': getattr(scenario_result, 'success', False),
            'expert_assigned': getattr(scenario_result, 'expert_assigned', None),
            'case_created': getattr(scenario_result, 'case_created', None)
        }
    
    def _fast_extract_ai_classification_information(self, intent_result: Any) -> Dict[str, Any]:
        """PERFORMANCE OPTIMIZED: Fast AI classification extraction."""
        return {
            'ai_intent': self._map_ai_intent(getattr(intent_result, 'intent', None)),
            'ai_confidence': getattr(intent_result, 'confidence', None)
        }
    
    def _fast_extract_context_information(self, **additional_context) -> Dict[str, Any]:
        """PERFORMANCE OPTIMIZED: Fast context extraction."""
        context_data = {}
        
        # PERFORMANCE OPTIMIZATION: Only extract commonly used context fields
        if 'test_mode' in additional_context:
            context_data['test_mode'] = additional_context['test_mode']
        
        if 'environment' in additional_context:
            context_data['environment'] = additional_context['environment']
            
        return context_data
    
    def _create_minimal_fallback_record(
        self, 
        email_data: Any, 
        processing_result: Any,
        error_message: str
    ) -> ScenarioProcessingRecord:
        """PERFORMANCE OPTIMIZED: Create minimal fallback record."""
        return ScenarioProcessingRecord(
            processing_id=getattr(processing_result, 'processing_id', str(uuid.uuid4())),
            email_id=getattr(email_data, 'id', 'unknown'),
            sender_email='error@unknown.com',
            received_datetime=datetime.now(timezone.utc),
            process_success=False,
            process_error=f"Fast fallback: {error_message}",
            scenario_type=ScenarioType.UNKNOWN
        )
    
    def _extract_base_information(
        self, 
        email_data: Any, 
        processing_result: Any, 
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """Extract base email and processing information."""
        
        # Processing identifiers
        processing_id = getattr(processing_result, 'processing_id', str(uuid.uuid4()))
        email_id = getattr(email_data, 'id', 'unknown')
        
        # Email source information (with sanitization)
        raw_sender_email = self._safe_extract_sender_email(email_data)
        sender_email = self._sanitize_email(raw_sender_email, "sender_email") if raw_sender_email else None
        
        raw_sender_name = self._safe_extract_sender_name(email_data)
        sender_name = self._sanitize_string(raw_sender_name, max_length=200, field_name="sender_name") if raw_sender_name else None
        
        # Email metadata (with sanitization)
        raw_subject = getattr(email_data, 'subject', None)
        subject = self._sanitize_string(raw_subject, max_length=500, field_name="subject") if raw_subject else None
        
        received_datetime = getattr(email_data, 'received_datetime', datetime.now(timezone.utc))
        sent_datetime = getattr(email_data, 'sent_datetime', None)
        
        raw_email_body = getattr(email_data, 'email_body', None)
        email_body = self._sanitize_string(raw_email_body, max_length=None, field_name="email_body") if raw_email_body else None
        
        # Processing workflow information (with sanitization)
        process_success = getattr(processing_result, 'success', False)
        processing_duration_ms = getattr(processing_result, 'processing_duration_ms', None)
        
        raw_process_error = getattr(processing_result, 'error', None)
        process_error = self._sanitize_string(raw_process_error, max_length=1000, field_name="process_error") if raw_process_error else None
        
        # Email lifecycle (with sanitization)
        raw_destination_folder = getattr(processing_result, 'destination_folder', None)
        destination_folder = self._sanitize_string(raw_destination_folder, max_length=200, field_name="destination_folder") if raw_destination_folder else None
        
        raw_storage_location = getattr(processing_result, 'storage_location', None)
        storage_location = self._sanitize_string(raw_storage_location, max_length=500, field_name="storage_location") if raw_storage_location else None
        
        return {
            'processing_id': processing_id,
            'email_id': email_id,
            'correlation_id': correlation_id,
            'sender_email': sender_email,
            'sender_name': sender_name,
            'subject': subject,
            'received_datetime': received_datetime,
            'sent_datetime': sent_datetime,
            'email_body': email_body,
            'process_success': process_success,
            'processing_duration_ms': processing_duration_ms,
            'process_error': process_error,
            'destination_folder': destination_folder,
            'storage_location': storage_location,
            'recipient_emails': self._extract_recipient_emails(email_data),
            'email_importance': self._map_email_importance(email_data),
            'has_attachments': getattr(email_data, 'has_attachments', False),
            'attachment_count': getattr(email_data, 'attachment_count', 0),
            'conversation_id': getattr(email_data, 'conversation_id', None)
        }
    
    def _extract_scenario_information(self, scenario_result: Any) -> Dict[str, Any]:
        """Extract scenario processing information."""
        
        # Map scenario type
        scenario_type = self._map_scenario_type(getattr(scenario_result, 'scenario_type', None))
        
        # Basic scenario information (with sanitization)
        raw_error_message = getattr(scenario_result, 'error_message', None)
        error_message = self._sanitize_string(raw_error_message, max_length=1000, field_name="scenario_error_message") if raw_error_message else None
        
        raw_agent_actions_log = getattr(scenario_result, 'agent_actions_log', [])
        agent_actions_log = self._sanitize_list(raw_agent_actions_log) if raw_agent_actions_log else []
        
        scenario_data = {
            'scenario_type': scenario_type,
            'scenario_success': getattr(scenario_result, 'success', False),
            'scenario_error_message': error_message,
            'agent_actions_log': agent_actions_log
        }
        
        # Expert assignment information (Scenario 5) with sanitization
        raw_expert_assigned = getattr(scenario_result, 'expert_assigned', None)
        if raw_expert_assigned:
            expert_assigned = self._sanitize_string(raw_expert_assigned, max_length=200, field_name="expert_assigned")
            raw_expert_id = getattr(scenario_result, 'expert_id', None)
            expert_id = self._sanitize_string(raw_expert_id, max_length=100, field_name="expert_id") if raw_expert_id else None
            
            raw_expert_email = getattr(scenario_result, 'expert_email', None)
            expert_email = self._sanitize_email(raw_expert_email, "expert_email") if raw_expert_email else None
            
            scenario_data.update({
                'expert_assigned': expert_assigned,
                'expert_id': expert_id,
                'expert_email': expert_email,
                'assignment_method': 'round_robin'  # Default assignment method
            })
        
        # Salesforce case information (with sanitization)
        raw_case_created = getattr(scenario_result, 'case_created', None)
        if raw_case_created:
            case_created = self._sanitize_string(raw_case_created, max_length=100, field_name="case_created")
            scenario_data.update({
                'case_created': case_created,
                'case_status': 'Assigned'  # Default initial status
            })
        
        # Email forwarding information (with sanitization)
        raw_emails_sent = getattr(scenario_result, 'emails_sent', [])
        if raw_emails_sent:
            # Sanitize email list - each should be a valid email
            emails_forwarded = []
            if isinstance(raw_emails_sent, list):
                for email in raw_emails_sent[:10]:  # Limit to 10 emails
                    if isinstance(email, str):
                        sanitized_email = self._sanitize_email(email, "forwarded_email")
                        if sanitized_email and not sanitized_email.startswith("["):
                            emails_forwarded.append(sanitized_email)
            
            scenario_data.update({
                'emails_forwarded': emails_forwarded,
                'forwarding_success': True,
                'forwarding_reason': self._determine_forwarding_reason(scenario_type)
            })
        
        return scenario_data
    
    def _extract_original_subject_information(self, original_subject_result: Any) -> Dict[str, Any]:
        """Extract original subject extraction information with sanitization."""
        
        # Sanitize extracted subject
        raw_original_subject = getattr(original_subject_result, 'original_subject', None)
        original_subject = self._sanitize_string(raw_original_subject, max_length=500, field_name="original_subject_result") if raw_original_subject else None
        
        # Sanitize reasoning output
        raw_reasoning = getattr(original_subject_result, 'reasoning', None)
        reasoning = self._sanitize_string(raw_reasoning, max_length=2000, field_name="original_subject_reasoning") if raw_reasoning else None
        
        return {
            'original_subject_result': original_subject,
            'original_subject_confidence': getattr(original_subject_result, 'confidence', None),
            'original_subject_reasoning': reasoning,
            'original_subject_extraction_method': getattr(original_subject_result, 'extraction_method', 'ai_analysis'),
            'original_subject_processing_duration_ms': getattr(original_subject_result, 'processing_duration_ms', None),
            'original_subject_model_version': getattr(original_subject_result, 'model_version', None)
        }
    
    def _extract_ai_classification_information(self, intent_result: Any) -> Dict[str, Any]:
        """Extract AI classification information with sanitization."""
        
        # Map intent to tracking enum
        ai_intent = self._map_ai_intent(getattr(intent_result, 'intent', None))
        
        # Sanitize AI reasoning output
        raw_reasoning = getattr(intent_result, 'reasoning', None)
        ai_reasoning = self._sanitize_string(raw_reasoning, max_length=2000, field_name="ai_reasoning") if raw_reasoning else None
        
        # Sanitize detected phrases
        raw_detected_phrases = getattr(intent_result, 'detected_phrases', [])
        ai_detected_phrases = self._sanitize_list(raw_detected_phrases) if raw_detected_phrases else []
        
        return {
            'email_intent': ai_intent,
            'email_intent_confidence': getattr(intent_result, 'confidence', None),
            'email_intent_reasoning': ai_reasoning,
            'email_intent_detected_phrases': ai_detected_phrases,
            'email_intent_processing_duration_ms': getattr(intent_result, 'processing_duration_ms', None),
            'email_intent_model_version': getattr(intent_result, 'model_version', None)
        }
    
    def _extract_context_information(
        self, 
        email_data: Any, 
        processing_result: Any,
        **additional_context
    ) -> Dict[str, Any]:
        """Extract additional context information with sanitization."""
        
        context_data = {}
        
        # Test mode detection
        test_mode = additional_context.get('test_mode', False)
        if test_mode:
            # Sanitize test mode substitutions
            raw_substitutions = additional_context.get('test_email_substitutions', {})
            sanitized_substitutions = self._sanitize_dict(raw_substitutions) if raw_substitutions else {}
            
            context_data.update({
                'test_mode': True,
                'test_mode_type': TestModeType.EMAIL_TEST,  # Default test mode type
                'test_email_substitutions': sanitized_substitutions
            })
        
        # Environment information (sanitize to prevent injection)
        raw_environment = additional_context.get('environment')
        if raw_environment:
            environment = self._sanitize_string(str(raw_environment), max_length=50, field_name="environment")
            context_data['environment'] = environment
        
        # Performance information (validate numeric values)
        memory_usage = additional_context.get('memory_usage_mb')
        if memory_usage and isinstance(memory_usage, (int, float)) and 0 <= memory_usage <= 100000:
            context_data['memory_usage_mb'] = memory_usage
        
        connection_wait_time = additional_context.get('connection_pool_wait_ms')
        if connection_wait_time and isinstance(connection_wait_time, (int, float)) and 0 <= connection_wait_time <= 300000:
            context_data['connection_pool_wait_ms'] = connection_wait_time
        
        # Version information (sanitize to prevent injection)
        raw_version = additional_context.get('monitor_version', '1.0.0')
        monitor_version = self._sanitize_string(str(raw_version), max_length=20, field_name="monitor_version")
        context_data['monitor_version'] = monitor_version
        
        return context_data
    
    def _safe_extract_sender_email(self, email_data: Any) -> str:
        """Safely extract sender email with fallbacks."""
        try:
            if hasattr(email_data, 'sender') and hasattr(email_data.sender, 'email'):
                return email_data.sender.email
            elif hasattr(email_data, 'from') and hasattr(email_data['from'], 'emailAddress'):
                return email_data['from']['emailAddress']['address']
            else:
                return 'unknown@unknown.com'
        except (AttributeError, KeyError, TypeError):
            return 'unknown@unknown.com'
    
    def _safe_extract_sender_name(self, email_data: Any) -> Optional[str]:
        """Safely extract sender name with fallbacks."""
        try:
            if hasattr(email_data, 'sender') and hasattr(email_data.sender, 'name'):
                return email_data.sender.name
            elif hasattr(email_data, 'from') and hasattr(email_data['from'], 'emailAddress'):
                return email_data['from']['emailAddress'].get('name')
            else:
                return None
        except (AttributeError, KeyError, TypeError):
            return None
    
    def _extract_recipient_emails(self, email_data: Any) -> List[str]:
        """Extract all recipient email addresses."""
        recipients = []
        
        try:
            if hasattr(email_data, 'recipients'):
                # Pydantic model structure
                for recipient_type in ['to', 'cc', 'bcc']:
                    recipient_list = getattr(email_data.recipients, recipient_type, [])
                    for recipient in recipient_list:
                        if hasattr(recipient, 'email'):
                            recipients.append(recipient.email)
            
            elif isinstance(email_data, dict):
                # Dictionary structure from Graph API
                for recipient_type in ['toRecipients', 'ccRecipients', 'bccRecipients']:
                    recipient_list = email_data.get(recipient_type, [])
                    for recipient in recipient_list:
                        if isinstance(recipient, dict) and 'emailAddress' in recipient:
                            recipients.append(recipient['emailAddress']['address'])
                            
        except Exception as e:
            self.logger.debug("Failed to extract recipient emails", error=str(e))
        
        return recipients
    
    def _map_email_importance(self, email_data: Any) -> EmailImportanceLevel:
        """Map email importance to tracking enum."""
        try:
            importance = getattr(email_data, 'importance', 'normal')
            if isinstance(importance, str):
                importance_lower = importance.lower()
                if importance_lower == 'high':
                    return EmailImportanceLevel.HIGH
                elif importance_lower == 'low':
                    return EmailImportanceLevel.LOW
                else:
                    return EmailImportanceLevel.NORMAL
            else:
                return EmailImportanceLevel.NORMAL
        except Exception:
            return EmailImportanceLevel.NORMAL
    
    def _map_scenario_type(self, scenario_type: Any) -> ScenarioType:
        """Map scenario type to tracking enum."""
        if not scenario_type:
            return ScenarioType.UNKNOWN
        
        try:
            if hasattr(scenario_type, 'value'):
                # Enum value
                scenario_str = scenario_type.value
            else:
                scenario_str = str(scenario_type)
            
            # Map string values to tracking enums
            mapping = {
                'scenario_5': ScenarioType.SCENARIO_5,
                'scenario_6': ScenarioType.SCENARIO_6,
                'scenario_7': ScenarioType.SCENARIO_7,
                'scenario_8': ScenarioType.SCENARIO_8,
                'scenario_9': ScenarioType.SCENARIO_9,
                'scenario_10': ScenarioType.SCENARIO_10,
                'scenario_11': ScenarioType.SCENARIO_11
            }
            
            return mapping.get(scenario_str.lower(), ScenarioType.UNKNOWN)
            
        except Exception:
            return ScenarioType.UNKNOWN
    
    def _map_ai_intent(self, intent: Any) -> AIIntent:
        """Map AI intent to tracking enum."""
        if not intent:
            return AIIntent.UNKNOWN
        
        try:
            if hasattr(intent, 'value'):
                intent_str = intent.value
            else:
                intent_str = str(intent)
            
            # Map string values to tracking enums
            mapping = {
                'POSITIVE': AIIntent.POSITIVE,
                'NEGATIVE': AIIntent.NEGATIVE,
                'SERVICE_INQUIRY': AIIntent.SERVICE_INQUIRY,
                'OUT_OF_OFFICE': AIIntent.OUT_OF_OFFICE,
                'EMAIL_INVALID': AIIntent.EMAIL_INVALID,
                'NO_LONGER_WORKS': AIIntent.NO_LONGER_WORKS
            }
            
            return mapping.get(intent_str.upper(), AIIntent.UNKNOWN)
            
        except Exception:
            return AIIntent.UNKNOWN
    
    def _determine_forwarding_reason(self, scenario_type: ScenarioType) -> str:
        """Determine forwarding reason based on scenario type."""
        reason_mapping = {
            ScenarioType.SCENARIO_6: "Negative customer response requiring attention",
            ScenarioType.SCENARIO_7: "Customer service inquiry requiring assistance", 
            ScenarioType.SCENARIO_10: "Contact no longer works at company - requires attention"
        }
        
        return reason_mapping.get(scenario_type, "Email forwarding for manual review")
    
    def _create_fallback_record(
        self, 
        email_data: Any, 
        processing_result: Any,
        error_message: str
    ) -> ScenarioProcessingRecord:
        """Create minimal fallback record when transformation fails."""
        try:
            return ScenarioProcessingRecord(
                processing_id=getattr(processing_result, 'processing_id', str(uuid.uuid4())),
                email_id=getattr(email_data, 'id', 'unknown'),
                sender_email=self._safe_extract_sender_email(email_data),
                received_datetime=getattr(email_data, 'received_datetime', datetime.now(timezone.utc)),
                process_success=False,
                process_error=f"Data transformation failed: {error_message}",
                scenario_type=ScenarioType.UNKNOWN
            )
        except Exception as e:
            # Ultimate fallback - minimal valid record
            return ScenarioProcessingRecord(
                processing_id=str(uuid.uuid4()),
                email_id='transformation_error',
                sender_email='error@unknown.com',
                received_datetime=datetime.now(timezone.utc),
                process_success=False,
                process_error=f"Complete transformation failure: {str(e)}"
            )