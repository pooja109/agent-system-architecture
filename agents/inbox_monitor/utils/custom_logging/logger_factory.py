# utils/logging/logger_factory.py
import logging
import logging.handlers
import sys
from typing import Dict, Optional, List, Any, Type
import atexit
import threading

from .config import LoggingConfig, ConsoleConfig, StructuredConfig, FileConfig
from .console_handler import ConsoleHandler
from .structured_handler import StructuredHandler, StructuredFormatter
from .exceptions import LoggerInitializationError


class LoggerFactory:
    """Factory for creating and managing application loggers."""
    
    _instance: Optional['LoggerFactory'] = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls) -> 'LoggerFactory':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not self._initialized:
            self.config: Optional[LoggingConfig] = None
            self.console_handler: Optional[ConsoleHandler] = None
            self.structured_handler: Optional[StructuredHandler] = None
            self.file_handler: Optional[logging.Handler] = None
            self._loggers: Dict[str, logging.Logger] = {}
            self._setup_complete = False
            LoggerFactory._initialized = True
            
            # Register cleanup on exit
            atexit.register(self.cleanup)
    
    def initialize(self, config: LoggingConfig) -> None:
        """
        Initialize the logger factory with configuration.
        
        This method can be called multiple times, but will raise an error
        if the factory is already initialized unless cleanup has been called first.
        """
        try:
            with self._lock:
                if self._setup_complete:
                    raise LoggerInitializationError(
                        "Logger factory already initialized. Call cleanup() first to re-initialize."
                    )
                
                self.config = config
                self._setup_handlers()
                self._configure_third_party_loggers()
                self._setup_complete = True
                
        except Exception as e:
            raise LoggerInitializationError(f"Failed to initialize logger factory: {e}")
    
    def _setup_handlers(self) -> None:
        """Set up all configured log handlers."""
        if not self.config:
            raise LoggerInitializationError("Configuration not provided")
        
        # Set up console handler
        if self.config.console.enabled:
            self.console_handler = ConsoleHandler(self.config.console)
        
        # Set up structured handler
        if self.config.structured.enabled:
            self.structured_handler = StructuredHandler(self.config.structured)
        
        # Set up file handler if configured
        if self.config.file.enabled and self.config.file.file_path:
            self._setup_file_handler()
    
    def _setup_file_handler(self) -> None:
        """Set up file-based logging handler."""
        if not self.config or not self.config.file.file_path:
            return
        
        try:
            file_config = self.config.file
            
            if file_config.rotation_enabled:
                # Use rotating file handler
                self.file_handler = logging.handlers.RotatingFileHandler(
                    filename=file_config.file_path,
                    maxBytes=file_config.max_size_mb * 1024 * 1024,
                    backupCount=file_config.backup_count
                )
            else:
                # Use basic file handler
                self.file_handler = logging.FileHandler(file_config.file_path)
            
            # Use structured formatter for file output
            structured_formatter = StructuredFormatter(
                StructuredConfig(
                    level=file_config.level,
                    include_timestamp=True,
                    include_logger_name=True,
                    include_thread_info=True
                )
            )
            self.file_handler.setFormatter(structured_formatter)
            level_value = file_config.level.value if hasattr(file_config.level, 'value') else file_config.level
            self.file_handler.setLevel(level_value)
            
        except Exception as e:
            raise LoggerInitializationError(f"Failed to setup file handler: {e}")
    
    def _configure_third_party_loggers(self) -> None:
        """Configure third-party library loggers to reduce noise."""
        if not self.config:
            return
        
        suppression_configs = []
        
        if self.config.suppress_azure_sdk:
            suppression_configs.extend([
                ('azure', logging.WARNING),
                ('azure.core', logging.WARNING),
                ('azure.identity', logging.WARNING),
                ('azure.keyvault', logging.WARNING),
            ])
        
        if self.config.suppress_urllib3:
            suppression_configs.extend([
                ('urllib3', logging.WARNING),
                ('urllib3.connectionpool', logging.WARNING),
            ])
        
        if self.config.disable_http_logging:
            suppression_configs.extend([
                ('requests', logging.WARNING),
                ('httpx', logging.WARNING),
                ('aiohttp', logging.WARNING),
            ])
        
        # Apply suppressions
        for logger_name, level in suppression_configs:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
            # Prevent propagation to avoid duplicate messages
            if logger_name != 'root':
                logger.propagate = False
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the specified name."""
        if not self._setup_complete:
            raise LoggerInitializationError("Logger factory not initialized")
        
        if name in self._loggers:
            return self._loggers[name]
        
        with self._lock:
            # Double-check after acquiring lock
            if name in self._loggers:
                return self._loggers[name]
            
            # Create new logger
            logger = logging.getLogger(name)
            logger.handlers.clear()  # Remove any existing handlers
            logger.propagate = False  # Don't propagate to root logger
            
            # Add configured handlers
            if self.console_handler:
                logger.addHandler(self.console_handler)
            
            if self.structured_handler:
                logger.addHandler(self.structured_handler)
            
            if self.file_handler:
                logger.addHandler(self.file_handler)
            
            # Set logger level to most verbose handler level
            min_level = logging.CRITICAL
            for handler in logger.handlers:
                min_level = min(min_level, handler.level)
            logger.setLevel(min_level)
            
            self._loggers[name] = logger
            return logger
    
    def get_console_logger(self, name: str) -> logging.Logger:
        """Get a logger that only outputs to console (for user-facing messages)."""
        console_logger_name = f"{name}_console_only"
        
        if console_logger_name in self._loggers:
            return self._loggers[console_logger_name]
        
        with self._lock:
            if console_logger_name in self._loggers:
                return self._loggers[console_logger_name]
            
            # Create console-only logger
            logger = logging.getLogger(console_logger_name)
            logger.handlers.clear()
            logger.propagate = False
            
            if self.console_handler:
                logger.addHandler(self.console_handler)
                logger.setLevel(self.console_handler.level)
            
            self._loggers[console_logger_name] = logger
            return logger
    
    def get_structured_logger(self, name: str) -> logging.Logger:
        """Get a logger that only outputs structured logs (for production diagnostics)."""
        structured_logger_name = f"{name}_structured_only"
        
        if structured_logger_name in self._loggers:
            return self._loggers[structured_logger_name]
        
        with self._lock:
            if structured_logger_name in self._loggers:
                return self._loggers[structured_logger_name]
            
            # Create structured-only logger
            logger = logging.getLogger(structured_logger_name)
            logger.handlers.clear()
            logger.propagate = False
            
            if self.structured_handler:
                logger.addHandler(self.structured_handler)
                logger.setLevel(self.structured_handler.level)
            
            if self.file_handler:
                logger.addHandler(self.file_handler)
            
            self._loggers[structured_logger_name] = logger
            return logger
    
    def reconfigure(self, new_config: LoggingConfig) -> None:
        """Reconfigure the logger factory with new settings."""
        with self._lock:
            # Clean up existing handlers
            self._cleanup_handlers()
            
            # Reset state
            self.config = new_config
            self._loggers.clear()
            
            # Reinitialize
            self._setup_handlers()
            self._configure_third_party_loggers()
    
    def _cleanup_handlers(self) -> None:
        """Clean up existing handlers."""
        handlers = [self.console_handler, self.structured_handler, self.file_handler]
        
        for handler in handlers:
            if handler:
                try:
                    handler.close()
                except:
                    pass  # Ignore cleanup errors
        
        self.console_handler = None
        self.structured_handler = None
        self.file_handler = None
    
    def cleanup(self) -> None:
        """
        Clean up resources on shutdown.
        
        This method cleans up handlers and loggers but preserves the ability
        to re-initialize the factory if needed.
        """
        with self._lock:
            self._cleanup_handlers()
            
            # Clean up all created loggers
            for logger in self._loggers.values():
                logger.handlers.clear()
            
            self._loggers.clear()
            self._setup_complete = False
    
    @classmethod
    def from_existing_config(cls, existing_config: Any) -> 'LoggerFactory':
        """
        Create logger factory from existing configuration object.
        
        This method provides integration with the existing config/settings.py
        system by accepting configuration objects and converting them to
        LoggingConfig format.
        
        Args:
            existing_config: Existing configuration object (e.g., from config/settings.py)
            
        Returns:
            Initialized LoggerFactory instance
            
        Example:
            from config.settings import get_settings
            settings = get_settings()
            factory = LoggerFactory.from_existing_config(settings)
        """
        # Convert existing config to LoggingConfig
        logging_config = cls._convert_existing_config(existing_config)
        
        # Get factory instance and initialize
        factory = cls()
        factory.initialize(logging_config)
        
        return factory
    
    @classmethod
    def _convert_existing_config(cls, existing_config: Any) -> LoggingConfig:
        """
        Convert existing configuration to LoggingConfig.
        
        This method handles the conversion from various existing configuration
        formats to our standardized LoggingConfig format.
        
        Args:
            existing_config: The existing configuration object
            
        Returns:
            Converted LoggingConfig instance
        """
        from .config import LoggingConfig, ConsoleConfig, StructuredConfig, FileConfig, LogLevel
        import os
        
        # Detect environment
        environment = "development"
        if hasattr(existing_config, 'environment'):
            environment = existing_config.environment
        elif os.getenv('ENVIRONMENT'):
            environment = os.getenv('ENVIRONMENT').lower()
        elif os.getenv('ENV'):
            environment = os.getenv('ENV').lower()
        
        # Extract logging level (try various common attribute names)
        log_level = LogLevel.INFO
        for attr_name in ['log_level', 'logging_level', 'level', 'LOG_LEVEL']:
            if hasattr(existing_config, attr_name):
                level_value = getattr(existing_config, attr_name)
                if isinstance(level_value, str) and level_value.upper() in LogLevel.__members__:
                    log_level = LogLevel(level_value.upper())
                    break
        
        # Check for debug mode
        debug_mode = False
        for attr_name in ['debug', 'DEBUG', 'debug_mode']:
            if hasattr(existing_config, attr_name):
                debug_mode = bool(getattr(existing_config, attr_name))
                break
        
        if debug_mode:
            log_level = LogLevel.DEBUG
        
        # Create console configuration
        console_config = ConsoleConfig(
            enabled=True,
            level=log_level,
            color_enabled=not environment == "production"
        )
        
        # Create structured configuration
        structured_config = StructuredConfig(
            enabled=True,
            level=LogLevel.DEBUG if debug_mode else LogLevel.INFO,
            include_timestamp=True,
            include_logger_name=True,
            include_thread_info=environment == "production"
        )
        
        # Create file configuration (if file logging is configured)
        file_config = FileConfig(enabled=False)
        
        # Check for file logging configuration
        for attr_name in ['log_file', 'logging_file', 'LOG_FILE']:
            if hasattr(existing_config, attr_name):
                log_file_path = getattr(existing_config, attr_name)
                if log_file_path:
                    file_config = FileConfig(
                        enabled=True,
                        file_path=log_file_path,
                        level=LogLevel.DEBUG
                    )
                    break
        
        # Create the complete logging configuration
        logging_config = LoggingConfig(
            console=console_config,
            structured=structured_config,
            file=file_config,
            environment=environment,
            suppress_azure_sdk=True,
            suppress_urllib3=True,
            disable_http_logging=True
        )
        
        return logging_config
    
    @classmethod
    def reset(cls) -> None:
        """Reset the factory instance (primarily for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance.cleanup()
                cls._instance = None
                cls._initialized = False
    
    @classmethod
    def reset_for_testing(cls) -> None:
        """
        Reset factory state for testing purposes.
        
        This method provides a clean reset that allows the factory to be
        re-initialized after cleanup, addressing the issue where cleanup
        would prevent subsequent re-initialization.
        """
        with cls._lock:
            if cls._instance:
                # Clean up existing instance
                cls._instance._cleanup_handlers()
                cls._instance._loggers.clear()
                cls._instance._setup_complete = False
                cls._instance.config = None
                
                # Reset class-level state
                cls._instance = None
                cls._initialized = False