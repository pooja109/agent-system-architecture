"""
Service Status Monitoring System - Real-time Service Health and Performance Tracking
"""

import time
import threading
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from collections import deque

try:
    from ui.enterprise_dashboard import ServiceStatus, ServiceMetric
    DASHBOARD_AVAILABLE = True
except ImportError:
    # Fallback definitions
    class ServiceStatus(Enum):
        PENDING = ("⏳", "dim")
        CONNECTING = ("🔄", "yellow")
        HEALTHY = ("✅", "green")
        WARNING = ("⚠️", "yellow")
        ERROR = ("❌", "red")
    
    @dataclass
    class ServiceMetric:
        name: str
        current_duration: float = 0.0
        status: ServiceStatus = ServiceStatus.PENDING
        operations_count: int = 0
    
    DASHBOARD_AVAILABLE = False


class ServiceHealth(Enum):
    """Service health levels."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DOWN = "down"


@dataclass
class ServiceOperation:
    """Individual service operation record."""
    operation_id: str
    service_name: str
    operation_type: str  # 'auth', 'query', 'upload', etc.
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    duration: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.end_time is not None
        
    @property
    def current_duration(self) -> float:
        """Get current duration (ongoing or final)."""
        if self.end_time:
            return self.duration
        else:
            return (datetime.now(timezone.utc) - self.start_time).total_seconds()


@dataclass 
class ServiceHealthMetrics:
    """Health metrics for a service."""
    service_name: str
    status: ServiceStatus = ServiceStatus.PENDING
    health: ServiceHealth = ServiceHealth.UNKNOWN
    
    # Performance metrics
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    
    # Timing metrics
    average_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    last_operation_time: Optional[datetime] = None
    
    # Health indicators
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    uptime_percentage: float = 100.0
    
    # Recent performance tracking
    recent_response_times: deque = field(default_factory=lambda: deque(maxlen=10))
    
    # SLA tracking
    sla_threshold_seconds: float = 2.0  # Default 2 second SLA
    sla_violations: int = 0
    
    # Trend analysis
    trend_window: deque = field(default_factory=lambda: deque(maxlen=5))  # Last 5 averages
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        return 100.0 - self.success_rate
    
    @property
    def sla_compliance_rate(self) -> float:
        """Calculate SLA compliance rate percentage."""
        if self.total_operations == 0:
            return 100.0
        compliant_operations = self.total_operations - self.sla_violations
        return (compliant_operations / self.total_operations) * 100.0
    
    @property
    def performance_trend(self) -> str:
        """Analyze performance trend."""
        if len(self.trend_window) < 2:
            return "stable"  # Not enough data
            
        recent_values = list(self.trend_window)
        if len(recent_values) >= 3:
            # Compare first half vs second half
            first_half = sum(recent_values[:len(recent_values)//2]) / (len(recent_values)//2)
            second_half = sum(recent_values[len(recent_values)//2:]) / (len(recent_values) - len(recent_values)//2)
            
            change_percent = ((second_half - first_half) / first_half) * 100
            
            if change_percent > 15:
                return "degrading"
            elif change_percent < -15:
                return "improving"
            else:
                return "stable"
        else:
            # Simple comparison for limited data
            if recent_values[-1] > recent_values[0] * 1.2:
                return "degrading"
            elif recent_values[-1] < recent_values[0] * 0.8:
                return "improving"
            else:
                return "stable"
    
    def update_timing_metrics(self, duration: float):
        """Update timing metrics with new operation."""
        self.recent_response_times.append(duration)
        
        # Update average
        if self.total_operations == 1:
            self.average_response_time = duration
            self.min_response_time = duration
            self.max_response_time = duration
        else:
            # Running average
            self.average_response_time = (
                (self.average_response_time * (self.total_operations - 1) + duration) / 
                self.total_operations
            )
            self.min_response_time = min(self.min_response_time, duration)
            self.max_response_time = max(self.max_response_time, duration)
        
        # Check SLA violation
        if duration > self.sla_threshold_seconds:
            self.sla_violations += 1
            
        # Update trend analysis
        if len(self.recent_response_times) >= 3:  # Need enough data for trend
            recent_avg = sum(list(self.recent_response_times)[-3:]) / 3
            self.trend_window.append(recent_avg)
    
    def determine_health(self) -> ServiceHealth:
        """Determine overall service health."""
        # Check if service has been used
        if self.total_operations == 0:
            return ServiceHealth.UNKNOWN
            
        # Check recent failures
        if self.consecutive_failures >= 3:
            return ServiceHealth.DOWN
        elif self.consecutive_failures >= 2:
            return ServiceHealth.FAILING
            
        # Check success rate
        if self.success_rate < 50:
            return ServiceHealth.FAILING
        elif self.success_rate < 80:
            return ServiceHealth.DEGRADED
            
        # Check response times
        if len(self.recent_response_times) >= 3:
            avg_recent = sum(self.recent_response_times) / len(self.recent_response_times)
            if avg_recent > 10.0:  # More than 10 seconds is concerning
                return ServiceHealth.DEGRADED
            elif avg_recent > 5.0:  # More than 5 seconds is warning
                return ServiceHealth.DEGRADED
                
        return ServiceHealth.HEALTHY


class ServiceMonitor:
    """
    Real-time service monitoring and health tracking.
    
    Features:
    - Progressive status updates (pending → connecting → healthy)
    - Real-time performance metrics
    - Health assessment and alerting
    - Service dependency tracking
    - Automatic recovery detection
    """
    
    def __init__(self, update_callback: Optional[Callable] = None):
        self.update_callback = update_callback
        
        # Service registry and metrics
        self.services: Dict[str, ServiceHealthMetrics] = {}
        self.active_operations: Dict[str, ServiceOperation] = {}
        
        # Service definitions with health thresholds
        self.service_definitions = {
            "azure_key_vault": {
                "display_name": "Azure Key Vault",
                "max_response_time": 3.0,
                "critical_operations": ["authenticate", "get_secret"]
            },
            "databricks_pool": {
                "display_name": "Databricks Connection Pool", 
                "max_response_time": 5.0,
                "critical_operations": ["connect", "query"]
            },
            "ai_foundry": {
                "display_name": "Azure AI Foundry",
                "max_response_time": 8.0,
                "critical_operations": ["classify", "generate"]
            },
            "email_service": {
                "display_name": "Email Service",
                "max_response_time": 4.0,
                "critical_operations": ["send", "receive"]
            },
            "prompt_manager": {
                "display_name": "Prompt Manager",
                "max_response_time": 1.0,
                "critical_operations": ["load_prompt", "validate"]
            },
            "salesforce": {
                "display_name": "Salesforce API",
                "max_response_time": 6.0,
                "critical_operations": ["create_case", "query"]
            }
        }
        
        # Initialize service metrics
        self._initialize_services()
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
    def _initialize_services(self):
        """Initialize service health metrics."""
        for service_name, definition in self.service_definitions.items():
            self.services[service_name] = ServiceHealthMetrics(
                service_name=service_name
            )
            
    def start_monitoring(self):
        """Start the service monitoring loop."""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.stop_event.clear()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop the service monitoring loop."""
        if not self.monitoring_active:
            return
            
        self.monitoring_active = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            
    def start_operation(self, service_name: str, operation_type: str, 
                       operation_id: Optional[str] = None) -> str:
        """Start tracking a service operation."""
        if operation_id is None:
            operation_id = f"{service_name}_{operation_type}_{int(time.time() * 1000)}"
            
        # Ensure service is registered - create if needed
        if service_name not in self.services:
            self.services[service_name] = ServiceHealthMetrics(service_name=service_name)
            
        # Update service status to connecting
        self.services[service_name].status = ServiceStatus.CONNECTING
        self._notify_status_change(service_name, ServiceStatus.CONNECTING)
            
        # Create operation record
        operation = ServiceOperation(
            operation_id=operation_id,
            service_name=service_name,
            operation_type=operation_type,
            start_time=datetime.now(timezone.utc)
        )
        
        self.active_operations[operation_id] = operation
        return operation_id
        
    def complete_operation(self, operation_id: str, success: bool = True, 
                          error_message: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None):
        """Complete a tracked service operation."""
        if operation_id not in self.active_operations:
            return
            
        operation = self.active_operations[operation_id]
        operation.end_time = datetime.now(timezone.utc)
        operation.success = success
        operation.duration = (operation.end_time - operation.start_time).total_seconds()
        
        if error_message:
            operation.error_message = error_message
        if metadata:
            operation.metadata.update(metadata)
            
        # Update service metrics
        self._update_service_metrics(operation)
        
        # Remove from active operations
        del self.active_operations[operation_id]
        
        # Determine new service status
        service_metrics = self.services[operation.service_name]
        new_status = self._determine_service_status(service_metrics)
        
        if service_metrics.status != new_status:
            service_metrics.status = new_status
            self._notify_status_change(operation.service_name, new_status)
            
    def _update_service_metrics(self, operation: ServiceOperation):
        """Update service health metrics based on completed operation."""
        service_name = operation.service_name
        if service_name not in self.services:
            return
            
        metrics = self.services[service_name]
        
        # Update operation counts
        metrics.total_operations += 1
        metrics.last_operation_time = operation.end_time
        
        if operation.success:
            metrics.successful_operations += 1
            metrics.consecutive_failures = 0  # Reset failure count
        else:
            metrics.failed_operations += 1
            metrics.consecutive_failures += 1
            metrics.last_failure_time = operation.end_time
            
        # Update timing metrics
        metrics.update_timing_metrics(operation.duration)
        
        # Update health assessment
        metrics.health = metrics.determine_health()
        
    def _determine_service_status(self, metrics: ServiceHealthMetrics) -> ServiceStatus:
        """Determine appropriate service status based on metrics."""
        if metrics.health == ServiceHealth.DOWN:
            return ServiceStatus.ERROR
        elif metrics.health == ServiceHealth.FAILING:
            return ServiceStatus.ERROR
        elif metrics.health == ServiceHealth.DEGRADED:
            return ServiceStatus.WARNING
        elif metrics.health == ServiceHealth.HEALTHY:
            return ServiceStatus.HEALTHY
        else:
            return ServiceStatus.PENDING
            
    def _notify_status_change(self, service_name: str, status: ServiceStatus):
        """Notify callback of service status changes."""
        if self.update_callback:
            try:
                # Convert to format expected by dashboard
                duration = self.services[service_name].average_response_time
                success = status in [ServiceStatus.HEALTHY, ServiceStatus.WARNING]
                
                self.update_callback(service_name, duration, success)
            except Exception as e:
                # Don't let callback errors break monitoring
                print(f"Service monitor callback error: {e}")
                
    def _monitoring_loop(self):
        """Background monitoring loop for health checks."""
        while self.monitoring_active and not self.stop_event.is_set():
            try:
                # Check for stale operations
                self._check_stale_operations()
                
                # Perform periodic health assessments
                self._assess_service_health()
                
                # Sleep for monitoring interval
                self.stop_event.wait(1.0)  # Check every second
                
            except Exception as e:
                print(f"Service monitoring error: {e}")
                
    def _check_stale_operations(self):
        """Check for operations that have been running too long."""
        current_time = datetime.now(timezone.utc)
        stale_threshold = 30.0  # 30 seconds
        
        stale_operations = []
        for op_id, operation in self.active_operations.items():
            duration = (current_time - operation.start_time).total_seconds()
            if duration > stale_threshold:
                stale_operations.append(op_id)
                
        # Mark stale operations as failed
        for op_id in stale_operations:
            self.complete_operation(
                op_id, 
                success=False, 
                error_message="Operation timeout"
            )
            
    def _assess_service_health(self):
        """Perform periodic health assessments."""
        for service_name, metrics in self.services.items():
            # Update health status
            old_health = metrics.health
            metrics.health = metrics.determine_health()
            
            # Check if status should change
            new_status = self._determine_service_status(metrics)
            if metrics.status != new_status:
                metrics.status = new_status
                self._notify_status_change(service_name, new_status)
                
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """Get current status of a service."""
        if service_name in self.services:
            return self.services[service_name].status
        return None
        
    def get_service_metrics(self, service_name: str) -> Optional[ServiceHealthMetrics]:
        """Get detailed metrics for a service."""
        return self.services.get(service_name)
        
    def get_all_service_statuses(self) -> Dict[str, ServiceStatus]:
        """Get status of all services."""
        return {
            name: metrics.status 
            for name, metrics in self.services.items()
        }
        
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        total_services = len(self.services)
        healthy_services = sum(
            1 for metrics in self.services.values()
            if metrics.health == ServiceHealth.HEALTHY
        )
        
        degraded_services = sum(
            1 for metrics in self.services.values()
            if metrics.health == ServiceHealth.DEGRADED
        )
        
        failing_services = sum(
            1 for metrics in self.services.values()
            if metrics.health in [ServiceHealth.FAILING, ServiceHealth.DOWN]
        )
        
        return {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "degraded_services": degraded_services,
            "failing_services": failing_services,
            "overall_health_percentage": (healthy_services / max(total_services, 1)) * 100,
            "active_operations": len(self.active_operations)
        }
        
    def simulate_service_progression(self, service_name: str):
        """Simulate progressive service status updates for demo purposes."""
        if service_name not in self.services:
            return
            
        # Simulate: pending → connecting → healthy progression
        statuses = [
            (ServiceStatus.PENDING, 0.2),
            (ServiceStatus.CONNECTING, 0.8), 
            (ServiceStatus.HEALTHY, 0.3)
        ]
        
        async def _simulate():
            for status, delay in statuses:
                self.services[service_name].status = status
                self._notify_status_change(service_name, status)
                await asyncio.sleep(delay)
                
        # Run simulation in background
        asyncio.create_task(_simulate())


# Integration helper
def create_service_monitor(dashboard_callback: Optional[Callable] = None) -> ServiceMonitor:
    """Create a service monitor with dashboard integration."""
    return ServiceMonitor(update_callback=dashboard_callback)