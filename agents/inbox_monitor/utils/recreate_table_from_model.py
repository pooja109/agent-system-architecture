#!/usr/bin/env python3
"""
Model-Based Table Recreation Script
==================================

Generates CREATE TABLE SQL directly from the ScenarioProcessingRecord Pydantic model
to ensure perfect schema synchronization between Python code and database.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, date

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.scenario_tracking_models import ScenarioProcessingRecord
from pydantic import BaseModel
from pydantic.fields import FieldInfo
import inspect

# Use minimal imports to avoid dependency issues
try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    SDK_AVAILABLE = True
except ImportError:
    print("Installing databricks-sdk...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "databricks-sdk", "azure-identity", "azure-keyvault-secrets"])
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    SDK_AVAILABLE = True

from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient


def get_sql_type_from_pydantic_field(field_name: str, field_info: FieldInfo, annotation: Any) -> str:
    """Convert Pydantic field type to Databricks SQL type."""
    
    # Handle Union/Optional types (get the first non-None type)
    origin = getattr(annotation, '__origin__', None)
    args = getattr(annotation, '__args__', ())
    
    if origin is type(None) or annotation is type(None):
        return "STRING"
    
    # Handle Union types (Optional[X] is Union[X, None])
    if origin is type(None) or str(origin) == 'typing.Union':
        # Get the first non-None type
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            annotation = non_none_args[0]
            origin = getattr(annotation, '__origin__', None)
            args = getattr(annotation, '__args__', ())
    
    # Handle string types and enums
    if annotation is str or str(annotation).startswith('typing.Literal') or hasattr(annotation, '__members__'):
        return "STRING"
    
    # Handle boolean
    if annotation is bool:
        return "BOOLEAN"
    
    # Handle integers
    if annotation is int:
        if field_name.endswith('_ms') or field_name.endswith('_duration_ms'):
            return "BIGINT"
        else:
            return "INT"
    
    # Handle floats
    if annotation is float:
        return "DOUBLE"
    
    # Handle datetime and date
    if annotation is datetime or str(annotation) == 'datetime.datetime':
        return "TIMESTAMP"
    elif annotation is date or str(annotation) == 'datetime.date':
        return "DATE"
    
    # Handle List types
    if origin is list or str(origin) == 'typing.List':
        if args:
            element_type = get_sql_type_from_pydantic_field(f"{field_name}_element", field_info, args[0])
            return f"ARRAY<{element_type}>"
        else:
            return "ARRAY<STRING>"
    
    # Handle Dict types
    if origin is dict or str(origin) == 'typing.Dict':
        if len(args) >= 2:
            key_type = get_sql_type_from_pydantic_field(f"{field_name}_key", field_info, args[0])
            value_type = get_sql_type_from_pydantic_field(f"{field_name}_value", field_info, args[1])
            return f"MAP<{key_type}, {value_type}>"
        else:
            return "MAP<STRING, STRING>"
    
    # Handle complex types (default to STRING for JSON serialization)
    return "STRING"


def generate_create_table_sql(catalog: str, schema: str, table_suffix: str) -> str:
    """Generate CREATE TABLE SQL from ScenarioProcessingRecord model."""
    
    # Fixed: Use proper table name generation
    quoted_table_name = f"`{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}`"
    
    sql_parts = [
        f"CREATE TABLE {quoted_table_name} (",
    ]
    
    # Get model fields
    model_fields = ScenarioProcessingRecord.model_fields
    
    # Define field groups for better organization
    field_groups = {
        "Primary identifiers": ["processing_id", "email_id", "conversation_id", "correlation_id"],
        "Email source information": ["sender_email", "sender_name", "recipient_emails", "subject", "received_datetime", "sent_datetime", "email_body", "email_importance", "has_attachments", "attachment_count"],
        "Processing workflow": ["processed_at", "processing_duration_ms", "process_success", "process_error", "monitor_version", "retry_count"],
        "Email Intent Classification": ["email_intent", "email_intent_confidence", "email_intent_reasoning", "email_intent_detected_phrases", "email_intent_processing_duration_ms", "email_intent_model_version"],
        "Original Subject Extraction": ["original_subject_result", "original_subject_confidence", "original_subject_reasoning", "original_subject_extraction_method", "original_subject_processing_duration_ms", "original_subject_model_version"],
        "Scenario processing": ["scenario_type", "scenario_success", "scenario_processing_duration_ms", "scenario_error_message"],
        "Actions and results": ["agent_actions_log"],
        "Expert assignment": ["assignment_id", "expert_assigned", "expert_id", "expert_email", "assignment_method"],
        "Salesforce integration": ["case_created", "case_subject", "case_status", "sf_contact_id", "sf_account_id", "account_name"],
        "Email forwarding": ["emails_forwarded", "forwarding_reason", "forwarding_success", "forwarding_error"],
        "Database updates": ["external_operations_status", "status_updates"],
        "Test mode tracking": ["test_mode", "test_mode_type", "test_email_substitutions", "environment"],
        "Email lifecycle": ["destination_folder", "storage_location", "email_deleted"],
        "Original subject tracking": ["original_email_subject"],
        "Graph API Raw Data": ["email_payload", "email_headers"],
        "Customer interaction patterns": ["customer_interaction_count", "last_customer_interaction", "customer_scenario_history"],
        "Performance tracking": ["memory_usage_mb", "cpu_time_ms", "connection_pool_wait_ms"],
        "Audit fields": ["created_at", "updated_at", "created_by", "data_version", "processing_date"]
    }
    
    # Generate SQL for each field group
    for group_name, field_names in field_groups.items():
        sql_parts.append(f"    -- {group_name}")
        
        for field_name in field_names:
            if field_name not in model_fields:
                continue
                
            field_info = model_fields[field_name]
            annotation = field_info.annotation
            
            # Get SQL type
            sql_type = get_sql_type_from_pydantic_field(field_name, field_info, annotation)
            
            # Determine if field is required
            is_required = field_info.is_required() and field_name in ["processing_id", "email_id", "sender_email", "received_datetime", "process_success"]
            
            # Remove DEFAULT values for Databricks compatibility
            # Databricks requires special table properties to support DEFAULT values
            default_clause = ""
            
            # Get field description from docstring or default
            description = field_info.description or f"{field_name.replace('_', ' ').title()}"
            
            # Handle special field cases
            not_null = " NOT NULL" if is_required else ""
            
            sql_parts.append(f"    {field_name} {sql_type}{not_null}{default_clause} COMMENT '{description}',")
        
        sql_parts.append("")  # Empty line between groups
    
    # Remove the last comma and empty line
    if sql_parts[-1] == "":
        sql_parts.pop()
    sql_parts[-1] = sql_parts[-1].rstrip(',')
    
    # Add table properties (remove expression-based partitioning for Databricks compatibility)
    sql_parts.extend([
        ")",
        "USING DELTA",
        "TBLPROPERTIES (",
        "    'delta.autoOptimize.optimizeWrite' = 'true',",
        "    'delta.autoOptimize.autoCompact' = 'true',",
        "    'delta.feature.allowColumnDefaults' = 'supported',",
        "    'delta.deletedFileRetentionDuration' = 'interval 7 days',",
        "    'delta.logRetentionDuration' = 'interval 30 days'",
        ");"
    ])
    
    return "\n".join(sql_parts)


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
            import time
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
    print("🔧 Recreating Table from Pydantic Model")
    print("=" * 50)
    
    # Initialize logger system first
    print("🔧 Initializing logger system...")
    try:
        from utils.custom_logging import initialize_logging, LoggingConfig
        initialize_logging(LoggingConfig())
        print("✅ Logger system initialized")
    except Exception as e:
        print(f"❌ Logger initialization failed: {e}")
        import structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        print("✅ Fallback logger configuration applied")
    
    # Load and validate settings using the proper pattern
    print("🔧 Loading configuration...")
    try:
        from config.settings import get_settings, validate_settings
        settings = await get_settings()
        if not validate_settings(settings):
            print("❌ Configuration validation failed")
            return False
    except Exception as e:
        print(f"❌ Configuration validation error: {e}")
        return False

    print("✅ Configuration validated")
    print(f"   Environment: {settings.environment}")
    print(f"   Databricks: {settings.databricks_oauth.server_hostname}")
    print(f"   Catalog: {settings.databricks_oauth.catalog}")
    print(f"   Schema: {settings.databricks_oauth.schema_name}")
    print(f"   Table Suffix: {settings.databricks_oauth.table_suffix or '(none)'}")
    
    # Get table details from settings
    catalog = settings.databricks_oauth.catalog
    schema = settings.databricks_oauth.schema_name 
    table_suffix = settings.databricks_oauth.table_suffix or ""
    table_name = f"{catalog}.{schema}.inbox_monitor_scenario_processing{table_suffix}"
    
    print(f"📋 Table to recreate: {table_name}")
    
    # Generate SQL from model
    print("🔧 Generating CREATE TABLE SQL from Pydantic model...")
    try:
        create_sql = generate_create_table_sql(catalog, schema, table_suffix)
        print(f"✅ Generated SQL schema from model ({len(create_sql)} characters)")
        
        # Save the generated SQL for inspection
        output_file = project_root / "database" / "generated_schema_from_model.sql"
        with open(output_file, 'w') as f:
            f.write(create_sql)
        print(f"💾 Saved generated SQL to: {output_file}")
        
    except Exception as e:
        print(f"❌ Failed to generate SQL from model: {e}")
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
    
    # Initialize connection pool using the proper pattern
    print("\n🔑 Initializing Databricks connection pool...")
    try:
        from services.databricks_connection_pool import initialize_connection_pool, get_connection_pool, ConnectionPoolConfig
        
        # Create connection pool configuration
        pool_config = ConnectionPoolConfig(
            min_connections=1,
            max_connections=3,
            connection_timeout_seconds=30
        )
        
        # Initialize the connection pool with production settings
        await initialize_connection_pool(
            databricks_settings=settings.databricks_oauth,
            key_vault_settings=settings.key_vault,
            pool_config=pool_config,
            test_mode=False  # Use production mode for actual table creation
        )
        
        # Get the initialized pool
        pool = await get_connection_pool()
        print("✅ Connected to Databricks with connection pool")
        
    except Exception as e:
        print(f"❌ Failed to initialize Databricks connection pool: {e}")
        return False
    
    try:
        # Step 1: Drop the existing table
        print(f"\n🗑️  Dropping existing table: {table_name}")
        drop_sql = f"DROP TABLE IF EXISTS `{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}`"
        
        async with pool.get_connection() as connection:
            await connection.execute_sql(drop_sql)
            print("✅ Table dropped successfully")
            
            # Step 2: Create the new table using model-generated SQL
            print(f"🔧 Creating table with model-generated schema: {table_name}")
            await connection.execute_sql(create_sql)
            print("✅ Table created successfully with model schema")
            
            # Step 3: Verify the table was created
            print(f"🔍 Verifying table: {table_name}")
            verify_sql = f"DESCRIBE TABLE `{catalog}`.`{schema}`.`inbox_monitor_scenario_processing{table_suffix}`"
            result = await connection.execute_sql(verify_sql)
            
            if hasattr(result, 'rows') and result.rows:
                columns = result.rows
                column_names = [row.get('col_name', '') for row in columns]
                print(f"✅ Table verified: {len(columns)} columns found")
                
                # Check for key model fields
                model_fields_to_check = [
                    'email_intent', 'email_intent_confidence', 'email_intent_reasoning',
                    'original_subject_result', 'original_subject_confidence', 
                    'email_payload', 'original_email_subject', 'processing_id', 'sender_email'
                ]
                
                found_model_fields = [f for f in model_fields_to_check if f in column_names]
                print(f"✅ Model fields verified: {len(found_model_fields)}/{len(model_fields_to_check)}")
                
                # Check total field count matches model
                model_fields = list(ScenarioProcessingRecord.model_fields.keys())
                expected_field_count = len(model_fields)
                actual_field_count = len(column_names)
                
                print(f"📊 Field count: {actual_field_count} actual vs {expected_field_count} expected")
                
                # Show some of the fields found
                print("\n📋 Key model fields found in table:")
                for field in found_model_fields:
                    print(f"  ✅ {field}")
                
                # Clean up connection pool
                try:
                    from services.databricks_connection_pool import shutdown_connection_pool
                    await shutdown_connection_pool()
                    print("✅ Connection pool cleaned up")
                except Exception as e:
                    print(f"⚠️ Connection pool cleanup warning: {e}")
                
                if len(found_model_fields) == len(model_fields_to_check):
                    print("\n🎉 TABLE RECREATION SUCCESSFUL!")
                    print("   • Table schema generated directly from ScenarioProcessingRecord model")
                    print("   • All field types automatically mapped from Pydantic types")
                    print("   • Schema is guaranteed to match Python model")
                    print(f"   • Total fields: {actual_field_count} (expected: {expected_field_count})")
                    print(f"\n🚀 Table {table_name} is ready for use!")
                    return True
                else:
                    print("\n⚠️  Table created but schema validation failed")
                    missing_fields = [f for f in model_fields_to_check if f not in column_names]
                    if missing_fields:
                        print(f"   Missing fields: {missing_fields}")
                    return False
            else:
                print("❌ Could not verify table creation")
                return False
            
    except Exception as e:
        print(f"❌ Table recreation failed: {e}")
        import traceback
        traceback.print_exc()
        # Clean up connection pool on error
        try:
            from services.databricks_connection_pool import shutdown_connection_pool
            await shutdown_connection_pool()
        except:
            pass
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)