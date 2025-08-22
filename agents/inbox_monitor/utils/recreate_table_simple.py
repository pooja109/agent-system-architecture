#!/usr/bin/env python3
"""
Simple Table Recreation Script
==============================

Drops and recreates the scenario tracking table with the new schema.
Uses direct SQL connection without complex settings dependencies.
"""

import os
import sys
from pathlib import Path
import asyncio

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to install databricks-sql-connector if not available
try:
    from databricks import sql
except ImportError:
    print("Installing databricks-sql-connector...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "databricks-sql-connector", "azure-identity", "azure-keyvault-secrets"])
    from databricks import sql

from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient


def main():
    print("🔧 Recreating Scenario Tracking Table")
    print("=" * 50)
    
    # Validate required environment variables
    required_vars = [
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH", 
        "DATABRICKS_CATALOG",
        "DATABRICKS_SCHEMA",
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID", 
        "AZURE_CLIENT_SECRET",
        "AZURE_KEY_VAULT_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        return False
    
    print("✅ Environment variables validated")
    
    # Get table details
    catalog = os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("DATABRICKS_SCHEMA") 
    table_suffix = os.getenv("DATABRICKS_TABLE_SUFFIX", "")
    table_name = f"{catalog}.{schema}.inbox_monitor_scenario_processing{table_suffix}"
    
    print(f"📋 Table to recreate: {table_name}")
    
    # Load schema SQL
    schema_file = project_root / "database" / "scenario_tracking_schema.sql"
    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Replace placeholders
        schema_sql = schema_sql.replace("{catalog}", catalog)
        schema_sql = schema_sql.replace("{schema}", schema)
        schema_sql = schema_sql.replace("{table_suffix}", table_suffix)
        
        print(f"✅ Loaded schema SQL ({len(schema_sql)} characters)")
        
    except FileNotFoundError:
        print(f"❌ Schema SQL file not found: {schema_file}")
        return False
    except Exception as e:
        print(f"❌ Failed to load schema SQL: {e}")
        return False
    
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
    
    try:
        print("\n🔑 Getting Databricks credentials from Key Vault...")
        
        # Get Databricks credentials from Key Vault
        credential = ClientSecretCredential(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET")
        )
        
        kv_client = SecretClient(
            vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
            credential=credential
        )
        
        # Get Databricks service principal credentials from Key Vault
        databricks_tenant_id = kv_client.get_secret("sales-engagement-service-principal-tenantid").value
        databricks_client_id = kv_client.get_secret("sales-engagement-service-principal-clientid").value
        databricks_client_secret = kv_client.get_secret("sales-engagement-service-principal-secretid").value
        
        print("✅ Retrieved Databricks credentials from Key Vault")
        
        # Create Databricks connection
        print("🔌 Connecting to Databricks...")
        connection = sql.connect(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
            http_path=os.getenv("DATABRICKS_HTTP_PATH"),
            auth_type="oauth",
            client_id=databricks_client_id,
            client_secret=databricks_client_secret
        )
        
        print("✅ Connected to Databricks")
        cursor = connection.cursor()
        
        # Step 1: Drop the existing table
        print(f"\n🗑️  Dropping existing table: {table_name}")
        drop_sql = f"DROP TABLE IF EXISTS {table_name}"
        cursor.execute(drop_sql)
        print("✅ Table dropped successfully")
        
        # Step 2: Create the new table with updated schema
        print(f"🔧 Creating table with new schema: {table_name}")
        
        # Replace CREATE TABLE IF NOT EXISTS with CREATE TABLE for clean creation
        create_sql = schema_sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")
        
        cursor.execute(create_sql)
        print("✅ Table created successfully with new schema")
        
        # Step 3: Verify the table was created
        print(f"🔍 Verifying table: {table_name}")
        verify_sql = f"DESCRIBE TABLE {table_name}"
        cursor.execute(verify_sql)
        
        columns = cursor.fetchall()
        column_names = [col[0] for col in columns]
        print(f"✅ Table verified: {len(columns)} columns found")
        
        # Check for key new fields
        new_fields_to_check = [
            'email_intent', 'email_intent_confidence', 'email_intent_reasoning',
            'original_subject_result', 'original_subject_confidence', 
            'email_payload', 'original_email_subject'
        ]
        
        found_new_fields = [f for f in new_fields_to_check if f in column_names]
        print(f"✅ New fields verified: {len(found_new_fields)}/{len(new_fields_to_check)}")
        
        # Check that old ai_ fields are NOT present (they should be replaced)
        old_fields = ['ai_intent', 'ai_confidence', 'ai_reasoning']
        old_still_present = [f for f in old_fields if f in column_names]
        
        if old_still_present:
            print(f"❌ Old ai_ fields still present: {old_still_present}")
            print("   This indicates the schema SQL still has old field names!")
        else:
            print("✅ Old ai_ fields successfully replaced with email_intent_ fields")
        
        # Show some of the new fields found
        print("\n📋 New fields found in table:")
        for field in found_new_fields:
            print(f"  ✅ {field}")
        
        cursor.close()
        connection.close()
        
        if len(found_new_fields) == len(new_fields_to_check) and not old_still_present:
            print("\n🎉 TABLE RECREATION SUCCESSFUL!")
            print("   • Old ai_* fields replaced with email_intent_* fields")
            print("   • New original subject extraction fields added")  
            print("   • New Graph API JSON fields added")
            print("   • All field names properly updated")
            print(f"\n🚀 Table {table_name} is ready for use!")
            return True
        else:
            print("\n⚠️  Table created but schema validation failed")
            if missing_fields := [f for f in new_fields_to_check if f not in column_names]:
                print(f"   Missing fields: {missing_fields}")
            if old_still_present:
                print(f"   Old fields still present: {old_still_present}")
            return False
            
    except Exception as e:
        print(f"❌ Table recreation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)