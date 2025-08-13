# Inbox Monitor - Intelligent Email Response System

## 📖 Quick Navigation

**New to Inbox Monitor?** Start here:
- [⚡ Setup Guide](docs/SETUP.md) - Get Inbox Monitor running in 30 minutes
- [⚙️ Configuration Guide](docs/CONFIGURATION.md) - Environment setup and authentication
- [📋 Scenarios Guide](docs/SCENARIOS.md) - Understanding AI email classification and business actions
- [🧪 Testing Guide](docs/TESTING.md) - Complete test execution guide
- [🔧 Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions

**Complete Documentation:**
- [📚 Documentation Hub](docs/README.md) - Organized guide to all documentation
- [👤 User Guide](docs/USER_GUIDE.md) - Complete user reference and workflows
- [🎭 Demo Playbook](docs/DEMO_PLAYBOOK.md) - Demo scenarios and presentations
- [🖥️ UI Components Overview](docs/UI_COMPONENTS_OVERVIEW.md) - User interface system guide

**Technical References:**
- [🏗️ Services Overview](docs/SERVICES-OVERVIEW.md) - Complete services architecture
- [🔧 Utilities Reference](docs/UTILS.md) - Comprehensive utilities documentation
- [📝 Logging Migration Guide](docs/LOGGING-MIGRATION-GUIDE.md) - Updated logging system guide

**Working with the complete email automation system?**
- [📧 Email Agent Documentation](../email/README.md) - Outbound email campaign processing
- [📥 Inbox Monitor Documentation](../inbox_monitor/README.md) - Inbound email AI classification

## 🚀 New to Inbox Monitor? Start Here!

**8 Critical Success Factors for Quick Ownership:**

1. **🔐 Azure Key Vault is Your Friend** - All credentials are centrally managed in Azure Key Vault. Never hardcode secrets. The system automatically retrieves OAuth tokens, API keys, and connection strings securely.

2. **🧪 Always Use Test Mode First** - Set `TEST_MODE=true` and `TEST_EMAIL_OVERRIDE=your-email@company.com` when getting started. This routes all outputs safely to your test email instead of production systems.

3. **📊 Monitor the 6 AI Scenarios** - The system classifies emails into 6 business intents (Positive, Negative, Service Inquiry, Out of Office, Email Invalid, No Longer Works). Each triggers different automated actions across Salesforce, Databricks, and email forwarding.

4. **⚡ OAuth Over Everything** - The system uses OAuth service principal authentication for all services (no more personal access tokens). This provides enterprise-grade security and automatic token refresh.

5. **🔄 Connection Pooling Saves Resources** - Databricks connections are pooled for 80-90% performance improvement. The system handles connection lifecycle automatically - just use the services normally.

6. **📈 Health Checks Are Built-In** - Use `python main.py status` for comprehensive health monitoring. The system provides health endpoints at `/health` and `/health/detailed` for operational monitoring.

7. **🎯 Start with Single Email Processing** - Use `python main.py check` to process current inbox contents one time. This is perfect for testing and validation before enabling continuous monitoring with `python main.py run`.

8. **📚 Follow the Documentation Flow** - Go Setup → Configuration → Scenarios → Testing → User Guide. Each document builds on the previous one and cross-references related information.

## Overview

The Inbox Monitor is an advanced AI-powered email processing system that automatically monitors a designated email inbox, classifies incoming customer responses, and takes appropriate actions based on the email content. This system is designed to handle customer outreach responses and route them to the correct teams or update relevant CRM systems.

> **🚀 Phase 4 Complete**: Now includes advanced features like YAML scenario configuration, comprehensive export system (JSON, CSV, HTML, Markdown, Excel), robust error recovery, performance optimization with caching, demo templates, and complete documentation. Ready for production deployment!

## Table of Contents

1. [Quick Navigation](#-quick-navigation) ← **Start Here**
2. [System Architecture](#system-architecture)
3. [Features & Capabilities](#features--capabilities)
4. [Scenario Processing](#scenario-processing)
5. [Installation & Setup](#installation--setup) → See [Setup Guide](docs/SETUP.md)
6. [Configuration](#configuration) → See [Configuration Guide](docs/CONFIGURATION.md)
7. [Usage](#usage)
8. [Test Mode](#test-mode)
9. [Testing Framework](#testing-framework)
10. [Monitoring & Maintenance](#monitoring--maintenance)
11. [Troubleshooting](#troubleshooting) → See [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
12. [API References](#api-references)

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
- **Databricks SQL**: Expert assignment and round-robin management with OAuth authentication
- **Azure Communication Services**: Email sending capabilities
- **Azure Key Vault**: Secure credential management for OAuth
- **Connection Pooling**: Efficient database connection management
- **Structlog**: Structured logging and monitoring

### OAuth Migration Implementation

This system has been migrated from Personal Access Token (PAT) authentication to OAuth service principal authentication for Databricks connectivity. Key improvements include:

- **Enhanced Security**: OAuth service principal authentication replaces PAT tokens
- **Connection Pooling**: 80-90% reduction in connection overhead
- **Health Monitoring**: Comprehensive health check endpoints for operational monitoring
- **Automatic Token Management**: Transparent OAuth token refresh and caching
- **Production Readiness**: Full monitoring, alerting, and troubleshooting capabilities

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

**📋 For detailed scenario documentation with business logic and examples, see the [Scenarios Guide](docs/SCENARIOS.md).**

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
1. Update Salesforce contact's `Is_Email_Invalid__c` field to `true`
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

**🔧 For step-by-step setup instructions, see the [Setup Guide](docs/SETUP.md).**

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

**⚙️ For comprehensive configuration reference, see the [Configuration Guide](docs/CONFIGURATION.md).**

### Environment Variables

Create a `.env` file or set environment variables:

#### Required Core Settings

```bash
# Microsoft Graph API
# Graph API credentials are now retrieved from Azure Key Vault
# Required Key Vault secrets:
# - graph-api-tenant-id
# - graph-api-client-id  
# - graph-api-client-secret
GRAPH_API_MONITORED_EMAIL=inbox@yourcompany.com

# Azure AI Foundry
# Azure AI Foundry credentials are now retrieved from Azure Key Vault
# Required Key Vault secrets:
# - azure-ai-foundry-endpoint
# - azure-ai-foundry-tenant-id
# - azure-ai-foundry-client-id
# - azure-ai-foundry-client-secret

# Salesforce
# Salesforce credentials are now retrieved from Azure Key Vault
# Required Key Vault secrets:
# - sf-base-url
# - sf-client-id
# - sf-client-secret
# - sf-token-endpoint
# - sf-api-version
# - sf-case-record-type-id
# - sf-case-queue

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
HEALTH_CHECK_PORT=8080              # Health check server port (default: 8080)
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
curl http://localhost:8080/health

# Get detailed health information
curl http://localhost:8080/health/detailed | jq '.'

# Check readiness for traffic
curl http://localhost:8080/ready
```

### Configuration Validation

The system validates all required configurations on startup. Missing or invalid settings will prevent the application from starting with clear error messages.

## Usage

### Command Line Interface

The Inbox Monitor features a sophisticated, modern CLI with rich formatting, intelligent environment detection, and comprehensive configuration options. The interface automatically adapts to your environment (development, production, containerized) and provides appropriate defaults.

#### Quick Reference

```bash
# Core Commands
python main.py check       # One-time inbox check
python main.py run         # Continuous monitoring
python main.py status      # System health check
python main.py test        # Connection testing
python main.py setup       # Database initialization

# With Options
python main.py --quiet check --limit 5         # Minimal output, 5 emails
python main.py --verbose status --detailed     # Detailed diagnostics
python main.py --debug run --interval 30       # Debug mode, 30s interval
python main.py --format json status            # JSON output for scripts
```

### Core Commands

#### 1. Check - One-time Inbox Processing

```bash
python main.py check [options]
```

**Purpose**: Process current inbox emails once and exit - ideal for testing or manual operations.

**Options**:
- `--limit N` - Process only N messages (default: 10)

**Examples**:
```bash
# Standard check with rich formatting
python main.py check

# Quick check with minimal output
python main.py --quiet check --limit 5

# Detailed check with progress indicators
python main.py --verbose check

# JSON output for automation
python main.py --format json check
```

**Sample Output** (Clean Format):
```
╭──────────────────────────────────────────────────╮
│  📧 Inbox Monitor v1.0.0                         │
│  AI-powered email monitoring and response system │
╰──────────────────────────────────────────────────╯

  Inbox Check Results   
               ╷        
  📊 Processed │     3  
  ❌ Failed    │     0  
  ⏱️ Duration   │ 2.45s  
  ⚡ Rate      │ 1.2/s  
               ╵        

✅ Processing complete - 3 emails classified and routed
```

#### 2. Run - Continuous Monitoring Service

```bash
python main.py run [options]
```

**Purpose**: Start the continuous email monitoring service for production use.

**Options**:
- `--interval N` - Check interval in seconds (default: 60)

**Examples**:
```bash
# Start monitoring with defaults
python main.py run

# Production monitoring with custom interval
python main.py --environment production run --interval 300

# Development mode with debug output
python main.py --debug run --interval 30

# Monitoring with professional theme
python main.py --theme professional run
```

**Sample Output**:
```
╭──────────────────────────────────────────────────╮
│  📧 Inbox Monitor v1.0.0                         │
│  AI-powered email monitoring and response system │
╰──────────────────────────────────────────────────╯

🚀 Starting Inbox Monitor with Connection Pooling
📧 Monitoring: inbox@yourcompany.com
⏱️  Polling interval: 300 seconds
📁 Output: salesforce
🔧 Connection pool initialized successfully with 2-5 connections
✅ Health check server started on port 8080

Press Ctrl+C to stop...

✅ Processed 3 emails in 2.45 seconds
   📊 Positive responses: 1 (assigned to expert)
   📧 Service inquiries: 1 (forwarded to account team)  
   ❌ Invalid emails: 1 (marked in Salesforce)
```

#### 3. Status - System Health Check

```bash
python main.py status [options]
```

**Purpose**: Display comprehensive system status and component health information.

**Options**:
- `--detailed` - Show full component diagnostics and response times

**Examples**:
```bash
# Standard system status
python main.py status

# Detailed component health
python main.py status --detailed

# Minimal status check
python main.py --quiet status

# JSON status for monitoring
python main.py --format json status
```

**Sample Output** (Standard):
```
╭──────────────────────────────────────────────────╮
│  📧 Inbox Monitor v1.0.0                         │
│  AI-powered email monitoring and response system │
╰──────────────────────────────────────────────────╯

╭───────────────────── System Health ─────────────────────╮
│                                                         │
│  ✅ System Status: 5/5 components healthy               │
│                                                         │
│    ✅ Key Vault: HEALTHY                               │
│    ✅ OAuth Authentication: HEALTHY                    │
│    ✅ Connection Pool: HEALTHY                         │
│    ✅ Database Connectivity: HEALTHY                   │
│    ✅ Service Integration: HEALTHY                     │
│                                                         │
│  💡 Use --detailed for full diagnostic information     │
│                                                         │
╰─────────────────────────────────────────────────────────╯
```

**Sample Output** (Detailed):
```
╭──────────────── System Summary ────────────────╮
│ Overall Status: HEALTHY | Response Time: 12.6s │
╰─────────────────────────────────────────────────╯

              System Component Status               
╭─────────────────┬────────────┬──────────────────╮
│ Component       │   Status   │ Response Time    │
├─────────────────┼────────────┼──────────────────┤
│ Key Vault       │ ✅ HEALTHY │ 11.3s            │
│ OAuth Auth      │ ✅ HEALTHY │ 8.5s             │
│ Connection Pool │ ✅ HEALTHY │ Database conn... │
│ Database        │ ✅ HEALTHY │ 0.5s query time │
│ Services        │ ✅ HEALTHY │ Pool not active  │
╰─────────────────┴────────────┴──────────────────╯
```

#### 4. Test - Connection Verification

```bash
python main.py test [options]
```

**Purpose**: Test Microsoft Graph API connectivity and mailbox access.

**Examples**:
```bash
# Basic connection test
python main.py test

# Verbose connection test
python main.py --verbose test
```

#### 5. Setup - Database Initialization

```bash
python main.py setup [options]
```

**Purpose**: Initialize required Databricks database tables and structure.

**Options**:
- `--force` - Force setup even if tables exist

**Examples**:
```bash
# Initial setup
python main.py setup

# Force recreation of tables
python main.py setup --force
```

### Advanced CLI Features

#### Verbosity Control

Control the amount of output and detail level:

```bash
# Minimal output - only essential results and errors
python main.py --quiet check

# Detailed progress information with rich formatting
python main.py --verbose run

# Full diagnostic output including HTTP requests
python main.py --debug status --detailed
```

#### Output Formats

Choose from multiple output formats for different use cases:

```bash
# Clean, user-friendly output with rich formatting (default)
python main.py --format clean status

# Machine-readable JSON for automation and scripts
python main.py --format json status

# Comprehensive diagnostic output with full details
python main.py --format detailed status

# Minimal essential information only
python main.py --format minimal check

# Tabular data presentation
python main.py --format table status

# Compact single-line format
python main.py --format compact check
```

#### Themes and Styling

Professional themes that adapt to your terminal and use case:

```bash
# Auto-detect appropriate theme (default)
python main.py --theme auto status

# Professional blue theme for business environments
python main.py --theme professional run

# Dark terminal theme for development
python main.py --theme dark check

# Light terminal theme 
python main.py --theme light status

# High contrast for accessibility
python main.py --theme high_contrast status

# Minimal theme with no colors or formatting
python main.py --theme minimal check
```

#### UI Controls

Fine-tune the interface appearance:

```bash
# Disable all colors
python main.py --no-color status

# Use ASCII characters only (no Unicode)
python main.py --no-unicode check

# Disable emoji icons
python main.py --no-emoji run

# Disable progress indicators
python main.py --no-progress check

# Use compact output layout
python main.py --compact status

# Override terminal width for formatting
python main.py --width 120 status
```

#### Environment and Configuration

Control environment detection and configuration:

```bash
# Override automatic environment detection
python main.py --environment production run

# Use custom configuration file
python main.py --config-file config.yaml check

# Dry run mode - show what would be done
python main.py --dry-run check

# Force console logging even in production
python main.py --force-console-logging run

# Disable timestamps in output
python main.py --no-timestamps status

# Show logger names in output
python main.py --show-logger-names check
```

### Usage Patterns

#### Development and Testing

```bash
# Quick development check with minimal output
python main.py --quiet check --limit 3

# Development with detailed progress and debug info
python main.py --debug --theme dark check --detailed

# Test system health with comprehensive diagnostics
python main.py --verbose status --detailed

# Safe testing with dry run
python main.py --dry-run check
```

#### Production Operations

```bash
# Production monitoring with structured logging
python main.py --environment production run

# Production health check for monitoring systems
python main.py --quiet --format json status

# Professional themed status for reports
python main.py --theme professional --format detailed status
```

#### Automation and Scripting

```bash
# JSON output for parsing in scripts
python main.py --quiet --format json check > results.json

# Minimal output for cron jobs
python main.py --format minimal --no-color check

# Machine-readable status for monitoring
python main.py --format json status | jq '.overall_status'
```

### Environment Detection

The CLI automatically detects your environment and applies appropriate defaults:

- **Development**: Clean console output, colored formatting, progress indicators
- **Production**: Structured logging, minimal console output, JSON diagnostics
- **Containerized**: Structured logging only, optimized for log aggregation
- **Testing**: Reduced logging, simplified output, faster execution

You can override detection with `--environment {development|production|testing}`.

### Production Usage

For production deployment, use a process manager like systemd or supervisor with the enhanced CLI options:

**systemd service example** (`/etc/systemd/system/inbox-monitor.service`):
```ini
[Unit]
Description=Inbox Monitor Service
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/path/to/agents/inbox_monitor
ExecStart=/usr/bin/python main.py --environment production run --interval 300
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enhanced production commands**:
```bash
# Enable and start the service
sudo systemctl enable inbox-monitor
sudo systemctl start inbox-monitor

# Check service status with rich formatting
sudo systemctl status inbox-monitor

# Monitor system health
python main.py --environment production status --detailed

# View logs with clean formatting
sudo journalctl -u inbox-monitor -f
```

### Command Reference

#### Global Options (Available for All Commands)

**Verbosity Control**:
- `--quiet, -q` - Minimal output, essential results only
- `--verbose, -v` - Detailed progress with rich formatting  
- `--debug, -d` - Full diagnostic output including HTTP requests
- `--log-level {critical,error,warning,info,debug}` - Specific log level

**Output Formatting**:
- `--format {clean,json,detailed,minimal,table,tree,compact}` - Output format (default: clean)
- `--theme {default,dark,light,minimal,professional,high_contrast,auto}` - Color theme (default: auto)

**UI Controls**:
- `--no-color` - Disable colored output
- `--no-unicode` - Use ASCII characters only
- `--no-emoji` - Disable emoji icons  
- `--no-progress` - Disable progress indicators
- `--compact` - Use compact output layout
- `--width WIDTH` - Override terminal width

**Environment & Configuration**:
- `--environment {development,production,testing}` - Override environment detection
- `--config-file CONFIG_FILE` - Path to configuration file
- `--dry-run` - Show what would be done without executing
- `--force-console-logging` - Force console logging in production
- `--no-timestamps` - Disable timestamps in output
- `--show-logger-names` - Show logger names in output

#### Command-Specific Options

**check command**:
- `--limit N` - Process only N messages (default: 10)

**run command**:
- `--interval N` - Check interval in seconds (default: 60)

**status command**:
- `--detailed` - Show comprehensive component diagnostics

**setup command**:
- `--force` - Force setup even if tables exist

### Getting Help

```bash
# Show main help
python main.py --help

# Show help for specific command
python main.py check --help
python main.py run --help  
python main.py status --help

# Quick command reference
python main.py --help | grep "Available commands" -A 10
```

### Environment-Specific Examples

**Development Environment**:
```bash
# Quick development workflow
python main.py setup                    # One-time setup
python main.py test                     # Verify connections
python main.py --debug check --limit 3  # Test with few emails
python main.py --theme dark run         # Start with dark theme
```

**Production Environment**:
```bash
# Production deployment workflow  
python main.py --environment production status --detailed  # Health check
python main.py --environment production run               # Start monitoring
python main.py --quiet --format json status              # Monitoring status
```

**CI/CD and Automation**:
```bash
# Automated testing and deployment
python main.py --format json test > test_results.json
python main.py --quiet check --limit 1 || exit 1
python main.py --format minimal status | grep "HEALTHY"
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

#### ⚡ **NEW: Advanced Test Runner CLI** (Recommended)

The system includes a comprehensive test runner with advanced features for development productivity and CI/CD integration:

```bash
# Quick feedback for development (< 2 minutes)
python test_runner.py --fast

# Complete test suite excluding slow tests (< 8 minutes)  
python test_runner.py --all-except-slow

# Critical path validation (< 1 minute)
python test_runner.py --smoke

# Full test suite including slow tests (15+ minutes)
python test_runner.py --full

# Integration tests with mocked services (< 5 minutes)
python test_runner.py --integration

# Edge case testing (< 3 minutes)
python test_runner.py --edge-cases
```

#### Advanced Test Runner Features

**Configuration Profiles:**
```bash
# Use predefined development profile
python test_runner.py --profile fast-dev

# Use CI pull request profile
python test_runner.py --profile ci-pull-request

# List all available profiles
python test_runner.py --list-profiles
```

**Reporting and Analysis:**
```bash
# Generate HTML report with comprehensive analytics
python test_runner.py --fast --generate-report html

# Export results in multiple formats
python test_runner.py --smoke --export-formats json csv html

# Run analysis with insights and recommendations
python test_runner.py --integration --analyze

# Show performance trends over time
python test_runner.py --trends
```

**Advanced Development Features:**
```bash
# Watch mode - continuous testing with file monitoring
python test_runner.py --fast --watch

# Performance benchmarking with regression detection
python test_runner.py --smoke --benchmark

# Code coverage with detailed reports
python test_runner.py --fast --coverage --coverage-report html

# Custom test filtering with pytest markers
python test_runner.py --custom "fast and azure and not slow"
```

**CI/CD Integration:**
```bash
# Optimize for GitHub Actions
python test_runner.py --all-except-slow --ci-mode github

# Optimize for Azure DevOps
python test_runner.py --smoke --ci-mode azure

# CI-safe mode for automated environments
python test_runner.py --ci-safe
```

**Information Commands:**
```bash
# Show available test markers and their descriptions
python test_runner.py --list-markers

# Show estimated execution time
python test_runner.py --fast --estimate-time

# Show supported export formats
python test_runner.py --supported-formats

# Preview what would be executed without running
python test_runner.py --integration --dry-run
```

#### Traditional pytest Commands (Still Supported)

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
- **Usage**: Tests the Is_Email_Invalid__c field update with boolean values
- **Note**: Demonstrates the updated boolean field approach for invalid emails

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
2. Check contacts with `Is_Email_Invalid__c` field updates
3. Review any test assignments created

**Databricks**:
1. Query assignment tables for test identifiers
2. Check for test assignment records
3. Verify test data doesn't affect production metrics

## Monitoring & Maintenance

### Logging

The system uses a dual-stream structured logging architecture with configurable levels:

```python
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Dual streams: Clean console output + structured JSON logging

# Example structured log entry
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

**🔧 For comprehensive troubleshooting procedures, see the [Troubleshooting Guide](docs/TROUBLESHOOTING.md).**

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
- `Key Vault authentication failed`: Missing or invalid Azure Key Vault configuration
- `Graph API credentials not found in Key Vault`: Missing required Graph API secrets in Key Vault
- `Azure AI Foundry credentials not found in Key Vault`: Missing required AI Foundry secrets in Key Vault
- `Salesforce credentials not found in Key Vault`: Missing required Salesforce secrets in Key Vault
- `target_salesforce_email is required when test mode is enabled`: Test mode configuration incomplete

#### Service Errors
- `Failed to classify email intent`: AI service unavailable or misconfigured
- `Failed to create Salesforce case`: Salesforce API or permission issues
- `No available experts for assignment`: Empty or inactive expert pool

#### Processing Errors
- `Contact not found in lookup table`: Customer not in Databricks database
- `Is_Email_Invalid__c field update errors`: Salesforce boolean field update issues
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

### Main Application CLI

```bash
# Basic Commands
python main.py check                    # One-time inbox processing
python main.py run                      # Continuous monitoring service
python main.py status                   # System health check  
python main.py test                     # Connection verification
python main.py setup                    # Database initialization

# Enhanced Usage with Options
python main.py --quiet check --limit 5                 # Minimal output
python main.py --verbose status --detailed             # Rich diagnostics
python main.py --debug run --interval 30               # Full debug mode
python main.py --format json status                    # JSON output
python main.py --theme professional run                # Themed interface
python main.py --environment production run            # Production mode
python main.py --dry-run check                        # Safe testing
```

### CLI Integration Examples

```bash
# Development workflow
python main.py setup && \
python main.py test && \
python main.py --debug check --limit 3

# Production health monitoring
python main.py --quiet --format json status | \
jq '.overall_status' | \
grep -q "HEALTHY" && echo "Service OK" || echo "Service Issue"

# Automated deployment verification  
python main.py --environment production status --detailed && \
python main.py --quiet check --limit 1
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
        is_email_invalid=True
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

### Testing and Validation
- [ ] Get familiar with CLI: `python main.py --help`
- [ ] Validate configuration: `python main.py status --detailed`
- [ ] Test connections: `python main.py --verbose test`
- [ ] Configure test mode for safe testing
- [ ] Test basic functionality: `python main.py --debug check --limit 1`
- [ ] Run unit tests: `pytest`
- [ ] Run integration tests (with caution)

### Production Deployment
- [ ] Verify production readiness: `python main.py --environment production status`
- [ ] Disable test mode (`TEST_MODE=false`)
- [ ] Set up enhanced systemd service with CLI options
- [ ] Configure structured logging and monitoring
- [ ] Set up health check alerts using `/health` endpoints
- [ ] Test production deployment: `python main.py --environment production --quiet check --limit 1`
- [ ] Document operational procedures with CLI examples

### Development Workflow
- [ ] Use development theme: `python main.py --theme dark status`
- [ ] Enable debug mode for troubleshooting: `python main.py --debug check`
- [ ] Use quiet mode for automation: `python main.py --quiet --format json status`
- [ ] Test with dry run: `python main.py --dry-run check`

### Ongoing Maintenance
- [ ] Monitor processing metrics and error rates
- [ ] Review AI classification accuracy weekly
- [ ] Update expert assignments monthly
- [ ] Conduct quarterly system reviews

---

*This system represents a sophisticated integration of multiple cloud services to provide intelligent, automated email response handling. Proper configuration and testing are essential for reliable operation.*