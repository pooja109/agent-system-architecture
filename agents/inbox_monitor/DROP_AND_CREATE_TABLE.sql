-- =====================================================================
-- DROP AND RECREATE TABLE WITH NEW SCHEMA
-- =====================================================================
-- Execute these statements in Databricks SQL Editor to completely
-- replace the table with the new schema
-- =====================================================================

-- 1. Drop the existing table
DROP TABLE IF EXISTS mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev;

-- 2. Create the table with the new schema (no old ai_* fields)
CREATE TABLE `mld01_sandbox_de`.`ai_garage`.`inbox_monitor_scenario_processing_dev` (
    -- Primary identifiers and correlation
    process_id STRING NOT NULL COMMENT 'Unique processing ID from ProcessingResult',
    email_id STRING NOT NULL COMMENT 'Microsoft Graph email message ID',
    conversation_id STRING COMMENT 'Email thread/conversation ID for grouping related messages',
    correlation_id STRING COMMENT 'Correlation ID for tracking processing across services',
    
    -- Processing execution and timing
    process_success BOOLEAN NOT NULL DEFAULT false COMMENT 'Whether processing completed successfully',
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'When processing started',
    processing_duration_ms BIGINT COMMENT 'Total processing time in milliseconds',
    scenario_processing_duration_ms BIGINT COMMENT 'Scenario-specific processing time in milliseconds',
    
    -- Email core properties
    sender_email STRING NOT NULL COMMENT 'Email sender address',
    sender_name STRING COMMENT 'Email sender display name',
    recipient_emails ARRAY<STRING> COMMENT 'List of recipient email addresses',
    subject STRING COMMENT 'Email subject line',
    received_datetime TIMESTAMP COMMENT 'When email was received',
    sent_datetime TIMESTAMP COMMENT 'When email was originally sent',
    email_body STRING COMMENT 'Email body content preview',
    body_length BIGINT COMMENT 'Length of email body in characters',
    has_subject BOOLEAN DEFAULT false COMMENT 'Whether email has a subject line',
    has_attachments BOOLEAN DEFAULT false COMMENT 'Whether email has attachments',
    attachment_count INT DEFAULT 0 COMMENT 'Number of attachments',
    importance STRING DEFAULT 'normal' COMMENT 'Email importance level',
    
    -- Email Intent Classification Results (email-intent-classifier agent)
    email_intent STRING COMMENT 'Email intent classified by email-intent-classifier agent (POSITIVE, NEGATIVE, SERVICE_INQUIRY, etc.)',
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
    
    -- Scenario classification and execution results
    scenario_type STRING COMMENT 'Scenario type (scenario_5, scenario_6, etc., or unknown)',
    scenario_confidence DOUBLE COMMENT 'Confidence score for scenario classification (0.0-1.0)',
    scenario_reasoning STRING COMMENT 'Reasoning for scenario selection',
    scenario_decision_factors ARRAY<STRING> COMMENT 'List of factors that influenced scenario decision',
    scenario_execution_success BOOLEAN DEFAULT false COMMENT 'Whether scenario execution completed successfully',
    scenario_execution_time_ms BIGINT COMMENT 'Time taken to execute scenario actions in milliseconds',
    
    -- Contact and customer information
    customer_id STRING COMMENT 'Customer identifier if found',
    customer_name STRING COMMENT 'Customer name from contact lookup',
    customer_company STRING COMMENT 'Customer company/organization',
    contact_lookup_method STRING COMMENT 'Method used for contact lookup (salesforce, graph, manual)',
    contact_lookup_success BOOLEAN DEFAULT false COMMENT 'Whether contact lookup was successful',
    contact_lookup_time_ms BIGINT COMMENT 'Time taken for contact lookup in milliseconds',
    
    -- Response generation and forwarding
    expert_assigned STRING COMMENT 'Expert/specialist assigned to handle the email',
    expert_assignment_method STRING COMMENT 'Method used to assign expert (round_robin, manual, etc.)',
    expert_assignment_reasoning STRING COMMENT 'Reasoning for expert assignment',
    response_generated BOOLEAN DEFAULT false COMMENT 'Whether an automated response was generated',
    response_sent BOOLEAN DEFAULT false COMMENT 'Whether response was successfully sent',
    response_generation_time_ms BIGINT COMMENT 'Time taken to generate response in milliseconds',
    response_template_used STRING COMMENT 'Template used for response generation',
    
    -- Actions taken during processing
    agent_actions_log ARRAY<STRING> COMMENT 'List of actions performed during processing',
    emails_forwarded ARRAY<STRING> COMMENT 'List of email addresses to which email was forwarded',
    cases_created ARRAY<STRING> COMMENT 'List of case/ticket IDs created',
    notifications_sent ARRAY<STRING> COMMENT 'List of notification recipients',
    
    -- Error handling and debugging
    error_occurred BOOLEAN DEFAULT false COMMENT 'Whether any errors occurred during processing',
    error_messages ARRAY<STRING> COMMENT 'List of error messages encountered',
    warning_messages ARRAY<STRING> COMMENT 'List of warning messages',
    debug_information STRING COMMENT 'Additional debug information for troubleshooting',
    retry_count INT DEFAULT 0 COMMENT 'Number of processing retry attempts',
    
    -- External system integration
    salesforce_case_id STRING COMMENT 'Salesforce case ID if created',
    sf_account_id STRING COMMENT 'Salesforce account ID if found',
    sf_contact_id STRING COMMENT 'Salesforce contact ID if found',
    external_reference_ids MAP<STRING, STRING> COMMENT 'Map of external system reference IDs',
    
    -- Business intelligence and analytics
    business_unit STRING COMMENT 'Business unit associated with the email',
    product_interest ARRAY<STRING> COMMENT 'Products/services mentioned in email',
    priority_score DOUBLE COMMENT 'Calculated priority score for business analytics',
    lead_quality_score DOUBLE COMMENT 'Estimated lead quality score',
    follow_up_required BOOLEAN DEFAULT false COMMENT 'Whether follow-up action is required',
    follow_up_date TIMESTAMP COMMENT 'Suggested follow-up date',
    
    -- Email Lifecycle Management
    destination_folder STRING COMMENT 'Outlook folder where email was moved after processing',
    storage_location STRING COMMENT 'File storage location if email was archived (deprecated)',
    email_deleted BOOLEAN DEFAULT FALSE COMMENT 'Whether original email was deleted',
    
    -- Original Subject Tracking
    original_email_subject STRING COMMENT 'Original email subject (migrated from storage_location)',
    
    -- Graph API Raw Data Storage
    email_payload STRING COMMENT 'Complete Graph API message JSON response',
    email_headers STRING COMMENT 'Graph API internetMessageHeaders array as JSON',
    
    -- Customer scenario history and context
    customer_scenario_history ARRAY<STRING> COMMENT 'Historical scenarios for this customer',
    previous_interaction_count INT DEFAULT 0 COMMENT 'Number of previous interactions with this customer',
    interaction_pattern STRING COMMENT 'Pattern of customer interactions (new, returning, frequent)',
    
    -- Performance monitoring and optimization
    cache_hit_rate DOUBLE COMMENT 'Cache hit rate during processing',
    database_query_count INT DEFAULT 0 COMMENT 'Number of database queries executed',
    api_call_count INT DEFAULT 0 COMMENT 'Number of external API calls made',
    memory_usage_mb DOUBLE COMMENT 'Peak memory usage during processing in MB',
    
    -- Quality assurance and validation
    data_quality_score DOUBLE COMMENT 'Overall data quality score for this record',
    validation_errors ARRAY<STRING> COMMENT 'List of data validation errors',
    data_completeness_percentage DOUBLE COMMENT 'Percentage of expected fields that are populated',
    
    -- Audit and compliance
    created_by STRING DEFAULT 'inbox_monitor_system' COMMENT 'System/user that created this record',
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP() COMMENT 'When this record was created',
    last_modified_by STRING COMMENT 'System/user that last modified this record',
    last_modified_timestamp TIMESTAMP COMMENT 'When this record was last modified',
    data_retention_date TIMESTAMP COMMENT 'Date when this record should be archived/deleted',
    
    -- Environment and deployment tracking
    environment STRING DEFAULT 'production' COMMENT 'Environment where processing occurred (dev, staging, prod)',
    deployment_version STRING COMMENT 'Version of the inbox monitor system',
    feature_flags ARRAY<STRING> COMMENT 'List of feature flags active during processing',
    
    -- Status tracking and workflow
    processing_status STRING DEFAULT 'completed' COMMENT 'Current processing status',
    workflow_stage STRING COMMENT 'Current stage in the processing workflow',
    next_action STRING COMMENT 'Next action to be taken',
    status_updates ARRAY<STRUCT<timestamp:TIMESTAMP, status:STRING, message:STRING>> COMMENT 'Timeline of status updates'
)
USING DELTA
PARTITIONED BY (DATE(processed_at))
LOCATION 's3://your-databricks-storage/tables/inbox_monitor_scenario_processing_dev'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.deletedFileRetentionDuration' = 'interval 7 days',
    'delta.logRetentionDuration' = 'interval 30 days'
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_sender_email ON mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev (sender_email);
CREATE INDEX IF NOT EXISTS idx_scenario_type ON mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev (scenario_type);
CREATE INDEX IF NOT EXISTS idx_processed_at ON mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev (processed_at);

-- Optimize table for common query patterns
OPTIMIZE mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev
ZORDER BY (sender_email, scenario_type, processed_at);

-- =====================================================================
-- VERIFICATION QUERY
-- =====================================================================
-- Run this to verify the table was created with the correct schema:
DESCRIBE TABLE mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev;