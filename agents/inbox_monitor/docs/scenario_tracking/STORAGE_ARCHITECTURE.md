# Storage Architecture for Scenario Tracking System

## Overview

The scenario tracking system uses a layered storage architecture designed for high performance, reliability, and scalability. This document details the storage components and their interactions.

## Architecture Layers

### 1. Data Model Layer (Phase 1)

#### Pydantic Models
- **ScenarioProcessingRecord**: Primary data model for scenario tracking
- **ScenarioTrackingConfiguration**: Configuration management model
- **Supporting Enums**: ScenarioType, AIIntent, etc.

#### Key Features
- **Type Safety**: Runtime validation of all data
- **Serialization**: Automatic conversion to Databricks-compatible formats
- **PII Handling**: Built-in truncation and validation for sensitive data
- **Audit Fields**: Comprehensive tracking of data lifecycle

```python
# Example data flow
email_data -> ScenarioProcessingRecord -> to_databricks_dict() -> Delta Table
```

### 2. Storage Service Layer (Phase 2)

#### ScenarioTrackingClient
High-performance async client for Databricks operations.

**Core Capabilities:**
- **Connection Pooling**: Efficient resource management
- **Batch Operations**: Optimized bulk insertions
- **Circuit Breaker**: Automatic failure handling
- **Retry Logic**: Resilient error recovery

#### Performance Architecture

```
┌─────────────────────┐
│   Application       │
│   Layer            │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│ ScenarioTracking    │
│ Client             │
├─────────────────────┤
│ • Async Operations  │
│ • Batch Processing  │
│ • Circuit Breaker   │
│ • Health Monitoring │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│ Connection Pool     │
├─────────────────────┤
│ • OAuth Client      │
│ • Pool Management   │
│ • Connection Reuse  │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│ Databricks          │
│ Delta Lake         │
└─────────────────────┘
```

### 3. Integration Layer (Phase 3)

#### Email Processing Integration
Seamless integration with existing email processing pipeline.

**Integration Points:**
- **Scenario Processor**: Captures scenario classification results
- **Email Processor**: Records processing outcomes
- **Pipeline Events**: Tracks email lifecycle stages

#### Non-Blocking Design
Storage operations run asynchronously to prevent email processing delays.

```python
async def process_email_with_tracking(email):
    # Primary processing (blocking)
    result = await process_email(email)
    
    # Storage tracking (non-blocking)
    asyncio.create_task(store_tracking_data(email, result))
    
    return result  # Immediate return
```

## Database Schema Design

### Table Structure

```sql
CREATE TABLE inbox_monitor_scenario_processing (
    -- Primary identifiers
    process_id STRING NOT NULL,
    email_id STRING NOT NULL,
    correlation_id STRING,
    
    -- Email metadata (PII)
    sender_email STRING NOT NULL,
    sender_name STRING,
    recipient_emails ARRAY<STRING>,
    subject STRING,
    
    -- Processing results
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    process_success BOOLEAN NOT NULL,
    processing_duration_ms INT,
    scenario_type STRING,
    
    -- Scenario outcomes
    expert_assigned STRING,
    case_created STRING,
    emails_forwarded ARRAY<STRING>,
    external_operations_status MAP<STRING, STRING>,
    agent_actions_log ARRAY<STRING>,
    
    -- AI classification
    email_intent STRING,
    email_intent_confidence DOUBLE,
    email_intent_reasoning STRING,
    email_intent_detected_phrases ARRAY<STRING>,
    email_intent_processing_duration_ms BIGINT,
    email_intent_model_version STRING,
    original_subject_result STRING,
    original_subject_confidence DOUBLE,
    original_subject_reasoning STRING,
    
    -- Audit and lifecycle
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    created_by STRING DEFAULT 'inbox_monitor'
)
USING DELTA
PARTITIONED BY (DATE(processed_at))
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true'
);
```

### Partitioning Strategy

#### Date-Based Partitioning
- **Partition Key**: `DATE(processed_at)`
- **Benefits**: 
  - Efficient time-range queries
  - Automatic data lifecycle management
  - Optimized for analytical workloads

#### Indexing Strategy
- **Primary Index**: process_id (unique identifier)
- **Secondary Indexes**: 
  - email_id (email lookups)
  - sender_email (customer queries)
  - scenario_type (analytics)

## Performance Optimizations

### 1. Connection Management

#### Connection Pooling
```python
class ConnectionPool:
    max_connections: int = 8
    connection_timeout: int = 30
    retry_attempts: int = 3
    
    async def get_connection(self):
        # Reuse existing connections
        # Handle connection lifecycle
        # Manage pool capacity
```

#### OAuth Token Management
- **Token Caching**: Reuse valid tokens
- **Automatic Refresh**: Handle token expiration
- **Secure Storage**: Environment-based configuration

### 2. Batch Operations

#### Intelligent Batching
```python
# Adaptive batch sizing based on performance
if processing_time < target_time:
    batch_size = min(batch_size * 1.2, max_batch_size)
else:
    batch_size = max(batch_size * 0.8, min_batch_size)
```

#### Transaction Management
- **Batch Transactions**: Group operations for consistency
- **Partial Success**: Handle mixed success/failure scenarios
- **Rollback Strategy**: Clean failure recovery

### 3. Data Optimization

#### PII Data Management
```python
# Automatic data truncation
subject = subject[:500] + "..." if len(subject) > 500 else subject
email_body = email_body[:255] if len(email_body) > 255 else email_body
```

#### Compression and Encoding
- **Delta Lake Compression**: Automatic compression
- **Column Optimization**: Efficient encoding for common data patterns
- **Partition Pruning**: Query optimization through partitioning

## Scalability Architecture

### Horizontal Scaling

#### Multiple Client Instances
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │    │   Client    │    │   Client    │
│ Instance 1  │    │ Instance 2  │    │ Instance 3  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └─────────────────┬──────────────────┘
                         │
                ┌────────▼────────┐
                │ Connection Pool  │
                │  Load Balancer   │
                └────────┬────────┘
                         │
                ┌────────▼────────┐
                │   Databricks    │
                │   Cluster       │
                └─────────────────┘
```

#### Auto-Scaling Considerations
- **Connection Pool Limits**: Prevent database overload
- **Rate Limiting**: Manage request volumes
- **Circuit Breaker**: Automatic failure protection

### Vertical Scaling

#### Memory Management
- **Object Pooling**: Reuse expensive objects
- **Garbage Collection**: Efficient memory cleanup
- **Buffer Management**: Optimal memory utilization

#### CPU Optimization
- **Async Operations**: Non-blocking I/O
- **Concurrent Processing**: Parallel batch operations
- **CPU-Aware Batching**: Size batches for CPU capacity

## Monitoring and Observability

### Performance Metrics

#### Core Metrics
```python
class StorageMetrics:
    records_per_second: float
    average_latency_ms: float
    success_rate_percentage: float
    connection_pool_utilization: float
    batch_efficiency: float
    error_rate: float
```

#### Health Checks
```python
async def health_check():
    return {
        "database_connectivity": "healthy",
        "connection_pool": "healthy", 
        "batch_queue_size": 5,
        "circuit_breaker_status": "closed",
        "last_successful_operation": "2024-01-15T10:30:00Z"
    }
```

### Error Tracking

#### Error Categories
- **Connection Errors**: Database connectivity issues
- **Validation Errors**: Data model violations
- **Performance Errors**: Timeout and latency issues
- **Business Logic Errors**: Scenario processing failures

#### Error Handling Strategy
```python
async def resilient_storage(record):
    for attempt in range(max_retries):
        try:
            return await store_record(record)
        except TransientError:
            await asyncio.sleep(backoff_delay(attempt))
        except PermanentError:
            log_error_and_alert(record)
            return False
    
    return False  # All retries exhausted
```

## Security Architecture

### Data Protection

#### PII Handling
- **Field-Level Truncation**: Automatic data limiting
- **Access Control**: Database-level permissions
- **Audit Logging**: Comprehensive access tracking
- **Data Minimization**: Store only necessary information

#### Encryption
- **In Transit**: TLS/HTTPS for all connections
- **At Rest**: Databricks encryption at rest
- **Token Security**: Secure OAuth token handling

### Compliance Features

#### GDPR Compliance
```python
# Data subject rights support
async def delete_customer_data(customer_email):
    # Anonymize or delete customer records
    pass

async def export_customer_data(customer_email):
    # Export all customer data
    pass
```

#### Audit Trail
- **Operation Logging**: All database operations logged
- **Access Tracking**: User and system access records
- **Change History**: Delta Lake time travel capabilities

## Disaster Recovery

### Backup Strategy

#### Automated Backups
- **Delta Lake Snapshots**: Point-in-time recovery
- **Cross-Region Replication**: Geographic redundancy
- **Incremental Backups**: Efficient storage utilization

#### Recovery Procedures
```bash
# Point-in-time recovery
RESTORE TABLE scenario_processing 
TO TIMESTAMP AS OF '2024-01-15T10:00:00'

# Version-based recovery
RESTORE TABLE scenario_processing
TO VERSION AS OF 123
```

### High Availability

#### Multi-Region Deployment
```
Primary Region (East)     Secondary Region (West)
┌─────────────────────┐   ┌─────────────────────┐
│ Active Databricks   │◄──┤ Standby Databricks  │
│ Cluster            │   │ Cluster            │
└─────────────────────┘   └─────────────────────┘
         │                          │
┌─────────▼─────────┐       ┌─────────▼─────────┐
│ Active Storage    │◄──────┤ Replicated Storage │
│ (Delta Lake)      │       │ (Delta Lake)       │
└───────────────────┘       └───────────────────┘
```

#### Failover Mechanisms
- **Automatic Detection**: Health monitoring and failure detection
- **Traffic Routing**: DNS-based failover
- **Data Synchronization**: Real-time replication

## Future Enhancements

### Analytics Preparation (Phase 4)
- **Aggregation Tables**: Pre-computed analytics
- **Data Marts**: Business intelligence optimization
- **Real-Time Streaming**: Event-driven analytics

### Advanced Monitoring (Phase 5)
- **Predictive Alerting**: Machine learning-based monitoring
- **Performance Optimization**: Automated tuning
- **Capacity Planning**: Usage-based scaling

The storage architecture provides a robust foundation for the scenario tracking system, designed for current needs while enabling future scalability and feature enhancement.