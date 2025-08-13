# Inbox Monitor Services Architecture

This document provides a comprehensive technical overview of all services within the `agents/inbox_monitor/services` folder. Each service is designed to handle specific aspects of the inbox monitoring and email processing pipeline.

> **📚 Related Documentation:**
> - **Understanding Workflows:** [Scenarios Guide](SCENARIOS.md) - Business logic and email processing scenarios
> - **Configuration:** [Configuration Guide](CONFIGURATION.md) - Service authentication and setup
> - **UI System:** [UI Components Overview](UI_COMPONENTS_OVERVIEW.md) - User interface architecture
> - **Developer Tools:** [Utilities Reference](UTILS.md) - Supporting utilities and scripts
> - **Testing Services:** [Testing Guide](TESTING.md) - Service testing and validation
> - **Troubleshooting:** [Troubleshooting Guide](TROUBLESHOOTING.md) - Service-related issues
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Overview

The inbox monitor system follows a microservices-inspired architecture where each service has a specific responsibility. Services are organized into several categories:

- **Core Processing Services**: Handle the main email processing workflow
- **External Integration Services**: Manage connections to external systems (Azure, Salesforce, Databricks)
- **Infrastructure Services**: Provide foundational capabilities (logging, connection pooling, health monitoring)
- **Utility Services**: Support services for template rendering, formatting, etc.

---

## Core Processing Services

### Email Processor
**File**: `email_processor.py`

The main orchestrator for email processing operations within the inbox monitor system.

**Key Responsibilities**:
- Coordinates the complete email processing workflow
- Manages email intake, validation, and processing pipeline
- Handles email content normalization and preparation for downstream services
- Provides structured logging throughout the processing lifecycle

**Key Features**:
- Asynchronous processing capabilities
- Comprehensive error handling and recovery
- Performance metrics tracking
- Integration with business logic logging

**Dependencies**: Configuration settings, logging infrastructure, business logic logger mixin

---

### Scenario Processor
**File**: `scenario_processor.py`

Processes email scenarios (5-11) including intent classification, expert assignment, and case creation.

**Key Responsibilities**:
- Classifies incoming emails using AI intent detection
- Routes emails to appropriate processing scenarios (5-11)
- Orchestrates multi-step workflows for each scenario type
- Manages scenario-specific business logic

**Supported Scenarios**:
- **Scenario 5**: Positive response - Creates Salesforce case and assigns to expert
- **Scenario 6**: Negative response - Forwards to Victoria Grant
- **Scenario 7**: Service inquiry - Forwards to account team
- **Scenario 8**: Out of office - Updates Databricks table
- **Scenario 9**: Invalid email - Updates Salesforce Invalid_Email field
- **Scenario 10**: No longer works - Forwards to Victoria Grant
- **Scenario 11**: [Reserved for future use]

**Key Features**:
- AI-powered email intent classification using Azure AI Foundry
- Content cleaning and formatting before AI analysis
- Test mode support with email substitution
- Comprehensive error handling with timeout protection
- Integration with all external services (Salesforce, Databricks, email forwarding)

**Dependencies**: Azure AI Foundry Client, Contact Lookup Service, Round Robin Service, Salesforce Client, Email Forwarding Manager, Content Formatter

---

### Response Handler
**File**: `response_handler.py`

Simplified response handler for processing email responses without scheduling dependencies.

**Key Responsibilities**:
- Processes customer email responses
- Integrates with scenario processor for response routing
- Provides comprehensive response logging and tracking
- Handles response metadata extraction

**Key Features**:
- Response ID generation for tracking
- Customer information extraction from emails
- Integration with scenario processing pipeline
- Structured logging with correlation IDs

**Dependencies**: Scenario Processor, Business Logic Logger Mixin

---

### Monitor
**File**: `monitor.py`

Main inbox monitoring service that orchestrates the entire email monitoring and processing workflow.

**Key Responsibilities**:
- Monitors designated email inboxes for new messages
- Coordinates email retrieval and processing
- Manages monitoring lifecycle (start, stop, health checks)
- Provides monitoring status and metrics

**Key Features**:
- Continuous inbox monitoring with configurable intervals
- Integration with Graph API for email retrieval
- Comprehensive error handling and recovery mechanisms
- Performance monitoring and metrics collection
- Graceful shutdown handling

**Dependencies**: Graph API Client, Email Processor, configuration settings

---

## External Integration Services

### Azure AI Foundry Client
**File**: `azure_ai_foundry_client.py`

Provides AI-powered email intent classification using Azure AI Foundry services.

**Key Responsibilities**:
- Classifies email intents (positive, negative, service inquiry, etc.)
- Manages Azure AI Foundry API interactions
- Processes and validates AI classification responses
- Provides confidence scoring and reasoning

**Supported Intent Classifications**:
- `POSITIVE`: Customer interested in services
- `NEGATIVE`: Customer declining services
- `SERVICE_INQUIRY`: Customer requesting service information
- `OUT_OF_OFFICE`: Automated out-of-office responses
- `EMAIL_INVALID`: Bounced/invalid email notifications
- `NO_LONGER_WORKS`: Person no longer at company
- `UNKNOWN`: Unable to classify intent

**Key Features**:
- Asynchronous HTTP client with proper timeout handling
- Circuit breaker pattern for resilience
- Response validation and error handling
- Performance metrics tracking

**Dependencies**: Azure Key Vault Client for credentials, HTTPX for HTTP operations

---

### Salesforce Client
**File**: `salesforce_client.py`

Client for interacting with Salesforce API to create cases and update contacts.

**Key Responsibilities**:
- OAuth authentication with Salesforce
- Case creation with enhanced field mapping
- Contact updates for email validation status
- SOQL query execution
- Organization information retrieval

**Key Features**:
- Automatic token refresh with expiration handling
- Circuit breaker pattern for API resilience
- HTTP/2 support with fallback to HTTP/1.1
- Enhanced case creation with proper categorization fields
- Boolean field updates for email validity tracking
- Comprehensive error handling and logging

**API Capabilities**:
- Create cases with full field mapping (Type, Request_Case_Category__c, etc.)
- Update contact `Is_Email_Invalid__c` field
- Execute custom SOQL queries
- Retrieve organization metadata

**Dependencies**: Circuit Breaker service, API Client Logger Mixin

---

### Graph API Client
**File**: `graph_api_client.py`

Client for Microsoft Graph API operations, primarily for email retrieval and management.

**Key Responsibilities**:
- Manages Microsoft Graph API authentication
- Retrieves emails from specified inboxes
- Handles email metadata processing
- Provides email filtering and querying capabilities

**Key Features**:
- OAuth2 token management with automatic refresh
- Efficient email pagination and batching
- Email content parsing and normalization
- Rate limiting and retry logic
- Comprehensive API error handling

**Dependencies**: Azure Key Vault Client for credentials, circuit breaker patterns

---

### Azure Key Vault Client
**File**: `azure_key_vault_client.py`

Manages secure credential retrieval from Azure Key Vault for various external service integrations.

**Key Responsibilities**:
- Secure retrieval of API credentials and secrets
- Azure authentication for Key Vault access
- Credential caching and refresh management
- Support for various credential types (AI Foundry, Salesforce, Graph API)

**Key Features**:
- DefaultAzureCredential authentication
- Credential validation and error handling
- Test mode support for development
- Structured logging for security audit trails

**Supported Credentials**:
- Azure AI Foundry API keys and endpoints
- Salesforce OAuth credentials
- Microsoft Graph API credentials
- Database connection strings

**Dependencies**: Azure SDK libraries, structured logging

---

### Databricks OAuth Client
**File**: `databricks_oauth_client.py`

OAuth-authenticated client for Databricks SQL operations with enhanced security and performance.

**Key Responsibilities**:
- OAuth2 authentication with Databricks
- SQL query execution with parameterization
- Connection management and optimization
- Performance monitoring and logging

**Key Features**:
- OAuth2 token lifecycle management
- SQL injection prevention through parameterization
- Connection pooling integration
- Query performance tracking
- Comprehensive error handling

**Dependencies**: OAuth2 libraries, connection pool infrastructure

---

### Databricks Connection Pool
**File**: `databricks_connection_pool.py`

Thread-safe connection pooling system for OAuth-authenticated Databricks clients.

**Key Responsibilities**:
- Manages pool of Databricks OAuth connections
- Provides thread-safe connection acquisition/release
- Handles connection lifecycle and health checks
- Optimizes performance through connection reuse

**Key Features**:
- Thread-safe connection management with context managers
- Configurable pool sizing and timeouts
- Connection health validation
- Performance metrics and monitoring
- Automatic connection cleanup and resource management

**Pool Configuration Options**:
- `max_size`: Maximum number of connections
- `min_size`: Minimum number of connections to maintain
- `max_idle_time`: Maximum time a connection can be idle
- `health_check_interval`: Frequency of connection health checks

**Dependencies**: Databricks OAuth Client, threading primitives, structured logging

---

### Databricks Warehouse Manager
**File**: `databricks_warehouse_manager.py`

Advanced warehouse management service with pre-warming capabilities and intelligent resource optimization.

**Key Responsibilities**:
- Manages Databricks SQL warehouse lifecycle
- Implements warehouse pre-warming strategies
- Optimizes query performance through warehouse state management
- Provides warehouse health monitoring and diagnostics

**Key Features**:
- Automatic warehouse startup and pre-warming
- Query optimization through warehouse state awareness
- Performance monitoring with detailed metrics
- Intelligent resource allocation
- Cost optimization through efficient warehouse management

**Management Capabilities**:
- Warehouse state detection (starting, running, stopped)
- Automatic scaling based on workload
- Performance benchmark tracking
- Resource utilization optimization

**Dependencies**: Databricks OAuth Client, performance monitoring infrastructure

---

## Infrastructure Services

### Pooled Service Base
**File**: `pooled_service_base.py`

Abstract base class for services that require connection pooling capabilities.

**Key Responsibilities**:
- Provides connection pool integration pattern
- Defines standard interface for pooled operations
- Handles connection acquisition and release
- Provides base error handling and logging

**Key Features**:
- Abstract base class with connection pool integration
- Context manager support for automatic resource cleanup
- Error handling patterns for connection failures
- Performance monitoring hooks

**Pattern Usage**:
```python
async def service_operation(self, *args):
    return await self.execute_with_connection(
        self._operation_impl, *args
    )
```

**Dependencies**: Connection pool infrastructure, structured logging

---

### Contact Lookup Service
**File**: `contact_lookup_service.py`

Provides Salesforce contact and account information lookup from Databricks data warehouse.

**Key Responsibilities**:
- Looks up Salesforce contact IDs by email address
- Retrieves associated account information
- Manages lookup table queries and caching
- Handles test mode email substitutions

**Key Features**:
- Efficient contact lookup with single query optimization
- Account name and ID retrieval
- Test mode support for development
- Connection pooling for performance
- Comprehensive error handling and fallback logic

**Lookup Table**: `snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t`

**Dependencies**: Databricks Connection Pool, OAuth Client, test mode settings

---

### Round Robin Service
**File**: `round_robin_service.py`

Manages round-robin assignment of leads to Low Touch Experts using Databricks for data storage.

**Key Responsibilities**:
- Implements round-robin assignment algorithm
- Manages expert availability and assignment tracking
- Creates and maintains assignment records
- Provides assignment statistics and reporting

**Key Features**:
- True round-robin distribution based on assignment count and timestamps
- Integration with `active_rep_pool_v` view for expert management
- Assignment status tracking (assigned, out_of_office, email_invalid, etc.)
- Test mode support for email substitution
- Comprehensive assignment analytics

**Database Tables**:
- **Assignment Table**: `expert_lead_assignments{suffix}` (tracks all assignments)
- **Expert View**: `active_rep_pool_v` (active expert pool)

**Assignment Algorithm**:
1. Query active experts with current assignment counts
2. Select expert with lowest assignment count
3. For ties, select expert with oldest last assignment date
4. Create assignment record with updated counts

**Dependencies**: Databricks Connection Pool, Pooled Service Base, test mode settings

---

### Circuit Breaker
**File**: `circuit_breaker.py`

Implements circuit breaker pattern for resilient external service communication.

**Key Responsibilities**:
- Prevents cascade failures in distributed systems
- Provides configurable failure thresholds and recovery timeouts
- Monitors service health and availability
- Offers circuit state management (closed, open, half-open)

**Key Features**:
- Configurable failure thresholds and recovery periods
- Automatic circuit state transitions
- Exception type filtering for circuit breaker triggers
- Performance metrics and monitoring hooks
- Thread-safe operation

**Circuit States**:
- **Closed**: Normal operation, calls pass through
- **Open**: Service assumed down, calls fail immediately
- **Half-Open**: Testing service recovery, limited calls allowed

**Dependencies**: Threading primitives, structured logging

---

### Health Check Service
**File**: `health_check_service.py`

Comprehensive health monitoring service for all system components and external dependencies.

**Key Responsibilities**:
- Monitors health of all services and external dependencies
- Provides detailed health status reporting
- Supports readiness and liveness check patterns
- Generates comprehensive system health assessments

**Health Check Categories**:
- **Key Vault**: Credential access and authentication
- **OAuth Services**: Databricks and other OAuth connections
- **Connection Pools**: Pool health and capacity
- **Database Connectivity**: Query execution and response times
- **External APIs**: Salesforce, Graph API, Azure AI availability

**Key Features**:
- Multi-level health reporting (simple, detailed, comprehensive)
- Performance metrics integration
- Configurable health check intervals
- Failure pattern detection and alerting

**Dependencies**: All external service clients, connection pools, performance monitoring

---

## Utility Services

### Template Renderer
**File**: `template_renderer.py`

Provides template rendering capabilities for dynamic prompt generation with variable substitution.

**Key Responsibilities**:
- Renders prompt templates with variable substitution
- Validates template variables against schemas
- Provides type coercion and formatting
- Manages template compilation and caching

**Key Features**:
- Safe variable substitution using Python's `string.Template`
- Variable validation with type checking
- Template compilation caching for performance
- Missing variable detection and reporting
- Post-processing and cleanup of rendered content

**Variable Processing**:
- Type-specific formatting (string, integer, float, boolean, list)
- Email address normalization
- Subject and body content formatting
- Domain-specific value processing

**Dependencies**: Template configuration models, prompt validation exceptions

---

### Email Forwarding Manager
**File**: `email_forwarding_manager.py`

Manages email forwarding operations with template-based content generation.

**Key Responsibilities**:
- Generates forwarding email content using external templates
- Creates forwarding scripts for email agent execution
- Manages scenario-specific forwarding configurations
- Provides template-based email composition

**Key Features**:
- External template integration for email content
- Scenario-specific forwarding templates
- Dynamic script generation for email agent
- Fallback mechanisms for template failures
- Integration with email agent subprocess execution

**Supported Scenarios**:
- Negative response forwarding
- Service inquiry forwarding
- "No longer works" notifications
- Custom forwarding with reason overrides

**Dependencies**: Template management system, email agent integration

---

## Logging Services

The `services/logging/` folder contains specialized logging mixins that provide structured logging capabilities for different service types.

### Service Logger Mixin
**File**: `services/logging/service_logger_mixin.py`

Base logging mixin for general service operations.

**Key Features**:
- Structured logging with consistent format
- Service-specific log formatting
- Performance metric integration
- Error context preservation

---

### API Client Logger Mixin
**File**: `services/logging/api_client_logger.py`

Specialized logging for external API interactions.

**Key Features**:
- Request/response logging with sanitization
- API performance metrics
- Error rate tracking
- Credential information redaction

---

### Business Logic Logger Mixin
**File**: `services/logging/business_logic_logger.py`

Logging mixin for business logic operations.

**Key Features**:
- Business process tracking
- Decision point logging
- Workflow state management
- Customer interaction logging

---

### Database Logger Mixin
**File**: `services/logging/database_logger.py`

Database operation logging with query performance tracking.

**Key Features**:
- Query execution logging
- Performance metric tracking
- Connection pool monitoring
- Database error categorization

---

## Service Dependencies and Integration Patterns

### Connection Management
Many services follow a consistent pattern for connection management:
1. **Pooled Services**: Use `PooledServiceBase` for connection pooling
2. **Context Managers**: Support async context managers for resource cleanup
3. **Error Handling**: Consistent error patterns with proper cleanup

### Authentication Patterns
Services use standardized authentication approaches:
1. **OAuth2**: Databricks and other OAuth-enabled services
2. **Key Vault**: Centralized credential management through Azure Key Vault
3. **Token Management**: Automatic refresh and expiration handling

### Logging Integration
All services integrate with the structured logging system:
1. **Specialized Mixins**: Service-type-specific logging capabilities
2. **Performance Metrics**: Built-in performance tracking
3. **Error Context**: Rich error information with correlation IDs

### Testing and Development
Services support comprehensive testing patterns:
1. **Test Mode**: Email substitution and safe testing modes
2. **Mock Integration**: Support for mock clients and test doubles
3. **Configuration Override**: Environment-specific configuration management

---

## Performance and Scalability Considerations

### Connection Pooling
- Databricks connections are pooled for optimal performance
- Configurable pool sizes based on workload requirements
- Health checks ensure connection quality

### Caching Strategies
- Template compilation caching in Template Renderer
- Credential caching in Key Vault Client
- Query result caching where appropriate

### Asynchronous Operations
- All I/O operations are asynchronous
- Proper timeout handling for external service calls
- Concurrent operation support with proper resource management

### Resource Management
- Automatic cleanup through context managers
- Connection release and resource deallocation
- Memory-efficient processing for large datasets

This comprehensive service architecture enables robust, scalable, and maintainable email processing workflows with proper separation of concerns and excellent observability.