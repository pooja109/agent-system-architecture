-- =====================================================================
-- DATABRICKS TABLE MIGRATION SCRIPT
-- =====================================================================
-- Copy and paste the following SQL statements into your Databricks SQL Editor
-- Execute them one by one to add the new columns to your existing table
-- =====================================================================

-- 1. Add Email Intent Classification fields (renamed from ai_*)
ALTER TABLE mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev ADD COLUMNS (
    email_intent STRING COMMENT 'Email intent classified by email-intent-classifier agent (POSITIVE, NEGATIVE, SERVICE_INQUIRY, etc.)',
    email_intent_confidence DOUBLE COMMENT 'Email intent classification confidence score (0.0-1.0)',
    email_intent_reasoning STRING COMMENT 'Email intent classification reasoning',
    email_intent_detected_phrases ARRAY<STRING> COMMENT 'Key phrases detected by email intent classifier',
    email_intent_processing_duration_ms BIGINT COMMENT 'Email intent classification processing time in milliseconds',
    email_intent_model_version STRING COMMENT 'Email intent classifier model version'
);

-- 2. Add Original Subject Extraction fields (original-subject-extractor agent)
ALTER TABLE mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev ADD COLUMNS (
    original_subject_result STRING COMMENT 'Original subject extracted by original-subject-extractor agent',
    original_subject_confidence DOUBLE COMMENT 'Original subject extraction confidence score (0.0-1.0)',
    original_subject_reasoning STRING COMMENT 'Original subject extraction reasoning',
    original_subject_extraction_method STRING COMMENT 'Method used for original subject extraction',
    original_subject_processing_duration_ms BIGINT COMMENT 'Original subject extraction processing time in milliseconds',
    original_subject_model_version STRING COMMENT 'Original subject extractor model version'
);

-- 3. Add additional fields for Graph API JSON and original subject tracking
ALTER TABLE mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev ADD COLUMNS (
    original_email_subject STRING COMMENT 'Original email subject (migrated from storage_location)',
    email_payload STRING COMMENT 'Complete Graph API message JSON response',
    email_headers STRING COMMENT 'Graph API internetMessageHeaders array as JSON'
);

-- =====================================================================
-- VERIFICATION QUERIES
-- =====================================================================
-- After running the above ALTER TABLE statements, execute these to verify:

-- Check that all new columns were added
DESCRIBE TABLE mld01_sandbox_de.ai_garage.inbox_monitor_scenario_processing_dev;

-- Count total columns (should be significantly more than before)
SELECT COUNT(*) as total_columns
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'ai_garage' 
  AND TABLE_NAME = 'inbox_monitor_scenario_processing_dev';

-- Verify specific new columns exist
SELECT column_name, data_type, comment
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'ai_garage' 
  AND TABLE_NAME = 'inbox_monitor_scenario_processing_dev'
  AND column_name IN (
    'email_intent',
    'email_intent_confidence', 
    'original_subject_result',
    'original_subject_confidence',
    'email_payload',
    'original_email_subject'
  )
ORDER BY column_name;

-- =====================================================================
-- EXPECTED RESULTS
-- =====================================================================
-- After successful migration, you should see these 15 new columns:
-- 1. email_intent
-- 2. email_intent_confidence
-- 3. email_intent_reasoning
-- 4. email_intent_detected_phrases
-- 5. email_intent_processing_duration_ms
-- 6. email_intent_model_version
-- 7. original_subject_result
-- 8. original_subject_confidence
-- 9. original_subject_reasoning
-- 10. original_subject_extraction_method
-- 11. original_subject_processing_duration_ms
-- 12. original_subject_model_version
-- 13. original_email_subject
-- 14. email_payload
-- 15. email_headers
-- =====================================================================