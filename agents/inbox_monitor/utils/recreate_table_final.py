#!/usr/bin/env python3
"""
Working Table Recreation Script
===============================

Drop and recreate the scenario tracking table using direct SQL execution.
This script works around dependency issues by using minimal imports.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project to path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Minimal imports to avoid dependency issues
import structlog
import time
from datetime import datetime, timezone

# Import only what we need for SQL execution
try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    from databricks.sdk.service.sql import ExecuteStatementRequest
    SDK_AVAILABLE = True
except ImportError:
    print("Installing databricks-sdk...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "databricks-sdk", "azure-identity", "azure-keyvault-secrets"])
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    from databricks.sdk.service.sql import ExecuteStatementRequest
    SDK_AVAILABLE = True

from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient


class SimpleDatabricksClient:
    """Simplified Databricks client for table operations."""
    
    def __init__(self):
        self.client = None
        self.warehouse_id = None
        
    async def connect(self):
        """Connect to Databricks using service principal from Key Vault."""
        try:
            print("🔑 Getting credentials from Key Vault...")
            
            # Get Key Vault credentials
            credential = ClientSecretCredential(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET")
            )
            
            kv_client = SecretClient(
                vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
                credential=credential
            )
            
            # Get Databricks service principal from Key Vault
            databricks_client_id = kv_client.get_secret("sales-engagement-service-principal-clientid").value
            databricks_client_secret = kv_client.get_secret("sales-engagement-service-principal-secretid").value
            
            print("✅ Retrieved Databricks credentials from Key Vault")
            
            # Extract warehouse ID from HTTP path
            self.warehouse_id = os.getenv("DATABRICKS_HTTP_PATH").split("/")[-1]
            
            # Create Databricks client
            config = Config(
                host=f"https://{os.getenv('DATABRICKS_SERVER_HOSTNAME')}",
                client_id=databricks_client_id,
                client_secret=databricks_client_secret
            )
            
            self.client = WorkspaceClient(config=config)
            print("✅ Connected to Databricks")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def execute_sql(self, sql_statement, description="Executing SQL"):
        """Execute SQL statement."""
        if not self.client:
            raise Exception("Not connected to Databricks")
        
        try:
            print(f"🔧 {description}")
            
            # Execute SQL statement
            response = self.client.statement_execution.execute_statement(
                warehouse_id=self.warehouse_id,
                statement=sql_statement,
                wait_timeout="300s"
            )
            
            # Wait for completion
            while response.status.state.value in ["PENDING", "RUNNING"]:
                time.sleep(2)
                response = self.client.statement_execution.get_statement(response.statement_id)
            
            if response.status.state.value == "SUCCEEDED":
                print(f"✅ {description} completed successfully")
                return response.result
            else:
                error_msg = response.status.error.message if response.status.error else "Unknown error"
                print(f"❌ {description} failed: {error_msg}")
                return None
                
        except Exception as e:
            print(f"❌ {description} failed: {e}")
            return None


async def main():
    print("🔧 Recreating Scenario Tracking Table")
    print("=" * 50)
    
    # Validate environment variables
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
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
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
        
    except Exception as e:
        print(f"❌ Failed to load schema SQL: {e}")
        return False
    
    # Connect to Databricks
    client = SimpleDatabricksClient()
    if not await client.connect():
        return False
    
    try:
        # Step 1: Drop the existing table
        drop_sql = f"DROP TABLE IF EXISTS {table_name}"
        result = await client.execute_sql(drop_sql, f"Dropping table {table_name}")
        if result is None:
            print("❌ Failed to drop table")
            return False
        
        # Step 2: Create the new table
        # Replace CREATE TABLE IF NOT EXISTS with CREATE TABLE for clean creation
        create_sql = schema_sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")
        
        result = await client.execute_sql(create_sql, f"Creating table {table_name}")
        if result is None:
            print("❌ Failed to create table")
            return False
        
        # Step 3: Verify the table
        verify_sql = f"DESCRIBE TABLE {table_name}"
        result = await client.execute_sql(verify_sql, f"Verifying table {table_name}")
        
        if result and hasattr(result, 'data_array'):
            columns = result.data_array
            column_names = [row[0] for row in columns if len(row) > 0]
            print(f"✅ Table verified: {len(columns)} columns found")
            
            # Check for key new fields
            new_fields_to_check = [
                'email_intent', 'email_intent_confidence', 'email_intent_reasoning',
                'original_subject_result', 'original_subject_confidence', 
                'email_payload', 'original_email_subject'
            ]
            
            found_new_fields = [f for f in new_fields_to_check if f in column_names]
            print(f"✅ New fields verified: {len(found_new_fields)}/{len(new_fields_to_check)}")
            
            # Check that old ai_ fields are NOT present
            old_fields = ['ai_intent', 'ai_confidence', 'ai_reasoning']
            old_still_present = [f for f in old_fields if f in column_names]
            
            if old_still_present:
                print(f"❌ Old ai_ fields still present: {old_still_present}")
            else:
                print("✅ Old ai_ fields successfully replaced with email_intent_ fields")
            
            # Show new fields found
            print("\n📋 New fields found in table:")
            for field in found_new_fields[:10]:  # Show first 10
                print(f"  ✅ {field}")
            
            if len(found_new_fields) == len(new_fields_to_check) and not old_still_present:
                print("\n🎉 TABLE RECREATION SUCCESSFUL!")
                print("   • Old ai_* fields replaced with email_intent_* fields")
                print("   • New original subject extraction fields added")  
                print("   • New Graph API JSON fields added")
                print("   • All field names properly updated")
                print(f"\n🚀 Table {table_name} is ready for use!")
                return True
            else:
                print("\n⚠️  Table created but some fields may be missing")
                if missing_fields := [f for f in new_fields_to_check if f not in column_names]:
                    print(f"   Missing fields: {missing_fields}")
                return len(found_new_fields) > 0  # Partial success
        else:
            print("❌ Could not verify table creation")
            return False
            
    except Exception as e:
        print(f"❌ Table operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)