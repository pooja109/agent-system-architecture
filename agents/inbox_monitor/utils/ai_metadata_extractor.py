"""
AI Metadata Extractor
=====================

Utilities for extracting AI model version information from
Azure AI Foundry responses and processing results.
Note: Token usage fields were removed as they don't exist in the database table.
"""

from typing import Dict, Any, Optional, Tuple
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)


def extract_ai_metadata(intent_result: Optional[Any], processing_result: Optional[Any]) -> Dict[str, Any]:
    """
    Extract AI model version from AI processing results.
    Note: Token usage fields were removed as they don't exist in the database table.
    
    Args:
        intent_result: Intent classification result from Azure AI Foundry
        processing_result: General processing result that may contain AI metadata
    
    Returns:
        Dict containing ai_model_version (token fields removed)
    """
    
    metadata = {
        'ai_model_version': None
    }
    
    try:
        # Extract model version from intent result
        model_version = extract_model_version_from_intent(intent_result)
        if model_version:
            metadata['ai_model_version'] = model_version
        
        # Extract model version from processing result if not found
        if not metadata['ai_model_version']:
            model_version = extract_model_version_from_processing(processing_result)
            if model_version:
                metadata['ai_model_version'] = model_version
        
        logger.debug(f"Extracted AI metadata: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting AI metadata: {e}")
        return metadata


def extract_model_version_from_intent(intent_result: Optional[Any]) -> Optional[str]:
    """
    Extract AI model version from intent classification result.
    
    Args:
        intent_result: Intent classification result from Azure AI Foundry
        
    Returns:
        Model version string or None if not found
    """
    
    if not intent_result:
        return None
    
    try:
        # Check for model information in various response formats
        if hasattr(intent_result, 'model'):
            return str(intent_result.model)
        
        if hasattr(intent_result, 'model_version'):
            return str(intent_result.model_version)
        
        # Check in metadata
        if hasattr(intent_result, 'metadata'):
            metadata = intent_result.metadata
            if isinstance(metadata, dict):
                return metadata.get('model_version') or metadata.get('model')
        
        # Check raw response if available
        if hasattr(intent_result, 'raw_response'):
            raw = intent_result.raw_response
            if isinstance(raw, dict):
                return raw.get('model') or raw.get('model_version')
        
        logger.debug("No model version found in intent result")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting model version from intent: {e}")
        return None


def extract_model_version_from_processing(processing_result: Optional[Any]) -> Optional[str]:
    """
    Extract AI model version from processing result.
    
    Args:
        processing_result: General processing result that may contain AI metadata
        
    Returns:
        Model version string or None if not found
    """
    
    if not processing_result:
        return None
    
    try:
        # Check for model information in processing result
        if hasattr(processing_result, 'ai_model_version'):
            return str(processing_result.ai_model_version)
        
        if hasattr(processing_result, 'model_version'):
            return str(processing_result.model_version)
        
        # Check metadata
        if hasattr(processing_result, 'metadata'):
            metadata = processing_result.metadata
            if isinstance(metadata, dict):
                return metadata.get('ai_model_version') or metadata.get('model_version')
        
        # Check processing_metadata
        if hasattr(processing_result, 'processing_metadata'):
            proc_meta = processing_result.processing_metadata
            if isinstance(proc_meta, dict):
                return proc_meta.get('ai_model_version') or proc_meta.get('model_version')
        
        logger.debug("No model version found in processing result")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting model version from processing: {e}")
        return None


# NOTE: Token usage extraction functions have been removed as token fields 
# don't exist in the database schema. Original functions preserved in git history.