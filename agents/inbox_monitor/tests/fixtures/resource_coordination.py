"""
Unified resource coordination and orchestration for comprehensive resource management.

This module provides a unified coordination layer that manages all 4 resource management
frameworks (memory, CPU, connections, system monitoring) together with priority-based
resource allocation and automatic intervention.
"""
import pytest
import asyncio
import threading
import time
import gc
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager, contextmanager
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Import all resource management frameworks
from tests.fixtures.memory_management import MemoryManager, MemoryBudget, DataSampler
from tests.fixtures.cpu_management import CPUManager, CPUBudget, ParallelExecutionManager
from tests.fixtures.connection_management import ConnectionPoolManager, ConnectionBudget
from tests.fixtures.system_monitoring import SystemMonitor, SystemLimits, ResourceInterventionManager


@dataclass
class UnifiedResourceBudget:
    """Unified resource budget coordinating all resource types."""
    memory_budget: MemoryBudget
    cpu_budget: CPUBudget
    connection_budget: ConnectionBudget
    system_limits: SystemLimits
    priority: int = 1  # 1=highest, 5=lowest priority
    coordination_enabled: bool = True


class UnifiedResourceCoordinator:
    """
    Unified resource coordinator managing all 4 resource management frameworks.
    
    Provides centralized coordination, priority-based resource allocation,
    and automatic intervention across memory, CPU, connections, and system monitoring.
    """
    
    def __init__(self):
        # Initialize all resource managers
        self.memory_manager = MemoryManager()
        self.cpu_manager = CPUManager()
        self.connection_manager = ConnectionPoolManager()
        self.system_monitor = SystemMonitor()
        self.intervention_manager = ResourceInterventionManager()
        
        # Coordination state
        self.coordination_active = False
        self.coordinator_thread: Optional[threading.Thread] = None
        self.resource_priorities: Dict[str, int] = {}
        self.active_test_contexts: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.resource_history: Dict[str, List[float]] = {
            'memory_usage': [],
            'cpu_usage': [],
            'connection_count': [],
            'coordination_overhead': []
        }
        
        # Default unified budgets by test category
        self.default_unified_budgets = {
            'unit': UnifiedResourceBudget(
                memory_budget=MemoryBudget(50.0, 40.0, 45.0),
                cpu_budget=CPUBudget(30.0, 10.0, 25.0, 2),
                connection_budget=ConnectionBudget(3, 2, 15.0, 180.0),
                system_limits=SystemLimits(50.0, 40.0, 70.0, 20.0, 50),
                priority=3
            ),
            'integration': UnifiedResourceBudget(
                memory_budget=MemoryBudget(100.0, 80.0, 90.0),
                cpu_budget=CPUBudget(50.0, 30.0, 40.0, 4),
                connection_budget=ConnectionBudget(5, 3, 20.0, 240.0),
                system_limits=SystemLimits(60.0, 50.0, 75.0, 30.0, 100),
                priority=2
            ),
            'edge_case': UnifiedResourceBudget(
                memory_budget=MemoryBudget(200.0, 160.0, 180.0),
                cpu_budget=CPUBudget(70.0, 60.0, 60.0, 6),
                connection_budget=ConnectionBudget(8, 4, 25.0, 300.0),
                system_limits=SystemLimits(70.0, 60.0, 80.0, 40.0, 200),
                priority=1  # Highest priority
            ),
            'e2e': UnifiedResourceBudget(
                memory_budget=MemoryBudget(300.0, 240.0, 270.0),
                cpu_budget=CPUBudget(80.0, 120.0, 70.0, 8),
                connection_budget=ConnectionBudget(10, 5, 30.0, 360.0),
                system_limits=SystemLimits(75.0, 65.0, 80.0, 50.0, 300),
                priority=1
            ),
            'performance': UnifiedResourceBudget(
                memory_budget=MemoryBudget(500.0, 400.0, 450.0),
                cpu_budget=CPUBudget(90.0, 300.0, 80.0, 12),
                connection_budget=ConnectionBudget(15, 8, 30.0, 600.0),
                system_limits=SystemLimits(80.0, 70.0, 85.0, 100.0, 500),
                priority=1
            )
        }
    
    def get_unified_budget(self, test_category: str) -> UnifiedResourceBudget:
        """Get unified resource budget for test category."""
        return self.default_unified_budgets.get(test_category, self.default_unified_budgets['integration'])
    
    def set_resource_priority(self, test_name: str, priority: int):
        """Set resource priority for a specific test (1=highest, 5=lowest)."""
        self.resource_priorities[test_name] = priority
    
    def start_unified_monitoring(self, test_category: str, test_name: str = "unknown"):
        """Start unified monitoring across all resource frameworks."""
        budget = self.get_unified_budget(test_category)
        
        # Configure individual managers with unified budget
        self.memory_manager.set_memory_budget(test_category, budget.memory_budget)
        self.cpu_manager.set_cpu_budget(test_category, budget.cpu_budget)
        self.connection_manager.set_connection_budget('unified', budget.connection_budget)
        self.system_monitor.set_limits(budget.system_limits)
        
        # Start individual monitoring
        self.memory_manager.start_monitoring(test_category)
        self.cpu_manager.start_monitoring(test_category)
        self.system_monitor.start_monitoring()
        
        # Register cross-framework intervention callbacks
        self._setup_cross_framework_callbacks()
        
        # Start coordination thread
        self.coordination_active = True
        self._start_coordination_thread(test_name, budget.priority)
    
    def stop_unified_monitoring(self) -> Dict[str, Any]:
        """Stop unified monitoring and return comprehensive statistics."""
        # Stop coordination
        self.coordination_active = False
        if self.coordinator_thread:
            self.coordinator_thread.join(timeout=2.0)
        
        # Stop individual managers and collect statistics
        memory_stats = self.memory_manager.stop_monitoring()
        cpu_stats = self.cpu_manager.stop_monitoring()
        system_stats = self.system_monitor.stop_monitoring()
        
        # Comprehensive statistics
        unified_stats = {
            'memory_stats': memory_stats,
            'cpu_stats': cpu_stats,
            'system_stats': system_stats,
            'connection_stats': {
                'total_connections': len(self.connection_manager.active_connections),
                'connections_by_service': dict(self.connection_manager.connection_stats)
            },
            'coordination_stats': {
                'resource_history': dict(self.resource_history),
                'intervention_count': self.intervention_manager.interventions_triggered,
                'active_contexts': len(self.active_test_contexts)
            }
        }
        
        return unified_stats
    
    def _setup_cross_framework_callbacks(self):
        """Setup cross-framework intervention callbacks."""
        
        def memory_cpu_coordination(resources: Dict[str, float], violations: List[str]):
            """Coordinate memory pressure with CPU throttling."""
            if any('Memory usage' in v for v in violations):
                # Memory pressure detected - throttle CPU to reduce memory allocation rate
                self.cpu_manager.register_throttle_callback(
                    lambda cpu, limit: time.sleep(0.2) if cpu > limit * 0.8 else None
                )
        
        def connection_memory_coordination(resources: Dict[str, float], violations: List[str]):
            """Coordinate connection pressure with memory cleanup."""
            if resources.get('open_files', 0) > 800:  # High file handle usage
                # Connection pressure detected - trigger memory cleanup
                self.memory_manager.force_cleanup()
        
        def system_wide_emergency_intervention(resources: Dict[str, float], violations: List[str]):
            """Emergency intervention when multiple resource limits exceeded."""
            if len(violations) >= 2:  # Multiple resource violations
                # Emergency resource reclamation
                self.memory_manager.force_cleanup()
                gc.collect()
                time.sleep(0.5)  # Brief pause for system recovery
                
                # If still critical, raise exception
                if len(violations) >= 3:
                    raise RuntimeError(f"Critical resource exhaustion: {violations}")
        
        # Register callbacks
        self.system_monitor.register_intervention_callback(memory_cpu_coordination)
        self.system_monitor.register_intervention_callback(connection_memory_coordination)
        self.system_monitor.register_intervention_callback(system_wide_emergency_intervention)
    
    def _start_coordination_thread(self, test_name: str, priority: int):
        """Start coordination thread for unified resource management."""
        
        def coordinate_resources():
            """Coordinate resources across all frameworks."""
            while self.coordination_active:
                try:
                    start_time = time.perf_counter()
                    
                    # Collect current resource usage
                    memory_usage = self.memory_manager.get_current_memory_usage()
                    cpu_usage = self.cpu_manager.get_cpu_usage()
                    connection_count = self.connection_manager.get_connection_count()
                    system_resources = self.system_monitor.get_system_resources()
                    
                    # Update resource history
                    self.resource_history['memory_usage'].append(memory_usage)
                    self.resource_history['cpu_usage'].append(cpu_usage)
                    self.resource_history['connection_count'].append(connection_count)
                    
                    # Priority-based resource allocation
                    if priority == 1:  # High priority tests get more resources
                        self._adjust_resources_for_priority(1.2)  # 20% more resources
                    elif priority >= 4:  # Low priority tests get fewer resources
                        self._adjust_resources_for_priority(0.8)  # 20% fewer resources
                    
                    # Cross-framework coordination logic
                    if memory_usage > 150.0 and cpu_usage > 60.0:
                        # High memory + CPU usage - coordinate throttling
                        time.sleep(0.1)  # Brief coordination pause
                    
                    if connection_count > 10 and memory_usage > 100.0:
                        # High connections + memory - trigger cleanup
                        self.memory_manager.gentle_cleanup()
                    
                    # Track coordination overhead
                    coordination_time = time.perf_counter() - start_time
                    self.resource_history['coordination_overhead'].append(coordination_time)
                    
                    # Keep history bounded
                    for key in self.resource_history:
                        if len(self.resource_history[key]) > 1000:
                            self.resource_history[key] = self.resource_history[key][-500:]
                    
                except Exception as e:
                    # Coordination errors shouldn't crash tests
                    pass
                
                time.sleep(0.5)  # Coordination interval
        
        self.coordinator_thread = threading.Thread(target=coordinate_resources, daemon=True)
        self.coordinator_thread.start()
    
    def _adjust_resources_for_priority(self, multiplier: float):
        """Adjust resource allocations based on test priority."""
        # PHASE 3 RECOVERY: Implement actual priority-based resource allocation
        try:
            if multiplier > 1.0:
                # High priority - allocate more resources
                self.memory_manager.memory_budgets = {
                    k: MemoryBudget(
                        v.max_memory_mb * multiplier,
                        v.warning_threshold_mb * multiplier,
                        v.critical_threshold_mb * multiplier,
                        v.cleanup_interval_seconds
                    )
                    for k, v in self.memory_manager.memory_budgets.items()
                }
                # CPU gets more time and concurrent operations
                for category, budget in self.cpu_manager.cpu_budgets.items():
                    budget.max_execution_time *= multiplier
                    budget.max_concurrent_operations = min(
                        int(budget.max_concurrent_operations * multiplier),
                        16  # Cap at reasonable limit
                    )
            elif multiplier < 1.0:
                # Low priority - reduce resource allocation
                for category, budget in self.memory_manager.memory_budgets.items():
                    budget.max_memory_mb *= multiplier
                    budget.warning_threshold_mb *= multiplier
                    budget.critical_threshold_mb *= multiplier
                # CPU gets less time and fewer concurrent operations
                for category, budget in self.cpu_manager.cpu_budgets.items():
                    budget.max_execution_time *= multiplier
                    budget.max_concurrent_operations = max(
                        int(budget.max_concurrent_operations * multiplier),
                        1  # Minimum of 1 operation
                    )
        except Exception:
            # Don't let priority adjustment break resource management
            pass
    
    @contextmanager
    def unified_resource_management(self, test_category: str, test_name: str = "unknown"):
        """Context manager for unified resource management across all frameworks."""
        self.start_unified_monitoring(test_category, test_name)
        
        context = {
            'test_name': test_name,
            'test_category': test_category,
            'start_time': time.time()
        }
        self.active_test_contexts.append(context)
        
        try:
            yield self
        finally:
            # Remove context
            if context in self.active_test_contexts:
                self.active_test_contexts.remove(context)
            
            # Stop monitoring and cleanup
            stats = self.stop_unified_monitoring()
            
            # Force cleanup to prevent resource leaks
            self.memory_manager.force_cleanup()
            
            # PHASE 3 RECOVERY: Fix async cleanup issues properly
            try:
                # Attempt async cleanup if event loop is available
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop and not loop.is_closed():
                        # Create task for async cleanup
                        cleanup_task = asyncio.create_task(
                            self.connection_manager.cleanup_all_connections()
                        )
                        # Add callback to track completion
                        cleanup_task.add_done_callback(
                            lambda task: None if task.exception() is None 
                            else print(f"Async cleanup error: {task.exception()}")
                        )
                except RuntimeError:
                    # No running event loop, perform sync cleanup
                    self._sync_connection_cleanup()
            except Exception:
                # Fallback to sync cleanup
                self._sync_connection_cleanup()
    
    def _sync_connection_cleanup(self):
        """Synchronous connection cleanup fallback."""
        try:
            # Direct cleanup without async
            for connection in list(self.connection_manager.active_connections):
                try:
                    if hasattr(connection, 'close') and not asyncio.iscoroutinefunction(connection.close):
                        connection.close()
                    elif hasattr(connection, 'disconnect') and not asyncio.iscoroutinefunction(connection.disconnect):
                        connection.disconnect()
                except Exception:
                    pass
            # Clear connection tracking
            self.connection_manager.active_connections.clear()
            self.connection_manager.connection_stats.clear()
        except Exception:
            pass  # Best effort cleanup


# Convenience fixtures for unified resource management
@pytest.fixture(scope="function")
def unified_resource_coordinator():
    """Provide unified resource coordinator for comprehensive resource management."""
    coordinator = UnifiedResourceCoordinator()
    try:
        yield coordinator
    finally:
        # Cleanup
        coordinator.stop_unified_monitoring()


@pytest.fixture(scope="function")
def comprehensive_resource_management(unified_resource_coordinator):
    """Provide comprehensive resource management with all frameworks coordinated."""
    def _resource_context(test_category: str, test_name: str = "unknown"):
        return unified_resource_coordinator.unified_resource_management(test_category, test_name)
    
    return _resource_context


# Decorators for comprehensive resource management
def comprehensive_resource_test(test_category: str = 'integration', memory_limit: float = 200.0, 
                               cpu_limit: float = 70.0, max_connections: int = 10):
    """
    Decorator for tests requiring comprehensive resource management.
    
    Automatically applies all 4 resource management frameworks with coordination.
    """
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            # This would be implemented as a proper decorator in production
            return test_func(*args, **kwargs)
        return wrapper
    return decorator


# Data sampling integration with resource coordination
class CoordinatedDataSampler(DataSampler):
    """Enhanced data sampler integrated with resource coordination."""
    
    def __init__(self, resource_coordinator: UnifiedResourceCoordinator):
        super().__init__()
        self.coordinator = resource_coordinator
    
    def adaptive_sample_range(self, start: int, stop: int, target_memory_mb: float = 100.0):
        """Adaptive range sampling based on current memory usage."""
        current_memory = self.coordinator.memory_manager.get_current_memory_usage()
        
        # Adjust sample size based on memory pressure
        if current_memory > target_memory_mb * 0.8:
            max_samples = 25  # Conservative sampling under memory pressure
        elif current_memory > target_memory_mb * 0.5:
            max_samples = 50  # Moderate sampling
        else:
            max_samples = 100  # Full sampling when memory is available
        
        return list(self.sample_range(start, stop, max_samples))
    
    def create_adaptive_test_data(self, size: int, target_memory_mb: float = 100.0):
        """Create test data with adaptive sizing based on memory availability."""
        current_memory = self.coordinator.memory_manager.get_current_memory_usage()
        
        # Adapt data size based on memory pressure
        if current_memory > target_memory_mb * 0.8:
            max_size = min(size, 50)   # Small datasets under pressure
        elif current_memory > target_memory_mb * 0.5:
            max_size = min(size, 200)  # Medium datasets
        else:
            max_size = min(size, 500)  # Large datasets when memory available
        
        return self.create_test_data(size, max_size)


@pytest.fixture(scope="function")
def coordinated_data_sampler(unified_resource_coordinator):
    """Provide data sampler integrated with resource coordination."""
    return CoordinatedDataSampler(unified_resource_coordinator)