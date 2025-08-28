"""
Health Check Service for OAuth Migration Monitoring
==================================================

Comprehensive health monitoring service for operational monitoring
of OAuth authentication, connection pooling, and service integration.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import structlog
from enum import Enum

from services.databricks_connection_pool import get_connection_pool, ConnectionPoolConfig, ConnectionPoolException
from services.databricks_oauth_client import DatabricksOAuthClient
from services.azure_key_vault_client import AzureKeyVaultClient
from services.round_robin_service import RoundRobinService
from services.contact_lookup_service import ContactLookupService
from config.settings import get_settings

# Phase 3 integration monitoring
try:
    from utils.production_monitoring_phase3 import phase3_health_check
    PHASE3_MONITORING_AVAILABLE = True
except ImportError:
    PHASE3_MONITORING_AVAILABLE = False
    
try:
    from services.scenario_tracking_integration import get_tracking_integration
    SCENARIO_TRACKING_AVAILABLE = True
except ImportError:
    SCENARIO_TRACKING_AVAILABLE = False


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ComponentHealth:
    """Individual component health information."""
    
    def __init__(self, name: str, status: HealthStatus, message: str = "", 
                 metrics: Optional[Dict[str, Any]] = None, 
                 response_time_ms: Optional[float] = None):
        self.name = name
        self.status = status
        self.message = message
        self.metrics = metrics or {}
        self.response_time_ms = response_time_ms
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "metrics": self.metrics,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp
        }


class HealthCheckService:
    """Comprehensive health monitoring service for OAuth migration."""
    
    def __init__(self):
        """Initialize health check service."""
        self.logger = structlog.get_logger(__name__)
        self._settings = None
        self._health_cache: Dict[str, ComponentHealth] = {}
        self._cache_duration = timedelta(seconds=30)  # Cache health checks for 30 seconds
    
    async def _get_settings(self):
        """Lazy load settings."""
        if self._settings is None:
            self._settings = await get_settings()
        return self._settings
    
    async def get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status with detailed component information.
        
        Returns:
            Dictionary with comprehensive health status
        """
        self.logger.info("Performing comprehensive health check")
        overall_start = time.time()
        
        try:
            # Check all components concurrently
            health_checks = await asyncio.gather(
                self._check_key_vault_health(),
                self._check_oauth_health(),
                self._check_connection_pool_health(),
                self._check_database_health(),
                self._check_service_health(),
                self._check_scenario_tracking_health(),
                return_exceptions=True
            )
            
            # Process health check results
            component_healths = []
            for result in health_checks:
                if isinstance(result, ComponentHealth):
                    component_healths.append(result)
                elif isinstance(result, Exception):
                    component_healths.append(ComponentHealth(
                        name="unknown_component",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check failed: {str(result)}"
                    ))
            
            # Determine overall health status
            overall_status = self._determine_overall_status(component_healths)
            
            # Collect performance metrics
            performance_metrics = await self._collect_performance_metrics()
            
            total_time = time.time() - overall_start
            
            health_response = {
                "overall_status": overall_status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_time_ms": round(total_time * 1000, 2),
                "components": [comp.to_dict() for comp in component_healths],
                "performance_metrics": performance_metrics,
                "system_info": {
                    "agent_type": "inbox_monitor",
                    "oauth_migration_enabled": True,
                    "connection_pooling_enabled": True
                }
            }
            
            self.logger.info("Comprehensive health check completed", 
                           extra={"overall_status": overall_status.value, "total_time_ms": round(total_time * 1000, 2)})
            
            return health_response
            
        except Exception as e:
            self.logger.error(f"Comprehensive health check failed: {e}")
            return {
                "overall_status": HealthStatus.UNHEALTHY.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "components": [],
                "system_info": {
                    "agent_type": "inbox_monitor",
                    "oauth_migration_enabled": True,
                    "connection_pooling_enabled": True
                }
            }
    
    async def get_simple_health_status(self) -> Dict[str, Any]:
        """Get simple health status for load balancer integration.
        
        Returns:
            Simple health status dictionary
        """
        start_time = time.time()
        
        try:
            # Quick health checks for critical components
            pool_health = await self._check_connection_pool_health_quick()
            oauth_health = await self._check_oauth_health_quick()
            
            # Determine simple status
            if (pool_health.status == HealthStatus.HEALTHY and 
                oauth_health.status == HealthStatus.HEALTHY):
                status = HealthStatus.HEALTHY
                message = "All critical systems operational"
            elif (pool_health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] and
                  oauth_health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]):
                status = HealthStatus.DEGRADED
                message = "Some systems degraded but operational"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Critical systems unavailable"
            
            response_time = time.time() - start_time
            
            return {
                "status": status.value,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_time_ms": round(response_time * 1000, 2)
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_time_ms": round((time.time() - start_time) * 1000, 2)
            }
    
    async def get_readiness_status(self) -> Dict[str, Any]:
        """Get readiness status for Kubernetes readiness probe.
        
        Returns:
            Readiness status dictionary
        """
        start_time = time.time()
        
        try:
            # Check if system is ready to accept traffic
            pool_ready = await self._check_connection_pool_ready()
            oauth_ready = await self._check_oauth_ready()
            
            ready = pool_ready and oauth_ready
            
            response_time = time.time() - start_time
            
            return {
                "ready": ready,
                "status": "READY" if ready else "NOT_READY",
                "message": "System ready to accept traffic" if ready else "System not ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_time_ms": round(response_time * 1000, 2),
                "checks": {
                    "connection_pool_ready": pool_ready,
                    "oauth_ready": oauth_ready
                }
            }
            
        except Exception as e:
            return {
                "ready": False,
                "status": "NOT_READY",
                "message": f"Readiness check failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_time_ms": round((time.time() - start_time) * 1000, 2)
            }
    
    async def _check_key_vault_health(self) -> ComponentHealth:
        """Check Key Vault health status."""
        start_time = time.time()
        
        try:
            settings = await self._get_settings()
            async with AzureKeyVaultClient(settings.key_vault) as kv_client:
                # Test connection
                connection_result = await kv_client.test_connection()
                
                if not connection_result:
                    return ComponentHealth(
                        name="key_vault",
                        status=HealthStatus.UNHEALTHY,
                        message="Key Vault connection test failed",
                        response_time_ms=round((time.time() - start_time) * 1000, 2)
                    )
                
                # Test credential retrieval
                credentials_start = time.time()
                credentials = await kv_client.get_databricks_credentials()
                credentials_time = time.time() - credentials_start
                
                if not credentials.client_id:
                    return ComponentHealth(
                        name="key_vault",
                        status=HealthStatus.DEGRADED,
                        message="Key Vault credentials incomplete",
                        response_time_ms=round((time.time() - start_time) * 1000, 2),
                        metrics={
                            "credential_retrieval_time_ms": round(credentials_time * 1000, 2)
                        }
                    )
                
                return ComponentHealth(
                    name="key_vault",
                    status=HealthStatus.HEALTHY,
                    message="Key Vault operational",
                    response_time_ms=round((time.time() - start_time) * 1000, 2),
                    metrics={
                        "credential_retrieval_time_ms": round(credentials_time * 1000, 2),
                        "connection_test_passed": True
                    }
                )
                
        except Exception as e:
            return ComponentHealth(
                name="key_vault",
                status=HealthStatus.UNHEALTHY,
                message=f"Key Vault error: {str(e)}",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _check_oauth_health(self) -> ComponentHealth:
        """Check OAuth authentication health status."""
        start_time = time.time()
        
        try:
            settings = await self._get_settings()
            async with AzureKeyVaultClient(settings.key_vault) as kv_client:
                from services.databricks_oauth_client import DatabricksOAuthClient
                
                async with DatabricksOAuthClient(settings.databricks_oauth, kv_client) as oauth_client:
                    # Test OAuth token info
                    token_info = await oauth_client.get_current_token_info()
                    
                    if not token_info or not token_info.get("client_id"):
                        return ComponentHealth(
                            name="oauth_authentication",
                            status=HealthStatus.UNHEALTHY,
                            message="OAuth token info unavailable",
                            response_time_ms=round((time.time() - start_time) * 1000, 2)
                        )
                    
                    # Test database connectivity with OAuth
                    db_test_start = time.time()
                    connection_result = await oauth_client.test_connection()
                    db_test_time = time.time() - db_test_start
                    
                    if not connection_result:
                        return ComponentHealth(
                            name="oauth_authentication",
                            status=HealthStatus.DEGRADED,
                            message="OAuth database connection failed",
                            response_time_ms=round((time.time() - start_time) * 1000, 2),
                            metrics={
                                "database_test_time_ms": round(db_test_time * 1000, 2)
                            }
                        )
                    
                    return ComponentHealth(
                        name="oauth_authentication",
                        status=HealthStatus.HEALTHY,
                        message="OAuth authentication operational",
                        response_time_ms=round((time.time() - start_time) * 1000, 2),
                        metrics={
                            "token_info_available": True,
                            "database_connection_test_passed": True,
                            "database_test_time_ms": round(db_test_time * 1000, 2)
                        }
                    )
                    
        except Exception as e:
            return ComponentHealth(
                name="oauth_authentication",
                status=HealthStatus.UNHEALTHY,
                message=f"OAuth error: {str(e)}",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _check_connection_pool_health(self) -> ComponentHealth:
        """Check connection pool health status."""
        start_time = time.time()
        
        try:
            # Check if connection pool is available
            try:
                pool = await get_connection_pool()
            except ConnectionPoolException:
                # Pool not initialized - this is expected for standalone health checks
                # Since OAuth authentication is tested separately, report pool as not active
                return ComponentHealth(
                    name="connection_pool",
                    status=HealthStatus.HEALTHY,
                    message="Connection pool not active (requires running monitor)",
                    response_time_ms=round((time.time() - start_time) * 1000, 2)
                )
            
            if not pool._is_initialized:
                return ComponentHealth(
                    name="connection_pool",
                    status=HealthStatus.UNHEALTHY,
                    message="Connection pool not initialized",
                    response_time_ms=round((time.time() - start_time) * 1000, 2)
                )
            
            # Get pool metrics
            metrics = pool.get_metrics()
            pool_status = pool.get_pool_status()
            
            # Test connection acquisition
            conn_test_start = time.time()
            async with pool.get_connection() as conn:
                conn_result = await conn.test_connection()
            conn_test_time = time.time() - conn_test_start
            
            if not conn_result:
                return ComponentHealth(
                    name="connection_pool",
                    status=HealthStatus.DEGRADED,
                    message="Connection pool connections unhealthy",
                    response_time_ms=round((time.time() - start_time) * 1000, 2),
                    metrics={
                        "total_connections": metrics.total_connections,
                        "active_connections": metrics.active_connections,
                        "connection_test_time_ms": round(conn_test_time * 1000, 2)
                    }
                )
            
            # Determine health based on utilization
            utilization = (metrics.active_connections / metrics.total_connections) * 100
            
            if utilization > 90:
                status = HealthStatus.DEGRADED
                message = f"Connection pool high utilization ({utilization:.1f}%)"
            else:
                status = HealthStatus.HEALTHY
                message = f"Connection pool operational ({utilization:.1f}% utilization)"
            
            return ComponentHealth(
                name="connection_pool",
                status=status,
                message=message,
                response_time_ms=round((time.time() - start_time) * 1000, 2),
                metrics={
                    "total_connections": metrics.total_connections,
                    "active_connections": metrics.active_connections,
                    "total_checkouts": metrics.total_checkouts,
                    "utilization_percent": round(utilization, 1),
                    "connection_test_time_ms": round(conn_test_time * 1000, 2),
                    "is_initialized": pool_status["is_initialized"]
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="connection_pool",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection pool error: {str(e)}",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _check_database_health(self) -> ComponentHealth:
        """Check database connectivity health status."""
        start_time = time.time()
        
        try:
            # Check if connection pool is available
            try:
                pool = await get_connection_pool()
            except ConnectionPoolException:
                # Pool not initialized - this is expected for standalone health checks
                # Since OAuth authentication is tested separately, report database as not active
                return ComponentHealth(
                    name="database_connectivity", 
                    status=HealthStatus.HEALTHY,
                    message="Database not active (requires running monitor)",
                    response_time_ms=round((time.time() - start_time) * 1000, 2)
                )
            
            # Test database operations
            query_start = time.time()
            async with pool.get_connection() as conn:
                result = await conn.execute_sql("SELECT 'health_check' as status, CURRENT_TIMESTAMP() as timestamp")
            query_time = time.time() - query_start
            
            if result.row_count != 1:
                return ComponentHealth(
                    name="database_connectivity",
                    status=HealthStatus.DEGRADED,
                    message="Database query returned unexpected result",
                    response_time_ms=round((time.time() - start_time) * 1000, 2),
                    metrics={
                        "query_time_ms": round(query_time * 1000, 2)
                    }
                )
            
            # Check query performance
            if query_time > 2.0:  # More than 2 seconds is concerning
                status = HealthStatus.DEGRADED
                message = f"Database queries slow ({query_time:.2f}s)"
            else:
                status = HealthStatus.HEALTHY
                message = "Database connectivity operational"
            
            return ComponentHealth(
                name="database_connectivity",
                status=status,
                message=message,
                response_time_ms=round((time.time() - start_time) * 1000, 2),
                metrics={
                    "query_time_ms": round(query_time * 1000, 2),
                    "query_result_count": result.row_count
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="database_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _check_service_health(self) -> ComponentHealth:
        """Check service integration health status."""
        start_time = time.time()
        
        try:
            # First check if connection pool is available
            pool_available = True
            try:
                pool = await get_connection_pool()
            except ConnectionPoolException:
                pool_available = False
            
            # If pool isn't available, report expected status for standalone health check
            if not pool_available:
                return ComponentHealth(
                    name="service_integration",
                    status=HealthStatus.HEALTHY,
                    message="Services not active (requires running monitor)",
                    response_time_ms=round((time.time() - start_time) * 1000, 2),
                    metrics={
                        "pool_required": True,
                        "pool_available": False,
                        "services_tested": 0
                    }
                )
            
            service_results = []
            
            # Test RoundRobinService
            rr_start = time.time()
            try:
                async with RoundRobinService() as rr_service:
                    rr_result = await rr_service.test_connection()
                    rr_time = time.time() - rr_start
                    service_results.append(("round_robin_service", rr_result, rr_time))
            except Exception as e:
                service_results.append(("round_robin_service", False, time.time() - rr_start, str(e)))
            
            # Test ContactLookupService
            cl_start = time.time()
            try:
                async with ContactLookupService() as cl_service:
                    cl_result = await cl_service.test_connection()
                    cl_time = time.time() - cl_start
                    service_results.append(("contact_lookup_service", cl_result, cl_time))
            except Exception as e:
                service_results.append(("contact_lookup_service", False, time.time() - cl_start, str(e)))
            
            # Test ScenarioTrackingIntegration
            st_start = time.time()
            try:
                from services.scenario_tracking_integration import get_tracking_integration
                tracking_integration = await get_tracking_integration()
                st_health = await tracking_integration.get_integration_health()
                st_result = st_health.get("status") in ["healthy", "disabled"]
                st_time = time.time() - st_start
                service_results.append(("scenario_tracking_integration", st_result, st_time))
            except Exception as e:
                service_results.append(("scenario_tracking_integration", False, time.time() - st_start, str(e)))
            
            # Analyze service results
            healthy_services = sum(1 for result in service_results if len(result) == 3 and result[1])
            total_services = len(service_results)
            
            metrics = {}
            failed_services = []
            
            for result in service_results:
                service_name = result[0]
                if len(result) == 3:  # Success case
                    _, success, response_time = result
                    metrics[f"{service_name}_response_time_ms"] = round(response_time * 1000, 2)
                    metrics[f"{service_name}_healthy"] = success
                    if not success:
                        failed_services.append(service_name)
                else:  # Error case
                    _, success, response_time, error = result
                    metrics[f"{service_name}_response_time_ms"] = round(response_time * 1000, 2)
                    metrics[f"{service_name}_healthy"] = False
                    metrics[f"{service_name}_error"] = error
                    failed_services.append(service_name)
            
            # Determine overall service health
            if healthy_services == total_services:
                status = HealthStatus.HEALTHY
                message = f"All {total_services} services operational"
            elif healthy_services > 0:
                status = HealthStatus.DEGRADED
                message = f"{healthy_services}/{total_services} services operational"
            else:
                status = HealthStatus.UNHEALTHY
                message = "All services unavailable"
            
            metrics["healthy_services"] = healthy_services
            metrics["total_services"] = total_services
            
            return ComponentHealth(
                name="service_integration",
                status=status,
                message=message,
                response_time_ms=round((time.time() - start_time) * 1000, 2),
                metrics=metrics
            )
            
        except Exception as e:
            return ComponentHealth(
                name="service_integration",
                status=HealthStatus.UNHEALTHY,
                message=f"Service health check error: {str(e)}",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive performance metrics."""
        try:
            pool = await get_connection_pool()
            metrics = pool.get_metrics()
            
            return {
                "connection_pool": {
                    "total_connections": metrics.total_connections,
                    "active_connections": metrics.active_connections,
                    "total_checkouts": metrics.total_checkouts,
                    "utilization_percent": round((metrics.active_connections / metrics.total_connections) * 100, 1)
                },
                "system": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_type": "inbox_monitor"
                }
            }
        except Exception:
            return {}
    
    async def _check_connection_pool_health_quick(self) -> ComponentHealth:
        """Quick connection pool health check."""
        try:
            pool = await get_connection_pool()
            if not pool._is_initialized:
                return ComponentHealth("connection_pool", HealthStatus.UNHEALTHY, "Pool not initialized")
            return ComponentHealth("connection_pool", HealthStatus.HEALTHY, "Pool initialized")
        except Exception:
            return ComponentHealth("connection_pool", HealthStatus.UNHEALTHY, "Pool unavailable")
    
    async def _check_oauth_health_quick(self) -> ComponentHealth:
        """Quick OAuth health check."""
        try:
            settings = await self._get_settings()
            async with AzureKeyVaultClient(settings.key_vault) as kv_client:
                credentials = await kv_client.get_databricks_credentials()
                if credentials.client_id:
                    return ComponentHealth("oauth", HealthStatus.HEALTHY, "OAuth credentials available")
                else:
                    return ComponentHealth("oauth", HealthStatus.UNHEALTHY, "OAuth credentials missing")
        except Exception:
            return ComponentHealth("oauth", HealthStatus.UNHEALTHY, "OAuth unavailable")
    
    async def _check_scenario_tracking_health(self) -> ComponentHealth:
        """Check scenario tracking integration health."""
        start_time = time.time()
        
        try:
            from services.scenario_tracking_integration import get_tracking_integration
            tracking_integration = await get_tracking_integration()
            health_result = await tracking_integration.get_integration_health()
            response_time = (time.time() - start_time) * 1000
            
            status_map = {
                "healthy": HealthStatus.HEALTHY,
                "degraded": HealthStatus.DEGRADED,
                "unhealthy": HealthStatus.UNHEALTHY,
                "disabled": HealthStatus.HEALTHY,  # Disabled is considered healthy since it's intentional
                "not_initialized": HealthStatus.DEGRADED
            }
            
            status = status_map.get(health_result.get("status"), HealthStatus.UNKNOWN)
            
            # Extract key metrics
            metrics = {
                "enabled": health_result.get("config_enabled", False),
                "initialized": health_result.get("initialized", False),
                "initialization_failed": health_result.get("initialization_failed", False),
            }
            
            # Add batch processing metrics if available
            if "batch_processing" in health_result:
                batch_info = health_result["batch_processing"]
                metrics.update({
                    "batch_enabled": batch_info.get("enabled", False),
                    "batch_queue_length": batch_info.get("queue_length", 0),
                    "batch_task_running": batch_info.get("batch_task_running", False)
                })
            
            # Add retry configuration if available
            if "retry_configuration" in health_result:
                retry_info = health_result["retry_configuration"]
                metrics.update({
                    "retry_max_attempts": retry_info.get("max_attempts", 0),
                    "retry_enabled": retry_info.get("max_attempts", 0) > 0
                })
            
            # Create status message
            if status == HealthStatus.HEALTHY:
                if health_result.get("status") == "disabled":
                    message = "Scenario tracking disabled by configuration"
                else:
                    message = "Scenario tracking operational"
            elif status == HealthStatus.DEGRADED:
                message = f"Scenario tracking degraded: {health_result.get('status', 'unknown')}"
            else:
                message = f"Scenario tracking unhealthy: {health_result.get('status', 'unknown')}"
                
            # Add client status if available
            if "tracking_client" in health_result:
                client_status = health_result["tracking_client"].get("status")
                if client_status and client_status != "healthy":
                    message += f" (client: {client_status})"
            
            # **NEW: Add Phase 3 monitoring metrics if available**
            if PHASE3_MONITORING_AVAILABLE:
                try:
                    phase3_health = await phase3_health_check()
                    
                    # Enhance metrics with Phase 3 data
                    metrics.update({
                        "phase3_monitoring_active": phase3_health.get("monitoring_active", False),
                        "phase3_status": phase3_health.get("status", "unknown"),
                        "sla_compliance_rate": phase3_health.get("sla_compliance", {}).get("compliance_rate"),
                        "availability_rate": phase3_health.get("availability", {}).get("rate"),
                        "avg_overhead_percent": phase3_health.get("performance", {}).get("avg_overhead_percent")
                    })
                    
                    # Update status based on Phase 3 health
                    if phase3_health.get("status") == "degraded" and status == HealthStatus.HEALTHY:
                        status = HealthStatus.DEGRADED
                        message += " (Phase 3 performance degraded)"
                    elif phase3_health.get("status") == "error" and status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                        status = HealthStatus.UNHEALTHY
                        message += " (Phase 3 monitoring error)"
                        
                except Exception as phase3_error:
                    self.logger.debug(f"Phase 3 monitoring check failed: {phase3_error}")
                    metrics["phase3_monitoring_error"] = str(phase3_error)
            
            return ComponentHealth(
                name="scenario_tracking",
                status=status,
                message=message,
                metrics=metrics,
                response_time_ms=round(response_time, 2)
            )
            
        except ImportError:
            return ComponentHealth(
                name="scenario_tracking",
                status=HealthStatus.UNKNOWN,
                message="Scenario tracking module not available",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
        except Exception as e:
            return ComponentHealth(
                name="scenario_tracking",
                status=HealthStatus.UNHEALTHY,
                message=f"Scenario tracking health check failed: {str(e)}",
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _check_connection_pool_ready(self) -> bool:
        """Check if connection pool is ready."""
        try:
            pool = await get_connection_pool()
            return pool._is_initialized and len(pool._connections) > 0
        except Exception:
            return False
    
    async def _check_oauth_ready(self) -> bool:
        """Check if OAuth is ready."""
        try:
            settings = await self._get_settings()
            async with AzureKeyVaultClient(settings.key_vault) as kv_client:
                credentials = await kv_client.get_databricks_credentials()
                return bool(credentials.client_id)
        except Exception:
            return False
    
    def _determine_overall_status(self, component_healths: List[ComponentHealth]) -> HealthStatus:
        """Determine overall health status from component healths."""
        if not component_healths:
            return HealthStatus.UNKNOWN
        
        statuses = [comp.status for comp in component_healths]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN