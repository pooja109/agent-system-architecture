# Inbox Monitor - Intelligent Email Response System

## Overview

The Inbox Monitor is an advanced AI-powered email processing system that automatically monitors a designated email inbox, classifies incoming customer responses, and takes appropriate actions based on the email content. This system is designed to handle customer outreach responses and route them to the correct teams or update relevant CRM systems.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Features & Capabilities](#features--capabilities)
3. [Scenario Processing](#scenario-processing)
4. [Installation & Setup](#installation--setup)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Test Mode](#test-mode)
8. [Testing Framework](#testing-framework)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Troubleshooting](#troubleshooting)
11. [API References](#api-references)

## System Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Email Inbox   │───▶│  Inbox Monitor  │───▶│ Azure AI Foundry│
│  (Microsoft 365)│    │   Main System   │    │ Intent Classifier│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │   Salesforce    │ │   Databricks    │ │ Email Forwarding│
    │  Case Creation  │ │ Expert Assignment│ │   (Victoria/    │
    │ Contact Updates │ │ Round-Robin Mgmt │ │  Account Team)  │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Technology Stack

- **Python 3.9+**: Core application language
- **Azure AI Foundry**: Intent classification using Semantic Kernel
- **Microsoft Graph API**: Email monitoring and processing
- **Salesforce REST API**: CRM operations and case management
- **Databricks SQL**: Expert assignment and round-robin management
- **Azure Communication Services**: Email sending capabilities
- **Structlog**: Structured logging and monitoring

## Features & Capabilities

### Intelligent Email Classification

The system uses Azure AI Foundry with advanced prompts to classify customer email responses into six distinct intents:

1. **Positive**: Customer shows interest, wants more engagement
2. **Negative**: Customer wants to stop communication
3. **Service Inquiry**: Customer has questions about existing services
4. **Out of Office**: Automated absence notifications
5. **Email Invalid**: Bounce messages, delivery failures
6. **No Longer Works**: Person has left the company

### Automated Response Actions

Based on the classified intent, the system automatically:

- **Creates Salesforce cases** for positive responses
- **Assigns expert representatives** using round-robin logic
- **Forwards emails** to appropriate teams (Victoria Grant, Account Team)
- **Updates contact records** to mark invalid emails
- **Manages assignment status** to prevent future emails to invalid addresses

### Multi-Service Integration

- **Microsoft 365 Graph API**: Real-time email monitoring
- **Salesforce**: Automated case creation and contact management
- **Databricks**: Expert assignment tracking and analytics
- **Azure Communication Services**: Email forwarding and notifications

## Scenario Processing

The system processes emails through specific scenarios (5-11) based on AI classification:

### Scenario 5: Positive Response
**Intent**: Customer shows interest and wants more engagement
**Actions**:
1. Look up customer contact in Databricks
2. Assign expert using round-robin algorithm
3. Create Salesforce case assigned to expert
4. Update expert assignment count

**Example Response**: "I'm very interested in learning more about your solutions. Could you please have someone call me?"

### Scenario 6: Negative Response
**Intent**: Customer wants to stop communication
**Actions**:
1. Forward email to Victoria Grant for review
2. Log customer request to stop contact

**Example Response**: "Please remove me from your contact list immediately."

### Scenario 7: Service Inquiry
**Intent**: Customer has questions about existing services
**Actions**:
1. Forward email to Account Team
2. Ensure customer gets proper support

**Example Response**: "I have a question about my recent order #12345."

### Scenario 8: Out of Office
**Intent**: Automated out-of-office response
**Actions**:
1. Update assignment status to "out_of_office"
2. Temporarily pause email attempts

**Example Response**: "Thank you for your email. I am currently out of the office..."

### Scenario 9: Invalid Email
**Intent**: Email delivery failure or bounce notification
**Actions**:
1. Update Salesforce contact's `Invalid_Email__c` field with bounced email
2. Update assignment status to "email_invalid"
3. Prevent future email attempts

**Example Response**: "Your message could not be delivered. The email address may be invalid..."

### Scenario 10: No Longer Works
**Intent**: Person no longer works at the company
**Actions**:
1. Forward email to Victoria Grant
2. Update assignment status to "no_longer_works"
3. Stop future email attempts

**Example Response**: "John no longer works at this company. He left last month..."

## Installation & Setup

### Prerequisites

- Python 3.9 or higher
- Azure subscription with AI Foundry access
- Microsoft 365 tenant with Graph API permissions
- Salesforce org with API access
- Databricks workspace

### Install Dependencies

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

### Database Setup

Initialize the Databricks tables:

```bash
python main.py setup
```

This creates:
- `expert_lead_assignments` table for round-robin management
- Required views and permissions

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

#### Required Core Settings

```bash
# Microsoft Graph API
GRAPH_API_TENANT_ID=your-tenant-id
GRAPH_API_CLIENT_ID=your-client-id
GRAPH_API_CLIENT_SECRET=your-client-secret
INBOX_MONITOR_EMAIL=inbox@yourcompany.com

# Azure AI Foundry
AZURE_AI_FOUNDRY_CONNECTION_STRING=https://endpoint;key;resource_group;project_name

# Salesforce
SALESFORCE_BASE_URL=https://yourorg.sandbox.my.salesforce.com
SALESFORCE_CLIENT_ID=your-salesforce-client-id
SALESFORCE_CLIENT_SECRET=your-salesforce-client-secret
SALESFORCE_USERNAME=your-salesforce-username
SALESFORCE_PASSWORD=your-salesforce-password
SALESFORCE_CASE_QUEUE=Case_Queue_Name

# Databricks
DATABRICKS_SERVER_HOSTNAME=your-databricks-server.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_ACCESS_TOKEN=your-access-token
DATABRICKS_CATALOG=your-catalog
DATABRICKS_SCHEMA=your-schema

# Scenario Configuration
SCENARIO_VICTORIA_GRANT_EMAIL=victoria.grant@yourcompany.com
SCENARIO_ACCOUNT_TEAM_EMAIL=support@yourcompany.com
```

#### Optional Test Mode Settings

```bash
# Test Mode (for safe testing)
TEST_MODE=true
TEST_EMAIL_SENDER=your-test-email@yourcompany.com
TEST_SALESFORCE_EMAIL=real-customer@clientcompany.com
TEST_FORCE_SCENARIO=9  # Force specific scenario for testing
```

#### Optional Advanced Settings

```bash
# Processing Configuration
INBOX_MONITOR_POLLING_INTERVAL=300  # seconds
INBOX_MONITOR_BATCH_SIZE=10
INBOX_MONITOR_MAX_RETRY_ATTEMPTS=3

# Logging
LOGGING_LEVEL=INFO
LOGGING_FORMAT=json

# Environment
ENVIRONMENT=production
INBOX_MONITOR_DRY_RUN=false
```

### Configuration Validation

The system validates all required configurations on startup. Missing or invalid settings will prevent the application from starting with clear error messages.

## Usage

### Command Line Interface

The inbox monitor provides several commands for different operations:

#### Start Continuous Monitoring

```bash
python main.py run
```

**What it does**:
- Monitors the configured email inbox continuously
- Processes new emails every 5 minutes (configurable)
- Classifies emails using AI and routes them appropriately
- Logs all activities with structured logging

**Output Example**:
```
🚀 Starting Inbox Monitor
📧 Monitoring: inbox@yourcompany.com
⏱️  Polling interval: 300 seconds
📁 Output: salesforce
Press Ctrl+C to stop...

✅ Processed 3 emails in 2.45 seconds
   📊 Positive responses: 1 (assigned to expert)
   📧 Service inquiries: 1 (forwarded to account team)
   ❌ Invalid emails: 1 (marked in Salesforce)
```

#### Check Inbox Once

```bash
python main.py check
```

**What it does**:
- Processes all current emails in the inbox once
- Useful for testing or manual processing
- Shows detailed results and exits

**Output Example**:
```
🔄 Checking inbox once...
✅ Inbox check completed:
   📊 Processed: 5 emails
   ❌ Failed: 0 emails
   ⏱️  Time: 8.32 seconds
```

#### Show System Status

```bash
python main.py status
```

**What it does**:
- Validates all configurations
- Tests all service connections
- Shows current system health

**Output Example**:
```
📊 Inbox Monitor Status
==================================================
✅ Configuration: Valid
⚙️  Configuration:
   Environment: production
   Monitored email: inbox@yourcompany.com
   Polling interval: 300 seconds
   Batch size: 10
   Output type: salesforce
🧪 Modes:
   Dry run: DISABLED
🔗 Testing connections...
✅ All connections healthy
```

#### Test API Connections

```bash
python main.py test
```

**What it does**:
- Tests Microsoft Graph API connection
- Verifies inbox access permissions
- Shows user and mailbox information

#### Setup Database Tables

```bash
python main.py setup
```

**What it does**:
- Creates required Databricks tables
- Sets up proper permissions and indexes
- Validates table structure

### Production Usage

For production deployment, use a process manager like systemd or supervisor:

**systemd service example** (`/etc/systemd/system/inbox-monitor.service`):
```ini
[Unit]
Description=Inbox Monitor Service
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/path/to/agents/inbox_monitor
ExecStart=/usr/bin/python main.py run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start the service:
```bash
sudo systemctl enable inbox-monitor
sudo systemctl start inbox-monitor
sudo systemctl status inbox-monitor
```

## Test Mode

Test Mode is a crucial feature that allows safe testing of the system without affecting production data or real customer emails.

### How Test Mode Works

1. **Email Substitution**: When an email is received from your test email address, the system substitutes it with a real customer email for database lookups
2. **Safe Testing**: Allows testing all scenarios without sending emails from real customer addresses
3. **Real Integration**: Tests actual Salesforce, Databricks, and AI Foundry integration

### Configuring Test Mode

```bash
# Enable test mode
TEST_MODE=true

# Your test email (the one you'll send emails from)
TEST_EMAIL_SENDER=your-test-email@yourcompany.com

# Real customer email to simulate (must exist in Salesforce/Databricks)
TEST_SALESFORCE_EMAIL=real-customer@clientcompany.com

# Optional: Force specific scenario for testing
TEST_FORCE_SCENARIO=9  # Forces bounce email scenario
```

### Test Mode Example

1. **Setup**: Configure test mode with your email and a real customer email
2. **Send Test Email**: Send an email from `your-test-email@yourcompany.com` to the monitored inbox
3. **System Processing**:
   - Detects your test email as sender
   - Substitutes lookup to use `real-customer@clientcompany.com`
   - Processes normally with real Salesforce/Databricks operations
   - Updates the real customer's records safely

### Benefits of Test Mode

- ✅ **Safe Testing**: No need to use real customer emails
- ✅ **Real Integration**: Tests actual service connections
- ✅ **Complete Workflow**: Tests end-to-end processing
- ✅ **Production Data**: Works with real customer records
- ✅ **Scenario Testing**: Can force specific scenarios

## Testing Framework

The system includes comprehensive testing capabilities for development, validation, and troubleshooting.

### Test Files Overview

#### Core Test Files

**`test_end_to_end_integration.py`**
- **Purpose**: Complete integration testing with real services
- **What it tests**: All scenarios (5-10) with actual Salesforce, Databricks, and AI Foundry
- **Usage**: `python test_end_to_end_integration.py`
- **Safety**: Requires explicit confirmation due to real operations
- **Output**: Detailed test report with timing and success metrics

**`test_scenarios.py`**
- **Purpose**: Unit testing of individual scenarios
- **What it tests**: Scenario logic without real service calls
- **Usage**: `pytest test_scenarios.py`
- **Safety**: Uses mocked services, completely safe

**`test_scenarios_mock.py`**
- **Purpose**: Mocked scenario testing with AI classification
- **What it tests**: AI classification + scenario routing with mocked external services
- **Usage**: `python test_scenarios_mock.py`

#### Service-Specific Tests

**`tests/test_salesforce_client.py`**
- **Purpose**: Salesforce API integration testing
- **Coverage**: Case creation, contact updates, authentication
- **Usage**: `pytest tests/test_salesforce_client.py`

**`tests/test_azure_ai_foundry_client.py`**
- **Purpose**: AI Foundry classification testing
- **Coverage**: Intent classification, agent management, response parsing
- **Usage**: `pytest tests/test_azure_ai_foundry_client.py`

**`tests/test_round_robin_service.py`**
- **Purpose**: Expert assignment testing
- **Coverage**: Round-robin logic, assignment tracking, status updates
- **Usage**: `pytest tests/test_round_robin_service.py`

#### Specialized Test Files

**`test_real_ai_classification.py`**
- **Purpose**: Real AI classification testing with sample emails
- **What it tests**: Azure AI Foundry with various email types
- **Usage**: `python test_real_ai_classification.py`
- **Note**: Uses real AI service, consumes tokens

**`test_complete_scenarios.py`**
- **Purpose**: Complete scenario workflow testing
- **Coverage**: Full scenario processing with mocked external services
- **Usage**: `pytest test_complete_scenarios.py`

### Running Tests

#### Run All Tests
```bash
# Run all pytest tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html
```

#### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/

# Integration tests
python test_end_to_end_integration.py

# Scenario tests
pytest test_scenarios.py test_complete_scenarios.py

# Service tests
pytest tests/test_*_client.py
```

#### Run Individual Scenarios
```bash
# Test positive response scenario
pytest test_scenarios.py::test_scenario_5_positive

# Test bounce email scenario
pytest test_scenarios.py::test_scenario_9_email_invalid
```

### Test Reports and Output

#### Integration Test Reports

Integration tests generate detailed reports saved as `integration_test_report_*.txt`:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        END-TO-END INTEGRATION TEST REPORT                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Test ID: E2E_TEST_20250721_205654                                           ║
║ Timestamp: 2025-07-21T20:59:33.898070Z                                      ║
║ Environment: production                                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ SUMMARY                                                                      ║
║   Total Tests: 6                                                            ║
║   Successful:  5                                                            ║
║   Failed:      1                                                            ║
║   Success Rate:  83.3%                                                      ║
║   Avg Processing Time:  3.45s                                               ║
║   Total Processing Time: 20.71s                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

Scenario_5_Positive: ✅ PASS (2.34s)
  Real Operations:
    ai_classification: ✅ Real
    salesforce_case: ✅ Real
    databricks_assignment: ✅ Real
  Actions Taken:
    • Found contact in Databricks: Account=0013800001MJTpeAAH, Contact=0033t00004eN3ANAA0
    • Assigned expert via round-robin: Michael Villarreal
    • Created Salesforce case: 500Dl00000AHpxOIAT
```

#### Test Configuration Files

Some test files you created during development:

**`test_scenario_9_config.py`** (Excluded from git)
- **Purpose**: Validates Scenario 9 configuration
- **Usage**: Checks test mode setup for bounce testing
- **Output**: Shows configured emails and test mode status

**`test_salesforce_fix.py`** (Excluded from git)
- **Purpose**: Validates Salesforce field fix
- **Usage**: Tests the Invalid_Email__c field update with email addresses
- **Note**: Demonstrates the fix for boolean vs email field issue

### Test Data Management

#### Test Identifiers

All integration tests use unique identifiers for tracking:
- **Format**: `E2E_TEST_YYYYMMDD_HHMMSS`
- **Purpose**: Identifies test data in Salesforce and Databricks
- **Cleanup**: Search for test identifier to find test records

#### Manual Cleanup

After integration tests, you may need to manually clean up:

**Salesforce**:
1. Search for cases with test identifier in Subject/Description
2. Check contacts with `Invalid_Email__c` field updates
3. Review any test assignments created

**Databricks**:
1. Query assignment tables for test identifiers
2. Check for test assignment records
3. Verify test data doesn't affect production metrics

## Monitoring & Maintenance

### Logging

The system uses structured logging with configurable levels:

```python
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Formats: json, standard

# Example log entry
{
    "event": "Email intent classified successfully",
    "intent": "positive",
    "confidence": 0.95,
    "processing_time_ms": 1250,
    "sender": "customer@example.com",
    "timestamp": "2025-07-21T20:30:15.123456Z",
    "logger": "services.azure_ai_foundry_client",
    "level": "info"
}
```

### Key Metrics to Monitor

#### Processing Metrics
- **Email processing rate**: Emails processed per minute
- **Classification accuracy**: AI confidence scores
- **Processing time**: End-to-end processing duration
- **Error rates**: Failed classifications or service calls

#### Service Health
- **API response times**: Graph API, Salesforce, Databricks
- **Authentication status**: Token refresh success/failure
- **Connection stability**: Service availability and timeouts

#### Business Metrics
- **Scenario distribution**: Volume of each scenario type
- **Expert assignment balance**: Round-robin effectiveness
- **Customer response rates**: Positive vs negative responses

### Health Checks

Regular health checks ensure system reliability:

```bash
# Daily health check
python main.py status

# Connection testing
python main.py test

# Process a test batch
python main.py check
```

### Maintenance Tasks

#### Weekly
- Review error logs for patterns
- Check expert assignment balance
- Validate AI classification accuracy
- Monitor service quota usage

#### Monthly
- Update expert availability in Databricks
- Review and optimize AI prompts
- Analyze scenario distribution trends
- Clean up old test data

#### Quarterly
- Review and update configuration
- Assess performance optimizations
- Update dependencies and security patches
- Conduct full integration testing

## Troubleshooting

### Common Issues and Solutions

#### Email Not Processing

**Symptoms**: New emails not being detected or processed

**Troubleshooting Steps**:
1. Check Graph API permissions: `python main.py test`
2. Verify inbox configuration: `python main.py status`
3. Check polling interval settings
4. Review authentication status

**Common Causes**:
- Expired authentication tokens
- Changed mailbox permissions
- Network connectivity issues
- Polling interval too long

#### AI Classification Errors

**Symptoms**: Low confidence scores or incorrect classification

**Troubleshooting Steps**:
1. Test AI service: `python test_real_ai_classification.py`
2. Review recent classification results
3. Check Azure AI Foundry service status
4. Validate API credentials

**Common Causes**:
- Service outages or throttling
- Prompt engineering issues
- Ambiguous email content
- Model deployment problems

#### Salesforce Integration Issues

**Symptoms**: Case creation failures or contact update errors

**Troubleshooting Steps**:
1. Test Salesforce connection: `pytest tests/test_salesforce_client.py`
2. Check field permissions and validation rules
3. Verify contact and account data
4. Review API quotas and limits

**Common Causes**:
- Insufficient permissions
- Invalid field values
- Missing required data
- API rate limits

#### Databricks Connection Problems

**Symptoms**: Expert assignment failures or connection timeouts

**Troubleshooting Steps**:
1. Test database connection: `python setup_databricks.py`
2. Verify table structure and permissions
3. Check warehouse availability
4. Review SQL query performance

**Common Causes**:
- Warehouse not running
- Table schema changes
- Network connectivity
- SQL permission issues

### Error Codes and Messages

#### Configuration Errors
- `GRAPH_API_TENANT_ID is required`: Missing Microsoft 365 tenant ID
- `target_salesforce_email is required when test mode is enabled`: Test mode configuration incomplete
- `Invalid Azure AI Foundry connection string format`: Malformed connection string

#### Service Errors
- `Failed to classify email intent`: AI service unavailable or misconfigured
- `Failed to create Salesforce case`: Salesforce API or permission issues
- `No available experts for assignment`: Empty or inactive expert pool

#### Processing Errors
- `Contact not found in lookup table`: Customer not in Databricks database
- `Invalid Email: invalid email address: true`: Salesforce field type mismatch (fixed)
- `SSL shutdown timed out`: Network connectivity issues (automatically handled)

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
python main.py run --log-level DEBUG
```

This provides verbose output including:
- API request/response details
- Database query execution
- Internal processing steps
- Timing information

### Support and Documentation

#### Additional Resources
- **Test Mode Guide**: `README_TEST_MODE.md`
- **Setup Instructions**: `SETUP.md`
- **Salesforce Permissions**: `SALESFORCE_PERMISSIONS_ISSUE.md`

#### Getting Help
1. Check system status: `python main.py status`
2. Review recent logs for error patterns
3. Test individual components
4. Consult troubleshooting section above

## API References

### Main Application

```python
# Start continuous monitoring
python main.py run

# Process inbox once
python main.py check

# Show system status
python main.py status

# Test connections
python main.py test

# Setup database
python main.py setup
```

### Service Classes

#### Azure AI Foundry Client
```python
from services.azure_ai_foundry_client import AzureAIFoundryClient

async with AzureAIFoundryClient(settings.azure_ai_foundry) as client:
    result = await client.classify_email_intent(
        subject="Email subject",
        body="Email body content", 
        sender_email="sender@example.com"
    )
    # result.intent: EmailIntent enum
    # result.confidence: float (0.0-1.0)
    # result.reasoning: str
```

#### Salesforce Client
```python
from services.salesforce_client import SalesforceClient, CaseCreateRequest

async with SalesforceClient(settings.salesforce) as sf_client:
    # Create case
    case_request = CaseCreateRequest(
        account_id="account_id",
        contact_id="contact_id", 
        owner_id="expert_id",
        subject="Case subject",
        description="Case description"
    )
    response = await sf_client.create_case(case_request)
    
    # Update contact
    contact_update = ContactUpdateRequest(
        contact_id="contact_id",
        invalid_email_address="bounced@email.com"
    )
    success = await sf_client.update_contact_invalid_email(contact_update)
```

#### Round Robin Service
```python
from services.round_robin_service import RoundRobinService

async with RoundRobinService(settings.databricks, settings.test_mode) as rr_service:
    # Assign expert
    expert = await rr_service.assign_lead_to_expert("customer@example.com")
    
    # Update assignment status
    await rr_service.update_assignment_status(
        assignment_id="assignment_id",
        new_status="email_invalid"
    )
    
    # Get statistics
    stats = await rr_service.get_assignment_statistics()
```

### Email Models

```python
from models.email import Email, EmailAddress, EmailBody

# Email structure
email = Email(
    id="unique_id",
    conversation_id="conversation_id",
    received_datetime=datetime.now(UTC),
    sender=EmailAddress(email="sender@example.com", name="Sender Name"),
    subject="Email subject",
    body=EmailBody(content_type="text/plain", content="Email content"),
    # ... additional fields
)
```

### Configuration Models

```python
from config.settings import get_settings, AppSettings

# Load configuration
settings = get_settings()

# Access configuration sections
settings.graph_api.tenant_id
settings.salesforce.base_url
settings.azure_ai_foundry.endpoint
settings.databricks.server_hostname
settings.test_mode.enabled
```

---

## Quick Start Checklist

### Initial Setup
- [ ] Install Python 3.9+ and dependencies
- [ ] Configure environment variables
- [ ] Set up Azure AI Foundry project
- [ ] Configure Microsoft 365 Graph API permissions
- [ ] Set up Salesforce connected app
- [ ] Configure Databricks workspace and tables
- [ ] Run database setup: `python main.py setup`

### Testing
- [ ] Validate configuration: `python main.py status`
- [ ] Test connections: `python main.py test`
- [ ] Configure test mode for safe testing
- [ ] Run unit tests: `pytest`
- [ ] Run integration tests (with caution)

### Production Deployment
- [ ] Disable test mode (`TEST_MODE=false`)
- [ ] Set up process monitoring (systemd/supervisor)
- [ ] Configure log rotation and monitoring
- [ ] Set up health check alerts
- [ ] Document operational procedures

### Ongoing Maintenance
- [ ] Monitor processing metrics and error rates
- [ ] Review AI classification accuracy weekly
- [ ] Update expert assignments monthly
- [ ] Conduct quarterly system reviews

---

*This system represents a sophisticated integration of multiple cloud services to provide intelligent, automated email response handling. Proper configuration and testing are essential for reliable operation.*