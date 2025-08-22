-- Migration script to add new fields to existing inbox_monitor_scenario_processing table
-- This script adds the new email intent, original subject, and Graph API JSON fields

-- Add new Email Intent Classification fields (renamed from ai_*)
ALTER TABLE `{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}`
ADD COLUMNS (
    email_intent STRING COMMENT 'Email intent classified by email-intent-classifier agent (POSITIVE, NEGATIVE, SERVICE_INQUIRY, etc.)',
    email_intent_confidence DOUBLE COMMENT 'Email intent classification confidence score (0.0-1.0)',
    email_intent_reasoning STRING COMMENT 'Email intent classification reasoning',
    email_intent_detected_phrases ARRAY<STRING> COMMENT 'Key phrases detected by email intent classifier',
    email_intent_processing_duration_ms BIGINT COMMENT 'Email intent classification processing time in milliseconds',
    email_intent_model_version STRING COMMENT 'Email intent classifier model version'
);

-- Add Original Subject Extraction fields (original-subject-extractor agent)
ALTER TABLE `{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}`
ADD COLUMNS (
    original_subject_result STRING COMMENT 'Original subject extracted by original-subject-extractor agent',
    original_subject_confidence DOUBLE COMMENT 'Original subject extraction confidence score (0.0-1.0)',
    original_subject_reasoning STRING COMMENT 'Original subject extraction reasoning',
    original_subject_extraction_method STRING COMMENT 'Method used for original subject extraction',
    original_subject_processing_duration_ms BIGINT COMMENT 'Original subject extraction processing time in milliseconds',
    original_subject_model_version STRING COMMENT 'Original subject extractor model version'
);

-- Add additional fields
ALTER TABLE `{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}`
ADD COLUMNS (
    original_email_subject STRING COMMENT 'Original email subject (migrated from storage_location)',
    email_payload STRING COMMENT 'Complete Graph API message JSON response',
    email_headers STRING COMMENT 'Graph API internetMessageHeaders array as JSON'
);

-- Note: The old ai_* columns will remain for backward compatibility during transition
-- They can be dropped later once all applications are updated to use the new field names