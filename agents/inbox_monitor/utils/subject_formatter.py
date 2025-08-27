"""
Subject Formatter Utility
=========================

Formats Support Request subjects with Account Name integration for Phase 5 requirements.
Provides "AI Agent Led INQUIRY | <Account Name>" formatting with fallback handling.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

class SubjectFormatter:
    """Formats Support Request subjects with Account Name integration"""
    
    def __init__(self):
        self.ai_inquiry_template = "AI Agent Led INQUIRY | {account_name}"
        self.fallback_template = "AI Agent Led INQUIRY | {fallback_name}"
        self.max_subject_length = 255  # Salesforce Subject field limit
        
    def format_ai_inquiry_subject(
        self, 
        account_name: str, 
        original_subject: Optional[str] = None
    ) -> str:
        """
        Format subject line as "AI Agent Led INQUIRY | <Account Name>"
        With fallback handling for missing/invalid account names
        """
        
        try:
            # Clean and validate account name
            cleaned_account_name = self._clean_account_name(account_name)
            
            if cleaned_account_name:
                # Use account name in template
                formatted_subject = self.ai_inquiry_template.format(account_name=cleaned_account_name)
                
                # Validate length and truncate if necessary
                if len(formatted_subject) <= self.max_subject_length:
                    logger.info("Formatted subject with account name: %s", formatted_subject)
                    return formatted_subject
                else:
                    # Truncate account name if too long
                    max_account_length = self.max_subject_length - len("AI Agent Led INQUIRY | ")
                    truncated_account = cleaned_account_name[:max_account_length-3] + "..."
                    formatted_subject = self.ai_inquiry_template.format(account_name=truncated_account)
                    
                    logger.warning("Account name truncated for subject length: %s", formatted_subject)
                    return formatted_subject
            else:
                # Use fallback format when account name is not available
                return self._create_fallback_subject(original_subject)
                
        except Exception as e:
            logger.error("Error formatting AI inquiry subject: %s", e)
            return self._create_fallback_subject(original_subject)
    
    def _clean_account_name(self, account_name: str) -> str:
        """Clean and validate account name for subject line usage"""
        
        if not account_name or not isinstance(account_name, str):
            return ""
        
        # Clean the account name
        cleaned = account_name.strip()
        
        # Remove common redundant prefixes
        prefixes_to_remove = ['Account:', 'Company:', 'Organization:']
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        # Remove excessive whitespace and normalize
        cleaned = ' '.join(cleaned.split())
        
        # Remove problematic characters for email subjects
        cleaned = re.sub(r'[<>"\r\n\t]', '', cleaned)
        
        # Validate minimum length and content
        if len(cleaned) < 2:
            return ""
        
        # Reasonable length limit for account name portion
        if len(cleaned) > 100:
            cleaned = cleaned[:97] + "..."
        
        return cleaned
    
    def _create_fallback_subject(self, original_subject: Optional[str] = None) -> str:
        """Create fallback subject when account name is not available"""
        
        # Try to extract meaningful context from original subject
        if original_subject and isinstance(original_subject, str):
            cleaned_original = original_subject.strip()
            
            # Look for company/account indicators in the original subject
            account_indicators = re.findall(r'\b([A-Z][a-zA-Z\s&]+(?:Inc|LLC|Corp|Company|Ltd))\b', cleaned_original)
            if account_indicators:
                potential_account = account_indicators[0]
                if len(potential_account) <= 50:
                    formatted_subject = self.ai_inquiry_template.format(account_name=potential_account)
                    if len(formatted_subject) <= self.max_subject_length:
                        logger.info("Used original subject account indicator: %s", formatted_subject)
                        return formatted_subject
            
            # Use first few words as context
            words = cleaned_original.split()[:3]
            if words and len(' '.join(words)) <= 30:
                context = ' '.join(words)
                fallback_name = f"{context} Inquiry"
                formatted_subject = self.fallback_template.format(fallback_name=fallback_name)
                if len(formatted_subject) <= self.max_subject_length:
                    logger.info("Used original subject context: %s", formatted_subject)
                    return formatted_subject
        
        # Default fallback
        default_fallback = "Customer Inquiry"
        formatted_subject = self.fallback_template.format(fallback_name=default_fallback)
        
        logger.info("Used default fallback subject: %s", formatted_subject)
        return formatted_subject
    
    def validate_subject_format(self, subject: str) -> bool:
        """Validate that subject meets business requirements"""
        
        if not subject or len(subject) > self.max_subject_length:
            return False
        
        if not subject.startswith("AI Agent Led INQUIRY"):
            return False
        
        # Check for problematic characters
        if re.search(r'[<>"\r\n\t]', subject):
            return False
        
        return True