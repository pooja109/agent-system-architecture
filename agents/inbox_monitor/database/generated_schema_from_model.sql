CREATE TABLE `mld01_sandbox_de`.`ai_garage`.`inbox_monitor_scenario_processing_dev` (
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
    email_importance STRING COMMENT 'Email Importance',
    has_attachments BOOLEAN COMMENT 'Has Attachments',
    attachment_count INT COMMENT 'Attachment Count',

    -- Processing workflow
    processed_at TIMESTAMP COMMENT 'Processed At',
    processing_duration_ms BIGINT COMMENT 'Total processing time',
    process_success BOOLEAN NOT NULL COMMENT 'Whether processing succeeded',
    process_error STRING COMMENT 'Error message if failed',
    monitor_version STRING COMMENT 'System version',
    retry_count INT COMMENT 'Retry Count',

    -- Email Intent Classification
    email_intent STRING COMMENT 'Email intent classified by email-intent-classifier agent',
    email_intent_confidence DOUBLE COMMENT 'Email intent classification confidence score',
    email_intent_reasoning STRING COMMENT 'Email intent classification reasoning',
    email_intent_detected_phrases ARRAY<STRING> COMMENT 'Key phrases detected by email intent classifier',
    email_intent_processing_duration_ms BIGINT COMMENT 'Email intent classification processing time in milliseconds',
    email_intent_model_version STRING COMMENT 'Email intent classifier model version',

    -- Original Subject Extraction
    original_subject_result STRING COMMENT 'Original subject extracted by original-subject-extractor agent',
    original_subject_confidence DOUBLE COMMENT 'Original subject extraction confidence score',
    original_subject_reasoning STRING COMMENT 'Original subject extraction reasoning',
    original_subject_extraction_method STRING COMMENT 'Method used for original subject extraction',
    original_subject_processing_duration_ms BIGINT COMMENT 'Original subject extraction processing time in milliseconds',
    original_subject_model_version STRING COMMENT 'Original subject extractor model version',

    -- Scenario processing
    scenario_type STRING COMMENT 'Scenario Type',
    scenario_success BOOLEAN COMMENT 'Scenario Success',
    scenario_processing_duration_ms BIGINT COMMENT 'Scenario Processing Duration Ms',
    scenario_error_message STRING COMMENT 'Scenario Error Message',

    -- Actions and results
    agent_actions_log ARRAY<STRING> COMMENT 'Agent Actions Log',

    -- Expert assignment
    assignment_id STRING COMMENT 'Foreign key to expert_lead_assignments table',
    expert_assigned STRING COMMENT 'Expert name (PII)',
    expert_id STRING COMMENT 'Expert system ID',
    expert_email STRING COMMENT 'Expert email address (PII)',
    assignment_method STRING COMMENT 'Assignment method used',

    -- Salesforce integration
    case_created STRING COMMENT 'Salesforce case ID',
    case_subject STRING COMMENT 'Case subject (may contain PII)',
    case_status STRING COMMENT 'Case status',
    sf_contact_id STRING COMMENT 'Customer contact ID',
    sf_account_id STRING COMMENT 'Customer account ID',
    account_name STRING COMMENT 'Customer company name (PII)',

    -- Email forwarding
    emails_forwarded ARRAY<STRING> COMMENT 'Forwarded email addresses (PII)',
    forwarding_reason STRING COMMENT 'Reason for forwarding',
    forwarding_success BOOLEAN COMMENT 'Forwarding success status',
    forwarding_error STRING COMMENT 'Forwarding error details',

    -- Database updates
    external_operations_status MAP<STRING, STRING> COMMENT 'External Operations Status',
    status_updates ARRAY<STRING> COMMENT 'Status Updates',

    -- Test mode tracking
    test_mode BOOLEAN COMMENT 'DEPRECATED: Use test utilities',
    test_mode_type STRING COMMENT 'DEPRECATED',
    test_email_substitutions MAP<STRING, STRING> COMMENT 'DEPRECATED: Mixed types from test_mode settings',
    environment STRING COMMENT 'Environment',

    -- Email lifecycle
    destination_folder STRING COMMENT 'Destination Folder',
    storage_location STRING COMMENT 'Storage Location',
    email_deleted BOOLEAN COMMENT 'Email Deleted',

    -- Original subject tracking
    original_email_subject STRING COMMENT 'Original email subject (migrated from storage_location)',

    -- Graph API Raw Data
    email_payload STRING COMMENT 'Complete Graph API message JSON response',
    email_headers STRING COMMENT 'Graph API internetMessageHeaders array as JSON',

    -- Customer interaction patterns
    customer_interaction_count INT COMMENT 'Customer Interaction Count',
    last_customer_interaction TIMESTAMP COMMENT 'Last Customer Interaction',
    customer_scenario_history ARRAY<STRING> COMMENT 'Customer Scenario History',

    -- Performance tracking
    memory_usage_mb DOUBLE COMMENT 'Memory Usage Mb',
    cpu_time_ms BIGINT COMMENT 'Cpu Time Ms',
    connection_pool_wait_ms BIGINT COMMENT 'Connection Pool Wait Ms',

    -- Audit fields
    created_at TIMESTAMP COMMENT 'Created At',
    updated_at TIMESTAMP COMMENT 'Updated At',
    created_by STRING COMMENT 'Created By',
    data_version INT COMMENT 'Data Version',
    processing_date DATE COMMENT 'Date partition field for the table'
)
USING DELTA
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.feature.allowColumnDefaults' = 'supported',
    'delta.deletedFileRetentionDuration' = 'interval 7 days',
    'delta.logRetentionDuration' = 'interval 30 days'
);