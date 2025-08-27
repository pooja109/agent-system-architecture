"""
Template Rendering Service for Dynamic Prompt Generation
=======================================================

Provides template rendering capabilities for external prompt files
with variable substitution, validation, and error handling.
"""

import re
from typing import Dict, Any, Optional, List, Union
import structlog
from string import Template

try:
    from models.prompt_models import TemplateConfig
    from exceptions.prompt_exceptions import TemplateRenderError, PromptValidationError
except ImportError:
    from ..models.prompt_models import TemplateConfig
    from ..exceptions.prompt_exceptions import TemplateRenderError, PromptValidationError


class TemplateRenderer:
    """
    Renders prompt templates with variable substitution and validation.
    
    Features:
    - Safe variable substitution using string.Template
    - Variable validation against template schema
    - Type coercion and formatting
    - Missing variable detection and error reporting
    - Performance optimization with template compilation
    """
    
    def __init__(self):
        """Initialize the template renderer."""
        self.logger = structlog.get_logger(__name__)
        self._compiled_templates: Dict[str, Template] = {}
        self._render_count = 0
        self._error_count = 0
    
    def render_template(
        self, 
        template_config: TemplateConfig, 
        variables: Dict[str, Any],
        strict_mode: bool = True
    ) -> str:
        """
        Render a template with provided variables.
        
        Args:
            template_config: Template configuration with template string and variable definitions
            variables: Dictionary of variables to substitute in template
            strict_mode: Whether to require all template variables to be provided
            
        Returns:
            Rendered template string with variables substituted
            
        Raises:
            TemplateRenderError: If template rendering fails
            PromptValidationError: If variable validation fails
        """
        try:
            self._render_count += 1
            template_key = f"{template_config.template_version}_{hash(template_config.template)}"
            
            # Compile template if not cached
            if template_key not in self._compiled_templates:
                self._compiled_templates[template_key] = Template(template_config.template)
            
            compiled_template = self._compiled_templates[template_key]
            
            # Validate and process variables
            processed_variables = self._process_variables(
                variables, 
                template_config.variables or {},
                strict_mode
            )
            
            # Render template
            try:
                if strict_mode:
                    rendered = compiled_template.substitute(processed_variables)
                else:
                    rendered = compiled_template.safe_substitute(processed_variables)
            except KeyError as e:
                missing_var = str(e).strip("'\"")
                self._error_count += 1
                raise TemplateRenderError(
                    f"Missing required template variable: {missing_var}",
                    template_name=f"template_v{template_config.template_version}",
                    missing_variables=[missing_var]
                ) from e
            except ValueError as e:
                self._error_count += 1
                raise TemplateRenderError(
                    f"Template syntax error: {e}",
                    template_name=f"template_v{template_config.template_version}"
                ) from e
            
            # Final validation and cleanup
            rendered_clean = self._post_process_rendered_template(rendered)
            
            self.logger.debug(
                "Template rendered successfully",
                template_version=template_config.template_version,
                variable_count=len(processed_variables),
                rendered_length=len(rendered_clean),
                render_count=self._render_count
            )
            
            return rendered_clean
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(
                "Template rendering failed",
                template_version=template_config.template_version if template_config else "unknown",
                error=str(e),
                variables_provided=list(variables.keys()) if variables else [],
                error_count=self._error_count
            )
            
            if isinstance(e, (TemplateRenderError, PromptValidationError)):
                raise
            else:
                raise TemplateRenderError(f"Template rendering failed: {e}") from e
    
    def validate_template_variables(
        self, 
        template_config: TemplateConfig, 
        variables: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Validate template variables without rendering.
        
        Args:
            template_config: Template configuration
            variables: Variables to validate
            
        Returns:
            Dictionary with validation results: {"errors": [...], "warnings": [...]}
        """
        validation_results = {"errors": [], "warnings": []}
        template_vars = template_config.variables or {}
        
        try:
            # Extract variables from template string
            template_var_names = self._extract_template_variables(template_config.template)
            
            # Check for required variables
            for var_name in template_var_names:
                if var_name not in variables:
                    if var_name in template_vars:
                        var_def = template_vars[var_name]
                        if isinstance(var_def, dict) and var_def.get("required", True):
                            validation_results["errors"].append(
                                f"Required variable '{var_name}' is missing"
                            )
                        else:
                            validation_results["warnings"].append(
                                f"Optional variable '{var_name}' not provided"
                            )
                    else:
                        validation_results["warnings"].append(
                            f"Template variable '{var_name}' has no definition"
                        )
            
            # Check for unused variables
            for var_name in variables:
                if var_name not in template_var_names:
                    validation_results["warnings"].append(
                        f"Provided variable '{var_name}' is not used in template"
                    )
            
            # Validate variable types and values
            for var_name, var_value in variables.items():
                if var_name in template_vars:
                    var_def = template_vars[var_name]
                    if isinstance(var_def, dict):
                        type_errors = self._validate_variable_type(var_name, var_value, var_def)
                        validation_results["errors"].extend(type_errors)
            
        except Exception as e:
            validation_results["errors"].append(f"Validation process failed: {e}")
        
        return validation_results
    
    def get_rendering_statistics(self) -> Dict[str, Any]:
        """Get template rendering performance statistics."""
        return {
            "total_renders": self._render_count,
            "total_errors": self._error_count,
            "error_rate_percent": (
                (self._error_count / self._render_count * 100) 
                if self._render_count > 0 else 0
            ),
            "compiled_templates_cached": len(self._compiled_templates)
        }
    
    def clear_template_cache(self) -> None:
        """Clear compiled template cache."""
        self._compiled_templates.clear()
        self.logger.info("Template cache cleared")
    
    def _process_variables(
        self, 
        variables: Dict[str, Any], 
        variable_definitions: Dict[str, Any],
        strict_mode: bool
    ) -> Dict[str, str]:
        """Process and validate variables before template rendering."""
        processed = {}
        
        for var_name, var_value in variables.items():
            try:
                # Apply formatting rules if defined
                if var_name in variable_definitions:
                    var_def = variable_definitions[var_name]
                    if isinstance(var_def, dict):
                        processed_value = self._format_variable_value(var_value, var_def)
                    else:
                        processed_value = str(var_value)
                else:
                    processed_value = str(var_value)
                
                # Clean up the value
                processed_value = processed_value.strip() if processed_value else ""
                
                # Apply additional formatting rules
                processed[var_name] = self._apply_formatting_rules(var_name, processed_value)
                
            except Exception as e:
                if strict_mode:
                    raise PromptValidationError(
                        f"Variable processing failed for '{var_name}': {e}"
                    ) from e
                else:
                    # In non-strict mode, use string representation as fallback
                    processed[var_name] = str(var_value) if var_value is not None else ""
                    self.logger.warning(
                        "Variable processing failed, using fallback",
                        variable_name=var_name,
                        error=str(e)
                    )
        
        return processed
    
    def _format_variable_value(self, value: Any, variable_definition: Dict[str, Any]) -> str:
        """Format a variable value according to its definition."""
        var_type = variable_definition.get("type", "string").lower()
        
        if value is None:
            default_value = variable_definition.get("default_value")
            if default_value is not None:
                return str(default_value)
            elif variable_definition.get("required", True):
                raise PromptValidationError(
                    f"Required variable has None value and no default"
                )
            else:
                return ""
        
        # Type-specific formatting
        if var_type == "string":
            return str(value)
        elif var_type == "integer":
            try:
                return str(int(value))
            except (ValueError, TypeError):
                raise PromptValidationError(f"Cannot convert '{value}' to integer")
        elif var_type == "float":
            try:
                return str(float(value))
            except (ValueError, TypeError):
                raise PromptValidationError(f"Cannot convert '{value}' to float")
        elif var_type == "boolean":
            return str(bool(value)).lower()
        elif var_type in ["list", "array"]:
            if isinstance(value, (list, tuple)):
                return ", ".join(str(item) for item in value)
            else:
                return str(value)
        else:
            return str(value)
    
    def _apply_formatting_rules(self, var_name: str, value: str) -> str:
        """Apply specific formatting rules based on variable name."""
        # Email-specific formatting
        if "email" in var_name.lower():
            return value.lower().strip()
        
        # Subject-specific formatting
        if "subject" in var_name.lower():
            return value.strip() if value.strip() else "No Subject"
        
        # Body-specific formatting
        if "body" in var_name.lower():
            # Truncate if too long (increased from 2000 for better content retention)
            max_length = 10000
            if len(value) > max_length:
                return value[:max_length] + "... [truncated]"
            return value
        
        # Domain-specific formatting (only for actual domain values, not domain types/classifications)
        if var_name.lower() in ["domain", "sender_domain", "email_domain"]:
            return value.lower().strip()
        
        return value
    
    def _extract_template_variables(self, template_string: str) -> List[str]:
        """Extract variable names from template string."""
        # Find all ${variable_name} patterns
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, template_string)
        
        # Also find $variable_name patterns (without braces)
        pattern2 = r'\$([a-zA-Z_][a-zA-Z0-9_]*)'
        matches2 = re.findall(pattern2, template_string)
        
        # Combine and deduplicate
        all_variables = list(set(matches + matches2))
        
        return all_variables
    
    def _validate_variable_type(
        self, 
        var_name: str, 
        var_value: Any, 
        var_definition: Dict[str, Any]
    ) -> List[str]:
        """Validate variable type against its definition."""
        errors = []
        expected_type = var_definition.get("type", "string").lower()
        
        try:
            if expected_type == "string":
                if not isinstance(var_value, (str, int, float, bool)):
                    errors.append(f"Variable '{var_name}' must be convertible to string")
            elif expected_type == "integer":
                int(var_value)
            elif expected_type == "float":
                float(var_value)
            elif expected_type == "boolean":
                if not isinstance(var_value, (bool, int, str)):
                    errors.append(f"Variable '{var_name}' must be convertible to boolean")
            elif expected_type in ["list", "array"]:
                if not isinstance(var_value, (list, tuple, str)):
                    errors.append(f"Variable '{var_name}' must be a list, tuple, or string")
            
            # Check enum values
            if "enum" in var_definition:
                allowed_values = var_definition["enum"]
                if var_value not in allowed_values:
                    errors.append(
                        f"Variable '{var_name}' value '{var_value}' not in allowed values: {allowed_values}"
                    )
        
        except (ValueError, TypeError) as e:
            errors.append(f"Variable '{var_name}' type validation failed: {e}")
        
        return errors
    
    def _post_process_rendered_template(self, rendered: str) -> str:
        """Apply final cleanup and validation to rendered template."""
        # Remove excessive whitespace
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', rendered)
        
        # Ensure proper line endings
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        
        # Strip leading/trailing whitespace but preserve internal structure
        cleaned = cleaned.strip()
        
        return cleaned