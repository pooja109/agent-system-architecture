# Inbox Monitor Utilities Reference

This comprehensive reference document provides detailed technical documentation for all utility scripts in the `agents/inbox_monitor/utils/` folder. These utilities support development, testing, deployment, and maintenance activities for the inbox monitor system.

> **📚 Related Documentation:**
> - **Getting Started:** [Setup Guide](SETUP.md) - Initial installation using setup utilities
> - **Testing Workflows:** [Testing Guide](TESTING.md) - Using test utilities and runners
> - **Services Architecture:** [Services Overview](SERVICES-OVERVIEW.md) - Technical architecture
> - **Operations:** [User Guide](USER_GUIDE.md) - Daily usage patterns
> - **Logging Migration:** [Logging Migration Guide](LOGGING-MIGRATION-GUIDE.md) - Logging system utilities
> - **Troubleshooting:** [Troubleshooting Guide](TROUBLESHOOTING.md) - Utility-related issues
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## Overview

The utilities are organized into several functional categories:

- **Development and Testing**: Scripts for running tests, generating test data, and validating functionality
- **System Setup and Configuration**: Scripts for initializing external services and validating system health
- **Documentation and Examples**: Scripts that demonstrate system usage patterns
- **Content Processing**: Utilities for formatting, validating, and processing email content
- **System Infrastructure**: Core utilities for async cleanup, retry logic, and field validation
- **Logging Framework**: Comprehensive logging system with enterprise-grade capabilities

---

## Development and Testing Utilities

### Test Email Generator
**File**: `test_email_generator.py`  
**Purpose**: Generates comprehensive test emails covering all AI Agent intent scenarios

#### Overview
A sophisticated email generation system that creates 20 unique, realistic test emails designed to test every aspect of the AI Agent intent classification system. This utility is essential for end-to-end testing and validation of email processing workflows.

#### Key Features
- **Comprehensive Intent Coverage**: Generates emails for all 7 supported intent types (POSITIVE, NEGATIVE, SERVICE_INQUIRY, OUT_OF_OFFICE, NO_LONGER_WORKS, EMAIL_INVALID, UNKNOWN)
- **Realistic Email Formatting**: Creates properly formatted HTML emails with realistic business scenarios
- **Azure Communication Services Integration**: Sends emails via ACS with proper threading headers
- **Simulation Mode**: Supports mock mode for testing without sending real emails
- **Template-Based Generation**: Uses structured scenarios with customizable templates

#### Supported Intent Scenarios

##### POSITIVE Responses (6 scenarios)
- Very interested prospects with immediate needs
- Budget-ready customers seeking pricing information  
- Urgent implementation requirements
- Expansion and growth opportunities
- Team-evaluated solutions with stakeholder buy-in
- ROI-focused decision makers

##### SERVICE_INQUIRY Responses (5 scenarios)
- Technical integration questions (AWS Lambda, SAP, APIs)
- Demo and evaluation requests
- Pricing tier inquiries for different company sizes
- Security and compliance requirement discussions
- Implementation timeline and support questions

##### NEGATIVE Responses (4 scenarios)
- Direct "not interested" responses
- Existing solution satisfaction
- Budget constraint limitations
- Timing misalignment scenarios

##### OUT_OF_OFFICE Responses (3 scenarios)
- Vacation notifications with return dates
- Conference attendance with limited access
- Medical leave with alternative contacts

##### NO_LONGER_WORKS Responses (3 scenarios)
- Employee departures with forwarding information
- Internal promotions and role changes
- Department transfers with new contact routing

##### EMAIL_INVALID Responses (2 scenarios)
- Mail daemon bounce notifications
- Domain-level email delivery failures

#### Technical Architecture

**Email Generation Process**:
1. **Scenario Selection**: Chooses from 20 pre-defined business scenarios
2. **Outreach Creation**: Generates personalized outreach emails using business templates
3. **Response Simulation**: Creates realistic customer responses based on intent type
4. **Email Formatting**: Converts to proper HTML with email threading headers
5. **ACS Integration**: Sends via Azure Communication Services with proper metadata

**Email Structure Components**:
- **Threading Headers**: `In-Reply-To`, `References`, `Thread-Topic` for proper email threading
- **HTML Formatting**: Proper HTML structure with inline CSS styling
- **Business Signatures**: Realistic contact signatures with company information
- **Original Message Quoting**: Properly formatted quoted original messages

#### Configuration Requirements

**Environment Variables**:
```bash
# Required
TEST_EMAIL_OVERRIDE=target_email@domain.com        # Where to send test emails
GRAPH_API_MONITORED_EMAIL=inbox@company.com        # Reply-to address

# Azure Communication Services
ACS_CONNECTION_STRING=endpoint=https://...         # ACS connection string
ACS_SENDER_EMAIL=noreply@domain.azurecomm.net     # Verified sender domain
```

#### Usage Examples

**Basic Email Generation**:
```bash
# Generate and send 20 test emails
python utils/test_email_generator.py

# Import as module
from utils.test_email_generator import EmailGenerator
generator = EmailGenerator(acs_connection_string, acs_sender_email)
results = await generator.generate_and_send_test_emails(20)
```

**Simulation Mode** (recommended for development):
```python
# Set simulation mode to avoid sending real emails
simulation_mode = True
acs_connection_string = "mock-connection-string" if simulation_mode else actual_connection
```

#### Output and Reporting

**Generation Statistics**:
- Total emails generated and sent
- Intent distribution breakdown
- Success/failure rates by scenario
- Performance metrics and timing data

**Email Distribution Example**:
- POSITIVE: 6 emails (30%)
- SERVICE_INQUIRY: 5 emails (25%) 
- NEGATIVE: 4 emails (20%)
- OUT_OF_OFFICE: 3 emails (15%)
- NO_LONGER_WORKS: 3 emails (15%)
- EMAIL_INVALID: 2 emails (10%)

#### Integration with Testing Workflow
1. **Pre-Test Setup**: Run email generator to populate test inbox
2. **System Processing**: Execute `python main.py check` to process emails
3. **Validation**: Verify AI classification accuracy and routing logic
4. **Response Testing**: Reply to generated emails to test response workflows

#### Error Handling and Resilience
- **Connection Failures**: Automatic retry with exponential backoff
- **Template Errors**: Fallback to default templates
- **ACS Rate Limiting**: Built-in delays between sends
- **Validation Failures**: Detailed error reporting with scenario context

#### Dependencies
- `azure.communication.email`: Azure Communication Services SDK
- `dotenv`: Environment variable management
- `pathlib`: File system operations
- `asyncio`: Asynchronous processing
- `uuid`: Unique identifier generation

---

### Send Test Emails Utility
**File**: `send_test_emails.py`  
**Purpose**: Simple wrapper script for launching the test email generator

#### Overview
A lightweight wrapper script that provides a convenient command-line interface for the test email generator. Handles initialization, error management, and user feedback for the email generation process.

#### Key Features
- **Simplified Interface**: Single command execution without complex parameters
- **Error Handling**: Graceful handling of interruptions and failures
- **Status Reporting**: Clear feedback on generation progress and results
- **Interrupt Handling**: Proper cleanup on user interruption (Ctrl+C)

#### Usage Examples
```bash
# Run test email generation
python utils/send_test_emails.py

# Direct script execution
cd utilities && ./send_test_emails.py
```

#### Integration Pattern
- Imports and executes `test_email_generator.main()` function
- Provides consistent command-line interface across different environments
- Handles async execution context management

---

### Comprehensive Test Runner
**File**: `run_comprehensive_tests.py`  
**Purpose**: Advanced test execution system with coverage analysis, performance benchmarking, and detailed reporting

#### Overview
A sophisticated test orchestration system that provides enterprise-grade testing capabilities including comprehensive test suite management, code coverage analysis, performance benchmarking, and multi-format reporting.

#### Key Features
- **Multiple Test Suite Support**: Manages various test categories (unit, integration, performance, edge cases)
- **Coverage Analysis**: Comprehensive code coverage reporting with HTML/XML output
- **Performance Benchmarking**: Execution time tracking and performance regression detection
- **Quality Gates**: Automated linting, type checking, and security scanning
- **Multi-Format Reporting**: JSON, CSV, HTML, Markdown export capabilities

#### Test Suite Configuration

**Supported Test Suites**:
1. **Unit Tests** (`test_*.py`, markers: `unit`, timeout: 120s)
   - Individual component testing
   - Mock-based isolated testing
   - Fast execution for CI/CD pipelines

2. **Comprehensive Unit** (`test_comprehensive_unit.py`, timeout: 180s)
   - Extended unit test coverage
   - All public method testing
   - Boundary condition validation

3. **Graph API Comprehensive** (`test_graph_api_comprehensive.py`, timeout: 120s)
   - Microsoft Graph API integration testing
   - Authentication flow validation
   - API response handling verification

4. **Edge Cases** (`test_comprehensive_edge_cases.py`, markers: `edge_case`, timeout: 180s)
   - Boundary condition testing
   - Error condition simulation
   - Resilience validation

5. **Error Conditions** (`test_comprehensive_errors.py`, markers: `error_condition`, timeout: 180s)
   - Failure scenario testing
   - Recovery mechanism validation
   - Error handling verification

6. **Performance Integration** (`test_performance_integration.py`, markers: `performance`, timeout: 300s)
   - Performance regression testing
   - Load testing scenarios
   - Integration performance validation

#### Advanced Features

**Coverage Analysis**:
- **Line Coverage**: Statement execution tracking
- **Branch Coverage**: Conditional logic path analysis
- **Function Coverage**: Function invocation tracking
- **HTML Reports**: Visual coverage reports with highlighting
- **Failure Threshold**: 90% coverage requirement enforcement

**Quality Checks**:
- **Black Formatting**: Code style consistency validation
- **Ruff Linting**: Python code quality analysis
- **MyPy Type Checking**: Static type validation with strict mode
- **Bandit Security**: Security vulnerability scanning

**Performance Monitoring**:
- **Execution Time Tracking**: Per-test and suite-level timing
- **Performance Regression Detection**: Comparison with baseline metrics
- **Resource Usage Monitoring**: Memory and CPU utilization tracking
- **Bottleneck Identification**: Slowest operation identification

#### Command Line Interface

**Basic Usage**:
```bash
# Run all tests with default configuration
python utils/run_comprehensive_tests.py

# Skip coverage analysis for faster execution
python utils/run_comprehensive_tests.py --no-coverage

# Verbose output with detailed logging
python utils/run_comprehensive_tests.py --verbose

# Stop on first failure
python utils/run_comprehensive_tests.py --fail-fast
```

**Advanced Options**:
```bash
# Run specific test suite
python utils/run_comprehensive_tests.py --suite unit_tests

# Skip quality checks (linting, type checking)
python utils/run_comprehensive_tests.py --no-quality

# Custom output directory
python utils/run_comprehensive_tests.py --output-dir /path/to/results

# List available test suites
python utils/run_comprehensive_tests.py --list-suites
```

#### Output Structure

**Test Results Directory** (`test_output/`):
- `{suite_name}_report.json`: Detailed test results per suite
- `test_summary.json`: Comprehensive execution summary
- `combined_coverage.{html,json,xml}`: Coverage analysis results

**Coverage Directory** (`coverage/`):
- `{suite_name}_coverage/`: Individual suite coverage reports
- `combined_coverage/`: Comprehensive coverage analysis

#### CI/CD Integration

**Exit Code Behavior**:
- **0**: All tests pass, coverage >= 90%, quality checks pass
- **1**: Test failures, coverage < 90%, or quality issues

**CI Pipeline Example**:
```bash
# CI execution with fail-fast and quality enforcement
python utils/run_comprehensive_tests.py --fail-fast --verbose

# Check exit code for pipeline control
if [ $? -eq 0 ]; then
    echo "All quality gates passed - proceeding with deployment"
else
    echo "Quality gates failed - blocking deployment"
    exit 1
fi
```

#### Performance Optimization
- **Parallel Suite Execution**: Independent suites run concurrently where possible
- **Selective Coverage**: Individual suite coverage disabled for speed
- **Timeout Management**: Per-suite timeout configuration
- **Resource Monitoring**: Memory usage tracking and optimization

#### Dependencies
- **pytest**: Test framework with extensive plugin ecosystem
- **pytest-cov**: Coverage analysis integration
- **pytest-json-report**: JSON reporting capabilities
- **subprocess**: External tool execution (Black, Ruff, MyPy, Bandit)

---

### Simple Test Runner
**File**: `run_tests.py`  
**Purpose**: Lightweight test execution with basic pytest configuration

#### Overview
A simplified test runner that provides basic test execution capabilities with minimal configuration. Ideal for quick test runs during development and basic CI environments.

#### Key Features
- **Minimal Configuration**: Simple pytest execution with essential options
- **Clean Output**: Disabled warnings for cleaner test output
- **Path Management**: Automatic Python path configuration for imports
- **Exit Code Management**: Proper exit codes for CI/CD integration

#### Configuration Options
- **Verbose Output** (`-v`): Detailed test information
- **Short Traceback** (`--tb=short`): Concise error reporting
- **Warning Suppression** (`-p no:warnings`): Cleaner output display

#### Usage Examples
```bash
# Run all tests
python utils/run_tests.py

# Direct execution
./utils/run_tests.py
```

#### Use Cases
- **Development Testing**: Quick test runs during code development
- **Simple CI**: Basic continuous integration test execution
- **Debugging**: Minimal overhead for focused testing

---

## System Setup and Configuration Utilities

### Databricks Setup Script
**File**: `setup_databricks.py`  
**Purpose**: Comprehensive Databricks infrastructure initialization and validation

#### Overview
A sophisticated setup and validation script that initializes all required Databricks components for the inbox monitor system. This script ensures proper database schema creation, connection validation, and functional testing of the round-robin expert assignment system.

#### Key Responsibilities
- **Database Schema Creation**: Creates expert lead assignment tables with proper schema
- **Connection Validation**: Tests OAuth authentication and database connectivity
- **Expert Pool Verification**: Validates active expert view availability and data integrity
- **Round-Robin Testing**: Functional testing of assignment algorithms
- **Health Monitoring**: Comprehensive system health checks and reporting

#### Setup Process Workflow

**Phase 1: Configuration Validation**
- Loads and validates all configuration settings
- Validates Databricks OAuth credentials
- Verifies connection parameters and permissions

**Phase 2: Connection Testing**
- Establishes OAuth-authenticated Databricks connection
- Tests query execution capabilities
- Validates warehouse access and permissions

**Phase 3: Database Schema Setup**
- Creates `expert_lead_assignments` table with comprehensive schema
- Configures proper indexing and constraints
- Validates table structure and permissions

**Phase 4: Expert Pool Validation**
- Verifies `active_rep_pool_v` view exists and is accessible
- Validates expert data completeness (names, emails, active status)
- Reports expert availability and distribution

**Phase 5: Functional Testing**
- Executes test lead assignment using round-robin algorithm
- Validates assignment record creation and retrieval
- Tests assignment status updates and tracking

**Phase 6: Statistics and Reporting**
- Generates assignment statistics and expert distribution
- Provides system readiness assessment
- Reports performance metrics and recommendations

#### Database Schema Details

**Expert Lead Assignments Table**:
```sql
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.expert_lead_assignments{suffix} (
    assignment_id STRING PRIMARY KEY,
    expert_id STRING NOT NULL,
    expert_email STRING NOT NULL,
    expert_name STRING NOT NULL,
    customer_email STRING NOT NULL,
    lead_status STRING DEFAULT 'assigned',
    assignment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_assignment_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assignment_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Table Features**:
- **Primary Key**: Unique assignment tracking via `assignment_id`
- **Expert Tracking**: Complete expert information (ID, email, name)
- **Status Management**: Assignment status tracking with timestamps
- **Round-Robin Support**: Assignment count and timestamp for algorithm
- **Audit Trail**: Creation and update timestamp tracking

#### Expert Pool Integration

**Active Rep Pool View Requirements**:
- **View Name**: `active_rep_pool_v`
- **Required Columns**: 
  - `expert_id`: Unique expert identifier
  - `expert_email`: Expert contact email
  - `expert_name`: Display name
  - `is_active`: Boolean active status (ISACTIVE column)

**Validation Process**:
1. View existence and accessibility verification
2. Required column presence validation
3. Active expert count and distribution analysis
4. Data quality assessment (email format, name completeness)

#### Round-Robin Algorithm Testing

**Test Assignment Process**:
1. **Test Customer**: Uses `test.customer@example.com` as test subject
2. **Expert Selection**: Executes round-robin algorithm to select expert
3. **Assignment Creation**: Creates assignment record with full metadata
4. **Retrieval Validation**: Tests assignment lookup by customer email
5. **Status Update Testing**: Validates status change to `test_completed`

**Algorithm Validation**:
- Verifies lowest assignment count selection
- Tests timestamp-based tie-breaking
- Validates assignment count increment
- Confirms proper record creation and indexing

#### Configuration Requirements

**Environment Variables**:
```bash
# Databricks Configuration
DATABRICKS_OAUTH_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_OAUTH_CLIENT_ID=your-oauth-client-id
DATABRICKS_OAUTH_CLIENT_SECRET=your-oauth-client-secret
DATABRICKS_OAUTH_TENANT_ID=your-azure-tenant-id

# Database Configuration  
DATABRICKS_CATALOG=your_catalog_name
DATABRICKS_SCHEMA=your_schema_name
DATABRICKS_TABLE_SUFFIX=_production  # or _test, _dev
```

#### Usage Examples

**Standard Setup**:
```bash
# Run complete setup and validation
python utils/setup_databricks.py
```

**Validation Output Example**:
```
🚀 Starting Databricks setup for Inbox Monitor
============================================================
Loading configuration...
✅ Configuration validated
   Environment: production
   Databricks: your-workspace.cloud.databricks.com
   Catalog: your_catalog
   Schema: your_schema
   Table Suffix: _production

✅ Databricks connection validated successfully
✅ Expert lead assignments table created/verified successfully
✅ Found 15 active experts in active_rep_pool_v view
✅ Round-robin assignment test successful
   Assigned to: John Smith (jsmith@company.com)
   Assignment ID: assgn_abc123def456
   Assignment Count: 3

📊 Assignment Statistics:
   Total Assignments: 127
   Active Assignments: 89
   Unique Customers: 45
   Unique Experts: 15

🎉 Databricks setup completed successfully!
```

#### Error Handling and Troubleshooting

**Common Setup Issues**:
1. **Connection Failures**: OAuth credential validation and network connectivity
2. **Permission Issues**: Catalog/schema access rights validation
3. **View Missing**: `active_rep_pool_v` view creation or access issues
4. **Data Quality**: Expert data completeness and format validation

**Diagnostic Information**:
- Detailed error messages with resolution guidance
- Connection parameter validation and suggestions
- Permission requirement documentation
- Database object status reporting

#### Integration with System Workflow
1. **Pre-Deployment**: Run setup script before system deployment
2. **Health Checks**: Periodic validation of database health
3. **Expert Management**: Validation of expert pool changes
4. **Performance Monitoring**: Assignment distribution analysis

#### Dependencies
- **structlog**: Structured logging for setup process
- **services.round_robin_service**: Round-robin assignment implementation
- **config.settings**: Configuration management and validation
- **asyncio**: Asynchronous operation support

---

### Example Usage Script
**File**: `example_usage.py`  
**Purpose**: Demonstrates system usage patterns and configuration requirements

#### Overview
A comprehensive demonstration script that showcases proper system usage, configuration requirements, and common operational patterns. Serves as both documentation and a quick reference for system setup and operation.

#### Key Features
- **Command Examples**: Demonstrates all major system commands
- **Configuration Documentation**: Complete environment variable reference
- **Azure AD Setup Guide**: Step-by-step Azure app registration process
- **Output Examples**: Shows expected system behavior and output formats

#### System Command Demonstrations

**Status Checking**:
```bash
python main.py status
# Shows: Configuration validation, service health, connectivity status
```

**Connection Testing**:
```bash
python main.py test
# Tests: Graph API authentication, AI service connectivity, database access
```

**Single Inbox Check**:
```bash
python main.py check
# Processes: Current inbox contents, applies AI classification, executes workflows
```

**Continuous Monitoring**:
```bash
python main.py run
# Starts: Continuous email monitoring with configurable polling interval
```

#### Environment Configuration Reference

**Required Environment Variables**:
```bash
# Microsoft Graph API Configuration
GRAPH_API_TENANT_ID=your-azure-tenant-id
GRAPH_API_CLIENT_ID=your-app-client-id  
GRAPH_API_CLIENT_SECRET=your-app-client-secret
GRAPH_API_MONITORED_EMAIL=inbox@yourdomain.com

# Optional Performance and Behavior Configuration
INBOX_MONITOR_POLLING_INTERVAL=300      # Polling frequency in seconds
INBOX_MONITOR_BATCH_SIZE=10             # Email batch processing size
INBOX_MONITOR_DRY_RUN=false            # Enable dry-run mode
INBOX_MONITOR_OUTPUT_TYPE=file         # Output destination (file/console)
INBOX_MONITOR_OUTPUT_DIR=./output      # Output directory path

# Logging Configuration  
LOG_LEVEL=INFO                         # Logging verbosity level
LOG_FORMAT=json                        # Logging format (json/text)
```

#### Azure AD App Registration Guide

**Step-by-Step Setup Process**:
1. **Azure Portal Access**: Navigate to Azure Active Directory > App registrations
2. **Application Creation**: Create new registration with appropriate name
3. **API Permission Configuration**:
   - Microsoft Graph > Application permissions > Mail.ReadWrite
   - Grant admin consent for organization
4. **Client Secret Creation**: Generate client secret with appropriate expiration
5. **Configuration Values**: Record Application ID, Directory ID, and client secret

**Required Permissions**:
- `Mail.ReadWrite`: Application-level permission for inbox access
- `User.Read.All`: Optional for user information lookup
- **Admin Consent**: Required for application-level Graph API access

#### Output Directory Structure
```
./test_output/
├── processed_emails/     # Processed email records
├── classifications/      # AI classification results
├── assignments/         # Expert assignment records
└── logs/               # System operation logs
```

#### Integration Examples
- **Development Setup**: Local environment configuration
- **Production Deployment**: Enterprise configuration patterns
- **Testing Environment**: Safe testing configuration
- **Monitoring Setup**: Operational monitoring configuration

#### Use Cases
- **New Developer Onboarding**: Quick system understanding
- **System Documentation**: Reference for configuration options
- **Troubleshooting Guide**: Common issues and solutions
- **Operations Manual**: Day-to-day operational guidance

---

## Content Processing Utilities

### Content Formatter
**File**: `content_formatter.py`  
**Purpose**: Sophisticated email content processing utility for converting HTML to structured text and extracting conversation context

#### Overview
An advanced email content processing system that handles HTML-to-text conversion, extracts conversation context from reply emails, and creates structured case descriptions for Salesforce integration. This utility is essential for processing customer email responses and maintaining conversation history.

#### Key Features
- **HTML-to-Text Conversion**: Robust HTML parsing with proper handling of email formatting
- **Conversation Context Extraction**: Identifies and separates customer responses from original emails
- **Original Email Recovery**: Extracts original outbound email content from reply threads
- **Signature Information Parsing**: Conservative extraction of customer contact details
- **Structured Case Generation**: Creates formatted case descriptions with metadata
- **Date/Time Processing**: Handles timezone conversion and response time calculation

#### Core Processing Models

**ContentFormattingConfig**: Configuration for content processing behavior
```python
class ContentFormattingConfig(BaseModel):
    content_format: str = "structured"  # raw, clean_text, structured
    max_description_length: int = 5000
    preserve_signature: bool = True
    include_metadata: bool = True
    truncate_html_fallback: bool = True
```

**ConversationContext**: Complete conversation thread information
```python
class ConversationContext(BaseModel):
    customer_response: str              # Customer's new response
    original_email: OriginalEmailContent | None  # Original outbound email
    conversation_id: str | None         # Email thread ID
    thread_references: list[str]        # Email threading headers
    has_conversation_context: bool      # Context extraction success
```

#### Content Processing Workflow

**Phase 1: HTML Content Cleaning**
1. Remove HTML comments, CSS styles, and scripts
2. Convert HTML entities to readable text
3. Replace HTML tags with appropriate formatting
4. Clean up excessive whitespace and normalize structure

**Phase 2: Conversation Context Extraction**
1. Identify reply separators (horizontal rules, forward markers)
2. Separate customer response from original email content
3. Extract original email headers (From, Sent, Subject)
4. Parse original email body content with cleanup

**Phase 3: Signature Information Parsing**
1. Conservative extraction from customer response only
2. Identify email addresses, phone numbers, titles
3. Validate against suspicious content patterns
4. Apply corporate naming convention filters

**Phase 4: Structured Case Generation**
1. Combine customer details, response, and original context
2. Calculate response times with timezone handling
3. Format with structured template including metadata
4. Apply length limits with intelligent truncation

#### Usage Examples

**Basic Content Processing**:
```python
from utils.content_formatter import ContentFormatter, ContentFormattingConfig

config = ContentFormattingConfig(
    content_format="structured",
    preserve_signature=True,
    include_metadata=True
)

formatter = ContentFormatter(config)
clean_content = formatter.clean_email_content(email)
```

**Structured Case Description**:
```python
case_description = formatter.create_structured_case_description(
    email=email,
    expert_name="John Smith",
    account_id="0013000001ABC123",
    contact_id="0033000001DEF456"
)
```

#### Advanced Features

**Timezone Handling**:
- Eastern Time (America/New_York) with automatic DST
- UTC conversion for consistent storage
- Response time calculation in business format

**Content Validation**:
- Email format validation with regex patterns
- Corporate name pattern recognition
- Suspicious content filtering to prevent misclassification

**Error Recovery**:
- Fallback to raw HTML when processing fails
- Multiple extraction pattern attempts
- Conservative signature parsing to prevent false positives

#### Dependencies
- `pydantic`: Data validation and modeling
- `structlog`: Structured logging support
- `zoneinfo`: Timezone handling
- `html`: HTML entity processing
- `re`: Regular expression pattern matching

---

### Subject Formatter
**File**: `subject_formatter.py`  
**Purpose**: Standardizes Salesforce case subjects with account name integration

#### Overview
A specialized utility for creating consistent, standardized subject lines for Salesforce Support Request cases. Implements the "AI Agent Led INQUIRY | <Account Name>" format with intelligent fallback handling and validation.

#### Key Features
- **Standardized Format**: Implements "AI Agent Led INQUIRY | <Account Name>" pattern
- **Account Name Integration**: Pulls account names from Salesforce data
- **Intelligent Fallbacks**: Handles missing or invalid account names gracefully
- **Length Validation**: Ensures compliance with Salesforce 255-character limit
- **Content Sanitization**: Removes problematic characters for email compatibility

#### Configuration Options
```python
class SubjectFormatter:
    ai_inquiry_template = "AI Agent Led INQUIRY | {account_name}"
    fallback_template = "AI Agent Led INQUIRY | {fallback_name}"
    max_subject_length = 255  # Salesforce limit
```

#### Processing Logic

**Account Name Cleaning**:
1. Remove common prefixes (Account:, Company:, Organization:)
2. Normalize whitespace and remove problematic characters
3. Apply reasonable length limits (100 characters max)
4. Validate minimum content requirements

**Fallback Strategy**:
1. Extract company indicators from original subject
2. Use first few words as context if available
3. Default to "Customer Inquiry" as final fallback

#### Usage Examples
```python
from utils.subject_formatter import SubjectFormatter

formatter = SubjectFormatter()

# Standard usage with account name
subject = formatter.format_ai_inquiry_subject(
    account_name="Acme Corporation",
    original_subject="Question about automation services"
)
# Result: "AI Agent Led INQUIRY | Acme Corporation"

# Fallback handling for missing account
subject = formatter.format_ai_inquiry_subject(
    account_name="",
    original_subject="Interested in your solutions"
)
# Result: "AI Agent Led INQUIRY | Customer Inquiry"
```

#### Integration Points
- **Salesforce Case Creation**: Provides standardized subjects for cases
- **Email Processing**: Maintains consistent subject formatting
- **Account Management**: Integrates with contact lookup services

---

### Salesforce Field Validator
**File**: `salesforce_field_validator.py`  
**Purpose**: Validates and corrects Salesforce field values with fallback strategies

#### Overview
A validation utility that ensures Salesforce Support Request fields meet picklist requirements and business rules. Provides intelligent fallback values when field validation fails, preventing case creation errors in production environments.

#### Key Features
- **Picklist Validation**: Validates against common Salesforce picklist values
- **Fallback Strategies**: Provides reasonable default values for failed validations
- **Field Configuration**: Configurable validation rules and required values
- **Error Recovery**: Graceful handling of validation failures
- **Detailed Reporting**: Comprehensive validation result reporting

#### Field Configuration
```python
field_configurations = {
    'Type': {
        'required_value': 'Digital Outreach',
        'fallback_values': ['Other', 'Email', 'Phone', 'Web'],
        'is_required': True
    },
    'Status': {
        'required_value': 'Assigned',
        'fallback_values': ['New', 'Open', 'In Progress', 'Working'],
        'is_required': True
    },
    'Request_Case_Category__c': {
        'required_value': 'AI Agent',
        'fallback_values': ['General', 'Technical', 'Support', 'Other'],
        'is_required': False
    }
}
```

#### Validation Process
1. **Field Value Assessment**: Evaluates provided values against expected formats
2. **Requirement Checking**: Validates required vs optional field compliance
3. **Fallback Application**: Applies appropriate fallback values for invalid data
4. **Result Compilation**: Creates detailed validation reports with corrections

#### Usage Examples
```python
from utils.salesforce_field_validator import SalesforceFieldValidator

validator = SalesforceFieldValidator()

field_values = {
    'Type': 'Custom Type',  # Invalid value
    'Status': 'Assigned',   # Valid value
    # Missing Request_Case_Category__c
}

result = validator.validate_support_request_fields(field_values)

# Access corrected values
corrected_fields = result['corrected_fields']
# Result: {'Type': 'Digital Outreach', 'Status': 'Assigned', 'Request_Case_Category__c': 'AI Agent'}
```

#### Validation Results
```python
class FieldValidationResult:
    is_valid: bool              # Whether original value was acceptable
    original_value: Any         # Original provided value
    corrected_value: Any        # Corrected value to use
    used_fallback: bool        # Whether fallback was applied
    validation_message: str     # Description of validation action
```

---

## System Infrastructure Utilities

### Async Cleanup
**File**: `async_cleanup.py`  
**Purpose**: Comprehensive async resource cleanup with connection timeout prevention

#### Overview
A critical infrastructure utility that provides safe cleanup of asynchronous resources without causing connection timeouts or hanging processes. Essential for production deployments and testing environments where proper resource cleanup is crucial.

#### Key Features
- **Task Cleanup**: Safe cancellation and cleanup of pending asyncio tasks
- **Client Closure**: Timeout-protected async client connection closure
- **Warning Suppression**: Comprehensive filtering of network/SSL warnings
- **Graceful Shutdown**: Orchestrated shutdown sequence with resource management
- **Exception Filtering**: Intelligent suppression of non-critical async errors

#### Core Functions

**safe_cleanup_tasks(timeout: float = 5.0)**:
- Identifies and cancels pending asyncio tasks
- Waits for task completion with timeout protection
- Provides detailed logging of cleanup progress

**safe_close_client(client, client_name: str, timeout: float = 2.0)**:
- Safely closes async clients (aclose/close methods)
- Timeout protection prevents hanging connections
- Handles both coroutine and synchronous close methods

**suppress_future_warnings()**:
- Ultra-aggressive warning suppression for production
- Filters network, SSL, and async-related exceptions
- Patches aiohttp and SSL modules to prevent hanging
- Sets up comprehensive exception hooks

#### Warning Suppression Categories
- **Network Exceptions**: Connection errors, timeouts, SSL issues
- **Async Warnings**: Future exceptions, unclosed sessions, connectors
- **Library Noise**: aiohttp, asyncio, urllib3, Azure SDK warnings
- **SSL/TLS Issues**: Certificate problems, handshake failures

#### Usage Examples
```python
from utils.async_cleanup import graceful_shutdown, safe_close_client, suppress_future_warnings

# Enable warning suppression for production
suppress_future_warnings()

# Clean up async client
async def cleanup_services():
    await safe_close_client(http_client, "HTTP Client")
    await graceful_shutdown(timeout=10.0)

# Production shutdown sequence
try:
    await service_operations()
finally:
    await graceful_shutdown()
```

#### Production Integration
- **CI/CD Pipelines**: Prevents hanging test runs
- **Container Deployments**: Clean container shutdown
- **Service Orchestration**: Graceful service termination
- **Development Testing**: Clean test environment shutdown

---

### Retry Utilities
**File**: `retry.py`  
**Purpose**: Robust retry logic implementation with exponential backoff

#### Overview
A comprehensive retry system that provides resilient operation execution with configurable backoff strategies. Essential for handling transient failures in distributed systems and external service integrations.

#### Key Features
- **Exponential Backoff**: Configurable delay multiplication between retries
- **Exception Filtering**: Selective retry based on exception types
- **Test Mode Optimization**: Reduced delays for testing environments
- **Decorator Pattern**: Easy application to async functions
- **Comprehensive Logging**: Detailed retry attempt tracking

#### Core Components

**retry_with_backoff Decorator**:
```python
@retry_with_backoff(
    max_attempts=3,
    delay_seconds=30,
    backoff_factor=2.0,
    exceptions=(ConnectionError, TimeoutError)
)
async def external_api_call():
    # Function implementation
    pass
```

**retry_operation Function**:
```python
success, result, error = await retry_operation(
    operation=api_call_function,
    operation_name="Salesforce API Call",
    max_attempts=3,
    delay_seconds=30,
    *args, **kwargs
)
```

#### Configuration Options
- **max_attempts**: Maximum retry attempts (default: 3)
- **delay_seconds**: Initial delay between retries (default: 30)
- **backoff_factor**: Delay multiplication factor (default: 2.0)
- **exceptions**: Tuple of exception types to catch and retry

#### Smart Test Mode
- Automatically detects test environments (TEST_MODE, PYTEST_CURRENT_TEST)
- Uses minimal delays (0.1s, 0.01s) to speed up testing
- Maintains same retry logic without production delays

#### Usage Patterns
```python
# Service integration with retry
@retry_with_backoff(max_attempts=3, delay_seconds=30)
async def salesforce_create_case(case_data):
    async with self.client.post('/cases', json=case_data) as response:
        if response.status != 201:
            raise ConnectionError(f"API error: {response.status}")
        return await response.json()

# Direct retry operation
async def robust_database_query():
    success, result, error = await retry_operation(
        operation=database_client.execute_query,
        operation_name="Database Query",
        max_attempts=3,
        query="SELECT * FROM contacts"
    )
    if not success:
        logger.error(f"Database query failed: {error}")
        raise DatabaseError(error)
    return result
```

---

## Logging Framework

### Enterprise Logger
**File**: `utils/logging/enterprise_logger.py`  
**Purpose**: Intelligent enterprise-grade logging system with noise reduction and performance tracking

#### Overview
A sophisticated logging framework designed for enterprise environments, providing intelligent noise reduction, performance monitoring, and categorized logging capabilities. Optimized for production deployments with comprehensive observability features.

#### Key Features
- **Intelligent Filtering**: Category-based noise reduction for cleaner logs
- **Performance Tracking**: Built-in operation timing and metrics collection
- **Enterprise Categories**: Structured logging categories (SYSTEM, PERFORMANCE, SECURITY, etc.)
- **Configurable Suppression**: Template and debug log suppression in production
- **Context Management**: Performance timing context managers
- **Metrics Collection**: Automatic performance metrics aggregation

#### Log Categories
```python
class LogCategory(Enum):
    SYSTEM = "system"           # Core system operations
    PERFORMANCE = "performance" # Performance metrics
    SECURITY = "security"       # Security events
    BUSINESS = "business"       # Business logic
    INTEGRATION = "integration" # External service calls
    TEMPLATE = "template"       # Template processing (noisy)
    DATABASE = "database"       # Database operations
    NETWORK = "network"         # Network operations
```

#### Configuration Options
```python
@dataclass
class EnterpriseLogConfig:
    level: LogLevel = LogLevel.INFO
    quiet_mode: bool = False
    performance_tracking: bool = True
    noise_reduction: bool = True
    excluded_categories: Set[LogCategory] = {LogCategory.TEMPLATE}
    metrics_collection: bool = True
```

#### Usage Examples
```python
from utils.logging.enterprise_logger import get_enterprise_logger, create_enterprise_config

# Create enterprise logger
config = create_enterprise_config(quiet_mode=False, level="INFO")
logger = get_enterprise_logger("EmailProcessor", config)

# Log different event types
logger.log_system_event("Service started", level=LogLevel.INFO)
logger.log_business_event("Customer response processed", customer_id="12345")
logger.log_integration_event("Salesforce", "CreateCase", success=True, duration_ms=250.5)

# Performance timing
with logger.performance_timer("Email Processing"):
    # Process email operations
    process_customer_email()

# Collect metrics
metrics = logger.get_metrics()
```

### Logging Configuration
**File**: `utils/logging/config.py`  
**Purpose**: Comprehensive configuration system for dual-stream logging architecture

#### Overview
A complete configuration framework supporting console, structured, and file logging outputs. Provides environment-aware settings, validation, and flexible formatting options for different deployment scenarios.

#### Configuration Models

**LogLevel Enumeration**:
- CRITICAL, ERROR, WARNING, INFO, DEBUG levels
- Direct mapping to Python logging constants
- Environment-appropriate level selection

**OutputFormat Options**:
- CLEAN: Human-friendly console output with icons and colors
- JSON: Structured JSON output for log aggregation
- DETAILED: Verbose diagnostic output with metadata
- MINIMAL: Essential output only for production
- TABLE, TREE, COMPACT: Specialized formatting options

#### Handler Configurations

**ConsoleConfig**: User-friendly terminal output
```python
class ConsoleConfig(BaseModel):
    enabled: bool = True
    level: LogLevel = LogLevel.INFO
    format: OutputFormat = OutputFormat.CLEAN
    color_enabled: bool = True
    timestamp_enabled: bool = False
    show_logger_name: bool = False
```

**StructuredConfig**: Production JSON logging
```python
class StructuredConfig(BaseModel):
    enabled: bool = True
    level: LogLevel = LogLevel.DEBUG
    format: str = "json"
    include_timestamp: bool = True
    include_logger_name: bool = True
    include_thread_info: bool = False
    include_process_info: bool = False
```

**FileConfig**: Optional file-based logging
```python
class FileConfig(BaseModel):
    enabled: bool = False
    file_path: Optional[Path] = None
    level: LogLevel = LogLevel.DEBUG
    max_size_mb: int = 100
    backup_count: int = 5
    rotation_enabled: bool = True
```

### Console Handler
**File**: `utils/logging/console_handler.py`  
**Purpose**: Advanced console output handler with color support and multiple format options

#### Overview
A sophisticated console logging handler that provides clean, user-friendly terminal output with ANSI color support, customizable formatting, and intelligent fallback mechanisms.

#### Key Features
- **ANSI Color Support**: Level-specific colors with terminal detection
- **Multiple Formats**: Clean, minimal, detailed output options
- **Icon Integration**: Visual indicators for different log levels
- **Thread Safety**: Safe concurrent logging from multiple threads
- **Graceful Degradation**: Fallback formatting when errors occur
- **Terminal Detection**: Automatic color disabling for non-TTY outputs

#### Format Implementations

**Clean Format** (default):
- Icons for log levels (🔍 DEBUG, ℹ️ INFO, ⚠️ WARNING, ❌ ERROR, 🚨 CRITICAL)
- Optional timestamps and logger names
- Color-coded messages with automatic TTY detection
- Concise, readable output for development

**Minimal Format**:
- Message content only
- No metadata, timestamps, or formatting
- Ideal for scripting and automated processing

**Detailed Format**:
- Complete diagnostic information
- Timestamps with milliseconds
- File names and line numbers
- Exception traceback integration
- Full metadata for debugging

#### Color Scheme
```python
LEVEL_COLORS = {
    logging.DEBUG: ColorCodes.CYAN,
    logging.INFO: ColorCodes.GREEN,
    logging.WARNING: ColorCodes.YELLOW,
    logging.ERROR: ColorCodes.RED,
    logging.CRITICAL: ColorCodes.BRIGHT_RED + ColorCodes.BOLD,
}
```

---

## Usage Patterns and Best Practices

### Development Workflow
1. **Environment Setup**: Use `example_usage.py` for configuration reference
2. **Database Initialization**: Run `setup_databricks.py` to prepare infrastructure  
3. **Test Data Generation**: Execute `test_email_generator.py` to create test emails
4. **System Testing**: Use `run_comprehensive_tests.py` for thorough validation
5. **Functional Testing**: Run simple tests with `run_tests.py` for quick feedback

### Production Deployment
1. **Infrastructure Validation**: Execute `setup_databricks.py` to verify database setup
2. **Health Monitoring**: Implement regular health checks using setup script validation
3. **Performance Monitoring**: Use comprehensive test runner for performance benchmarking
4. **Quality Assurance**: Implement continuous testing with comprehensive test suite

### Testing Strategy
1. **Unit Testing**: Use simple test runner for rapid development feedback
2. **Integration Testing**: Use comprehensive test runner for full system validation
3. **End-to-End Testing**: Generate test emails and process through full workflow
4. **Performance Testing**: Regular comprehensive test runs with performance tracking

### Maintenance Operations
1. **Database Health**: Periodic setup script execution for health validation
2. **Test Coverage**: Regular comprehensive test execution for coverage analysis  
3. **Performance Monitoring**: Ongoing performance benchmarking and regression detection
4. **Quality Gates**: Continuous quality checking with linting and security scanning

---

## Integration with CI/CD Pipelines

### Pre-Deployment Validation
```bash
# Infrastructure setup validation
python utils/setup_databricks.py

# Comprehensive testing with quality gates
python utils/run_comprehensive_tests.py --fail-fast

# Generate test data for system validation
python utils/test_email_generator.py
```

### Continuous Integration
```bash
# Fast feedback loop for development
python utils/run_tests.py

# Coverage and quality validation
python utils/run_comprehensive_tests.py --no-quality --coverage
```

### Production Readiness
```bash
# Full system validation
python utils/run_comprehensive_tests.py --verbose
python utils/setup_databricks.py
python utils/example_usage.py  # Configuration validation
```

---

## Troubleshooting and Support

### Common Issues

#### Test Execution Problems
- **Import Errors**: Verify Python path configuration and module availability
- **Database Connection**: Validate Databricks OAuth credentials and network access
- **Permission Errors**: Check file system permissions for output directories

#### Email Generation Issues  
- **ACS Configuration**: Verify Azure Communication Services connection string
- **Authentication**: Validate sender domain registration and verification
- **Rate Limiting**: Implement delays between email sends to avoid throttling

#### Setup Script Problems
- **Database Permissions**: Verify catalog and schema access permissions
- **Expert View Missing**: Ensure `active_rep_pool_v` view exists and is accessible
- **OAuth Authentication**: Validate Databricks OAuth configuration and tokens

### Performance Optimization
- **Test Parallelization**: Use test suite-level parallelization for faster execution
- **Database Connection Pooling**: Configure appropriate connection pool sizes
- **Email Batch Processing**: Optimize batch sizes for email generation and processing

### Security Considerations
- **Credential Management**: Use environment variables and secure secret management
- **Email Content**: Sanitize generated email content to prevent security issues
- **Database Access**: Implement least-privilege access patterns for database operations

---

## Complete Utilities Index

### Development and Testing Utilities
- `test_email_generator.py` - Comprehensive test email generation for all intent scenarios
- `send_test_emails.py` - Simple wrapper for test email generation
- `run_comprehensive_tests.py` - Advanced test runner with coverage and quality gates
- `run_tests.py` - Lightweight pytest runner for development

### System Setup and Configuration
- `setup_databricks.py` - Complete Databricks infrastructure initialization
- `example_usage.py` - System usage demonstrations and configuration guide

### Content Processing Utilities
- `content_formatter.py` - Advanced email content processing and case description generation
- `subject_formatter.py` - Standardized Salesforce case subject formatting
- `salesforce_field_validator.py` - Field validation with fallback strategies

### System Infrastructure Utilities
- `async_cleanup.py` - Comprehensive async resource cleanup and warning suppression
- `retry.py` - Robust retry logic with exponential backoff

### Logging Framework (`utils/logging/`)
- `enterprise_logger.py` - Enterprise-grade logging with noise reduction
- `config.py` - Comprehensive logging configuration system
- `console_handler.py` - Advanced console output with color support
- `structured_handler.py` - JSON structured logging for production
- `logger_factory.py` - Centralized logger factory and management
- `correlation.py` - Request correlation and tracing utilities
- `exceptions.py` - Logging-specific exception classes
- `sensitive_data_filter.py` - Automatic PII filtering for logs
- `http_client_config.py` - HTTP request/response logging configuration
- `message_formatter.py` - Message formatting utilities
- `service_integration.py` - Service-specific logging integration

---

This utilities reference provides comprehensive technical documentation for all utility scripts, enabling effective system development, testing, and maintenance operations. Each utility serves specific operational needs while integrating seamlessly with the overall inbox monitor system architecture.