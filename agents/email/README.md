# Email Agent - Enterprise Email Campaign Processing System

## 📖 Quick Navigation

**New to Email Agent?** Start here:
- [⚡ Setup Guide](docs/SETUP.md) - Get Email Agent running in 30 minutes
- [⚙️ Configuration Guide](docs/CONFIGURATION.md) - Environment setup and authentication
- [🔧 Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions

**Working with the complete email automation system?**
- [📧 Email Agent Documentation](../email/README.md) - Outbound email campaign processing
- [📥 Inbox Monitor Documentation](../inbox_monitor/README.md) - Inbound email AI classification

## Overview

The Email Agent is a sophisticated email processing system designed for automated email campaign management at enterprise scale. It seamlessly integrates Azure Communication Services, Azure Blob Storage, and Databricks to provide a complete email processing pipeline from campaign data to delivery confirmation.

## Table of Contents

1. [Quick Navigation](#-quick-navigation) ← **Start Here**
2. [System Architecture](#system-architecture)
3. [Features & Capabilities](#features--capabilities)
4. [Email Processing Pipeline](#email-processing-pipeline)
5. [Installation & Setup](#installation--setup) → See [Setup Guide](docs/SETUP.md)
6. [Configuration](#configuration) → See [Configuration Guide](docs/CONFIGURATION.md)
7. [Usage](#usage)
8. [Test Mode](#test-mode)
9. [Data Models & Schema](#data-models--schema)
10. [Testing Framework](#testing-framework)
11. [Monitoring & Analytics](#monitoring--analytics)
12. [Troubleshooting](#troubleshooting) → See [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
13. [API References](#api-references)

## System Architecture

### Process Flow Diagrams

For detailed visual workflows, see the comprehensive system diagrams:
- [**Outbound Email Campaign Workflow**](diagrams/outbound_email_campaign_workflow.md) - Complete email processing pipeline from monitoring to delivery
- [**Outbound Email Error Handling**](diagrams/outbound_email_error_handling.md) - Error handling, retry logic, and recovery procedures  
- [**Integrated System Overview**](diagrams/integrated_system_overview.md) - Complete system architecture and component relationships

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Databricks    │    │  Azure Blob     │    │   Azure ACS     │
│   Data Lake     │    │   Storage       │    │ Email Service   │
│                 │    │                 │    │                 │
│ • Pipeline      │    │ • Email HTML    │    │ • SMTP Delivery │
│   tracking      │    │ • Research JSON │    │ • Status        │
│ • Email audit   │    │ • Customer data │    │   tracking      │
│ • Statistics    │    │ • Metadata      │    │ • Authentication│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                   ┌─────────────────┐
                   │   Email Agent   │
                   │   Application   │
                   │                 │
                   │ • Email         │
                   │   Processor     │
                   │ • Batch         │
                   │   Processing    │
                   │ • Content       │
                   │   Assembly      │
                   │ • Test Mode     │
                   │ • Analytics     │
                   └─────────────────┘
```

### Technology Stack

- **Python 3.8+**: Core application language with async/await support
- **Azure Communication Services**: Enterprise-grade email delivery
- **Azure Blob Storage**: Scalable content storage with dual authentication
- **Databricks SQL**: Data warehouse and analytics platform with OAuth authentication
- **Azure Key Vault**: Secure credential management for OAuth
- **Connection Pooling**: Efficient database connection management
- **Pydantic**: Configuration validation and data modeling
- **Structlog**: Structured logging and observability
- **asyncio**: Asynchronous processing for high throughput

### OAuth Migration Implementation

This system has been migrated from Personal Access Token (PAT) authentication to OAuth service principal authentication for Databricks connectivity. Key improvements include:

- **Enhanced Security**: OAuth service principal authentication replaces PAT tokens
- **Connection Pooling**: 80-90% reduction in connection overhead
- **Health Monitoring**: Comprehensive health check endpoints for operational monitoring
- **Automatic Token Management**: Transparent OAuth token refresh and caching
- **Production Readiness**: Full monitoring, alerting, and troubleshooting capabilities

## Features & Capabilities

### Intelligent Email Processing

The system provides a complete email campaign processing pipeline:

1. **Database Monitoring**: Continuously monitors Databricks for pending email campaigns
2. **Content Assembly**: Retrieves personalized email content from blob storage
3. **Contact Management**: Extracts recipient information from research data
4. **Email Delivery**: Sends emails via Azure Communication Services
5. **Status Tracking**: Maintains complete audit trails and delivery confirmation

### Enterprise-Grade Integration

- **Azure Communication Services**: Professional email delivery with authentication
- **Azure Blob Storage**: Scalable content storage with SAS token security
- **Databricks**: Data warehouse integration with SQL analytics
- **Comprehensive Logging**: Structured logging with JSON format support

### Advanced Features

- **Test Mode**: Safe testing environment with email redirection
- **Batch Processing**: Configurable batch sizes for optimal performance
- **Error Recovery**: Intelligent retry logic with failure tracking
- **Analytics**: Built-in processing statistics and performance monitoring
- **Security**: SAS token support for enhanced authentication

## Email Processing Pipeline

### 1. Campaign Monitoring

The system monitors the Databricks table for records where:
- `agent_name = 'communication'`
- `status = 'S'` (Successfully processed by communication agent)
- `is_email_sent IS NULL` (Not yet sent)

### 2. Content Retrieval Process

For each pending email campaign:

1. **Load Research Data**: Retrieves `{customer_id}_research_output.json` from blob storage
   - Contains contact information and email metadata
   - Includes subject line in `sample_email_subject` field
   - Provides recipient details in `contact_list[0].email`

2. **Load Email Content**: Retrieves `{customer_id}_email.html` from blob storage
   - Personalized HTML email content
   - Ready-to-send format with proper styling

3. **Contact Extraction**: Processes contact information
   - Primary contact from research data
   - Email validation and formatting
   - Name and title extraction

### 3. Email Assembly & Delivery

1. **Content Assembly**: Combines HTML content with subject line and recipient
2. **Test Mode Processing**: Applies test mode transformations if enabled
3. **Azure Delivery**: Sends via Azure Communication Services
4. **Status Tracking**: Updates database with delivery confirmation
5. **Audit Logging**: Records all processing steps and outcomes

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- Azure subscription with Communication Services resource
- Azure Storage Account with blob container
- Databricks workspace with SQL warehouse
- Network connectivity between all services

### Install Dependencies

```bash
cd agents/email
pip install -r requirements.txt
```

### Required Python Packages

```
azure-communication-email>=1.0.0
azure-storage-blob>=12.14.0
azure-identity>=1.12.0
databricks-sql-connector>=3.0.0
pydantic>=2.0.0
structlog>=23.1.0
aiohttp>=3.8.0
```

### Database Setup

Initialize the Databricks tables:

```bash
python main.py setup
```

This creates:
- `email_communication_pipeline` table for workflow tracking
- Required views for pending emails and statistics
- Proper indexes and permissions

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

#### Required Core Settings

```bash
# Azure Communication Services
# ACS credentials are now retrieved from Azure Key Vault
# Required Key Vault secrets:
# - azure-communication-connection-string
# - azure-communication-sender-email

# Azure Blob Storage (choose one authentication method)
# Option 1: Connection String
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...

# Option 2: SAS Token (recommended for production)
AZURE_STORAGE_ACCOUNT_NAME=yourstorageaccount
AZURE_STORAGE_SAS_TOKEN=?sv=2022-11-02&ss=b&srt=sco&sp=rwdlacupiytfx&se=2024-12-31T23:59:59Z...

BLOB_CONTAINER_NAME=lowtouch

# Databricks
DATABRICKS_SERVER_HOSTNAME=your-workspace.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_ACCESS_TOKEN=your-token
DATABRICKS_CATALOG=your_catalog
DATABRICKS_SCHEMA=your_schema
```

#### Optional Test Mode Settings

```bash
# Test Mode (for safe testing)
TEST_MODE=true
TEST_EMAIL_OVERRIDE=your-test-email@yourcompany.com
```

#### Optional Processing Settings

```bash
# Processing Configuration
EMAIL_PROCESSING_INTERVAL_MINUTES=5  # Processing interval
EMAIL_BATCH_SIZE=10                  # Emails per batch
EMAIL_MAX_RETRY_ATTEMPTS=3           # Retry attempts

# Logging
LOGGING_LEVEL=INFO
LOGGING_FORMAT=json

# Environment
ENVIRONMENT=production
```

### Azure Storage Authentication Options

**Option 1: Connection String**
- Full account access with permanent credentials
- Suitable for development environments
- Simple setup and configuration

**Option 2: SAS Token (Recommended for Production)**
- Time-limited access with configurable expiration
- Scoped permissions (can limit to specific containers/operations)
- Enhanced security with easy rotation and revocation

To generate a SAS token:
1. Go to Azure Portal → Storage Account → Shared Access Signature
2. Set permissions: Read, List (minimum required)
3. Set appropriate expiration date
4. Generate token and use in `AZURE_STORAGE_SAS_TOKEN`

### OAuth Configuration

The system uses OAuth service principal authentication for Databricks connectivity. Required Azure Key Vault secrets:

```bash
# Service Principal Credentials (stored in Azure Key Vault)
AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-service-principal-client-id
AZURE_CLIENT_SECRET=your-service-principal-secret

# Key Vault Secret Names (default values)
KEY_VAULT_TENANT_ID_SECRET=sales-engagement-service-principal-tenantid
KEY_VAULT_CLIENT_ID_SECRET=sales-engagement-service-principal-clientid
KEY_VAULT_CLIENT_SECRET_SECRET=sales-engagement-service-principal-secretid

# Connection Pool Configuration
CONNECTION_POOL_MIN_SIZE=2          # Minimum connections (default: 2)
CONNECTION_POOL_MAX_SIZE=4          # Maximum connections (default: 4)
CONNECTION_TIMEOUT_SECONDS=30       # Connection timeout (default: 30)

# Health Monitoring
HEALTH_CHECK_PORT=8081              # Health check server port (default: 8081)
HEALTH_CHECK_ENABLED=true           # Enable health endpoints (default: true)
METRICS_COLLECTION_INTERVAL=60      # Metrics collection interval (default: 60s)
```

### Health Check Endpoints

The system provides comprehensive health monitoring endpoints:

- **`GET /health`**: Simple health check for load balancers (returns 200/503)
- **`GET /health/detailed`**: Comprehensive system health with component details
- **`GET /ready`**: Kubernetes readiness probe endpoint
- **`GET /`**: Service information and available endpoints

Example health check usage:
```bash
# Check service health
curl http://localhost:8081/health

# Get detailed health information
curl http://localhost:8081/health/detailed | jq '.'

# Check readiness for traffic
curl http://localhost:8081/ready
```

### Configuration Validation

The system validates all required configurations on startup. Missing or invalid settings will prevent the application from starting with clear error messages.

## Usage

### Command Line Interface

The email agent provides comprehensive commands for all operations:

#### Process Emails

```bash
# Run continuous processing (production mode)
python main.py run

# Process emails once and exit
python main.py process
```

**Continuous Processing Output**:
```
🚀 Starting Email Agent
📧 Processing interval: 5 minutes
📁 Blob container: lowtouch
⚡ Batch size: 10
Press Ctrl+C to stop...

✅ Processed batch: 5 emails sent, 0 failed (3.2s)
✅ Processed batch: 3 emails sent, 0 failed (2.1s)
⏱️  Next check in 5 minutes...
```

**Single Processing Output**:
```
🔄 Processing emails once...
✅ Processing completed:
   📊 Processed: 8 records
   📧 Sent: 7 emails
   ❌ Failed: 1 email
```

#### Testing & Diagnostics

```bash
# Send test email
python main.py test user@example.com

# Show system status
python main.py status

# Show processing statistics
python main.py stats 30  # Last 30 days
```

**Test Email Output**:
```
📧 Sending test email to: user@example.com
✅ Test email sent successfully!
   📨 Message ID: <abc123@azure.com>
```

**System Status Output**:
```
📊 System Status
==================================================
✅ Configuration: Valid
⚙️  Configuration:
   Environment: production
   Processing interval: 5 minutes
   Batch size: 10
   Databricks catalog: your_catalog
   Databricks schema: your_schema
   Blob container: lowtouch
🧪 Test Mode:
   Status: DISABLED
🔗 Connection Tests:
✅ Databricks: Connected
✅ Azure Communication Services: Connected
✅ Azure Blob Storage: Connected
```

#### Setup & Maintenance

```bash
# Setup database tables
python main.py setup

# Show help
python main.py --help
```

### Alternative Runner

For simpler operations, use the dedicated runner:

```bash
# Start continuous processing
python run_email_processor.py

# Process once and exit
python run_email_processor.py --once

# Send test email
python run_email_processor.py --test user@example.com
```

### Production Usage

For production deployment, use a process manager like systemd:

**systemd service example** (`/etc/systemd/system/email-agent.service`):
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

## Test Mode

Test Mode is a critical feature that enables safe testing of the email system without affecting real customers or sending unintended emails.

### How Test Mode Works

1. **Email Redirection**: When test mode is enabled, all emails are redirected to a designated test email address
2. **Content Preservation**: Original email content and formatting are preserved
3. **Safe Testing**: Allows testing of the complete email pipeline without customer impact
4. **Real Integration**: Tests actual Azure services and Databricks integration

### Configuring Test Mode

```bash
# Enable test mode
TEST_MODE=true

# Redirect all emails to this address
TEST_EMAIL_OVERRIDE=your-test-email@yourcompany.com
```

### Test Mode Example

1. **Setup**: Configure test mode with your test email address
2. **Process Campaign**: Run normal email processing commands
3. **System Processing**:
   - Retrieves real customer data and email content
   - Processes normally through all stages
   - Redirects final email delivery to test address
   - Updates database with actual processing results

### Benefits of Test Mode

- ✅ **Customer Safety**: No risk of sending emails to real customers
- ✅ **Real Testing**: Tests actual service integrations and data processing
- ✅ **Complete Pipeline**: Validates end-to-end email processing workflow
- ✅ **Production Data**: Works with real customer content and research data
- ✅ **Easy Toggle**: Simple environment variable to enable/disable

## Data Models & Schema

### Database Schema

#### Main Table: `email_communication_pipeline`

| Column | Type | Description |
|--------|------|-------------|
| `batch_id` | INT | Batch processing identifier |
| `run_date` | STRING | Processing run date |
| `agent_name` | STRING | Processing agent name |
| `status` | STRING | Agent processing status (S/F/P) |
| `customer_id` | STRING | Customer identifier |
| `contact_id` | STRING | Contact identifier |
| `customer_name` | STRING | Customer name |
| `is_email_sent` | BOOLEAN | Email delivery status |
| `recipient_email` | STRING | Email recipient address |
| `subject` | STRING | Email subject line |
| `send_timestamp` | TIMESTAMP | Email send time |
| `send_status` | STRING | Delivery status (sent/failed) |
| `acs_message_id` | STRING | Azure Communication Services message ID |
| `error_message` | STRING | Error details if failed |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Record update time |

### Data Models

#### EmailRecord
```python
@dataclass
class EmailRecord:
    batch_id: int
    run_date: str
    agent_name: str
    status: str
    customer_id: str
    # ... additional fields for email tracking
```

#### ResearchOutput
```python
@dataclass
class ResearchOutput:
    customer_name: str
    customer_id: str
    sample_email_subject: str
    contact_list: list[ContactInfo]
    # ... additional campaign metadata
```

#### EmailContent
```python
@dataclass
class EmailContent:
    subject: str
    body_html: str
    recipient_email: str
    # ... additional content fields
```

### Blob Storage Structure

Expected blob storage organization:
```
lowtouch/
└── 20240707/                           # Date folder (YYYYMMDD)
    └── 10016125/                       # Customer ID folder
        └── communication_output/       # Communication output folder
            ├── 10016125_research_output.json   # Contact and metadata
            └── 10016125_email.html             # Email content
```

**Research Output JSON Structure**:
```json
{
    "customer_name": "ACME Corporation",
    "customer_id": "10016125",
    "sample_email_subject": "Partnership Opportunity with ACME",
    "contact_list": [
        {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@acme.com",
            "title": "VP of Technology",
            "salesforce_contact_id": "003XX000004TMM2"
        }
    ],
    "division": "Technology",
    "primary_reason_for_outreach": "Partnership discussion",
    "summary": "Technology partnership opportunity..."
}
```

## Testing Framework

The system includes comprehensive testing capabilities for development, validation, and production monitoring.

### Test Commands

#### System Testing
```bash
# Test complete system functionality
python main.py test user@example.com

# Check all service connections
python main.py status

# Test database setup
python main.py setup
```

#### Processing Testing
```bash
# Process emails once (safe for testing)
python main.py process

# Use alternative runner for testing
python run_email_processor.py --once
```

### Test Files and Scripts

#### Core Test Scripts

**`test_email_loading.py`**
- **Purpose**: Tests email content loading from blob storage
- **Usage**: `python test_email_loading.py`
- **Coverage**: Blob storage connectivity, file retrieval, content parsing

**`test_single_record.py`**
- **Purpose**: Tests processing of individual email records
- **Usage**: `python test_single_record.py`
- **Coverage**: Single email workflow, database integration, error handling

**`simple_processor.py`**
- **Purpose**: Simplified email processor for testing and development
- **Usage**: Used by main.py for core processing logic
- **Coverage**: Complete email processing pipeline with error handling

#### Utility Scripts

**`find_customer_email.py`**
- **Purpose**: Searches for specific customer email records
- **Usage**: Development and debugging tool
- **Coverage**: Database queries and record lookup

**`populate_data.py`**
- **Purpose**: Populates test data for development
- **Usage**: `python populate_data.py`
- **Coverage**: Database setup and test data creation

**`scripts/populate_pipeline_data.py`**
- **Purpose**: Comprehensive pipeline data population
- **Usage**: `python scripts/populate_pipeline_data.py`
- **Coverage**: End-to-end test data creation

### Test Data Management

#### Development Data Population

```bash
# Create test pipeline data
python scripts/populate_pipeline_data.py

# Fast population for testing
python scripts/populate_pipeline_data_fast.py

# Simple test data creation
python scripts/populate_simple.py
```

#### Test Environment Setup

1. **Configure Test Mode**: Set `TEST_MODE=true` in environment
2. **Set Test Email**: Configure `TEST_EMAIL_OVERRIDE`
3. **Create Test Data**: Use population scripts to create test records
4. **Run Processing**: Execute `python main.py process` to test workflow

## Monitoring & Analytics

### Logging System

The system uses structured logging with configurable levels and formats:

```python
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Formats: json, standard

# Example structured log entry
{
    "event": "Email sent successfully",
    "customer_id": "10016125",
    "recipient_email": "customer@example.com",
    "acs_message_id": "abc123@azure.com",
    "processing_time_ms": 1250,
    "timestamp": "2024-07-21T20:30:15.123456Z",
    "logger": "services.email_service",
    "level": "info"
}
```

### Key Metrics to Monitor

#### Processing Metrics
- **Email processing rate**: Emails processed per hour/day
- **Delivery success rate**: Percentage of successful deliveries
- **Processing time**: Average time from database query to delivery
- **Error rates**: Failed processing attempts and reasons

#### Service Health
- **API response times**: Azure services, Databricks connectivity
- **Authentication status**: Token validity and refresh success
- **Connection stability**: Service availability and timeout rates

#### Business Metrics
- **Campaign volume**: Total emails processed per time period
- **Content types**: Distribution of email content categories
- **Customer engagement**: Delivery confirmation rates

### Analytics Commands

```bash
# Show processing statistics
python main.py stats 7    # Last 7 days
python main.py stats 30   # Last 30 days

# System health check
python main.py status
```

**Analytics Output Example**:
```
📈 Email Processing Statistics (Last 30 days)
==================================================
📊 Summary:
   Total processed: 1,247
   Successfully sent: 1,201
   Failed: 46
   Success rate: 96.3%

📋 Details:
   sent: 1,201
   failed: 46
   processing: 0
```

### Database Analytics Views

The system creates SQL views for advanced analytics:

```sql
-- Pending emails ready for processing
SELECT * FROM pending_emails_view;

-- Email delivery status tracking
SELECT * FROM email_delivery_status_view;

-- Processing performance statistics
SELECT * FROM email_processing_stats_view;
```

### Health Checks

Regular health checks ensure system reliability:

```bash
# Daily health check
python main.py status

# Weekly processing review
python main.py stats 7

# Monthly analytics
python main.py stats 30
```

### Maintenance Tasks

#### Daily
- Review processing logs for errors
- Check email delivery success rates
- Monitor system resource usage
- Validate service connectivity

#### Weekly  
- Analyze processing statistics and trends
- Review failed email records and causes
- Check Azure service quotas and limits
- Update test data if needed

#### Monthly
- Review and optimize configuration settings
- Analyze long-term processing trends
- Update dependencies and security patches
- Conduct full system integration testing

## Troubleshooting

### Common Issues and Solutions

#### Email Not Processing

**Symptoms**: No emails being sent despite pending records in database

**Troubleshooting Steps**:
1. Check system status: `python main.py status`
2. Verify database connection and pending records
3. Check Azure Communication Services configuration
4. Review application logs for errors

**Common Causes**:
- Invalid ACS connection string or sender email
- Database connectivity issues
- Blob storage authentication problems
- Processing service not running

#### Blob Storage Access Errors

**Symptoms**: File not found errors or access denied messages

**Troubleshooting Steps**:
1. Verify blob storage configuration: `python main.py status`
2. Check container name and file paths
3. Validate SAS token expiration if using SAS authentication
4. Ensure proper permissions on storage account

**Common Causes**:
- Expired SAS tokens
- Incorrect container or file paths
- Insufficient storage account permissions
- Network connectivity issues

#### Email Delivery Failures

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

#### Database Connection Problems

**Symptoms**: Cannot connect to Databricks or query failures

**Troubleshooting Steps**:
1. Test Databricks connection: `python main.py status`
2. Verify access token validity
3. Check SQL warehouse status
4. Review network connectivity

**Common Causes**:
- Expired Databricks access token
- SQL warehouse not running
- Network firewall restrictions
- Invalid connection parameters

### Error Codes and Messages

#### Configuration Errors
- `Key Vault authentication failed`: Missing or invalid Azure Key Vault configuration
- `ACS credentials not found in Key Vault`: Missing required secrets in Key Vault
- `DATABRICKS_ACCESS_TOKEN is required`: Missing Databricks authentication
- `Invalid blob storage configuration`: Malformed storage settings

#### Processing Errors
- `Failed to load research output`: Blob storage file retrieval error
- `Invalid recipient email address`: Email validation failure
- `Azure Communication Services error`: Email delivery service failure

#### Database Errors
- `Failed to connect to Databricks`: Connection or authentication issue
- `Table does not exist`: Database setup not completed
- `SQL execution failed`: Query or data integrity issue

### Debug Mode

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

### Log Analysis

#### Application Logs
- Review structured logs for error patterns
- Monitor processing times and bottlenecks
- Track success/failure rates over time

#### Azure Portal Monitoring
- Azure Communication Services delivery metrics
- Blob storage access patterns and errors
- Service availability and performance

#### Databricks Monitoring
- SQL warehouse usage and performance
- Query execution times and errors
- Data processing statistics

### Support Resources

#### Getting Help
1. Check system status first: `python main.py status`
2. Review recent logs for specific error messages
3. Test individual components with test commands
4. Consult troubleshooting section for common issues

#### Additional Documentation
- Azure Communication Services documentation
- Azure Blob Storage best practices
- Databricks SQL warehouse management
- Python async/await patterns

## API References

### Main Application

```python
# CLI Commands
python main.py run                      # Continuous processing
python main.py process                  # Process once
python main.py test <email>             # Send test email
python main.py status                   # System status
python main.py stats [days]             # Processing statistics
python main.py setup                    # Database setup
```

### Service Classes

#### EmailService
```python
from services.email_service import EmailService

# Initialize email service
email_service = EmailService(settings)
await email_service.initialize()

# Process pending emails
results = await email_service.process_pending_emails(batch_size=10)

# Send test email
result = await email_service.send_test_email("user@example.com")

# Get processing statistics
stats = email_service.get_processing_stats(days=30)

# Cleanup
email_service.cleanup()
```

#### BlobStorageService
```python
from services.blob_service import BlobStorageService

# Initialize blob service
blob_service = BlobStorageService(settings.azure_storage)

# Get email content
research_data = blob_service.get_research_output(customer_id, date_folder)
email_content = blob_service.get_email_content(customer_id, date_folder)

# Test connection
is_connected = blob_service.test_connection()
```

#### AzureEmailClient
```python
from email_clients.azure_email_client import AzureEmailClient

# Initialize email client
email_client = AzureEmailClient(settings.azure_communication)

# Send email
result = await email_client.send_email(
    to_email="recipient@example.com",
    subject="Subject Line",
    body_html="<html>Email content</html>"
)

# Test connection
is_connected = await email_client.test_connection()
```

### Data Models

#### EmailRecord
```python
from database.models import EmailRecord

# Create email record
record = EmailRecord(
    batch_id=123,
    run_date="20240721",
    agent_name="communication",
    status="S",
    customer_id="10016125",
    # ... additional fields
)
```

#### ResearchOutput
```python
from database.models import ResearchOutput

# Load from JSON data
research = ResearchOutput.from_dict(json_data)

# Get primary contact
contact = research.get_primary_contact()
primary_email = contact.email if contact else None
```

### Configuration

```python
from config.settings import get_settings, AppSettings

# Load settings
settings = get_settings()

# Access configuration sections
settings.azure_communication.connection_string
settings.azure_storage.account_name
settings.databricks.server_hostname
settings.processing.batch_size
settings.test_mode.test_mode
```

---

## Quick Start Checklist

### Initial Setup
- [ ] Install Python 3.8+ and dependencies
- [ ] Configure Azure Communication Services resource
- [ ] Set up Azure Storage Account with blob container
- [ ] Configure Databricks workspace and SQL warehouse
- [ ] Set up environment variables
- [ ] Run database setup: `python main.py setup`

### Testing
- [ ] Validate configuration: `python main.py status`
- [ ] Send test email: `python main.py test user@example.com`
- [ ] Configure test mode for safe testing
- [ ] Process test batch: `python main.py process`

### Production Deployment
- [ ] Disable test mode (`TEST_MODE=false`)
- [ ] Set up process monitoring (systemd/supervisor)
- [ ] Configure log rotation and monitoring
- [ ] Set up health check alerts
- [ ] Document operational procedures

### Ongoing Maintenance
- [ ] Monitor processing metrics and delivery rates
- [ ] Review email delivery statistics weekly
- [ ] Update Azure service configurations as needed
- [ ] Conduct monthly system performance reviews

---

*This Email Agent provides enterprise-grade email campaign processing with comprehensive monitoring, security, and scalability features. Proper configuration and testing are essential for reliable operation in production environments.*