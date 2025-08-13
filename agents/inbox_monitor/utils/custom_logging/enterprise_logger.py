"""
Enterprise Logging System
========================

Intelligent logging system with noise reduction, performance monitoring,
and enterprise-grade observability features.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

class LogLevel(Enum):
    """Enterprise log levels with intelligent filtering."""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR" 
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"

class LogCategory(Enum):
    """Log categories for intelligent filtering."""
    SYSTEM = "system"           # Core system operations
    PERFORMANCE = "performance" # Performance metrics
    SECURITY = "security"       # Security events
    BUSINESS = "business"       # Business logic
    INTEGRATION = "integration" # External service calls
    TEMPLATE = "template"       # Template processing (noisy)
    DATABASE = "database"       # Database operations
    NETWORK = "network"         # Network operations

@dataclass
class EnterpriseLogConfig:
    """Configuration for enterprise logging."""
    level: LogLevel = LogLevel.INFO
    quiet_mode: bool = False
    performance_tracking: bool = True
    noise_reduction: bool = True
    excluded_categories: Set[LogCategory] = None
    metrics_collection: bool = True
    
    def __post_init__(self):
        if self.excluded_categories is None:
            # Default: Exclude noisy categories in production
            self.excluded_categories = {LogCategory.TEMPLATE, LogCategory.TRACE}

class EnterpriseLogger:
    """Enterprise-grade logger with intelligent filtering and performance tracking."""
    
    def __init__(self, name: str, config: EnterpriseLogConfig = None):
        self.name = name
        self.config = config or EnterpriseLogConfig()
        self.logger = logging.getLogger(name)
        self.metrics: Dict[str, Any] = {}
        self.operation_timers: Dict[str, float] = {}
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging with enterprise configuration."""
        # Configure log level based on enterprise config
        level_mapping = {
            LogLevel.CRITICAL: logging.CRITICAL,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.INFO: logging.INFO,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.TRACE: logging.DEBUG  # Map TRACE to DEBUG
        }
        
        self.logger.setLevel(level_mapping[self.config.level])
        
        # Create enterprise formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _should_log(self, category: LogCategory, level: LogLevel) -> bool:
        """Intelligent filtering logic."""
        if self.config.quiet_mode and level in [LogLevel.DEBUG, LogLevel.TRACE]:
            return False
        
        if self.config.noise_reduction and category in self.config.excluded_categories:
            return False
            
        return True
    
    def log_system_event(self, message: str, level: LogLevel = LogLevel.INFO, **kwargs):
        """Log system events with enterprise context."""
        if self._should_log(LogCategory.SYSTEM, level):
            extra_info = f" | {kwargs}" if kwargs else ""
            self.logger.log(logging.INFO, f"[SYSTEM] {message}{extra_info}")
    
    def log_performance_event(self, message: str, duration_ms: float = None, **kwargs):
        """Log performance events with metrics collection."""
        if not self._should_log(LogCategory.PERFORMANCE, LogLevel.INFO):
            return
            
        if self.config.performance_tracking:
            perf_info = f" | Duration: {duration_ms:.2f}ms" if duration_ms else ""
            extra_info = f" | {kwargs}" if kwargs else ""
            self.logger.info(f"[PERFORMANCE] {message}{perf_info}{extra_info}")
            
            # Collect metrics
            if self.config.metrics_collection and duration_ms:
                self.metrics[f"perf_{message.lower().replace(' ', '_')}"] = duration_ms
    
    def log_business_event(self, message: str, level: LogLevel = LogLevel.INFO, **kwargs):
        """Log business logic events."""
        if self._should_log(LogCategory.BUSINESS, level):
            extra_info = f" | {kwargs}" if kwargs else ""
            self.logger.log(logging.INFO, f"[BUSINESS] {message}{extra_info}")
    
    def log_integration_event(self, service: str, operation: str, 
                            success: bool, duration_ms: float = None, **kwargs):
        """Log external service integration events."""
        if not self._should_log(LogCategory.INTEGRATION, LogLevel.INFO):
            return
            
        status = "SUCCESS" if success else "FAILED"
        perf_info = f" | {duration_ms:.2f}ms" if duration_ms else ""
        extra_info = f" | {kwargs}" if kwargs else ""
        
        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"[{service.upper()}] {operation} - {status}{perf_info}{extra_info}")
    
    def suppress_template_noise(self, operation: str):
        """Suppress noisy template operations."""
        if LogCategory.TEMPLATE not in self.config.excluded_categories:
            return
        
        # Only log template operations at DEBUG level or if errors occur
        if self.config.level in [LogLevel.DEBUG, LogLevel.TRACE]:
            self.logger.debug(f"[TEMPLATE] {operation}")
    
    @contextmanager
    def performance_timer(self, operation_name: str):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.log_performance_event(operation_name, duration_ms)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected performance metrics."""
        return {
            "logger_name": self.name,
            "config": {
                "level": self.config.level.value,
                "quiet_mode": self.config.quiet_mode,
                "noise_reduction": self.config.noise_reduction
            },
            "metrics": self.metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

def get_enterprise_logger(name: str, config: EnterpriseLogConfig = None) -> EnterpriseLogger:
    """Factory function for creating enterprise loggers."""
    return EnterpriseLogger(name, config)

def create_enterprise_config(quiet_mode: bool = False, 
                           performance_tracking: bool = True,
                           level: str = "INFO") -> EnterpriseLogConfig:
    """Create enterprise logging configuration."""
    log_level = LogLevel(level.upper())
    
    excluded_categories = {LogCategory.TEMPLATE}
    if quiet_mode:
        excluded_categories.update({LogCategory.TEMPLATE, LogCategory.DATABASE})
    
    return EnterpriseLogConfig(
        level=log_level,
        quiet_mode=quiet_mode,
        performance_tracking=performance_tracking,
        noise_reduction=True,
        excluded_categories=excluded_categories,
        metrics_collection=True
    )