# ui/progress/progress_manager.py
import asyncio
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from contextlib import contextmanager
import uuid

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn
from rich.live import Live
from rich.console import Console

from utils.custom_logging.correlation import get_correlation_id


class ProgressType(str, Enum):
    """Types of progress indicators."""
    SPINNER = "spinner"
    BAR = "bar"
    COUNTER = "counter"
    STATUS = "status"


class OperationType(str, Enum):
    """Types of operations that can be tracked."""
    AUTHENTICATION = "authentication"
    INBOX_CHECK = "inbox_check"
    EMAIL_PROCESSING = "email_processing"
    SERVICE_INITIALIZATION = "service_initialization"
    SYSTEM_STATUS = "system_status"
    DATABASE_OPERATION = "database_operation"


@dataclass
class ProgressState:
    """State of a progress-tracked operation."""
    operation_id: str
    operation_type: OperationType
    description: str
    progress_type: ProgressType
    total: Optional[int] = None
    current: int = 0
    status: str = "starting"
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None


class ProgressManager:
    """Central manager for progress tracking and display."""
    
    def __init__(self, console: Console, enabled: bool = True):
        self.console = console
        self.enabled = enabled
        self.operations: Dict[str, ProgressState] = {}
        self._progress_display: Optional[Progress] = None
        self._live_display: Optional[Live] = None
        self._lock = threading.Lock()
        self._task_ids: Dict[str, Any] = {}  # Maps operation_id to rich task_id
        
        # Performance optimization settings
        self._update_throttle_interval = 0.1  # 10Hz rate limiting (100ms)
        self._last_update_times: Dict[str, float] = {}  # Track last update time per operation
        self._pending_updates: Dict[str, Dict[str, Any]] = {}  # Batch pending updates
        self._cleanup_interval = 300  # 5 minutes cleanup interval
        self._last_cleanup = time.time()
        self._max_operations_history = 100  # Limit retained operation history
        
    def is_enabled(self) -> bool:
        """Check if progress indicators are enabled."""
        return self.enabled and self.console.is_terminal
    
    def create_operation(self, 
                        operation_type: OperationType,
                        description: str,
                        progress_type: ProgressType = ProgressType.SPINNER,
                        total: Optional[int] = None) -> str:
        """Create a new progress-tracked operation."""
        operation_id = str(uuid.uuid4())[:8]
        correlation_id = get_correlation_id()
        
        with self._lock:
            self.operations[operation_id] = ProgressState(
                operation_id=operation_id,
                operation_type=operation_type,
                description=description,
                progress_type=progress_type,
                total=total,
                correlation_id=correlation_id
            )
            
            # Add to rich progress display if enabled
            if self.is_enabled() and self._progress_display:
                if progress_type == ProgressType.BAR and total:
                    task_id = self._progress_display.add_task(description, total=total)
                else:
                    task_id = self._progress_display.add_task(description, total=None)
                self._task_ids[operation_id] = task_id
        
        return operation_id
    
    def update_operation(self, 
                        operation_id: str,
                        current: Optional[int] = None,
                        status: Optional[str] = None,
                        description: Optional[str] = None,
                        **metadata) -> None:
        """Update progress for an operation with 10Hz rate limiting and batching."""
        current_time = time.time()
        
        with self._lock:
            if operation_id not in self.operations:
                return
            
            operation = self.operations[operation_id]
            
            # Always update the operation state immediately
            if current is not None:
                operation.current = current
            if status is not None:
                operation.status = status
            if description is not None:
                operation.description = description
            
            operation.metadata.update(metadata)
            operation.updated_at = current_time
            
            # Batch updates for display rendering (10Hz rate limiting)
            last_update_time = self._last_update_times.get(operation_id, 0)
            time_since_last_update = current_time - last_update_time
            
            if time_since_last_update >= self._update_throttle_interval:
                # Time to update display
                self._flush_operation_update(operation_id, operation)
                self._last_update_times[operation_id] = current_time
                
                # Clear any pending update for this operation
                self._pending_updates.pop(operation_id, None)
            else:
                # Batch the update for later
                if operation_id not in self._pending_updates:
                    self._pending_updates[operation_id] = {}
                
                update_data = self._pending_updates[operation_id]
                if current is not None:
                    update_data['current'] = current
                if status is not None:
                    update_data['status'] = status
                if description is not None:
                    update_data['description'] = description
                update_data.update(metadata)
            
            # Periodic cleanup to prevent memory leaks
            self._periodic_cleanup(current_time)
    
    def complete_operation(self, operation_id: str, 
                         final_status: str = "completed",
                         result_summary: Optional[str] = None) -> None:
        """Mark an operation as completed."""
        with self._lock:
            if operation_id not in self.operations:
                return
            
            operation = self.operations[operation_id]
            operation.status = final_status
            operation.updated_at = time.time()
            
            if result_summary:
                operation.metadata['result_summary'] = result_summary
            
            # Complete rich progress task
            if self.is_enabled() and self._progress_display and operation_id in self._task_ids:
                task_id = self._task_ids[operation_id]
                if operation.progress_type == ProgressType.BAR and operation.total:
                    self._progress_display.update(task_id, completed=operation.total)
                
                # Remove task after a short delay to show completion
                def remove_task():
                    time.sleep(1.0)
                    if self._progress_display:
                        try:
                            self._progress_display.remove_task(task_id)
                        except:
                            pass  # Task might already be removed
                
                threading.Timer(1.0, remove_task).start()
                del self._task_ids[operation_id]
    
    def fail_operation(self, operation_id: str, 
                      error: Exception,
                      error_context: Optional[str] = None) -> None:
        """Mark an operation as failed."""
        with self._lock:
            if operation_id not in self.operations:
                return
            
            operation = self.operations[operation_id]
            operation.status = "failed"
            operation.updated_at = time.time()
            operation.metadata.update({
                'error_type': type(error).__name__,
                'error_message': str(error),
                'error_context': error_context
            })
            
            # Update rich progress to show error
            if self.is_enabled() and self._progress_display and operation_id in self._task_ids:
                task_id = self._task_ids[operation_id]
                error_desc = f"❌ {operation.description}: {str(error)}"
                self._progress_display.update(task_id, description=error_desc)
                
                # Remove task after showing error
                def remove_task():
                    time.sleep(2.0)
                    if self._progress_display:
                        try:
                            self._progress_display.remove_task(task_id)
                        except:
                            pass
                
                threading.Timer(2.0, remove_task).start()
                del self._task_ids[operation_id]
    
    @contextmanager
    def start_progress_display(self, title: Optional[str] = None):
        """Start the rich progress display context."""
        if not self.is_enabled():
            yield
            return
        
        # Create progress display with appropriate columns
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%", style="progress.percentage"),
            TimeElapsedColumn(),
        ]
        
        self._progress_display = Progress(*columns, console=self.console)
        
        with self._progress_display:
            if title:
                self.console.print(f"\n[bold blue]{title}[/bold blue]")
            yield
        
        self._progress_display = None
        self._task_ids.clear()
    
    def get_operation_summary(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information for an operation."""
        with self._lock:
            if operation_id not in self.operations:
                return None
            
            operation = self.operations[operation_id]
            duration = operation.updated_at - operation.started_at
            
            return {
                'operation_id': operation_id,
                'operation_type': operation.operation_type.value,
                'description': operation.description,
                'status': operation.status,
                'duration_seconds': duration,
                'correlation_id': operation.correlation_id,
                'metadata': operation.metadata.copy()
            }
    
    def cleanup_completed_operations(self, max_age_seconds: float = 300) -> None:
        """Clean up old completed operations."""
        current_time = time.time()
        
        with self._lock:
            expired_operations = [
                op_id for op_id, operation in self.operations.items()
                if operation.status in ['completed', 'failed'] 
                and current_time - operation.updated_at > max_age_seconds
            ]
            
            for op_id in expired_operations:
                del self.operations[op_id]
                if op_id in self._task_ids:
                    del self._task_ids[op_id]
    
    def _flush_operation_update(self, operation_id: str, operation: ProgressState) -> None:
        """Flush a single operation update to the display."""
        if not self.is_enabled() or not self._progress_display or operation_id not in self._task_ids:
            return
        
        task_id = self._task_ids[operation_id]
        update_kwargs = {}
        
        if operation.description:
            update_kwargs['description'] = operation.description
            
        if operation.current is not None:
            if operation.progress_type == ProgressType.BAR:
                update_kwargs['completed'] = operation.current
            else:
                # For spinner/counter, include current in description
                current_desc = f"{operation.description}: {operation.current}"
                if operation.total:
                    current_desc += f"/{operation.total}"
                update_kwargs['description'] = current_desc
        
        if update_kwargs:
            try:
                self._progress_display.update(task_id, **update_kwargs)
            except Exception:
                # Silently handle display update errors to prevent disrupting operations
                pass
    
    def _periodic_cleanup(self, current_time: float) -> None:
        """Perform periodic cleanup to prevent memory leaks."""
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = current_time
        
        # Remove old completed operations beyond the history limit
        completed_operations = [
            (op_id, op) for op_id, op in self.operations.items()
            if op.status in ['completed', 'failed', 'cancelled']
        ]
        
        if len(completed_operations) > self._max_operations_history:
            # Sort by completion time and remove oldest
            completed_operations.sort(key=lambda x: x[1].updated_at)
            operations_to_remove = completed_operations[:-self._max_operations_history]
            
            for op_id, _ in operations_to_remove:
                # Clean up all tracking data for this operation
                self.operations.pop(op_id, None)
                self._last_update_times.pop(op_id, None)
                self._pending_updates.pop(op_id, None)
                self._task_ids.pop(op_id, None)
    
    def flush_pending_updates(self) -> None:
        """Flush all pending batched updates to display."""
        with self._lock:
            for operation_id, update_data in self._pending_updates.items():
                if operation_id in self.operations:
                    operation = self.operations[operation_id]
                    self._flush_operation_update(operation_id, operation)
            
            # Clear all pending updates
            self._pending_updates.clear()
            
            # Update last update times to prevent immediate re-batching
            current_time = time.time()
            for operation_id in self.operations:
                self._last_update_times[operation_id] = current_time
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the progress manager."""
        with self._lock:
            return {
                'active_operations': len([op for op in self.operations.values() 
                                        if op.status not in ['completed', 'failed', 'cancelled']]),
                'total_operations': len(self.operations),
                'pending_updates': len(self._pending_updates),
                'update_throttle_interval': self._update_throttle_interval,
                'cleanup_interval': self._cleanup_interval,
                'max_operations_history': self._max_operations_history,
                'last_cleanup': self._last_cleanup,
                'memory_usage_estimate': {
                    'operations': len(self.operations) * 200,  # Rough estimate in bytes
                    'pending_updates': len(self._pending_updates) * 100,
                    'update_times': len(self._last_update_times) * 50
                }
            }


# Convenience decorators and context managers
@contextmanager
def track_operation(progress_manager: ProgressManager,
                   operation_type: OperationType,
                   description: str,
                   progress_type: ProgressType = ProgressType.SPINNER):
    """Context manager for tracking an operation."""
    operation_id = progress_manager.create_operation(operation_type, description, progress_type)
    
    try:
        yield operation_id
        progress_manager.complete_operation(operation_id)
    except Exception as e:
        progress_manager.fail_operation(operation_id, e)
        raise


def track_async_operation(progress_manager: ProgressManager,
                         operation_type: OperationType,
                         description: str):
    """Decorator for tracking async operations."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            operation_id = progress_manager.create_operation(operation_type, description)
            
            try:
                result = await func(*args, **kwargs)
                progress_manager.complete_operation(operation_id)
                return result
            except Exception as e:
                progress_manager.fail_operation(operation_id, e)
                raise
        
        return wrapper
    return decorator