# TEMPLATE: High-Performance External Service Mocks

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

class FastMockGraphAPIClient:
    """High-performance mock for Graph API client with instant responses."""
    
    def __init__(self):
        self.call_count = 0
        self.call_history = []
    
    async def get_inbox_messages(self, *args, **kwargs):
        """Instant mock response for inbox messages."""
        self.call_count += 1
        self.call_history.append(('get_inbox_messages', args, kwargs))
        # Return immediately with mock data
        return {
            'value': [
                {
                    'id': f'mock-message-{self.call_count}',
                    'subject': 'Mock Subject',
                    'body': {'content': 'Mock Body'},
                    'from': {'emailAddress': {'address': 'mock@example.com'}}
                }
            ]
        }
    
    async def move_message(self, message_id, folder_id):
        """Instant mock response for message moving."""
        self.call_history.append(('move_message', message_id, folder_id))
        # Simulate success immediately
        return {'success': True}
    
    async def create_folder(self, folder_name):
        """Instant mock response for folder creation."""
        self.call_history.append(('create_folder', folder_name))
        return {'id': f'mock-folder-{self.call_count}', 'displayName': folder_name}

@pytest.fixture
def fast_graph_client():
    """Fixture providing high-performance Graph API mock."""
    return FastMockGraphAPIClient()

# Mock decorator for entire test classes
def fast_external_service_mocks(cls):
    """Class decorator to apply high-performance mocks to all test methods."""
    
    # Apply mocks to all test methods
    for attr_name in dir(cls):
        if attr_name.startswith('test_'):
            method = getattr(cls, attr_name)
            if callable(method):
                # Wrap with performance mocks
                setattr(cls, attr_name, fast_mock_wrapper(method))
    
    return cls

def fast_mock_wrapper(test_method):
    """Wraps test methods with high-performance mocks."""
    @patch('services.graph_api_client.GraphAPIClient')
    @patch('services.azure_ai_foundry_client.AzureAIFoundryClient')
    @patch('httpx.AsyncClient')
    async def wrapper(mock_httpx, mock_azure, mock_graph, *args, **kwargs):
        # Configure mocks for instant responses
        mock_graph.return_value = FastMockGraphAPIClient()
        mock_azure.return_value = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_httpx.return_value.__aenter__.return_value.get.return_value.json.return_value = {}
        
        return await test_method(*args, **kwargs)
    
    return wrapper