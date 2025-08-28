# Inbox Monitor Configuration Guide

Complete configuration reference for Inbox Monitor multi-service authentication and setup.

> **📚 Related Documentation:**
> - **Prerequisites:** [Setup Guide](SETUP.md) - Initial installation and dependencies
> - **Understanding the System:** [Scenarios Guide](SCENARIOS.md) - AI email classification and business actions
> - **Validation:** [Testing Guide](TESTING.md) - Test your configuration
> - **Operations:** [User Guide](USER_GUIDE.md) - Daily usage and workflows
> - **Need Help?** [Troubleshooting Guide](TROUBLESHOOTING.md) - Common configuration issues
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Overview

The Inbox Monitor integrates with 4 core services using OAuth service principal authentication and Azure Key Vault for secure credential management. This system has been migrated from Personal Access Token (PAT) authentication to OAuth for enhanced security and production readiness.

**Key Features:**
- OAuth service principal authentication across all services
- Azure Key Vault centralized secret management
- Connection pooling for 80-90% reduction in connection overhead
- Comprehensive health monitoring and alerting
- Automatic token management and refresh

## Required Service Configuration

### Microsoft Graph API

**Purpose**: Email monitoring and message processing from Microsoft 365

**Required Configuration:**
```bash
# Environment variable (required)
GRAPH_API_MONITORED_EMAIL=inbox@yourcompany.com
```

**Required Azure Key Vault Secrets:**
```bash
# Key Vault secret names (these must be created in your Azure Key Vault)
graph-api-tenant-id          # Your Azure tenant ID
graph-api-client-id          # Service principal client ID
graph-api-client-secret      # Service principal client secret
```

**Required Permissions:**
- `Mail.Read` - Read email from monitored inbox
- `Mail.ReadWrite` - Process and manage email messages
- `User.Read` - Basic user profile access

**Setup Steps:**
1. Register application in Azure AD
2. Grant required Graph API permissions
3. Create client secret
4. Store credentials in Azure Key Vault with exact secret names above

### Azure AI Foundry

**Purpose**: Intent classification using advanced AI models for email routing

**Required Azure Key Vault Secrets:**
```bash
# Key Vault secret names
azure-ai-foundry-endpoint       # AI Foundry service endpoint URL
azure-ai-foundry-tenant-id     # Azure tenant ID for AI service
azure-ai-foundry-client-id     # Service principal client ID
azure-ai-foundry-client-secret # Service principal client secret
```

**Configuration Requirements:**
- Azure AI Foundry project deployed
- Model deployment for intent classification
- Service principal with access to AI resources
- Semantic Kernel integration configured

**Model Configuration:**
- Intent classification model deployed
- 6 email scenario classification capabilities
- Confidence scoring enabled

### Salesforce Integration

**Purpose**: CRM operations including case creation and contact field updates

**Required Azure Key Vault Secrets:**
```bash
# Key Vault secret names
sf-base-url                  # Salesforce instance URL (e.g., https://yourorg.salesforce.com)
sf-client-id                 # Connected App Consumer Key
sf-client-secret             # Connected App Consumer Secret
sf-token-endpoint           # OAuth token endpoint
sf-api-version              # API version (e.g., v58.0)
sf-case-record-type-id      # Record Type ID for created cases
sf-case-queue               # Queue ID for case assignment
```

**Required Salesforce Setup:**
1. Create Connected App with OAuth enabled
2. Configure OAuth scopes: `api`, `refresh_token`
3. Set up required custom fields:
   - `Is_Email_Invalid__c` (Boolean) on Contact object
4. Configure case record types and queues
5. Grant API permissions to service principal

**Field Requirements:**
- Contact object must have `Is_Email_Invalid__c` boolean field
- Case object access for creation and updates
- Queue management permissions

### Databricks Integration

**Purpose**: Expert assignment tracking and round-robin algorithm management

**Environment Variables:**
```bash
DATABRICKS_SERVER_HOSTNAME=your-databricks-server.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_CATALOG=your-catalog
DATABRICKS_SCHEMA=your-schema
```

**OAuth Configuration (stored in Azure Key Vault):**
```bash
# Service Principal Credentials for OAuth
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-service-principal-client-id
AZURE_CLIENT_SECRET=your-service-principal-secret

# Key Vault Secret Names for OAuth (default values)
KEY_VAULT_TENANT_ID_SECRET=sales-engagement-service-principal-tenantid
KEY_VAULT_CLIENT_ID_SECRET=sales-engagement-service-principal-clientid
KEY_VAULT_CLIENT_SECRET_SECRET=sales-engagement-service-principal-secretid
```

**Database Objects Required:**
- `expert_lead_assignments` table for round-robin management
- Contact lookup tables for customer information
- Proper permissions for OAuth service principal

## Environment Variables Reference

### Required Core Settings

```bash
# Azure Key Vault (required for all service authentication)
AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/

# Microsoft Graph API
GRAPH_API_MONITORED_EMAIL=inbox@yourcompany.com

# Databricks
DATABRICKS_SERVER_HOSTNAME=your-databricks-server.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_CATALOG=your-catalog
DATABRICKS_SCHEMA=your-schema

# Scenario Configuration
SCENARIO_VICTORIA_GRANT_EMAIL=victoria.grant@yourcompany.com
SCENARIO_ACCOUNT_TEAM_EMAIL=support@yourcompany.com
```

### Optional Test Mode Settings

```bash
# Test Mode (for safe testing without affecting production data)
TEST_MODE=true                                    # Enable test mode
TEST_EMAIL_SENDER=your-test-email@yourcompany.com # Override sender for testing
TEST_SALESFORCE_EMAIL=real-customer@clientcompany.com # Test customer email
TEST_FORCE_SCENARIO=9                             # Force specific scenario for testing
```

### Optional Advanced Settings

```bash
# Processing Configuration
INBOX_MONITOR_POLLING_INTERVAL=300  # Email check interval in seconds (default: 300)
INBOX_MONITOR_BATCH_SIZE=10         # Max emails processed per batch (default: 10)
INBOX_MONITOR_MAX_RETRY_ATTEMPTS=3  # Retry attempts for failed operations (default: 3)

# Connection Pool Configuration
CONNECTION_POOL_MIN_SIZE=2          # Minimum connections (default: 2)
CONNECTION_POOL_MAX_SIZE=4          # Maximum connections (default: 4)
CONNECTION_TIMEOUT_SECONDS=30       # Connection timeout (default: 30)

# Logging
LOGGING_LEVEL=INFO                  # Log level: DEBUG, INFO, WARNING, ERROR
LOGGING_FORMAT=json                 # Log format: json or text

# Environment
ENVIRONMENT=production              # Environment identifier
INBOX_MONITOR_DRY_RUN=false        # Dry run mode (no actual service calls)

# Health Monitoring
HEALTH_CHECK_PORT=8080              # Health check server port (default: 8080)
HEALTH_CHECK_ENABLED=true           # Enable health endpoints (default: true)
METRICS_COLLECTION_INTERVAL=60      # Metrics collection interval (default: 60s)
```

## OAuth and Security Configuration

### Azure Key Vault Setup

**Required Permissions for Service Principal:**
- `Key Vault Secrets User` role or equivalent
- `Get` and `List` permissions on secrets
- Access to all required secret names listed above

**Authentication Flow:**
1. Application authenticates to Azure AD using service principal
2. Retrieves service-specific credentials from Key Vault
3. Uses retrieved credentials for OAuth flows with each service
4. Maintains token cache and automatic refresh

### Service Principal Requirements

**For Azure Key Vault Access:**
```bash
# Primary service principal for Key Vault access
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-service-principal-client-id
AZURE_CLIENT_SECRET=your-service-principal-secret
```

**For Databricks OAuth:**
- Same service principal or separate OAuth-enabled principal
- Databricks workspace access
- SQL warehouse permissions

## Health Monitoring Configuration

### Health Check Endpoints

The system provides comprehensive health monitoring:

```bash
# Health check endpoints
GET /health           # Simple health check (200/503)
GET /health/detailed  # Comprehensive system health with component details
GET /ready           # Kubernetes readiness probe
GET /                # Service information and available endpoints
```

**Example Usage:**
```bash
# Check service health
curl http://localhost:8080/health

# Get detailed health information with JSON formatting
curl http://localhost:8080/health/detailed | jq '.'

# Check readiness for traffic
curl http://localhost:8080/ready
```

### Health Monitoring Configuration

```bash
HEALTH_CHECK_PORT=8080              # Port for health endpoints
HEALTH_CHECK_ENABLED=true           # Enable/disable health monitoring
METRICS_COLLECTION_INTERVAL=60      # How often to collect metrics (seconds)
```

## Configuration Validation

### Startup Validation

The system validates all configurations on startup and will prevent launch with clear error messages for:

- Missing required environment variables
- Invalid Azure Key Vault configuration
- Missing or inaccessible Key Vault secrets
- Invalid service credentials
- Network connectivity issues

### Service-by-Service Validation

**Validate Graph API Configuration:**
```bash
# Test Graph API connection
python -c "
from services.graph_api_client import GraphAPIClient
import asyncio
async def test():
    client = GraphAPIClient()
    await client.test_connection()
asyncio.run(test())
"
```

**Validate Salesforce Configuration:**
```bash
# Test Salesforce connection
python -c "
from services.salesforce_client import SalesforceClient
client = SalesforceClient()
client.test_connection()
"
```

**Validate Databricks OAuth Configuration:**
```bash
# Test Databricks connection with OAuth
python -c "
from services.databricks_oauth_client import DatabricksOAuthClient
client = DatabricksOAuthClient()
client.test_connection()
"
```

### Integration Testing

Run comprehensive configuration validation:

```bash
# Test all service integrations
python main.py test

# Validate complete system status
python main.py status
```

## Troubleshooting Configuration Issues

### Common Configuration Problems

**Key Vault Authentication Failures:**
```bash
# Verify Key Vault URL and service principal credentials
# Check AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
# Ensure service principal has proper Key Vault permissions
```

**Missing Secrets in Key Vault:**
```bash
# Verify all required secrets exist with exact names:
# graph-api-tenant-id, graph-api-client-id, graph-api-client-secret
# azure-ai-foundry-endpoint, azure-ai-foundry-tenant-id, etc.
# sf-base-url, sf-client-id, sf-client-secret, etc.
```

**Service Connection Failures:**
```bash
# Check network connectivity to all service endpoints
# Verify service principal permissions for each service
# Test OAuth flows independently for each service
```

## Related Documentation

**Email Agent Integration**:
- [Email Agent Configuration Guide](../../email/docs/CONFIGURATION.md) - Shared Azure service setup patterns
- [Email Agent Setup](../../email/docs/SETUP.md) - Understanding outbound campaign configuration
- Both features use Azure Key Vault, OAuth, and Databricks with similar configuration patterns

**Complete System Documentation**:
- [Email Agent Main Documentation](../../email/README.md) - Comprehensive outbound campaign processing reference
- **[Setup Guide](SETUP.md)** - Initial installation and service setup procedures
- **[Scenarios Guide](SCENARIOS.md)** - Understanding what the configured services do
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Service configuration and integration issues
- **[Main README](README.md)** - Complete system documentation