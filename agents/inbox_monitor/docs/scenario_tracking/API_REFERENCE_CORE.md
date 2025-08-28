# Core API Reference - Inbox Monitor Scenario Tracking

## Overview

This document provides comprehensive API reference for the core scenario tracking system (Phases 1-3). The API includes database operations, configuration management, and service interfaces for storing and retrieving scenario processing data.

**Current Implementation**: The system uses table `mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev` with the `ScenarioTrackingClient` as the primary interface.

## ScenarioTrackingClient

The primary client interface for interacting with the scenario tracking system. This client provides high-performance storage and retrieval of scenario processing data with graceful error handling and performance optimization.

### Class Definition

```python
class ScenarioTrackingClient:
    """
    Scenario Tracking Client for comprehensive scenario processing data management.
    
    Provides high-performance storage and retrieval of scenario processing data
    with graceful error handling and performance optimization.
    """
```

### Constructor

```python
def __init__(self, table_suffix: str = "", config: ScenarioTrackingConfiguration = None)
```

**Parameters:**
- `table_suffix` (str): Table suffix for environment isolation (e.g., "_test", "_staging")
- `config` (ScenarioTrackingConfiguration, optional): Custom configuration override

**Example:**
```python
# Production client
async with ScenarioTrackingClient() as client:
    # Use client methods

# Test client with isolation
async with ScenarioTrackingClient(table_suffix="_test") as client:
    # Use client methods with isolated tables
```

### Context Manager Support

The client supports async context manager protocol for proper resource management:

```python
async def __aenter__(self) -> InboxMonitorDatabricksClient
async def __aexit__(self, exc_type, exc_val, exc_tb)
```

### Core Methods

#### store_scenario_processing_record

Store a single scenario processing record.

```python
async def store_scenario_processing_record(
    self, 
    record: ScenarioProcessingRecord
) -> bool
```

**Parameters:**
- `record` (ScenarioProcessingRecord): The scenario processing record to store

**Returns:**
- `bool`: True if storage was successful, False otherwise

**Example:**
```python
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from datetime import datetime, timezone

record = ScenarioProcessingRecord(
    process_id="unique-processing-id",
    email_id="email-message-id",
    sender_email="customer@company.com",
    received_datetime=datetime.now(timezone.utc),
    process_success=True,
    scenario_type=ScenarioType.SCENARIO_5,
    expert_assigned="John Doe",
    case_created="CASE12345"
)

async with ScenarioTrackingClient() as client:
    success = await client.store_scenario_processing_record(record)
    print(f"Storage successful: {success}")
```

#### get_recent_scenario_records

Retrieve recent scenario processing records.

```python
async def get_recent_scenario_records(
    self, 
    limit: int = 100
) -> List[ScenarioProcessingRecord]
```

**Parameters:**
- `limit` (int): Maximum number of records to retrieve (default: 100)

**Returns:**
- `List[ScenarioProcessingRecord]`: List of recent scenario processing records

**Example:**
```python
async with ScenarioTrackingClient() as client:
    recent_records = await client.get_recent_scenario_records(limit=50)
    print(f"Retrieved {len(recent_records)} recent records")
```

#### get_scenario_records_by_email_id

Get scenario records for a specific email ID.

```python
async def get_scenario_records_by_email_id(
    self, 
    email_id: str
) -> List[ScenarioProcessingRecord]
```

**Parameters:**
- `email_id` (str): The email ID to search for

**Returns:**
- `List[ScenarioProcessingRecord]`: List of scenario processing records for the email

**Example:**
```python
async with ScenarioTrackingClient() as client:
    email_records = await client.get_scenario_records_by_email_id("email-123")
    print(f"Found {len(email_records)} records for email")
```

#### get_scenario_records_by_sender

Get scenario records for a specific sender.

```python
async def get_scenario_records_by_sender(
    self, 
    sender_email: str
) -> List[ScenarioProcessingRecord]
```

**Parameters:**
- `sender_email` (str): The sender email to search for

**Returns:**
- `List[ScenarioProcessingRecord]`: List of scenario processing records from the sender

**Example:**
```python
async with ScenarioTrackingClient() as client:
    sender_records = await client.get_scenario_records_by_sender("customer@company.com")
    print(f"Found {len(sender_records)} records from sender")
```

### Health and Monitoring Methods

#### test_connection

Test the database connection.

```python
async def test_connection(self) -> bool
```

**Returns:**
- `bool`: True if connection is successful, False otherwise

**Example:**
```python
async with ScenarioTrackingClient() as client:
    if await client.test_connection():
        print("Database connection successful")
    else:
        print("Database connection failed")
```

#### get_health_status

Get detailed health status of the client.

```python
async def get_health_status(self) -> Dict[str, Any]
```

**Returns:**
- `Dict[str, Any]`: Dictionary with health status information

**Example:**
```python
async with ScenarioTrackingClient() as client:
    health = await client.get_health_status()
    print(f"Service status: {health['status']}")
    print(f"Circuit breaker status: {health.get('circuit_breaker', {})}")
```

#### get_performance_metrics

Get performance metrics.

```python
async def get_performance_metrics(self) -> Dict[str, Any]
```

**Returns:**
- `Dict[str, Any]`: Dictionary with performance metrics

**Example:**
```python
async with ScenarioTrackingClient() as client:
    metrics = await client.get_performance_metrics()
    print(f"Storage throughput: {metrics.get('storage_throughput', 'N/A')}")
```

#### flush_pending_operations

Flush any pending async operations.

```python
async def flush_pending_operations(self)
```

**Example:**
```python
async with ScenarioTrackingClient() as client:
    # ... perform operations
    await client.flush_pending_operations()  # Ensure all operations complete
```

## ScenarioProcessingRecord

Data model for scenario processing records.

### Class Definition

```python
class ScenarioProcessingRecord(BaseModel):
    """Comprehensive scenario processing record for storage and analytics."""
```

### Core Fields

#### Identifiers
- `process_id` (str): Unique processing identifier
- `email_id` (str): Email message identifier
- `correlation_id` (Optional[str]): Correlation identifier for tracking
- `conversation_id` (Optional[str]): Email conversation thread identifier

#### Email Information (PII - handle carefully)
- `sender_email` (str): Sender email address
- `sender_name` (Optional[str]): Sender display name
- `recipient_emails` (List[str]): List of recipient email addresses
- `subject` (Optional[str]): Email subject line (truncated for PII compliance)
- `email_body` (Optional[str]): Email body content (truncated for PII compliance)

#### Processing Results
- `received_datetime` (datetime): Email received timestamp
- `processed_at` (datetime): Processing timestamp (auto-generated)
- `process_success` (bool): Whether processing succeeded
- `processing_duration_ms` (Optional[int]): Processing duration in milliseconds
- `process_error` (Optional[str]): Error message if processing failed

#### Scenario Classification
- `scenario_type` (ScenarioType): Classified scenario type
- `email_intent` (Optional[str]): Email intent classified by email-intent-classifier agent
- `email_intent_confidence` (Optional[float]): Email intent classification confidence score (0.0-1.0)
- `email_intent_reasoning` (Optional[str]): Email intent classification reasoning
- `email_intent_detected_phrases` (List[str]): Key phrases detected by email intent classifier
- `email_intent_processing_duration_ms` (Optional[int]): Email intent classification processing time in milliseconds
- `email_intent_model_version` (Optional[str]): Email intent classifier model version
- `original_subject_result` (Optional[str]): Original subject extracted by original-subject-extractor agent
- `original_subject_confidence` (Optional[float]): Original subject extraction confidence score (0.0-1.0)
- `original_subject_reasoning` (Optional[str]): Original subject extraction reasoning

#### Scenario Outcomes
- `expert_assigned` (Optional[str]): Assigned expert name
- `expert_email` (Optional[str]): Assigned expert email
- `case_created` (Optional[str]): Created case identifier
- `emails_forwarded` (List[str]): List of emails that received forwards
- `forwarding_success` (Optional[bool]): Whether email forwarding succeeded
- `external_operations_status` (Dict[str, str]): Database updates performed
- `agent_actions_log` (List[str]): List of actions taken during processing

#### System Fields
- `test_mode` (Optional[bool]): Whether record was created in test mode
- `environment` (Optional[str]): Environment identifier
- `table_suffix` (Optional[str]): Table suffix used for storage

### Factory Methods

#### from_processing_results

Create record from email processing results.

```python
@classmethod
def from_processing_results(
    cls,
    email_data: Email,
    processing_result: ProcessingResult,
    scenario_result: Optional[ScenarioResult] = None,
    correlation_id: Optional[str] = None
) -> ScenarioProcessingRecord
```

**Parameters:**
- `email_data` (Email): Email data object
- `processing_result` (ProcessingResult): Processing result object
- `scenario_result` (ScenarioResult, optional): Scenario-specific result
- `correlation_id` (str, optional): Correlation identifier

**Returns:**
- `ScenarioProcessingRecord`: Constructed record

**Example:**
```python
record = ScenarioProcessingRecord.from_processing_results(
    email_data=email,
    processing_result=result,
    scenario_result=scenario_result,
    correlation_id="track-123"
)
```

### Data Serialization

#### to_databricks_dict

Serialize record for Databricks storage.

```python
def to_databricks_dict(self) -> Dict[str, Any]
```

**Returns:**
- `Dict[str, Any]`: Dictionary suitable for database insertion

**Example:**
```python
record = ScenarioProcessingRecord(...)
databricks_data = record.to_databricks_dict()
# Ready for database insertion
```

## ScenarioType Enumeration

Enumeration of supported scenario types.

```python
class ScenarioType(str, Enum):
    SCENARIO_5 = "scenario_5"      # Expert assignment required
    SCENARIO_6 = "scenario_6"      # Negative feedback handling
    SCENARIO_7 = "scenario_7"      # Service inquiry routing
    SCENARIO_8 = "scenario_8"      # Out of office handling
    SCENARIO_9 = "scenario_9"      # Invalid email handling
    SCENARIO_10 = "scenario_10"    # Employee departure handling
    SCENARIO_11 = "scenario_11"    # Unknown/unclassified scenarios
    UNKNOWN = "unknown"            # Fallback for unclassified
```

## ScenarioTrackingConfiguration

Configuration class for scenario tracking behavior.

```python
class ScenarioTrackingConfiguration(BaseModel):
    """Configuration for scenario tracking operations."""
    
    # Storage behavior
    enabled: bool = True
    async_insert: bool = True
    batch_insert_size: int = 50
    
    # Reliability settings
    retry_attempts: int = 3
    connection_timeout_seconds: int = 30
    
    # Performance settings
    max_connection_pool_size: int = 8
    performance_monitoring: bool = True
```

## Error Handling

The API uses specific exception types for different error conditions:

### ServiceUnavailableError
Raised when the service is temporarily unavailable (e.g., circuit breaker open).

### DataValidationError
Raised when record validation fails.

### DatabaseConnectionError
Raised when database connection fails.

### QueryExecutionError
Raised when database query execution fails.

### BatchProcessingError
Raised when batch processing fails significantly.

### TableInitializationError
Raised when table initialization fails.

## Response Formats

### Success Response
```python
{
    "success": True,
    "data": {...},
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### Error Response
```python
{
    "success": False,
    "error": "Error description",
    "error_type": "ErrorClassName",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### Health Check Response
```python
{
    "service_name": "scenario_tracking_client",
    "status": "healthy",  # healthy, degraded, unhealthy
    "timestamp": "2024-01-01T12:00:00Z",
    "checks": {
        "database_connectivity": {
            "status": "healthy",
            "response_time_ms": 45.2
        },
        "batch_queue": {
            "status": "healthy",
            "queue_size": 5
        }
    },
    "metrics": {
        "total_operations": 1000,
        "success_rate": 0.97,
        "average_response_time_ms": 120.5
    },
    "circuit_breaker": {
        "failures": 0,
        "is_open": false
    }
}
```

## Rate Limiting and Performance

### Throughput Targets
- **Core System**: 8+ records per second
- **Success Rate**: 90%+ under normal conditions
- **Storage Latency**: <500ms per record average
- **Batch Processing**: 50-100 record batches optimal

### Circuit Breaker
The client implements circuit breaker pattern:
- **Failure Threshold**: 5 consecutive failures
- **Timeout**: 5 minutes before retry
- **Automatic Reset**: On successful operation

### Connection Pooling
- **Max Connections**: 8 (configurable)
- **Connection Timeout**: 30 seconds
- **Retry Attempts**: 3

## Best Practices

### Error Handling
```python
async with ScenarioTrackingClient() as client:
    try:
        success = await client.store_scenario_processing_record(record)
        if not success:
            logger.warning("Storage failed but didn't raise exception")
    except ServiceUnavailableError:
        logger.error("Service temporarily unavailable")
        # Implement retry logic
    except DataValidationError as e:
        logger.error(f"Invalid record data: {e}")
        # Fix data and retry
```

### Performance Optimization
```python
# Use batch operations for multiple records
records = [record1, record2, record3]
async with client._client as underlying_client:
    result = await underlying_client.store_scenario_results_batch(records)
    
# Flush pending operations before closing
await client.flush_pending_operations()
```

### Resource Management
```python
# Always use context manager
async with ScenarioTrackingClient() as client:
    # Client will be properly closed
    pass

# For long-running services
client = InboxMonitorDatabricksClient()
try:
    await client.__aenter__()
    # Use client
finally:
    await client.__aexit__(None, None, None)
```

This API reference provides comprehensive coverage of the core scenario tracking system interfaces and best practices for integration.