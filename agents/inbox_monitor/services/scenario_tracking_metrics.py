"""
Performance metrics collection for scenario tracking service.
Provides comprehensive monitoring and observability.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque, defaultdict
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a specific operation type."""
    operation_name: str
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    recent_durations: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100.0
    
    @property
    def average_duration_ms(self) -> float:
        """Calculate average operation duration."""
        if self.total_operations == 0:
            return 0.0
        return self.total_duration_ms / self.total_operations
    
    @property
    def recent_average_duration_ms(self) -> float:
        """Calculate recent average duration (last 100 operations)."""
        if not self.recent_durations:
            return 0.0
        return sum(self.recent_durations) / len(self.recent_durations)
    
    def record_operation(self, duration_ms: float, success: bool = True):
        """Record a completed operation."""
        self.total_operations += 1
        self.total_duration_ms += duration_ms
        self.recent_durations.append(duration_ms)
        
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)


class ScenarioTrackingMetrics:
    """Comprehensive metrics collection for scenario tracking service."""
    
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.operation_metrics: Dict[str, OperationMetrics] = {}
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.batch_sizes: deque = deque(maxlen=50)  # Track recent batch sizes
        self.connection_wait_times: deque = deque(maxlen=100)
        self.memory_usage_samples: deque = deque(maxlen=50)
        self._lock = asyncio.Lock()
    
    async def record_operation(self, operation_name: str, duration_ms: float, 
                              success: bool = True, error_type: str = None):
        """Record metrics for a completed operation."""
        async with self._lock:
            if operation_name not in self.operation_metrics:
                self.operation_metrics[operation_name] = OperationMetrics(operation_name)
            
            self.operation_metrics[operation_name].record_operation(duration_ms, success)
            
            if not success and error_type:
                self.error_counts[error_type] += 1
    
    async def record_batch_operation(self, batch_size: int, total_duration_ms: float,
                                   successful_records: int, failed_records: int):
        """Record metrics for batch operations."""
        self.batch_sizes.append(batch_size)
        success_rate = successful_records / batch_size if batch_size > 0 else 0
        
        await self.record_operation(
            "batch_insert",
            total_duration_ms,
            success=(failed_records == 0)
        )
        
        logger.info(
            "Batch operation completed",
            batch_size=batch_size,
            successful_records=successful_records,
            failed_records=failed_records,
            success_rate=success_rate,
            duration_ms=total_duration_ms
        )
    
    async def record_connection_wait(self, wait_time_ms: float):
        """Record connection pool wait times."""
        async with self._lock:
            self.connection_wait_times.append(wait_time_ms)
    
    async def record_memory_usage(self, memory_mb: float):
        """Record memory usage samples."""
        async with self._lock:
            self.memory_usage_samples.append(memory_mb)
    
    def get_summary_metrics(self) -> Dict[str, Any]:
        """Get summary of all collected metrics."""
        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        operation_summaries = {}
        for name, metrics in self.operation_metrics.items():
            operation_summaries[name] = {
                "total_operations": metrics.total_operations,
                "success_rate": metrics.success_rate,
                "average_duration_ms": metrics.average_duration_ms,
                "recent_average_duration_ms": metrics.recent_average_duration_ms,
                "min_duration_ms": metrics.min_duration_ms,
                "max_duration_ms": metrics.max_duration_ms
            }
        
        # Connection pool statistics
        connection_stats = {}
        if self.connection_wait_times:
            wait_times = list(self.connection_wait_times)
            connection_stats = {
                "average_wait_time_ms": sum(wait_times) / len(wait_times),
                "max_wait_time_ms": max(wait_times),
                "recent_samples": len(wait_times)
            }
        
        # Batch operation statistics
        batch_stats = {}
        if self.batch_sizes:
            sizes = list(self.batch_sizes)
            batch_stats = {
                "average_batch_size": sum(sizes) / len(sizes),
                "max_batch_size": max(sizes),
                "min_batch_size": min(sizes),
                "total_batches": len(sizes)
            }
        
        # Memory usage statistics
        memory_stats = {}
        if self.memory_usage_samples:
            samples = list(self.memory_usage_samples)
            memory_stats = {
                "average_memory_mb": sum(samples) / len(samples),
                "max_memory_mb": max(samples),
                "recent_samples": len(samples)
            }
        
        return {
            "service_uptime_seconds": uptime_seconds,
            "start_time": self.start_time.isoformat(),
            "operations": operation_summaries,
            "error_counts": dict(self.error_counts),
            "connection_pool": connection_stats,
            "batch_operations": batch_stats,
            "memory_usage": memory_stats,
            "health_score": self._calculate_health_score()
        }
    
    def _calculate_health_score(self) -> float:
        """Calculate overall service health score (0-100)."""
        if not self.operation_metrics:
            return 100.0  # No operations yet
        
        total_score = 0.0
        operation_count = 0
        
        for metrics in self.operation_metrics.values():
            if metrics.total_operations > 0:
                # Success rate component (0-50 points)
                success_score = (metrics.success_rate / 100.0) * 50
                
                # Performance component (0-50 points)
                # Penalize operations that take too long
                avg_duration = metrics.recent_average_duration_ms or metrics.average_duration_ms
                if avg_duration < 1000:  # < 1 second
                    perf_score = 50
                elif avg_duration < 5000:  # < 5 seconds
                    perf_score = 30
                elif avg_duration < 10000:  # < 10 seconds
                    perf_score = 10
                else:
                    perf_score = 0
                
                total_score += success_score + perf_score
                operation_count += 1
        
        return total_score / operation_count if operation_count > 0 else 100.0
    
    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """Get list of performance alerts based on metrics."""
        alerts = []
        
        # Check for high error rates
        for operation_name, metrics in self.operation_metrics.items():
            if metrics.total_operations > 10 and metrics.success_rate < 95.0:
                alerts.append({
                    "type": "high_error_rate",
                    "operation": operation_name,
                    "success_rate": metrics.success_rate,
                    "severity": "high" if metrics.success_rate < 90.0 else "medium"
                })
        
        # Check for slow operations
        for operation_name, metrics in self.operation_metrics.items():
            avg_duration = metrics.recent_average_duration_ms or metrics.average_duration_ms
            if avg_duration > 10000:  # > 10 seconds
                alerts.append({
                    "type": "slow_operation",
                    "operation": operation_name,
                    "average_duration_ms": avg_duration,
                    "severity": "high" if avg_duration > 30000 else "medium"
                })
        
        # Check for connection pool issues
        if self.connection_wait_times:
            avg_wait = sum(self.connection_wait_times) / len(self.connection_wait_times)
            if avg_wait > 5000:  # > 5 seconds
                alerts.append({
                    "type": "connection_pool_slow",
                    "average_wait_time_ms": avg_wait,
                    "severity": "high" if avg_wait > 15000 else "medium"
                })
        
        return alerts


# Global metrics instance
_metrics_instance: Optional[ScenarioTrackingMetrics] = None

def get_metrics_instance() -> ScenarioTrackingMetrics:
    """Get or create global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ScenarioTrackingMetrics()
    return _metrics_instance

async def record_operation_metric(operation_name: str, duration_ms: float, 
                                success: bool = True, error_type: str = None):
    """Convenience function to record operation metrics."""
    metrics = get_metrics_instance()
    await metrics.record_operation(operation_name, duration_ms, success, error_type)