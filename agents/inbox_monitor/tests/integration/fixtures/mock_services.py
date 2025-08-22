"""
Mock Services for Integration Testing
=====================================

Mock service implementations for testing logging integration without
external dependencies.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock

from services.logging.api_client_logger import APIClientLoggerMixin
from services.logging.business_logic_logger import BusinessLogicLoggerMixin
from services.logging.database_logger import DatabaseLoggerMixin
from services.logging.service_logger_mixin import ServiceLoggerMixin


class MockGraphAPIClient(APIClientLoggerMixin):
    """Mock Graph API client for testing."""
    
    def __init__(self, test_mode: bool = True):
        """Initialize mock client."""
        self.__init_logging__("mock_graph_client")
        self.test_mode = test_mode
        self._authenticated = False
        self.mock_messages = []
    
    async def authenticate(self) -> bool:
        """Mock authentication."""
        correlation_id = self.log_authentication_start("OAuth2")
        
        try:
            # Simulate authentication delay
            await asyncio.sleep(0.1)
            
            if self.test_mode:
                self._authenticated = True
                self.log_authentication_success(correlation_id, "OAuth2")
                return True
            else:
                raise Exception("Mock authentication failure")
        
        except Exception as e:
            self.log_authentication_failure(correlation_id, "OAuth2", e)
            raise
    
    async def get_inbox_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Mock getting inbox messages."""
        correlation_id = self.log_api_call("Graph API", "/me/messages", "GET")
        
        if not self._authenticated:
            await self.authenticate()
        
        # Generate mock messages
        messages = []
        for i in range(min(limit, len(self.mock_messages))):
            messages.append({
                'id': f'mock_message_{i}',
                'subject': f'Mock Message {i}',
                'from': {
                    'emailAddress': {
                        'address': f'sender{i}@example.com',
                        'name': f'Sender {i}'
                    }
                },
                'receivedDateTime': datetime.now(timezone.utc).isoformat(),
                'body': {
                    'content': f'Mock content for message {i}',
                    'contentType': 'text'
                }
            })
        
        self.log_api_response(correlation_id, 200, len(messages), 150.0)
        return messages
    
    def add_mock_message(self, message: Dict[str, Any]):
        """Add a mock message to be returned by get_inbox_messages."""
        self.mock_messages.append(message)
    
    async def move_message(self, message_id: str, folder_id: str) -> bool:
        """Mock moving a message."""
        correlation_id = self.log_api_call("Graph API", f"/me/messages/{message_id}/move", "POST")
        
        # Simulate API delay
        await asyncio.sleep(0.05)
        
        if self.test_mode:
            self.log_api_response(correlation_id, 200, 0, 75.0)
            return True
        else:
            raise Exception("Mock move failure")
    
    async def create_folder(self, folder_name: str) -> Dict[str, Any]:
        """Mock creating a folder."""
        correlation_id = self.log_api_call("Graph API", "/me/mailFolders", "POST")
        
        await asyncio.sleep(0.1)
        
        folder = {
            'id': f'mock_folder_{folder_name}',
            'displayName': folder_name,
            'parentFolderId': 'Inbox'
        }
        
        self.log_api_response(correlation_id, 201, len(str(folder)), 120.0)
        return folder
    
    async def close(self):
        """Mock cleanup."""
        self.log_user_message("Mock Graph client closed", "info")


class MockEmailProcessor(BusinessLogicLoggerMixin):
    """Mock email processor for testing."""
    
    def __init__(self, settings=None, graph_client=None):
        """Initialize mock processor."""
        self.__init_logging__("mock_email_processor")
        self.settings = settings or Mock()
        self.graph_client = graph_client or MockGraphAPIClient()
        self.processed_emails = []
    
    async def process_inbox(self) -> Dict[str, Any]:
        """Mock inbox processing."""
        correlation_id = self.log_processing_start("inbox", "batch")
        
        try:
            # Mock getting messages
            messages = await self.graph_client.get_inbox_messages(10)
            
            results = {
                "success": True,
                "processed_count": 0,
                "failed_count": 0,
                "errors": [],
                "processing_results": [],
            }
            
            for message in messages:
                result = await self._process_single_email(message)
                results["processing_results"].append(result)
                
                if result.get("success", False):
                    results["processed_count"] += 1
                else:
                    results["failed_count"] += 1
                    if result.get("error"):
                        results["errors"].append(result["error"])
            
            self.log_processing_result(
                correlation_id, 
                "inbox", 
                "completed",
                {"processed": results["processed_count"], "failed": results["failed_count"]}
            )
            
            return results
        
        except Exception as e:
            self.log_operation_error("inbox", correlation_id, e)
            raise
    
    async def _process_single_email(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Mock single email processing."""
        email_id = message.get("id", "unknown")
        email_correlation_id = self.log_processing_start("email", email_id)
        
        try:
            # Simulate processing delay
            await asyncio.sleep(0.05)
            
            # Mock processing result
            result = {
                "success": True,
                "email_id": email_id,
                "process_id": f"proc_{email_id}",
                "error": None,
                "destination_folder": "Processed_Mock",
                "storage_location": f"/tmp/mock_{email_id}.json",
                "processing_duration_ms": 50
            }
            
            self.processed_emails.append(message)
            
            self.log_processing_result(
                email_correlation_id,
                "email",
                "processed",
                {"email_id": email_id}
            )
            
            return result
        
        except Exception as e:
            self.log_operation_error("email", email_correlation_id, e)
            return {
                "success": False,
                "email_id": email_id,
                "error": str(e)
            }


class MockSalesforceClient(APIClientLoggerMixin):
    """Mock Salesforce client for testing."""
    
    def __init__(self, settings=None, test_mode: bool = True):
        """Initialize mock client."""
        self.__init_logging__("mock_salesforce_client")
        self.settings = settings or Mock()
        self.test_mode = test_mode
        self._access_token = None
        self.created_cases = []
    
    async def authenticate(self) -> str:
        """Mock authentication."""
        correlation_id = self.log_authentication_start("OAuth2_ClientCredentials")
        
        try:
            # Simulate auth delay
            await asyncio.sleep(0.1)
            
            if self.test_mode:
                self._access_token = "mock_access_token_123"
                self.log_authentication_success(correlation_id, "OAuth2_ClientCredentials")
                return self._access_token
            else:
                raise Exception("Mock Salesforce auth failure")
        
        except Exception as e:
            self.log_authentication_failure(correlation_id, "OAuth2_ClientCredentials", e)
            raise
    
    async def create_case(self, case_data: Dict[str, Any]) -> Dict[str, str]:
        """Mock case creation."""
        correlation_id = self.log_api_call("Salesforce", "/services/data/v57.0/sobjects/Case", "POST")
        
        if not self._access_token:
            await self.authenticate()
        
        # Simulate API delay
        await asyncio.sleep(0.15)
        
        case_id = f"mock_case_{len(self.created_cases)}"
        result = {
            "id": case_id,
            "success": True,
            "errors": []
        }
        
        self.created_cases.append({**case_data, "id": case_id})
        
        self.log_api_response(correlation_id, 201, len(str(result)), 150.0)
        return result
    
    async def update_contact(self, contact_data: Dict[str, Any]) -> bool:
        """Mock contact update."""
        correlation_id = self.log_api_call("Salesforce", f"/services/data/v57.0/sobjects/Contact/{contact_data.get('contact_id')}", "PATCH")
        
        await asyncio.sleep(0.1)
        
        self.log_api_response(correlation_id, 204, 0, 100.0)
        return True


class MockDatabricksClient(DatabaseLoggerMixin):
    """Mock Databricks client for testing."""
    
    def __init__(self, test_mode: bool = True):
        """Initialize mock client."""
        self.__init_logging__("mock_databricks_client")
        self.test_mode = test_mode
        self.mock_data = []
    
    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Mock query execution."""
        correlation_id = self.log_query_start("databricks", query)
        
        try:
            # Simulate query execution delay
            await asyncio.sleep(0.2)
            
            # Return mock data based on query patterns
            if "SELECT" in query.upper() and "contact" in query.lower():
                results = [
                    {
                        "email": "test@example.com",
                        "sf_account_id": "mock_account_123",
                        "sf_contact_id": "mock_contact_456",
                        "account_name": "Mock Company"
                    }
                ]
            else:
                results = self.mock_data
            
            self.log_query_success(
                correlation_id,
                len(results),
                200.0,
                {"query_type": "SELECT", "table_count": 1}
            )
            
            return results
        
        except Exception as e:
            self.log_query_error(correlation_id, e, {"query": query})
            raise
    
    def add_mock_data(self, data: List[Dict[str, Any]]):
        """Add mock data to be returned by queries."""
        self.mock_data.extend(data)


class MockInboxMonitor(ServiceLoggerMixin):
    """Mock inbox monitor for testing."""
    
    def __init__(self, settings=None):
        """Initialize mock monitor."""
        self.__init_logging__("mock_inbox_monitor")
        self.settings = settings or Mock()
        self._running = False
        self.check_count = 0
    
    async def check_inbox_once(self, limit: int = 10) -> tuple[int, int]:
        """Mock single inbox check."""
        correlation_id = self.log_operation_start("inbox_check", limit=limit)
        
        try:
            # Simulate check delay
            await asyncio.sleep(0.1)
            
            processed = min(limit, 5)  # Mock processing some emails
            failed = 0
            
            self.check_count += 1
            
            self.log_operation_success(
                "inbox_check",
                correlation_id,
                f"Processed {processed} emails",
                processed_count=processed,
                failed_count=failed
            )
            
            return processed, failed
        
        except Exception as e:
            self.log_operation_error("inbox_check", correlation_id, e)
            raise
    
    async def start_monitoring(self):
        """Mock continuous monitoring."""
        correlation_id = self.log_operation_start("continuous_monitoring")
        
        self._running = True
        self.log_user_message("Starting mock continuous monitoring", "info")
        
        try:
            while self._running:
                await self.check_inbox_once()
                await asyncio.sleep(60)  # Check every minute in mock
        
        except Exception as e:
            self.log_operation_error("continuous_monitoring", correlation_id, e)
            raise
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        self.log_user_message("Mock monitoring stopped", "info")


class MockHealthCheckService(ServiceLoggerMixin):
    """Mock health check service for testing."""
    
    def __init__(self):
        """Initialize mock health service."""
        self.__init_logging__("mock_health_service")
        self.component_status = {
            "database": {"healthy": True, "status": "connected"},
            "keyvault": {"healthy": True, "status": "accessible"},
            "graph_api": {"healthy": True, "status": "authenticated"},
            "salesforce": {"healthy": True, "status": "connected"}
        }
    
    async def get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Mock comprehensive health check."""
        correlation_id = self.log_operation_start("health_check", check_type="comprehensive")
        
        try:
            # Simulate health check delay
            await asyncio.sleep(0.1)
            
            self.log_operation_success(
                "health_check",
                correlation_id,
                "Health check completed",
                healthy_components=sum(1 for status in self.component_status.values() if status["healthy"]),
                total_components=len(self.component_status)
            )
            
            return self.component_status
        
        except Exception as e:
            self.log_operation_error("health_check", correlation_id, e)
            raise
    
    def set_component_status(self, component: str, healthy: bool, status: str):
        """Set mock component status."""
        self.component_status[component] = {"healthy": healthy, "status": status}


def create_mock_services_suite() -> Dict[str, Any]:
    """Create a complete suite of mock services for testing."""
    graph_client = MockGraphAPIClient()
    email_processor = MockEmailProcessor(graph_client=graph_client)
    salesforce_client = MockSalesforceClient()
    databricks_client = MockDatabricksClient()
    inbox_monitor = MockInboxMonitor()
    health_service = MockHealthCheckService()
    
    return {
        "graph_client": graph_client,
        "email_processor": email_processor,
        "salesforce_client": salesforce_client,
        "databricks_client": databricks_client,
        "inbox_monitor": inbox_monitor,
        "health_service": health_service
    }


def create_mock_email_message(message_id: str = "test_123", 
                            subject: str = "Test Message",
                            sender_email: str = "sender@example.com") -> Dict[str, Any]:
    """Create a mock email message in Graph API format."""
    return {
        'id': message_id,
        'subject': subject,
        'from': {
            'emailAddress': {
                'address': sender_email,
                'name': sender_email.split('@')[0].title()
            }
        },
        'receivedDateTime': datetime.now(timezone.utc).isoformat(),
        'body': {
            'content': f'This is test content for {subject}',
            'contentType': 'text/plain'
        },
        'conversationId': f'conversation_{message_id}',
        'sender': {
            'emailAddress': {
                'address': sender_email,
                'name': sender_email.split('@')[0].title()
            }
        }
    }