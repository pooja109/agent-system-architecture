# Email Agent Troubleshooting Guide

Common issues and solutions for Email Agent email campaign processing.

## Quick Diagnostic Commands

Run these commands first for fast issue identification:

```bash
# Check complete system status
python main.py status

# Test email delivery
python main.py test your-email@yourcompany.com

# Enable debug logging for detailed information
python main.py --log-level DEBUG process

# Show processing statistics
python main.py stats 7  # Last 7 days
```

## Common Issues by Symptom

### Email Not Processing

**Symptoms**: No emails being sent despite pending records in database

**Troubleshooting Steps**:
1. Check system status:
   ```bash
   python main.py status
   ```
2. Verify database connection and pending records
3. Check Azure Communication Services configuration
4. Review application logs for errors

**Common Causes**:
- Invalid ACS connection string or sender email
- Database connectivity issues
- Blob storage authentication problems
- Processing service not running

**Solutions**:
```bash
# Verify Key Vault secrets exist
curl "https://your-keyvault.vault.azure.net/secrets/azure-communication-connection-string?api-version=7.4"

# Check if SQL warehouse is running
python -c "
import os
from databricks.sql import connect
conn = connect(
    server_hostname=os.getenv('DATABRICKS_SERVER_HOSTNAME'),
    http_path=os.getenv('DATABRICKS_HTTP_PATH'),
    access_token=os.getenv('DATABRICKS_ACCESS_TOKEN')
)
print('Database connection successful')
"

# Test processing with single run
python main.py process
```

### Blob Storage Access Errors

**Symptoms**: File not found errors or access denied messages

**Troubleshooting Steps**:
1. Verify blob storage configuration:
   ```bash
   python main.py status
   ```
2. Check container name and file paths
3. Validate SAS token expiration if using SAS authentication
4. Ensure proper permissions on storage account

**Common Causes**:
- Expired SAS tokens
- Incorrect container or file paths
- Insufficient storage account permissions
- Network connectivity issues

**Solutions**:
```bash
# Test blob container access
python -c "
from azure.storage.blob import BlobServiceClient
import os

# Using connection string
if os.getenv('AZURE_STORAGE_CONNECTION_STRING'):
    client = BlobServiceClient.from_connection_string(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))
# Using SAS token
else:
    account_url = f'https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net'
    client = BlobServiceClient(account_url=account_url, credential=os.getenv('AZURE_STORAGE_SAS_TOKEN'))

container = client.get_container_client(os.getenv('BLOB_CONTAINER_NAME'))
print('Container access successful')
for blob in container.list_blobs(max_results=5):
    print(f'Found blob: {blob.name}')
"

# Regenerate SAS token if expired
# Go to Azure Portal → Storage Account → Shared Access Signature
# Set permissions: Read, List (minimum required)
# Set new expiration date and generate
```

### Email Delivery Failures

**Symptoms**: Emails marked as failed in database

**Troubleshooting Steps**:
1. Check Azure Communication Services status
2. Verify recipient email addresses
3. Review error messages in database
4. Test with known valid email address

**Common Causes**:
- Invalid recipient email addresses
- Domain-specific delivery restrictions
- Azure service rate limiting
- SMTP authentication issues

**Solutions**:
```bash
# Test with a known good email
python main.py test your-verified-email@yourcompany.com

# Check ACS service status in Azure Portal
# Review delivery reports in ACS dashboard

# Query failed emails from database
python -c "
import os
from databricks.sql import connect
conn = connect(
    server_hostname=os.getenv('DATABRICKS_SERVER_HOSTNAME'),
    http_path=os.getenv('DATABRICKS_HTTP_PATH'),
    access_token=os.getenv('DATABRICKS_ACCESS_TOKEN')
)
cursor = conn.cursor()
cursor.execute('''
    SELECT email_recipient, failure_reason, created_at 
    FROM email_communication_pipeline 
    WHERE email_sent = false 
    ORDER BY created_at DESC 
    LIMIT 10
''')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} at {row[2]}')
"
```

### Database Connection Problems

**Symptoms**: Cannot connect to Databricks or query failures

**Troubleshooting Steps**:
1. Test Databricks connection:
   ```bash
   python main.py status
   ```
2. Verify access token validity
3. Check SQL warehouse status
4. Review network connectivity

**Common Causes**:
- Expired Databricks access token
- SQL warehouse not running
- Network firewall restrictions
- Invalid connection parameters

**Solutions**:
```bash
# Check if access token is valid
curl -H "Authorization: Bearer $DATABRICKS_ACCESS_TOKEN" \
     https://$DATABRICKS_SERVER_HOSTNAME/api/2.0/clusters/list

# Verify SQL warehouse status
curl -H "Authorization: Bearer $DATABRICKS_ACCESS_TOKEN" \
     https://$DATABRICKS_SERVER_HOSTNAME/api/2.0/sql/warehouses

# Test connection with OAuth (if configured)
python -c "
from services.databricks_oauth_client import DatabricksOAuthClient
client = DatabricksOAuthClient()
token = client.get_access_token()
print('OAuth authentication successful')
"
```

### Key Vault Authentication Issues

**Symptoms**: "Key Vault authentication failed" or missing secrets errors

**Common Causes**:
- Invalid service principal credentials
- Missing Key Vault access policies
- Incorrect Key Vault URL
- Missing required secrets in Key Vault

**Solutions**:
```bash
# Test service principal authentication
az login --service-principal \
  --username $AZURE_CLIENT_ID \
  --password $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID

# List Key Vault secrets
az keyvault secret list --vault-name your-keyvault-name

# Check required secrets exist
az keyvault secret show --vault-name your-keyvault-name \
  --name azure-communication-connection-string

# Test Key Vault access from Python
python -c "
from azure.keyvault.secrets import SecretClient
from azure.identity import ClientSecretCredential
import os

credential = ClientSecretCredential(
    tenant_id=os.getenv('AZURE_TENANT_ID'),
    client_id=os.getenv('AZURE_CLIENT_ID'),
    client_secret=os.getenv('AZURE_CLIENT_SECRET')
)
client = SecretClient(vault_url=os.getenv('AZURE_KEY_VAULT_URL'), credential=credential)
secret = client.get_secret('azure-communication-connection-string')
print('Key Vault access successful')
"
```

## Error Reference

### Configuration Errors
- **`Key Vault authentication failed`**: Missing or invalid Azure Key Vault configuration
- **`ACS credentials not found in Key Vault`**: Missing required secrets in Key Vault
- **`DATABRICKS_ACCESS_TOKEN is required`**: Missing Databricks authentication
- **`Invalid blob storage configuration`**: Malformed storage settings

### Processing Errors
- **`Failed to load research output`**: Blob storage file retrieval error
- **`Invalid recipient email address`**: Email validation failure
- **`Azure Communication Services error`**: Email delivery service failure

### Database Errors
- **`Failed to connect to Databricks`**: Connection or authentication issue
- **`Table does not exist`**: Database setup not completed
  ```bash
  python main.py setup
  ```
- **`SQL execution failed`**: Query or data integrity issue

### Connection Pool Errors
- **`Connection pool exhausted`**: Too many concurrent operations
- **`OAuth token refresh failed`**: Service principal authentication issue
- **`Connection timeout`**: Network latency or service unavailability

## Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
python main.py --log-level DEBUG process
```

This provides verbose output including:
- API request/response details
- Database query execution
- Blob storage file operations
- Email processing steps
- Timing information
- OAuth token refresh operations
- Connection pool metrics

### Log Analysis Tips

#### Application Logs
- Look for ERROR and WARNING level messages
- Monitor processing times for bottlenecks
- Track success/failure rates over time
- Review OAuth token refresh patterns

#### Structured Log Queries
When using JSON logging format:
```bash
# Filter for errors only
python main.py --log-level DEBUG process 2>&1 | jq 'select(.level == "error")'

# Monitor processing times
python main.py --log-level DEBUG process 2>&1 | jq 'select(.event == "processing_completed")'
```

## Health Monitoring

### Health Check Endpoints
```bash
# Simple health check (200/503)
curl http://localhost:8081/health

# Detailed component health
curl http://localhost:8081/health/detailed

# Kubernetes readiness probe
curl http://localhost:8081/ready

# Service information
curl http://localhost:8081/
```

### Monitoring Key Metrics
- Email processing throughput
- Database connection pool utilization
- Azure service response times
- Failed email ratios

## Performance Troubleshooting

### Slow Processing
- **Check connection pool settings**: Increase `CONNECTION_POOL_MAX_SIZE`
- **Monitor SQL warehouse**: Ensure adequate compute capacity
- **Review batch size**: Adjust `EMAIL_BATCH_SIZE` for optimal performance
- **Network latency**: Test connectivity between services

### High Error Rates
- **Review email addresses**: Validate recipient data quality
- **Check service limits**: Monitor Azure service quotas
- **Examine retry logic**: Verify `EMAIL_MAX_RETRY_ATTEMPTS` setting

## Getting Help

### Support Escalation Process
1. **Check system status first**:
   ```bash
   python main.py status
   ```
2. **Enable debug logging**: Run with `--log-level DEBUG`
3. **Gather error details**: Copy specific error messages and stack traces
4. **Test individual components**: Use test commands to isolate issues
5. **Review configuration**: Verify all environment variables and secrets

### Additional Resources
- **Azure Portal**: Monitor service health and quotas
- **Databricks Console**: Check SQL warehouse performance
- **Azure Key Vault**: Verify secret access and permissions
- **Application logs**: Review structured logging output

## Understanding Inbound Response Patterns

If you're troubleshooting email delivery issues, understanding customer response patterns can help:

- [Inbox Monitor Scenarios](../../inbox_monitor/docs/SCENARIOS.md) - See what types of responses customers send
- [Positive Response Handling](../../inbox_monitor/docs/SCENARIOS.md#scenario-5-positive-response) - How interested customers respond
- [Invalid Email Handling](../../inbox_monitor/docs/SCENARIOS.md#scenario-9-invalid-email) - How bounce messages are processed

This can help you understand whether delivery issues are systemic or related to specific customer response patterns.

## Related Documentation

**Inbox Monitor Integration**:
- [Inbox Monitor Troubleshooting Guide](../../inbox_monitor/docs/TROUBLESHOOTING.md) - Shared Azure service troubleshooting
- [Inbox Monitor Scenarios Guide](../../inbox_monitor/docs/SCENARIOS.md) - Understanding customer response patterns
- Cross-feature debugging context for integrated system troubleshooting

**Complete System Documentation**:
- [Inbox Monitor Main Documentation](../../inbox_monitor/README.md) - Comprehensive inbound email handling reference
- **[Setup Guide](SETUP.md)** - Installation procedures and first-run steps
- **[Configuration Guide](CONFIGURATION.md)** - Environment setup and settings verification
- **[Main README](../README.md)** - Complete system documentation and architecture