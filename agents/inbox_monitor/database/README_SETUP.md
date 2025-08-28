# Scenario Tracking Table Setup Guide

This guide explains how to create the scenario processing tracking table in Databricks. You have multiple options depending on your needs.

## Table Overview

The `inbox_monitor_scenario_processing` table provides comprehensive tracking of email processing scenarios with:

- **69 fields** covering all aspects of email processing
- **Delta table optimization** with auto-optimize and compaction
- **Date-based partitioning** for query performance
- **Strategic indexing** for common access patterns
- **PII handling** with field length limits and data retention controls

## Setup Options

### Option 1: Integrated Setup (Recommended for New Installations)

Create all Databricks tables including scenario tracking as part of the main setup:

```bash
# Complete setup including round-robin tables + scenario tracking
python main.py setup
```

**What this does:**
- ✅ Creates expert assignment tables (round-robin functionality)
- ✅ Creates scenario processing tracking table  
- ✅ Verifies active expert pool view
- ✅ Tests all functionality end-to-end
- ✅ Displays setup statistics

**Use when:** Setting up the entire inbox monitor system for the first time.

### Option 2: Scenario Tracking Only Setup (Recommended)

Create only the scenario tracking table via the main application:

```bash
# Via main.py command (recommended)
python main.py setup-scenario-tracking
python main.py setup-scenario-tracking --verify  # with additional testing
```

**What this does:**
- ✅ Creates scenario processing tracking table only
- ✅ Verifies table structure and properties
- ✅ Tests basic CRUD operations  
- ✅ Displays table statistics and details

**Use when:** 
- Adding scenario tracking to existing inbox monitor installation
- Re-creating scenario tracking table after schema changes
- Testing scenario tracking functionality in isolation

### Option 3: Simple SQL Generator (For Manual Execution)

If you need to see the SQL or run it manually:

```bash
# Generate and display the SQL
python utils/create_scenario_table.py
```

**What this does:**
- ✅ Validates environment variables
- ✅ Loads and formats SQL schema 
- ✅ Displays SQL with your environment values
- ✅ Provides clear copy-paste instructions

**Use when:**
- You want to review the SQL before execution
- You need to execute SQL manually in Databricks
- You want to understand the table structure
- Environment/dependency issues prevent other options

### Option 4: Manual SQL Execution

If you prefer to work directly with the SQL:

```bash
# View the raw SQL schema
cat database/scenario_tracking_schema.sql

# Replace placeholders manually:
# {catalog} -> your_catalog_name
# {schema} -> your_schema_name  
# {table_suffix} -> your_environment_suffix (or empty)
```

Then execute the SQL in Databricks SQL Editor or notebook.

## Verification Steps

After running any setup option, verify the table was created successfully:

### 1. Check Table Exists

```sql
-- In Databricks SQL Editor
SHOW TABLES IN your_catalog.your_schema LIKE '*scenario_processing*';
```

### 2. Verify Table Structure

```sql
-- Check column count and structure
DESCRIBE your_catalog.your_schema.inbox_monitor_scenario_processing;
```

### 3. Check Table Properties

```sql
-- Verify Delta table properties
SHOW TBLPROPERTIES your_catalog.your_schema.inbox_monitor_scenario_processing;
```

### 4. Test Basic Operations

```sql
-- Test insert and select
SELECT COUNT(*) FROM your_catalog.your_schema.inbox_monitor_scenario_processing;
```

## Environment Variables

Make sure these environment variables are configured:

```bash
# Required Databricks settings
DATABRICKS_SERVER_HOSTNAME=your-databricks-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_CATALOG=your_catalog
DATABRICKS_SCHEMA=your_schema

# Optional table suffix for environment isolation
DATABRICKS_TABLE_SUFFIX=_dev  # or _test, _prod, etc.

# Scenario tracking configuration
SCENARIO_TRACKING_ENABLED=true
SCENARIO_TRACKING_BATCH_SIZE=100
SCENARIO_TRACKING_ASYNC_INSERT=true
```

## Table Schema Details

The scenario tracking table includes these key field groups:

| Field Group | Count | Description |
|-------------|--------|-------------|
| **Identifiers** | 4 | process_id, email_id, conversation_id, correlation_id |
| **Email Source** | 11 | Sender, recipients, subject, content previews |
| **Processing Workflow** | 6 | Timestamps, success status, errors, retries |
| **AI Classification** | 6 | Intent, confidence, reasoning, detected phrases |
| **Scenario Results** | 4 | Scenario type, success, timing, errors |
| **Expert Assignment** | 4 | Expert details for Scenario 5 |
| **Salesforce Integration** | 6 | Case creation and customer account data |
| **Email Forwarding** | 4 | Forwarding results for Scenarios 6,7,10 |
| **Database Updates** | 2 | Change tracking and status updates |
| **Test Mode** | 4 | Test mode configuration and substitutions |
| **Email Lifecycle** | 3 | Folder moves, archiving, deletion status |
| **Customer Analytics** | 3 | Interaction patterns and history |
| **Performance Tracking** | 3 | Memory, CPU, connection pool metrics |
| **Audit Fields** | 4 | Creation, updates, versioning |
| **Total** | **69** | **Comprehensive scenario tracking** |

## Performance Optimization

The table is optimized for performance with:

### Partitioning Strategy
```sql
PARTITIONED BY (DATE(processed_at))
```
- Optimal for time-based queries
- Supports efficient data retention and archiving

### ZORDER Optimization  
```sql
ZORDER BY (sender_email, scenario_type, processed_at)
```
- Multi-dimensional clustering on most-queried fields
- Speeds up customer-specific and scenario-specific queries

### Strategic Indexes
1. **Sender + Time Index**: Customer interaction analysis
2. **Expert Assignment Index**: Scenario 5 workload balancing  
3. **Case Tracking Index**: Salesforce integration queries

## Troubleshooting

### Common Issues

**1. Module not found error (standalone scripts)**
```
ModuleNotFoundError: No module named 'config'
```
**Solution:** Run the script from the inbox_monitor directory:
```bash
cd /path/to/agents/inbox_monitor
python utils/create_scenario_table.py
# or use the main.py commands instead:
python main.py setup-scenario-tracking
```

**2. Schema file not found**
```
ERROR: Schema file not found: .../database/scenario_tracking_schema.sql
```
**Solution:** Ensure you're running from the inbox_monitor directory

**3. Connection failed**
```  
ERROR: Databricks connection validation failed
```
**Solution:** Check environment variables and Key Vault credentials

**4. Logger factory not initialized**
```
ERROR: Logger factory not initialized
```
**Solution:** Use the main.py commands instead of standalone scripts:
```bash
python main.py setup-scenario-tracking
```

**5. Permission denied**
```
ERROR: Permission denied creating table
```
**Solution:** Ensure service principal has CREATE TABLE permissions

### Getting Help

1. **Check logs:** Setup scripts provide detailed logging
2. **Verify environment:** Run `python main.py status` to check configuration
3. **Test connection:** Run `python main.py test` to validate Databricks access
4. **Run diagnostics:** Use `--verbose` flag for detailed output

## Next Steps

After successful table creation:

1. **Run tests:** `python -m pytest tests/test_scenario_tracking_models.py`
2. **Integration test:** `python test_end_to_end_integration.py`  
3. **Start monitoring:** `python main.py run`
4. **Monitor usage:** Check Databricks SQL Editor for query performance

The scenario tracking table will automatically start collecting data once the inbox monitor processes emails in production.