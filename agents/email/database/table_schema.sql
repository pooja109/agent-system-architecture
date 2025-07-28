-- Email Communication Pipeline Table
-- This table combines workflow tracking with email audit functionality
-- Supports the complete email communication lifecycle from research to delivery

CREATE TABLE IF NOT EXISTS `{catalog}`.`{schema}`.`email_communication_pipeline{table_suffix}` (
    -- Primary workflow tracking fields
    batch_id INT NOT NULL COMMENT 'Simple integer batch identifier',
    run_date DATE NOT NULL COMMENT 'Date the batch was processed',
    agent_name STRING NOT NULL COMMENT 'Name of the agent that processed this record (communication, research, etc.)',
    status STRING NOT NULL COMMENT 'Processing status (S=Success, F=Failed, P=Pending)',
    input_file STRING COMMENT 'Full blob storage path to input file (research output JSON)',
    output_file STRING COMMENT 'Full blob storage path to output file (email HTML)',
    
    -- Review and approval workflow
    is_reviewed BOOLEAN DEFAULT FALSE COMMENT 'Whether the content has been reviewed',
    review_notes STRING COMMENT 'Notes from the review process',
    is_approved BOOLEAN DEFAULT FALSE COMMENT 'Whether the content has been approved for sending',
    approved_notes STRING COMMENT 'Notes from the approval process',
    
    -- Email sending tracking
    is_email_sent BOOLEAN DEFAULT FALSE COMMENT 'Whether the email has been successfully sent',
    
    -- Customer and contact information
    customer_id STRING NOT NULL COMMENT 'Unique customer identifier',
    contact_id STRING COMMENT 'Contact identifier from the research output',
    customer_name STRING COMMENT 'Customer/company name',
    
    -- Email audit and delivery tracking
    sent_email_id STRING COMMENT 'Unique identifier for the sent email (UUID)',
    recipient_email STRING COMMENT 'Email address where the email was sent',
    subject STRING COMMENT 'Email subject line',
    send_timestamp TIMESTAMP COMMENT 'When the email was actually sent',
    send_status STRING COMMENT 'Email send status (sent, failed, pending)',
    error_message STRING COMMENT 'Error details if email sending failed',
    acs_message_id STRING COMMENT 'Azure Communication Services message ID for tracking',
    
    -- Additional metadata for blob processing
    blob_date_folder STRING COMMENT 'Date folder in blob storage (e.g., 20200707)',
    json_file_path STRING COMMENT 'Full path to the research JSON file',
    html_file_path STRING COMMENT 'Full path to the email HTML file',
    
    -- Audit fields
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'Record creation timestamp',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP() COMMENT 'Record last update timestamp',
    processed_by STRING DEFAULT 'email_processor' COMMENT 'System/service that processed this record',
    
    -- Primary key and constraints
    PRIMARY KEY (batch_id, customer_id)
) 
USING DELTA
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.feature.allowColumnDefaults' = 'supported'
)
COMMENT 'Unified table for email communication pipeline tracking and audit trail';

-- Note: Unity Catalog doesn't support CREATE INDEX commands
-- Databricks automatically optimizes queries using Z-ordering and clustering
-- Consider using OPTIMIZE and ZORDER commands in separate maintenance scripts if needed

-- View for pending email processing
CREATE VIEW IF NOT EXISTS `{catalog}`.`{schema}`.`pending_emails{table_suffix}` AS
SELECT 
    batch_id,
    customer_id,
    customer_name,
    input_file,
    output_file,
    run_date,
    created_at
FROM `{catalog}`.`{schema}`.`email_communication_pipeline{table_suffix}`
WHERE agent_name = 'communication' 
    AND status = 'S' 
    AND is_email_sent IS NULL 
    AND is_approved = TRUE
ORDER BY run_date ASC, batch_id ASC;

-- View for email delivery tracking
CREATE VIEW IF NOT EXISTS `{catalog}`.`{schema}`.`email_delivery_status{table_suffix}` AS
SELECT 
    batch_id,
    customer_id,
    customer_name,
    recipient_email,
    subject,
    send_status,
    send_timestamp,
    acs_message_id,
    error_message,
    created_at,
    updated_at
FROM `{catalog}`.`{schema}`.`email_communication_pipeline{table_suffix}`
WHERE is_email_sent IS NOT NULL
ORDER BY send_timestamp DESC;

-- View for processing statistics
CREATE VIEW IF NOT EXISTS `{catalog}`.`{schema}`.`email_processing_stats{table_suffix}` AS
SELECT 
    run_date,
    agent_name,
    status,
    COUNT(*) as record_count,
    SUM(CASE WHEN is_email_sent = TRUE THEN 1 ELSE 0 END) as emails_sent,
    SUM(CASE WHEN send_status = 'failed' THEN 1 ELSE 0 END) as emails_failed,
    MAX(updated_at) as last_updated
FROM `{catalog}`.`{schema}`.`email_communication_pipeline{table_suffix}`
GROUP BY run_date, agent_name, status
ORDER BY run_date DESC, agent_name, status;