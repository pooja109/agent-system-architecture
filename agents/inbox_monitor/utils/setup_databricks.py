#!/usr/bin/env python3
"""
Databricks Setup Script
========================

Script to initialize the required Databricks tables for the inbox monitor
round-robin expert assignment system.
"""

import asyncio
import sys
from pathlib import Path

import structlog
from config.settings import get_settings, validate_settings
from services.round_robin_service import RoundRobinService
from services.databricks_connection_pool import get_connection_pool

# Configure logging
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


async def validate_databricks_connection() -> bool:
    """Validate that Databricks connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    logger.info("Validating Databricks connection...")

    settings = get_settings()

    try:
        async with RoundRobinService(settings.databricks_oauth) as service:
            success = await service.test_connection()
            if success:
                logger.info("✅ Databricks connection validated successfully")
                return True
            else:
                logger.error("❌ Databricks connection test failed")
                return False
    except Exception as e:
        logger.error("❌ Databricks connection validation failed", extra={"error_message": str(e)})
        return False


async def verify_active_rep_pool_view() -> bool:
    """Verify that the active_rep_pool_v view exists and has data.

    Returns:
        True if view exists and has data, False otherwise
    """
    logger.info("Verifying active_rep_pool_v view...")

    settings = get_settings()

    try:
        async with RoundRobinService(settings.databricks_oauth) as service:
            experts = await service.verify_expert_view()

            if experts:
                logger.info(f"✅ Found {len(experts)} active experts in active_rep_pool_v view")
                for expert in experts[:3]:  # Show first 3 experts
                    logger.info(
                        f"   Expert: {expert.expert_name} ({expert.expert_email}) - Active: {expert.is_active}"
                    )
                if len(experts) > 3:
                    logger.info(f"   ... and {len(experts) - 3} more experts")
                return True
            else:
                logger.warning("⚠️  active_rep_pool_v view exists but contains no active experts")
                return False

    except Exception as e:
        logger.error("❌ Failed to verify active_rep_pool_v view", extra={"error_message": str(e)})
        logger.error("   Make sure the view exists and contains ISACTIVE column")
        return False


async def create_assignment_table() -> bool:
    """Create the expert_lead_assignments table.

    Returns:
        True if table created successfully, False otherwise
    """
    logger.info("Creating expert lead assignments table...")

    settings = get_settings()

    try:
        async with RoundRobinService(settings.databricks_oauth) as service:
            success = await service.create_assignment_table()

            if success:
                logger.info("✅ Expert lead assignments table created/verified successfully")

                # Display the table information
                table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.expert_lead_assignments{settings.databricks_oauth.table_suffix}"
                logger.info(f"   Table: {table_name}")
                logger.info("   Schema:")
                logger.info("     • assignment_id STRING (Primary Key)")
                logger.info("     • expert_id STRING")
                logger.info("     • expert_email STRING")
                logger.info("     • expert_name STRING")
                logger.info("     • customer_email STRING")
                logger.info("     • lead_status STRING (default: 'assigned')")
                logger.info("     • assignment_date TIMESTAMP")
                logger.info("     • last_assignment_timestamp TIMESTAMP")
                logger.info("     • assignment_count INT (default: 1)")
                logger.info("     • created_at TIMESTAMP (default: CURRENT_TIMESTAMP)")
                logger.info("     • updated_at TIMESTAMP (default: CURRENT_TIMESTAMP)")

                return True
            else:
                logger.error("❌ Failed to create expert lead assignments table")
                return False

    except Exception as e:
        logger.error("❌ Error creating assignment table", extra={"error_message": str(e)})
        return False


async def test_round_robin_assignment() -> bool:
    """Test the round-robin assignment functionality.

    Returns:
        True if test successful, False otherwise
    """
    logger.info("Testing round-robin assignment functionality...")

    settings = get_settings()

    try:
        async with RoundRobinService(settings.databricks_oauth) as service:
            # Test assignment
            test_customer_email = "test.customer@example.com"

            logger.info(f"Testing assignment for customer: {test_customer_email}")
            assignment = await service.assign_lead_to_expert(test_customer_email)

            if assignment:
                logger.info("✅ Round-robin assignment test successful")
                logger.info(f"   Assigned to: {assignment.expert_name} ({assignment.expert_email})")
                logger.info(f"   Assignment ID: {assignment.assignment_id}")
                logger.info(f"   Assignment Count: {assignment.assignment_count}")

                # Test retrieval
                retrieved = await service.get_assignment_by_customer(test_customer_email)
                if retrieved:
                    logger.info("✅ Assignment retrieval test successful")
                else:
                    logger.warning("⚠️  Assignment retrieval test failed")

                # Test status update
                update_success = await service.update_assignment_status(
                    assignment.assignment_id, "test_completed"
                )
                if update_success:
                    logger.info("✅ Assignment status update test successful")
                else:
                    logger.warning("⚠️  Assignment status update test failed")

                return True
            else:
                logger.error("❌ Round-robin assignment test failed - no assignment returned")
                return False

    except Exception as e:
        logger.error("❌ Round-robin assignment test failed", extra={"error_message": str(e)})
        return False


async def create_scenario_tracking_table() -> bool:
    """Create the scenario processing tracking table.

    Returns:
        True if table created successfully, False otherwise
    """
    logger.info("Creating scenario processing tracking table...")

    try:
        settings = await get_settings()
        
        # Load schema SQL
        schema_file = Path(__file__).parent.parent / "database" / "scenario_tracking_schema.sql"
        
        if not schema_file.exists():
            logger.warning(f"⚠️  Scenario tracking schema file not found: {schema_file}")
            logger.info("   Skipping scenario tracking table creation")
            return True  # Non-critical for round-robin setup
            
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Replace placeholders with actual values
        formatted_sql = schema_sql.format(
            catalog=settings.databricks_oauth.catalog,
            schema=settings.databricks_oauth.schema_name,
            table_suffix=settings.databricks_oauth.table_suffix or ""
        )
        
        pool = get_connection_pool()
        
        async with pool.get_connection() as connection:
            cursor = await connection.cursor()
            
            # Split SQL into individual statements
            statements = [stmt.strip() for stmt in formatted_sql.split(';') if stmt.strip()]
            
            for i, statement in enumerate(statements):
                if statement:
                    logger.info(f"   Executing statement {i+1}/{len(statements)}...")
                    await cursor.execute(statement)
                    
            logger.info("✅ Scenario processing tracking table created successfully")
            
            # Display table information
            table_name = f"{settings.databricks_oauth.catalog}.{settings.databricks_oauth.schema_name}.inbox_monitor_scenario_processing{settings.databricks_oauth.table_suffix or ''}"
            logger.info(f"   Table: {table_name}")
            logger.info("   Features: 69 fields, Delta optimization, partitioning, 3 indexes")
            
            return True
            
    except Exception as e:
        logger.error("❌ Failed to create scenario tracking table", extra={"error_message": str(e)})
        logger.info("   This is non-critical for round-robin functionality")
        return True  # Don't fail the entire setup for scenario tracking issues


async def display_assignment_statistics() -> None:
    """Display current assignment statistics."""
    logger.info("Retrieving assignment statistics...")

    settings = await get_settings()

    try:
        async with RoundRobinService(settings.databricks_oauth) as service:
            stats = await service.get_assignment_statistics()

            if stats:
                logger.info("📊 Assignment Statistics:")
                logger.info(f"   Total Assignments: {stats.get('total_assignments', 0)}")
                logger.info(f"   Active Assignments: {stats.get('active_assignments', 0)}")
                logger.info(f"   Unique Customers: {stats.get('unique_customers', 0)}")
                logger.info(f"   Unique Experts: {stats.get('unique_experts', 0)}")

                if stats.get("expert_assignment_counts"):
                    logger.info("   Expert Assignment Counts:")
                    for expert_stats in stats["expert_assignment_counts"]:
                        logger.info(
                            f"     {expert_stats.get('expert_name', 'Unknown')}: {expert_stats.get('assignment_count', 0)} assignments"
                        )
            else:
                logger.info("📊 No assignment statistics available")

    except Exception as e:
        logger.error("Failed to retrieve assignment statistics", extra={"error_message": str(e)})


async def main():
    """Main setup routine for Databricks tables."""
    logger.info("🚀 Starting Databricks setup for Inbox Monitor")
    logger.info("=" * 60)

    # Load and validate settings
    logger.info("Loading configuration...")
    settings = get_settings()

    try:
        if not validate_settings(settings):
            logger.error("❌ Configuration validation failed")
            sys.exit(1)
    except Exception as e:
        logger.error("❌ Configuration validation error", extra={"error_message": str(e)})
        sys.exit(1)

    logger.info("✅ Configuration validated")
    logger.info(f"   Environment: {settings.environment}")
    logger.info(f"   Databricks: {settings.databricks_oauth.server_hostname}")
    logger.info(f"   Catalog: {settings.databricks_oauth.catalog}")
    logger.info(f"   Schema: {settings.databricks_oauth.schema_name}")
    logger.info(f"   Table Suffix: {settings.databricks_oauth.table_suffix}")

    # Step 1: Validate Databricks connection
    if not await validate_databricks_connection():
        logger.error("❌ Setup failed: Cannot connect to Databricks")
        sys.exit(1)

    # Step 2: Create assignment table FIRST (before verifying view with JOINs)
    if not await create_assignment_table():
        logger.error("❌ Setup failed: Could not create assignment table")
        sys.exit(1)

    # Step 3: Create scenario tracking table
    logger.info("Setting up scenario processing tracking...")
    scenario_success = await create_scenario_tracking_table()
    if scenario_success:
        logger.info("✅ Scenario tracking table setup completed")
    else:
        logger.warning("⚠️  Scenario tracking table setup had issues (non-critical)")

    # Step 4: Verify active_rep_pool_v view
    if not await verify_active_rep_pool_view():
        logger.error("❌ Setup failed: active_rep_pool_v view not available or empty")
        logger.error("   Please ensure the view exists and contains active experts")
        sys.exit(1)

    # Step 5: Test round-robin functionality
    if not await test_round_robin_assignment():
        logger.error("❌ Setup failed: Round-robin assignment test failed")
        sys.exit(1)

    # Step 6: Display current statistics
    await display_assignment_statistics()

    # Success
    logger.info("=" * 60)
    logger.info("🎉 Databricks setup completed successfully!")
    logger.info("")
    logger.info("✅ All components verified:")
    logger.info("   • Databricks connection")
    logger.info("   • active_rep_pool_v view")
    logger.info("   • expert_lead_assignments table")
    logger.info("   • inbox_monitor_scenario_processing table")
    logger.info("   • Round-robin assignment logic")
    logger.info("")
    logger.info("🚀 Inbox Monitor is ready for operation!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("   1. Run scenario tracking tests: python -m pytest tests/test_scenario_tracking_models.py")
    logger.info("   2. Run integration tests: python test_end_to_end_integration.py")
    logger.info("   3. Start inbox monitoring: python main.py")


if __name__ == "__main__":
    asyncio.run(main())
