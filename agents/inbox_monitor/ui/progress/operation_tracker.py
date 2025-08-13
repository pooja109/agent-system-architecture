# ui/progress/operation_tracker.py
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class TrackedOperation:
    """Individual tracked operation."""
    id: str
    name: str
    started_at: float
    status: str = "running"
    progress: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: Optional[float] = None
    

class OperationTracker:
    """Tracks multiple operations concurrently."""
    
    def __init__(self):
        self.operations: Dict[str, TrackedOperation] = {}
    
    def start_operation(self, name: str, **metadata) -> str:
        """Start tracking a new operation."""
        op_id = str(uuid.uuid4())[:8]
        operation = TrackedOperation(
            id=op_id,
            name=name,
            started_at=time.time(),
            metadata=metadata
        )
        self.operations[op_id] = operation
        return op_id
    
    def update_progress(self, op_id: str, progress: float, **metadata) -> None:
        """Update progress for an operation."""
        if op_id in self.operations:
            self.operations[op_id].progress = progress
            self.operations[op_id].metadata.update(metadata)
    
    def complete_operation(self, op_id: str, **metadata) -> None:
        """Mark an operation as completed."""
        if op_id in self.operations:
            self.operations[op_id].status = "completed"
            self.operations[op_id].completed_at = time.time()
            self.operations[op_id].metadata.update(metadata)
    
    def fail_operation(self, op_id: str, error: str, **metadata) -> None:
        """Mark an operation as failed."""
        if op_id in self.operations:
            self.operations[op_id].status = "failed"
            self.operations[op_id].completed_at = time.time()
            self.operations[op_id].metadata.update(error=error, **metadata)
    
    def get_operation_status(self, op_id: str) -> Optional[Dict[str, Any]]:
        """Get status information for an operation."""
        if op_id not in self.operations:
            return None
        
        op = self.operations[op_id]
        duration = (op.completed_at or time.time()) - op.started_at
        
        return {
            'id': op.id,
            'name': op.name,
            'status': op.status,
            'progress': op.progress,
            'duration': duration,
            'metadata': op.metadata.copy()
        }
    
    def get_active_operations(self) -> Dict[str, Dict[str, Any]]:
        """Get all currently active operations."""
        return {
            op_id: self.get_operation_status(op_id)
            for op_id, op in self.operations.items()
            if op.status == "running"
        }
    
    def cleanup_completed(self, max_age_seconds: float = 300) -> None:
        """Clean up old completed operations."""
        current_time = time.time()
        to_remove = []
        
        for op_id, op in self.operations.items():
            if (op.status in ["completed", "failed"] and 
                op.completed_at and 
                current_time - op.completed_at > max_age_seconds):
                to_remove.append(op_id)
        
        for op_id in to_remove:
            del self.operations[op_id]