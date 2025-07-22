#!/usr/bin/env python3
"""
Databricks View Inspector
=========================

Script to inspect the actual structure of the active_rep_pool_v view
and show what columns are available.
"""

import asyncio

import structlog
from config.settings import get_settings
from services.round_robin_service import RoundRobinService

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


async def inspect_active_rep_pool_view():
    """Inspect the structure and content of the active_rep_pool_v view."""

    settings = get_settings()
    logger.info("Inspecting active_rep_pool_v view structure...")

    async with RoundRobinService(settings.databricks) as service:
        try:
            # Get the view name
            view_name = f"`{settings.databricks.catalog}`.`{settings.databricks.schema_name}`.`active_rep_pool_v`"
            logger.info(f"Inspecting view: {view_name}")

            # First, describe the table structure
            describe_query = f"DESCRIBE {view_name}"

            with service.connection.cursor() as cursor:
                logger.info("Getting view structure...")
                cursor.execute(describe_query)
                columns = cursor.fetchall()

                logger.info("📋 View Structure:")
                logger.info("=" * 50)
                for col in columns:
                    col_name = col[0]
                    col_type = col[1]
                    col_nullable = col[2] if len(col) > 2 else "unknown"
                    logger.info(f"  {col_name:<20} {col_type:<15} (nullable: {col_nullable})")

                # Now get a sample of the data
                logger.info("\n📊 Sample Data (first 5 rows):")
                logger.info("=" * 50)

                sample_query = f"SELECT * FROM {view_name} LIMIT 5"
                cursor.execute(sample_query)
                sample_rows = cursor.fetchall()

                if sample_rows:
                    # Print column headers
                    col_names = [col[0] for col in columns]
                    header = " | ".join([f"{name:<15}" for name in col_names])
                    logger.info(header)
                    logger.info("-" * len(header))

                    # Print sample data
                    for row in sample_rows:
                        row_str = " | ".join([f"{val!s:<15}" for val in row])
                        logger.info(row_str)
                else:
                    logger.warning("No data found in the view")

                # Check for potential expert-related columns
                logger.info("\n🔍 Analysis:")
                logger.info("=" * 50)

                [col[0].lower() for col in columns]
                potential_mappings = {}

                # Look for expert ID
                for col in columns:
                    col_name = col[0]
                    col_lower = col_name.lower()
                    if any(keyword in col_lower for keyword in ["id", "psid", "user"]):
                        potential_mappings.setdefault("expert_id_candidates", []).append(col_name)

                # Look for expert email
                for col in columns:
                    col_name = col[0]
                    col_lower = col_name.lower()
                    if any(keyword in col_lower for keyword in ["email", "mail"]):
                        potential_mappings.setdefault("expert_email_candidates", []).append(
                            col_name
                        )

                # Look for expert name
                for col in columns:
                    col_name = col[0]
                    col_lower = col_name.lower()
                    if any(keyword in col_lower for keyword in ["name", "alias", "full"]):
                        potential_mappings.setdefault("expert_name_candidates", []).append(col_name)

                # Look for active status
                for col in columns:
                    col_name = col[0]
                    col_lower = col_name.lower()
                    if any(keyword in col_lower for keyword in ["active", "status", "enabled"]):
                        potential_mappings.setdefault("is_active_candidates", []).append(col_name)

                logger.info("Potential column mappings:")
                for mapping_type, candidates in potential_mappings.items():
                    logger.info(f"  {mapping_type}: {candidates}")

                if not potential_mappings:
                    logger.warning("Could not identify potential column mappings")
                    logger.info("Available columns:", col_names=[col[0] for col in columns])

        except Exception as e:
            logger.error(f"Failed to inspect view: {e}")
            raise


async def main():
    """Main inspection routine."""
    logger.info("🔍 Starting Databricks View Inspection")
    logger.info("=" * 60)

    try:
        await inspect_active_rep_pool_view()

        logger.info("\n✅ View inspection completed!")
        logger.info("\nNext steps:")
        logger.info("1. Update round_robin_service.py to use the correct column names")
        logger.info("2. Map the columns to our expected expert fields")
        logger.info("3. Re-run the setup: python main.py setup")

    except Exception as e:
        logger.error(f"❌ Inspection failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
