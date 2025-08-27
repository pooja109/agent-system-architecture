# Prompt Management System

A robust, scalable prompt management infrastructure for loading AI agent instructions from external YAML configuration files.

## Overview

The Prompt Management System provides centralized loading, validation, and caching of agent prompts from external YAML files. This enables prompt engineers to work independently from developers and allows for version control of AI instructions separate from code changes.

## Features

- **YAML-based Configuration Loading**: External prompt configurations with validation
- **High-Performance Caching**: In-memory caching with TTL support and hot-reloading
- **Schema Validation**: JSON schema validation for prompt structure integrity
- **Production-Ready Reliability**: Circuit breaker pattern, health checks, memory monitoring
- **Comprehensive Security**: Directory traversal protection, YAML injection prevention
- **Async/Await Support**: Non-blocking operations for high-performance applications
- **Extensive Testing**: 50+ tests with 80% coverage across all critical paths

## Quick Start

### Basic Usage

```python
import asyncio
from services.prompt_manager import PromptManager

async def main():
    # Initialize the prompt manager
    manager = PromptManager()
    
    # Load a prompt configuration
    config = await manager.load_prompt_config("email_classification")
    
    # Get system instructions
    instructions = await manager.get_system_instructions("email_classification")
    
    print(f"Agent: {config.agent_config.name}")
    print(f"Version: {config.agent_config.version}")
    print(f"Instructions length: {len(instructions)} characters")

asyncio.run(main())
```

### Advanced Configuration

```python
from pathlib import Path
from services.prompt_manager import PromptManager

# Custom configuration
manager = PromptManager(
    prompts_base_path=Path("./custom_prompts"),
    cache_ttl_seconds=600,           # 10 minute cache TTL
    enable_hot_reload=True,          # Development mode
    schema_validation=True,          # Enable JSON schema validation
    enable_circuit_breaker=True,     # Production resilience
    circuit_breaker_failure_threshold=3,
    circuit_breaker_recovery_timeout=30
)
```

## Directory Structure

```
prompts/
├── email_classification/
│   ├── system_instructions.yaml      # Main agent configuration
│   ├── classification_template.yaml  # Prompt templates
│   └── examples.yaml                 # Usage examples
├── schemas/
│   ├── system_instructions_schema.json  # Validation schemas
│   └── template_schema.json
└── README.md                         # This file
```

## Configuration Format

### System Instructions (system_instructions.yaml)

```yaml
agent_config:
  name: "email-intent-classifier"
  description: "AI agent for email intent classification"
  version: "1.0.0"
  author: "Your Team"

system_instructions: |
  You are an expert AI agent specializing in email intent classification.
  
  INTENT CATEGORIES TO CLASSIFY:
  1. POSITIVE - Customer shows genuine interest
  2. NEGATIVE - Customer clearly wants to stop communication
  3. SERVICE_INQUIRY - Customer has questions about existing services
  
  CONFIDENCE SCORING GUIDELINES:
  - High confidence (0.85-0.99): Clear intent with multiple indicators
  - Medium confidence (0.60-0.84): Reasonable intent but some ambiguity
  - Low confidence (0.30-0.59): Unclear intent or minimal content
  
  RESPONSE FORMAT:
  Always respond with valid JSON containing intent and confidence.

confidence_scoring:
  high:
    range: [0.85, 0.99]
    description: "Clear intent with multiple indicators"
  medium:
    range: [0.60, 0.84]
    description: "Reasonable intent but some ambiguity"
  low:
    range: [0.30, 0.59]
    description: "Unclear intent or minimal content"
  very_low:
    range: [0.10, 0.29]
    description: "Highly ambiguous signals"

response_format:
  type: "json"
  response_schema:
    intent: "string"
    confidence: "float"
    reasoning: "string"
```

### Template Configuration (template_name.yaml)

```yaml
template_version: "1.0.0"
template: |
  Please analyze this email and classify the sender's intent:
  
  EMAIL DETAILS:
  From: {sender_email}
  Subject: {subject}
  Body: {body}
  
  Analyze the context and provide classification in JSON format.

variables:
  sender_email:
    description: "Email address of sender"
    type: "string"
    required: true
  subject:
    description: "Email subject line"
    type: "string"  
    required: true
  body:
    description: "Email body content"
    type: "string"
    required: true
```

## API Reference

### PromptManager Class

#### Constructor
```python
PromptManager(
    prompts_base_path: Optional[Path] = None,
    cache_ttl_seconds: int = 300,
    enable_hot_reload: bool = False,
    schema_validation: bool = True,
    enable_circuit_breaker: bool = True,
    circuit_breaker_failure_threshold: int = 5,
    circuit_breaker_recovery_timeout: int = 60
)
```

#### Core Methods

##### `load_prompt_config(prompt_name: str) -> PromptConfig`
Loads and validates a prompt configuration from YAML file.

```python
config = await manager.load_prompt_config("email_classification")
```

##### `get_system_instructions(prompt_name: str) -> str`
Retrieves system instructions for a specific prompt.

```python
instructions = await manager.get_system_instructions("email_classification")
```

##### `load_template(prompt_name: str, template_name: str) -> TemplateConfig`
Loads a specific template configuration.

```python
template = await manager.load_template("email_classification", "classification_template")
```

#### Management Methods

##### `clear_cache(prompt_name: Optional[str] = None) -> None`
Clears cached prompts (all or specific prompt).

```python
manager.clear_cache()  # Clear all
manager.clear_cache("email_classification")  # Clear specific
```

##### `validate_all_prompts() -> Dict[str, bool]`
Validates all prompt configurations in the prompts directory.

```python
results = await manager.validate_all_prompts()
print(f"Validation results: {results}")
```

#### Monitoring Methods

##### `get_cache_statistics() -> Dict[str, Any]`
Retrieves cache performance statistics.

```python
stats = manager.get_cache_statistics()
print(f"Hit rate: {stats['hit_rate_percent']}%")
```

##### `get_memory_statistics() -> Dict[str, Any]`
Gets memory usage statistics for the PromptManager.

```python
memory = manager.get_memory_statistics()
print(f"Cache size: {memory['cache_memory_usage']['total_cache_size_mb']} MB")
```

##### `health_check() -> Dict[str, Any]`
Performs comprehensive health check of the system.

```python
health = await manager.health_check()
print(f"Status: {health['status']}")
```

## Production Deployment

### Performance Characteristics

- **Cold Start**: < 100ms for first prompt load
- **Cache Hit**: < 1ms for cached prompt retrieval
- **Memory Usage**: < 10MB for typical prompt collections
- **Concurrent Access**: Supports 100+ concurrent requests
- **File I/O**: < 50ms for YAML file parsing

### Recommended Production Settings

```python
# Production configuration
manager = PromptManager(
    prompts_base_path=Path("/app/prompts"),
    cache_ttl_seconds=3600,          # 1 hour cache
    enable_hot_reload=False,         # Disable in production
    schema_validation=True,          # Always validate
    enable_circuit_breaker=True,     # Enable resilience
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_timeout=60
)
```

### Health Monitoring

```python
# Health check endpoint example
from fastapi import FastAPI

app = FastAPI()

@app.get("/health/prompts")
async def prompt_health():
    health = await manager.health_check()
    return {
        "status": health["status"],
        "cache_stats": health["cache_status"],
        "memory_usage": health["memory_status"]["cache_memory_usage"]["total_cache_size_mb"],
        "validation_results": health["prompt_validation"]
    }
```

### Circuit Breaker Monitoring

```python
# Monitor circuit breaker status
stats = manager.get_cache_statistics()
if "circuit_breaker" in stats:
    cb = stats["circuit_breaker"]
    print(f"Circuit Breaker State: {cb['state']}")
    print(f"Failure Count: {cb['failure_count']}")
    print(f"Success Count: {cb['success_count']}")
```

## Error Handling

### Exception Types

- `PromptNotFoundError`: Prompt file or directory doesn't exist
- `PromptValidationError`: YAML structure or content validation failure
- `PromptCacheError`: Cache operation failures
- `TemplateRenderError`: Template rendering issues
- `SchemaValidationError`: JSON schema validation failures

### Example Error Handling

```python
from exceptions.prompt_exceptions import (
    PromptNotFoundError,
    PromptValidationError,
    PromptCacheError
)

try:
    config = await manager.load_prompt_config("nonexistent_prompt")
except PromptNotFoundError as e:
    print(f"Prompt not found: {e}")
except PromptValidationError as e:
    print(f"Validation error: {e}")
    if e.details and "validation_errors" in e.details:
        for error in e.details["validation_errors"]:
            print(f"  - {error}")
except PromptCacheError as e:
    print(f"Cache error: {e}")
```

## Development Workflow

### Creating New Prompts

1. Create directory: `prompts/{prompt_name}/`
2. Add `system_instructions.yaml` with required fields
3. Validate configuration: `await manager.validate_all_prompts()`
4. Test loading: `await manager.load_prompt_config("{prompt_name}")`

### Hot Reloading for Development

```python
# Enable hot reloading during development
manager = PromptManager(
    enable_hot_reload=True,
    cache_ttl_seconds=30  # Short TTL for development
)

# File changes will be automatically detected and cache invalidated
```

### Testing Your Prompts

```python
# Validate all prompts
results = await manager.validate_all_prompts()
for prompt_name, is_valid in results.items():
    if not is_valid:
        print(f"❌ {prompt_name} failed validation")
    else:
        print(f"✅ {prompt_name} validated successfully")
```

## Troubleshooting

### Common Issues

1. **FileNotFoundError**: Check that prompt directory and YAML files exist
2. **YAML Parsing Errors**: Validate YAML syntax with online validator
3. **Validation Errors**: Check against schema requirements
4. **Permission Errors**: Ensure read permissions on prompt directories
5. **Memory Issues**: Monitor cache size and clear if needed

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug logging
manager = PromptManager()
# All operations will now include detailed debug logs
```

### Performance Debugging

```python
# Monitor performance
import time

start = time.time()
config = await manager.load_prompt_config("email_classification")
load_time = (time.time() - start) * 1000

print(f"Load time: {load_time:.2f}ms")

# Check cache statistics
stats = manager.get_cache_statistics()
print(f"Cache hit rate: {stats['hit_rate_percent']}%")
```

## Contributing

1. Follow existing code patterns and type hints
2. Add comprehensive tests for new functionality
3. Update documentation for API changes
4. Ensure all tests pass: `pytest tests/`
5. Validate prompt schemas after changes

## License

This project is licensed under the same license as the parent project.

## Support

For issues and questions:
1. Check the troubleshooting guide
2. Review error logs with debug mode enabled
3. Validate YAML syntax and schema compliance
4. Test with minimal configuration first