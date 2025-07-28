"""
Contact Lookup Service
======================

Service for looking up Salesforce account and contact IDs from Databricks
based on email addresses.
"""

from typing import Any

import structlog
from databricks import sql
from databricks.sql.client import Connection
from pydantic import BaseModel, Field

try:
    from config.settings import DatabricksSettings, TestModeSettings
except ImportError:
    from ..config.settings import DatabricksSettings, TestModeSettings


class ContactLookupResult(BaseModel):
    """Result of contact lookup operation."""

    email: str = Field(..., description="Email address searched")
    sf_account_id: str | None = Field(None, description="Salesforce Account ID")
    sf_contact_id: str | None = Field(None, description="Salesforce Contact ID")
    found: bool = Field(..., description="Whether contact was found")


class ContactLookupService:
    """Service for looking up contact and account IDs from Databricks."""

    def __init__(
        self, settings: DatabricksSettings, test_mode_settings: TestModeSettings | None = None
    ):
        """Initialize the contact lookup service.

        Args:
            settings: Databricks configuration settings
            test_mode_settings: Test mode configuration for email substitution
        """
        self.settings = settings
        self.test_mode_settings = test_mode_settings
        self.logger = structlog.get_logger(__name__)
        self.connection: Connection | None = None

        # Table path for contact lookup
        self._lookup_table = "snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t"

    async def __aenter__(self) -> "ContactLookupService":
        """Async context manager entry."""
        if not self.connection:
            await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> bool:
        """Connect to Databricks.

        Returns:
            True if connection successful, False otherwise
        """
        if self.connection is not None:
            return True
            
        try:
            self.connection = sql.connect(
                server_hostname=self.settings.server_hostname,
                http_path=self.settings.http_path,
                access_token=self.settings.access_token,
                # Optimize connection settings
                _user_agent_entry="inbox_monitor_contact_lookup/2.1.0",
                # Add connection pooling settings
                catalog=None,  # Will be set per query if needed
                schema=None   # Will be set per query if needed
            )
            self.logger.info("Connected to Databricks for contact lookup service")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Databricks: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Databricks."""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("Disconnected from Databricks contact lookup service")
            except Exception as e:
                self.logger.error(f"Error disconnecting from Databricks: {e}")
            finally:
                self.connection = None

    async def lookup_contact_by_email(self, email: str) -> ContactLookupResult:
        """Lookup Salesforce account and contact IDs by email address.

        Args:
            email: Email address to search for

        Returns:
            ContactLookupResult with account and contact IDs if found

        Raises:
            Exception: If lookup fails
        """
        try:
            if self.connection is None:
                success = await self.connect()
                if not success:
                    raise RuntimeError("Database connection not established")

            # Handle test mode email substitution
            lookup_email = email
            original_email = email

            if (
                self.test_mode_settings
                and self.test_mode_settings.enabled
                and email.lower() == self.test_mode_settings.test_sender_email.lower()
            ):
                lookup_email = self.test_mode_settings.target_salesforce_email
                self.logger.info(
                    "Test mode enabled: substituting email for lookup",
                    original_email=original_email,
                    lookup_email=lookup_email,
                    test_mode=True,
                )

            # Optimized query with explicit column selection and index hint
            query = f"""
            SELECT /*+ INDEX(EMAIL) */
                EMAIL,
                SF_ACCOUNT_ID,
                SF_CONTACT_ID
            FROM {self._lookup_table}
            WHERE UPPER(EMAIL) = UPPER(?)
            LIMIT 1
            """

            self.logger.info(
                "Looking up contact information",
                email=lookup_email,
                original_email=original_email if lookup_email != original_email else None,
                table=self._lookup_table,
            )

            with self.connection.cursor() as cursor:
                cursor.execute(query, [lookup_email])
                row = cursor.fetchone()

                if row:
                    # Contact found
                    row[0]
                    sf_account_id = row[1] if row[1] else None
                    sf_contact_id = row[2] if row[2] else None

                    # Return result with original email (for test mode transparency)
                    result = ContactLookupResult(
                        email=original_email,
                        sf_account_id=sf_account_id,
                        sf_contact_id=sf_contact_id,
                        found=True,
                    )

                    self.logger.info(
                        "Contact lookup successful",
                        email=original_email,
                        lookup_email=lookup_email if lookup_email != original_email else None,
                        sf_account_id=sf_account_id,
                        sf_contact_id=sf_contact_id,
                        test_mode_substitution=lookup_email != original_email,
                    )

                    return result
                else:
                    # Contact not found
                    result = ContactLookupResult(
                        email=original_email, sf_account_id=None, sf_contact_id=None, found=False
                    )

                    self.logger.warning(
                        "Contact not found in lookup table",
                        email=original_email,
                        lookup_email=lookup_email if lookup_email != original_email else None,
                        table=self._lookup_table,
                        test_mode_substitution=lookup_email != original_email,
                    )

                    return result

        except Exception as e:
            self.logger.error("Failed to lookup contact information", email=email, error=str(e))
            raise

    async def test_connection(self) -> bool:
        """Test the connection to Databricks and verify table access.

        Returns:
            True if connection and table access successful, False otherwise
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Test table access with a simple count query
            test_query = f"SELECT COUNT(*) as record_count FROM {self._lookup_table} LIMIT 1"

            with self.connection.cursor() as cursor:
                cursor.execute(test_query)
                result = cursor.fetchone()

                if result:
                    record_count = result[0]
                    self.logger.info(
                        "Contact lookup table access successful",
                        table=self._lookup_table,
                        record_count=record_count,
                    )
                    return True
                else:
                    self.logger.error("No result from table access test")
                    return False

        except Exception as e:
            self.logger.error(
                "Contact lookup table access test failed", table=self._lookup_table, error=str(e)
            )
            return False

    async def get_table_info(self) -> dict[str, Any]:
        """Get information about the lookup table structure.

        Returns:
            Dictionary with table information
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")

            # Get table structure
            describe_query = f"DESCRIBE {self._lookup_table}"

            with self.connection.cursor() as cursor:
                cursor.execute(describe_query)
                columns = cursor.fetchall()

                # Get sample data
                sample_query = f"SELECT * FROM {self._lookup_table} LIMIT 3"
                cursor.execute(sample_query)
                sample_rows = cursor.fetchall()

                return {
                    "table_name": self._lookup_table,
                    "columns": [{"name": col[0], "type": col[1]} for col in columns],
                    "sample_data": sample_rows,
                }

        except Exception as e:
            self.logger.error(
                "Failed to get table information", table=self._lookup_table, error=str(e)
            )
            return {"error": str(e)}

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    def close(self):
        """Close the database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("Closed Databricks connection for contact lookup service")
            except Exception as e:
                self.logger.error(f"Error closing Databricks connection: {e}")
            finally:
                self.connection = None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
