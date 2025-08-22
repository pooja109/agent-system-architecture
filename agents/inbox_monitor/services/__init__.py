"""Inbox Monitor Services."""

from . import monitor
from .monitor import InboxMonitor
from .graph_api_client import GraphAPIClient
from .email_processor import EmailProcessor
from .azure_ai_foundry_client import AzureAIFoundryClient
from .contact_lookup_service import ContactLookupService
from .response_handler import ResponseHandler
from .round_robin_service import RoundRobinService
from .salesforce_client import SalesforceClient
from .scenario_processor import ScenarioProcessor

# Scenario tracking services
from .scenario_tracking_client import (
    ScenarioTrackingClient,
    ScenarioAnalyticsResult,
    CustomerInteractionHistory,
    ExpertWorkloadStats
)
from .scenario_tracking_integration import (
    ScenarioTrackingIntegration,
    TrackingIntegrationResult,
    get_tracking_integration,
    close_tracking_integration
)
from .scenario_tracking_exceptions import (
    ScenarioTrackingException,
    DatabaseConnectionError,
    DataValidationError,
    BatchProcessingError,
    TableInitializationError,
    QueryExecutionError,
    ServiceUnavailableError
)
from .scenario_tracking_metrics import (
    ScenarioTrackingMetrics,
    OperationMetrics,
    get_metrics_instance,
    record_operation_metric
)

__all__ = [
    "monitor",
    "InboxMonitor",
    "GraphAPIClient", 
    "EmailProcessor",
    "AzureAIFoundryClient",
    "ContactLookupService",
    "ResponseHandler",
    "RoundRobinService",
    "SalesforceClient",
    "ScenarioProcessor",
    # Scenario tracking
    "ScenarioTrackingClient",
    "ScenarioAnalyticsResult", 
    "CustomerInteractionHistory",
    "ExpertWorkloadStats",
    "ScenarioTrackingIntegration",
    "TrackingIntegrationResult",
    "get_tracking_integration",
    "close_tracking_integration",
    "ScenarioTrackingException",
    "DatabaseConnectionError",
    "DataValidationError", 
    "BatchProcessingError",
    "TableInitializationError",
    "QueryExecutionError",
    "ServiceUnavailableError",
    "ScenarioTrackingMetrics",
    "OperationMetrics",
    "get_metrics_instance",
    "record_operation_metric",
]
