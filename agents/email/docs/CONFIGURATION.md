# Email Agent Configuration Guide

Complete configuration reference for Email Agent environment setup.

## Overview

The Email Agent uses OAuth service principal authentication for enhanced security, with credentials managed through Azure Key Vault. The system supports both connection string and SAS token authentication for blob storage, with comprehensive configuration validation on startup.

## Required Configuration

### Core Services

#### Azure Communication Services
Email delivery credentials are retrieved from Azure Key Vault. Required Key Vault secrets:
- `azure-communication-connection-string`
- `azure-communication-sender-email`

#### Azure Blob Storage Configuration Options

**Option 1: Connection String**
```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
```
- Full account access with permanent credentials
- Suitable for development environments
- Simple setup and configuration

**Option 2: SAS Token (Recommended for Production)**
```bash
AZURE_STORAGE_ACCOUNT_NAME=yourstorageaccount
AZURE_STORAGE_SAS_TOKEN=?sv=2022-11-02&ss=b&srt=sco&sp=rwdlacupiytfx&se=2024-12-31T23:59:59Z...
```
- Time-limited access with configurable expiration
- Scoped permissions (can limit to specific containers/operations)
- Enhanced security with easy rotation and revocation

To generate a SAS token:
1. Go to Azure Portal → Storage Account → Shared Access Signature
2. Set permissions: Read, List (minimum required)
3. Set appropriate expiration date
4. Generate token and use in `AZURE_STORAGE_SAS_TOKEN`

#### Databricks Connection
```bash
DATABRICKS_SERVER_HOSTNAME=your-workspace.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_ACCESS_TOKEN=your-token
DATABRICKS_CATALOG=your_catalog
DATABRICKS_SCHEMA=your_schema
```

### Environment Variables

#### Required Core Settings
```bash
# Azure Blob Storage
BLOB_CONTAINER_NAME=lowtouch

# Azure Key Vault for ACS credentials
AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-service-principal-client-id
AZURE_CLIENT_SECRET=your-service-principal-secret
```

#### Optional Processing Settings
```bash
# Processing Configuration
EMAIL_PROCESSING_INTERVAL_MINUTES=5  # Processing interval (default: 5)
EMAIL_BATCH_SIZE=10                  # Emails per batch (default: 10)
EMAIL_MAX_RETRY_ATTEMPTS=3           # Retry attempts (default: 3)

# Logging
LOGGING_LEVEL=INFO                   # INFO, DEBUG, WARNING, ERROR
LOGGING_FORMAT=json                  # json, text

# Environment
ENVIRONMENT=production               # production, development, testing
```

## OAuth Configuration

### Service Principal Setup
The system uses OAuth service principal authentication for Databricks connectivity. Store these credentials in Azure Key Vault:

```bash
# Key Vault Secret Names (default values)
KEY_VAULT_TENANT_ID_SECRET=sales-engagement-service-principal-tenantid
KEY_VAULT_CLIENT_ID_SECRET=sales-engagement-service-principal-clientid
KEY_VAULT_CLIENT_SECRET_SECRET=sales-engagement-service-principal-secretid
```

### Connection Pool Configuration
```bash
CONNECTION_POOL_MIN_SIZE=2          # Minimum connections (default: 2)
CONNECTION_POOL_MAX_SIZE=4          # Maximum connections (default: 4)
CONNECTION_TIMEOUT_SECONDS=30       # Connection timeout (default: 30)
```

Benefits of connection pooling:
- **80-90% reduction** in connection overhead
- Automatic token management and refresh
- Enhanced reliability and performance
- Production-ready monitoring

## Test Mode Configuration

Test Mode enables safe testing without affecting real customers:

```bash
# Test Mode Settings
TEST_MODE=true                      # Enable test mode (default: false)
TEST_EMAIL_OVERRIDE=your-test-email@yourcompany.com
```

### How Test Mode Works
1. **Email Redirection**: All emails redirect to designated test address
2. **Content Preservation**: Original content and formatting preserved
3. **Safe Testing**: Complete pipeline testing without customer impact
4. **Real Integration**: Tests actual Azure services and Databricks

### Test Mode Benefits
- ✅ **Customer Safety**: No risk of sending emails to real customers
- ✅ **Real Testing**: Tests actual service integrations and data processing
- ✅ **Complete Pipeline**: Validates end-to-end workflow
- ✅ **Production Data**: Works with real customer content and research data

## Health Monitoring

### Health Check Configuration
```bash
HEALTH_CHECK_PORT=8081              # Health check server port (default: 8081)
HEALTH_CHECK_ENABLED=true           # Enable health endpoints (default: true)
METRICS_COLLECTION_INTERVAL=60      # Metrics collection interval (default: 60s)
```

### Available Endpoints
- **`GET /health`**: Simple health check for load balancers (returns 200/503)
- **`GET /health/detailed`**: Comprehensive system health with component details
- **`GET /ready`**: Kubernetes readiness probe endpoint
- **`GET /`**: Service information and available endpoints

### Health Check Usage
```bash
# Check service health
curl http://localhost:8081/health

# Get detailed health information
curl http://localhost:8081/health/detailed | jq '.'

# Check readiness for traffic
curl http://localhost:8081/ready
```

## Production Configuration

### Deployment Settings
```bash
# Production Environment
ENVIRONMENT=production
LOGGING_LEVEL=INFO
LOGGING_FORMAT=json

# Performance Tuning
EMAIL_PROCESSING_INTERVAL_MINUTES=5
EMAIL_BATCH_SIZE=10
CONNECTION_POOL_MAX_SIZE=4
```

### Systemd Service Configuration
Create `/etc/systemd/system/email-agent.service`:

```ini
[Unit]
Description=Email Agent Service
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/path/to/agents/email
ExecStart=/usr/bin/python main.py run
Restart=always
RestartSec=10
Environment=PYTHONPATH=/path/to/agents/email

[Install]
WantedBy=multi-user.target
```

Start the service:
```bash
sudo systemctl enable email-agent
sudo systemctl start email-agent
sudo systemctl status email-agent
```

## Configuration Validation

The system validates all required configurations on startup. Missing or invalid settings will prevent the application from starting with clear error messages.

### Validation Commands
```bash
# Verify complete configuration
python main.py status

# Test connections
python main.py test user@example.com

# Setup database tables if needed
python main.py setup
```

### Common Configuration Issues
- **Missing Key Vault secrets**: Ensure all required secrets exist
- **Invalid SAS token**: Check expiration date and permissions
- **SQL warehouse not running**: Verify Databricks SQL warehouse status
- **Network connectivity**: Ensure all services can communicate

## Related Documentation

**Inbox Monitor Integration**:
- [Inbox Monitor Configuration Guide](../../inbox_monitor/docs/CONFIGURATION.md) - Shared Azure service setup patterns
- [Inbox Monitor Setup](../../inbox_monitor/docs/SETUP.md) - Understanding the inbound campaigns that generate responses
- When Email Agent sends campaigns, responses are processed by Inbox Monitor using similar Azure Key Vault and OAuth patterns

**Complete System Documentation**:
- [Inbox Monitor Main Documentation](../../inbox_monitor/README.md) - Comprehensive inbound email handling reference
- **[Setup Guide](SETUP.md)** - Initial installation procedures
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Configuration issues and solutions
- **[Main README](../README.md)** - Complete system documentation