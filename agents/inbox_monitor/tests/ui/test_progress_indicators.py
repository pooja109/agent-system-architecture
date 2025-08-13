# tests/ui/test_progress_indicators.py
import pytest
import asyncio
from unittest.mock import Mock, patch
from io import StringIO

from ui.progress.progress_manager import ProgressManager, OperationType, ProgressType
from rich.console import Console


class TestProgressIndicators:
    """Test progress indicator functionality."""
    
    @pytest.fixture
    def mock_console(self):
        """Mock console for testing."""
        return Console(file=StringIO(), force_terminal=True, width=80)
    
    @pytest.fixture
    def progress_manager(self, mock_console):
        """Progress manager for testing."""
        return ProgressManager(mock_console, enabled=True)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_create_and_complete_operation(self, progress_manager):
        """Test basic operation lifecycle."""
        # Create operation
        operation_id = progress_manager.create_operation(
            OperationType.INBOX_CHECK,
            "Testing inbox check",
            ProgressType.SPINNER
        )
        
        assert operation_id in progress_manager.operations
        
        # Update operation
        progress_manager.update_operation(operation_id, status="processing")
        
        operation = progress_manager.operations[operation_id]
        assert operation.status == "processing"
        
        # Complete operation
        progress_manager.complete_operation(operation_id, "completed", "Test successful")
        
        assert operation.status == "completed"
        assert operation.metadata['result_summary'] == "Test successful"
    
    @pytest.mark.fast
    @pytest.mark.integration
    def test_progress_display_context(self, progress_manager):
        """Test progress display context manager."""
        with progress_manager.start_progress_display("Test Operations"):
            operation_id = progress_manager.create_operation(
                OperationType.EMAIL_PROCESSING,
                "Processing emails",
                ProgressType.BAR,
                total=10
            )
            
            # Update progress
            progress_manager.update_operation(operation_id, current=5)
            
            progress_manager.complete_operation(operation_id)
        
        # Verify operation was tracked
        summary = progress_manager.get_operation_summary(operation_id)
        assert summary is not None
        assert summary['status'] == 'completed'
    
    @pytest.mark.medium
    @pytest.mark.integration
    def test_concurrent_operations(self, progress_manager):
        """Test multiple concurrent operations."""
        with progress_manager.start_progress_display("Concurrent Test"):
            # Create multiple operations
            operations = []
            for i in range(3):
                op_id = progress_manager.create_operation(
                    OperationType.SERVICE_INITIALIZATION,
                    f"Service {i}",
                    ProgressType.SPINNER
                )
                operations.append(op_id)
            
            # Complete operations in reverse order
            for op_id in reversed(operations):
                progress_manager.complete_operation(op_id)
            
            # Verify all operations completed
            for op_id in operations:
                summary = progress_manager.get_operation_summary(op_id)
                assert summary['status'] == 'completed'
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_operation_failure(self, progress_manager):
        """Test operation failure handling."""
        operation_id = progress_manager.create_operation(
            OperationType.DATABASE_OPERATION,
            "Test database operation",
            ProgressType.SPINNER
        )
        
        # Simulate failure
        test_error = ValueError("Database connection failed")
        progress_manager.fail_operation(operation_id, test_error, "Connection timeout")
        
        operation = progress_manager.operations[operation_id]
        assert operation.status == "failed"
        assert operation.metadata['error_type'] == "ValueError"
        assert operation.metadata['error_message'] == "Database connection failed"
        assert operation.metadata['error_context'] == "Connection timeout"
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_disabled_progress_manager(self, mock_console):
        """Test progress manager when disabled."""
        disabled_manager = ProgressManager(mock_console, enabled=False)
        
        assert not disabled_manager.is_enabled()
        
        # Operations should still be tracked even if display is disabled
        operation_id = disabled_manager.create_operation(
            OperationType.INBOX_CHECK,
            "Test disabled operation"
        )
        
        assert operation_id in disabled_manager.operations
        
        disabled_manager.complete_operation(operation_id)
        summary = disabled_manager.get_operation_summary(operation_id)
        assert summary['status'] == 'completed'
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_cleanup_completed_operations(self, progress_manager):
        """Test cleanup of old completed operations."""
        # Create and complete some operations
        old_ops = []
        for i in range(3):
            op_id = progress_manager.create_operation(
                OperationType.SYSTEM_STATUS,
                f"Old operation {i}",
                ProgressType.SPINNER
            )
            progress_manager.complete_operation(op_id)
            old_ops.append(op_id)
        
        # Verify operations exist before cleanup
        assert len(progress_manager.operations) == 3
        
        # Run cleanup
        progress_manager.cleanup_completed_operations(max_age_seconds=0)
        
        # Verify operations were cleaned up
        assert len(progress_manager.operations) == 0

    @pytest.mark.fast
    @pytest.mark.unit
    def test_performance_metrics(self, progress_manager):
        """Test performance metrics functionality."""
        # Create some operations
        op1 = progress_manager.create_operation(OperationType.INBOX_CHECK, "Test 1")
        op2 = progress_manager.create_operation(OperationType.EMAIL_PROCESSING, "Test 2")
        progress_manager.complete_operation(op1)
        
        metrics = progress_manager.get_performance_metrics()
        
        assert 'active_operations' in metrics
        assert 'total_operations' in metrics
        assert 'pending_updates' in metrics
        assert 'update_throttle_interval' in metrics
        assert metrics['total_operations'] == 2
        assert metrics['active_operations'] == 1  # op2 is still active
        assert metrics['update_throttle_interval'] == 0.1  # 10Hz