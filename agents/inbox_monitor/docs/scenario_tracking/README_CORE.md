# Inbox Monitor Scenario Tracking System - Core Implementation

## Overview

This document covers the core implementation of the Inbox Monitor Scenario Tracking System, consisting of Phases 1-3:

- **Phase 1**: Database Schema and Models Setup
- **Phase 2**: Databricks Client Service Implementation  
- **Phase 3**: Email Processing Pipeline Integration

The core system provides comprehensive data storage and tracking for email scenario processing, creating the foundation for future analytics and monitoring capabilities.

## Core Architecture

### Phase 1: Database Foundation
- **Delta Table Schema**: Optimized for both transactional inserts and analytical queries
- **Pydantic Models**: Type-safe data structures with comprehensive validation
- **Data Transformation**: Utilities for converting between email processing and storage formats

### Phase 2: Storage Service
- **Async Databricks Client**: High-performance database operations with connection pooling
- **Error Resilience**: Graceful failure handling that never blocks email processing
- **Batch Optimization**: Efficient bulk storage operations

### Phase 3: Processing Integration
- **Pipeline Integration**: Seamless integration with existing email processing workflow
- **Background Storage**: Non-blocking async storage operations
- **Comprehensive Tracking**: Captures all scenario processing details and outcomes

## Quick Start

### Prerequisites

- Python 3.9+
- Databricks workspace with Unity Catalog enabled
- Azure Active Directory OAuth application
- Core Python packages: `pydantic`, `structlog`, `databricks-sdk`

### Installation

1. **Install Core Dependencies**
   ```bash
   pip install pydantic structlog databricks-sdk
   ```

2. **Configure Environment**
   ```bash
   export DATABRICKS_HOST="your-databricks-host"
   export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"
   export DATABRICKS_OAUTH_CLIENT_ID="your-oauth-client-id"
   export DATABRICKS_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
   ```

3. **Deploy Core System**
   ```bash
   python scripts/deployment/deploy_core_scenario_tracking.py --config config/core_production_config.yaml
   ```

### Basic Usage

#### Storing Scenario Processing Data

```python
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from services.scenario_tracking_client import ScenarioTrackingClient
from datetime import datetime, timezone

# Create scenario tracking record
record = ScenarioProcessingRecord(
    process_id="unique-processing-id",
    email_id="email-message-id",
    sender_email="customer@company.com",
    received_datetime=datetime.now(timezone.utc),
    process_success=True,
    scenario_type=ScenarioType.SCENARIO_5,
    expert_assigned="John Doe",
    case_created="CASE12345",
    agent_actions_log=["expert_assignment", "case_creation"]
)

# Store in Databricks - use the scenario tracking client
async with ScenarioTrackingClient() as client:
    success = await client.store_scenario_processing_record(record)
    print(f"Storage successful: {success}")
```

#### Integration with Email Processing

```python
# In your email processor integration
from models.email import Email
from services.scenario_processor import ScenarioProcessor

async def process_email_with_tracking(email_data: Email):
    # Process email through scenarios
    async with ScenarioProcessor() as processor:
        result = await processor.process_email_scenario(email_data)
    
    # Create tracking record from processing results
    tracking_record = ScenarioProcessingRecord.from_processing_results(
        email_data=email_data,
        processing_result=result,
        scenario_result=result.scenario_result,
        correlation_id="unique-correlation-id"
    )
    
    # Store tracking data (non-blocking)
    async with ScenarioTrackingClient() as client:
        await client.store_scenario_processing_record(tracking_record)
    
    return result
```

## Core Configuration

### Database Configuration

The system uses configuration from `config/settings.py` and environment variables:

```bash
# Environment variables for production deployment
export DATABRICKS_HOST="your-databricks-host"
export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"
export DATABRICKS_OAUTH_CLIENT_ID="your-oauth-client-id"
export DATABRICKS_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
export DATABRICKS_TABLE_SUFFIX="_dev"  # for development, "_prod" for production
```

### Actual Table Configuration

The system currently uses the table:
```
mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
```

With schema dynamically configured based on environment settings and table suffix.

## Data Model Reference

### ScenarioProcessingRecord

The core data model captures comprehensive information about each email processed:

```python
class ScenarioProcessingRecord(BaseModel):
    # Core identifiers
    process_id: str
    email_id: str
    correlation_id: Optional[str]
    
    # Email information (PII - handle carefully)
    sender_email: str
    sender_name: Optional[str]
    recipient_emails: List[str]
    subject: Optional[str]
    
    # Processing results
    process_success: bool
    processing_duration_ms: Optional[int]
    scenario_type: ScenarioType
    
    # Scenario-specific outcomes
    expert_assigned: Optional[str]
    case_created: Optional[str]
    emails_forwarded: List[str]
    external_operations_status: Dict[str, str]
    agent_actions_log: List[str]
    
    # Email Intent Classification (email-intent-classifier agent)
    email_intent: Optional[str]
    email_intent_confidence: Optional[float]
    email_intent_reasoning: Optional[str]
    email_intent_detected_phrases: List[str]
    email_intent_processing_duration_ms: Optional[int]
    email_intent_model_version: Optional[str]
    
    # Original Subject Extraction (original-subject-extractor agent)
    original_subject_result: Optional[str]
    original_subject_confidence: Optional[float]
    original_subject_reasoning: Optional[str]
```

### Key Methods

- `to_databricks_dict()`: Serialize for database storage
- `from_processing_results()`: Factory method to create from email processing
- `create_scenario_processing_record()`: Email model integration method

## Performance Optimization

### Core System Optimizations

1. **Connection Pooling**: Reuses database connections for efficiency
2. **Batch Processing**: Groups insertions for better throughput  
3. **Async Operations**: Non-blocking storage prevents email processing delays
4. **Data Partitioning**: Table partitioned by date for optimal queries
5. **Selective Indexing**: Indexes on frequently queried fields

### Performance Targets

- **Storage Throughput**: 8+ records per second
- **Success Rate**: 90%+ under normal conditions
- **Processing Impact**: <5% overhead on email processing
- **Storage Latency**: <500ms per record average

## Error Handling

### Graceful Degradation

The core system is designed to never impact email processing:

```python
# Storage failures are handled gracefully
try:
    await client.store_scenario_result(record)
except Exception as e:
    logger.warning("Scenario tracking storage failed", error=str(e))
    # Email processing continues normally
```

### Retry Mechanisms

- **Connection Failures**: Automatic retry with exponential backoff
- **Transient Errors**: 3 retry attempts with increasing delays
- **Batch Failures**: Individual record retry for partial batch success
- **Circuit Breaker**: Temporary disable on persistent failures

### Error Monitoring

Basic error monitoring is built into the core system:
- Storage success/failure rates
- Connection pool health
- Processing time metrics
- Data validation errors

## Security and Compliance

### PII Data Handling

The system handles Personally Identifiable Information (PII):

- **Email Addresses**: Customer and expert email addresses
- **Names**: Customer and expert names
- **Content**: Limited email subject and preview text
- **Account Data**: Salesforce account and contact information

### Security Measures

- **OAuth Authentication**: All database connections use OAuth 2.0
- **Environment Variables**: No hardcoded secrets in code
- **Data Limits**: Email content truncated to prevent excessive storage
- **Access Control**: Database-level access controls
- **Audit Trail**: Comprehensive logging of data access

### Compliance Features

- **Data Retention**: Configurable retention policies
- **Right to Deletion**: Support for data removal requests
- **Access Logging**: Audit trail for data access
- **Data Minimization**: Only necessary data is stored

## Troubleshooting

### Common Issues

1. **Storage Failures**
   ```bash
   # Check database connectivity
   python -c "import asyncio; from services.databricks_connection_pool import get_connection_pool; asyncio.run(get_connection_pool())"
   ```

2. **Performance Issues**
   ```bash
   # Check connection pool status
   python -c "import asyncio; from services.scenario_tracking_client import ScenarioTrackingClient; asyncio.run(ScenarioTrackingClient().health_check())"
   ```

3. **Data Validation Errors**
   ```python
   # Validate record before storage
   try:
       record = ScenarioProcessingRecord(**data)
       print("Record is valid")
   except ValidationError as e:
       print(f"Validation failed: {e}")
   ```

### Diagnostic Queries

```sql
-- Check recent processing activity
SELECT 
    DATE(processed_at) as date,
    COUNT(*) as total_processed,
    AVG(processing_duration_ms) as avg_time,
    COUNT(CASE WHEN process_success THEN 1 END) as successful
FROM inbox_monitor_scenario_processing
WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 7 DAYS
GROUP BY DATE(processed_at)
ORDER BY date DESC;

-- Check scenario distribution
SELECT 
    scenario_type,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
FROM inbox_monitor_scenario_processing
WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
GROUP BY scenario_type
ORDER BY count DESC;
```

## Future Enhancements

The core system is designed to support future analytics and monitoring phases:

### Phase 4 Preparation
- Data is structured for efficient analytics queries
- Performance metrics are captured for trend analysis
- Customer interaction patterns are tracked

### Phase 5 Preparation  
- Health check hooks are available
- Performance monitoring data is collected
- Error tracking provides foundation for alerting

## Testing

### Core Test Suite

```bash
# Run core integration tests
python -m pytest tests/scenario_tracking/test_core_integration.py -v

# Run performance benchmarks
python -m pytest tests/scenario_tracking/test_storage_performance.py -v -m benchmark

# Validate production readiness
python scripts/testing/validate_core_production_readiness.py
```

### Test Coverage

The core system maintains >90% test coverage across:
- Unit tests for data models and validation
- Integration tests for database operations
- Performance tests for throughput validation
- Security tests for compliance verification

## Support

For core system issues:
1. Check this troubleshooting section
2. Review application logs
3. Run diagnostic queries
4. Contact development team

The core system provides a solid foundation for comprehensive scenario tracking, ready for future enhancement with analytics and monitoring capabilities.