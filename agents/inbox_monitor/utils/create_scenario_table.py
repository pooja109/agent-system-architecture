#!/usr/bin/env python3
"""
Scenario Tracking Table Creator with Drop and Recreate
======================================================

Standalone script to drop and recreate the scenario processing tracking table in Databricks.
This ensures the table is created with the updated schema, replacing old ai_* fields 
with new email_intent_* fields and adding the new original subject and Graph API fields.

USAGE:
    python create_scenario_table.py

WARNING: This will DROP the existing table and recreate it with the new schema.
All existing data will be LOST. Make sure to backup any important data first.
"""

import asyncio
import sys
import os
from pathlib import Path

def main():
    print("🔧 Creating Scenario Tracking Table")
    print("=" * 50)
    
    # Find the inbox_monitor directory
    script_dir = Path(__file__).resolve().parent
    inbox_monitor_dir = script_dir.parent
    
    # Verify we're in the right location
    settings_file = inbox_monitor_dir / "config" / "settings.py"
    schema_file = inbox_monitor_dir / "database" / "scenario_tracking_schema.sql"
    
    if not settings_file.exists():
        print(f"❌ Error: Cannot find settings.py at {settings_file}")
        print("   Please run this script from the inbox_monitor directory:")
        print(f"   cd {inbox_monitor_dir}")
        print(f"   python utils/create_scenario_table.py")
        return False
    
    if not schema_file.exists():
        print(f"❌ Error: Cannot find schema file at {schema_file}")
        return False
    
    # Load schema SQL
    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        print(f"✅ Loaded schema SQL ({len(schema_sql.splitlines())} lines)")
    except Exception as e:
        print(f"❌ Failed to load schema SQL: {e}")
        return False
    
    # Check environment variables
    required_env_vars = [
        'DATABRICKS_SERVER_HOSTNAME',
        'DATABRICKS_HTTP_PATH',
        'DATABRICKS_CATALOG',
        'DATABRICKS_SCHEMA'
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print()
        print("Please set these environment variables and try again.")
        return False
    
    print("✅ Environment variables validated")
    
    # Display what would be created
    catalog = os.getenv('DATABRICKS_CATALOG')
    schema = os.getenv('DATABRICKS_SCHEMA')
    table_suffix = os.getenv('DATABRICKS_TABLE_SUFFIX', '')
    
    table_name = f"{catalog}.{schema}.inbox_monitor_scenario_processing{table_suffix}"
    print(f"📋 Table to create: {table_name}")
    
    # Show the SQL that would be executed (with placeholders replaced)
    formatted_sql = schema_sql.format(
        catalog=catalog,
        schema=schema,
        table_suffix=table_suffix
    )
    
    print()
    print("📄 SQL to execute:")
    print("-" * 50)
    # Show first few lines and last few lines
    lines = formatted_sql.split('\n')
    for i, line in enumerate(lines[:10]):
        print(f"{i+1:3d}: {line}")
    if len(lines) > 20:
        print("    ... (truncated) ...")
        for i, line in enumerate(lines[-5:], len(lines)-5):
            print(f"{i+1:3d}: {line}")
    
    print("-" * 50)
    print()
    
    # Ask for confirmation before dropping the table
    print("⚠️  WARNING: This will DROP the existing table and recreate it!")
    print("   All existing data will be PERMANENTLY LOST.")
    print()
    
    # Check for auto-confirmation via environment variable
    if os.getenv("AUTO_CONFIRM_DROP_TABLE") == "true":
        print("🤖 AUTO_CONFIRM_DROP_TABLE=true detected, proceeding automatically...")
        confirm = "yes"
    else:
        confirm = input("Do you want to proceed? (type 'yes' to confirm): ").strip().lower()
    
    if confirm != "yes":
        print("❌ Operation cancelled by user")
        return False
    
    print()
    print("🚀 Executing table drop and recreate...")
    
    # Now execute the actual drop and create operations
    try:
        # Import the Databricks client
        sys.path.insert(0, str(inbox_monitor_dir))
        from services.databricks_oauth_client import DatabricksOAuthClient
        
        # Run the async operation
        async def execute_table_operations():
            client = DatabricksOAuthClient()
            await client.__aenter__()
            
            try:
                # 1. Drop the existing table
                drop_sql = f"DROP TABLE IF EXISTS {table_name}"
                print(f"🗑️  Dropping existing table: {table_name}")
                await client.execute_sql(drop_sql)
                print("✅ Table dropped successfully")
                
                # 2. Create the new table with updated schema
                print(f"🔧 Creating table with new schema: {table_name}")
                
                # Replace CREATE TABLE IF NOT EXISTS with CREATE TABLE for clean creation
                create_sql = formatted_sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")
                
                await client.execute_sql(create_sql)
                print("✅ Table created successfully with new schema")
                
                # 3. Verify the table was created
                verify_sql = f"DESCRIBE TABLE {table_name}"
                result = await client.execute_sql(verify_sql)
                
                if 'data' in result:
                    columns = result['data']
                    print(f"✅ Table verified: {len(columns)} columns found")
                    
                    # Check for key new fields
                    column_names = [col[0] for col in columns]
                    new_fields_to_check = [
                        'email_intent', 'email_intent_confidence', 'original_subject_result', 
                        'email_payload', 'original_email_subject'
                    ]
                    
                    found_new_fields = [f for f in new_fields_to_check if f in column_names]
                    print(f"✅ New fields verified: {len(found_new_fields)}/{len(new_fields_to_check)}")
                    
                    # Check that old ai_ fields are NOT present (they should be replaced)
                    old_fields = ['ai_intent', 'ai_confidence', 'ai_reasoning']
                    old_still_present = [f for f in old_fields if f in column_names]
                    
                    if old_still_present:
                        print(f"⚠️  Old ai_ fields still present: {old_still_present}")
                    else:
                        print("✅ Old ai_ fields successfully replaced with email_intent_ fields")
                    
                    if len(found_new_fields) == len(new_fields_to_check) and not old_still_present:
                        print()
                        print("🎉 TABLE RECREATION SUCCESSFUL!")
                        print("   • Old ai_* fields replaced with email_intent_* fields")
                        print("   • New original subject extraction fields added")  
                        print("   • New Graph API JSON fields added")
                        print("   • All field names properly updated")
                        return True
                    else:
                        print("⚠️  Table created but some fields may be missing")
                        return False
                else:
                    print("❌ Could not verify table creation")
                    return False
                    
            finally:
                await client.__aexit__(None, None, None)
        
        # Execute the async operations
        success = asyncio.run(execute_table_operations())
        return success
        
    except Exception as e:
        print(f"❌ Table operation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)