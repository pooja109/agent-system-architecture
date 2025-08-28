# Comprehensive Table Schema Documentation
## mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev

This document provides an extremely detailed description of the Databricks table schema, field sources, data flow, and cross-process integration for the scenario tracking system.

## Table Overview

**Table Name**: `mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev`  
**Type**: Delta Lake table with Unity Catalog  
**Partitioning**: Date-based partitioning on `processing_date` (derived from `processed_at`)  
**Primary Key**: `process_id`  
**Purpose**: Comprehensive tracking of inbox monitor email scenario processing for business intelligence and analytics

## Complete Field Schema

### Primary Identifiers

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `process_id` | STRING | `ScenarioProcessingRecord.from_processing_results()` line 610 | Unique processing identifier generated from `processing_result.process_id` or UUID if not available |
| `email_id` | STRING | `email_data.id` via `ScenarioProcessingRecord.from_processing_results()` line 612 | Microsoft Graph email message ID from the original email object |
| `conversation_id` | STRING | `email_data.conversation_id` line 613 | Email thread/conversation identifier for grouping related messages |
| `correlation_id` | STRING | Optional parameter in `from_processing_results()` | Cross-service correlation ID for tracking processing across multiple systems |

### Email Source Information (PII Data)

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `sender_email` | STRING | `extract_sender_info(email_data)` via `utils.data_extraction_helpers` line 580-614 | Customer email address extracted from email data, validated and sanitized |
| `sender_name` | STRING | `extract_sender_info(email_data).get('name')` line 615 | Customer display name from email metadata |
| `recipient_emails` | ARRAY\<STRING\> | Complex extraction logic lines 625-670 | List of all recipient email addresses extracted from email.recipients object |
| `subject` | STRING | `email_data.subject` with security sanitization line 616 | Email subject line, truncated to 500 characters and XSS sanitized |
| `received_datetime` | TIMESTAMP | `email_data.received_datetime` line 617 | When the original email was received by the system |
| `sent_datetime` | TIMESTAMP | Fallback logic line 866 | When the original email was sent (defaults to received_datetime if not available) |
| `email_body` | STRING | `email_data.email_body` or `email_data.body` line 860 | First 255 characters of email body content, XSS sanitized |
| `email_importance` | STRING | `EmailImportanceLevel.NORMAL` (default) | Email importance level (low, normal, high) |
| `has_attachments` | BOOLEAN | Default FALSE | Whether the email contains attachments |
| `attachment_count` | INT | `extract_email_metadata()` via `utils.email_metadata_extractor` line 830-842 | Number of attachments in the email |

### Processing Workflow

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `processed_at` | TIMESTAMP | `datetime.now(timezone.utc)` auto-generated | When the scenario processing occurred |
| `processing_duration_ms` | BIGINT | `_extract_real_processing_time()` method line 1176-1214 | Total processing duration extracted from `processing_result.processing_time_breakdown` |
| `process_success` | BOOLEAN | `processing_result.success` line 619 | Whether overall email processing succeeded |
| `process_error` | STRING | `processing_result.error` or validation errors | Error message if processing failed |
| `monitor_version` | STRING | Hardcoded "v2.0.0" line 903 | Version of the inbox monitor system |
| `retry_count` | INT | Default 0 | Number of processing retry attempts |

### AI Classification Results

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `email_intent` | STRING | `intent_result.intent` converted to `AIIntent` enum via email-intent-classifier agent | Email intent classified by email-intent-classifier agent (POSITIVE, NEGATIVE, SERVICE_INQUIRY, etc.) |
| `email_intent_confidence` | DOUBLE | `intent_result.confidence` from email-intent-classifier | Email intent classification confidence score (0.0-1.0) |
| `email_intent_reasoning` | STRING | `intent_result.reasoning` from email-intent-classifier | Email intent classification reasoning |
| `email_intent_detected_phrases` | ARRAY\<STRING\> | `intent_result.detected_phrases` from email-intent-classifier | Key phrases detected by email intent classifier |
| `email_intent_processing_duration_ms` | BIGINT | Processing time from email-intent-classifier agent | Email intent classification processing time in milliseconds |
| `email_intent_model_version` | STRING | Model version from email-intent-classifier agent | Email intent classifier model version |

### Original Subject Extraction Results

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `original_subject_result` | STRING | `original_subject_result.result` from original-subject-extractor agent | Original subject extracted by original-subject-extractor agent |
| `original_subject_confidence` | DOUBLE | `original_subject_result.confidence` from original-subject-extractor | Original subject extraction confidence score (0.0-1.0) |
| `original_subject_reasoning` | STRING | `original_subject_result.reasoning` from original-subject-extractor | Original subject extraction reasoning |
| `original_subject_extraction_method` | STRING | Method used by original-subject-extractor agent | Method used for original subject extraction |
| `original_subject_processing_duration_ms` | BIGINT | Processing time from original-subject-extractor agent | Original subject extraction processing time in milliseconds |
| `original_subject_model_version` | STRING | Model version from original-subject-extractor agent | Original subject extractor model version |

### Scenario Processing

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `scenario_type` | STRING | `scenario_result.scenario_type` mapped to `ScenarioType` enum lines 675-692 | Scenario classification (scenario_5, scenario_6, etc.) |
| `scenario_success` | BOOLEAN | `scenario_result.success` line 696 | Whether scenario processing succeeded |
| `scenario_processing_duration_ms` | BIGINT | `_extract_real_scenario_processing_time()` method lines 1274-1327 | Scenario execution time extracted from processing breakdown |
| `scenario_error_message` | STRING | `scenario_result.error_message` line 701 | Error details if scenario processing failed |

### Actions and Results

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `agent_actions_log` | ARRAY\<STRING\> | `scenario_result.agent_actions_log` or scenario-specific defaults lines 697, 714-729 | List of all actions taken during processing |

### Expert Assignment (Scenario 5)

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `expert_assigned` | STRING | `scenario_result.expert_assigned` line 698 | Name of assigned sales expert |
| `expert_id` | STRING | Hardcoded "0053t00000AvcSuAAJ" line 913 | Salesforce user ID of assigned expert |
| `expert_email` | STRING | Hardcoded "madelyn.locascio@staples.com" line 917 | Email address of assigned expert |
| `assignment_method` | STRING | `get_expert_assignment_method()` via `utils.data_extraction_helpers` line 919 | How expert was assigned (round_robin, manual, etc.) |

### Salesforce Integration

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `case_created` | STRING | `scenario_result.case_created` or generated case ID line 699, 732 | Salesforce case ID if case was created |
| `case_subject` | STRING | Generated from customer name line 922-924 | Subject line of created Salesforce case |
| `case_status` | STRING | Default "New" line 927 | Status of the created case |
| `sf_contact_id` | STRING | Hardcoded "0033t00003txInQAAU" line 930 | Salesforce contact ID for customer |
| `sf_account_id` | STRING | Hardcoded "0013t00002NHELMAA5" line 933 | Salesforce account ID for customer |
| `account_name` | STRING | Hardcoded "Ps Bakery Inc" line 936 | Customer company name from Salesforce |

### Email Forwarding

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `emails_forwarded` | ARRAY\<STRING\> | `scenario_result.emails_sent` line 700, 741 | Email addresses where message was forwarded |
| `forwarding_reason` | STRING | Scenario-specific logic line 965 | Reason for email forwarding |
| `forwarding_success` | BOOLEAN | Based on `process_success` line 940 | Whether email forwarding succeeded |
| `forwarding_error` | STRING | From `process_error` line 958 | Error details if forwarding failed |

### Database Updates

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `external_operations_status` | MAP\<STRING,STRING\> | Hardcoded map line 942-946 | Key-value pairs of database updates made |
| `status_updates` | ARRAY\<STRUCT\> | `DatabaseUpdateRecord` objects line 948-955 | Detailed status change tracking with table, field, old/new values |

### Test Mode and Environment

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `test_mode` | BOOLEAN | From kwargs or default FALSE | Whether test mode was active during processing |
| `test_mode_type` | STRING | `TestModeType` enum | Type of test mode (full_test, email_test, etc.) |
| `test_email_substitutions` | MAP\<STRING,STRING\> | Default substitution map line 990 | Email substitutions made in test mode |
| `environment` | STRING | `detect_environment()` via `utils.data_extraction_helpers` line 994-1001 | Environment metadata with test mode info |

### Email Lifecycle

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `destination_folder` | STRING | `_get_real_destination_folder()` method line 1361-1364 | Outlook folder where email was moved with timestamp |
| `storage_location` | STRING | `_get_real_storage_location()` method line 1366-1388 | File storage location with date-based path structure |
| `email_deleted` | BOOLEAN | Default FALSE | Whether original email was deleted |

### Customer Analytics

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `customer_interaction_count` | INT | Default 1 line 979 | Total interactions from this customer |
| `last_customer_interaction` | TIMESTAMP | `received_datetime` fallback line 983 | Previous interaction timestamp from same customer |
| `customer_scenario_history` | ARRAY\<STRING\> | Generated scenario history line 987 | Previous scenario types for this customer |

### Performance Metrics

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `memory_usage_mb` | DOUBLE | `_get_real_memory_usage()` via psutil line 1330-1342 | Memory usage during processing from psutil |
| `cpu_time_ms` | BIGINT | `_get_real_cpu_time()` via psutil line 1344-1358 | CPU processing time from psutil |
| `connection_pool_wait_ms` | BIGINT | Default 12ms line 976 | Time spent waiting for database connection |

### Audit Fields

| Field Name | Data Type | Source Code Location | Description |
|------------|-----------|---------------------|-------------|
| `created_at` | TIMESTAMP | `datetime.now(timezone.utc)` auto-generated | Record creation timestamp |
| `updated_at` | TIMESTAMP | `datetime.now(timezone.utc)` auto-generated | Record last update timestamp |
| `created_by` | STRING | Default "inbox_monitor" | Service that created this record |
| `data_version` | INT | Default 1 | Schema version for data migration tracking |
| `processing_date` | DATE | Derived from `processed_at` | Date partition column for query performance |

## Data Flow Architecture

### 1. Email Processing Pipeline

```
Email Received → Email Processor → Scenario Processor → AI Classification → Expert Assignment → Database Storage
```

#### Entry Point: `services/email_processor.py`
- Receives email from Microsoft Graph API
- Extracts email metadata and content
- Creates `Email` model object

#### Scenario Processing: `services/scenario_processor.py`
- Processes email through scenario classification
- Determines scenario type (5-11)
- Executes scenario-specific logic
- Creates `ScenarioResult` object

#### AI Classification: `services/azure_ai_foundry_client.py`
- Classifies email intent using Azure OpenAI
- Determines customer sentiment and intent
- Returns `IntentClassificationResult`

#### Data Storage: `services/inbox_monitor_databricks_client.py`
- Combines all processing results
- Creates `ScenarioProcessingRecord`
- Stores in Databricks table

### 2. Data Transformation Process

```python
# In ScenarioProcessingRecord.from_processing_results()

# Extract and validate email data
sender_info = extract_sender_info(email_data)
environment = detect_environment()

# Create record with comprehensive field population
record = ScenarioProcessingRecord(
    # Core identifiers from processing results
    process_id=processing_result.process_id,
    email_id=email_data.id,
    
    # Email data with security validation
    sender_email=validated_email,
    subject=sanitized_subject,
    
    # AI classification results
    email_intent=mapped_intent,
    email_intent_confidence=intent_result.confidence,
    
    # Scenario outcomes
    scenario_type=mapped_scenario_type,
    expert_assigned=scenario_result.expert_assigned,
    case_created=generated_case_id
)

# Convert to database format
databricks_data = record.to_databricks_dict()
```

## Cross-Process Integration

### Integration with Research Tool

The research tool can leverage scenario tracking data for customer intelligence:

```sql
-- Get customer email history for research context
SELECT 
    sender_email,
    sender_name,
    account_name,
    COUNT(*) as total_interactions,
    AVG(email_intent_confidence) as avg_email_intent_confidence,
    COLLECT_LIST(scenario_type) as scenario_history,
    COLLECT_LIST(subject) as subject_history
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE sender_email = 'customer@company.com'
GROUP BY sender_email, sender_name, account_name;
```

**Research Integration Points:**
- `sender_email` + `account_name` → Customer identification
- `email_intent` + `email_intent_reasoning` → Customer sentiment analysis
- `customer_scenario_history` → Interaction pattern analysis
- `subject` + `email_body` → Content analysis for research context

### Integration with Email Generation Tool

Email generation can use tracking data for personalized responses:

```sql
-- Get customer context for email generation
SELECT 
    sender_name,
    expert_assigned,
    expert_email,
    case_created,
    email_intent_reasoning,
    agent_actions_log,
    scenario_type
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE process_id = 'current_process_id'
AND process_success = true;
```

**Email Generation Integration Points:**
- `expert_assigned` + `expert_email` → Personalization from expert
- `case_created` → Reference case number in response
- `email_intent_reasoning` → Understand customer intent for appropriate response
- `scenario_type` → Apply scenario-specific email templates

### Integration with Marketo Email Sending

Marketo can reference tracking data for email campaign optimization:

```sql
-- Get customer segments for Marketo campaigns
SELECT 
    sender_email,
    account_name,
    scenario_type,
    email_intent,
    expert_assigned,
    processed_at,
    customer_interaction_count
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE process_success = true
AND processed_at >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS;
```

**Marketo Integration Points:**
- `sender_email` → Email targeting
- `email_intent` → Segment customers by intent (POSITIVE vs NEGATIVE)
- `scenario_type` → Campaign customization by scenario
- `account_name` → Company-specific campaigns
- `expert_assigned` → Expert follow-up campaigns

### Full Process Data Pipeline

```
1. RESEARCH PHASE
   ├── Company Research Tool generates leads
   ├── Data stored in research database
   └── Lead qualification scores

2. EMAIL GENERATION PHASE  
   ├── AI generates personalized emails
   ├── References research data for context
   ├── Email templates customized by industry/company
   └── Email content stored for tracking

3. MARKETO SENDING PHASE
   ├── Emails sent via Marketo campaigns
   ├── Delivery and engagement tracking
   ├── Bounce and unsubscribe handling
   └── Campaign performance metrics

4. INBOX MONITOR RESPONSE PROCESSING ← THIS TABLE
   ├── Customer responses received via Graph API
   ├── AI intent classification (POSITIVE/NEGATIVE)
   ├── Scenario routing (5-11)
   ├── Expert assignment for positive leads
   ├── Salesforce case creation
   └── Response data stored in scenario_tracking table

5. ANALYTICS AND OPTIMIZATION
   ├── Cross-reference all pipeline data
   ├── Campaign ROI analysis
   ├── Lead conversion tracking
   └── Process improvement insights
```

## Advanced Analytics Queries

### Lead Generation Pipeline Analysis

```sql
-- Full pipeline performance analysis
SELECT 
    DATE_TRUNC('week', processed_at) as week,
    COUNT(*) as total_responses,
    COUNT(CASE WHEN email_intent = 'POSITIVE' THEN 1 END) as positive_responses,
    COUNT(CASE WHEN scenario_type = 'scenario_5' THEN 1 END) as expert_assignments,
    COUNT(CASE WHEN case_created IS NOT NULL THEN 1 END) as cases_created,
    AVG(processing_duration_ms) as avg_response_time,
    COUNT(DISTINCT account_name) as unique_companies
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 90 DAYS
GROUP BY DATE_TRUNC('week', processed_at)
ORDER BY week DESC;
```

### Expert Performance Tracking

```sql
-- Expert assignment and case creation efficiency
SELECT 
    expert_assigned,
    expert_email,
    COUNT(*) as total_assignments,
    COUNT(CASE WHEN case_created IS NOT NULL THEN 1 END) as cases_created,
    COUNT(CASE WHEN case_status = 'Closed Won' THEN 1 END) as won_cases,
    AVG(scenario_processing_duration_ms) as avg_processing_time,
    AVG(email_intent_confidence) as avg_lead_quality
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE scenario_type = 'scenario_5'
AND expert_assigned IS NOT NULL
AND processed_at >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS
GROUP BY expert_assigned, expert_email
ORDER BY cases_created DESC;
```

### Customer Journey Analysis

```sql
-- Customer interaction progression and conversion
SELECT 
    sender_email,
    account_name,
    MIN(processed_at) as first_interaction,
    MAX(processed_at) as latest_interaction,
    COUNT(*) as total_interactions,
    COLLECT_LIST(scenario_type) as scenario_progression,
    COLLECT_LIST(email_intent) as intent_progression,
    MAX(CASE WHEN case_created IS NOT NULL THEN 1 ELSE 0 END) as converted_to_case
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE process_success = true
GROUP BY sender_email, account_name
HAVING COUNT(*) > 1  -- Multi-touch customers only
ORDER BY total_interactions DESC;
```

## Data Quality and Monitoring

### Key Quality Metrics

1. **Processing Success Rate**: `process_success` field completion
2. **AI Classification Quality**: `email_intent_confidence` scores and `email_intent` distribution
3. **Scenario Classification Accuracy**: `scenario_type` distribution and success rates
4. **Expert Assignment Coverage**: `expert_assigned` completion for Scenario 5
5. **Case Creation Rate**: `case_created` completion for positive intents

### Monitoring Queries

```sql
-- Data quality health check
SELECT 
    DATE(processed_at) as processing_date,
    COUNT(*) as total_records,
    AVG(CASE WHEN process_success THEN 1.0 ELSE 0.0 END) as success_rate,
    AVG(email_intent_confidence) as avg_email_intent_confidence,
    COUNT(CASE WHEN expert_assigned IS NULL AND scenario_type = 'scenario_5' THEN 1 END) as missing_expert_assignments,
    COUNT(CASE WHEN case_created IS NULL AND email_intent = 'POSITIVE' THEN 1 END) as missing_case_creations
FROM mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 7 DAYS
GROUP BY DATE(processed_at)
ORDER BY processing_date DESC;
```

This comprehensive table serves as the central data hub for the entire lead generation and customer response processing pipeline, enabling full-cycle analytics from initial research through customer response and conversion tracking.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Review existing documentation in agents/inbox_monitor/docs/scenario_tracking", "status": "completed"}, {"id": "2", "content": "Analyze current implementation of scenario tracker process", "status": "completed"}, {"id": "3", "content": "Compare documentation vs implementation and identify discrepancies", "status": "completed"}, {"id": "4", "content": "Update existing documentation where discrepancies are found", "status": "completed"}, {"id": "5", "content": "Analyze Databricks table schema mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev", "status": "completed"}, {"id": "6", "content": "Create comprehensive .md file documenting table schema, field sources, and cross-process integration", "status": "completed"}]