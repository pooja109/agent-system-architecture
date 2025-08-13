"""
Mock Service Provider - Simulates real services for demos
"""

import asyncio
import random
from typing import Dict, Any
from datetime import datetime
import uuid


class MockServiceProvider:
    """Provides mock implementations of all services."""
    
    def __init__(self, realistic_timing: bool = True) -> None:
        """Initialize mock service provider with response times."""
        if realistic_timing:
            # Realistic timing that matches live system performance
            self.response_times = {
                'email': random.uniform(0.5, 1.2),      # Email processing: 0.5-1.2s
                'ai': random.uniform(1.0, 2.5),         # AI classification: 1-2.5s  
                'salesforce': random.uniform(0.8, 1.8), # Salesforce API: 0.8-1.8s
                'databricks': random.uniform(2.5, 4.0), # Database queries: 2.5-4s
                'key_vault': random.uniform(0.3, 0.7),  # Key Vault: 0.3-0.7s
                'response': random.uniform(0.2, 0.5),   # Response generation: 0.2-0.5s
                'connection_pool': random.uniform(3.5, 5.0), # Pool initialization: 3.5-5s
            }
        else:
            # Fast timing for quick demos
            self.response_times = {
                'email': 0.1,
                'ai': 0.3,
                'salesforce': 0.2,
                'databricks': 0.4,
                'key_vault': 0.1,
                'response': 0.1,
                'connection_pool': 0.5,
            }
    
    # ============================================================================
    # CORE SERVICE METHODS
    # ============================================================================
    
    async def receive_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate receiving an email."""
        await asyncio.sleep(self.response_times['email'])
        
        return {
            'id': str(uuid.uuid4()),
            'subject': email_data.get('subject', 'Test Email'),
            'from': email_data.get('from', 'customer@example.com'),
            'body': email_data.get('body', 'Test email content'),
            'received': datetime.now().isoformat()
        }
    
    async def classify_intent(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate AI intent classification."""
        await asyncio.sleep(self.response_times['ai'])
        
        # Determine intent based on email subject to match CORRECT scenario categories
        subject = email.get('subject', '').lower()
        body = email.get('body', '').lower()
        
        if 'interesting' in subject or 'interested' in body:
            classification = 'positive_response'
        elif 'stop contacting' in subject or 'stop' in subject:
            classification = 'negative_response'
        elif 'question about' in subject or 'order' in subject:
            classification = 'service_inquiry'
        elif 'out of office' in subject or 'automatic reply' in subject:
            classification = 'out_of_office'
        elif 'delivery status notification' in subject or 'bounce' in body:
            classification = 'invalid_email'
        elif 'no longer works' in body or 'left' in body:
            classification = 'no_longer_works'
        else:
            classification = 'general'
        
        return {
            'classification': classification,
            'confidence': round(random.uniform(0.85, 0.99), 2),
            'tokens_used': random.randint(200, 500),
            'processing_time': self.response_times['ai']
        }
    
    async def create_case(self, email: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Simulate Salesforce case creation."""
        await asyncio.sleep(self.response_times['salesforce'])
        
        # Generate mock case ID
        case_id = f"CS{random.randint(10000, 99999)}"
        return case_id
    
    # ============================================================================
    # BUSINESS LOGIC METHODS
    # ============================================================================
    
    async def send_response(self, email: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate sending automated response."""
        await asyncio.sleep(self.response_times['response'])
        
        return {
            'sent': True,
            'template': 'service_inquiry_response',
            'recipient': email.get('from')
        }
    
    async def create_engagement(self, email: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Simulate creating positive engagement record."""
        await asyncio.sleep(self.response_times['salesforce'])
        
        engagement_id = f"ENG{random.randint(10000, 99999)}"
        return engagement_id
    
    async def remove_contact(self, email: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Simulate removing contact from lists."""
        await asyncio.sleep(self.response_times['salesforce'])
        
        removal_id = f"REM{random.randint(10000, 99999)}"
        return removal_id
    
    async def update_contact_status(self, email: Dict[str, Any], intent: Dict[str, Any], status: str) -> str:
        """Simulate updating contact status."""
        await asyncio.sleep(self.response_times['salesforce'])
        
        update_id = f"UPD{random.randint(10000, 99999)}"
        return update_id
    
    async def mark_email_invalid(self, email: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Simulate marking email as invalid."""
        await asyncio.sleep(self.response_times['response'])
        
        invalid_id = f"INV{random.randint(10000, 99999)}"
        return invalid_id
    
    # ============================================================================
    # EMAIL NOTIFICATION METHODS
    # ============================================================================
    
    async def send_victoria_grant_notification(self, email: Dict[str, Any], intent: Dict[str, Any], notification_type: str) -> str:
        """Send notification email to Victoria Grant."""
        await asyncio.sleep(self.response_times['email'])
        
        notification_id = f"NOTIFY_VG_{notification_type.upper()}_{random.randint(10000, 99999)}"
        return notification_id
    
    async def send_account_team_notification(self, email: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Send notification to account team."""
        await asyncio.sleep(self.response_times['email'])
        
        notification_id = f"NOTIFY_TEAM_{random.randint(10000, 99999)}"
        return notification_id
    
    # ============================================================================
    # DATABASE UPDATE METHODS
    # ============================================================================
    
    async def update_databricks_assignment(self, email: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Update Databricks assignment tables."""
        await asyncio.sleep(self.response_times['salesforce'])
        
        update_id = f"DB_UPDATE_{random.randint(10000, 99999)}"
        return update_id
    
    # ============================================================================
    # INFRASTRUCTURE SERVICE METHODS
    # ============================================================================
    
    async def initialize_connection_pool(self) -> Dict[str, Any]:
        """Simulate connection pool initialization."""
        await asyncio.sleep(self.response_times['connection_pool'])
        
        return {
            'status': 'initialized',
            'min_connections': 2,
            'max_connections': 5,
            'created_connections': 2,
            'initialization_time': self.response_times['connection_pool']
        }
    
    async def authenticate_key_vault(self) -> Dict[str, Any]:
        """Simulate Azure Key Vault authentication."""
        await asyncio.sleep(self.response_times['key_vault'])
        
        return {
            'vault_url': 'https://mock-keyvault.vault.azure.net/',
            'secret_count': random.randint(45, 55),
            'authentication_time': self.response_times['key_vault']
        }
    
    async def query_databricks(self, query_type: str) -> Dict[str, Any]:
        """Simulate Databricks database queries."""
        await asyncio.sleep(self.response_times['databricks'])
        
        return {
            'query_type': query_type,
            'execution_time': self.response_times['databricks'] * 1000,  # Convert to ms
            'rows_returned': random.randint(1, 5),
            'success': True
        }
    
    # ============================================================================
    # LEGACY COMPATIBILITY METHODS
    # ============================================================================
    
    async def update_contact(self, email: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate updating contact record."""
        await asyncio.sleep(self.response_times['salesforce'])
        
        return {
            'updated': True,
            'contact_id': f"CNT{random.randint(10000, 99999)}",
            'status': 'inactive'
        }