"""
Round Robin Assignment Service
==============================

Service for managing round-robin assignment of leads to Low Touch Experts
using Databricks for data storage and the active_rep_pool_v view.
Now uses connection pooling for optimal performance.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

try:
    from config.settings import TestModeSettings
    from services.pooled_service_base import PooledServiceBase
    from services.databricks_oauth_client import DatabricksOAuthClient
    from services.logging.service_logger_mixin import ServiceLoggerMixin
except ImportError:
    from ..config.settings import TestModeSettings
    from .pooled_service_base import PooledServiceBase
    from .databricks_oauth_client import DatabricksOAuthClient
    from services.logging.service_logger_mixin import ServiceLoggerMixin


class ExpertAssignment(BaseModel):
    """Model for expert assignment tracking."""

    assignment_id: str = Field(..., description="Unique assignment identifier")
    expert_id: str = Field(..., description="Expert ID from active_rep_pool_v")
    expert_email: str = Field(..., description="Expert email address")
    expert_name: str = Field(..., description="Expert full name")
    customer_email: str = Field(..., description="Customer email address")
    lead_status: str = Field(default="assigned", description="Lead status")
    assignment_date: datetime = Field(..., description="Assignment timestamp")
    last_assignment_timestamp: datetime = Field(..., description="Last assignment for this expert")
    assignment_count: int = Field(..., description="Total assignments for this expert")


class ActiveExpert(BaseModel):
    """Model for active expert from active_rep_pool_v."""

    expert_id: str = Field(..., description="Expert ID")
    expert_email: str = Field(..., description="Expert email")
    expert_name: str = Field(..., description="Expert name")
    is_active: bool = Field(..., description="Whether expert is active")
    last_assignment_date: datetime | None = Field(None, description="Last assignment date")
    assignment_count: int = Field(default=0, description="Total assignments")


class RoundRobinService(PooledServiceBase, ServiceLoggerMixin):
    """Service for managing round-robin lead assignment with connection pooling."""

    def __init__(self, test_mode_settings: TestModeSettings | None = None, databricks_settings = None):
        """Initialize the round-robin service with connection pooling.

        Args:
            test_mode_settings: Test mode configuration for email substitution
            databricks_settings: Databricks OAuth settings (if None, will be loaded lazily)
        """
        super().__init__()
        # Initialize service logging mixin
        self.__init_logging__("round_robin_service")
        
        self.test_mode_settings = test_mode_settings
        self.databricks_settings = databricks_settings
        
        # Table names will be set during initialization or lazily
        self._assignment_table = None
        self._expert_view = None

    async def _ensure_table_names(self):
        """Ensure table names are initialized."""
        if self._assignment_table is None:
            if self.databricks_settings is None:
                # Load settings lazily if not provided - this should be rare
                try:
                    from config.settings import get_settings
                    settings = await get_settings()
                except ImportError:
                    from ..config.settings import get_settings
                    settings = await get_settings()
                self.databricks_settings = settings.databricks_oauth
            
            self._assignment_table = f"`{self.databricks_settings.catalog}`.`{self.databricks_settings.schema_name}`.`expert_lead_assignments{self.databricks_settings.table_suffix}`"
            self._expert_view = f"`{self.databricks_settings.catalog}`.`{self.databricks_settings.schema_name}`.`active_rep_pool_v`"

    # Connection management handled by base class and global pool

    async def create_assignment_table(self) -> bool:
        """Create the expert lead assignments table if it doesn't exist.

        Returns:
            True if table created/exists, False otherwise
        """
        await self._ensure_table_names()
        return await self.execute_with_connection(
            self._create_assignment_table_impl
        )
    
    async def _create_assignment_table_impl(self, connection: DatabricksOAuthClient) -> bool:
        """Implementation of create assignment table."""
        try:
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self._assignment_table} (
                assignment_id STRING NOT NULL,
                expert_id STRING NOT NULL,
                expert_email STRING NOT NULL,
                expert_name STRING NOT NULL,
                customer_email STRING NOT NULL,
                lead_status STRING NOT NULL,
                assignment_date TIMESTAMP NOT NULL,
                last_assignment_timestamp TIMESTAMP NOT NULL,
                assignment_count INT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                PRIMARY KEY (assignment_id)
            )
            USING DELTA
            TBLPROPERTIES (
                'delta.autoOptimize.optimizeWrite' = 'true',
                'delta.autoOptimize.autoCompact' = 'true'
            )
            COMMENT 'Expert lead assignments for round-robin distribution'
            """

            await connection.execute_sql(create_table_sql)
            self.logger.info("Expert lead assignments table created/verified")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create assignment table: {e}")
            return False

    async def verify_expert_view(self) -> list[ActiveExpert]:
        """Verify the active_rep_pool_v view exists and get basic expert info (without assignment data).

        This method doesn't require the assignment table to exist, making it suitable for setup validation.

        Returns:
            List of active experts from the view

        Raises:
            Exception: If query fails or view doesn't exist
        """
        await self._ensure_table_names()
        return await self.execute_with_connection(
            self._verify_expert_view_impl
        )
    
    async def _verify_expert_view_impl(self, connection: DatabricksOAuthClient) -> list[ActiveExpert]:
        try:
            # Query active experts without assignment data (for setup validation)
            # Using actual view schema: ID, EMAIL, NAME, ALIAS, ISACTIVE, etc.
            query = f"""
            SELECT
                ID as expert_id,
                EMAIL as expert_email,
                NAME as expert_name,
                CAST(ISACTIVE as BOOLEAN) as is_active
            FROM {self._expert_view}
            WHERE ISACTIVE = 1
            ORDER BY NAME
            """

            rows = await connection.execute_sql_fetchall(query)

            experts = []
            for row in rows:
                expert = ActiveExpert(
                    expert_id=row["expert_id"],
                    expert_email=row["expert_email"],
                    expert_name=row["expert_name"],
                    is_active=bool(row["is_active"]),
                    last_assignment_date=None,  # Not queried in this method
                    assignment_count=0,  # Not queried in this method
                )
                experts.append(expert)

            self.logger.info(f"Found {len(experts)} active experts in view")
            return experts

        except Exception as e:
            self.logger.error(f"Failed to verify expert view: {e}")
            raise

    async def get_active_experts(self) -> list[ActiveExpert]:
        """Get list of active experts from the active_rep_pool_v view.

        Returns:
            List of active experts

        Raises:
            Exception: If query fails
        """
        return await self.execute_with_connection(self._get_active_experts_impl)
    
    async def _get_active_experts_impl(self, connection: DatabricksOAuthClient) -> list[ActiveExpert]:
        """Implementation of get_active_experts using provided connection.
        
        Args:
            connection: OAuth client from connection pool
            
        Returns:
            List of active experts
        """
        try:
            # Optimized query with better indexing and reduced subquery complexity
            query = f"""
            WITH expert_assignments AS (
                SELECT 
                    expert_id,
                    MAX(assignment_date) as last_assignment_date,
                    COUNT(*) as assignment_count
                FROM {self._assignment_table}
                WHERE lead_status = 'assigned'
                GROUP BY expert_id
            )
            SELECT
                e.ID as expert_id,
                e.EMAIL as expert_email,
                e.NAME as expert_name,
                CAST(e.ISACTIVE as BOOLEAN) as is_active,
                COALESCE(a.last_assignment_date, CAST('1900-01-01' AS TIMESTAMP)) as last_assignment_date,
                COALESCE(a.assignment_count, 0) as assignment_count
            FROM {self._expert_view} e
            LEFT JOIN expert_assignments a ON e.ID = a.expert_id
            WHERE e.ISACTIVE = 1
            ORDER BY
                COALESCE(a.assignment_count, 0) ASC,
                COALESCE(a.last_assignment_date, CAST('1900-01-01' AS TIMESTAMP)) ASC
            """

            rows = await connection.execute_sql_fetchall(query)

            experts = []
            for row in rows:
                expert = ActiveExpert(
                    expert_id=row["expert_id"],
                    expert_email=row["expert_email"],
                    expert_name=row["expert_name"],
                    is_active=bool(row["is_active"]),
                    last_assignment_date=row.get("last_assignment_date"),
                    assignment_count=int(row.get("assignment_count", 0)),
                )
                experts.append(expert)

            self.logger.info(f"Retrieved {len(experts)} active experts")
            return experts

        except Exception as e:
            self.logger.error(f"Failed to get active experts: {e}")
            raise

    async def assign_lead_to_expert(self, customer_email: str) -> ExpertAssignment | None:
        """Assign a lead to expert using round-robin logic with pooled connection.

        Args:
            customer_email: Customer email address

        Returns:
            ExpertAssignment if successful, None otherwise
        """
        await self._ensure_table_names()
        result = await self.execute_with_connection(
            self._assign_lead_to_expert_impl,
            customer_email
        )
        
        # Handle connection pool not available - this should not happen in LIVE mode  
        if result is None:
            self.logger.error("Connection pool not available - this should not happen in LIVE mode")
            raise Exception("Connection pool not available - ensure connection pool is initialized before using services")
        
        return result
    
    async def _assign_lead_to_expert_impl(
        self, 
        connection: DatabricksOAuthClient, 
        customer_email: str
    ) -> ExpertAssignment | None:
        """Implementation of lead assignment using provided connection.
        
        Args:
            connection: OAuth client from connection pool
            customer_email: Customer email address
            
        Returns:
            ExpertAssignment if successful, None otherwise
        """
        try:
            # Handle test mode email substitution for assignment tracking
            assignment_email = customer_email
            original_email = customer_email

            if (
                self.test_mode_settings
                and (self.test_mode_settings.enabled or self.test_mode_settings.email_test_mode)
                and self.test_mode_settings.target_salesforce_email
            ):
                assignment_email = self.test_mode_settings.target_salesforce_email
                self.logger.info(
                    "Test mode enabled: substituting email for round-robin assignment",
                    extra={
                        "original_email": original_email,
                        "assignment_email": assignment_email,
                        "test_mode": True,
                    }
                )

            # Check for existing assignment
            existing_query = f"""
                SELECT assignment_id, expert_id, expert_email, expert_name, 
                       lead_status, assignment_date, last_assignment_timestamp, assignment_count
                FROM {self._assignment_table}
                WHERE customer_email = '{assignment_email}' 
                AND lead_status = 'assigned'
                ORDER BY assignment_date DESC
                LIMIT 1
            """

            existing_result = await connection.execute_sql_fetchone(existing_query)
            
            if existing_result:
                # Return existing assignment
                return ExpertAssignment(
                    assignment_id=existing_result["assignment_id"],
                    expert_id=existing_result["expert_id"],
                    expert_email=existing_result["expert_email"],
                    expert_name=existing_result["expert_name"],
                    customer_email=assignment_email,
                    lead_status=existing_result["lead_status"],
                    assignment_date=existing_result["assignment_date"],
                    last_assignment_timestamp=existing_result["last_assignment_timestamp"],
                    assignment_count=existing_result["assignment_count"]
                )

            # Get next expert using round-robin logic
            next_expert_query = f"""
                WITH expert_assignment_counts AS (
                    SELECT 
                        e.ID as expert_id,
                        e.EMAIL as expert_email,
                        e.NAME as expert_name,
                        COALESCE(a.assignment_count, 0) as current_assignments,
                        COALESCE(a.last_assignment_timestamp, '1970-01-01 00:00:00') as last_assigned
                    FROM {self._expert_view} e
                    LEFT JOIN (
                        SELECT 
                            expert_id,
                            COUNT(*) as assignment_count,
                            MAX(last_assignment_timestamp) as last_assignment_timestamp
                        FROM {self._assignment_table}
                        WHERE lead_status = 'assigned'
                        GROUP BY expert_id
                    ) a ON e.ID = a.expert_id
                    WHERE e.ISACTIVE = 1
                )
                SELECT expert_id, expert_email, expert_name,
                       current_assignments, last_assigned
                FROM expert_assignment_counts
                ORDER BY current_assignments ASC, last_assigned ASC
                LIMIT 1
            """

            next_expert = await connection.execute_sql_fetchone(next_expert_query)
            
            if not next_expert:
                self.logger.error("No active experts available for assignment")
                return None

            # Create assignment
            assignment_id = str(uuid.uuid4())
            assignment_timestamp = datetime.now(UTC)

            insert_query = f"""
                INSERT INTO {self._assignment_table}
                (assignment_id, expert_id, expert_email, expert_name, customer_email,
                 lead_status, assignment_date, last_assignment_timestamp, assignment_count,
                 created_at, updated_at)
                VALUES (
                    '{assignment_id}',
                    '{next_expert["expert_id"]}',
                    '{next_expert["expert_email"]}', 
                    '{next_expert["expert_name"]}',
                    '{assignment_email}',
                    'assigned',
                    '{assignment_timestamp.isoformat()}',
                    '{assignment_timestamp.isoformat()}',
                    {int(next_expert["current_assignments"]) + 1},
                    '{assignment_timestamp.isoformat()}',
                    '{assignment_timestamp.isoformat()}'
                )
            """

            await connection.execute_sql(insert_query)

            assignment = ExpertAssignment(
                assignment_id=assignment_id,
                expert_id=next_expert["expert_id"],
                expert_email=next_expert["expert_email"],
                expert_name=next_expert["expert_name"],
                customer_email=assignment_email,
                lead_status="assigned",
                assignment_date=assignment_timestamp,
                last_assignment_timestamp=assignment_timestamp,
                assignment_count=int(next_expert["current_assignments"]) + 1
            )

            self.logger.info(
                "Lead assigned to expert using pooled connection",
                extra={
                    "assignment_id": assignment_id,
                    "expert_name": next_expert["expert_name"],
                    "customer_email": customer_email
                }
            )

            return assignment

        except Exception as e:
            self.logger.error(
                "Failed to assign lead to expert with pooled connection",
                extra={
                    "error": str(e),
                    "customer_email": customer_email
                }
            )
            return None

    async def get_assignment_by_customer(self, customer_email: str) -> ExpertAssignment | None:
        """Get assignment for customer using pooled connection."""
        await self._ensure_table_names()
        return await self.execute_with_connection(
            self._get_assignment_by_customer_impl,
            customer_email
        )
    
    async def _get_assignment_by_customer_impl(
        self,
        connection: DatabricksOAuthClient,
        customer_email: str
    ) -> ExpertAssignment | None:
        """Implementation of get assignment by customer."""
            
        try:
            query = f"""
            SELECT
                assignment_id, expert_id, expert_email, expert_name, customer_email,
                lead_status, assignment_date, last_assignment_timestamp, assignment_count
            FROM {self._assignment_table}
            WHERE customer_email = '{customer_email}'
            ORDER BY assignment_date DESC
            LIMIT 1
            """

            row = await connection.execute_sql_fetchone(query)

            if row:
                assignment = ExpertAssignment(
                    assignment_id=row["assignment_id"],
                    expert_id=row["expert_id"],
                    expert_email=row["expert_email"],
                    expert_name=row["expert_name"],
                    customer_email=row["customer_email"],
                    lead_status=row["lead_status"],
                    assignment_date=row["assignment_date"],
                    last_assignment_timestamp=row["last_assignment_timestamp"],
                    assignment_count=row["assignment_count"],
                )

                return assignment
            else:
                return None

        except Exception as e:
            self.logger.error(f"Failed to get assignment by customer: {e}")
            return None

    async def update_assignment_status(self, assignment_id: str, new_status: str) -> bool:
        """Update the status of an assignment.

        Args:
            assignment_id: Assignment ID to update
            new_status: New status for the assignment

        Returns:
            True if update successful, False otherwise
        """
        await self._ensure_table_names()
        return await self.execute_with_connection(self._update_assignment_status_impl, assignment_id, new_status)
    
    async def _update_assignment_status_impl(self, connection: DatabricksOAuthClient, assignment_id: str, new_status: str) -> bool:
        """Implementation of update_assignment_status using provided connection.
        
        Args:
            connection: OAuth client from connection pool
            assignment_id: Assignment ID to update
            new_status: New status for the assignment
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            update_sql = f"""
            UPDATE {self._assignment_table}
            SET
                lead_status = '{new_status}',
                updated_at = CURRENT_TIMESTAMP()
            WHERE assignment_id = '{assignment_id}'
            """

            result = await connection.execute_sql(update_sql)
            
            # For this update operation, we'll assume success if no exception was thrown
            # The OAuth client doesn't provide rowcount information
            self.logger.info(
                "Assignment status updated",
                extra={
                    "assignment_id": assignment_id,
                    "new_status": new_status,
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to update assignment status: {e}")
            return False

    async def get_assignment_statistics(self) -> dict[str, Any]:
        """Get statistics about expert assignments.

        Returns:
            Dictionary with assignment statistics
        """
        await self._ensure_table_names()
        return await self.execute_with_connection(self._get_assignment_statistics_impl)
    
    async def _get_assignment_statistics_impl(self, connection: DatabricksOAuthClient) -> dict[str, Any]:
        """Implementation of get_assignment_statistics using provided connection.
        
        Args:
            connection: OAuth client from connection pool
            
        Returns:
            Dictionary with assignment statistics
        """
        try:
            stats_query = f"""
            SELECT
                expert_id,
                expert_email,
                expert_name,
                COUNT(*) as total_assignments,
                SUM(CASE WHEN lead_status = 'assigned' THEN 1 ELSE 0 END) as active_assignments,
                MAX(assignment_date) as last_assignment_date,
                MIN(assignment_date) as first_assignment_date
            FROM {self._assignment_table}
            GROUP BY expert_id, expert_email, expert_name
            ORDER BY total_assignments DESC
            """

            expert_stats = await connection.execute_sql_fetchall(stats_query)

            # Overall statistics
            overall_query = f"""
            SELECT
                COUNT(*) as total_assignments,
                COUNT(DISTINCT expert_id) as active_experts,
                COUNT(DISTINCT customer_email) as unique_customers,
                AVG(assignment_count) as avg_assignments_per_expert
            FROM {self._assignment_table}
            """

            overall_result = await connection.execute_sql_fetchone(overall_query)
            overall_stats = overall_result if overall_result else {}

            return {"overall_statistics": overall_stats, "expert_statistics": expert_stats}

        except Exception as e:
            self.logger.error(f"Failed to get assignment statistics: {e}")
            return {"error": str(e)}

    # test_connection method provided by PooledServiceBase

    # Support Request creation moved back to scenario processor using content formatter
