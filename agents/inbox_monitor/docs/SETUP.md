# Inbox Monitor Setup Guide

Quick guide to get the Inbox Monitor AI email classification system running locally.

> **📚 Related Documentation:**
> - **Next Steps:** [Configuration Guide](CONFIGURATION.md) - Detailed authentication and environment setup
> - **Understanding the System:** [Scenarios Guide](SCENARIOS.md) - AI email classification and business actions
> - **Testing:** [Testing Guide](TESTING.md) - Validate your installation
> - **Need Help?** [Troubleshooting Guide](TROUBLESHOOTING.md) - Common setup issues
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Prerequisites

- Python 3.9 or higher
- Azure subscription with AI Foundry access
- Microsoft 365 tenant with Graph API permissions
- Salesforce org with API access
- Databricks workspace
- Azure Key Vault for secure credential storage

### Graph API Permissions Checklist

Required Microsoft Graph API permissions:
- `Mail.Read` - Read email from monitored inbox
- `Mail.ReadWrite` - Process and manage email messages
- `User.Read` - Basic user profile access

### Azure AI Foundry Project Access

- Azure AI Foundry endpoint configured
- Model deployment for intent classification
- Service principal with access to AI resources

### Salesforce Connected App Setup

Required Salesforce configuration:
- Connected App with OAuth enabled
- API access permissions
- Case creation and contact update permissions
- Required custom fields configured

## Quick Start

### 1. Install Dependencies

```bash
cd agents/inbox_monitor
pip install -r requirements.txt
```

### Required Python Packages

```
semantic-kernel[azure]>=1.33.0
azure-identity>=1.23.0
aiohttp>=3.8.0
pydantic>=2.11.0
structlog>=24.1.0
databricks-sql-connector>=3.0.0
httpx>=0.24.0
```

### 2. Database Initialization

Initialize the Databricks tables for expert assignments:

```bash
python main.py setup
```

This creates:
- `expert_lead_assignments` table for round-robin management
- Required views and permissions
- Connection validation

### 3. Service Authentication Verification

Verify all service connections are working:

```bash
python main.py status
```

**Expected Output**:
```
📊 Inbox Monitor Status
==================================================
✅ Configuration: Valid
🔗 Testing connections...
✅ All connections healthy
```

### 4. First Test Run

Start with email monitoring in test mode:

```bash
# Set test mode environment variables
export TEST_MODE=true
export TEST_EMAIL_SENDER=your-test-email@yourcompany.com

# Run single check
python main.py check
```

### 5. AI Classification Verification

Test AI classification with sample scenarios:

```bash
# Force specific scenario for testing
export TEST_FORCE_SCENARIO=5  # Test positive response classification

python main.py check
```

## Service Setup Overview

The Inbox Monitor requires integration with 4 core services:

1. **Microsoft Graph API**: Email monitoring and message processing
2. **Azure AI Foundry**: Intent classification using advanced AI models
3. **Salesforce**: CRM operations for case creation and contact management
4. **Databricks**: Expert assignment tracking and round-robin algorithm

All service credentials are securely stored in Azure Key Vault. See [Configuration Guide](CONFIGURATION.md) for detailed authentication setup.

## Common Setup Issues

### Graph API Permission Errors
```
Error: Insufficient privileges to complete the operation
```
**Solution**: Verify Graph API permissions include `Mail.Read` and `Mail.ReadWrite`

### Azure Key Vault Access Denied
```
Error: Key Vault authentication failed
```
**Solution**: Ensure service principal has `Get` and `List` permissions on Key Vault secrets

### Databricks Connection Failed
```
Error: Failed to establish Databricks connection
```
**Solution**: Verify OAuth service principal credentials and workspace access

### AI Classification Service Unavailable
```
Error: Failed to classify email intent
```
**Solution**: Check Azure AI Foundry endpoint configuration and model deployment status

## Related Documentation

**Email Agent Integration**:
- [Email Agent Setup Guide](../../email/docs/SETUP.md) - Understanding the outbound campaigns that generate responses
- [Email Agent Configuration](../../email/docs/CONFIGURATION.md) - Shared Azure service setup patterns
- When Inbox Monitor creates Salesforce cases (Scenario 5), they may trigger new Email Agent campaigns

**Complete System Documentation**:
- [Email Agent Main Documentation](../../email/README.md) - Comprehensive outbound campaign processing reference
- **[Configuration Guide](CONFIGURATION.md)** - Multi-service authentication setup
- **[Scenarios Guide](SCENARIOS.md)** - Understanding AI classification and business actions
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Multi-service integration issues

## Next Steps

After completing setup, continue with these guides:

**Essential Configuration:**
- **[Configuration Guide](CONFIGURATION.md)** - Complete multi-service authentication setup
- **[Testing Guide](TESTING.md)** - Validate your installation works correctly

**Understanding the System:**
- **[Scenarios Guide](SCENARIOS.md)** - Learn AI email classification and business actions
- **[User Guide](USER_GUIDE.md)** - Complete operational workflows and daily usage

**Advanced Topics:**
- **[Services Overview](SERVICES-OVERVIEW.md)** - Technical architecture and services
- **[Utilities Reference](UTILS.md)** - Developer tools and utility scripts
- **[UI Components Overview](UI_COMPONENTS_OVERVIEW.md)** - User interface system

**Support:**
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Documentation Hub](README.md)** - All available guides

## Validation Commands

### Test All Components
```bash
# Test all service connections
python main.py test

# Run comprehensive status check
python main.py status

# Test single email processing
python main.py check
```

### Health Check Verification
```bash
# Check service health endpoints
curl http://localhost:8080/health

# Get detailed system health
curl http://localhost:8080/health/detailed | jq '.'
```

## Development Setup

For development and debugging:

```bash
# Enable debug logging
export LOGGING_LEVEL=DEBUG

# Enable dry run mode (no actual service calls)
export INBOX_MONITOR_DRY_RUN=true

# Run with detailed logging
python main.py run --log-level DEBUG
```