"""
Comprehensive Logging and Monitoring Infrastructure for Test Runner CLI
======================================================================

Provides advanced logging, monitoring, and observability features.
"""

import json
import logging
import logging.handlers
import time
import os
import sys
import threading
import traceback
import signal
import atexit
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
from enum import Enum

try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

class LogLevel(Enum):
    """Custom log levels for test runner."""
    TRACE = 5
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class MetricType(Enum):
    """Types of metrics to track."""
    COUNTER = "counter"
    GAUGE = "gauge" 
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class TestMetric:
    """A single test execution metric."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: str
    tags: Dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None

@dataclass
class HealthStatus:
    """Health status information."""
    is_healthy: bool
    status_message: str
    timestamp: str
    checks: Dict[str, bool] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)

class ThreadLifecycleManager:
    """Manages thread lifecycle and ensures proper cleanup."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.active_threads = []
        self.stop_event = threading.Event()
        self._cleanup_in_progress = False
        self._lock = threading.Lock()
        
        # Only set up handlers and atexit once
        self._setup_signal_handlers()
        atexit.register(self.cleanup_all_threads)
        self._initialized = True
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            # Signal handlers can only be set from main thread
            pass
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.stop_event.set()
        self.cleanup_all_threads()
    
    def register_thread(self, thread):
        """Register a thread for lifecycle management."""
        self.active_threads.append(thread)
    
    def cleanup_all_threads(self):
        """Cleanup all registered threads."""
        with self._lock:
            if self._cleanup_in_progress or self.stop_event.is_set():
                return  # Already cleaning up
                
            self._cleanup_in_progress = True
            
        try:
            print("Cleaning up active threads...")
            self.stop_event.set()
            
            # Work with a copy to avoid modification during iteration
            threads_to_cleanup = list(self.active_threads)
            
            for thread in threads_to_cleanup:
                if thread.is_alive():
                    print(f"Waiting for thread {thread.name} to finish...")
                    thread.join(timeout=2)  # Reduced timeout
                    
                    if thread.is_alive():
                        print(f"⚠️ Thread {thread.name} did not terminate within timeout")
                    else:
                        print(f"✅ Thread {thread.name} terminated cleanly")
                        
                # Remove from active threads list
                with self._lock:
                    if thread in self.active_threads:
                        self.active_threads.remove(thread)
        
        finally:
            with self._lock:
                self._cleanup_in_progress = False


class TestRunnerLogger:
    """Enhanced logger with structured logging and multiple outputs."""
    
    def __init__(self, name: str = "test_runner", log_dir: Optional[Path] = None):
        self.name = name
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        self._setup_handlers()
        self._setup_custom_levels()
        
        # Thread lifecycle manager
        self.thread_manager = ThreadLifecycleManager()
    
    def _setup_handlers(self):
        """Set up logging handlers."""
        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = self._create_colored_formatter()
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        log_file = self.log_dir / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # JSON structured log handler
        json_log_file = self.log_dir / f"{self.name}_structured.jsonl"
        json_handler = logging.FileHandler(json_log_file)
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(self._create_json_formatter())
        self.logger.addHandler(json_handler)
        
        # Error-only handler
        error_log_file = self.log_dir / f"{self.name}_errors.log"
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
    
    def _setup_custom_levels(self):
        """Set up custom log levels."""
        logging.addLevelName(LogLevel.TRACE.value, "TRACE")
        
        def trace(self, message, *args, **kwargs):
            if self.isEnabledFor(LogLevel.TRACE.value):
                self._log(LogLevel.TRACE.value, message, args, **kwargs)
        
        logging.Logger.trace = trace
    
    def _create_colored_formatter(self):
        """Create a colored formatter for console output."""
        class ColoredFormatter(logging.Formatter):
            COLORS = {
                'DEBUG': '\033[94m',     # Blue
                'INFO': '\033[92m',      # Green
                'WARNING': '\033[93m',   # Yellow
                'ERROR': '\033[91m',     # Red
                'CRITICAL': '\033[95m',  # Magenta
                'TRACE': '\033[96m',     # Cyan
                'ENDC': '\033[0m'        # End color
            }
            
            def format(self, record):
                log_color = self.COLORS.get(record.levelname, '')
                record.levelname = f"{log_color}{record.levelname}{self.COLORS['ENDC']}"
                return super().format(record)
        
        return ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def _create_json_formatter(self):
        """Create a JSON formatter for structured logging."""
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'thread': record.thread,
                    'thread_name': record.threadName
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_entry['exception'] = {
                        'type': record.exc_info[0].__name__,
                        'message': str(record.exc_info[1]),
                        'traceback': traceback.format_exception(*record.exc_info)
                    }
                
                # Add extra fields
                for key, value in record.__dict__.items():
                    if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                                  'filename', 'module', 'lineno', 'funcName', 'created', 
                                  'msecs', 'relativeCreated', 'thread', 'threadName', 
                                  'processName', 'process', 'message', 'exc_info', 'exc_text',
                                  'stack_info']:
                        log_entry[key] = value
                
                return json.dumps(log_entry)
        
        return JsonFormatter()
    
    def trace(self, message: str, **kwargs):
        """Log trace message."""
        self.logger.trace(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, extra=kwargs)
    
    def log_test_start(self, execution_mode: ExecutionMode, **kwargs):
        """Log test execution start."""
        self.info(
            f"Starting test execution in {execution_mode.name} mode",
            execution_mode=execution_mode.value,
            event_type="test_start",
            **kwargs
        )
    
    def log_test_complete(self, result: TestResult, **kwargs):
        """Log test execution completion."""
        self.info(
            f"Test execution completed: {result.passed_tests}/{result.total_tests} passed",
            execution_mode=result.execution_mode.value,
            event_type="test_complete",
            total_tests=result.total_tests,
            passed_tests=result.passed_tests,
            failed_tests=result.failed_tests,
            success_rate=result.success_rate,
            execution_time=result.total_execution_time,
            **kwargs
        )
    
    def log_test_failure(self, test_name: str, error_message: str, **kwargs):
        """Log individual test failure."""
        self.error(
            f"Test failed: {test_name}",
            event_type="test_failure",
            test_name=test_name,
            error_message=error_message,
            **kwargs
        )
    
    def log_performance_warning(self, test_name: str, duration: float, threshold: float, **kwargs):
        """Log performance warning for slow tests."""
        self.warning(
            f"Slow test detected: {test_name} took {duration:.2f}s (threshold: {threshold:.2f}s)",
            event_type="performance_warning",
            test_name=test_name,
            duration=duration,
            threshold=threshold,
            **kwargs
        )

class MetricsCollector:
    """Collects and manages test execution metrics."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("metrics")
        self.output_dir.mkdir(exist_ok=True)
        self.metrics: List[TestMetric] = []
        self._lock = threading.Lock()
    
    def record_metric(self, name: str, value: float, metric_type: MetricType, 
                     tags: Optional[Dict[str, str]] = None, description: Optional[str] = None):
        """Record a metric."""
        with self._lock:
            metric = TestMetric(
                name=name,
                value=value,
                metric_type=metric_type,
                timestamp=datetime.now().isoformat(),
                tags=tags or {},
                description=description
            )
            self.metrics.append(metric)
    
    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """Record a counter metric."""
        self.record_metric(name, value, MetricType.COUNTER, tags)
    
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a gauge metric."""
        self.record_metric(name, value, MetricType.GAUGE, tags)
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a histogram metric."""
        self.record_metric(name, value, MetricType.HISTOGRAM, tags)
    
    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a timer metric."""
        self.record_metric(name, value, MetricType.TIMER, tags)
    
    @contextmanager
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_metric(name, duration, MetricType.TIMER, tags)
    
    def get_metrics(self, name_filter: Optional[str] = None, 
                   since: Optional[datetime] = None) -> List[TestMetric]:
        """Get metrics with optional filtering."""
        filtered_metrics = []
        
        for metric in self.metrics:
            # Apply name filter
            if name_filter and name_filter not in metric.name:
                continue
            
            # Apply time filter
            if since:
                metric_time = datetime.fromisoformat(metric.timestamp)
                if metric_time < since:
                    continue
            
            filtered_metrics.append(metric)
        
        return filtered_metrics
    
    def export_metrics(self, format_type: str = "json"):
        """Export metrics to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type == "json":
            output_file = self.output_dir / f"metrics_{timestamp}.json"
            metrics_data = []
            for metric in self.metrics:
                metrics_data.append({
                    'name': metric.name,
                    'value': metric.value,
                    'type': metric.metric_type.value,
                    'timestamp': metric.timestamp,
                    'tags': metric.tags,
                    'description': metric.description
                })
            
            output_file.write_text(json.dumps(metrics_data, indent=2))
        
        elif format_type == "prometheus":
            output_file = self.output_dir / f"metrics_{timestamp}.prom"
            prometheus_lines = []
            
            for metric in self.metrics:
                # Convert to Prometheus format
                tags_str = ""
                if metric.tags:
                    tag_pairs = [f'{k}="{v}"' for k, v in metric.tags.items()]
                    tags_str = "{" + ",".join(tag_pairs) + "}"
                
                prometheus_lines.append(f"{metric.name}{tags_str} {metric.value}")
            
            output_file.write_text("\n".join(prometheus_lines))
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of collected metrics."""
        if not self.metrics:
            return {}
        
        stats = {
            'total_metrics': len(self.metrics),
            'metric_types': {},
            'time_range': {
                'start': min(m.timestamp for m in self.metrics),
                'end': max(m.timestamp for m in self.metrics)
            },
            'top_metrics': {}
        }
        
        # Count by type
        for metric in self.metrics:
            metric_type = metric.metric_type.value
            stats['metric_types'][metric_type] = stats['metric_types'].get(metric_type, 0) + 1
        
        # Find most common metric names
        metric_names = {}
        for metric in self.metrics:
            metric_names[metric.name] = metric_names.get(metric.name, 0) + 1
        
        stats['top_metrics'] = dict(sorted(metric_names.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return stats

class HealthChecker:
    """Monitors system health and performance."""
    
    def __init__(self, logger: Optional[TestRunnerLogger] = None):
        self.logger = logger or TestRunnerLogger("health_checker")
        self.checks: Dict[str, Callable[[], bool]] = {}
        self.last_check_time: Optional[datetime] = None
        self.last_status: Optional[HealthStatus] = None
    
    def register_check(self, name: str, check_function: Callable[[], bool]):
        """Register a health check function."""
        self.checks[name] = check_function
    
    def run_health_checks(self) -> HealthStatus:
        """Run all registered health checks."""
        check_results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                result = check_func()
                check_results[name] = result
                if not result:
                    overall_healthy = False
            except Exception as e:
                self.logger.error(f"Health check '{name}' failed with exception: {e}")
                check_results[name] = False
                overall_healthy = False
        
        # Collect system metrics
        metrics = self._collect_system_metrics()
        
        status = HealthStatus(
            is_healthy=overall_healthy,
            status_message="Healthy" if overall_healthy else "Unhealthy",
            timestamp=datetime.now().isoformat(),
            checks=check_results,
            metrics=metrics
        )
        
        self.last_check_time = datetime.now()
        self.last_status = status
        
        return status
    
    def _collect_system_metrics(self) -> Dict[str, float]:
        """Collect basic system metrics."""
        metrics = {}
        
        try:
            import psutil
            
            # CPU usage
            metrics['cpu_percent'] = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics['memory_percent'] = memory.percent
            metrics['memory_available_mb'] = memory.available / 1024 / 1024
            
            # Disk usage for current directory
            disk = psutil.disk_usage('.')
            metrics['disk_percent'] = (disk.used / disk.total) * 100
            metrics['disk_free_gb'] = disk.free / 1024 / 1024 / 1024
            
        except ImportError:
            # psutil not available, use basic checks
            metrics['python_version'] = float(f"{sys.version_info.major}.{sys.version_info.minor}")
            metrics['process_id'] = os.getpid()
        
        return metrics
    
    def setup_default_checks(self):
        """Set up default health checks."""
        
        def check_python_version():
            return sys.version_info >= (3, 7)
        
        def check_disk_space():
            try:
                import shutil
                total, used, free = shutil.disk_usage(".")
                # Check if less than 1GB free
                return free > 1 * 1024 * 1024 * 1024
            except:
                return True
        
        def check_log_directory():
            log_dir = Path("logs")
            return log_dir.exists() and log_dir.is_dir()
        
        def check_test_directory():
            test_dir = Path("tests")
            return test_dir.exists() and log_dir.is_dir()
        
        self.register_check("python_version", check_python_version)
        self.register_check("disk_space", check_disk_space)
        self.register_check("log_directory", check_log_directory)
        self.register_check("test_directory", check_test_directory)

class TestRunnerMonitor:
    """Main monitoring coordinator for the test runner."""
    
    def __init__(self, log_dir: Optional[Path] = None, metrics_dir: Optional[Path] = None):
        self.logger = TestRunnerLogger("test_runner_monitor", log_dir)
        self.metrics = MetricsCollector(metrics_dir)
        self.health_checker = HealthChecker(self.logger)
        self.health_checker.setup_default_checks()
        
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start_monitoring(self, interval_seconds: int = 30):
        """Start background monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._stop_event.clear()
        
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitoring_thread.start()
        
        self.logger.info("Background monitoring started", extra={"interval": interval_seconds})
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        self._stop_event.set()
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        
        self.logger.info("Background monitoring stopped")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Background monitoring loop."""
        while self._monitoring_active and not self._stop_event.wait(interval_seconds):
            try:
                # Run health checks
                health_status = self.health_checker.run_health_checks()
                
                # Record health metrics
                self.metrics.record_gauge("system_healthy", 1.0 if health_status.is_healthy else 0.0)
                
                for metric_name, value in health_status.metrics.items():
                    self.metrics.record_gauge(f"system_{metric_name}", value)
                
                # Log health status if unhealthy
                if not health_status.is_healthy:
                    failed_checks = [name for name, result in health_status.checks.items() if not result]
                    self.logger.warning(
                        f"Health check failed: {', '.join(failed_checks)}",
                        failed_checks=failed_checks
                    )
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
    
    @contextmanager
    def monitor_test_execution(self, execution_mode: ExecutionMode):
        """Context manager for monitoring test execution with detailed resource tracking."""
        start_time = time.time()
        resource_monitor = None
        
        # Log start
        self.logger.log_test_start(execution_mode)
        self.metrics.record_counter("test_executions_started", tags={"mode": execution_mode.value})
        
        try:
            # Start detailed resource monitoring
            resource_monitor = TestResourceMonitor()
            resource_monitor.start_monitoring()
            
            yield
            
            # Stop resource monitoring and collect final metrics
            resource_stats = resource_monitor.stop_monitoring()
            
            # Success metrics
            duration = time.time() - start_time
            self.metrics.record_timer("test_execution_duration", duration, 
                                    tags={"mode": execution_mode.value, "status": "success"})
            self.metrics.record_counter("test_executions_completed", 
                                      tags={"mode": execution_mode.value, "status": "success"})
            
            # Record detailed resource metrics
            if resource_stats:
                self._record_resource_metrics(resource_stats, execution_mode, "success")
            
        except Exception as e:
            # Failure metrics
            duration = time.time() - start_time
            self.metrics.record_timer("test_execution_duration", duration,
                                    tags={"mode": execution_mode.value, "status": "error"})
            self.metrics.record_counter("test_executions_completed",
                                      tags={"mode": execution_mode.value, "status": "error"})
            
            # Stop resource monitoring and collect metrics even on failure
            if resource_monitor:
                resource_stats = resource_monitor.stop_monitoring()
                if resource_stats:
                    self._record_resource_metrics(resource_stats, execution_mode, "error")
            
            self.logger.error(f"Test execution failed: {e}", extra={"execution_mode": execution_mode.value})
            raise
    
    def record_test_result(self, result: TestResult):
        """Record metrics from test result."""
        mode_tag = {"mode": result.execution_mode.value}
        
        # Basic test metrics
        self.metrics.record_gauge("tests_total", result.total_tests, mode_tag)
        self.metrics.record_gauge("tests_passed", result.passed_tests, mode_tag)
        self.metrics.record_gauge("tests_failed", result.failed_tests, mode_tag)
        self.metrics.record_gauge("tests_skipped", result.skipped_tests, mode_tag)
        self.metrics.record_gauge("success_rate", result.success_rate, mode_tag)
        self.metrics.record_timer("total_execution_time", result.total_execution_time, mode_tag)
        
        # Individual test timing metrics
        if result.individual_test_times:
            times = list(result.individual_test_times.values())
            self.metrics.record_gauge("avg_test_time", sum(times) / len(times), mode_tag)
            self.metrics.record_gauge("max_test_time", max(times), mode_tag)
            self.metrics.record_gauge("min_test_time", min(times), mode_tag)
            
            # Log slow tests
            slow_threshold = 10.0  # 10 seconds
            for test_name, duration in result.individual_test_times.items():
                if duration > slow_threshold:
                    self.logger.log_performance_warning(test_name, duration, slow_threshold)
        
        # Log completion
        self.logger.log_test_complete(result)
        
        # Log failures
        for failure in result.failure_details:
            # Extract test name from failure string
            test_name = failure.split(" ")[1] if len(failure.split(" ")) > 1 else "unknown"
            self.logger.log_test_failure(test_name, failure)
    
    def generate_monitoring_report(self, output_dir: Optional[Path] = None) -> Path:
        """Generate comprehensive monitoring report."""
        output_dir = output_dir or Path("reports")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_dir / f"monitoring_report_{timestamp}.json"
        
        # Gather report data
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'health_status': None,
            'metrics_summary': self.metrics.get_summary_stats(),
            'recent_metrics': [],
            'log_summary': self._get_log_summary()
        }
        
        # Add current health status
        try:
            health_status = self.health_checker.run_health_checks()
            report_data['health_status'] = {
                'is_healthy': health_status.is_healthy,
                'status_message': health_status.status_message,
                'timestamp': health_status.timestamp,
                'checks': health_status.checks,
                'metrics': health_status.metrics
            }
        except Exception as e:
            self.logger.error(f"Failed to get health status for report: {e}")
        
        # Add recent metrics
        since_time = datetime.now() - timedelta(hours=24)
        recent_metrics = self.metrics.get_metrics(since=since_time)
        report_data['recent_metrics'] = [
            {
                'name': m.name,
                'value': m.value,
                'type': m.metric_type.value,
                'timestamp': m.timestamp,
                'tags': m.tags
            }
            for m in recent_metrics[-100:]  # Last 100 metrics
        ]
        
        # Write report
        report_file.write_text(json.dumps(report_data, indent=2))
        
        self.logger.info(f"Monitoring report generated: {report_file}")
        return report_file
    
    def _get_log_summary(self) -> Dict[str, Any]:
        """Get summary of recent log entries."""
        summary = {
            'log_files': [],
            'recent_errors': [],
            'warning_count': 0,
            'error_count': 0
        }
        
        try:
            # List log files
            log_dir = Path("logs")
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    summary['log_files'].append({
                        'name': log_file.name,
                        'size_bytes': log_file.stat().st_size,
                        'modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                    })
                
                # Count recent errors and warnings (simplified)
                error_log = log_dir / "test_runner_monitor_errors.log"
                if error_log.exists():
                    try:
                        error_content = error_log.read_text()
                        summary['error_count'] = error_content.count('ERROR')
                        summary['warning_count'] = error_content.count('WARNING')
                        
                        # Get last few errors
                        error_lines = [line for line in error_content.split('\n') if 'ERROR' in line]
                        summary['recent_errors'] = error_lines[-5:]  # Last 5 errors
                        
                    except Exception:
                        pass
        
        except Exception as e:
            self.logger.error(f"Failed to generate log summary: {e}")
        
        return summary
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old monitoring data."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Clean up old metrics
        original_count = len(self.metrics.metrics)
        self.metrics.metrics = [
            m for m in self.metrics.metrics 
            if datetime.fromisoformat(m.timestamp) > cutoff_date
        ]
        removed_count = original_count - len(self.metrics.metrics)
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old metrics")
        
        # Clean up old log files
        try:
            log_dir = Path("logs")
            if log_dir.exists():
                for log_file in log_dir.glob("*.log.*"):  # Rotated log files
                    if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff_date:
                        log_file.unlink()
                        self.logger.debug(f"Removed old log file: {log_file}")
        
        except Exception as e:
            self.logger.error(f"Error cleaning up log files: {e}")
        
        # Clean up old reports
        try:
            reports_dir = Path("reports")
            if reports_dir.exists():
                for report_file in reports_dir.glob("monitoring_report_*.json"):
                    if datetime.fromtimestamp(report_file.stat().st_mtime) < cutoff_date:
                        report_file.unlink()
                        self.logger.debug(f"Removed old report: {report_file}")
        
        except Exception as e:
            self.logger.error(f"Error cleaning up reports: {e}")

    def _record_resource_metrics(self, resource_stats: Dict[str, Any], 
                                execution_mode: ExecutionMode, status: str):
        """Record detailed resource usage metrics."""
        tags = {"mode": execution_mode.value, "status": status}
        
        # Record CPU metrics
        if 'cpu_usage' in resource_stats:
            cpu_data = resource_stats['cpu_usage']
            self.metrics.record_gauge("test_cpu_avg_percent", cpu_data['average'], tags=tags)
            self.metrics.record_gauge("test_cpu_max_percent", cpu_data['maximum'], tags=tags)
            self.metrics.record_gauge("test_cpu_min_percent", cpu_data['minimum'], tags=tags)
        
        # Record Memory metrics  
        if 'memory_usage' in resource_stats:
            mem_data = resource_stats['memory_usage']
            self.metrics.record_gauge("test_memory_avg_mb", mem_data['average_mb'], tags=tags)
            self.metrics.record_gauge("test_memory_max_mb", mem_data['peak_mb'], tags=tags)
            self.metrics.record_gauge("test_memory_avg_percent", mem_data['average_percent'], tags=tags)
        
        # Record I/O metrics
        if 'io_usage' in resource_stats:
            io_data = resource_stats['io_usage']
            self.metrics.record_counter("test_disk_read_bytes", io_data['read_bytes'], tags=tags)
            self.metrics.record_counter("test_disk_write_bytes", io_data['write_bytes'], tags=tags)
            self.metrics.record_counter("test_disk_read_count", io_data['read_count'], tags=tags)
            self.metrics.record_counter("test_disk_write_count", io_data['write_count'], tags=tags)
        
        # Record performance summary
        if 'summary' in resource_stats:
            summary = resource_stats['summary']
            self.metrics.record_gauge("test_monitoring_duration", summary['monitoring_duration'], tags=tags)
            self.metrics.record_counter("test_monitoring_samples", summary['sample_count'], tags=tags)


@dataclass
class ResourceSnapshot:
    """A single snapshot of system resource usage."""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    disk_read_count: int = 0
    disk_write_count: int = 0


class TestResourceMonitor:
    """Detailed resource monitoring during test execution."""
    
    def __init__(self, sample_interval: float = 0.5):
        self.sample_interval = sample_interval
        self.snapshots: List[ResourceSnapshot] = []
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.start_time: Optional[float] = None
        self.initial_io_counters: Optional[Any] = None
        
    def start_monitoring(self):
        """Start continuous resource monitoring."""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.start_time = time.time()
        self.snapshots.clear()
        self.stop_event.clear()
        
        # Capture initial I/O counters
        try:
            import psutil
            process = psutil.Process()
            self.initial_io_counters = process.io_counters()
        except (ImportError, AttributeError, psutil.NoSuchProcess):
            self.initial_io_counters = None
        
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
    
    def stop_monitoring(self) -> Optional[Dict[str, Any]]:
        """Stop monitoring and return collected statistics."""
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            return None
        
        self.stop_event.set()
        self.monitoring_thread.join(timeout=2.0)
        
        return self._analyze_snapshots()
    
    def _monitoring_loop(self):
        """Main monitoring loop that collects resource snapshots."""
        try:
            import psutil
            process = psutil.Process()
        except ImportError:
            return  # Can't monitor without psutil
        
        while not self.stop_event.is_set():
            try:
                # Collect system-wide metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                
                # Collect process I/O metrics
                io_read_bytes = 0
                io_write_bytes = 0 
                io_read_count = 0
                io_write_count = 0
                
                try:
                    current_io = process.io_counters()
                    if self.initial_io_counters:
                        io_read_bytes = current_io.read_bytes - self.initial_io_counters.read_bytes
                        io_write_bytes = current_io.write_bytes - self.initial_io_counters.write_bytes
                        io_read_count = current_io.read_count - self.initial_io_counters.read_count
                        io_write_count = current_io.write_count - self.initial_io_counters.write_count
                except (AttributeError, psutil.NoSuchProcess):
                    pass  # I/O counters not available on this platform
                
                # Create snapshot
                snapshot = ResourceSnapshot(
                    timestamp=time.time(),
                    cpu_percent=cpu_percent,
                    memory_mb=memory.used / 1024 / 1024,
                    memory_percent=memory.percent,
                    disk_read_bytes=io_read_bytes,
                    disk_write_bytes=io_write_bytes,
                    disk_read_count=io_read_count,
                    disk_write_count=io_write_count
                )
                
                self.snapshots.append(snapshot)
                
                # Wait for next sample
                self.stop_event.wait(timeout=self.sample_interval)
                
            except Exception as e:
                # Continue monitoring even if individual samples fail
                pass
    
    def _analyze_snapshots(self) -> Dict[str, Any]:
        """Analyze collected snapshots and return statistics."""
        if not self.snapshots:
            return {}
        
        # Calculate CPU statistics
        cpu_values = [s.cpu_percent for s in self.snapshots]
        cpu_stats = {
            'average': sum(cpu_values) / len(cpu_values),
            'maximum': max(cpu_values),
            'minimum': min(cpu_values),
            'samples': len(cpu_values)
        }
        
        # Calculate Memory statistics
        memory_mb_values = [s.memory_mb for s in self.snapshots]
        memory_percent_values = [s.memory_percent for s in self.snapshots]
        memory_stats = {
            'average_mb': sum(memory_mb_values) / len(memory_mb_values),
            'peak_mb': max(memory_mb_values),
            'average_percent': sum(memory_percent_values) / len(memory_percent_values),
            'peak_percent': max(memory_percent_values),
            'samples': len(memory_mb_values)
        }
        
        # Calculate I/O statistics (final values)
        final_snapshot = self.snapshots[-1]
        io_stats = {
            'read_bytes': final_snapshot.disk_read_bytes,
            'write_bytes': final_snapshot.disk_write_bytes,
            'read_count': final_snapshot.disk_read_count,
            'write_count': final_snapshot.disk_write_count,
            'total_io_bytes': final_snapshot.disk_read_bytes + final_snapshot.disk_write_bytes,
            'total_io_operations': final_snapshot.disk_read_count + final_snapshot.disk_write_count
        }
        
        # Calculate monitoring summary
        monitoring_duration = self.snapshots[-1].timestamp - self.snapshots[0].timestamp
        summary_stats = {
            'monitoring_duration': monitoring_duration,
            'sample_count': len(self.snapshots),
            'sample_interval': self.sample_interval,
            'effective_sample_rate': len(self.snapshots) / max(monitoring_duration, 0.001)
        }
        
        return {
            'cpu_usage': cpu_stats,
            'memory_usage': memory_stats,
            'io_usage': io_stats,
            'summary': summary_stats,
            'snapshots': len(self.snapshots)  # Don't include raw snapshots to save space
        }