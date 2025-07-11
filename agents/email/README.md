# SendEmail - Enterprise Email Processing System

A modular, enterprise-grade email processing system that integrates Azure Communication Services, Azure Blob Storage, and Databricks for automated email campaign management.

## Overview

The SendEmail system is designed to:
- Monitor Databricks tables for email processing requests
- Retrieve email content and metadata from Azure Blob Storage
- Send emails using Azure Communication Services
- Track email delivery status and maintain audit trails
- Provide comprehensive logging and error handling

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Databricks    │    │  Azure Blob     │    │   Azure ACS     │
│   Database      │    │   Storage       │    │  Email Service  │
│                 │    │                 │    │                 │
│ • Pipeline      │    │ • Email HTML    │    │ • Email         │
│   tracking      │    │ • Research JSON │    │   delivery      │
│ • Email audit   │    │ • Metadata      │    │ • Status        │
│ • Statistics    │    │                 │    │   tracking      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                   ┌─────────────────┐
                   │   SendEmail     │
                   │   Application   │
                   │                 │
                   │ • Email         │
                   │   Processor     │
                   │ • Batch         │
                   │   Processing    │
                   │ • Error         │
                   │   Handling      │
                   └─────────────────┘
```

## Features

### ✅ Core Functionality
- **Automated Email Processing**: Monitors Databricks for pending emails every 5 minutes
- **Azure Integration**: Full integration with Azure Communication Services and Blob Storage
- **Enterprise Logging**: Comprehensive audit trail and error logging
- **Batch Processing**: Efficient processing of multiple emails in batches
- **Error Handling**: Robust error handling with retry logic and failure tracking

### ✅ Email Management
- **Template Loading**: Loads email templates from Azure Blob Storage
- **Contact Management**: Extracts recipient information from research data
- **Content Processing**: Handles HTML email content with proper formatting
- **Subject Line Extraction**: Automatically extracts subject lines from metadata

### ✅ Database Integration
- **Unified Table Design**: Single table for workflow and email audit tracking
- **Status Tracking**: Comprehensive tracking of email processing status
- **Performance Analytics**: Built-in reporting and statistics
- **Databricks Optimization**: Delta table format with auto-optimization

## Quick Start

### 1. Installation

```bash
# Clone or copy the SendEmail folder
cd SendEmail

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

Required environment variables:
```bash
# Azure Communication Services
ACS_CONNECTION_STRING=endpoint=https://your-acs.communication.azure.com/;accesskey=your-key
ACS_SENDER_EMAIL=noreply@your-domain.com

# Azure Blob Storage (choose one authentication method)
# Option 1: Connection String
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...

# Option 2: SAS Token (recommended for enhanced security)
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

### 3. Setup Database

```bash
# Create database tables
python main.py setup
```

### 4. Test the System

```bash
# Send test email
python main.py test your-email@example.com

# Check system status
python main.py status
```

### 5. Run Email Processor

```bash
# Run continuously (production mode)
python main.py run

# Process emails once and exit
python main.py process

# Alternative simple runner
python run_email_processor.py          # Continuous
python run_email_processor.py --once   # Single batch
```

## Usage

### Command Line Interface

The main interface provides several commands:

```bash
# Production Operations
python main.py run                      # Run continuous processor
python main.py process                  # Process emails once

# Testing and Diagnostics
python main.py test user@example.com    # Send test email
python main.py status                   # System health check
python main.py stats 7                  # 7-day statistics

# Setup
python main.py setup                    # Create database tables
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

## Data Flow

### 1. Email Request Processing

The system monitors the Databricks table for records where:
- `agent_name = 'communication'`
- `status = 'S'` (Success)
- `is_email_sent IS NULL` (Not yet sent)

### 2. Content Retrieval

For each pending email:
1. **Load Research Data**: Retrieves `{customer_id}_research_output.json` from blob storage
2. **Extract Contact Info**: Gets primary contact email from `contact_list[0].email`
3. **Load Email Content**: Retrieves `{customer_id}_email.html` from blob storage
4. **Extract Subject**: Uses `sample_email_subject` from research data

### 3. Email Delivery

1. **Format Email**: Prepares HTML content and subject line
2. **Send via ACS**: Uses Azure Communication Services for delivery
3. **Update Database**: Records success/failure status in Databricks
4. **Audit Trail**: Maintains complete delivery audit log

## Blob Storage Structure

Expected blob storage organization:
```
lowtouch/
└── 20200707/                           # Date folder
    └── 10016125/                       # Customer ID folder
        └── communication_output/       # Communication folder
            ├── 10016125_research_output.json   # Contact and subject data
            └── 10016125_email.html             # Email content
```

## Database Schema

### Main Table: `email_communication_pipeline`

| Column | Type | Description |
|--------|------|-------------|
| `batch_id` | INT | Batch identifier |
| `customer_id` | STRING | Customer identifier |
| `agent_name` | STRING | Processing agent name |
| `status` | STRING | Processing status (S/F/P) |
| `is_email_sent` | BOOLEAN | Email delivery status |
| `recipient_email` | STRING | Email recipient |
| `subject` | STRING | Email subject line |
| `send_status` | STRING | Delivery status (sent/failed) |
| `acs_message_id` | STRING | Azure message ID |
| `error_message` | STRING | Error details if failed |

### Views

- **`pending_emails`**: Ready-to-send emails
- **`email_delivery_status`**: Delivery tracking
- **`email_processing_stats`**: Performance analytics

## Error Handling

### Retry Logic
- Failed emails are marked as `send_status = 'failed'`
- No automatic retries (prevents infinite loops)
- Manual reprocessing requires resetting `is_email_sent` to NULL

### Error Categories
1. **Configuration Errors**: Missing credentials, invalid settings
2. **Blob Storage Errors**: File not found, access denied
3. **Email Delivery Errors**: Invalid recipients, ACS failures
4. **Database Errors**: Connection issues, constraint violations

### Logging
- **INFO**: Normal operations, processing statistics
- **WARNING**: Recoverable issues, domain warnings
- **ERROR**: Failed operations, system errors
- **DEBUG**: Detailed processing information

## Monitoring and Analytics

### System Status
```bash
python main.py status
```
Shows:
- Configuration validation
- Service connectivity
- Processing settings

### Processing Statistics
```bash
python main.py stats 30  # Last 30 days
```
Provides:
- Total emails processed
- Success/failure rates
- Processing trends

### Real-time Monitoring
- Application logs provide real-time processing status
- Databricks views enable SQL-based monitoring
- Azure portal provides ACS delivery metrics

## Security Considerations

### Credentials Management
- All sensitive data stored in environment variables
- No credentials in code or configuration files
- **SAS Token Support**: Enhanced security with time-limited, scoped access tokens
- Azure Key Vault integration ready (future enhancement)

### Azure Storage Authentication Options

**Option 1: Connection String**
- Full account access
- Permanent credentials
- Suitable for development environments

**Option 2: SAS Token (Recommended)**
- Time-limited access (configurable expiration)
- Scoped permissions (can limit to specific containers/operations)
- Enhanced security for production environments
- Easy to rotate and revoke

To generate a SAS token:
1. Go to Azure Portal → Storage Account → Shared Access Signature
2. Set appropriate permissions: Read, List (minimum required)
3. Set expiration date
4. Generate token and use in `AZURE_STORAGE_SAS_TOKEN`

### Email Security
- Validates email addresses before sending
- Prevents sending to suppressed domains
- Includes proper email headers and authentication

### Data Protection
- Audit trail maintains data lineage
- Error messages exclude sensitive information
- Secure Azure service-to-service communication

## Performance Optimization

### Database
- Delta table format with auto-optimization
- Strategic indexing on query patterns
- Batch processing for efficiency

### Email Delivery
- Async processing for concurrent operations
- Connection pooling and reuse
- Configurable batch sizes

### Blob Storage
- Efficient path-based file location
- Minimal data transfer
- Connection reuse

## Troubleshooting

### Common Issues

1. **Email Not Sending**
   ```bash
   python main.py test your-email@example.com
   ```
   Check: ACS configuration, domain settings

2. **Blob Access Errors**
   ```bash
   python main.py status
   ```
   Check: Storage connection string, container permissions

3. **Database Connection Issues**
   ```bash
   python main.py status
   ```
   Check: Databricks token, SQL warehouse status

### Debug Mode
```bash
python main.py --log-level DEBUG process
```

### Log Analysis
- Review application logs for detailed error information
- Check Azure portal for service-specific issues
- Monitor Databricks for data processing problems

## Development

### Project Structure
```
SendEmail/
├── config/                 # Configuration management
├── database/               # Databricks integration
├── email/                  # Email processing logic
├── services/               # Core business services
├── main.py                 # Main CLI interface
├── run_email_processor.py  # Simple runner
└── requirements.txt        # Dependencies
```

### Adding Features
1. **New Email Templates**: Update blob processing logic
2. **Additional Integrations**: Extend service classes
3. **Enhanced Analytics**: Add database views and queries
4. **Custom Notifications**: Implement in email service

### Testing
```bash
# Test individual components
python -c "from services.email_service import EmailService; print('Import OK')"

# Test full system
python main.py test your-test-email@example.com

# Process test batch
python main.py process
```

## Production Deployment

### Requirements
- Python 3.8+
- Azure Communication Services resource
- Azure Storage Account with blob container
- Databricks workspace with SQL warehouse
- Network connectivity between services

### Deployment Options
1. **Azure Container Instance**: Containerized deployment
2. **Virtual Machine**: Direct Python execution
3. **Azure Functions**: Serverless processing
4. **Kubernetes**: Scalable container orchestration

### Monitoring
- Application Insights for logging
- Azure Monitor for service health
- Databricks monitoring for data processing
- Custom dashboards for business metrics

---

## Support

For issues and questions:
1. Check logs and status first: `python main.py status`
2. Review troubleshooting section
3. Verify configuration and connectivity
4. Test with simple operations first

The SendEmail system is designed for reliability and ease of maintenance. With proper configuration and monitoring, it provides enterprise-grade email processing capabilities.