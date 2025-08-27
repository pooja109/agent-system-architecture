# Email Agent Setup Guide

Quick guide to get the Email Agent email campaign processor running locally.

## Prerequisites

Before starting, ensure you have:

- **Python 3.8 or higher** - Check with `python --version`
- **Azure subscription** with Communication Services resource
- **Azure Storage Account** with blob container
- **Databricks workspace** with SQL warehouse
- **Network connectivity** between all services

## Quick Start

### 1. Install Dependencies

```bash
cd agents/email
pip install -r requirements.txt
```

**Required packages will be installed:**
```text
azure-communication-email>=1.0.0
azure-storage-blob>=12.14.0
azure-identity>=1.12.0
databricks-sql-connector>=3.0.0
pydantic>=2.0.0
structlog>=23.1.0
aiohttp>=3.8.0
```

### 2. Environment Configuration

Create a `.env` file in the `agents/email/` directory:

```bash
# Minimal required configuration for first run
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
BLOB_CONTAINER_NAME=lowtouch

DATABRICKS_SERVER_HOSTNAME=your-workspace.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_ACCESS_TOKEN=your-token
DATABRICKS_CATALOG=your_catalog
DATABRICKS_SCHEMA=your_schema

# Azure Key Vault for ACS credentials
AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-service-principal-client-id
AZURE_CLIENT_SECRET=your-service-principal-secret

# Test mode (recommended for first run)
TEST_MODE=true
TEST_EMAIL_OVERRIDE=your-test-email@yourcompany.com
```

### 3. Database Initialization

Initialize the required Databricks tables:

```bash
python main.py setup
```

This creates:
- `email_communication_pipeline` table for workflow tracking
- Required views for pending emails and statistics
- Proper indexes and permissions

### 4. First Test Run

Verify the system configuration:

```bash
python main.py status
```

Run a single processing cycle:

```bash
python main.py process --single-run
```

### 5. Verification

Check that the system is working correctly:

1. **Database Connection**: Status command should show "Connected"
2. **Blob Storage**: Status should show container access
3. **Azure Communication Services**: No authentication errors
4. **Processing**: Single run should complete without errors

## Common Setup Issues

### Python Dependencies
- **Issue**: Package installation failures
- **Solution**: Use virtual environment: `python -m venv venv && source venv/bin/activate`

### Database Connection  
- **Issue**: "Failed to connect to Databricks"
- **Solution**: Verify `DATABRICKS_ACCESS_TOKEN` is valid and SQL warehouse is running

### Azure Storage Access
- **Issue**: "Blob container not found"
- **Solution**: Check `BLOB_CONTAINER_NAME` and storage account permissions

### Key Vault Authentication
- **Issue**: "Key Vault authentication failed"  
- **Solution**: Verify service principal credentials and Key Vault access policies

## Related Documentation

**Inbox Monitor Integration**:
- [Inbox Monitor Setup](../../inbox_monitor/docs/SETUP.md) - Setting up inbound response handling
- [Inbox Monitor Configuration](../../inbox_monitor/docs/CONFIGURATION.md) - Shared Azure service setup patterns
- When Email Agent sends campaigns, responses are processed by Inbox Monitor's AI classification system

**Complete System Documentation**:
- [Inbox Monitor Main Documentation](../../inbox_monitor/README.md) - Comprehensive inbound email handling reference
- **[Configuration Guide](CONFIGURATION.md)** - Complete environment and OAuth setup
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

## Next Steps

- **[Configuration Guide](CONFIGURATION.md)** - Complete environment and OAuth setup
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Main README](../README.md)** - Complete system documentation

## Getting Help

If setup issues persist:
1. Check the **[Troubleshooting Guide](TROUBLESHOOTING.md)** for detailed solutions
2. Review application logs with:
   ```bash
   python main.py --log-level DEBUG status
   ```
3. Verify all prerequisite services are properly configured