# tests/logging/test_config.py
import pytest
from pathlib import Path
from pydantic import ValidationError

from utils.custom_logging.config import (
    LoggingConfig,
    ConsoleConfig,
    StructuredConfig,
    FileConfig,
    LogLevel,
    OutputFormat
)


class TestLogLevel:
    """Test LogLevel enum functionality."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_log_level_values(self):
        """Test LogLevel enum values."""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"


class TestOutputFormat:
    """Test OutputFormat enum functionality."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_output_format_values(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.CLEAN == "clean"
        assert OutputFormat.JSON == "json"
        assert OutputFormat.DETAILED == "detailed"
        assert OutputFormat.MINIMAL == "minimal"


class TestConsoleConfig:
    """Test ConsoleConfig model."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_default_values(self):
        """Test default configuration values."""
        config = ConsoleConfig()
        assert config.enabled is True
        assert config.level == LogLevel.INFO
        assert config.format == OutputFormat.CLEAN
        assert config.color_enabled is True
        assert config.timestamp_enabled is False
        assert config.show_logger_name is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_custom_values(self):
        """Test custom configuration values."""
        config = ConsoleConfig(
            enabled=False,
            level=LogLevel.DEBUG,
            format=OutputFormat.MINIMAL,
            color_enabled=False,
            timestamp_enabled=True,
            show_logger_name=True
        )
        assert config.enabled is False
        assert config.level == LogLevel.DEBUG
        assert config.format == OutputFormat.MINIMAL
        assert config.color_enabled is False
        assert config.timestamp_enabled is True
        assert config.show_logger_name is True


class TestStructuredConfig:
    """Test StructuredConfig model."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_default_values(self):
        """Test default configuration values."""
        config = StructuredConfig()
        assert config.enabled is True
        assert config.level == LogLevel.DEBUG
        assert config.format == "json"
        assert config.include_timestamp is True
        assert config.include_logger_name is True
        assert config.include_thread_info is False
        assert config.include_process_info is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_custom_values(self):
        """Test custom configuration values."""
        config = StructuredConfig(
            enabled=False,
            level=LogLevel.ERROR,
            format="custom",
            include_timestamp=False,
            include_logger_name=False,
            include_thread_info=True,
            include_process_info=True
        )
        assert config.enabled is False
        assert config.level == LogLevel.ERROR
        assert config.format == "custom"
        assert config.include_timestamp is False
        assert config.include_logger_name is False
        assert config.include_thread_info is True
        assert config.include_process_info is True


class TestFileConfig:
    """Test FileConfig model."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_default_values(self):
        """Test default configuration values."""
        config = FileConfig()
        assert config.enabled is False
        assert config.file_path is None
        assert config.level == LogLevel.DEBUG
        assert config.max_size_mb == 100
        assert config.backup_count == 5
        assert config.rotation_enabled is True
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_file_path_validation(self):
        """Test file path validation."""
        # Test string path conversion
        config = FileConfig(file_path="/tmp/test.log")
        assert isinstance(config.file_path, Path)
        assert str(config.file_path) == "/tmp/test.log"
        
        # Test Path object
        path_obj = Path("/tmp/test2.log")
        config = FileConfig(file_path=path_obj)
        assert config.file_path == path_obj
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_enabled_file_config(self):
        """Test enabled file configuration."""
        config = FileConfig(
            enabled=True,
            file_path="/tmp/app.log",
            level=LogLevel.INFO,
            max_size_mb=50,
            backup_count=3,
            rotation_enabled=False
        )
        assert config.enabled is True
        assert str(config.file_path) == "/tmp/app.log"
        assert config.level == LogLevel.INFO
        assert config.max_size_mb == 50
        assert config.backup_count == 3
        assert config.rotation_enabled is False


class TestLoggingConfig:
    """Test LoggingConfig model."""
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_default_values(self):
        """Test default configuration values."""
        config = LoggingConfig()
        assert isinstance(config.console, ConsoleConfig)
        assert isinstance(config.structured, StructuredConfig)
        assert isinstance(config.file, FileConfig)
        assert config.environment == "development"
        assert config.disable_http_logging is True
        assert config.suppress_azure_sdk is True
        assert config.suppress_urllib3 is True
        assert config.async_logging is False
        assert config.buffer_size == 1000
        assert config.flush_interval_seconds == 1.0
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_environment_validation(self):
        """Test environment validation."""
        # Valid environments
        for env in ['development', 'production', 'testing']:
            config = LoggingConfig(environment=env)
            assert config.environment == env
        
        # Invalid environment should raise ValidationError
        with pytest.raises(ValidationError):
            LoggingConfig(environment="invalid_env")
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_python_log_level(self):
        """Test Python log level conversion."""
        config = LoggingConfig()
        
        import logging
        assert config.get_python_log_level(LogLevel.DEBUG) == logging.DEBUG
        assert config.get_python_log_level(LogLevel.INFO) == logging.INFO
        assert config.get_python_log_level(LogLevel.WARNING) == logging.WARNING
        assert config.get_python_log_level(LogLevel.ERROR) == logging.ERROR
        assert config.get_python_log_level(LogLevel.CRITICAL) == logging.CRITICAL
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_is_production(self):
        """Test production environment detection."""
        dev_config = LoggingConfig(environment="development")
        assert dev_config.is_production() is False
        
        prod_config = LoggingConfig(environment="production")
        assert prod_config.is_production() is True
        
        test_config = LoggingConfig(environment="testing")
        assert test_config.is_production() is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_is_containerized(self):
        """Test containerized environment detection."""
        config = LoggingConfig()
        # This will depend on the actual environment during testing
        result = config.is_containerized()
        assert isinstance(result, bool)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_custom_configuration(self):
        """Test complete custom configuration."""
        console_config = ConsoleConfig(
            enabled=True,
            level=LogLevel.WARNING,
            format=OutputFormat.DETAILED
        )
        
        structured_config = StructuredConfig(
            enabled=True,
            level=LogLevel.DEBUG,
            include_thread_info=True
        )
        
        file_config = FileConfig(
            enabled=True,
            file_path="/tmp/test.log",
            level=LogLevel.INFO
        )
        
        config = LoggingConfig(
            console=console_config,
            structured=structured_config,
            file=file_config,
            environment="production",
            disable_http_logging=False,
            suppress_azure_sdk=False,
            async_logging=True,
            buffer_size=2000
        )
        
        assert config.console.level == LogLevel.WARNING
        assert config.structured.include_thread_info is True
        assert config.file.enabled is True
        assert config.environment == "production"
        assert config.disable_http_logging is False
        assert config.suppress_azure_sdk is False
        assert config.async_logging is True
        assert config.buffer_size == 2000
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            LoggingConfig(invalid_field="should_not_be_allowed")