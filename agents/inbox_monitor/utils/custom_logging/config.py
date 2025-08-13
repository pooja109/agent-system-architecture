# utils/logging/config.py
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pathlib import Path
import logging


class LogLevel(str, Enum):
    """Supported logging levels for the logging system.
    
    This enumeration defines the standard logging levels that can be used
    throughout the application. Each level has a corresponding Python logging
    level that determines message filtering.
    
    Attributes:
        CRITICAL: Only critical system failures (level 50)
        ERROR: Error conditions that need attention (level 40)
        WARNING: Warning conditions that should be noted (level 30)
        INFO: General information messages (level 20)
        DEBUG: Detailed diagnostic information (level 10)
    
    Example:
        >>> config = ConsoleConfig(level=LogLevel.INFO)
        >>> assert config.level == "INFO"
    """
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class OutputFormat(str, Enum):
    """Supported output formats for console logging.
    
    This enumeration defines the different formatting styles available
    for console output, allowing customization based on use case and
    user preference.
    
    Attributes:
        CLEAN: Human-friendly console output with icons and colors
        JSON: Structured JSON output (same as structured handler)
        DETAILED: Verbose diagnostic output with full metadata
        MINIMAL: Minimal essential output only (just the message)
        TABLE: Tabular data presentation format
        TREE: Tree-structured hierarchical output
        COMPACT: Compact single-line format
    
    Example:
        >>> config = ConsoleConfig(format=OutputFormat.MINIMAL)
        >>> assert config.format == "minimal"
    """
    CLEAN = "clean"      # Human-friendly console output
    JSON = "json"        # Structured JSON output
    DETAILED = "detailed"  # Verbose diagnostic output
    MINIMAL = "minimal"  # Minimal essential output only
    TABLE = "table"      # Tabular data presentation
    TREE = "tree"        # Tree-structured hierarchical output
    COMPACT = "compact"  # Compact single-line format


class ConsoleConfig(BaseModel):
    """Configuration for console output handler.
    
    This class configures the console handler, which provides user-friendly
    output to the terminal. It supports various formatting options, colors,
    and can be disabled for production environments.
    
    Attributes:
        enabled (bool): Whether console output is enabled. Defaults to True.
        level (LogLevel): Minimum log level for console output. Defaults to INFO.
        format (OutputFormat): Console output format style. Defaults to CLEAN.
        color_enabled (bool): Whether to use ANSI colors in output. Defaults to True.
        timestamp_enabled (bool): Whether to include timestamps. Defaults to False.
        show_logger_name (bool): Whether to show logger name in output. Defaults to False.
    
    Example:
        >>> config = ConsoleConfig(
        ...     level=LogLevel.WARNING,
        ...     format=OutputFormat.MINIMAL,
        ...     color_enabled=False
        ... )
        >>> assert config.level == LogLevel.WARNING
    """
    enabled: bool = True
    level: LogLevel = LogLevel.INFO
    format: OutputFormat = OutputFormat.CLEAN
    color_enabled: bool = True
    timestamp_enabled: bool = False
    show_logger_name: bool = False
    
    model_config = ConfigDict(use_enum_values=True)


class StructuredConfig(BaseModel):
    """Configuration for structured logging handler.
    
    This class configures the structured handler, which outputs JSON-formatted
    logs suitable for production monitoring, log aggregation, and automated
    analysis systems.
    
    Attributes:
        enabled (bool): Whether structured output is enabled. Defaults to True.
        level (LogLevel): Minimum log level for structured output. Defaults to DEBUG.
        format (str): Output format identifier (currently only "json"). Defaults to "json".
        include_timestamp (bool): Whether to include timestamp in output. Defaults to True.
        include_logger_name (bool): Whether to include logger name. Defaults to True.
        include_thread_info (bool): Whether to include thread information. Defaults to False.
        include_process_info (bool): Whether to include process information. Defaults to False.
    
    Example:
        >>> config = StructuredConfig(
        ...     level=LogLevel.ERROR,
        ...     include_thread_info=True
        ... )
        >>> assert config.include_thread_info is True
    """
    enabled: bool = True
    level: LogLevel = LogLevel.DEBUG
    format: str = "json"
    include_timestamp: bool = True
    include_logger_name: bool = True
    include_thread_info: bool = False
    include_process_info: bool = False
    
    model_config = ConfigDict(use_enum_values=True)


class FileConfig(BaseModel):
    """Configuration for file-based logging.
    
    This class configures file output for logging, supporting log rotation
    and size management. File logging is optional and disabled by default.
    
    Attributes:
        enabled (bool): Whether file logging is enabled. Defaults to False.
        file_path (Optional[Path]): Path to the log file. Defaults to None.
        level (LogLevel): Minimum log level for file output. Defaults to DEBUG.
        max_size_mb (int): Maximum file size in megabytes before rotation. Defaults to 100.
        backup_count (int): Number of backup files to keep. Defaults to 5.
        rotation_enabled (bool): Whether to enable log rotation. Defaults to True.
    
    Example:
        >>> config = FileConfig(
        ...     enabled=True,
        ...     file_path="/var/log/app.log",
        ...     max_size_mb=50
        ... )
        >>> assert config.max_size_mb == 50
    """
    enabled: bool = False
    file_path: Optional[Path] = None
    level: LogLevel = LogLevel.DEBUG
    max_size_mb: int = 100
    backup_count: int = 5
    rotation_enabled: bool = True
    
    @field_validator('file_path', mode='before')
    @classmethod
    def validate_file_path(cls, v: Any) -> Optional[Path]:
        """Validate and convert file path to Path object.
        
        Args:
            v: The value to validate (string or Path object).
        
        Returns:
            Optional[Path]: The validated Path object or None.
        """
        if v and isinstance(v, str):
            return Path(v)
        return v

    model_config = ConfigDict(use_enum_values=True)


class LoggingConfig(BaseModel):
    """Complete logging system configuration.
    
    This is the main configuration class that combines all logging settings
    and provides a complete setup for the dual-stream logging system.
    
    Attributes:
        console (ConsoleConfig): Console handler configuration.
        structured (StructuredConfig): Structured handler configuration.
        file (FileConfig): File handler configuration.
        environment (str): Runtime environment (development, production, testing).
        disable_http_logging (bool): Whether to disable HTTP request/response logs.
        suppress_azure_sdk (bool): Whether to suppress verbose Azure SDK logs.
        suppress_urllib3 (bool): Whether to suppress verbose urllib3 logs.
        async_logging (bool): Whether to enable asynchronous logging.
        buffer_size (int): Size of the logging buffer for batching.
        flush_interval_seconds (float): Interval between buffer flushes.
    
    Example:
        >>> config = LoggingConfig(
        ...     environment="production",
        ...     console=ConsoleConfig(enabled=False),
        ...     async_logging=True
        ... )
        >>> assert config.environment == "production"
        >>> assert config.console.enabled is False
    """
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    structured: StructuredConfig = Field(default_factory=StructuredConfig)
    file: FileConfig = Field(default_factory=FileConfig)
    
    # Environment-based overrides
    environment: str = "development"  # development, production, testing
    disable_http_logging: bool = True
    suppress_azure_sdk: bool = True
    suppress_urllib3: bool = True
    
    # Performance settings
    async_logging: bool = False
    buffer_size: int = 1000
    flush_interval_seconds: float = 1.0
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate the environment setting.
        
        Args:
            v (str): The environment value to validate.
        
        Returns:
            str: The validated environment string.
        
        Raises:
            ValueError: If environment is not one of the allowed values.
        """
        valid_environments = {'development', 'production', 'testing'}
        if v not in valid_environments:
            raise ValueError(f'Environment must be one of {valid_environments}')
        return v
    
    def get_python_log_level(self, level: LogLevel) -> int:
        """Convert LogLevel enum to Python logging level constant.
        
        Args:
            level (LogLevel): The log level enum to convert.
        
        Returns:
            int: The corresponding Python logging level constant.
        
        Example:
            >>> config = LoggingConfig()
            >>> level = config.get_python_log_level(LogLevel.INFO)
            >>> assert level == 20
        """
        return getattr(logging, level.value)
    
    def is_production(self) -> bool:
        """Check if running in production environment.
        
        Returns:
            bool: True if environment is set to "production", False otherwise.
        
        Example:
            >>> config = LoggingConfig(environment="production")
            >>> assert config.is_production() is True
            >>> config.environment = "development"
            >>> assert config.is_production() is False
        """
        return self.environment == "production"
    
    def is_containerized(self) -> bool:
        """Detect if running in a containerized environment.
        
        This method checks for common indicators of containerized environments
        such as Kubernetes, Docker, and other container platforms.
        
        Returns:
            bool: True if running in a container, False otherwise.
        
        Note:
            This detection will be enhanced in Phase 2 with more comprehensive
            environment detection capabilities.
        
        Example:
            >>> config = LoggingConfig()
            >>> is_container = config.is_containerized()
            >>> print(f"Running in container: {is_container}")
        """
        # This will be enhanced in Phase 2 with proper environment detection
        import os
        return bool(
            os.getenv('KUBERNETES_SERVICE_HOST') or 
            os.getenv('DOCKER_CONTAINER') or
            os.path.exists('/.dockerenv')
        )

    model_config = ConfigDict(use_enum_values=True, extra='forbid')