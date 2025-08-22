-- Inbox Monitor Scenario Processing Tracking Table
-- Auto-generated from ScenarioProcessingRecord Pydantic model to ensure perfect schema synchronization
-- Delta table with comprehensive scenario tracking for business analytics

CREATE TABLE IF NOT EXISTS `{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}` (
    -- Primary identifiers
    processing_id STRING NOT NULL COMMENT 'Unique processing ID',
    email_id STRING NOT NULL COMMENT 'Microsoft Graph email message ID',
    conversation_id STRING COMMENT 'Email conversation ID',
    correlation_id STRING COMMENT 'Cross-service correlation ID',

    -- Email source information
    sender_email STRING NOT NULL COMMENT 'Original sender email address (PII)',
    sender_name STRING COMMENT 'Sender display name (PII)',
    recipient_emails ARRAY<STRING> COMMENT 'All recipient addresses (PII)',
    subject STRING COMMENT 'Email subject line (PII - truncated to 500 chars)',
    received_datetime TIMESTAMP NOT NULL COMMENT 'When email was received',
    sent_datetime TIMESTAMP COMMENT 'When email was sent',
    email_body STRING COMMENT 'Full email body content (PII)',
    email_importance STRING DEFAULT 'normal' COMMENT 'Email importance level',
    has_attachments BOOLEAN DEFAULT FALSE COMMENT 'Whether email has attachments',
    attachment_count INT DEFAULT 0 COMMENT 'Number of attachments',

    -- Processing workflow
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() COMMENT 'When processing started',
    processing_duration_ms BIGINT COMMENT 'Total processing time',
    process_success BOOLEAN NOT NULL COMMENT 'Whether processing succeeded',
    process_error STRING COMMENT 'Error message if failed',
    monitor_version STRING COMMENT 'System version',
    retry_count INT DEFAULT 0 COMMENT 'Number of retry attempts',

    -- Email Intent Classification Results (email-intent-classifier agent)
    email_intent STRING COMMENT 'Email intent classified by email-intent-classifier agent',
    email_intent_confidence DOUBLE COMMENT 'Email intent classification confidence score (0.0-1.0)',
    email_intent_reasoning STRING COMMENT 'Email intent classification reasoning',
    email_intent_detected_phrases ARRAY<STRING> COMMENT 'Key phrases detected by email intent classifier',
    email_intent_processing_duration_ms BIGINT COMMENT 'Email intent classification processing time in milliseconds',
    email_intent_model_version STRING COMMENT 'Email intent classifier model version',

    -- Original Subject Extraction Results (original-subject-extractor agent)
    original_subject_result STRING COMMENT 'Original subject extracted by original-subject-extractor agent',
    original_subject_confidence DOUBLE COMMENT 'Original subject extraction confidence score (0.0-1.0)',
    original_subject_reasoning STRING COMMENT 'Original subject extraction reasoning',
    original_subject_extraction_method STRING COMMENT 'Method used for original subject extraction',
    original_subject_processing_duration_ms BIGINT COMMENT 'Original subject extraction processing time in milliseconds',
    original_subject_model_version STRING COMMENT 'Original subject extractor model version',

    -- Scenario processing
    scenario_type STRING COMMENT 'Scenario type (scenario_5, scenario_6, etc., or unknown)',
    scenario_success BOOLEAN COMMENT 'Whether scenario processing succeeded',
    scenario_processing_duration_ms BIGINT COMMENT 'Scenario execution time in milliseconds',
    scenario_error_message STRING COMMENT 'Error details if scenario processing failed',

    -- Actions and results
    agent_actions_log ARRAY<STRING> COMMENT 'List of actions performed during processing',

    -- Expert assignment (Scenario 5) - PII: Contains expert names and contact info
    expert_assigned STRING COMMENT 'Expert name (PII)',
    expert_id STRING COMMENT 'Expert system ID',
    expert_email STRING COMMENT 'Expert email address (PII)',
    assignment_method STRING COMMENT 'Assignment method used',

    -- Salesforce integration - PII: Contains customer account information
    case_created STRING COMMENT 'Salesforce case ID',
    case_subject STRING COMMENT 'Case subject (may contain PII)',
    case_status STRING COMMENT 'Case status',
    sf_contact_id STRING COMMENT 'Customer contact ID',
    sf_account_id STRING COMMENT 'Customer account ID',
    account_name STRING COMMENT 'Customer company name (PII)',

    -- Email forwarding - PII: Contains email addresses
    emails_forwarded ARRAY<STRING> COMMENT 'Forwarded email addresses (PII)',
    forwarding_reason STRING COMMENT 'Reason for forwarding',
    forwarding_success BOOLEAN COMMENT 'Forwarding success status',
    forwarding_error STRING COMMENT 'Forwarding error details',

    -- Database updates
    external_operations_status MAP<STRING, STRING> COMMENT 'Key-value pairs of database updates made',
    status_updates ARRAY<STRING> COMMENT 'List of status updates',

    -- Test mode tracking - DEPRECATED: Test utilities should handle test data separately
    test_mode BOOLEAN DEFAULT FALSE COMMENT 'Whether test mode was active during processing',
    test_mode_type STRING COMMENT 'Type of test mode',
    test_email_substitutions MAP<STRING, STRING> COMMENT 'Email substitutions made in test mode',
    environment STRING COMMENT 'Environment where processing occurred (dev, staging, prod)',

    -- Email lifecycle
    destination_folder STRING COMMENT 'Outlook folder where email was moved after processing',
    storage_location STRING COMMENT 'File storage location if email was archived (deprecated)',
    email_deleted BOOLEAN DEFAULT FALSE COMMENT 'Whether original email was deleted',

    -- Original subject tracking
    original_email_subject STRING COMMENT 'Original email subject (migrated from storage_location)',

    -- Graph API Raw Data Storage
    email_payload STRING COMMENT 'Complete Graph API message JSON response',
    email_headers STRING COMMENT 'Graph API internetMessageHeaders array as JSON',

    -- Customer interaction patterns
    customer_interaction_count INT COMMENT 'Number of previous interactions with this customer',
    last_customer_interaction TIMESTAMP COMMENT 'Previous interaction from same customer',
    customer_scenario_history ARRAY<STRING> COMMENT 'Historical scenarios for this customer',

    -- Performance tracking
    memory_usage_mb DOUBLE COMMENT 'Peak memory usage during processing in MB',
    cpu_time_ms BIGINT COMMENT 'CPU processing time in milliseconds',
    connection_pool_wait_ms BIGINT COMMENT 'Time spent waiting for database connection',

    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() COMMENT 'When this record was created',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() COMMENT 'When this record was last modified',
    created_by STRING DEFAULT 'inbox_monitor' COMMENT 'System/user that created this record',
    data_version INT DEFAULT 1 COMMENT 'Schema version for data migration tracking',
    processing_date TIMESTAMP COMMENT 'Date partition field for the table'
)
USING DELTA
PARTITIONED BY (DATE(processed_at))
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.deletedFileRetentionDuration' = 'interval 7 days',
    'delta.logRetentionDuration' = 'interval 30 days'
)
COMMENT 'Comprehensive tracking of inbox monitor scenario processing synchronized with ScenarioProcessingRecord model';

