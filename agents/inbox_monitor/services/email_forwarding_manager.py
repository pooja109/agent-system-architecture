"""
Email Forwarding Manager Service
===============================

Manages external email forwarding templates and provides secure template rendering
for email forwarding operations.
"""

import os
import re
import html
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import structlog

try:
    from models.email import Email
    from services.prompt_manager import PromptManager
    from services.template_renderer import TemplateRenderer
    from models.prompt_models import TemplateConfig
    from exceptions.prompt_exceptions import (
        TemplateRenderError,
        PromptNotFoundError,
        PromptValidationError
    )
except ImportError:
    from ..models.email import Email
    from .prompt_manager import PromptManager
    from .template_renderer import TemplateRenderer
    from ..models.prompt_models import TemplateConfig
    from ..exceptions.prompt_exceptions import (
        TemplateRenderError,
        PromptNotFoundError,
        PromptValidationError
    )


class EmailForwardingManager:
    """
    Manages email forwarding templates and provides secure rendering capabilities.
    
    Features:
    - Template loading and caching for email forwarding
    - Secure Python script generation with proper escaping
    - Scenario-specific template selection
    - Comprehensive input validation and sanitization
    - Fallback mechanisms for missing templates
    """
    
    def __init__(self, prompt_manager: Optional[PromptManager] = None):
        """
        Initialize the email forwarding manager.
        
        Args:
            prompt_manager: Optional PromptManager instance (creates default if None)
        """
        self.prompt_manager = prompt_manager or PromptManager()
        self.template_renderer = TemplateRenderer()
        self.logger = structlog.get_logger(__name__)
        
        # Template caching and performance tracking
        self._template_cache: Dict[str, TemplateConfig] = {}
        self._render_count = 0
        self._error_count = 0
        
        # Security settings
        self._max_email_body_length = 50000  # Increased from 10000 for better content retention
        self._max_subject_length = 200
        self._allowed_file_extensions = ['.py']
        
        self.logger.debug("EmailForwardingManager initialized")
    
    async def generate_forwarding_email_content(
        self,
        original_email: Email,
        recipient_email: str,
        recipient_name: str,
        scenario_type: Optional[str] = None,
        reason_override: Optional[str] = None
    ) -> str:
        """
        Generate email content for forwarding using external templates.
        
        Args:
            original_email: The original email to forward
            recipient_email: Email address to forward to
            recipient_name: Name of the recipient
            scenario_type: Optional scenario type for scenario-specific templates
            reason_override: Optional custom reason for forwarding
            
        Returns:
            Formatted email content ready for forwarding
            
        Raises:
            TemplateRenderError: If template rendering fails
            PromptNotFoundError: If required templates are missing
        """
        try:
            self._render_count += 1
            
            # Determine forwarding reason
            if reason_override:
                forwarding_reason = reason_override
            elif scenario_type:
                forwarding_reason = await self._get_scenario_specific_reason(scenario_type)
            else:
                forwarding_reason = "Email forwarding requested"
            
            # Load base email forwarding template
            base_template = await self._load_email_forwarding_template()
            
            # Prepare template variables
            template_variables = {
                "reason": forwarding_reason,
                "sender_email": original_email.sender.email,
                "sender_name": original_email.sender.name or original_email.sender.email,
                "sent_datetime": original_email.received_datetime.strftime('%Y-%m-%d %H:%M:%S UTC'),
                "original_subject": original_email.subject or "No Subject",
                "original_body": self._sanitize_email_body(original_email.body.content if original_email.body else "")
            }
            
            # Render email content
            email_content = self.template_renderer.render_template(
                base_template,
                template_variables,
                strict_mode=True
            )
            
            self.logger.info(
                "Email forwarding content generated successfully",
                recipient_email=recipient_email,
                scenario_type=scenario_type,
                content_length=len(email_content),
                render_count=self._render_count
            )
            
            return email_content
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(
                "Failed to generate email forwarding content",
                error=str(e),
                recipient_email=recipient_email,
                scenario_type=scenario_type,
                error_count=self._error_count
            )
            
            if isinstance(e, (TemplateRenderError, PromptNotFoundError)):
                raise
            else:
                raise TemplateRenderError(f"Email content generation failed: {e}") from e
    
    async def generate_forwarding_script(
        self,
        email_content: str,
        subject: str,
        recipient_email: str,
        recipient_name: str,
        email_agent_path: str
    ) -> str:
        """
        Generate a Python script for email forwarding using external templates.
        
        Args:
            email_content: The email content to send
            subject: Email subject line
            recipient_email: Recipient email address
            recipient_name: Recipient display name
            email_agent_path: Path to the email agent directory
            
        Returns:
            Python script content ready for execution
            
        Raises:
            TemplateRenderError: If script generation fails
            PromptValidationError: If input validation fails
        """
        try:
            # Validate inputs
            self._validate_script_inputs(
                email_content, subject, recipient_email, recipient_name, email_agent_path
            )
            
            # Load script template
            script_template = await self._load_script_template()
            
            # Prepare secure template variables
            template_variables = {
                "email_agent_path": self._sanitize_file_path(email_agent_path),
                "escaped_subject": self._escape_for_python_string(subject),
                "escaped_body_html": self._escape_for_python_triple_quotes(
                    email_content.replace("\n", "<br>")
                ),
                "recipient_email": self._sanitize_email_address(recipient_email),
                "customer_id": "INBOX_MONITOR",
                "customer_name": self._sanitize_display_name(recipient_name),
                "contact_name": self._sanitize_display_name(recipient_name)
            }
            
            # Render script
            script_content = self.template_renderer.render_template(
                script_template,
                template_variables,
                strict_mode=True
            )
            
            self.logger.info(
                "Email forwarding script generated successfully",
                recipient_email=recipient_email,
                script_length=len(script_content)
            )
            
            return script_content
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(
                "Failed to generate email forwarding script",
                error=str(e),
                recipient_email=recipient_email
            )
            
            if isinstance(e, (TemplateRenderError, PromptValidationError)):
                raise
            else:
                raise TemplateRenderError(f"Script generation failed: {e}") from e
    
    async def get_scenario_forwarding_config(self, scenario_type: str) -> Dict[str, Any]:
        """
        Get forwarding configuration for a specific scenario.
        
        Args:
            scenario_type: Type of scenario (e.g., 'negative_response', 'service_inquiry')
            
        Returns:
            Dictionary with scenario-specific forwarding configuration
        """
        try:
            scenario_template = await self._load_scenario_template(scenario_type)
            
            # Extract configuration from template
            config = {
                "forwarding_reason": scenario_template.get("forwarding_reason", "Email forwarding requested"),
                "subject_template": scenario_template.get("subject_template", "FWD: ${original_subject}"),
                "additional_context": scenario_template.get("additional_context", ""),
                "escalation_priority": scenario_template.get("escalation_priority", "medium"),
                "requires_manual_review": scenario_template.get("requires_manual_review", True)
            }
            
            return config
            
        except Exception as e:
            self.logger.warning(
                "Failed to load scenario-specific configuration, using defaults",
                scenario_type=scenario_type,
                error=str(e)
            )
            
            # Return default configuration
            return {
                "forwarding_reason": "Email forwarding requested",
                "subject_template": "FWD: ${original_subject}",
                "additional_context": "",
                "escalation_priority": "medium",
                "requires_manual_review": True
            }
    
    def get_forwarding_statistics(self) -> Dict[str, Any]:
        """Get email forwarding performance statistics."""
        return {
            "total_renders": self._render_count,
            "total_errors": self._error_count,
            "error_rate_percent": (
                (self._error_count / self._render_count * 100) 
                if self._render_count > 0 else 0
            ),
            "cached_templates": len(self._template_cache)
        }
    
    async def _load_email_forwarding_template(self) -> TemplateConfig:
        """Load the base email forwarding template."""
        cache_key = "base_forward_template"
        
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]
        
        try:
            template_config = await self.prompt_manager.load_template(
                "email_forwarding",
                "base_forward_template"
            )
            
            self._template_cache[cache_key] = template_config
            return template_config
            
        except Exception as e:
            self.logger.error(
                "Failed to load base email forwarding template",
                error=str(e)
            )
            raise PromptNotFoundError(
                "Base email forwarding template not found",
                prompt_name="base_forward_template"
            ) from e
    
    async def _load_script_template(self) -> TemplateConfig:
        """Load the Python script generation template."""
        cache_key = "script_template"
        
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]
        
        try:
            template_config = await self.prompt_manager.load_template(
                "email_forwarding",
                "script_template"
            )
            
            self._template_cache[cache_key] = template_config
            return template_config
            
        except Exception as e:
            self.logger.error(
                "Failed to load script generation template",
                error=str(e)
            )
            raise PromptNotFoundError(
                "Script generation template not found",
                prompt_name="script_template"
            ) from e
    
    async def _load_scenario_template(self, scenario_type: str) -> Dict[str, Any]:
        """Load scenario-specific template configuration."""
        cache_key = f"scenario_{scenario_type}"
        
        if cache_key in self._template_cache:
            cached_data = self._template_cache[cache_key]
            if hasattr(cached_data, 'dict'):
                return cached_data.dict()
            else:
                return cached_data
        
        try:
            # Load scenario config directly from YAML file
            scenario_path = Path(self.prompt_manager.prompts_base_path) / "email_forwarding" / f"{scenario_type}.yaml"
            
            if scenario_path.exists():
                with open(scenario_path, 'r', encoding='utf-8') as f:
                    scenario_data = yaml.safe_load(f)
                
                # Cache the configuration
                self._template_cache[cache_key] = scenario_data
                
                return scenario_data
            else:
                self.logger.warning(
                    "Scenario template file not found",
                    scenario_type=scenario_type,
                    path=str(scenario_path)
                )
                return {}
            
        except Exception as e:
            self.logger.warning(
                "Failed to load scenario-specific template",
                scenario_type=scenario_type,
                error=str(e)
            )
            # Return empty dict to trigger default behavior
            return {}
    
    async def _get_scenario_specific_reason(self, scenario_type: str) -> str:
        """Get scenario-specific forwarding reason."""
        scenario_config = await self.get_scenario_forwarding_config(scenario_type)
        return scenario_config.get("forwarding_reason", "Email forwarding requested")
    
    def _sanitize_email_body(self, body: str) -> str:
        """Sanitize email body content for safe template rendering."""
        if not body:
            return ""
        
        # Truncate if too long
        if len(body) > self._max_email_body_length:
            body = body[:self._max_email_body_length] + "\n... [Content truncated for forwarding]"
        
        # Remove potentially dangerous content
        body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.IGNORECASE | re.DOTALL)
        body = re.sub(r'javascript:', '', body, flags=re.IGNORECASE)
        
        # Remove SQL injection patterns
        sql_patterns = [
            r';\s*drop\s+table\s+', r';\s*delete\s+from\s+', r';\s*update\s+.*\s+set\s+',
            r';\s*insert\s+into\s+', r';\s*create\s+table\s+', r';\s*alter\s+table\s+',
            r'union\s+select\s+', r'\/\*.*?\*\/', r'--.*$'
        ]
        for pattern in sql_patterns:
            body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove other injection patterns
        injection_patterns = [
            r'<\?php.*?\?>', r'<%.*?%>', r'\${.*?}', r'#\{.*?\}'
        ]
        for pattern in injection_patterns:
            body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.DOTALL)
        
        return body.strip()
    
    def _escape_for_python_string(self, text: str) -> str:
        """Escape text for safe inclusion in Python string literals."""
        if not text:
            return ""
        
        # Truncate if too long
        if len(text) > self._max_subject_length:
            text = text[:self._max_subject_length] + "..."
        
        # Escape quotes and special characters
        text = text.replace('\\', '\\\\')  # Escape backslashes
        text = text.replace('"', '\\"')    # Escape double quotes
        text = text.replace('\n', '\\n')   # Escape newlines
        text = text.replace('\r', '\\r')   # Escape carriage returns
        text = text.replace('\t', '\\t')   # Escape tabs
        
        return text
    
    def _escape_for_python_triple_quotes(self, text: str) -> str:
        """Escape text for safe inclusion in Python triple-quoted strings."""
        if not text:
            return ""
        
        # Replace triple quotes to prevent string termination
        text = text.replace('"""', '\\"\\"\\"')
        text = text.replace("'''", "\\'\\'\\'")
        
        # Escape backslashes
        text = text.replace('\\', '\\\\')
        
        return text
    
    def _sanitize_file_path(self, file_path: str) -> str:
        """Sanitize file path for safe use in templates."""
        if not file_path:
            raise PromptValidationError("File path cannot be empty")
        
        # Basic security check - check original path for suspicious patterns BEFORE resolution
        suspicious_patterns = ['..', '~', '$', '`', ';', '|', '&']
        
        for pattern in suspicious_patterns:
            if pattern in file_path:
                raise PromptValidationError(f"File path contains suspicious pattern: {pattern}")
        
        # Additional security check for sensitive system paths
        sensitive_paths = ['/etc/', '/usr/bin/', '/bin/', '/sbin/', '/root/', '/var/', '/sys/', '/proc/']
        file_path_lower = file_path.lower()
        
        for sensitive in sensitive_paths:
            if file_path_lower.startswith(sensitive):
                raise PromptValidationError(f"Access to system path not allowed: {file_path}")
        
        # Resolve to absolute path after security check
        path = Path(file_path).resolve()
        return str(path)
    
    def _sanitize_email_address(self, email: str) -> str:
        """Sanitize email address for safe use in templates."""
        if not email:
            raise PromptValidationError("Email address cannot be empty")
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise PromptValidationError(f"Invalid email address format: {email}")
        
        return email.lower().strip()
    
    def _sanitize_display_name(self, name: str) -> str:
        """Sanitize display name for safe use in templates."""
        if not name:
            return "Unknown"
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\'\\\r\n\t]', '', name)
        
        # Truncate if too long
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        
        return sanitized.strip() or "Unknown"
    
    def _validate_script_inputs(
        self,
        email_content: str,
        subject: str,
        recipient_email: str,
        recipient_name: str,
        email_agent_path: str
    ) -> None:
        """Validate inputs for script generation."""
        if not email_content:
            raise PromptValidationError("Email content cannot be empty")
        
        if not subject:
            raise PromptValidationError("Subject cannot be empty")
        
        if not recipient_email:
            raise PromptValidationError("Recipient email cannot be empty")
        
        if not recipient_name:
            raise PromptValidationError("Recipient name cannot be empty")
        
        if not email_agent_path:
            raise PromptValidationError("Email agent path cannot be empty")
        
        # Validate email agent path exists
        if not Path(email_agent_path).exists():
            raise PromptValidationError(f"Email agent path does not exist: {email_agent_path}")