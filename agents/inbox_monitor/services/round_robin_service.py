"""
Round Robin Assignment Service
==============================

Service for managing round-robin assignment of leads to Low Touch Experts
using Databricks for data storage and the active_rep_pool_v view.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from databricks import sql
from databricks.sql.client import Connection
from pydantic import BaseModel, Field

try:
    from config.settings import DatabricksSettings, TestModeSettings
except ImportError:
    from ..config.settings import DatabricksSettings, TestModeSettings


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


class RoundRobinService:
    """Service for managing round-robin lead assignment."""

    def __init__(
        self, settings: DatabricksSettings, test_mode_settings: TestModeSettings | None = None
    ):
        """Initialize the round-robin service.

        Args:
            settings: Databricks configuration settings
            test_mode_settings: Test mode configuration for email substitution
        """
        self.settings = settings
        self.test_mode_settings = test_mode_settings
        self.logger = structlog.get_logger(__name__)
        self.connection: Connection | None = None

        # Table names
        self._assignment_table = f"`{settings.catalog}`.`{settings.schema_name}`.`expert_lead_assignments{settings.table_suffix}`"
        self._expert_view = f"`{settings.catalog}`.`{settings.schema_name}`.`active_rep_pool_v`"

    async def __aenter__(self) -> "RoundRobinService":
        """Async context manager entry."""
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
        try:
            self.connection = sql.connect(
                server_hostname=self.settings.server_hostname,
                http_path=self.settings.http_path,
                access_token=self.settings.access_token,
            )
            self.logger.info("Connected to Databricks for round-robin service")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Databricks: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Databricks."""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("Disconnected from Databricks")
            except Exception as e:
                self.logger.error(f"Error disconnecting from Databricks: {e}")
            finally:
                self.connection = None

    async def create_assignment_table(self) -> bool:
        """Create the expert lead assignments table if it doesn't exist.

        Returns:
            True if table created/exists, False otherwise
        """
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

            if self.connection is None:
                raise RuntimeError("Database connection not established")
            with self.connection.cursor() as cursor:
                cursor.execute(create_table_sql)

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

            if self.connection is None:
                raise RuntimeError("Database connection not established")

            with self.connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

            experts = []
            for row in rows:
                expert = ActiveExpert(
                    expert_id=row[0],
                    expert_email=row[1],
                    expert_name=row[2],
                    is_active=bool(row[3]),
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
        try:
            # Query active experts with their assignment counts
            query = f"""
            SELECT
                e.ID as expert_id,
                e.EMAIL as expert_email,
                e.NAME as expert_name,
                CAST(e.ISACTIVE as BOOLEAN) as is_active,
                a.last_assignment_date,
                COALESCE(a.assignment_count, 0) as assignment_count
            FROM {self._expert_view} e
            LEFT JOIN (
                SELECT
                    expert_id,
                    MAX(assignment_date) as last_assignment_date,
                    COUNT(*) as assignment_count
                FROM {self._assignment_table}
                WHERE lead_status = 'assigned'
                GROUP BY expert_id
            ) a ON e.ID = a.expert_id
            WHERE e.ISACTIVE = 1
            ORDER BY
                COALESCE(a.assignment_count, 0) ASC,
                COALESCE(a.last_assignment_date, '1900-01-01') ASC
            """

            if self.connection is None:
                raise RuntimeError("Database connection not established")
            with self.connection.cursor() as cursor:
                cursor.execute(query)

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                experts = []
                for row in rows:
                    row_dict = dict(zip(columns, row, strict=False))

                    expert = ActiveExpert(
                        expert_id=row_dict["expert_id"],
                        expert_email=row_dict["expert_email"],
                        expert_name=row_dict["expert_name"],
                        is_active=bool(row_dict["is_active"]),
                        last_assignment_date=row_dict.get("last_assignment_date"),
                        assignment_count=int(row_dict.get("assignment_count", 0)),
                    )
                    experts.append(expert)

                self.logger.info(f"Retrieved {len(experts)} active experts")
                return experts

        except Exception as e:
            self.logger.error(f"Failed to get active experts: {e}")
            raise

    async def assign_lead_to_expert(self, customer_email: str) -> ExpertAssignment | None:
        """Assign a lead to the next available expert in round-robin fashion.

        Args:
            customer_email: Customer email address

        Returns:
            ExpertAssignment if successful, None otherwise

        Raises:
            Exception: If assignment fails
        """
        try:
            # Handle test mode email substitution for assignment tracking
            assignment_email = customer_email
            original_email = customer_email

            if (
                self.test_mode_settings
                and self.test_mode_settings.enabled
                and customer_email.lower() == self.test_mode_settings.test_sender_email.lower()
            ):
                assignment_email = self.test_mode_settings.target_salesforce_email
                self.logger.info(
                    "Test mode enabled: substituting email for round-robin assignment",
                    original_email=original_email,
                    assignment_email=assignment_email,
                    test_mode=True,
                )
            # Get active experts
            active_experts = await self.get_active_experts()

            if not active_experts:
                self.logger.warning("No active experts available for assignment")
                return None

            # Find the expert with the lowest assignment count
            # In case of tie, use the one with the oldest last assignment date
            next_expert = active_experts[
                0
            ]  # Already sorted by assignment_count and last_assignment_date

            # Create assignment record
            assignment_id = str(uuid.uuid4())
            assignment_date = datetime.now(UTC)

            assignment = ExpertAssignment(
                assignment_id=assignment_id,
                expert_id=next_expert.expert_id,
                expert_email=next_expert.expert_email,
                expert_name=next_expert.expert_name,
                customer_email=assignment_email,
                lead_status="assigned",
                assignment_date=assignment_date,
                last_assignment_timestamp=assignment_date,
                assignment_count=next_expert.assignment_count + 1,
            )

            # Insert assignment record
            insert_sql = f"""
            INSERT INTO {self._assignment_table} (
                assignment_id, expert_id, expert_email, expert_name, customer_email,
                lead_status, assignment_date, last_assignment_timestamp, assignment_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            if self.connection is None:
                raise RuntimeError("Database connection not established")
            with self.connection.cursor() as cursor:
                cursor.execute(
                    insert_sql,
                    [
                        assignment.assignment_id,
                        assignment.expert_id,
                        assignment.expert_email,
                        assignment.expert_name,
                        assignment.customer_email,
                        assignment.lead_status,
                        assignment.assignment_date,
                        assignment.last_assignment_timestamp,
                        assignment.assignment_count,
                        assignment_date,
                        assignment_date,
                    ],
                )

            self.logger.info(
                "Lead assigned to expert",
                assignment_id=assignment.assignment_id,
                expert_id=assignment.expert_id,
                expert_email=assignment.expert_email,
                customer_email=customer_email,
                assignment_count=assignment.assignment_count,
            )

            return assignment

        except Exception as e:
            self.logger.error(f"Failed to assign lead to expert: {e}")
            raise

    async def get_assignment_by_customer(self, customer_email: str) -> ExpertAssignment | None:
        """Get the latest assignment for a customer.

        Args:
            customer_email: Customer email address

        Returns:
            ExpertAssignment if found, None otherwise
        """
        try:
            query = f"""
            SELECT
                assignment_id, expert_id, expert_email, expert_name, customer_email,
                lead_status, assignment_date, last_assignment_timestamp, assignment_count
            FROM {self._assignment_table}
            WHERE customer_email = ?
            ORDER BY assignment_date DESC
            LIMIT 1
            """

            if self.connection is None:
                raise RuntimeError("Database connection not established")
            with self.connection.cursor() as cursor:
                cursor.execute(query, [customer_email])

                columns = [desc[0] for desc in cursor.description]
                row = cursor.fetchone()

                if row:
                    row_dict = dict(zip(columns, row, strict=False))

                    assignment = ExpertAssignment(
                        assignment_id=row_dict["assignment_id"],
                        expert_id=row_dict["expert_id"],
                        expert_email=row_dict["expert_email"],
                        expert_name=row_dict["expert_name"],
                        customer_email=row_dict["customer_email"],
                        lead_status=row_dict["lead_status"],
                        assignment_date=row_dict["assignment_date"],
                        last_assignment_timestamp=row_dict["last_assignment_timestamp"],
                        assignment_count=row_dict["assignment_count"],
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
        try:
            update_sql = f"""
            UPDATE {self._assignment_table}
            SET
                lead_status = ?,
                updated_at = CURRENT_TIMESTAMP()
            WHERE assignment_id = ?
            """

            if self.connection is None:
                raise RuntimeError("Database connection not established")
            with self.connection.cursor() as cursor:
                cursor.execute(update_sql, [new_status, assignment_id])

                # Check if any rows were affected
                if cursor.rowcount > 0:
                    self.logger.info(
                        "Assignment status updated",
                        assignment_id=assignment_id,
                        new_status=new_status,
                    )
                    return True
                else:
                    self.logger.warning(
                        "No assignment found to update", assignment_id=assignment_id
                    )
                    return False

        except Exception as e:
            self.logger.error(f"Failed to update assignment status: {e}")
            return False

    async def get_assignment_statistics(self) -> dict[str, Any]:
        """Get statistics about expert assignments.

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

            if self.connection is None:
                raise RuntimeError("Database connection not established")
            with self.connection.cursor() as cursor:
                cursor.execute(stats_query)

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                expert_stats = []
                for row in rows:
                    row_dict = dict(zip(columns, row, strict=False))
                    expert_stats.append(row_dict)

                # Overall statistics
                overall_query = f"""
                SELECT
                    COUNT(*) as total_assignments,
                    COUNT(DISTINCT expert_id) as active_experts,
                    COUNT(DISTINCT customer_email) as unique_customers,
                    AVG(assignment_count) as avg_assignments_per_expert
                FROM {self._assignment_table}
                """

                cursor.execute(overall_query)
                overall_row = cursor.fetchone()
                overall_columns = [desc[0] for desc in cursor.description]
                overall_stats = dict(zip(overall_columns, overall_row, strict=False))

                return {"overall_statistics": overall_stats, "expert_statistics": expert_stats}

        except Exception as e:
            self.logger.error(f"Failed to get assignment statistics: {e}")
            return {"error": str(e)}

    async def test_connection(self) -> bool:
        """Test the connection to Databricks.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.connection is None:
                raise RuntimeError("Database connection not established")
            query = "SELECT 1 as test"
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                return result is not None and result[0] == 1
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    def close(self):
        """Close the database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("Closed Databricks connection for round-robin service")
            except Exception as e:
                self.logger.error(f"Error closing Databricks connection: {e}")
            finally:
                self.connection = None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
