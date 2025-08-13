"""
External Service Test Manager
Orchestration and management of external service test execution.
"""
import asyncio
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()

class ExternalServiceTestManager:
    """
    External service test orchestration and management.
    
    Manages test data creation, cleanup, API quota management,
    and network condition simulation for external service testing.
    """
    
    def __init__(self):
        """Initialize external service test manager."""
        self.logger = structlog.get_logger(__name__)
        self._test_data = {}
        self._quotas = {}
        self._api_call_history = {}
        self._cleanup_tasks = []
    
    def check_service_availability(self, service_name: str) -> bool:
        """Check if a service is available for testing.
        
        Args:
            service_name: Service name (microsoft_graph, salesforce, azure_ai_foundry)
            
        Returns:
            True if service is available for testing
        """
        required_env_vars = {
            'microsoft_graph': [
                'MICROSOFT_GRAPH_CLIENT_ID',
                'MICROSOFT_GRAPH_CLIENT_SECRET', 
                'MICROSOFT_GRAPH_TENANT_ID'
            ],
            'salesforce': [
                'SALESFORCE_CLIENT_ID',
                'SALESFORCE_CLIENT_SECRET',
                'SALESFORCE_INSTANCE_URL'
            ],
            'azure_ai_foundry': [
                'AZURE_AI_FOUNDRY_ENDPOINT',
                'AZURE_AI_FOUNDRY_KEY'
            ]
        }
        
        if service_name not in required_env_vars:
            return False
        
        return all(os.getenv(var) for var in required_env_vars[service_name])
    
    async def setup_test_environment(self, service_name: str) -> Dict[str, Any]:
        """Set up test environment for a service.
        
        Args:
            service_name: Service name
            
        Returns:
            Test environment configuration
        """
        self.logger.info(f"Setting up test environment for {service_name}")
        
        if service_name == 'microsoft_graph':
            return await self._setup_graph_test_environment()
        elif service_name == 'salesforce':
            return await self._setup_salesforce_test_environment()
        elif service_name == 'azure_ai_foundry':
            return await self._setup_ai_foundry_test_environment()
        else:
            raise ValueError(f"Unknown service: {service_name}")
    
    async def _setup_graph_test_environment(self) -> Dict[str, Any]:
        """Set up Microsoft Graph test environment."""
        config = {
            'client_id': os.getenv('MICROSOFT_GRAPH_CLIENT_ID'),
            'client_secret': os.getenv('MICROSOFT_GRAPH_CLIENT_SECRET'),
            'tenant_id': os.getenv('MICROSOFT_GRAPH_TENANT_ID'),
            'test_mode': False
        }
        
        # Initialize quota tracking
        self._quotas['microsoft_graph'] = {
            'daily_limit': 10000,
            'current_usage': 0,
            'rate_limit_per_minute': 100,
            'current_minute_usage': 0,
            'minute_start': time.time()
        }
        
        self.logger.info("Microsoft Graph test environment ready")
        return config
    
    async def _setup_salesforce_test_environment(self) -> Dict[str, Any]:
        """Set up Salesforce test environment."""
        config = {
            'client_id': os.getenv('SALESFORCE_CLIENT_ID'),
            'client_secret': os.getenv('SALESFORCE_CLIENT_SECRET'),
            'instance_url': os.getenv('SALESFORCE_INSTANCE_URL'),
            'test_mode': False
        }
        
        # Initialize quota tracking
        self._quotas['salesforce'] = {
            'daily_limit': 15000,
            'current_usage': 0,
            'rate_limit_per_minute': 20,
            'current_minute_usage': 0,
            'minute_start': time.time()
        }
        
        self.logger.info("Salesforce test environment ready")
        return config
    
    async def _setup_ai_foundry_test_environment(self) -> Dict[str, Any]:
        """Set up Azure AI Foundry test environment."""
        config = {
            'endpoint': os.getenv('AZURE_AI_FOUNDRY_ENDPOINT'),
            'api_key': os.getenv('AZURE_AI_FOUNDRY_KEY'),
            'client_id': os.getenv('AZURE_AI_FOUNDRY_CLIENT_ID', ''),
            'client_secret': os.getenv('AZURE_AI_FOUNDRY_CLIENT_SECRET', ''),
            'tenant_id': os.getenv('AZURE_AI_FOUNDRY_TENANT_ID', ''),
            'test_mode': False
        }
        
        # Initialize quota tracking
        self._quotas['azure_ai_foundry'] = {
            'daily_limit': 1000,
            'current_usage': 0,
            'rate_limit_per_minute': 20,
            'current_minute_usage': 0,
            'minute_start': time.time()
        }
        
        self.logger.info("Azure AI Foundry test environment ready")
        return config
    
    async def track_api_call(self, service_name: str):
        """Track API call for quota management.
        
        Args:
            service_name: Service name
        """
        if service_name not in self._quotas:
            return
        
        quota = self._quotas[service_name]
        current_time = time.time()
        
        # Reset minute counter if needed
        if current_time - quota['minute_start'] >= 60:
            quota['current_minute_usage'] = 0
            quota['minute_start'] = current_time
        
        # Increment counters
        quota['current_usage'] += 1
        quota['current_minute_usage'] += 1
        
        # Check limits
        if quota['current_usage'] >= quota['daily_limit']:
            self.logger.warning(f"{service_name} daily quota exceeded: {quota['current_usage']}/{quota['daily_limit']}")
        
        if quota['current_minute_usage'] >= quota['rate_limit_per_minute']:
            self.logger.warning(f"{service_name} rate limit approached: {quota['current_minute_usage']}/{quota['rate_limit_per_minute']} per minute")
    
    async def check_quota_availability(self, service_name: str) -> bool:
        """Check if service has quota available.
        
        Args:
            service_name: Service name
            
        Returns:
            True if quota is available
        """
        if service_name not in self._quotas:
            return True
        
        quota = self._quotas[service_name]
        current_time = time.time()
        
        # Reset minute counter if needed
        if current_time - quota['minute_start'] >= 60:
            quota['current_minute_usage'] = 0
            quota['minute_start'] = current_time
        
        # Check limits
        daily_available = quota['current_usage'] < quota['daily_limit'] * 0.9  # Stay under 90%
        rate_available = quota['current_minute_usage'] < quota['rate_limit_per_minute'] * 0.8  # Stay under 80%
        
        return daily_available and rate_available
    
    async def create_test_data(self, service_name: str, data_type: str, count: int = 1) -> List[Dict[str, Any]]:
        """Create test data for a service.
        
        Args:
            service_name: Service name
            data_type: Type of test data to create
            count: Number of test items to create
            
        Returns:
            List of created test data
        """
        self.logger.info(f"Creating {count} {data_type} test data items for {service_name}")
        
        if service_name == 'microsoft_graph':
            return await self._create_graph_test_data(data_type, count)
        elif service_name == 'salesforce':
            return await self._create_salesforce_test_data(data_type, count)
        elif service_name == 'azure_ai_foundry':
            return await self._create_ai_foundry_test_data(data_type, count)
        else:
            raise ValueError(f"Unknown service: {service_name}")
    
    async def _create_graph_test_data(self, data_type: str, count: int) -> List[Dict[str, Any]]:
        """Create Microsoft Graph test data."""
        test_data = []
        
        if data_type == 'test_queries':
            for i in range(count):
                test_data.append({
                    'id': f'graph_test_{i}_{int(time.time())}',
                    'query_type': 'user_info',
                    'user_id': 'me',
                    'expected_fields': ['id', 'displayName', 'mail']
                })
        
        # Store for cleanup
        if 'microsoft_graph' not in self._test_data:
            self._test_data['microsoft_graph'] = []
        self._test_data['microsoft_graph'].extend(test_data)
        
        return test_data
    
    async def _create_salesforce_test_data(self, data_type: str, count: int) -> List[Dict[str, Any]]:
        """Create Salesforce test data."""
        test_data = []
        
        if data_type == 'test_queries':
            for i in range(count):
                test_data.append({
                    'id': f'sf_test_{i}_{int(time.time())}',
                    'query_type': 'soql',
                    'query': f'SELECT Id, Name FROM Account LIMIT {i+1}',
                    'expected_result': 'records'
                })
        
        # Store for cleanup
        if 'salesforce' not in self._test_data:
            self._test_data['salesforce'] = []
        self._test_data['salesforce'].extend(test_data)
        
        return test_data
    
    async def _create_ai_foundry_test_data(self, data_type: str, count: int) -> List[Dict[str, Any]]:
        """Create Azure AI Foundry test data."""
        test_data = []
        
        if data_type == 'test_prompts':
            prompts = [
                "Classify this email as urgent or normal: Hello, please review this when you have time.",
                "Classify this email as urgent or normal: URGENT: Server is down!",
                "Classify this email as urgent or normal: Thank you for your help yesterday."
            ]
            
            for i in range(count):
                prompt = prompts[i % len(prompts)]
                test_data.append({
                    'id': f'ai_test_{i}_{int(time.time())}',
                    'prompt': prompt,
                    'expected_classification': 'normal' if 'please' in prompt else 'urgent' if 'URGENT' in prompt else 'normal'
                })
        
        # Store for cleanup
        if 'azure_ai_foundry' not in self._test_data:
            self._test_data['azure_ai_foundry'] = []
        self._test_data['azure_ai_foundry'].extend(test_data)
        
        return test_data
    
    async def simulate_network_condition(self, condition: str, duration: float = 5.0):
        """Simulate network conditions for testing.
        
        Args:
            condition: Network condition to simulate (slow, intermittent, timeout)
            duration: Duration to maintain the condition
        """
        self.logger.info(f"Simulating {condition} network condition for {duration}s")
        
        if condition == 'slow':
            # Simulate by adding delays to API calls
            await asyncio.sleep(2.0)
        elif condition == 'intermittent':
            # Simulate by randomly failing some calls
            import random
            if random.choice([True, False]):
                raise Exception("Simulated intermittent network failure")
        elif condition == 'timeout':
            # Simulate by causing a timeout
            await asyncio.sleep(duration + 1)
        
        self.logger.info(f"Network condition simulation ({condition}) completed")
    
    async def cleanup_test_data(self, service_name: Optional[str] = None):
        """Clean up test data for a service or all services.
        
        Args:
            service_name: Service name to clean up, or None for all services
        """
        if service_name:
            services_to_clean = [service_name]
        else:
            services_to_clean = list(self._test_data.keys())
        
        for service in services_to_clean:
            if service in self._test_data:
                test_data = self._test_data[service]
                self.logger.info(f"Cleaning up {len(test_data)} test data items for {service}")
                
                # Service-specific cleanup
                if service == 'microsoft_graph':
                    await self._cleanup_graph_test_data(test_data)
                elif service == 'salesforce':
                    await self._cleanup_salesforce_test_data(test_data)
                elif service == 'azure_ai_foundry':
                    await self._cleanup_ai_foundry_test_data(test_data)
                
                # Clear from memory
                del self._test_data[service]
    
    async def _cleanup_graph_test_data(self, test_data: List[Dict[str, Any]]):
        """Clean up Microsoft Graph test data."""
        # For Graph API, most test data is read-only queries, no cleanup needed
        self.logger.info(f"Cleaned up {len(test_data)} Graph API test items")
    
    async def _cleanup_salesforce_test_data(self, test_data: List[Dict[str, Any]]):
        """Clean up Salesforce test data."""
        # For Salesforce, most test data is read-only queries, no cleanup needed
        self.logger.info(f"Cleaned up {len(test_data)} Salesforce test items")
    
    async def _cleanup_ai_foundry_test_data(self, test_data: List[Dict[str, Any]]):
        """Clean up Azure AI Foundry test data."""
        # For AI Foundry, test data is prompts, no cleanup needed
        self.logger.info(f"Cleaned up {len(test_data)} AI Foundry test items")
    
    async def cleanup_all(self):
        """Clean up all test data and resources."""
        self.logger.info("Cleaning up all external service test resources")
        
        # Clean up test data
        await self.cleanup_test_data()
        
        # Execute any pending cleanup tasks
        if self._cleanup_tasks:
            await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)
            self._cleanup_tasks.clear()
        
        # Reset quotas and history
        self._quotas.clear()
        self._api_call_history.clear()
        
        self.logger.info("External service test cleanup completed")
    
    def get_quota_status(self, service_name: str) -> Dict[str, Any]:
        """Get current quota status for a service.
        
        Args:
            service_name: Service name
            
        Returns:
            Quota status information
        """
        if service_name not in self._quotas:
            return {'status': 'unknown', 'message': 'No quota tracking configured'}
        
        quota = self._quotas[service_name]
        current_time = time.time()
        
        # Calculate usage percentages
        daily_usage_pct = (quota['current_usage'] / quota['daily_limit']) * 100
        
        # Reset minute counter if needed for accurate reporting
        if current_time - quota['minute_start'] >= 60:
            quota['current_minute_usage'] = 0
        
        minute_usage_pct = (quota['current_minute_usage'] / quota['rate_limit_per_minute']) * 100
        
        return {
            'service': service_name,
            'daily_usage': quota['current_usage'],
            'daily_limit': quota['daily_limit'],
            'daily_usage_percentage': round(daily_usage_pct, 1),
            'minute_usage': quota['current_minute_usage'],
            'minute_limit': quota['rate_limit_per_minute'],
            'minute_usage_percentage': round(minute_usage_pct, 1),
            'quota_available': daily_usage_pct < 90 and minute_usage_pct < 80
        }
    
    def get_api_call_history(self, service_name: str) -> List[Dict[str, Any]]:
        """Get API call history for a service.
        
        Args:
            service_name: Service name
            
        Returns:
            List of API call history entries
        """
        return self._api_call_history.get(service_name, [])
    
    def record_test_result(self, service_name: str, test_name: str, result: Dict[str, Any]):
        """Record test result for reporting.
        
        Args:
            service_name: Service name
            test_name: Test name
            result: Test result data
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if service_name not in self._api_call_history:
            self._api_call_history[service_name] = []
        
        self._api_call_history[service_name].append({
            'timestamp': timestamp,
            'test_name': test_name,
            'result': result
        })
        
        # Keep only last 100 entries
        if len(self._api_call_history[service_name]) > 100:
            self._api_call_history[service_name] = self._api_call_history[service_name][-100:]