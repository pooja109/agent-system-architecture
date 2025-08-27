"""
Regression prevention system to monitor test health and prevent future exclusions.

This module provides comprehensive test health monitoring to detect performance
degradation, resource usage increases, and reliability issues before they lead
to test exclusions.
"""
import pytest
import time
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import threading


@dataclass
class TestHealthMetric:
    """Test health metric data point."""
    test_name: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    success: bool
    timestamp: datetime
    execution_mode: str
    error_message: Optional[str] = None


@dataclass
class TestHealthAlert:
    """Test health alert definition."""
    alert_type: str
    test_name: str
    metric: str
    current_value: float
    threshold_value: float
    trend: str
    severity: str
    message: str
    timestamp: datetime


class TestHealthMonitor:
    """Monitors test health and prevents regression to exclusion status."""
    
    def __init__(self, db_path: Path = Path("test_health.db")):
        self.db_path = db_path
        self.init_database()
        self.alert_handlers: List[Callable[[TestHealthAlert], None]] = []
        
        # Health thresholds
        self.thresholds = {
            'execution_time_warning': 30.0,
            'execution_time_critical': 60.0,
            'memory_usage_warning': 100.0,  # MB
            'memory_usage_critical': 200.0,
            'cpu_usage_warning': 70.0,      # Percent
            'cpu_usage_critical': 90.0,
            'failure_rate_warning': 0.1,    # 10%
            'failure_rate_critical': 0.2    # 20%
        }
        
        # Trend analysis settings
        self.trend_window_days = 7
        self.trend_degradation_threshold = 1.5  # 50% performance degradation
        
    def init_database(self):
        """Initialize health monitoring database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    execution_time REAL NOT NULL,
                    memory_usage REAL NOT NULL,
                    cpu_usage REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    timestamp TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    threshold_value REAL NOT NULL,
                    trend TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_test_metrics_name_time 
                ON test_metrics(test_name, timestamp)
            """)
    
    def record_test_metric(self, metric: TestHealthMetric):
        """Record test health metric."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO test_metrics 
                (test_name, execution_time, memory_usage, cpu_usage, success, timestamp, execution_mode, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.test_name,
                metric.execution_time,
                metric.memory_usage,
                metric.cpu_usage,
                metric.success,
                metric.timestamp.isoformat(),
                metric.execution_mode,
                metric.error_message
            ))
    
    def analyze_test_health(self, test_name: str, days_back: int = 7) -> Dict[str, Any]:
        """Analyze health trends for a specific test."""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT execution_time, memory_usage, cpu_usage, success, timestamp
                FROM test_metrics 
                WHERE test_name = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """, (test_name, cutoff_date.isoformat()))
            
            metrics = cursor.fetchall()
        
        if not metrics:
            return {'status': 'no_data', 'test_name': test_name}
        
        # Calculate statistics
        execution_times = [m[0] for m in metrics]
        memory_usages = [m[1] for m in metrics]
        cpu_usages = [m[2] for m in metrics]
        successes = [m[3] for m in metrics]
        
        analysis = {
            'test_name': test_name,
            'data_points': len(metrics),
            'execution_time': {
                'mean': sum(execution_times) / len(execution_times),
                'max': max(execution_times),
                'min': min(execution_times),
                'trend': self.calculate_trend(execution_times)
            },
            'memory_usage': {
                'mean': sum(memory_usages) / len(memory_usages),
                'max': max(memory_usages),
                'min': min(memory_usages),
                'trend': self.calculate_trend(memory_usages)
            },
            'cpu_usage': {
                'mean': sum(cpu_usages) / len(cpu_usages),
                'max': max(cpu_usages),
                'min': min(cpu_usages),
                'trend': self.calculate_trend(cpu_usages)
            },
            'success_rate': sum(successes) / len(successes),
            'failure_rate': 1.0 - (sum(successes) / len(successes))
        }
        
        return analysis
    
    def calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for values."""
        if len(values) < 2:
            return 'insufficient_data'
        
        # Simple trend calculation - compare first half to second half
        mid_point = len(values) // 2
        first_half_avg = sum(values[:mid_point]) / mid_point
        second_half_avg = sum(values[mid_point:]) / (len(values) - mid_point)
        
        change_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else float('inf')
        
        if change_ratio > 1.2:
            return 'degrading'
        elif change_ratio < 0.8:
            return 'improving'
        else:
            return 'stable'
    
    def check_for_alerts(self, test_name: str) -> List[TestHealthAlert]:
        """Check if test requires alerts based on health analysis."""
        analysis = self.analyze_test_health(test_name)
        alerts = []
        
        if analysis.get('status') == 'no_data':
            return alerts
        
        # Check execution time alerts
        if analysis['execution_time']['mean'] > self.thresholds['execution_time_critical']:
            alerts.append(TestHealthAlert(
                alert_type='performance_degradation',
                test_name=test_name,
                metric='execution_time',
                current_value=analysis['execution_time']['mean'],
                threshold_value=self.thresholds['execution_time_critical'],
                trend=analysis['execution_time']['trend'],
                severity='critical',
                message=f"Test execution time {analysis['execution_time']['mean']:.1f}s exceeds critical threshold",
                timestamp=datetime.now()
            ))
        elif analysis['execution_time']['mean'] > self.thresholds['execution_time_warning']:
            alerts.append(TestHealthAlert(
                alert_type='performance_warning',
                test_name=test_name,
                metric='execution_time',
                current_value=analysis['execution_time']['mean'],
                threshold_value=self.thresholds['execution_time_warning'],
                trend=analysis['execution_time']['trend'],
                severity='warning',
                message=f"Test execution time {analysis['execution_time']['mean']:.1f}s approaching threshold",
                timestamp=datetime.now()
            ))
        
        # Check memory alerts
        if analysis['memory_usage']['mean'] > self.thresholds['memory_usage_critical']:
            alerts.append(TestHealthAlert(
                alert_type='memory_pressure',
                test_name=test_name,
                metric='memory_usage',
                current_value=analysis['memory_usage']['mean'],
                threshold_value=self.thresholds['memory_usage_critical'],
                trend=analysis['memory_usage']['trend'],
                severity='critical',
                message=f"Test memory usage {analysis['memory_usage']['mean']:.1f}MB exceeds critical threshold",
                timestamp=datetime.now()
            ))
        
        # Check failure rate alerts
        if analysis['failure_rate'] > self.thresholds['failure_rate_critical']:
            alerts.append(TestHealthAlert(
                alert_type='reliability_issue',
                test_name=test_name,
                metric='failure_rate',
                current_value=analysis['failure_rate'],
                threshold_value=self.thresholds['failure_rate_critical'],
                trend='degrading',
                severity='critical',
                message=f"Test failure rate {analysis['failure_rate']:.1%} indicates reliability issues",
                timestamp=datetime.now()
            ))
        
        # Record alerts
        for alert in alerts:
            self.record_alert(alert)
        
        return alerts
    
    def record_alert(self, alert: TestHealthAlert):
        """Record alert in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO test_alerts 
                (alert_type, test_name, metric, current_value, threshold_value, trend, severity, message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_type,
                alert.test_name,
                alert.metric,
                alert.current_value,
                alert.threshold_value,
                alert.trend,
                alert.severity,
                alert.message,
                alert.timestamp.isoformat()
            ))
    
    def generate_health_report(self, days_back: int = 7) -> str:
        """Generate comprehensive test health report."""
        # Get all unique test names from recent data
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT test_name FROM test_metrics 
                WHERE timestamp > ?
                ORDER BY test_name
            """, (cutoff_date.isoformat(),))
            test_names = [row[0] for row in cursor.fetchall()]
        
        # Analyze each test
        report_lines = [
            "# Test Health Report",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Analysis period:** {days_back} days",
            "",
            "## Summary",
            ""
        ]
        
        total_tests = len(test_names)
        tests_with_alerts = 0
        critical_alerts = 0
        
        for test_name in test_names:
            alerts = self.check_for_alerts(test_name)
            if alerts:
                tests_with_alerts += 1
                critical_alerts += sum(1 for a in alerts if a.severity == 'critical')
        
        report_lines.extend([
            f"- **Total tests monitored:** {total_tests}",
            f"- **Tests with health issues:** {tests_with_alerts}",
            f"- **Critical alerts:** {critical_alerts}",
            "",
            "## Detailed Analysis",
            ""
        ])
        
        for test_name in test_names:
            analysis = self.analyze_test_health(test_name, days_back)
            alerts = self.check_for_alerts(test_name)
            
            status_icon = "❌" if any(a.severity == 'critical' for a in alerts) else \
                         "⚠️" if alerts else "✅"
            
            report_lines.extend([
                f"### {test_name} {status_icon}",
                "",
                f"- **Data points:** {analysis.get('data_points', 0)}",
                f"- **Success rate:** {analysis.get('success_rate', 0):.1%}",
                f"- **Avg execution time:** {analysis.get('execution_time', {}).get('mean', 0):.2f}s",
                f"- **Avg memory usage:** {analysis.get('memory_usage', {}).get('mean', 0):.1f}MB",
                f"- **Performance trend:** {analysis.get('execution_time', {}).get('trend', 'unknown')}",
                ""
            ])
            
            if alerts:
                report_lines.append("**Active Alerts:**")
                for alert in alerts:
                    severity_icon = "🚨" if alert.severity == 'critical' else "⚠️"
                    report_lines.append(f"- {severity_icon} {alert.message}")
                report_lines.append("")
        
        return "\n".join(report_lines)
    
    def register_alert_handler(self, handler: Callable[[TestHealthAlert], None]):
        """Register handler for test health alerts."""
        self.alert_handlers.append(handler)
    
    def trigger_alert_handlers(self, alerts: List[TestHealthAlert]):
        """Trigger all registered alert handlers."""
        for alert in alerts:
            for handler in self.alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    print(f"Alert handler error: {e}")


# Integration with test execution
@pytest.fixture(scope="function")
def test_health_monitor():
    """Provide test health monitoring for each test."""
    monitor = TestHealthMonitor()
    return monitor


def health_monitored_test(test_name: str):
    """Decorator for tests that should be health monitored."""
    def decorator(func):
        func._health_monitored = True
        func._health_test_name = test_name
        return func
    return decorator


# Plugin integration for automatic monitoring
class TestHealthPlugin:
    """Pytest plugin for automatic test health monitoring."""
    
    def __init__(self):
        self.monitor = TestHealthMonitor()
        self.current_test_metrics = {}
    
    def pytest_runtest_setup(self, item):
        """Setup monitoring for each test."""
        self.current_test_metrics[item.nodeid] = {
            'start_time': time.time(),
            'start_memory': 0,  # Would be populated by memory monitor
        }
    
    def pytest_runtest_teardown(self, item, nextitem):
        """Record test metrics after each test."""
        if item.nodeid in self.current_test_metrics:
            metrics = self.current_test_metrics[item.nodeid]
            
            # Create health metric record
            health_metric = TestHealthMetric(
                test_name=item.nodeid,
                execution_time=time.time() - metrics['start_time'],
                memory_usage=metrics.get('peak_memory', 0),
                cpu_usage=metrics.get('peak_cpu', 0),
                success=True,  # Would be determined from test result
                timestamp=datetime.now(),
                execution_mode='unknown'  # Would be passed from runner
            )
            
            # Record and check for alerts
            self.monitor.record_test_metric(health_metric)
            alerts = self.monitor.check_for_alerts(item.nodeid)
            
            if alerts:
                self.monitor.trigger_alert_handlers(alerts)
            
            # Clean up
            del self.current_test_metrics[item.nodeid]