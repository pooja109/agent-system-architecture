#!/usr/bin/env python3
"""
Minimal Table Recreation Script - No Dependencies
=================================================

Executes the table drop and recreate using minimal dependencies.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_sql_with_databricks_cli(sql_statement, description):
    """Run SQL using Databricks CLI."""
    print(f"🔧 {description}")
    
    # Create temp file with SQL
    temp_sql_file = f"/tmp/databricks_sql_{int(time.time())}.sql"
    with open(temp_sql_file, 'w') as f:
        f.write(sql_statement)
    
    try:
        # Use databricks CLI to execute SQL
        cmd = [
            "databricks", "sql", "execute",
            "--warehouse-id", os.getenv("DATABRICKS_HTTP_PATH").split("/")[-1],
            "--file", temp_sql_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False
    finally:
        # Clean up temp file
        if os.path.exists(temp_sql_file):
            os.remove(temp_sql_file)


def main():
    print("🔧 Minimal Table Recreation")
    print("=" * 40)
    
    # Check if databricks CLI is available
    try:
        result = subprocess.run(["databricks", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Databricks CLI not found. Please install it first:")
            print("   pip install databricks-cli")
            print("   databricks configure --token")
            return False
        print("✅ Databricks CLI available")
    except Exception as e:
        print(f"❌ Databricks CLI check failed: {e}")
        return False
    
    # Get table details
    catalog = os.getenv("DATABRICKS_CATALOG", "mld01_sandbox_de")
    schema = os.getenv("DATABRICKS_SCHEMA", "ai_garage") 
    table_suffix = os.getenv("DATABRICKS_TABLE_SUFFIX", "_dev")
    table_name = f"{catalog}.{schema}.inbox_monitor_scenario_processing{table_suffix}"
    
    print(f"📋 Table to recreate: {table_name}")
    
    # Warning and confirmation
    print("\n⚠️  WARNING: This will DROP the existing table and recreate it!")
    print("   All existing data will be PERMANENTLY LOST.")
    print()
    
    if os.getenv("AUTO_CONFIRM_DROP_TABLE") == "true":
        print("🤖 AUTO_CONFIRM_DROP_TABLE=true detected, proceeding automatically...")
        confirm = "yes"
    else:
        confirm = input("Do you want to proceed? (type 'yes' to confirm): ").strip().lower()
    
    if confirm != "yes":
        print("❌ Operation cancelled by user")
        return False
    
    # Step 1: Drop table
    drop_sql = f"DROP TABLE IF EXISTS {table_name};"
    if not run_sql_with_databricks_cli(drop_sql, f"Dropping table {table_name}"):
        return False
    
    # Step 2: Read and execute create table SQL
    schema_file = Path(__file__).parent.parent / "DROP_AND_CREATE_TABLE.sql"
    
    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        return False
    
    try:
        with open(schema_file, 'r') as f:
            create_sql = f.read()
        
        # Extract just the CREATE TABLE statement (skip DROP and other commands)
        lines = create_sql.split('\n')
        create_lines = []
        in_create = False
        
        for line in lines:
            if line.strip().startswith('CREATE TABLE'):
                in_create = True
            
            if in_create:
                create_lines.append(line)
                
            if in_create and line.strip().endswith(');'):
                break
        
        create_statement = '\n'.join(create_lines)
        
        if not run_sql_with_databricks_cli(create_statement, f"Creating table {table_name}"):
            return False
        
        # Step 3: Verify table
        verify_sql = f"DESCRIBE TABLE {table_name};"
        if run_sql_with_databricks_cli(verify_sql, f"Verifying table {table_name}"):
            print("\n🎉 TABLE RECREATION SUCCESSFUL!")
            print("   • Table dropped and recreated with new schema")
            print("   • Old ai_* fields replaced with email_intent_* fields")
            print("   • New original subject and Graph API fields added")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Failed to read schema file: {e}")
        return False


if __name__ == "__main__":
    import time
    success = main()
    sys.exit(0 if success else 1)