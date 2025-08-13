"""
Pydantic Models for Prompt Configuration Validation
=================================================

Defines the structure and validation rules for external prompt configurations.
"""

from typing import Optional, Dict, List, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, timezone


class AgentConfig(BaseModel):
    """Configuration metadata for an AI agent."""
    
    name: str = Field(..., description="Agent name identifier")
    description: str = Field(..., description="Agent description and purpose")
    version: str = Field(..., description="Semantic version of the agent configuration")
    created_date: Optional[datetime] = Field(None, description="Configuration creation date")
    updated_date: Optional[datetime] = Field(None, description="Last update date")
    author: Optional[str] = Field(None, description="Configuration author")
    
    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v):
        """Validate semantic version format (x.y.z)."""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Version must be in semantic version format (x.y.z)')
        return v


class ConfidenceScoring(BaseModel):
    """Configuration for confidence scoring guidelines."""
    
    high: Dict[str, Union[List[float], str]] = Field(
        ..., 
        description="High confidence range and description"
    )
    medium: Dict[str, Union[List[float], str]] = Field(
        ..., 
        description="Medium confidence range and description"
    )
    low: Dict[str, Union[List[float], str]] = Field(
        ..., 
        description="Low confidence range and description"
    )
    very_low: Dict[str, Union[List[float], str]] = Field(
        ..., 
        description="Very low confidence range and description"
    )
    
    @field_validator('high', 'medium', 'low', 'very_low')
    @classmethod
    def validate_confidence_structure(cls, v):
        """Validate confidence scoring structure."""
        if 'range' not in v or 'description' not in v:
            raise ValueError('Confidence scoring must have range and description fields')
        
        if len(v['range']) != 2:
            raise ValueError('Confidence range must have exactly two values [min, max]')
        
        min_val, max_val = v['range']
        if not (0.0 <= min_val <= max_val <= 1.0):
            raise ValueError('Confidence range values must be between 0.0 and 1.0')
        
        return v


class ResponseFormat(BaseModel):
    """Configuration for expected response format."""
    
    type: str = Field(..., description="Response format type (e.g., 'json')")
    response_schema: Dict[str, str] = Field(..., description="Schema definition for response")
    
    @field_validator('type')
    @classmethod
    def validate_response_type(cls, v):
        """Validate response format type."""
        allowed_types = ['json', 'text', 'xml']
        if v.lower() not in allowed_types:
            raise ValueError(f'Response type must be one of: {allowed_types}')
        return v.lower()


class PromptConfig(BaseModel):
    """Main configuration model for agent prompts."""
    
    agent_config: AgentConfig = Field(..., description="Agent metadata configuration")
    system_instructions: str = Field(
        ..., 
        description="Complete system instructions for the agent",
        min_length=10
    )
    confidence_scoring: Optional[ConfidenceScoring] = Field(
        None, 
        description="Confidence scoring guidelines"
    )
    response_format: Optional[ResponseFormat] = Field(
        None, 
        description="Expected response format specification"
    )
    examples: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="Example inputs and expected outputs"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional metadata for the prompt"
    )
    
    @field_validator('system_instructions')
    @classmethod
    def validate_instructions_content(cls, v):
        """Validate system instructions content."""
        if not v.strip():
            raise ValueError('System instructions cannot be empty')
        
        # Check for required sections (customize based on your needs)
        required_sections = [
            "INTENT CATEGORIES",
            "CONFIDENCE SCORING", 
            "RESPONSE FORMAT"
        ]
        
        for section in required_sections:
            if section not in v.upper():
                raise ValueError(f'System instructions must contain {section} section')
        
        return v.strip()


class TemplateVariable(BaseModel):
    """Definition of a template variable."""
    
    name: str = Field(..., description="Variable name")
    description: str = Field(..., description="Variable description and purpose")
    type: str = Field(default="string", description="Variable data type")
    required: bool = Field(default=True, description="Whether variable is required")
    default_value: Optional[Any] = Field(None, description="Default value if not provided")
    
    @field_validator('type')
    @classmethod
    def validate_variable_type(cls, v):
        """Validate variable type."""
        allowed_types = ['string', 'integer', 'float', 'boolean', 'list', 'dict']
        if v.lower() not in allowed_types:
            raise ValueError(f'Variable type must be one of: {allowed_types}')
        return v.lower()


class TemplateConfig(BaseModel):
    """Configuration model for prompt templates."""
    
    template_version: str = Field(..., description="Template version")
    template: str = Field(
        ..., 
        description="Template string with variable placeholders",
        min_length=10
    )
    variables: Optional[Dict[str, Union[str, TemplateVariable]]] = Field(
        None, 
        description="Template variable definitions"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional template metadata"
    )
    
    @field_validator('template')
    @classmethod
    def validate_template_content(cls, v):
        """Validate template content."""
        if not v.strip():
            raise ValueError('Template content cannot be empty')
        return v.strip()
    
    @field_validator('template_version')
    @classmethod
    def validate_template_version(cls, v):
        """Validate template version format."""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Template version must be in semantic version format (x.y.z)')
        return v


class PromptValidationResult(BaseModel):
    """Result of prompt validation operations."""
    
    prompt_name: str = Field(..., description="Name of validated prompt")
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="When validation was performed"
    )
    
    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True
    )