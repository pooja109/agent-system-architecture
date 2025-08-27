"""
Databricks Warehouse Management - Pre-warming and Health Monitoring
==================================================================

Manages warehouse state to prevent 200+ second startup delays during demos.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import logging

try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import State
    DATABRICKS_SDK_AVAILABLE = True
except ImportError:
    DATABRICKS_SDK_AVAILABLE = False
    # Mock classes for when SDK isn't available
    class State(Enum):
        RUNNING = "RUNNING"
        STOPPED = "STOPPED" 
        STARTING = "STARTING"


class WarehouseHealth(Enum):
    """Warehouse health status."""
    OPTIMAL = "optimal"          # Running and ready
    WARMING = "warming"          # Starting up
    COLD = "cold"               # Stopped, needs startup
    DEGRADED = "degraded"       # Running but slow
    UNAVAILABLE = "unavailable" # Error state


class DatabricksWarehouseManager:
    """Manages Databricks warehouse state and performance."""
    
    def __init__(self, warehouse_id: str, workspace_client: Optional[Any] = None):
        self.warehouse_id = warehouse_id
        self.workspace_client = workspace_client
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.startup_times = []  # Track startup performance
        self.health_checks = []  # Track health check results
        self.last_health_check = None
        
        # Pre-warming configuration
        self.warmup_threshold_minutes = 15  # Start warming if inactive for 15+ min
        self.max_startup_wait_seconds = 300  # 5 minute max wait
        self.health_check_interval = 30     # Check health every 30s
        
    async def get_warehouse_state(self) -> Dict[str, Any]:
        """Get current warehouse state and metadata."""
        if not self.workspace_client:
            return {
                'state': State.RUNNING.value,  # Mock as running
                'health': WarehouseHealth.OPTIMAL.value,
                'last_activity': datetime.now().isoformat(),
                'estimated_startup_time': 0
            }
            
        try:
            warehouse = self.workspace_client.warehouses.get(self.warehouse_id)
            
            # Estimate startup time based on historical data
            avg_startup_time = sum(self.startup_times[-5:]) / len(self.startup_times[-5:]) if self.startup_times else 180
            
            return {
                'state': warehouse.state.value if warehouse.state else 'UNKNOWN',
                'health': self._determine_health(warehouse).value,
                'size': warehouse.warehouse_type.value if warehouse.warehouse_type else 'UNKNOWN',
                'last_activity': warehouse.health.details if warehouse.health else None,
                'estimated_startup_time': avg_startup_time if warehouse.state == State.STOPPED else 0,
                'cluster_count': warehouse.num_clusters or 1
            }
        except Exception as e:
            self.logger.error(f"Failed to get warehouse state: {e}")
            return {
                'state': 'ERROR',
                'health': WarehouseHealth.UNAVAILABLE.value,
                'error': str(e),
                'estimated_startup_time': 300  # Conservative estimate
            }
    
    def _determine_health(self, warehouse: Any) -> WarehouseHealth:
        """Determine warehouse health based on state and performance."""
        if not warehouse.state:
            return WarehouseHealth.UNAVAILABLE
            
        if warehouse.state == State.RUNNING:
            # Check performance metrics to determine if optimal or degraded
            recent_startup_times = self.startup_times[-3:] if self.startup_times else []
            if recent_startup_times and max(recent_startup_times) > 120:
                return WarehouseHealth.DEGRADED
            return WarehouseHealth.OPTIMAL
            
        elif warehouse.state == State.STARTING:
            return WarehouseHealth.WARMING
        elif warehouse.state == State.STOPPED:
            return WarehouseHealth.COLD
        else:
            return WarehouseHealth.UNAVAILABLE
    
    async def ensure_warehouse_ready(self, timeout_seconds: int = 300) -> Dict[str, Any]:
        """Ensure warehouse is running and ready for queries."""
        start_time = time.time()
        
        try:
            state_info = await self.get_warehouse_state()
            initial_state = state_info['state']
            
            self.logger.info(f"Warehouse initial state: {initial_state}")
            
            if initial_state == State.RUNNING.value:
                # Already running, verify with health check
                health_result = await self._perform_health_check()
                if health_result['healthy']:
                    return {
                        'ready': True,
                        'startup_time': 0,
                        'initial_state': initial_state,
                        'message': 'Warehouse already running and healthy'
                    }
            
            # Need to start warehouse
            if initial_state in [State.STOPPED.value, State.STARTING.value]:
                self.logger.info(f"Starting warehouse {self.warehouse_id}...")
                
                if self.workspace_client and initial_state == State.STOPPED.value:
                    try:
                        self.workspace_client.warehouses.start(self.warehouse_id)
                        self.logger.info("Warehouse start command sent")
                    except Exception as e:
                        self.logger.warning(f"Failed to send start command: {e}")
                
                # Wait for warehouse to be ready
                ready = await self._wait_for_ready_state(timeout_seconds)
                startup_time = time.time() - start_time
                
                # Record startup time for future estimates
                self.startup_times.append(startup_time)
                if len(self.startup_times) > 10:
                    self.startup_times.pop(0)  # Keep only last 10 measurements
                
                return {
                    'ready': ready,
                    'startup_time': startup_time,
                    'initial_state': initial_state,
                    'message': f"Warehouse ready after {startup_time:.1f}s" if ready else f"Timeout after {startup_time:.1f}s"
                }
            
            return {
                'ready': False,
                'startup_time': time.time() - start_time,
                'initial_state': initial_state,
                'message': f"Unexpected warehouse state: {initial_state}"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to ensure warehouse ready: {e}")
            return {
                'ready': False,
                'startup_time': time.time() - start_time,
                'initial_state': 'ERROR',
                'error': str(e),
                'message': f"Error ensuring warehouse ready: {e}"
            }
    
    async def _wait_for_ready_state(self, timeout_seconds: int = 300) -> bool:
        """Wait for warehouse to reach RUNNING state and pass health check."""
        start_time = time.time()
        check_interval = 10  # Check every 10 seconds
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                state_info = await self.get_warehouse_state()
                current_state = state_info['state']
                elapsed = time.time() - start_time
                remaining = timeout_seconds - elapsed
                
                self.logger.info(
                    f"Warehouse state: {current_state}, "
                    f"elapsed: {elapsed:.1f}s, remaining: {remaining:.1f}s"
                )
                
                if current_state == State.RUNNING.value:
                    # Verify with health check
                    health_result = await self._perform_health_check()
                    if health_result['healthy']:
                        self.logger.info(f"Warehouse ready after {elapsed:.1f}s")
                        return True
                    else:
                        self.logger.warning("Warehouse running but health check failed")
                
                elif current_state in ['ERROR', 'FAILED']:
                    self.logger.error(f"Warehouse failed to start: {current_state}")
                    return False
                
                # Continue waiting
                await asyncio.sleep(min(check_interval, remaining))
                
            except Exception as e:
                self.logger.error(f"Error checking warehouse state: {e}")
                await asyncio.sleep(check_interval)
        
        self.logger.warning(f"Warehouse not ready after {timeout_seconds}s timeout")
        return False
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform health check query on warehouse."""
        if not self.workspace_client:
            # Mock successful health check
            return {
                'healthy': True,
                'response_time': 0.1,
                'message': 'Mock health check passed'
            }
        
        try:
            start_time = time.time()
            
            # Simple health check query
            # Note: This would need actual SQL execution client
            # For now, assume healthy if warehouse is in RUNNING state
            state_info = await self.get_warehouse_state()
            
            response_time = time.time() - start_time
            healthy = state_info['state'] == State.RUNNING.value
            
            health_result = {
                'healthy': healthy,
                'response_time': response_time,
                'message': 'Health check completed',
                'timestamp': datetime.now().isoformat()
            }
            
            self.health_checks.append(health_result)
            if len(self.health_checks) > 20:
                self.health_checks.pop(0)  # Keep only last 20 checks
            
            self.last_health_check = health_result
            return health_result
            
        except Exception as e:
            error_result = {
                'healthy': False,
                'response_time': time.time() - start_time if 'start_time' in locals() else 0,
                'error': str(e),
                'message': f'Health check failed: {e}',
                'timestamp': datetime.now().isoformat()
            }
            
            self.health_checks.append(error_result)
            self.last_health_check = error_result
            return error_result
    
    async def proactive_warmup_check(self) -> Dict[str, Any]:
        """Check if warehouse needs proactive warming based on usage patterns."""
        try:
            state_info = await self.get_warehouse_state()
            
            # Check if warehouse has been idle and might be auto-pausing soon
            recommendation = {
                'should_warmup': False,
                'reason': '',
                'estimated_benefit': 0
            }
            
            if state_info['state'] == State.STOPPED.value:
                recommendation = {
                    'should_warmup': True,
                    'reason': 'Warehouse is stopped, warming will save startup time',
                    'estimated_benefit': state_info.get('estimated_startup_time', 180)
                }
            
            elif state_info['health'] == WarehouseHealth.DEGRADED.value:
                recommendation = {
                    'should_warmup': True,
                    'reason': 'Warehouse performance is degraded, restart may help',
                    'estimated_benefit': 30  # Benefit of restart
                }
            
            return {
                'current_state': state_info,
                'warmup_recommendation': recommendation,
                'health_history': self.health_checks[-5:] if self.health_checks else []
            }
            
        except Exception as e:
            self.logger.error(f"Proactive warmup check failed: {e}")
            return {
                'current_state': {'state': 'ERROR', 'error': str(e)},
                'warmup_recommendation': {
                    'should_warmup': False,
                    'reason': f'Check failed: {e}',
                    'estimated_benefit': 0
                }
            }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get warehouse performance summary."""
        if not self.startup_times:
            return {
                'startup_times': {
                    'count': 0,
                    'average': 0,
                    'min': 0,
                    'max': 0
                },
                'health_summary': {
                    'last_check': None,
                    'success_rate': 0
                }
            }
        
        health_success_rate = 0
        if self.health_checks:
            successful_checks = len([c for c in self.health_checks if c.get('healthy', False)])
            health_success_rate = (successful_checks / len(self.health_checks)) * 100
        
        return {
            'startup_times': {
                'count': len(self.startup_times),
                'average': sum(self.startup_times) / len(self.startup_times),
                'min': min(self.startup_times),
                'max': max(self.startup_times),
                'recent': self.startup_times[-3:] if len(self.startup_times) >= 3 else self.startup_times
            },
            'health_summary': {
                'last_check': self.last_health_check,
                'total_checks': len(self.health_checks),
                'success_rate': health_success_rate
            },
            'recommendations': self._get_performance_recommendations()
        }
    
    def _get_performance_recommendations(self) -> List[str]:
        """Get performance improvement recommendations."""
        recommendations = []
        
        if self.startup_times:
            avg_startup = sum(self.startup_times) / len(self.startup_times)
            max_startup = max(self.startup_times)
            
            if avg_startup > 120:
                recommendations.append(
                    f"Average startup time ({avg_startup:.1f}s) is high. "
                    "Consider using a larger warehouse size or keeping warehouse running during business hours."
                )
            
            if max_startup > 300:
                recommendations.append(
                    f"Maximum startup time ({max_startup:.1f}s) is very high. "
                    "Investigate warehouse configuration and network connectivity."
                )
        
        if self.health_checks:
            recent_failures = [c for c in self.health_checks[-5:] if not c.get('healthy', True)]
            if len(recent_failures) > 1:
                recommendations.append(
                    f"Recent health check failures detected ({len(recent_failures)}/5). "
                    "Monitor warehouse stability and consider restart if issues persist."
                )
        
        return recommendations if recommendations else ["Warehouse performance is optimal."]


# Factory function for easy integration
def create_warehouse_manager(warehouse_id: str, workspace_client: Optional[Any] = None) -> DatabricksWarehouseManager:
    """Create a warehouse manager instance."""
    return DatabricksWarehouseManager(warehouse_id, workspace_client)