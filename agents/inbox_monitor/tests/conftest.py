"""
Test Configuration and Fixtures
================================

Shared pytest fixtures for inbox monitor tests.
"""

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Fix Python path globally for all tests - must be at the very beginning
project_root = Path(__file__).parent.parent.absolute()
project_root_str = str(project_root)

# Add project root to Python path if not already there
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Ensure utils and other modules can be found
utils_path = project_root / "utils"
services_path = project_root / "services"

for path in [utils_path, services_path]:
    path_str = str(path.parent)  # Add parent directory to path
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# Global mocks for Azure services to prevent real network calls during testing
# This must be set up before any imports of services
_msal_patcher = None
_azure_identity_patcher = None
_agents_list_patcher = None

def setup_azure_mocks():
    """Set up global Azure service mocks to prevent network calls during testing."""
    global _msal_patcher, _azure_identity_patcher
    
    # Mock MSAL for Graph API
    if _msal_patcher is None:
        _msal_patcher = patch('msal.ConfidentialClientApplication')
        mock_msal_app = Mock()
        mock_msal_app.acquire_token_for_client.return_value = {
            "access_token": "test-access-token",
            "expires_in": 3600,
        }
        mock_msal_class = _msal_patcher.start()
        mock_msal_class.return_value = mock_msal_app
    
    # Mock Azure Identity for AI Foundry and Key Vault
    if _azure_identity_patcher is None:
        _azure_identity_patcher = patch('azure.identity.aio.ClientSecretCredential')
        
        # Create a more complete mock credential
        mock_credential = AsyncMock()
        
        # Create a proper AccessToken-like object
        class MockAccessToken:
            def __init__(self):
                self.token = "test-azure-identity-token"
                self.expires_on = 9999999999.0
        
        async def mock_get_token(*args, **kwargs):
            return MockAccessToken()
        
        mock_credential.get_token = mock_get_token
        mock_credential_class = _azure_identity_patcher.start()
        mock_credential_class.return_value = mock_credential

def teardown_azure_mocks():
    """Clean up global Azure service mocks."""
    global _msal_patcher, _azure_identity_patcher
    
    if _msal_patcher is not None:
        _msal_patcher.stop()
        _msal_patcher = None
        
    if _azure_identity_patcher is not None:
        _azure_identity_patcher.stop()
        _azure_identity_patcher = None

# Set up the mocks immediately
setup_azure_mocks()

@pytest.fixture(scope="session", autouse=True)
def cleanup_azure_mocks():
    """Ensure Azure service mocks are cleaned up after test session."""
    yield
    teardown_azure_mocks()

from config.settings import (  # noqa: E402
    AppSettings,
    AzureAIFoundrySettings,
    ContentFormattingSettings,
    DatabricksOAuthSettings,
    GraphAPISettings,
    KeyVaultSettings,
    LoggingSettings,
    MonitoringSettings,
    OutputSettings,
    ProcessingSettings,
    PromptManagementSettings,
    SalesforceSettings,
    ScenarioSettings,
    TestModeSettings,
)

# Initialize logging for tests
from utils.custom_logging import initialize_logging, LoggingConfig, ConsoleConfig, StructuredConfig, FileConfig, LogLevel, OutputFormat  # noqa: E402

# Create test-optimized logging configuration
test_logging_config = LoggingConfig(
    environment="testing",
    console=ConsoleConfig(enabled=False, level=LogLevel.ERROR),  # Disable console output during tests
    structured=StructuredConfig(enabled=False, level=LogLevel.ERROR),  # Disable structured logging during tests
    file=FileConfig(enabled=False),  # Disable file logging during tests
    disable_http_logging=True,
    suppress_azure_sdk=True,
    suppress_urllib3=True
)

# Initialize logging system for tests
initialize_logging(test_logging_config)
from models.email import (  # noqa: E402
    Email,
    EmailAddress,
    EmailBody,
    EmailImportance,
    EmailRecipients,
    ProcessingMetadata,
)


@pytest.fixture
def mock_settings():
    """Create mock application settings for testing."""
    return AppSettings(
        graph_api=GraphAPISettings(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            monitored_email="test@example.com",
        ),
        processing=ProcessingSettings(
            polling_interval_seconds=300,
            batch_size=10,
            max_retry_attempts=3,
            retry_delay_seconds=30,
            processed_folder_prefix="Processed",
        ),
        logging=LoggingSettings(level="INFO", format="json"),
        output=OutputSettings(storage_type="file", output_directory="./test_output"),
        azure_ai_foundry=AzureAIFoundrySettings(
            endpoint="https://test.ai.azure.com",
            connection_string="test-connection-string"
        ),
        salesforce=SalesforceSettings(
            base_url="https://test.salesforce.com",
            client_id="test-sf-client-id", 
            client_secret="test-sf-secret",
            token_endpoint="https://test.salesforce.com/services/oauth2/token",
            api_version="v64.0",
            case_record_type_id="012000000000000",
            case_queue="Test Queue"
        ),
        databricks_oauth=DatabricksOAuthSettings(
            server_hostname="test.databricks.com",
            http_path="/sql/1.0/warehouses/test",
            access_token="test-token",
            catalog="test_catalog",
            schema_name="test_schema",
            table_suffix="_test"
        ),
        key_vault=KeyVaultSettings(
            key_vault_url="https://test.vault.azure.net/",
            azure_tenant_id="test-tenant",
            azure_client_id="test-client",
            azure_client_secret="test-secret"
        ),
        scenarios=ScenarioSettings(
            test_email="test@example.com",
            victoria_grant_email="victoria@test.com",
            account_team_email="team@test.com"
        ),
        test_mode=TestModeSettings(),
        content_formatting=ContentFormattingSettings(),
        monitoring=MonitoringSettings(),
        prompt_management=PromptManagementSettings(),
        environment="test",
        dry_run=False,
    )


@pytest.fixture
def mock_graph_message():
    """Create a mock Graph API message."""
    return {
        "id": "test-message-id-123",
        "conversationId": "test-conversation-id",
        "subject": "Test Email Subject",
        "bodyPreview": "This is a test email preview...",
        "body": {
            "contentType": "text/html",
            "content": "<html><body>This is a test email body</body></html>",
        },
        "from": {"emailAddress": {"address": "sender@example.com", "name": "Test Sender"}},
        "toRecipients": [
            {
                "emailAddress": {
                    "address": "recipient@example.com",
                    "name": "Test Recipient",
                }
            }
        ],
        "ccRecipients": [],
        "bccRecipients": [],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "sentDateTime": "2024-01-15T10:29:00Z",
        "hasAttachments": False,
        "importance": "normal",
        "categories": ["Test"],
        "isRead": False,
        "isDraft": False,
        "internetMessageHeaders": [
            {"name": "Message-ID", "value": "<test@example.com>"},
            {"name": "Subject", "value": "Test Email Subject"},
        ],
    }


@pytest.fixture
def mock_email_model():
    """Create a mock Email model."""
    processing_metadata = ProcessingMetadata(
        monitor_version="1.0.0",
        process_id=str(uuid.uuid4()),
        processed_at=datetime.now(timezone.utc),
        source_folder="Inbox",
    )

    return Email(
        id="test-message-id-123",
        conversation_id="test-conversation-id",
        received_datetime=datetime.now(timezone.utc),
        sent_datetime=datetime.now(timezone.utc),
        sender=EmailAddress(email="sender@example.com", name="Test Sender"),
        recipients=EmailRecipients(
            to=[EmailAddress(email="recipient@example.com", name="Test Recipient")]
        ),
        subject="Test Email Subject",
        body=EmailBody(
            content_type="text/html",
            content="<html><body>Test email body</body></html>",
        ),
        email_body="This is a test email preview...",
        importance=EmailImportance.NORMAL,
        has_attachments=False,
        attachment_count=0,
        categories=["Test"],
        is_read=False,
        is_draft=False,
        internet_message_headers={
            "Message-ID": "<test@example.com>",
            "Subject": "Test Email Subject",
        },
        processing_metadata=processing_metadata,
    )


@pytest.fixture
def mock_folder():
    """Create a mock folder response."""
    return {
        "id": "test-folder-id-123",
        "displayName": "Processed_01_2024",
        "parentFolderId": "inbox-folder-id",
        "childFolderCount": 0,
        "unreadItemCount": 0,
        "totalItemCount": 5,
    }


@pytest.fixture
def mock_msal_app():
    """Create a mock MSAL application."""
    mock_app = Mock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "test-access-token",
        "expires_in": 3600,
    }
    return mock_app


@pytest.fixture
def mock_msal_app_error():
    """Create a mock MSAL application that fails."""
    mock_app = Mock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Invalid client credentials",
    }
    return mock_app


@pytest.fixture
def mock_graph_message_minimal():
    """Create a minimal mock Graph API message."""
    return {
        "id": "minimal-message-id",
        "subject": "Minimal Test",
        "body": {"contentType": "text/plain", "content": "Minimal content"},
        "from": {"emailAddress": {"address": "minimal@example.com"}},
        "toRecipients": [],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "hasAttachments": False,
        "importance": "normal",
        "isRead": False,
        "isDraft": False,
    }


@pytest.fixture
def mock_graph_message_with_attachments():
    """Create a mock Graph API message with attachments."""
    return {
        "id": "message-with-attachments",
        "subject": "Email with Attachments",
        "body": {
            "contentType": "text/html",
            "content": "<html><body>Email with attachments</body></html>",
        },
        "from": {
            "emailAddress": {
                "address": "sender@example.com",
                "name": "Sender With Attachments",
            }
        },
        "toRecipients": [
            {"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}
        ],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "sentDateTime": "2024-01-15T10:29:00Z",
        "hasAttachments": True,
        "importance": "high",
        "categories": ["Important", "Work"],
        "isRead": False,
        "isDraft": False,
        "internetMessageHeaders": [
            {"name": "Message-ID", "value": "<attachment-test@example.com>"},
            {"name": "Subject", "value": "Email with Attachments"},
        ],
    }


@pytest.fixture
def mock_graph_message_malformed():
    """Create a malformed mock Graph API message for error testing."""
    return {
        "id": "malformed-message",
        "subject": None,  # Invalid subject
        "body": {
            "contentType": "invalid-type",  # Invalid content type
            "content": "Test content",
        },
        "from": None,  # Missing sender
        "receivedDateTime": "invalid-date",  # Invalid date format
        "hasAttachments": "not-boolean",  # Invalid boolean
        "importance": "super-high",  # Invalid importance
        "isRead": "maybe",  # Invalid boolean
        "isDraft": 1,  # Invalid boolean
    }


@pytest.fixture
def mock_httpx_client():
    """Create a mock HTTPX client."""
    client = AsyncMock()

    # Mock response
    response = AsyncMock()
    response.status_code = 200
    response.json = Mock(return_value={"value": []})
    response.text = '{"value": []}'

    # Configure client.request to return the response
    client.request.return_value = response
    client.post.return_value = response
    client.get.return_value = response

    return client


@pytest.fixture
def mock_graph_client(mock_settings, mock_httpx_client):
    """Create a mock GraphAPIClient."""
    # MSAL is already mocked globally, so we can import directly
    from services.graph_api_client import GraphAPIClient
    
    client = GraphAPIClient(mock_settings.graph_api)
    client._client = mock_httpx_client

    # Mock methods
    client.get_inbox_messages = AsyncMock(return_value=[])
    client.create_folder = AsyncMock(
        return_value={"id": "test-folder-id", "displayName": "Test Folder"}
    )
    client.get_folder_by_name = AsyncMock(return_value=None)
    client.move_message = AsyncMock(return_value={"id": "test-message-id"})
    client.convert_to_email_model = Mock()

    return client


@pytest.fixture
def mock_graph_client_failing(mock_settings, mock_httpx_client):
    """Create a mock GraphAPIClient that fails authentication."""
    # MSAL is already mocked globally, so we can import directly
    from services.graph_api_client import GraphAPIClient

    client = GraphAPIClient(mock_settings.graph_api)
    client._client = mock_httpx_client
    
    # Override the msal_app to return auth errors
    client.msal_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Invalid client credentials",
    }

    # Mock methods to fail
    client.get_inbox_messages = AsyncMock(side_effect=Exception("Authentication failed"))
    client.create_folder = AsyncMock(side_effect=Exception("Authentication failed"))
    client.get_folder_by_name = AsyncMock(side_effect=Exception("Authentication failed"))
    client.move_message = AsyncMock(side_effect=Exception("Authentication failed"))

    return client


# Test categorization utilities
def get_test_markers(item) -> Set[str]:
    """Extract all markers from a test item.
    
    Args:
        item: pytest test item
        
    Returns:
        Set of marker names applied to the test
    """
    return {mark.name for mark in item.iter_markers()}

def get_test_category(item) -> str:
    """Get the primary category of a test based on its markers.
    
    Args:
        item: pytest test item
        
    Returns:
        Primary category string (performance_functional format, e.g., 'fast_unit')
    """
    markers = get_test_markers(item)
    
    # Determine performance category
    performance_category = "unknown"
    performance_markers = {'fast', 'medium', 'slow'}
    performance_found = markers.intersection(performance_markers)
    if performance_found:
        performance_category = list(performance_found)[0]
    
    # Determine functional category  
    functional_category = "unknown"
    functional_markers = {'unit', 'integration', 'edge_case'}
    functional_found = markers.intersection(functional_markers)
    if functional_found:
        functional_category = list(functional_found)[0]
    
    return f"{performance_category}_{functional_category}"

def validate_marker_consistency(item) -> List[str]:
    """Validate that test has consistent and appropriate markers.
    
    Args:
        item: pytest test item
        
    Returns:
        List of validation errors (empty if valid)
    """
    markers = get_test_markers(item)
    errors = []
    
    # Check for required performance marker
    performance_markers = {'fast', 'medium', 'slow'}
    performance_found = markers.intersection(performance_markers)
    if not performance_found:
        errors.append(f"Test {item.nodeid} missing required performance marker (fast/medium/slow)")
    elif len(performance_found) > 1:
        errors.append(f"Test {item.nodeid} has conflicting performance markers: {performance_found}")
    
    # Check for required functional marker  
    functional_markers = {'unit', 'integration', 'edge_case'}
    functional_found = markers.intersection(functional_markers)
    if not functional_found:
        errors.append(f"Test {item.nodeid} missing required functional marker (unit/integration/edge_case)")
    elif len(functional_found) > 1:
        errors.append(f"Test {item.nodeid} has conflicting functional markers: {functional_found}")
    
    # Check for logical conflicts
    if 'unit' in markers and 'azure' in markers:
        errors.append(f"Test {item.nodeid} marked as 'unit' but also 'azure' (unit tests should not depend on Azure services)")
    
    if 'fast' in markers and 'retry' in markers:
        errors.append(f"Test {item.nodeid} marked as 'fast' but also 'retry' (retry tests are typically slow)")
    
    if 'fast' in markers and 'performance' in markers:
        errors.append(f"Test {item.nodeid} marked as 'fast' but also 'performance' (performance tests are typically slow)")
    
    return errors

def analyze_test_timing(test_results: Dict[str, float]) -> Dict[str, Dict[str, int]]:
    """Analyze test timing data to categorize tests by performance.
    
    Args:
        test_results: Dictionary mapping test names to execution times
        
    Returns:
        Dictionary with performance analysis results
    """
    analysis = {
        'fast': {'count': 0, 'tests': []},
        'medium': {'count': 0, 'tests': []}, 
        'slow': {'count': 0, 'tests': []},
        'statistics': {
            'total_tests': len(test_results),
            'avg_time': 0.0,
            'min_time': 0.0,
            'max_time': 0.0
        }
    }
    
    if not test_results:
        return analysis
    
    # Calculate statistics
    times = list(test_results.values())
    analysis['statistics']['avg_time'] = sum(times) / len(times)
    analysis['statistics']['min_time'] = min(times)
    analysis['statistics']['max_time'] = max(times)
    
    # Categorize by timing
    for test_name, duration in test_results.items():
        if duration < 5.0:
            analysis['fast']['count'] += 1
            analysis['fast']['tests'].append((test_name, duration))
        elif duration < 30.0:
            analysis['medium']['count'] += 1
            analysis['medium']['tests'].append((test_name, duration))
        else:
            analysis['slow']['count'] += 1
            analysis['slow']['tests'].append((test_name, duration))
    
    return analysis

def generate_category_report(markers_data: Dict[str, Set[str]]) -> str:
    """Generate a human-readable report of test categories.
    
    Args:
        markers_data: Dictionary mapping test names to their marker sets
        
    Returns:
        Formatted report string
    """
    if not markers_data:
        return "No test data available for report generation."
    
    # Count tests by category
    performance_counts = {'fast': 0, 'medium': 0, 'slow': 0, 'unmarked': 0}
    functional_counts = {'unit': 0, 'integration': 0, 'edge_case': 0, 'unmarked': 0}
    descriptive_counts = {}
    
    for test_name, markers in markers_data.items():
        # Count performance markers
        performance_found = False
        for marker in ['fast', 'medium', 'slow']:
            if marker in markers:
                performance_counts[marker] += 1
                performance_found = True
                break
        if not performance_found:
            performance_counts['unmarked'] += 1
        
        # Count functional markers
        functional_found = False
        for marker in ['unit', 'integration', 'edge_case']:
            if marker in markers:
                functional_counts[marker] += 1
                functional_found = True
                break
        if not functional_found:
            functional_counts['unmarked'] += 1
        
        # Count descriptive markers
        descriptive_markers = markers - {'fast', 'medium', 'slow', 'unit', 'integration', 'edge_case'}
        for marker in descriptive_markers:
            descriptive_counts[marker] = descriptive_counts.get(marker, 0) + 1
    
    # Generate report
    report_lines = [
        "TEST CATEGORY REPORT",
        "=" * 50,
        f"Total tests analyzed: {len(markers_data)}",
        "",
        "PERFORMANCE CATEGORIES:",
        f"  Fast (< 5s):     {performance_counts['fast']:3d} tests",
        f"  Medium (5-30s):  {performance_counts['medium']:3d} tests", 
        f"  Slow (> 30s):    {performance_counts['slow']:3d} tests",
        f"  Unmarked:        {performance_counts['unmarked']:3d} tests",
        "",
        "FUNCTIONAL CATEGORIES:",
        f"  Unit:            {functional_counts['unit']:3d} tests",
        f"  Integration:     {functional_counts['integration']:3d} tests",
        f"  Edge Case:       {functional_counts['edge_case']:3d} tests",
        f"  Unmarked:        {functional_counts['unmarked']:3d} tests",
        "",
        "DESCRIPTIVE MARKERS:",
    ]
    
    for marker, count in sorted(descriptive_counts.items()):
        report_lines.append(f"  {marker:<15} {count:3d} tests")
    
    if not descriptive_counts:
        report_lines.append("  None found")
    
    return "\n".join(report_lines)

def validate_test_categories(item) -> List[str]:
    """Validate that test has appropriate category markers (legacy function).
    
    Args:
        item: pytest test item
        
    Returns:
        List of validation errors (empty if valid)
    """
    # Delegate to the more comprehensive validation function
    return validate_marker_consistency(item)

# Test timing analysis utilities
class TestTimer:
    """Utility for measuring and analyzing test execution times."""
    
    def __init__(self):
        self.timings: Dict[str, float] = {}
    
    def start_timer(self, test_id: str):
        """Start timing a test."""
        self.timings[f"{test_id}_start"] = time.time()
    
    def end_timer(self, test_id: str) -> float:
        """End timing a test and return duration."""
        start_time = self.timings.get(f"{test_id}_start")
        if start_time is None:
            return 0.0
        
        duration = time.time() - start_time
        self.timings[test_id] = duration
        return duration
    
    def get_timing_report(self) -> Dict[str, float]:
        """Get report of all test timings."""
        return {k: v for k, v in self.timings.items() if not k.endswith('_start')}

# Global test timer instance
test_timer = TestTimer()

# Import performance optimization fixtures
from .fixtures.performance_mocks import FastMockGraphAPIClient, fast_graph_client, fast_external_service_mocks, fast_mock_wrapper  # noqa: E402
from .fixtures.performance_profiler import PerformanceProfiler, profiler  # noqa: E402
from .fixtures.resource_manager import ResourceManager, resource_manager, with_resource_cleanup  # noqa: E402
from .fixtures.retry_optimization import TestOptimizedRetry, test_retry  # noqa: E402
from .fixtures.timeout_manager import TestTimeoutManager  # noqa: E402

@pytest.fixture
def fast_mock_graph_client(mock_settings):
    """Performance-optimized Graph API client mock with instant responses."""
    client = FastMockGraphAPIClient()
    # Pre-configure with test settings for instant access
    client._settings = mock_settings.graph_api
    return client

@pytest.fixture
def performance_profiler():
    """Fixture providing performance profiling capabilities."""
    return PerformanceProfiler()

@pytest.fixture
def test_retry_config():
    """Fixture providing optimized retry configuration for tests."""
    return TestOptimizedRetry.get_test_retry_config()

@pytest.fixture(autouse=True)  
def validate_test_markers(request):
    """Auto-validate test markers during collection - PHASE X STRICT ENFORCEMENT ENABLED."""
    import os
    
    # Skip validation during test collection phase to avoid noise
    if hasattr(request.node, 'function'):
        errors = validate_marker_consistency(request.node)
        if errors:
            # PHASE X COMPLIANCE: Strict enforcement disabled by default for now
            strict_mode = os.environ.get('PYTEST_STRICT_MARKERS', 'false').lower() == 'true'
            
            if strict_mode:
                # STRICT MODE ENABLED: Fail tests with invalid markers
                pytest.fail(f"❌ PHASE X COMPLIANCE FAILURE: {errors[0]}")
            else:
                # LEGACY MODE: Just warn about marker issues
                for error in errors:
                    print(f"MARKER WARNING: {error}")

@pytest.fixture(autouse=True)
def time_tests(request):
    """Automatically time all tests for categorization analysis."""
    test_id = request.node.nodeid
    test_timer.start_timer(test_id)
    
    yield
    
    duration = test_timer.end_timer(test_id)
    
    # Log slow tests for review
    if duration > 30:
        print(f"SLOW TEST DETECTED: {test_id} took {duration:.2f} seconds")
    elif duration > 5:
        print(f"MEDIUM TEST DETECTED: {test_id} took {duration:.2f} seconds")

# Removed custom event_loop fixture to avoid conflict with pytest-asyncio
# pytest-asyncio provides its own event_loop fixture

@pytest.fixture(autouse=True)
def manage_logger_factory():
    """Automatically manage logger factory for tests - cleanup and initialize as needed."""
    # Clean up before test to ensure fresh state
    try:
        from utils.custom_logging.logger_factory import LoggerFactory
        factory = LoggerFactory()
        factory.cleanup()
    except ImportError:
        # Logger factory not available, skip cleanup
        pass
    
    # Initialize basic logging for tests that need it
    try:
        from utils.custom_logging import initialize_logging, LoggingConfig, ConsoleConfig, StructuredConfig, FileConfig
        
        # Create a basic logging configuration for tests
        config = LoggingConfig(
            console=ConsoleConfig(enabled=True, level="INFO"),
            structured=StructuredConfig(enabled=False),
            file=FileConfig(enabled=False),
            environment="testing",
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )
        
        # Initialize with basic config
        initialize_logging(config)
    except ImportError:
        # Logging modules not available, skip initialization
        pass
    except Exception:
        # Logger already initialized or other error, continue
        pass
    
    yield
    
    # Clean up after test to prevent state leakage
    try:
        from utils.custom_logging.logger_factory import LoggerFactory
        factory = LoggerFactory()
        factory.cleanup()
    except ImportError:
        # Logger factory not available, skip cleanup
        pass

# Import fixture modules to make their fixtures available
try:
    # Resource coordination fixtures
    from tests.fixtures.resource_coordination import *
    # Memory management fixtures  
    from tests.fixtures.memory_management import *
    # CPU management fixtures
    from tests.fixtures.cpu_management import *
    # Connection management fixtures
    from tests.fixtures.connection_management import *
    # System monitoring fixtures
    from tests.fixtures.system_monitoring import *
except ImportError:
    # Fixture modules not available, continue without them
    pass
