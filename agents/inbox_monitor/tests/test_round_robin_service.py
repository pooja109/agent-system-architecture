"""
Tests for Round Robin Service
=============================
Unit tests for the round-robin assignment service using Databricks.
"""
import os
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.settings import DatabricksOAuthSettings  # noqa: E402
from services.round_robin_service import (
    ActiveExpert,
    ExpertAssignment,
    RoundRobinService,
)
@pytest.fixture
def databricks_settings():
    """Create Databricks settings for testing."""
    return DatabricksOAuthSettings(
        server_hostname="test.databricks.com",
        http_path="/sql/1.0/warehouses/test",
        access_token="test_token",
        catalog="test_catalog",
        schema_name="test_schema",
        table_suffix="_test",
    )
@pytest.fixture
def round_robin_service(databricks_settings):
    """Create round-robin service for testing."""
    return RoundRobinService(databricks_settings=databricks_settings)
@pytest.fixture
def mock_connection():
    """Create mock Databricks connection."""
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connection.cursor.return_value.__exit__.return_value = None
    return mock_connection
@pytest.fixture
def sample_active_experts():
    """Create sample active experts data."""
    return [
        ActiveExpert(
            expert_id="expert_1",
            expert_email="expert1@company.com",
            expert_name="Expert One",
            is_active=True,
            last_assignment_date=None,
            assignment_count=0,
        ),
        ActiveExpert(
            expert_id="expert_2",
            expert_email="expert2@company.com",
            expert_name="Expert Two",
            is_active=True,
            last_assignment_date=datetime(2024, 1, 1, tzinfo=UTC),
            assignment_count=1,
        ),
        ActiveExpert(
            expert_id="expert_3",
            expert_email="expert3@company.com",
            expert_name="Expert Three",
            is_active=True,
            last_assignment_date=datetime(2024, 1, 2, tzinfo=UTC),
            assignment_count=2,
        ),
    ]
class TestRoundRobinService:
    """Test cases for round-robin service."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.smoke
    @pytest.mark.medium
    @pytest.mark.integration
    def test_init(self, databricks_settings):
        """Test service initialization."""
        service = RoundRobinService(databricks_settings=databricks_settings)
        assert service.databricks_settings == databricks_settings
        assert service._assignment_table is None  # Initially None, set lazily
        assert service._expert_view is None  # Initially None, set lazily
    
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_connect_success(self, round_robin_service):
        """Test successful connection via connection pool."""
        # Mock the connection pool and test connection
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_connection = AsyncMock()  # Use AsyncMock for async methods
            mock_connection.test_connection.return_value = True
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_connection
            mock_get_pool.return_value = mock_pool
            result = await round_robin_service.test_connection()
            assert result is True
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_connect_failure(self, round_robin_service):
        """Test connection failure via connection pool."""
        # Mock connection pool failure
        with patch("services.pooled_service_base.get_connection_pool", side_effect=Exception("Connection error")):
            result = await round_robin_service.test_connection()
            assert result is False
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_context_manager(self, round_robin_service):
        """Test async context manager behavior."""
        # Mock the connection pool
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                # Service should have connection pool reference
                assert round_robin_service._connection_pool == mock_pool
            # After context exit, pool reference should be None
            assert round_robin_service._connection_pool is None
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_create_assignment_table_success(self, round_robin_service, mock_connection):
        """Test successful assignment table creation."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql.return_value = True
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                result = await round_robin_service.create_assignment_table()
                assert result is True
                mock_oauth_client.execute_sql.assert_called()
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_create_assignment_table_failure(self, round_robin_service, mock_connection):
        """Test assignment table creation failure."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql.side_effect = Exception("SQL error")
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                result = await round_robin_service.create_assignment_table()
                assert result is False
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_active_experts_success(self, round_robin_service, mock_connection):
        """Test successful retrieval of active experts."""
        # Mock the connection pool and OAuth client with query results
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchall.return_value = [
                {
                    "expert_id": "expert_1",
                    "expert_email": "expert1@company.com", 
                    "expert_name": "Expert One",
                    "is_active": True,
                    "last_assignment_date": None,
                    "assignment_count": 0
                },
                {
                    "expert_id": "expert_2", 
                    "expert_email": "expert2@company.com",
                    "expert_name": "Expert Two", 
                    "is_active": True,
                    "last_assignment_date": datetime(2024, 1, 1),
                    "assignment_count": 1
                }
            ]
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                experts = await round_robin_service.get_active_experts()
                assert len(experts) == 2
                assert experts[0].expert_id == "expert_1"
                assert experts[0].assignment_count == 0
                assert experts[1].expert_id == "expert_2"
                assert experts[1].assignment_count == 1
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_active_experts_failure(self, round_robin_service, mock_connection):
        """Test get active experts failure."""
        # Mock the connection pool and OAuth client with error
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchall.side_effect = Exception("SQL error")
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                with pytest.raises(Exception) as exc_info:
                    await round_robin_service.get_active_experts()
                assert "SQL error" in str(exc_info.value)
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_assign_lead_to_expert_success(self, round_robin_service, mock_connection):
        """Test successful lead assignment to expert."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            # Mock no existing assignment, then successful expert query and insert
            mock_oauth_client.execute_sql_fetchone.side_effect = [
                None,  # No existing assignment
                {  # Next expert query result
                    "expert_id": "expert_1",
                    "expert_email": "expert1@company.com",
                    "expert_name": "Expert One",
                    "current_assignments": 0,
                    "last_assigned": "1970-01-01 00:00:00"
                }
            ]
            mock_oauth_client.execute_sql.return_value = True  # Insert success
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                assignment = await round_robin_service.assign_lead_to_expert("customer@example.com")
                assert assignment is not None
                assert assignment.expert_id == "expert_1"
                assert assignment.expert_email == "expert1@company.com"
                assert assignment.customer_email == "customer@example.com"
                assert assignment.assignment_count == 1
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_assign_lead_to_expert_no_experts(self, round_robin_service, mock_connection):
        """Test lead assignment when no experts available."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            # Mock no existing assignment, then no experts available
            mock_oauth_client.execute_sql_fetchone.side_effect = [
                None,  # No existing assignment
                None   # No experts available
            ]
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                assignment = await round_robin_service.assign_lead_to_expert("customer@example.com")
                assert assignment is None
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_assign_lead_to_expert_failure(self, round_robin_service, mock_connection):
        """Test lead assignment failure."""
        # Mock the connection pool and OAuth client with error
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchone.side_effect = Exception("SQL error")
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                assignment = await round_robin_service.assign_lead_to_expert("customer@example.com")
                # Service handles errors gracefully and returns None
                assert assignment is None
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_assignment_by_customer_found(self, round_robin_service, mock_connection):
        """Test retrieving assignment by customer email when found."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchone.return_value = {
                "assignment_id": "assignment_1",
                "expert_id": "expert_1",
                "expert_email": "expert1@company.com",
                "expert_name": "Expert One",
                "customer_email": "customer@example.com",
                "lead_status": "assigned",
                "assignment_date": datetime(2024, 1, 1),
                "last_assignment_timestamp": datetime(2024, 1, 1),
                "assignment_count": 1
            }
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                assignment = await round_robin_service.get_assignment_by_customer("customer@example.com")
                assert assignment is not None
                assert assignment.assignment_id == "assignment_1"
                assert assignment.expert_id == "expert_1"
                assert assignment.customer_email == "customer@example.com"
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_assignment_by_customer_not_found(self, round_robin_service, mock_connection):
        """Test retrieving assignment by customer email when not found."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchone.return_value = None
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                assignment = await round_robin_service.get_assignment_by_customer("customer@example.com")
                assert assignment is None
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_assignment_by_customer_failure(self, round_robin_service, mock_connection):
        """Test get assignment by customer failure."""
        # Mock the connection pool and OAuth client with error
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchone.side_effect = Exception("SQL error")
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                assignment = await round_robin_service.get_assignment_by_customer("customer@example.com")
                assert assignment is None
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_update_assignment_status_success(self, round_robin_service, mock_connection):
        """Test successful assignment status update."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql.return_value = True
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                result = await round_robin_service.update_assignment_status("assignment_1", "completed")
                assert result is True
                mock_oauth_client.execute_sql.assert_called()
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_update_assignment_status_not_found(self, round_robin_service, mock_connection):
        """Test assignment status update when assignment not found."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql.return_value = True  # OAuth client doesn't report rowcount
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                # The service returns True even if no rows affected (OAuth client limitation)
                result = await round_robin_service.update_assignment_status("assignment_1", "completed")
                assert result is True
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_update_assignment_status_failure(self, round_robin_service, mock_connection):
        """Test assignment status update failure."""
        # Mock the connection pool and OAuth client with error
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql.side_effect = Exception("SQL error")
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                result = await round_robin_service.update_assignment_status("assignment_1", "completed")
                assert result is False
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_assignment_statistics_success(self, round_robin_service, mock_connection):
        """Test successful assignment statistics retrieval."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            # Mock expert stats query result
            mock_oauth_client.execute_sql_fetchall.return_value = [
                {
                    "expert_id": "expert_1",
                    "expert_email": "expert1@company.com",
                    "expert_name": "Expert One",
                    "total_assignments": 3,
                    "active_assignments": 1,
                    "last_assignment_date": datetime(2024, 1, 3),
                    "first_assignment_date": datetime(2024, 1, 1)
                }
            ]
            # Mock overall stats query result
            mock_oauth_client.execute_sql_fetchone.return_value = {
                "total_assignments": 10,
                "active_experts": 2,
                "unique_customers": 8,
                "avg_assignments_per_expert": 5.0
            }
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                stats = await round_robin_service.get_assignment_statistics()
                assert "overall_statistics" in stats
                assert "expert_statistics" in stats
                assert len(stats["expert_statistics"]) == 1
                assert stats["expert_statistics"][0]["expert_id"] == "expert_1"
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_get_assignment_statistics_failure(self, round_robin_service, mock_connection):
        """Test assignment statistics retrieval failure."""
        # Mock the connection pool and OAuth client with error
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.execute_sql_fetchall.side_effect = Exception("SQL error")
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            async with round_robin_service:
                stats = await round_robin_service.get_assignment_statistics()
                assert "error" in stats
                assert "SQL error" in stats["error"]
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_test_connection_success(self, round_robin_service, mock_connection):
        """Test successful connection test."""
        # Mock the connection pool and OAuth client
        with patch("services.pooled_service_base.get_connection_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_oauth_client = AsyncMock()
            mock_oauth_client.test_connection.return_value = True
            mock_pool.get_connection.return_value.__aenter__.return_value = mock_oauth_client
            mock_get_pool.return_value = mock_pool
            result = await round_robin_service.test_connection()
            assert result is True
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_test_connection_failure(self, round_robin_service, mock_connection):
        """Test connection test failure."""
        # Mock the connection pool with error
        with patch("services.pooled_service_base.get_connection_pool", side_effect=Exception("Connection error")):
            result = await round_robin_service.test_connection()
            assert result is False
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_expert_assignment_model(self):
        """Test expert assignment model."""
        assignment_data = {
            "assignment_id": "assignment_1",
            "expert_id": "expert_1",
            "expert_email": "expert1@company.com",
            "expert_name": "Expert One",
            "customer_email": "customer@example.com",
            "lead_status": "assigned",
            "assignment_date": datetime.now(UTC),
            "last_assignment_timestamp": datetime.now(UTC),
            "assignment_count": 1,
        }
        assignment = ExpertAssignment(**assignment_data)
        assert assignment.assignment_id == "assignment_1"
        assert assignment.expert_id == "expert_1"
        assert assignment.expert_email == "expert1@company.com"
        assert assignment.customer_email == "customer@example.com"
        assert assignment.lead_status == "assigned"
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_active_expert_model(self):
        """Test active expert model."""
        expert_data = {
            "expert_id": "expert_1",
            "expert_email": "expert1@company.com",
            "expert_name": "Expert One",
            "is_active": True,
            "last_assignment_date": datetime.now(UTC),
            "assignment_count": 5,
        }
        expert = ActiveExpert(**expert_data)
        assert expert.expert_id == "expert_1"
        assert expert.expert_email == "expert1@company.com"
        assert expert.expert_name == "Expert One"
        assert expert.is_active is True
        assert expert.assignment_count == 5
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    def test_active_expert_model_defaults(self):
        """Test active expert model with default values."""
        expert_data = {
            "expert_id": "expert_1",
            "expert_email": "expert1@company.com",
            "expert_name": "Expert One",
            "is_active": True,
        }
        expert = ActiveExpert(**expert_data)
        assert expert.last_assignment_date is None
        assert expert.assignment_count == 0