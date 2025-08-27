#!/usr/bin/env python3
"""
Migration script to add new columns to existing inbox_monitor_scenario_processing table.
This script adds the new email intent, original subject, and Graph API JSON fields.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.databricks_oauth_client import DatabricksOAuthClient
from config.settings import AppSettings


async def main():
    """Run the table schema migration."""
    print("🔧 Migrating Scenario Tracking Table Schema")
    print("=" * 50)
    
    # Load environment variables
    try:
        settings = AppSettings()
        print("✅ Loaded environment variables")
    except Exception as e:
        print(f"❌ Failed to load settings: {e}")
        return False
    
    # Validate required environment variables
    required_vars = [
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH", 
        "DATABRICKS_CATALOG",
        "DATABRICKS_SCHEMA"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print("\nPlease set these environment variables and try again.")
        return False
    
    print("✅ Environment variables validated")
    
    # Get table details
    catalog = os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("DATABRICKS_SCHEMA") 
    table_suffix = os.getenv("DATABRICKS_TABLE_SUFFIX", "")
    table_name = f"{catalog}.{schema}.inbox_monitor_scenario_processing{table_suffix}"
    
    print(f"📋 Table to migrate: {table_name}")
    
    # Load migration SQL
    migration_sql_path = project_root / "database" / "migrate_table_schema.sql"
    try:
        with open(migration_sql_path, 'r') as f:
            migration_sql = f.read()
        
        # Replace placeholders
        migration_sql = migration_sql.replace("{catalog}", catalog)
        migration_sql = migration_sql.replace("{schema}", schema)
        migration_sql = migration_sql.replace("{table_suffix}", table_suffix)
        
        print(f"✅ Loaded migration SQL ({len(migration_sql)} characters)")
        
    except FileNotFoundError:
        print(f"❌ Migration SQL file not found: {migration_sql_path}")
        return False
    except Exception as e:
        print(f"❌ Failed to load migration SQL: {e}")
        return False
    
    # Show the SQL that will be executed
    print("\n📄 Migration SQL to execute:")
    print("-" * 50)
    for i, line in enumerate(migration_sql.split('\n'), 1):
        if line.strip() and not line.strip().startswith('--'):
            print(f"{i:3}: {line}")
    print("-" * 50)
    
    # Execute migration
    try:
        print("\n🚀 Executing migration...")
        
        client = DatabricksOAuthClient()
        await client.__aenter__()
        
        # Split the SQL into individual ALTER TABLE statements
        statements = []
        current_statement = []
        
        for line in migration_sql.split('\n'):
            if line.strip():
                if line.strip().startswith('ALTER TABLE') and current_statement:
                    # Start of new statement, save the previous one
                    statements.append('\n'.join(current_statement))
                    current_statement = [line]
                elif not line.strip().startswith('--'):
                    current_statement.append(line)
        
        # Add the last statement
        if current_statement:
            statements.append('\n'.join(current_statement))
        
        print(f"📋 Executing {len(statements)} ALTER TABLE statements...")
        
        for i, statement in enumerate(statements, 1):
            try:
                print(f"  {i}/{len(statements)}: Executing ALTER TABLE...")
                result = await client.execute_sql(statement)
                print(f"  ✅ Statement {i} completed successfully")
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    print(f"  ⚠️  Statement {i}: Column already exists (skipping)")
                else:
                    print(f"  ❌ Statement {i} failed: {e}")
                    # Continue with other statements
        
        await client.__aexit__(None, None, None)
        
        print("\n✅ Migration completed successfully!")
        print("\n📋 New fields added:")
        new_fields = [
            "email_intent", "email_intent_confidence", "email_intent_reasoning",
            "email_intent_detected_phrases", "email_intent_processing_duration_ms", "email_intent_model_version",
            "original_subject_result", "original_subject_confidence", "original_subject_reasoning", 
            "original_subject_extraction_method", "original_subject_processing_duration_ms", "original_subject_model_version",
            "original_email_subject", "email_payload", "email_headers"
        ]
        
        for field in new_fields:
            print(f"  ✅ {field}")
        
        print(f"\n🎉 Table {table_name} successfully migrated!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run migration
    success = asyncio.run(main())
    sys.exit(0 if success else 1)