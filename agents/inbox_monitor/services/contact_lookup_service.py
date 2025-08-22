"""
Contact Lookup Service
======================

Service for looking up Salesforce account and contact IDs from Databricks
based on email addresses. Now uses connection pooling for optimal performance.
"""

from typing import Any, Optional
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from config.settings import TestModeSettings
from services.pooled_service_base import PooledServiceBase
from services.databricks_oauth_client import DatabricksOAuthClient
from services.logging.database_logger import DatabaseLoggerMixin


class ContactLookupResult(BaseModel):
    """Result of contact lookup operation."""

    email: str = Field(..., description="Email address searched")
    sf_account_id: str | None = Field(None, description="Salesforce Account ID")
    sf_contact_id: str | None = Field(None, description="Salesforce Contact ID")
    account_name: str | None = Field(None, description="Account/Customer name")
    found: bool = Field(..., description="Whether contact was found")




class ContactLookupService(PooledServiceBase, DatabaseLoggerMixin):
    """Service for looking up contact and account IDs from Databricks with connection pooling."""

    def __init__(self, test_mode_settings: TestModeSettings | None = None):
        """Initialize the contact lookup service with connection pooling.

        Args:
            test_mode_settings: Test mode configuration for email substitution
        """
        super().__init__()
        # Initialize database logging mixin
        self.__init_logging__("contact_lookup_service")
        
        self.test_mode_settings = test_mode_settings
        
        # Table path for contact lookup
        self._lookup_table = "snowflake_ml_dev.mlops.i2a_lowtouch_sls_cnct_lvl_t"

    # Connection management handled by base class and global pool

    async def lookup_contact_by_email(self, email: str) -> ContactLookupResult:
        """Lookup contact by email using pooled connection."""
        result = await self.execute_with_connection(
            self._lookup_contact_impl,
            email
        )
        
        # Handle connection pool not available - this should not happen in LIVE mode
        if result is None:
            self.logger.error("Connection pool not available - this should not happen in LIVE mode")
            raise Exception("Connection pool not available - ensure connection pool is initialized before using services")
        
        # Handle mock mode response
        if isinstance(result, dict) and result.get("status") == "mock_mode":
            self.logger.info("Returning mock ContactLookupResult for test/mock mode")
            return ContactLookupResult(
                email=email,
                sf_account_id="MOCK_ACCOUNT_ID",
                sf_contact_id="MOCK_CONTACT_ID",
                account_name="Mock Test Account",
                found=True
            )
        
        return result

    
    async def _lookup_contact_impl(
        self,
        connection: DatabricksOAuthClient,
        email: str
    ) -> ContactLookupResult:
        """Implementation of lookup contact by email.

        Args:
            email: Email address to search for

        Returns:
            ContactLookupResult with account and contact IDs if found

        Raises:
            Exception: If lookup fails
        """
        try:

            # Handle test mode email substitution
            lookup_email = email
            original_email = email

            if (
                self.test_mode_settings
                and (self.test_mode_settings.enabled or self.test_mode_settings.email_test_mode)
                and self.test_mode_settings.target_salesforce_email
            ):
                # For demo scenarios, always substitute to target email regardless of sender
                # This allows hardcoded scenario emails to work with real Salesforce data
                lookup_email = self.test_mode_settings.target_salesforce_email
                self.logger.info(
                    "Test mode enabled: substituting email for lookup",
                    extra={
                        "original_email": original_email,
                        "lookup_email": lookup_email,
                        "test_mode": True,
                    }
                )

            # Optimized query with explicit column selection including account name
            query = f"""
            SELECT
                EMAIL,
                SF_ACCOUNT_ID,
                SF_CONTACT_ID,
                CUST_NAME as ACCOUNT_NAME
            FROM {self._lookup_table}
            WHERE UPPER(EMAIL) = UPPER('{lookup_email}')
            LIMIT 1
            """

            self.logger.info(
                "Looking up contact information",
                extra={
                    "email": lookup_email,
                    "original_email": original_email if lookup_email != original_email else None,
                    "table": self._lookup_table,
                }
            )

            row = await connection.execute_sql_fetchone(query)

            if row:
                # Contact found - row is a dictionary
                sf_account_id = row.get("SF_ACCOUNT_ID") if row.get("SF_ACCOUNT_ID") else None
                sf_contact_id = row.get("SF_CONTACT_ID") if row.get("SF_CONTACT_ID") else None
                account_name = row.get("ACCOUNT_NAME") if row.get("ACCOUNT_NAME") else None

                # Return result with original email and account name (for test mode transparency)
                result = ContactLookupResult(
                    email=original_email,
                    sf_account_id=sf_account_id,
                    sf_contact_id=sf_contact_id,
                    account_name=account_name,
                    found=True,
                )

                self.logger.info(
                    "Contact lookup successful",
                    extra={
                        "email": original_email,
                        "lookup_email": lookup_email if lookup_email != original_email else None,
                        "sf_account_id": sf_account_id,
                        "sf_contact_id": sf_contact_id,
                        "account_name": account_name,
                        "test_mode_substitution": lookup_email != original_email,
                    }
                )

                return result
            else:
                # Contact not found
                result = ContactLookupResult(
                    email=original_email, 
                    sf_account_id=None, 
                    sf_contact_id=None, 
                    account_name=None,
                    found=False
                )

                self.logger.warning(
                    "Contact not found in lookup table",
                    extra={
                        "email": original_email,
                        "lookup_email": lookup_email if lookup_email != original_email else None,
                        "table": self._lookup_table,
                        "test_mode_substitution": lookup_email != original_email,
                    }
                )

                return result

        except Exception as e:
            self.logger.error(f"Failed to lookup contact information (email: {email}): {e}")
            raise


    async def test_connection(self) -> bool:
        """Test the connection to Databricks and verify table access.

        Returns:
            True if connection and table access successful, False otherwise
        """
        try:
            # Use parent class test_connection for basic connectivity
            basic_test = await super().test_connection()
            if not basic_test:
                return False

            # Test table access with a simple count query using pooled connection
            return await self.execute_with_connection(self._test_table_access_impl)

        except Exception as e:
            self.logger.error(
                "Contact lookup table access test failed", 
                extra={"table": self._lookup_table, "error_message": str(e)}
            )
            return False
    
    async def _test_table_access_impl(self, connection: DatabricksOAuthClient) -> bool:
        """Test table access using provided connection.
        
        Args:
            connection: OAuth client from connection pool
            
        Returns:
            True if table access successful, False otherwise
        """
        try:
            test_query = f"SELECT COUNT(*) as record_count FROM {self._lookup_table} LIMIT 1"
            result = await connection.execute_sql_fetchone(test_query)

            if result:
                record_count = result.get("record_count", 0)
                self.logger.info(
                    "Contact lookup table access successful",
                    extra={
                        "table": self._lookup_table,
                        "record_count": record_count,
                    }
                )
                return True
            else:
                self.logger.error("No result from table access test")
                return False
        
        except Exception as e:
            self.logger.error(f"Table access test failed: {e}")
            return False

    async def get_table_info(self) -> dict[str, Any]:
        """Get information about the lookup table structure.

        Returns:
            Dictionary with table information
        """
        return await self.execute_with_connection(self._get_table_info_impl)
    
    async def _get_table_info_impl(self, connection: DatabricksOAuthClient) -> dict[str, Any]:
        """Implementation of get_table_info using provided connection.
        
        Args:
            connection: OAuth client from connection pool
            
        Returns:
            Dictionary with table information
        """
        try:
            # Get table structure
            describe_query = f"DESCRIBE {self._lookup_table}"
            columns = await connection.execute_sql_fetchall(describe_query)

            # Get sample data
            sample_query = f"SELECT * FROM {self._lookup_table} LIMIT 3"
            sample_rows = await connection.execute_sql_fetchall(sample_query)

            return {
                "table_name": self._lookup_table,
                "columns": [{"name": col.get("col_name", ""), "type": col.get("data_type", "")} for col in columns],
                "sample_data": sample_rows,
            }

        except Exception as e:
            self.logger.error(
                "Failed to get table information", 
                extra={"table": self._lookup_table, "error_message": str(e)}
            )
            return {"error": str(e)}

    def close(self):
        """Close the database connection (legacy method for compatibility)."""
        # This method is kept for compatibility but actual cleanup is handled in disconnect()
        pass
