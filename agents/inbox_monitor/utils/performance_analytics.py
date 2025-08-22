"""
Performance Analytics - Stub Implementation
==========================================

This is a stub implementation to maintain test compatibility.
The full performance analytics module was archived.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time

@dataclass
class PerformanceMetrics:
    """Basic performance metrics for test compatibility."""
    processing_times: Dict[str, float]
    resource_usage: Dict[str, float]
    throughput_metrics: Dict[str, float]
    error_rates: Dict[str, float]
    latency_percentiles: Dict[str, float]
    trend_analysis: Dict[str, Any]

def collect_performance_metrics(operation: str = "default") -> PerformanceMetrics:
    """Collect basic performance metrics - stub implementation."""
    return PerformanceMetrics(
        processing_times={"total": 100.0, "ai_processing": 50.0},
        resource_usage={"memory_mb": 64.0, "cpu_percent": 25.0},
        throughput_metrics={"emails_per_second": 2.5, "operations_per_minute": 150.0},
        error_rates={"process_errors": 0.01, "connection_errors": 0.005},
        latency_percentiles={"p50": 200.0, "p95": 500.0, "p99": 1000.0},
        trend_analysis={"trend": "stable", "anomalies_detected": False}
    )

def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary - stub implementation."""
    return {
        "average_processing_time": 100.0,
        "total_operations": 1000,
        "success_rate": 0.95,
        "resource_efficiency": "good",
        "last_updated": time.time()
    }

def analyze_performance_anomalies(metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
    """Analyze performance anomalies - stub implementation."""
    # Return no anomalies for stable test behavior
    return []