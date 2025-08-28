"""
Configuration for environment detection and data extraction.
Provides centralized configuration for hardcoded value fixes.
"""

import os
from typing import Dict, Any
from pydantic import BaseModel, Field


class EnvironmentConfig(BaseModel):
    """Configuration for environment detection and data extraction."""
    
    environment: str = Field(default="development", description="Deployment environment")
    enable_sender_extraction: bool = Field(default=True, description="Enable sender info extraction")
    enable_assignment_reasoning: bool = Field(default=True, description="Enable assignment reasoning extraction")
    max_name_length: int = Field(default=100, description="Maximum length for extracted names")
    max_reasoning_length: int = Field(default=500, description="Maximum length for assignment reasoning")
    
    @classmethod
    def from_environment(cls) -> 'EnvironmentConfig':
        """Create configuration from environment variables."""
        
        return cls(
            environment=detect_environment_from_vars(),
            enable_sender_extraction=os.environ.get('ENABLE_SENDER_EXTRACTION', 'true').lower() == 'true',
            enable_assignment_reasoning=os.environ.get('ENABLE_ASSIGNMENT_REASONING', 'true').lower() == 'true',
            max_name_length=int(os.environ.get('MAX_NAME_LENGTH', '100')),
            max_reasoning_length=int(os.environ.get('MAX_REASONING_LENGTH', '500'))
        )


def detect_environment_from_vars() -> str:
    """Detect environment from various environment variable patterns."""
    
    env_patterns = {
        'ENVIRONMENT': lambda x: x.lower(),
        'ENV': lambda x: x.lower(), 
        'DEPLOYMENT_ENV': lambda x: x.lower(),
        'AZURE_ENV': lambda x: x.lower(),
        'NODE_ENV': lambda x: x.lower()
    }
    
    for var_name, transform in env_patterns.items():
        value = os.environ.get(var_name)
        if value:
            transformed = transform(value)
            if 'prod' in transformed:
                return 'production'
            elif 'test' in transformed or 'staging' in transformed:
                return 'test'
            elif 'dev' in transformed:
                return 'development'
    
    return 'development'


def get_data_extraction_settings() -> Dict[str, Any]:
    """Get current data extraction configuration settings."""
    
    config = EnvironmentConfig.from_environment()
    
    return {
        'environment': config.environment,
        'extraction_enabled': {
            'sender_info': config.enable_sender_extraction,
            'assignment_reasoning': config.enable_assignment_reasoning
        },
        'field_limits': {
            'max_name_length': config.max_name_length,
            'max_reasoning_length': config.max_reasoning_length
        },
        'environment_variables': {
            'ENVIRONMENT': os.environ.get('ENVIRONMENT'),
            'ENV': os.environ.get('ENV'),
            'DEPLOYMENT_ENV': os.environ.get('DEPLOYMENT_ENV'),
            'AZURE_ENV': os.environ.get('AZURE_ENV'),
            'NODE_ENV': os.environ.get('NODE_ENV')
        }
    }