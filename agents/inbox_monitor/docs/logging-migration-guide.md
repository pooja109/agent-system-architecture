# Logging Migration Guide

This guide provides step-by-step instructions for migrating from the current logging approach to the new Phase X dual-stream logging infrastructure.

> **📚 Related Documentation:**
> - **Configuration:** [Configuration Guide](CONFIGURATION.md) - Environment setup and authentication
> - **Utilities:** [Utilities Reference](UTILS.md) - Logging framework utilities and tools
> - **Services:** [Services Overview](SERVICES-OVERVIEW.md) - Service logging patterns
> - **Troubleshooting:** [Troubleshooting Guide](TROUBLESHOOTING.md) - Logging-related issues
> - **Testing:** [Testing Guide](TESTING.md) - Test logging configuration
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Overview

The new logging system provides:
- **Dual-stream architecture**: Clean console output + comprehensive structured logging
- **User-friendly console output**: Icons, colors, and readable formatting
- **Complete diagnostic information**: JSON structured logs for production analysis
- **Service integration helpers**: Easy adoption for existing services
- **Configuration system integration**: Works with existing config/settings.py

## Migration Phases

### Phase 1: Basic Setup (5 minutes)

Replace your current logging initialization with the new system:

**Before:**
```python
# Old logging setup in main.py
def setup_logging(level: str = "INFO", format_type: str = "json"):
    if format_type == "json":
        import structlog
        structlog.configure(...)
        logging.basicConfig(...)
```

**After:**
```python
# New logging setup
from utils.custom_logging import initialize_logging, LoggingConfig, get_logger
from config.settings import get_settings

def setup_logging():
    settings = get_settings()
    logging_config = LoggingConfig()  # Load from configuration
    initialize_logging(logging_config)
    
    # Get a logger for your module
    logger = get_logger("main")
    logger.info("Logging system initialized")
```

### Phase 2: Service Integration (10-15 minutes per service)

#### Option A: Decorator-based Integration (Recommended for new services)

```python
from utils.custom_logging.service_integration import ServiceLoggingIntegration

@integrate_service_logging
class EmailProcessor:
    def __init__(self, settings, graph_client):
        # Your existing initialization
        self.settings = settings
        self.graph_client = graph_client
        # Logging is automatically available as:
        # self.log, self.console_log, self.structured_log
        # self.log_info(), self.log_error(), etc.
        # self.user_info(), self.user_error(), etc.
    
    def process_email(self, email):
        # Clean user-facing message
        self.user_info(f"Processing email: {email.subject}")
        
        # Detailed diagnostic information
        self.log.debug("Email processing details", extra={
            "email_id": email.id,
            "sender": email.sender,
            "processing_stage": "validation"
        })
        
        try:
            # Your processing logic
            result = self._process_email_content(email)
            self.log_info("Email processed successfully", 
                         email_id=email.id, result_size=len(result))
            return result
        except Exception as e:
            # Automatic error logging with context
            self.log_error("Email processing failed", 
                          email_id=email.id, error=str(e), exc_info=True)
            raise
```

#### Option B: Instance-based Integration (For existing services)

```python
from utils.custom_logging import setup_service_logging

class GraphAPIClient:
    def __init__(self, settings):
        self.settings = settings
        # Add logging capabilities
        setup_service_logging(self, "graph_api")
    
    def make_request(self, method, endpoint):
        # User sees clean message
        self.user_info(f"Making {method} request to {endpoint}")
        
        # Logs get full details
        self.structured_log.debug("API request details", extra={
            "method": method,
            "endpoint": endpoint,
            "headers": self._safe_headers(),
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            response = self._make_actual_request(method, endpoint)
            self.log_info("API request successful", 
                         method=method, endpoint=endpoint, 
                         status_code=response.status_code)
            return response
        except Exception as e:
            self.log_error("API request failed", 
                          method=method, endpoint=endpoint, error=str(e))
            raise
```

### Phase 3: Print Statement Migration (5-10 minutes)

Replace existing print statements with appropriate logging:

**Before:**
```python
def process_inbox(self):
    print("🔄 Checking inbox...")
    print(f"📊 Found {len(emails)} emails")
    if error_count > 0:
        print(f"❌ {error_count} emails failed processing")
```

**After:**
```python
def process_inbox(self):
    # User-friendly console messages
    self.user_info("🔄 Checking inbox...")
    self.user_info(f"📊 Found {len(emails)} emails")
    
    # Detailed structured logging
    self.log.info("Inbox processing started", extra={
        "email_count": len(emails),
        "batch_size": self.batch_size,
        "processing_mode": self.mode
    })
    
    if error_count > 0:
        self.user_error(f"❌ {error_count} emails failed processing")
        self.log.error("Inbox processing completed with errors", extra={
            "total_emails": len(emails),
            "error_count": error_count,
            "success_rate": (len(emails) - error_count) / len(emails)
        })
```

**Automatic Migration Helper:**
```python
from utils.custom_logging import migrate_print_statements

# For quick migration of existing services
migrate_print_statements(service_instance, default_level="info")
# This replaces print with logging calls
```

### Phase 4: Error Handling Enhancement (10-15 minutes)

Enhance error handling with structured logging:

**Before:**
```python
try:
    result = dangerous_operation()
except Exception as e:
    logging.error(f"Operation failed: {e}")
    raise
```

**After:**
```python
from utils.custom_logging import log_service_error

try:
    result = dangerous_operation()
except Exception as e:
    # Structured error logging with context
    log_service_error(
        self.log, 
        "email_processor", 
        e, 
        operation="dangerous_operation",
        extra_context={
            "input_params": params,
            "processing_stage": current_stage,
            "retry_count": retry_count
        }
    )
    raise
```

## Service-Specific Migration Examples

### Azure Key Vault Client

```python
from utils.custom_logging import integrate_service_logging

@integrate_service_logging
class AzureKeyVaultClient:
    def get_secret(self, secret_name):
        # Clean user message (no sensitive data)
        self.user_info(f"Retrieving secret: {secret_name}")
        
        # Detailed logging (automatically redacted)
        self.log.debug("Key vault operation", extra={
            "operation": "get_secret",
            "secret_name": secret_name,
            "vault_url": self.vault_url
        })
        
        try:
            secret = self._get_secret_from_vault(secret_name)
            self.log_info("Secret retrieved successfully", secret_name=secret_name)
            return secret
        except Exception as e:
            self.log_error("Secret retrieval failed", 
                          secret_name=secret_name, error=str(e))
            raise
```

### Email Processing Service

```python
@integrate_service_logging
class EmailProcessor:
    def process_inbox(self):
        self.user_info("🚀 Starting inbox processing")
        
        emails = self._fetch_emails()
        self.log.info("Emails fetched", email_count=len(emails))
        
        for i, email in enumerate(emails):
            self.user_info(f"📧 Processing email {i+1}/{len(emails)}: {email.subject}")
            
            try:
                result = self._process_single_email(email)
                self.log.debug("Email processed", extra={
                    "email_id": email.id,
                    "subject": email.subject,
                    "result_type": type(result).__name__,
                    "processing_time": result.processing_time
                })
            except Exception as e:
                self.user_error(f"❌ Failed to process email: {email.subject}")
                self.log_error("Email processing failed", 
                              email_id=email.id, subject=email.subject)
```

### Database Connection Pool

```python
@integrate_service_logging  
class DatabricksConnectionPool:
    def get_connection(self):
        self.log.debug("Requesting connection from pool", extra={
            "available_connections": self.available_count,
            "total_connections": self.total_count,
            "waiting_requests": self.waiting_count
        })
        
        connection = self._get_from_pool()
        
        if connection:
            self.log.debug("Connection acquired", connection_id=connection.id)
        else:
            self.user_warning("⏳ Waiting for available connection...")
            self.log.warning("Connection pool exhausted", 
                           total_connections=self.total_count)
        
        return connection
```

## Testing Your Migration

### 1. Verify Dual Output
```python
from utils.custom_logging import get_logger, initialize_logging, LoggingConfig

# Initialize logging
config = LoggingConfig()
initialize_logging(config)

# Test dual output
logger = get_logger("test")
logger.info("This message appears in both console and structured logs")
logger.debug("This debug message only appears in structured logs")
```

### 2. Check Console Output
Run your service and verify:
- ✅ Clean, readable console messages with icons
- ✅ No verbose HTTP request/response logs in console
- ✅ User-friendly error messages
- ✅ Progress indicators working

### 3. Check Structured Logs
Verify structured logs contain:
- ✅ Complete diagnostic information
- ✅ Proper JSON formatting
- ✅ Exception details with stack traces
- ✅ Service context and metadata

## Configuration Integration

### Using Existing Settings

```python
# config/settings.py (your existing configuration)
class Settings:
    def __init__(self):
        self.environment = "development"
        self.debug = True
        self.log_level = "INFO"

# Your service
from utils.custom_logging import initialize_logging_from_settings
from config.settings import get_settings

settings = get_settings()
initialize_logging_from_settings(settings)
# Logging is now configured based on your existing settings
```

### Environment Variables
The system automatically detects:
- `ENVIRONMENT` or `ENV` → Sets logging environment
- `DEBUG` → Enables debug logging  
- `LOG_LEVEL` → Sets logging level
- `LOG_FILE` → Enables file logging

## Troubleshooting

### Common Issues

**Issue: "Logger not initialized" error**
```python
# Solution: Make sure to initialize logging first
from utils.custom_logging import initialize_logging_from_settings
initialize_logging_from_settings(settings)  # Add this before using loggers
```

**Issue: Print statements still appearing**
```python
# Solution: Use migrate_print_statements helper
from utils.custom_logging import migrate_print_statements
migrate_print_statements(service_instance)
```

**Issue: Too verbose console output**
```python
# Solution: Use console-only logger for user messages
from utils.custom_logging import get_console_logger
user_logger = get_console_logger("user_messages")
user_logger.info("Clean user message")  # Only goes to console
```

**Issue: Missing structured data**
```python
# Solution: Use structured-only logger for diagnostics
from utils.custom_logging import get_structured_logger
diagnostic_logger = get_structured_logger("diagnostics")
diagnostic_logger.info("Diagnostic data", extra={"detailed": "info"})
```

### Validation Checklist

After migration, verify:

- [ ] Console output is clean and user-friendly
- [ ] No sensitive data appears in logs
- [ ] Structured logs contain complete diagnostic info
- [ ] Exception handling includes proper context
- [ ] Service integration works correctly
- [ ] Performance impact is minimal (<5% overhead)
- [ ] All print statements have been replaced

## Performance Notes

The new logging system is designed for minimal performance impact:
- **Overhead**: <5% of application execution time
- **Memory**: <50MB additional memory usage
- **Threading**: Full thread safety with minimal locking
- **Buffering**: Intelligent buffering for high-volume scenarios

## Best Practices

### Do's
✅ **Use appropriate logger types**:
- `get_logger()` for dual output (most common)
- `get_console_logger()` for user-facing messages only
- `get_structured_logger()` for diagnostic data only

✅ **Include context in structured logs**:
```python
logger.info("Operation completed", extra={
    "operation_id": op_id,
    "duration": elapsed_time,
    "result_count": len(results)
})
```

✅ **Use service integration helpers**:
```python
@integrate_service_logging
class MyService:
    pass
```

### Don'ts
❌ **Don't log sensitive information**:
```python
# Bad
logger.info(f"User password: {password}")

# Good  
logger.info("User authentication successful", user_id=user_id)
```

❌ **Don't use print statements**:
```python
# Bad
print("Processing complete")

# Good
self.user_info("✅ Processing complete")
```

❌ **Don't skip error context**:
```python
# Bad
logger.error("Something failed")

# Good
logger.error("Email processing failed", extra={
    "email_id": email_id,
    "error_type": type(e).__name__,
    "processing_stage": stage
})
```

## Support

If you encounter issues during migration:

1. **Check the examples** in this guide for your specific use case
2. **Verify initialization** - ensure logging is initialized before use
3. **Test incrementally** - migrate one service at a time
4. **Use helper functions** - leverage the integration utilities provided

The migration should take 30-45 minutes for the entire codebase, with immediate benefits in terms of clean console output and comprehensive diagnostic logging.