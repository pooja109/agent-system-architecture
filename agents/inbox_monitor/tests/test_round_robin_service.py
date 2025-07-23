"""
Tests for Round Robin Service
=============================

Unit tests for the round-robin assignment service using Databricks.
"""

import os
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import DatabricksSettings  # noqa: E402
from services.round_robin_service import (
    ActiveExpert,
    ExpertAssignment,
    RoundRobinService,
)


@pytest.fixture
def databricks_settings():
    """Create Databricks settings for testing."""
    return DatabricksSettings(
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
    return RoundRobinService(databricks_settings)


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

    def test_init(self, databricks_settings):
        """Test service initialization."""
        service = RoundRobinService(databricks_settings)
        assert service.settings == databricks_settings
        assert service.connection is None
        assert service._assignment_table.endswith("expert_lead_assignments_test")
        assert service._expert_view.endswith("active_rep_pool_v")

    @pytest.mark.asyncio
    async def test_connect_success(self, round_robin_service):
        """Test successful connection to Databricks."""
        mock_connection = MagicMock()

        with patch("services.round_robin_service.sql.connect", return_value=mock_connection):
            result = await round_robin_service.connect()

            assert result is True
            assert round_robin_service.connection == mock_connection

    @pytest.mark.asyncio
    async def test_connect_failure(self, round_robin_service):
        """Test connection failure."""
        with patch(
            "services.round_robin_service.sql.connect", side_effect=Exception("Connection error")
        ):
            result = await round_robin_service.connect()

            assert result is False
            assert round_robin_service.connection is None

    @pytest.mark.asyncio
    async def test_disconnect(self, round_robin_service):
        """Test disconnection from Databricks."""
        mock_connection = MagicMock()
        round_robin_service.connection = mock_connection

        await round_robin_service.disconnect()

        mock_connection.close.assert_called_once()
        assert round_robin_service.connection is None

    @pytest.mark.asyncio
    async def test_create_assignment_table_success(self, round_robin_service, mock_connection):
        """Test successful assignment table creation."""
        round_robin_service.connection = mock_connection

        result = await round_robin_service.create_assignment_table()

        assert result is True
        mock_connection.cursor.assert_called()

    @pytest.mark.asyncio
    async def test_create_assignment_table_failure(self, round_robin_service, mock_connection):
        """Test assignment table creation failure."""
        round_robin_service.connection = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "SQL error"
        )

        result = await round_robin_service.create_assignment_table()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_experts_success(self, round_robin_service, mock_connection):
        """Test successful retrieval of active experts."""
        round_robin_service.connection = mock_connection

        # Mock cursor results
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.description = [
            ("expert_id",),
            ("expert_email",),
            ("expert_name",),
            ("is_active",),
            ("last_assignment_date",),
            ("assignment_count",),
        ]
        mock_cursor.fetchall.return_value = [
            ("expert_1", "expert1@company.com", "Expert One", True, None, 0),
            ("expert_2", "expert2@company.com", "Expert Two", True, datetime(2024, 1, 1), 1),
        ]

        experts = await round_robin_service.get_active_experts()

        assert len(experts) == 2
        assert experts[0].expert_id == "expert_1"
        assert experts[0].assignment_count == 0
        assert experts[1].expert_id == "expert_2"
        assert experts[1].assignment_count == 1

    @pytest.mark.asyncio
    async def test_get_active_experts_failure(self, round_robin_service, mock_connection):
        """Test get active experts failure."""
        round_robin_service.connection = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "SQL error"
        )

        with pytest.raises(Exception) as exc_info:
            await round_robin_service.get_active_experts()

        assert "Failed to get active experts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_assign_lead_to_expert_success(self, round_robin_service, mock_connection):
        """Test successful lead assignment to expert."""
        round_robin_service.connection = mock_connection

        # Mock get_active_experts
        mock_expert = ActiveExpert(
            expert_id="expert_1",
            expert_email="expert1@company.com",
            expert_name="Expert One",
            is_active=True,
            last_assignment_date=None,
            assignment_count=0,
        )

        with patch.object(round_robin_service, "get_active_experts", return_value=[mock_expert]):
            assignment = await round_robin_service.assign_lead_to_expert("customer@example.com")

            assert assignment is not None
            assert assignment.expert_id == "expert_1"
            assert assignment.expert_email == "expert1@company.com"
            assert assignment.customer_email == "customer@example.com"
            assert assignment.assignment_count == 1

    @pytest.mark.asyncio
    async def test_assign_lead_to_expert_no_experts(self, round_robin_service, mock_connection):
        """Test lead assignment when no experts available."""
        round_robin_service.connection = mock_connection

        with patch.object(round_robin_service, "get_active_experts", return_value=[]):
            assignment = await round_robin_service.assign_lead_to_expert("customer@example.com")

            assert assignment is None

    @pytest.mark.asyncio
    async def test_assign_lead_to_expert_failure(self, round_robin_service, mock_connection):
        """Test lead assignment failure."""
        round_robin_service.connection = mock_connection

        with patch.object(
            round_robin_service, "get_active_experts", side_effect=Exception("SQL error")
        ):
            with pytest.raises(Exception) as exc_info:
                await round_robin_service.assign_lead_to_expert("customer@example.com")

            assert "Failed to assign lead to expert" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_assignment_by_customer_found(self, round_robin_service, mock_connection):
        """Test retrieving assignment by customer email when found."""
        round_robin_service.connection = mock_connection

        # Mock cursor results
        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.description = [
            ("assignment_id",),
            ("expert_id",),
            ("expert_email",),
            ("expert_name",),
            ("customer_email",),
            ("lead_status",),
            ("assignment_date",),
            ("last_assignment_timestamp",),
            ("assignment_count",),
        ]
        mock_cursor.fetchone.return_value = (
            "assignment_1",
            "expert_1",
            "expert1@company.com",
            "Expert One",
            "customer@example.com",
            "assigned",
            datetime(2024, 1, 1),
            datetime(2024, 1, 1),
            1,
        )

        assignment = await round_robin_service.get_assignment_by_customer("customer@example.com")

        assert assignment is not None
        assert assignment.assignment_id == "assignment_1"
        assert assignment.expert_id == "expert_1"
        assert assignment.customer_email == "customer@example.com"

    @pytest.mark.asyncio
    async def test_get_assignment_by_customer_not_found(self, round_robin_service, mock_connection):
        """Test retrieving assignment by customer email when not found."""
        round_robin_service.connection = mock_connection

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        assignment = await round_robin_service.get_assignment_by_customer("customer@example.com")

        assert assignment is None

    @pytest.mark.asyncio
    async def test_get_assignment_by_customer_failure(self, round_robin_service, mock_connection):
        """Test get assignment by customer failure."""
        round_robin_service.connection = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "SQL error"
        )

        assignment = await round_robin_service.get_assignment_by_customer("customer@example.com")

        assert assignment is None

    @pytest.mark.asyncio
    async def test_update_assignment_status_success(self, round_robin_service, mock_connection):
        """Test successful assignment status update."""
        round_robin_service.connection = mock_connection

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.rowcount = 1

        result = await round_robin_service.update_assignment_status("assignment_1", "completed")

        assert result is True
        mock_cursor.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_assignment_status_not_found(self, round_robin_service, mock_connection):
        """Test assignment status update when assignment not found."""
        round_robin_service.connection = mock_connection

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.rowcount = 0

        result = await round_robin_service.update_assignment_status("assignment_1", "completed")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_assignment_status_failure(self, round_robin_service, mock_connection):
        """Test assignment status update failure."""
        round_robin_service.connection = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "SQL error"
        )

        result = await round_robin_service.update_assignment_status("assignment_1", "completed")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_assignment_statistics_success(self, round_robin_service, mock_connection):
        """Test successful assignment statistics retrieval."""
        round_robin_service.connection = mock_connection

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value

        # Mock first query (expert stats)
        mock_cursor.description = [
            ("expert_id",),
            ("expert_email",),
            ("expert_name",),
            ("total_assignments",),
            ("active_assignments",),
            ("last_assignment_date",),
            ("first_assignment_date",),
        ]
        mock_cursor.fetchall.return_value = [
            (
                "expert_1",
                "expert1@company.com",
                "Expert One",
                3,
                1,
                datetime(2024, 1, 3),
                datetime(2024, 1, 1),
            )
        ]

        # Mock second query (overall stats)
        mock_cursor.fetchone.return_value = (10, 2, 8, 5.0)

        stats = await round_robin_service.get_assignment_statistics()

        assert "overall_statistics" in stats
        assert "expert_statistics" in stats
        assert len(stats["expert_statistics"]) == 1
        assert stats["expert_statistics"][0]["expert_id"] == "expert_1"

    @pytest.mark.asyncio
    async def test_get_assignment_statistics_failure(self, round_robin_service, mock_connection):
        """Test assignment statistics retrieval failure."""
        round_robin_service.connection = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "SQL error"
        )

        stats = await round_robin_service.get_assignment_statistics()

        assert "error" in stats
        assert "SQL error" in stats["error"]

    @pytest.mark.asyncio
    async def test_test_connection_success(self, round_robin_service, mock_connection):
        """Test successful connection test."""
        round_robin_service.connection = mock_connection

        mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (1,)

        result = await round_robin_service.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, round_robin_service, mock_connection):
        """Test connection test failure."""
        round_robin_service.connection = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = Exception(
            "Connection error"
        )

        result = await round_robin_service.test_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_context_manager(self, round_robin_service):
        """Test async context manager."""
        with patch.object(round_robin_service, "connect", return_value=True):
            with patch.object(round_robin_service, "disconnect"):
                async with round_robin_service as service:
                    assert service == round_robin_service

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
