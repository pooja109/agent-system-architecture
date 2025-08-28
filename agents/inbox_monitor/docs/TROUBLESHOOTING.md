# Inbox Monitor Troubleshooting Guide

Multi-service integration issues and AI classification debugging for the Inbox Monitor system.

> **📚 Related Documentation:**
> - **Configuration Help:** [Configuration Guide](CONFIGURATION.md) - Service authentication and setup
> - **Setup Issues:** [Setup Guide](SETUP.md) - Installation and basic configuration
> - **Understanding Problems:** [Scenarios Guide](SCENARIOS.md) - How email processing should work
> - **Testing Problems:** [Testing Guide](TESTING.md) - Validate system components
> - **Technical Details:** [Services Overview](SERVICES-OVERVIEW.md) - Architecture and service details
> - **Daily Operations:** [User Guide](USER_GUIDE.md) - Normal system operation
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Quick Diagnostic Commands

**Essential troubleshooting commands for rapid issue diagnosis:**

```bash
# Comprehensive system status check
python main.py status

# Test all service connections
python main.py test

# Health check endpoints
curl http://localhost:8080/health
curl http://localhost:8080/health/detailed | jq '.'

# Debug logging for detailed troubleshooting
python main.py run --log-level DEBUG

# Single email processing test
python main.py check
```

## Service-Specific Issues

### Microsoft Graph API Issues

**Common Problems:**
- Email monitoring connectivity failures
- Permission and authentication errors
- Inbox access and message processing issues

#### Permission Errors
```
Error: Insufficient privileges to complete the operation
```
**Solution Steps:**
1. Verify Graph API permissions include `Mail.Read` and `Mail.ReadWrite`
2. Ensure service principal has been granted admin consent
3. Check tenant-level permissions for Graph API access
4. Validate monitored email configuration: `GRAPH_API_MONITORED_EMAIL`

#### Authentication Failures
```
Error: Graph API credentials not found in Key Vault
```
**Solution Steps:**
1. Verify Azure Key Vault contains required secrets:
   - `graph-api-tenant-id`
   - `graph-api-client-id`
   - `graph-api-client-secret`
2. Check service principal has `Get` and `List` permissions on Key Vault
3. Validate `AZURE_KEY_VAULT_URL` environment variable
4. Test Key Vault connectivity: `az keyvault secret show --name graph-api-tenant-id --vault-name your-vault`

#### Email Monitoring Connectivity
```
Error: Failed to retrieve emails from monitored inbox
```
**Solution Steps:**
1. Verify monitored email exists and is accessible
2. Check network connectivity to Graph API endpoints
3. Validate email format in `GRAPH_API_MONITORED_EMAIL`
4. Test email access with Graph Explorer: `https://developer.microsoft.com/en-us/graph/graph-explorer`

### Azure AI Foundry Classification Issues

**Common Problems:**
- AI service unavailability and timeout errors
- Classification accuracy and confidence score issues
- Model deployment and endpoint connectivity problems

#### AI Service Connection Failures
```
Error: Failed to classify email intent
```
**Solution Steps:**
1. Verify Azure AI Foundry endpoint configuration in Key Vault:
   - `azure-ai-foundry-endpoint`
   - `azure-ai-foundry-tenant-id`
   - `azure-ai-foundry-client-id`
   - `azure-ai-foundry-client-secret`
2. Check AI Foundry service status and model deployment
3. Validate network connectivity to AI Foundry endpoints
4. Test authentication with AI service independently

#### Classification Accuracy Issues
```
Warning: Low confidence score for email classification
```
**Solution Steps:**
1. Review email content for clarity and typical patterns
2. Check AI model deployment status and version
3. Enable debug logging to review classification reasoning:
   ```bash
   export LOGGING_LEVEL=DEBUG
   python main.py check
   ```
4. Consider manual classification for edge cases
5. Update AI prompts if consistent misclassification occurs

#### Model Deployment Problems
```
Error: AI model endpoint not available
```
**Solution Steps:**
1. Verify model deployment status in Azure AI Foundry
2. Check endpoint URL configuration in Key Vault
3. Validate model version and availability
4. Test endpoint connectivity with direct HTTP requests

### Salesforce Integration Issues

**Common Problems:**
- Case creation failures and validation errors
- Contact field update issues, especially boolean fields
- Authentication and API connectivity problems

#### Case Creation Failures
```
Error: Failed to create Salesforce case
```
**Solution Steps:**
1. Verify Salesforce credentials in Azure Key Vault:
   - `sf-base-url`
   - `sf-client-id`
   - `sf-client-secret`
   - `sf-token-endpoint`
   - `sf-api-version`
2. Check required case fields and record type configuration:
   - `sf-case-record-type-id`
   - `sf-case-queue`
3. Validate service principal has case creation permissions
4. Test Salesforce API connectivity:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        "https://yourorg.salesforce.com/services/data/v58.0/sobjects/Case/"
   ```

#### Boolean Field Update Errors (Scenario 9)
```
Error: Is_Email_Invalid__c field update errors
```
**Solution Steps:**
1. Verify `Is_Email_Invalid__c` field exists on Contact object
2. Check field permissions for API user
3. Validate field type is Boolean (Checkbox)
4. Test field update with direct API call:
   ```bash
   # Test contact field update
   curl -X PATCH \
        -H "Authorization: Bearer YOUR_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"Is_Email_Invalid__c":true}' \
        "https://yourorg.salesforce.com/services/data/v58.0/sobjects/Contact/CONTACT_ID"
   ```

#### Salesforce Authentication Issues
```
Error: Salesforce credentials not found in Key Vault
```
**Solution Steps:**
1. Verify all required Salesforce secrets exist in Key Vault
2. Check Connected App configuration in Salesforce:
   - OAuth enabled with appropriate scopes (`api`, `refresh_token`)
   - Service principal or user has proper permissions
3. Test OAuth flow independently
4. Validate token endpoint configuration

### Databricks Connection Issues

**Common Problems:**
- OAuth authentication failures and token refresh issues
- Connection pool exhaustion and timeout errors
- Expert assignment and round-robin algorithm problems

#### OAuth Authentication Failures
```
Error: Failed to establish Databricks connection
```
**Solution Steps:**
1. Verify OAuth service principal credentials in Key Vault:
   - Tenant ID secret: `sales-engagement-service-principal-tenantid`
   - Client ID secret: `sales-engagement-service-principal-clientid`
   - Client secret: `sales-engagement-service-principal-secretid`
2. Check Databricks workspace permissions for service principal
3. Validate OAuth token refresh configuration
4. Test connection with service principal:
   ```bash
   # Test Databricks OAuth connection
   python -c "
   from services.databricks_oauth_client import DatabricksOAuthClient
   client = DatabricksOAuthClient()
   client.test_connection()
   "
   ```

#### Connection Pool Issues
```
Error: Connection pool exhausted
```
**Solution Steps:**
1. Check connection pool configuration:
   ```bash
   CONNECTION_POOL_MIN_SIZE=2
   CONNECTION_POOL_MAX_SIZE=4
   CONNECTION_TIMEOUT_SECONDS=30
   ```
2. Monitor connection usage patterns and adjust pool size
3. Check for connection leaks in application code
4. Validate connection cleanup and disposal

#### Expert Assignment Failures
```
Error: No available experts for assignment
```
**Solution Steps:**
1. Verify `expert_lead_assignments` table exists and has data:
   ```sql
   SELECT * FROM your_catalog.your_schema.expert_lead_assignments;
   ```
2. Check expert availability and status
3. Validate round-robin algorithm logic
4. Review expert assignment count balancing

## Scenario-Specific Troubleshooting

### Positive Response (Scenario 5) Issues

**Expert Assignment Failures:**
- **Problem**: Expert lookup fails or round-robin assignment errors
- **Solution**: Check Databricks connection and expert table data
- **Verification**: `SELECT * FROM expert_lead_assignments WHERE is_active = true`

**Salesforce Case Creation Problems:**
- **Problem**: Case creation fails with validation errors
- **Solution**: Verify case record type ID and required fields
- **Verification**: Test case creation with minimal required fields

**Contact Lookup Issues:**
- **Problem**: Customer not found in Databricks contact database
- **Solution**: Verify contact data synchronization and table access
- **Verification**: Manual contact lookup query

### Email Invalid (Scenario 9) Issues

**Salesforce Boolean Field Update Problems:**
```
Error: Is_Email_Invalid__c field update errors
```
**Solution Steps:**
1. Verify field exists and is properly configured as Boolean
2. Check API user permissions for Contact field updates
3. Test direct field update via Salesforce API
4. Validate contact ID resolution and field access

**Assignment Status Update Failures:**
- **Problem**: Status not updated to "email_invalid"
- **Solution**: Check assignment tracking table and update logic
- **Verification**: Query assignment status after processing

### Service Inquiry (Scenario 7) Issues

**Email Forwarding Failures:**
- **Problem**: Account team email forwarding not working
- **Solution**: Verify `SCENARIO_ACCOUNT_TEAM_EMAIL` configuration
- **Verification**: Test email forwarding service connectivity

**Thread Context Loss:**
- **Problem**: Email context not preserved in forwarding
- **Solution**: Check email forwarding template and thread preservation
- **Verification**: Review forwarded email content for completeness

### Negative Response (Scenario 6) Issues

**Victoria Grant Email Forwarding:**
- **Problem**: Compliance emails not reaching Victoria Grant
- **Solution**: Verify `SCENARIO_VICTORIA_GRANT_EMAIL` configuration
- **Verification**: Test email delivery to Victoria Grant address

**Audit Trail Issues:**
- **Problem**: Unsubscribe requests not properly logged
- **Solution**: Check logging configuration and audit table updates
- **Verification**: Review audit logs for unsubscribe tracking

## AI Classification Debugging

### Understanding Low Confidence Scores

**Diagnostic Steps:**
1. **Enable Debug Logging**: `LOGGING_LEVEL=DEBUG`
2. **Review Classification Reasoning**: Check AI service logs for decision factors
3. **Analyze Email Content**: Look for mixed intents or unclear language
4. **Test with Similar Emails**: Compare classification patterns

**Common Edge Cases:**
- **Mixed Intent Emails**: Customer expresses multiple intents in single email
- **Forwarded Messages**: Email chains confuse classification
- **Non-English Content**: Language variations affect accuracy
- **Corporate Auto-Replies**: System messages appear personal

### Manual Classification Override

**For Testing Specific Scenarios:**
```bash
# Force specific scenario classification
export TEST_FORCE_SCENARIO=5  # Test positive response routing
python main.py check

# Test mode with email override
export TEST_MODE=true
export TEST_SALESFORCE_EMAIL=test-customer@example.com
python main.py check
```

**For Production Overrides:**
1. Use manual review process for uncertain classifications
2. Update AI prompts based on recurring edge cases
3. Implement confidence threshold adjustments

## Multi-Service Integration Debugging

### End-to-End Workflow Troubleshooting

**Complete Workflow Test:**
```bash
# Test full email processing pipeline
export LOGGING_LEVEL=DEBUG
python main.py check

# Check all service health endpoints
curl http://localhost:8080/health/detailed
```

**Service Availability Issues:**
1. **Check Service Dependencies**: All 4 services must be operational
2. **Validate Authentication**: Each service requires valid credentials
3. **Network Connectivity**: Verify outbound connectivity to all endpoints

### Authentication Token Refresh Problems

**OAuth Token Issues:**
- **Problem**: Token refresh failures causing service interruptions
- **Solution**: Check OAuth configuration and refresh logic
- **Verification**: Monitor token expiration and refresh patterns

**Key Vault Access Issues:**
- **Problem**: Intermittent Key Vault authentication failures
- **Solution**: Verify service principal permissions and network connectivity
- **Verification**: Test Key Vault access during peak usage times

## Error Reference

### Configuration Errors

| Error Message | Cause | Solution |
|---------------|--------|----------|
| `Key Vault authentication failed` | Missing/invalid Azure Key Vault config | Check `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` |
| `Graph API credentials not found in Key Vault` | Missing Graph API secrets | Create `graph-api-tenant-id`, `graph-api-client-id`, `graph-api-client-secret` |
| `Azure AI Foundry credentials not found in Key Vault` | Missing AI Foundry secrets | Create required AI Foundry secrets in Key Vault |
| `Salesforce credentials not found in Key Vault` | Missing Salesforce secrets | Create all required Salesforce secrets |
| `target_salesforce_email is required when test mode is enabled` | Incomplete test mode config | Set `TEST_SALESFORCE_EMAIL` for test mode |

### Service Errors

| Error Message | Cause | Solution |
|---------------|--------|----------|
| `Failed to classify email intent` | AI service unavailable/misconfigured | Check AI Foundry endpoint and model deployment |
| `Failed to create Salesforce case` | Salesforce API/permission issues | Verify case creation permissions and required fields |
| `No available experts for assignment` | Empty/inactive expert pool | Check expert_lead_assignments table data |
| `Contact not found in lookup table` | Missing customer data | Verify Databricks contact synchronization |
| `Is_Email_Invalid__c field update errors` | Salesforce field issues | Check Contact object field permissions |
| `SSL shutdown timed out` | Network connectivity issues | Automatic retry - check network stability |

## Debug Mode and Logging

### Enhanced Debug Logging

**Enable Comprehensive Debugging:**
```bash
export LOGGING_LEVEL=DEBUG
export LOGGING_FORMAT=json
python main.py run
```

**Debug Output Includes:**
- API request/response details for all services
- Database query execution and results
- Internal processing steps and timing
- AI classification reasoning and confidence scores
- Service authentication and token management

### Service-Specific Logging

**Graph API Debug Logging:**
- Email retrieval and processing details
- Permission validation and authentication flows
- Message parsing and classification preparation

**Salesforce Debug Logging:**
- Case creation with all field values
- Contact updates and field modifications
- OAuth token refresh and authentication

**Databricks Debug Logging:**
- Connection pool management and usage
- Expert assignment algorithm execution
- Query performance and result validation

**AI Classification Debug Logging:**
- Intent classification reasoning and confidence scores
- Prompt processing and response analysis
- Edge case handling and fallback logic

## Production Monitoring

### Health Check Integration

**Kubernetes/Container Health Checks:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Monitoring Alerts:**
- Service availability (health endpoints)
- Email processing success rate
- AI classification confidence scores
- Expert assignment balance
- Database connection pool health

## Understanding Outbound Campaign Context

When troubleshooting email classification issues, understanding the original campaigns can help:

- [Email Agent Campaign Processing](../../email/docs/TROUBLESHOOTING.md) - How outbound campaigns are generated
- [Email Agent Configuration](../../email/docs/CONFIGURATION.md) - Shared Azure service troubleshooting
- [Campaign Content Debugging](../../email/README.md#troubleshooting) - Understanding what customers are responding to

This context can help debug classification accuracy and understand response patterns.

## Related Documentation

**Email Agent Integration**:
- [Email Agent Troubleshooting Guide](../../email/docs/TROUBLESHOOTING.md) - Shared Azure service debugging
- [Email Agent Configuration](../../email/docs/CONFIGURATION.md) - Common OAuth and Key Vault issues
- Cross-feature context for integrated system troubleshooting

**Complete System Documentation**:
- [Email Agent Main Documentation](../../email/README.md) - Comprehensive outbound campaign processing reference
- **[Setup Guide](SETUP.md)** - Initial service setup procedures and validation
- **[Configuration Guide](CONFIGURATION.md)** - Service authentication and environment configuration
- **[Scenarios Guide](SCENARIOS.md)** - Understanding business logic for effective debugging
- **[Main README](README.md)** - Complete system documentation and architecture