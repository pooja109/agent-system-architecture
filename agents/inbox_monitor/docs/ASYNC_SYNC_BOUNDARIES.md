# Async/Sync Method Boundaries Documentation

This document defines the async/sync patterns used throughout the Inbox Monitor system and provides guidance for proper usage.

## Current Async/Sync Architecture

The system uses a **hybrid async/sync approach** with clear boundaries between async and sync operations.

### Async Method Categories

#### 1. Database Operations (ASYNC)
All database operations are implemented as async methods for optimal performance:

```python
# Scenario tracking models
async def from_processing_results(cls, results: dict) -> 'ScenarioProcessingRecord'

# Database clients
async def execute_query(self, query: str, parameters: dict = None)
async def get_connection(self) -> Connection
```

**Usage Pattern:**
```python
# ✅ CORRECT - await async database operations
record = await ScenarioProcessingRecord.from_processing_results(data)

# ❌ INCORRECT - will return coroutine object, not result
record = ScenarioProcessingRecord.from_processing_results(data)
```

#### 2. External Service Clients (ASYNC)
All external API calls and service integrations are async:

```python
# Azure services
async def get_secret(self, secret_name: str) -> str
async def send_request(self, endpoint: str, data: dict) -> dict

# Salesforce client  
async def create_case(self, case_data: dict) -> str
async def update_contact(self, contact_id: str, updates: dict) -> bool

# Graph API client
async def send_email(self, email_data: dict) -> dict
async def get_user_info(self, user_id: str) -> dict
```

#### 3. Resource Management (ASYNC)
Connection pools, resource cleanup, and lifecycle management:

```python
# Connection management
async def acquire_connection(self) -> Connection
async def release_connection(self, connection: Connection) -> None
async def cleanup_resources(self) -> None

# Health checks
async def check_service_health(self) -> HealthStatus
async def validate_connections(self) -> ValidationResult
```

### Sync Method Categories

#### 1. Configuration and Setup (SYNC)
System configuration, argument parsing, and initialization:

```python
# CLI argument parsing
def parse_arguments(self, args: List[str]) -> argparse.Namespace
def get_verbosity_config(self, args: argparse.Namespace) -> dict

# Environment detection
def detect_environment(self) -> EnvironmentType
def get_platform_info(self) -> dict

# Settings and configuration
def load_settings(self, config_path: str) -> Settings
def validate_configuration(self, config: dict) -> bool
```

#### 2. Data Processing and Validation (SYNC)
Data transformation, validation, and processing logic:

```python
# Email processing utilities
def extract_email_metadata(self, email_content: str) -> dict
def validate_email_format(self, email: str) -> bool
def format_response_content(self, content: str) -> str

# Validation utilities
def validate_pii_compliance(self, data: dict) -> ValidationResult
def sanitize_sensitive_data(self, content: str) -> str
```

#### 3. Logging and Monitoring (SYNC)
Logging, metrics, and monitoring operations:

```python
# Logging operations
def log_info(self, message: str, **kwargs) -> None
def log_error(self, message: str, error: Exception, **kwargs) -> None

# Metrics collection
def record_metric(self, name: str, value: float) -> None
def increment_counter(self, counter_name: str) -> None
```

## Usage Patterns and Best Practices

### 1. Async Service Integration Pattern

```python
class EmailProcessor:
    async def process_email_async(self, email_data: dict) -> ProcessingResult:
        """Main async processing pipeline."""
        # Database operations - ASYNC
        record = await ScenarioProcessingRecord.from_processing_results(email_data)
        
        # External service calls - ASYNC  
        response = await self.azure_client.send_request(endpoint, data)
        
        # Data processing - SYNC (called within async context)
        formatted_content = self.format_response_content(response['content'])
        
        return ProcessingResult(record, formatted_content)

    def process_email_sync(self, email_data: dict) -> ProcessingResult:
        """Sync wrapper for async operations."""
        return asyncio.run(self.process_email_async(email_data))
```

### 2. Database Operation Pattern

```python
# ✅ CORRECT - Async database operations
async def create_scenario_record(email_data: dict) -> ScenarioProcessingRecord:
    # Always await async factory methods
    record = await ScenarioProcessingRecord.from_processing_results(email_data)
    
    # Async database save
    await record.save()
    return record

# ✅ CORRECT - Sync wrapper when needed
def create_scenario_record_sync(email_data: dict) -> ScenarioProcessingRecord:
    return asyncio.run(create_scenario_record(email_data))
```

### 3. Service Client Pattern

```python
class ServiceManager:
    def __init__(self):
        # Sync initialization
        self.azure_client = AzureKeyVaultClient()
        self.salesforce_client = SalesforceClient()
    
    async def execute_workflow(self, workflow_data: dict) -> WorkflowResult:
        """Async workflow execution."""
        # Async service operations
        secrets = await self.azure_client.get_secret("api-key")
        case_id = await self.salesforce_client.create_case(workflow_data)
        
        # Sync data processing
        result = self.process_workflow_result(case_id, secrets)
        return result
    
    def process_workflow_result(self, case_id: str, secrets: dict) -> WorkflowResult:
        """Sync data processing."""
        # Pure data transformation - no I/O
        return WorkflowResult(case_id=case_id, processed_at=datetime.now())
```

## Event Loop Management

### Testing Context
```python
# In test files - proper async test setup
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations with proper event loop."""
    result = await ScenarioProcessingRecord.from_processing_results(test_data)
    assert result.processing_id == "expected-id"

# Mock async methods in tests
@pytest.fixture
def mock_async_factory():
    async def mock_from_processing_results(cls, data):
        return ScenarioProcessingRecord(processing_id=data.get('id'))
    return mock_from_processing_results
```

### Production Context
```python
# Entry point management
def main():
    """Main application entry point."""
    # Sync setup
    settings = load_settings()
    
    # Run async main loop
    asyncio.run(async_main(settings))

async def async_main(settings: Settings):
    """Async application loop."""
    # Async service startup
    await initialize_services(settings)
    
    # Main processing loop
    async for email in email_stream:
        await process_email(email)
```

## Error Handling Across Boundaries

### Async Error Propagation
```python
async def safe_async_operation() -> Optional[Result]:
    """Async operation with proper error handling."""
    try:
        return await risky_async_operation()
    except AsyncIOError as e:
        logger.error(f"Async operation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in async operation: {e}")
        raise AsyncOperationError(f"Operation failed: {e}") from e
```

### Sync Error Handling
```python
def safe_sync_operation() -> Optional[Result]:
    """Sync operation with proper error handling."""
    try:
        return risky_sync_operation()
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in sync operation: {e}")
        raise SyncOperationError(f"Operation failed: {e}") from e
```

## Common Anti-Patterns to Avoid

### ❌ Don't Do This

```python
# DON'T - Call async method without await
record = ScenarioProcessingRecord.from_processing_results(data)  # Returns coroutine!

# DON'T - Mix sync and async patterns incorrectly  
def mixed_function():
    # This creates nested event loop issues
    return asyncio.run(async_operation())

# DON'T - Block event loop with sync operations
async def blocking_async():
    time.sleep(5)  # Blocks event loop!
    return "result"
```

### ✅ Correct Patterns

```python
# DO - Always await async methods
record = await ScenarioProcessingRecord.from_processing_results(data)

# DO - Use proper async/sync boundaries
async def async_function():
    return await async_operation()

def sync_wrapper():
    return asyncio.run(async_function())

# DO - Use async-friendly operations in async context
async def non_blocking_async():
    await asyncio.sleep(5)  # Non-blocking sleep
    return "result"
```

## Migration Guidelines

### Converting Sync to Async
When converting sync methods to async:

1. **Add async keyword** to method definition
2. **Update all callers** to use await
3. **Replace blocking operations** with async equivalents
4. **Update tests** to use @pytest.mark.asyncio
5. **Handle event loop** management properly

### Converting Async to Sync  
When converting async methods to sync:

1. **Remove async keyword** from method definition
2. **Update all callers** to remove await
3. **Replace async operations** with sync equivalents
4. **Update tests** to remove asyncio markers
5. **Consider performance implications** of blocking operations

## Performance Considerations

### Async Benefits
- **Non-blocking I/O** - Better resource utilization
- **Concurrent processing** - Handle multiple operations simultaneously  
- **Scalable service integration** - Efficient external API usage

### Sync Benefits
- **Simpler debugging** - Easier to trace execution flow
- **Lower overhead** - No event loop management costs
- **Immediate execution** - No await/async complexity

## Architecture Decision Record

**Current Status**: The system uses hybrid async/sync architecture

**Decision**: Maintain clear boundaries between async I/O operations and sync data processing

**Rationale**: 
- Async for I/O operations provides performance benefits
- Sync for data processing provides simplicity and reliability  
- Clear boundaries prevent mixing patterns incorrectly

**Consequences**:
- Developers must understand async/sync boundaries
- Test setup requires async awareness
- Error handling must account for both patterns

This architecture provides optimal performance for I/O-bound operations while maintaining simplicity for data processing logic.