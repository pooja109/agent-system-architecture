#!/usr/bin/env python3
"""
Debug Contact Lookup
====================

Script to debug the contact lookup table and check if rburgamy@tcls.club exists.
"""

import asyncio

import structlog
from config.settings import get_settings
from services.contact_lookup_service import ContactLookupService

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


async def debug_contact_lookup():
    """Debug the contact lookup functionality."""

    settings = get_settings()
    logger.info("Starting contact lookup debug")

    async with ContactLookupService(settings.databricks) as lookup_service:
        try:
            # Test connection and get table info
            logger.info("Testing connection...")
            connection_ok = await lookup_service.test_connection()
            logger.info(f"Connection test: {'✅ PASS' if connection_ok else '❌ FAIL'}")

            if not connection_ok:
                logger.error("Cannot proceed - connection failed")
                return

            # Get table structure info
            logger.info("Getting table information...")
            table_info = await lookup_service.get_table_info()

            if "error" in table_info:
                logger.error("Failed to get table info", error=table_info["error"])
                return

            logger.info("📋 Table Information:")
            logger.info(f"  Table: {table_info['table_name']}")
            logger.info("  Columns:")
            for col in table_info["columns"]:
                logger.info(f"    {col['name']}: {col['type']}")

            logger.info("  Sample data:")
            for i, row in enumerate(table_info["sample_data"][:3]):
                logger.info(f"    Row {i+1}: {row}")

            # Test specific email lookup
            test_email = "rburgamy@tcls.club"
            logger.info(f"Looking up specific email: {test_email}")

            result = await lookup_service.lookup_contact_by_email(test_email)

            logger.info("🔍 Lookup Result:")
            logger.info(f"  Email: {result.email}")
            logger.info(f"  Found: {result.found}")
            logger.info(f"  Account ID: {result.sf_account_id}")
            logger.info(f"  Contact ID: {result.sf_contact_id}")

            if not result.found:
                logger.warning("❌ Email not found in table!")

                # Try to find similar emails
                logger.info("Searching for similar emails in the table...")

                # Run a query to find emails that might be similar
                query = """
                SELECT EMAIL, SF_ACCOUNT_ID, SF_CONTACT_ID
                FROM snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t
                WHERE UPPER(EMAIL) LIKE '%BURGAMY%'
                   OR UPPER(EMAIL) LIKE '%TCLS%'
                   OR UPPER(EMAIL) LIKE '%CLUB%'
                LIMIT 10
                """

                with lookup_service.connection.cursor() as cursor:
                    cursor.execute(query)
                    similar_emails = cursor.fetchall()

                    if similar_emails:
                        logger.info("Found similar emails:")
                        for email_row in similar_emails:
                            logger.info(
                                f"  {email_row[0]} -> Account: {email_row[1]}, Contact: {email_row[2]}"
                            )
                    else:
                        logger.info("No similar emails found")

                        # Get a random sample of emails from the table
                        logger.info("Getting random sample of emails from table...")
                        sample_query = """
                        SELECT EMAIL, SF_ACCOUNT_ID, SF_CONTACT_ID
                        FROM snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t
                        LIMIT 10
                        """
                        cursor.execute(sample_query)
                        sample_emails = cursor.fetchall()

                        logger.info("Sample emails in table:")
                        for email_row in sample_emails:
                            logger.info(
                                f"  {email_row[0]} -> Account: {email_row[1]}, Contact: {email_row[2]}"
                            )
            else:
                logger.info("✅ Email found successfully!")

        except Exception as e:
            logger.error(f"Debug failed: {e}")
            import traceback

            traceback.print_exc()


async def main():
    """Main debug routine."""
    logger.info("🔍 Starting Contact Lookup Debug")
    logger.info("=" * 60)

    await debug_contact_lookup()

    logger.info("=" * 60)
    logger.info("✅ Debug completed")


if __name__ == "__main__":
    asyncio.run(main())
