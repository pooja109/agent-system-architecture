#!/usr/bin/env python3
"""
Scenario Tracking Setup Script
==============================

Standalone script to create and setup the scenario processing tracking table 
in Databricks for comprehensive email processing analytics.

USAGE:
    # Run from inbox_monitor directory (recommended):
    cd /path/to/agents/inbox_monitor
    python utils/setup_scenario_tracking.py
    
    # Or run from any directory:
    python /path/to/agents/inbox_monitor/utils/setup_scenario_tracking.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Ensure we can import from the inbox_monitor directory regardless of where script is run
script_dir = Path(__file__).resolve().parent
inbox_monitor_dir = script_dir.parent

# Check if we're in the right directory structure
if not (inbox_monitor_dir / "config" / "settings.py").exists():
    print("❌ Error: This script must be run from the inbox_monitor project structure.")
    print(f"   Expected to find: {inbox_monitor_dir / 'config' / 'settings.py'}")
    print("   Current location:", script_dir)
    print()
    print("USAGE:")
    print("   cd /path/to/agents/inbox_monitor")
    print("   python utils/setup_scenario_tracking.py")
    print()
    sys.exit(1)

# Add the inbox_monitor directory to Python path
sys.path.insert(0, str(inbox_monitor_dir))

# Load .env file from the root directory (where Databricks config is located)
root_env_file = inbox_monitor_dir.parent.parent / ".env"
if root_env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(root_env_file)
    print(f"✅ Loaded environment variables from {root_env_file}")
else:
    print(f"⚠️  .env file not found at {root_env_file}")

# Change working directory to inbox_monitor for proper module imports
os.chdir(inbox_monitor_dir)

import structlog
from config.settings import get_settings, validate_settings

# Configure logging for standalone script
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Import connection pool after logging is configured
from services.databricks_connection_pool import get_connection_pool


async def validate_databricks_connection() -> bool:
    """Validate that Databricks connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    logger.info("Validating Databricks connection...")

    try:
        settings = await get_settings()
        
        # Import and initialize connection pool properly
        from services.databricks_connection_pool import initialize_connection_pool, get_connection_pool, ConnectionPoolConfig
        
        # Create connection pool configuration
        pool_config = ConnectionPoolConfig(
            min_connections=1,
            max_connections=3,
            connection_timeout_seconds=30
        )
        
        # Initialize the connection pool with correct parameters (not in test mode for real table creation)
        await initialize_connection_pool(
            databricks_settings=settings.databricks_oauth,
            key_vault_settings=settings.key_vault,
            pool_config=pool_config,
            test_mode=False  # We want to create real table, not mock
        )
        
        # Get the initialized pool
        pool = await get_connection_pool()
        
        try:
            async with pool.get_connection() as connection:
                logger.info(f"Got connection from pool: {type(connection)}")
                
                # Test basic connectivity using OAuth client API
                result = await connection.execute_sql("SELECT 1 as test")
                
                logger.info(f"Connection test result: {result}")
                logger.info(f"Result rows: {result.rows}")
                logger.info(f"Result columns: {result.columns}")
                
                if result.rows and len(result.rows) > 0:
                    test_value = result.rows[0].get('test')
                    # Handle both string and integer values
                    if test_value == 1 or test_value == '1':
                        logger.info("✅ Databricks connection validated successfully")
                        return True
                    else:
                        logger.error(f"❌ Databricks connection test failed - unexpected value: {test_value}")
                        return False
                else:
                    logger.error(f"❌ Databricks connection test failed - no rows returned. Rows: {result.rows}")
                    return False
                    
        except Exception as conn_error:
            logger.error(f"❌ Error during connection test: {conn_error}")
            return False
                
    except Exception as e:
        logger.error("❌ Databricks connection validation failed", error=str(e))
        return False


def load_schema_sql() -> str:
    """Load the scenario tracking schema SQL from file.
    
    Returns:
        SQL schema string with placeholders
    """
    try:
        schema_file = Path(__file__).parent.parent / "database" / "scenario_tracking_schema.sql"
        
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")
            
        with open(schema_file, 'r') as f:
            return f.read()
            
    except Exception as e:
        logger.error("❌ Failed to load schema SQL file", error=str(e))
        raise


async def create_scenario_tracking_table() -> bool:
    """Create the scenario processing tracking table.

    Returns:
        True if table created successfully, False otherwise
    """
    logger.info("Creating scenario processing tracking table...")

    try:
        settings = await get_settings()
        
        # Load schema SQL
        schema_sql = load_schema_sql()
        
        # Replace placeholders with actual values
        formatted_sql = schema_sql.format(
            catalog=settings.databricks_oauth.catalog,
            schema=settings.databricks_oauth.schema_name,
            table_suffix=settings.databricks_oauth.table_suffix or ""
        )
        
        # Get the already initialized pool
        pool = await get_connection_pool()
        
        async with pool.get_connection() as connection:
            # Split SQL into individual statements (handle multiple statements)
            statements = [stmt.strip() for stmt in formatted_sql.split(';') if stmt.strip()]
            
            for i, statement in enumerate(statements):
                if statement:
                    logger.info(f"Executing statement {i+1}/{len(statements)}...")
                    await connection.execute_sql(statement)
                    
            logger.info("✅ Scenario processing tracking table created successfully")
            
            # Display table information
            table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.inbox_monitor_scenario_processing{settings.databricks_oauth.table_suffix or ''}"
            logger.info(f"   Table: {table_name}")
            logger.info("   Features:")
            logger.info("     • 69 fields for comprehensive scenario tracking")
            logger.info("     • Delta table with auto-optimization enabled")
            logger.info("     • Date-based partitioning for query performance")  
            logger.info("     • ZORDER optimization on key fields")
            logger.info("     • 3 strategic indexes for common query patterns")
            logger.info("     • PII handling with field length limits")
            logger.info("     • Comprehensive audit trail capabilities")
            
            return True
            
    except Exception as e:
        logger.error("❌ Failed to create scenario tracking table", error=str(e))
        return False


async def verify_table_structure() -> bool:
    """Verify the scenario tracking table structure.

    Returns:
        True if table structure is correct, False otherwise
    """
    logger.info("Verifying scenario tracking table structure...")

    try:
        settings = await get_settings()
        pool = await get_connection_pool()
        
        table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.inbox_monitor_scenario_processing{settings.databricks_oauth.table_suffix or ''}"
        
        async with pool.get_connection() as connection:
            # Check table exists and get column count
            result = await connection.execute_sql(f"DESCRIBE {table_name}")
            columns = result.rows
            
            if not columns:
                logger.error("❌ Table structure verification failed - no columns found")
                return False
                
            column_count = len(columns)
            logger.info(f"✅ Table structure verified: {column_count} columns found")
            
            # Verify key columns exist
            column_names = [col.get('col_name', '').lower() for col in columns]
            required_columns = [
                'process_id', 'email_id', 'sender_email', 'received_datetime',
                'process_success', 'scenario_type', 'created_at'
            ]
            
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                logger.error(f"❌ Missing required columns: {missing_columns}")
                return False
                
            logger.info("✅ All required columns present")
            
            # Check table properties
            prop_result = await connection.execute_sql(f"SHOW TBLPROPERTIES {table_name}")
            properties = prop_result.rows
            
            property_dict = {prop.get('key', ''): prop.get('value', '') for prop in properties}
            
            # Verify Delta table properties
            delta_features = [
                'delta.autoOptimize.optimizeWrite',
                'delta.autoOptimize.autoCompact'
            ]
            
            for feature in delta_features:
                if property_dict.get(feature) == 'true':
                    logger.info(f"   ✓ {feature} enabled")
                else:
                    logger.warning(f"   ⚠ {feature} not enabled")
                    
            return True
            
    except Exception as e:
        logger.error("❌ Table structure verification failed", error=str(e))
        return False


async def test_table_operations() -> bool:
    """Test basic table operations (insert/select).

    Returns:
        True if operations successful, False otherwise
    """
    logger.info("Testing scenario tracking table operations...")

    try:
        settings = await get_settings()
        pool = await get_connection_pool()
        
        table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.inbox_monitor_scenario_processing{settings.databricks_oauth.table_suffix or ''}"
        
        async with pool.get_connection() as connection:
            # Test insert operation with minimal required fields
            from uuid import uuid4
            from datetime import datetime, timezone
            
            test_process_id = str(uuid4())
            test_email_id = str(uuid4())
            
            insert_sql = f"""
            INSERT INTO {table_name} (
                process_id, email_id, sender_email, received_datetime, process_success
            ) VALUES (
                '{test_process_id}', '{test_email_id}', 'test@setup.com', CURRENT_TIMESTAMP(), true
            )
            """
            
            await connection.execute_sql(insert_sql)
            logger.info("✅ Test insert operation successful")
            
            # Test select operation
            select_sql = f"""
            SELECT process_id, sender_email, process_success 
            FROM {table_name} 
            WHERE process_id = '{test_process_id}'
            """
            
            result = await connection.execute_sql(select_sql)
            rows = result.rows
            
            if rows and len(rows) == 1:
                logger.info("✅ Test select operation successful")
                row = rows[0]
                sender_email = row.get('sender_email', 'Unknown')
                process_success = row.get('process_success', False)
                logger.info(f"   Retrieved record: {sender_email} (success: {process_success})")
            else:
                logger.error("❌ Test select operation failed - record not found")
                return False
            
            # Clean up test record
            delete_sql = f"DELETE FROM {table_name} WHERE process_id = '{test_process_id}'"
            await connection.execute_sql(delete_sql)
            logger.info("✅ Test cleanup completed")
            
            return True
            
    except Exception as e:
        logger.error("❌ Table operations test failed", error=str(e))
        return False


async def display_table_statistics() -> None:
    """Display current table statistics."""
    logger.info("Retrieving scenario tracking table statistics...")

    try:
        settings = await get_settings()
        pool = await get_connection_pool()
        
        table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.inbox_monitor_scenario_processing{settings.databricks_oauth.table_suffix or ''}"
        
        async with pool.get_connection() as connection:
            # Get record count
            count_result = await connection.execute_sql(f"SELECT COUNT(*) as record_count FROM {table_name}")
            record_count = count_result.rows[0].get('record_count', 0) if count_result.rows else 0
            
            # Get table info
            table_info_result = await connection.execute_sql(f"SHOW TABLE EXTENDED LIKE '{table_name}'")
            table_info = table_info_result.rows
            
            logger.info("📊 Scenario Tracking Table Statistics:")
            logger.info(f"   Table Name: {table_name}")
            logger.info(f"   Record Count: {record_count}")
            
            if table_info:
                # Extract table size info if available
                for info in table_info:
                    if 'Statistics' in str(info):
                        logger.info(f"   Table Info: {info}")
                        
    except Exception as e:
        logger.error("Failed to retrieve table statistics", error=str(e))


async def main():
    """Main setup routine for scenario tracking table."""
    logger.info("🚀 Starting Scenario Tracking Table Setup")
    logger.info("=" * 60)

    # Load and validate settings
    logger.info("Loading configuration...")
    try:
        settings = await get_settings()
        if not validate_settings(settings):
            logger.error("❌ Configuration validation failed")
            sys.exit(1)
    except Exception as e:
        logger.error("❌ Configuration validation error", error=str(e))
        sys.exit(1)

    logger.info("✅ Configuration validated")
    logger.info(f"   Environment: {settings.environment}")
    logger.info(f"   Databricks: {settings.databricks_oauth.server_hostname}")
    logger.info(f"   Catalog: {settings.databricks_oauth.catalog}")
    logger.info(f"   Schema: {settings.databricks_oauth.schema_name}")
    logger.info(f"   Table Suffix: {settings.databricks_oauth.table_suffix or '(none)'}")
    logger.info(f"   Scenario Tracking Enabled: {settings.scenario_tracking.enabled}")

    try:
        # Step 1: Validate Databricks connection (this initializes the connection pool)
        if not await validate_databricks_connection():
            logger.error("❌ Setup failed: Cannot connect to Databricks")
            sys.exit(1)

        # Step 2: Create scenario tracking table
        if not await create_scenario_tracking_table():
            logger.error("❌ Setup failed: Could not create scenario tracking table")
            sys.exit(1)

        # Step 3: Verify table structure
        if not await verify_table_structure():
            logger.error("❌ Setup failed: Table structure verification failed")
            sys.exit(1)

        # Step 4: Test table operations
        if not await test_table_operations():
            logger.error("❌ Setup failed: Table operations test failed")
            sys.exit(1)

        # Step 5: Display table statistics
        await display_table_statistics()

        # Success
        logger.info("=" * 60)
        logger.info("🎉 Scenario Tracking Table Setup Completed Successfully!")
        logger.info("")
        logger.info("✅ All components verified:")
        logger.info("   • Databricks connection")
        logger.info("   • Scenario processing tracking table")
        logger.info("   • Table structure and properties")
        logger.info("   • Basic CRUD operations")
        logger.info("")
        logger.info("🚀 Scenario Tracking is ready for operation!")
        logger.info("")
        
        table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.inbox_monitor_scenario_processing{settings.databricks_oauth.table_suffix or ''}"
        logger.info("📋 Table Details:")
        logger.info(f"   Full Table Name: {table_name}")
        logger.info(f"   Fields: 69 comprehensive tracking fields")
        logger.info(f"   Partitioning: By processing date")
        logger.info(f"   Optimization: ZORDER by sender_email, scenario_type, processed_at")
        logger.info("")
        logger.info("🔧 Next steps:")
        logger.info("   1. Verify table in Databricks SQL UI")
        logger.info("   2. Run scenario tracking tests: python -m pytest tests/test_scenario_tracking_models.py")
        logger.info("   3. Start using scenario tracking in email processing pipeline")
        
    finally:
        # Cleanup connection pool
        try:
            from services.databricks_connection_pool import shutdown_connection_pool
            await shutdown_connection_pool()
            logger.info("✅ Connection pool cleaned up")
        except Exception as e:
            logger.warning("⚠️ Connection pool cleanup warning", error=str(e))


if __name__ == "__main__":
    asyncio.run(main())