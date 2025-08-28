"""
Custom Exceptions for Prompt Management Operations
================================================

Defines specific exception types for different prompt-related error scenarios.
"""


class PromptManagerError(Exception):
    """Base exception for all prompt management errors."""
    
    def __init__(self, message: str, prompt_name: str = None, details: dict = None):
        super().__init__(message)
        self.prompt_name = prompt_name
        self.details = details or {}
        self.message = message
    
    def __str__(self):
        base_msg = self.message
        if self.prompt_name:
            base_msg = f"[{self.prompt_name}] {base_msg}"
        
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg = f"{base_msg} (Details: {detail_str})"
        
        return base_msg


class PromptNotFoundError(PromptManagerError):
    """Raised when a requested prompt file or directory cannot be found."""
    
    def __init__(self, message: str, prompt_name: str = None, file_path: str = None):
        details = {"file_path": file_path} if file_path else {}
        super().__init__(message, prompt_name, details)


class PromptValidationError(PromptManagerError):
    """Raised when prompt configuration fails validation."""
    
    def __init__(self, message: str, prompt_name: str = None, validation_errors: list = None):
        details = {"validation_errors": validation_errors} if validation_errors else {}
        super().__init__(message, prompt_name, details)


class PromptCacheError(PromptManagerError):
    """Raised when cache operations fail."""
    
    def __init__(self, message: str, prompt_name: str = None, cache_operation: str = None):
        details = {"cache_operation": cache_operation} if cache_operation else {}
        super().__init__(message, prompt_name, details)


class TemplateRenderError(PromptManagerError):
    """Raised when template rendering fails."""
    
    def __init__(self, message: str, template_name: str = None, missing_variables: list = None):
        details = {"missing_variables": missing_variables} if missing_variables else {}
        super().__init__(message, template_name, details)


class SchemaValidationError(PromptManagerError):
    """Raised when YAML schema validation fails."""
    
    def __init__(self, message: str, schema_type: str = None, field_errors: dict = None):
        details = {"schema_type": schema_type}
        if field_errors:
            details["field_errors"] = field_errors
        super().__init__(message, None, details)