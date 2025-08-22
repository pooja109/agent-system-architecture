"""
Production Monitoring for Phase 3 Integration
=============================================

Enhanced monitoring capabilities for Phase 3 scenario tracking integration,
addressing the audit finding for production monitoring gaps.

This module provides:
- Real-time performance metrics collection
- SLA monitoring for the 5% overhead requirement
- Alerting for performance degradation
- Dashboard integration for operational visibility
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import statistics
import json

import structlog


logger = structlog.get_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""
    timestamp: datetime
    processing_duration_ms: float
    overhead_percent: float
    operation_type: str
    success: bool
    error_type: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAViolation:
    """SLA violation record."""
    timestamp: datetime
    metric_name: str
    threshold: float
    actual_value: float
    severity: AlertLevel
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Monitoring alert rule configuration."""
    name: str
    metric_path: str
    threshold: float
    comparison: str  # "gt", "lt", "eq", etc.
    level: AlertLevel
    cooldown_seconds: float = 300  # 5 minutes default
    enabled: bool = True
    last_triggered: Optional[datetime] = None


class Phase3MonitoringCollector:
    """
    Production monitoring collector for Phase 3 integration.
    
    Collects performance metrics, tracks SLA compliance, and triggers alerts
    for operational visibility and proactive issue detection.
    """
    
    def __init__(self, 
                 sla_threshold_percent: float = 5.0,
                 measurement_window_minutes: int = 15,
                 alert_callback: Optional[Callable] = None):
        """
        Initialize monitoring collector.
        
        Args:
            sla_threshold_percent: Maximum allowed overhead percentage
            measurement_window_minutes: Time window for aggregating metrics
            alert_callback: Optional callback function for alerts
        """
        self.sla_threshold_percent = sla_threshold_percent
        self.measurement_window = timedelta(minutes=measurement_window_minutes)
        self.alert_callback = alert_callback
        
        # Metric storage
        self.performance_metrics: List[PerformanceMetric] = []
        self.sla_violations: List[SLAViolation] = []
        
        # Alert rules
        self.alert_rules: List[AlertRule] = self._initialize_alert_rules()
        
        # Baseline performance tracking
        self.baseline_performance_ms = 200.0  # Default baseline
        self.baseline_measurements: List[float] = []
        self.baseline_established = False
        
        # Real-time metrics
        self.current_window_metrics: List[PerformanceMetric] = []
        
        # Monitoring state
        self.monitoring_enabled = True
        self.metrics_lock = asyncio.Lock()
        
        self.logger = structlog.get_logger(__name__)
    
    def _initialize_alert_rules(self) -> List[AlertRule]:
        """Initialize default alert rules for Phase 3 monitoring."""
        return [
            AlertRule(
                name="sla_overhead_warning",
                metric_path="overhead_percent",
                threshold=self.sla_threshold_percent * 0.8,  # 80% of SLA threshold
                comparison="gt",
                level=AlertLevel.WARNING,
                cooldown_seconds=300
            ),
            AlertRule(
                name="sla_overhead_critical",
                metric_path="overhead_percent",
                threshold=self.sla_threshold_percent,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                cooldown_seconds=60
            ),
            AlertRule(
                name="high_failure_rate",
                metric_path="failure_rate",
                threshold=0.1,  # 10% failure rate
                comparison="gt",
                level=AlertLevel.WARNING,
                cooldown_seconds=180
            ),
            AlertRule(
                name="tracking_integration_down",
                metric_path="availability",
                threshold=0.95,  # 95% availability
                comparison="lt",
                level=AlertLevel.CRITICAL,
                cooldown_seconds=30
            )
        ]
    
    async def record_performance_metric(self,
                                       processing_duration_ms: float,
                                       baseline_time_ms: float,
                                       operation_type: str,
                                       success: bool,
                                       error_type: Optional[str] = None,
                                       **context) -> None:
        """
        Record a performance metric for monitoring.
        
        Args:
            processing_duration_ms: Time taken for the operation
            baseline_time_ms: Expected baseline time
            operation_type: Type of operation being measured
            success: Whether the operation succeeded
            error_type: Type of error if operation failed
            **context: Additional context information
        """
        if not self.monitoring_enabled:
            return
        
        # Calculate overhead percentage
        overhead_percent = ((processing_duration_ms - baseline_time_ms) / baseline_time_ms) * 100 if baseline_time_ms > 0 else 0
        
        metric = PerformanceMetric(
            timestamp=datetime.now(timezone.utc),
            processing_duration_ms=processing_duration_ms,
            overhead_percent=overhead_percent,
            operation_type=operation_type,
            success=success,
            error_type=error_type,
            context=context
        )
        
        async with self.metrics_lock:
            self.performance_metrics.append(metric)
            self.current_window_metrics.append(metric)
            
            # Establish baseline if not done
            if not self.baseline_established and success:
                self.baseline_measurements.append(processing_duration_ms)
                if len(self.baseline_measurements) >= 20:  # Need sufficient samples
                    self.baseline_performance_ms = statistics.mean(self.baseline_measurements)
                    self.baseline_established = True
                    self.logger.info(
                        "Baseline performance established",
                        baseline_ms=self.baseline_performance_ms,
                        sample_size=len(self.baseline_measurements)
                    )
            
            # Check for SLA violations
            await self._check_sla_violations(metric)
            
            # Cleanup old metrics
            await self._cleanup_old_metrics()
    
    async def _check_sla_violations(self, metric: PerformanceMetric) -> None:
        """Check if a metric violates SLA requirements."""
        
        # Check overhead SLA
        if metric.overhead_percent > self.sla_threshold_percent:
            violation = SLAViolation(
                timestamp=metric.timestamp,
                metric_name="processing_overhead",
                threshold=self.sla_threshold_percent,
                actual_value=metric.overhead_percent,
                severity=AlertLevel.CRITICAL if metric.overhead_percent > self.sla_threshold_percent * 1.5 else AlertLevel.WARNING,
                context={
                    'operation_type': metric.operation_type,
                    'processing_duration_ms': metric.processing_duration_ms,
                    'baseline_performance_ms': self.baseline_performance_ms
                }
            )
            
            self.sla_violations.append(violation)
            await self._trigger_alert(violation)
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current aggregated metrics for monitoring dashboard."""
        
        async with self.metrics_lock:
            current_time = datetime.now(timezone.utc)
            window_start = current_time - self.measurement_window
            
            # Filter metrics to current window
            window_metrics = [
                m for m in self.performance_metrics
                if m.timestamp >= window_start
            ]
            
            if not window_metrics:
                return {
                    'status': 'no_data',
                    'timestamp': current_time.isoformat(),
                    'window_minutes': self.measurement_window.total_seconds() / 60
                }
            
            # Calculate aggregated metrics
            successful_metrics = [m for m in window_metrics if m.success]
            failed_metrics = [m for m in window_metrics if not m.success]
            
            # Performance statistics
            processing_times = [m.processing_duration_ms for m in successful_metrics]
            overhead_percentages = [m.overhead_percent for m in successful_metrics]
            
            avg_processing_time = statistics.mean(processing_times) if processing_times else 0
            avg_overhead_percent = statistics.mean(overhead_percentages) if overhead_percentages else 0
            p95_processing_time = statistics.quantiles(processing_times, n=20)[18] if len(processing_times) >= 20 else (max(processing_times) if processing_times else 0)
            p99_processing_time = statistics.quantiles(processing_times, n=100)[98] if len(processing_times) >= 100 else (max(processing_times) if processing_times else 0)
            
            # SLA compliance
            sla_compliant_ops = len([m for m in successful_metrics if m.overhead_percent <= self.sla_threshold_percent])
            sla_compliance_rate = (sla_compliant_ops / len(successful_metrics)) if successful_metrics else 1.0
            
            # Availability
            total_ops = len(window_metrics)
            successful_ops = len(successful_metrics)
            availability = (successful_ops / total_ops) if total_ops > 0 else 1.0
            
            # Recent violations
            recent_violations = [
                v for v in self.sla_violations
                if v.timestamp >= window_start
            ]
            
            return {
                'status': 'healthy' if sla_compliance_rate >= 0.95 and availability >= 0.99 else 'degraded',
                'timestamp': current_time.isoformat(),
                'window_minutes': self.measurement_window.total_seconds() / 60,
                'sample_size': len(window_metrics),
                'performance': {
                    'avg_processing_duration_ms': round(avg_processing_time, 2),
                    'avg_overhead_percent': round(avg_overhead_percent, 2),
                    'p95_processing_duration_ms': round(p95_processing_time, 2),
                    'p99_processing_duration_ms': round(p99_processing_time, 2),
                    'baseline_performance_ms': self.baseline_performance_ms,
                    'baseline_established': self.baseline_established
                },
                'sla_compliance': {
                    'threshold_percent': self.sla_threshold_percent,
                    'compliance_rate': round(sla_compliance_rate * 100, 2),
                    'compliant_operations': sla_compliant_ops,
                    'total_successful_operations': len(successful_metrics),
                    'meets_sla': sla_compliance_rate >= 0.95
                },
                'availability': {
                    'rate': round(availability * 100, 2),
                    'successful_operations': successful_ops,
                    'total_operations': total_ops,
                    'failed_operations': len(failed_metrics)
                },
                'violations': {
                    'recent_count': len(recent_violations),
                    'critical_count': len([v for v in recent_violations if v.severity == AlertLevel.CRITICAL]),
                    'warning_count': len([v for v in recent_violations if v.severity == AlertLevel.WARNING])
                },
                'error_analysis': {
                    'error_types': list(set([m.error_type for m in failed_metrics if m.error_type])),
                    'most_common_errors': self._get_error_frequency(failed_metrics)
                }
            }
    
    def _get_error_frequency(self, failed_metrics: List[PerformanceMetric]) -> Dict[str, int]:
        """Get frequency count of error types."""
        error_counts = {}
        for metric in failed_metrics:
            if metric.error_type:
                error_counts[metric.error_type] = error_counts.get(metric.error_type, 0) + 1
        
        # Sort by frequency
        return dict(sorted(error_counts.items(), key=lambda x: x[1], reverse=True))
    
    async def _trigger_alert(self, violation: SLAViolation) -> None:
        """Trigger an alert for SLA violation."""
        
        # Find matching alert rule
        alert_rule = None
        for rule in self.alert_rules:
            if (rule.metric_path == "overhead_percent" and 
                violation.metric_name == "processing_overhead" and
                violation.actual_value >= rule.threshold):
                alert_rule = rule
                break
        
        if not alert_rule or not alert_rule.enabled:
            return
        
        # Check cooldown period
        if (alert_rule.last_triggered and 
            (datetime.now(timezone.utc) - alert_rule.last_triggered).total_seconds() < alert_rule.cooldown_seconds):
            return
        
        # Update last triggered time
        alert_rule.last_triggered = datetime.now(timezone.utc)
        
        # Create alert payload
        alert_payload = {
            'alert_name': alert_rule.name,
            'level': alert_rule.level.value,
            'metric': violation.metric_name,
            'threshold': violation.threshold,
            'actual_value': violation.actual_value,
            'timestamp': violation.timestamp.isoformat(),
            'context': violation.context,
            'message': f"Phase 3 integration SLA violation: {violation.metric_name} = {violation.actual_value:.2f} (threshold: {violation.threshold:.2f})"
        }
        
        # Log the alert
        self.logger.warning(
            "Phase 3 monitoring alert triggered",
            **alert_payload
        )
        
        # Call alert callback if provided
        if self.alert_callback:
            try:
                await self.alert_callback(alert_payload)
            except Exception as e:
                self.logger.error("Alert callback failed", error=str(e))
    
    async def _cleanup_old_metrics(self) -> None:
        """Clean up metrics older than the retention window."""
        cutoff_time = datetime.now(timezone.utc) - (self.measurement_window * 4)  # Keep 4x the window
        
        self.performance_metrics = [
            m for m in self.performance_metrics
            if m.timestamp >= cutoff_time
        ]
        
        self.sla_violations = [
            v for v in self.sla_violations
            if v.timestamp >= cutoff_time
        ]
    
    async def generate_monitoring_report(self) -> Dict[str, Any]:
        """Generate comprehensive monitoring report for operations team."""
        
        metrics = await self.get_current_metrics()
        
        # Add trend analysis
        async with self.metrics_lock:
            # Get metrics from different time periods for trend analysis
            current_time = datetime.now(timezone.utc)
            
            periods = {
                'last_hour': current_time - timedelta(hours=1),
                'last_4_hours': current_time - timedelta(hours=4),
                'last_24_hours': current_time - timedelta(hours=24)
            }
            
            trends = {}
            for period_name, start_time in periods.items():
                period_metrics = [
                    m for m in self.performance_metrics
                    if m.timestamp >= start_time and m.success
                ]
                
                if period_metrics:
                    avg_overhead = statistics.mean([m.overhead_percent for m in period_metrics])
                    trends[period_name] = {
                        'avg_overhead_percent': round(avg_overhead, 2),
                        'sample_count': len(period_metrics),
                        'sla_compliant': avg_overhead <= self.sla_threshold_percent
                    }
                else:
                    trends[period_name] = {
                        'avg_overhead_percent': 0,
                        'sample_count': 0,
                        'sla_compliant': True
                    }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, trends)
        
        return {
            'report_timestamp': current_time.isoformat(),
            'monitoring_status': 'active' if self.monitoring_enabled else 'inactive',
            'current_metrics': metrics,
            'trends': trends,
            'recommendations': recommendations,
            'configuration': {
                'sla_threshold_percent': self.sla_threshold_percent,
                'measurement_window_minutes': self.measurement_window.total_seconds() / 60,
                'baseline_established': self.baseline_established,
                'baseline_performance_ms': self.baseline_performance_ms
            }
        }
    
    def _generate_recommendations(self, metrics: Dict[str, Any], trends: Dict[str, Any]) -> List[str]:
        """Generate operational recommendations based on metrics."""
        recommendations = []
        
        if metrics.get('status') == 'degraded':
            recommendations.append("🔴 System is experiencing degraded performance - investigate immediately")
        
        sla_compliance = metrics.get('sla_compliance', {})
        if sla_compliance.get('compliance_rate', 100) < 95:
            recommendations.append(f"⚠️ SLA compliance at {sla_compliance.get('compliance_rate', 0):.1f}% - below 95% target")
        
        availability = metrics.get('availability', {})
        if availability.get('rate', 100) < 99:
            recommendations.append(f"⚠️ Availability at {availability.get('rate', 100):.1f}% - below 99% target")
        
        # Check trends
        current_overhead = metrics.get('performance', {}).get('avg_overhead_percent', 0)
        if current_overhead > self.sla_threshold_percent * 0.8:
            recommendations.append(f"⚠️ Performance overhead at {current_overhead:.1f}% - approaching {self.sla_threshold_percent}% SLA limit")
        
        # Error analysis
        error_analysis = metrics.get('error_analysis', {})
        if error_analysis.get('most_common_errors'):
            top_error = list(error_analysis['most_common_errors'].keys())[0]
            recommendations.append(f"🔍 Most frequent error: {top_error} - investigate root cause")
        
        if not recommendations:
            recommendations.append("✅ All systems operating within normal parameters")
        
        return recommendations


# Global monitoring instance
_monitoring_collector: Optional[Phase3MonitoringCollector] = None

def get_monitoring_collector() -> Phase3MonitoringCollector:
    """Get or create global monitoring collector instance."""
    global _monitoring_collector
    
    if _monitoring_collector is None:
        _monitoring_collector = Phase3MonitoringCollector()
    
    return _monitoring_collector


async def record_phase3_metric(processing_duration_ms: float, 
                              baseline_time_ms: float,
                              operation_type: str,
                              success: bool,
                              **context) -> None:
    """Convenient function to record Phase 3 performance metrics."""
    collector = get_monitoring_collector()
    await collector.record_performance_metric(
        processing_duration_ms=processing_duration_ms,
        baseline_time_ms=baseline_time_ms,
        operation_type=operation_type,
        success=success,
        **context
    )


async def get_phase3_metrics() -> Dict[str, Any]:
    """Get current Phase 3 performance metrics."""
    collector = get_monitoring_collector()
    return await collector.get_current_metrics()


async def generate_phase3_report() -> Dict[str, Any]:
    """Generate comprehensive Phase 3 monitoring report."""
    collector = get_monitoring_collector()
    return await collector.generate_monitoring_report()


# Integration with existing health check system
async def phase3_health_check() -> Dict[str, Any]:
    """Health check specifically for Phase 3 integration."""
    try:
        collector = get_monitoring_collector()
        metrics = await collector.get_current_metrics()
        
        # Determine overall health
        is_healthy = (
            metrics.get('status') == 'healthy' and
            metrics.get('sla_compliance', {}).get('meets_sla', False) and
            metrics.get('availability', {}).get('rate', 0) >= 99
        )
        
        return {
            'service': 'phase3_scenario_tracking_integration',
            'status': 'healthy' if is_healthy else 'degraded',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'performance': metrics.get('performance', {}),
            'sla_compliance': metrics.get('sla_compliance', {}),
            'availability': metrics.get('availability', {}),
            'monitoring_active': collector.monitoring_enabled
        }
        
    except Exception as e:
        return {
            'service': 'phase3_scenario_tracking_integration',
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e),
            'monitoring_active': False
        }