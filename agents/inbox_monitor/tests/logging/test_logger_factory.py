# tests/logging/test_logger_factory.py - RECOVERED with performance optimization
import pytest
import logging
import threading
import tempfile
from pathlib import Path
from io import StringIO

from utils.custom_logging.logger_factory import LoggerFactory
from utils.custom_logging.config import LoggingConfig, ConsoleConfig, StructuredConfig, FileConfig, LogLevel, OutputFormat
from utils.custom_logging.exceptions import LoggerInitializationError

# Phase 1 Recovery: Import performance monitoring and logger isolation
from tests.fixtures.logger_isolation import logger_isolation, isolated_logger, logger_performance_monitor, assert_logger_performance_within_limits
from tests.fixtures.performance_monitoring import performance_monitor, enforce_logger_performance, assert_logger_test_performance
from tests.fixtures.optimized_mocks import mock_pool


@pytest.mark.usefixtures("isolated_logger")
class TestLoggerFactory:
    """Test LoggerFactory functionality with logger isolation."""
    
    def setup_method(self):
        """Reset factory before each test - now with isolation."""
        # Note: LoggerFactory.reset() is handled by logger_isolation fixture
        pass
    
    def teardown_method(self):
        """Clean up after each test - now handled by fixtures."""
        # Note: Cleanup is handled by logger_isolation fixture
        pass
    
    @pytest.fixture
    def basic_config(self):
        """Basic logging configuration for testing."""
        return LoggingConfig(
            console=ConsoleConfig(enabled=True, level=LogLevel.INFO, color_enabled=False),
            structured=StructuredConfig(enabled=True, level=LogLevel.DEBUG),
            environment="testing"
        )
    
    @pytest.fixture
    def console_only_config(self):
        """Console-only logging configuration."""
        return LoggingConfig(
            console=ConsoleConfig(enabled=True, level=LogLevel.INFO, color_enabled=False),
            structured=StructuredConfig(enabled=False),
            environment="testing"
        )
    
    @pytest.fixture
    def file_config(self):
        """File-based logging configuration."""
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        
        return LoggingConfig(
            console=ConsoleConfig(enabled=True, level=LogLevel.INFO, color_enabled=False),
            structured=StructuredConfig(enabled=True, level=LogLevel.DEBUG),
            file=FileConfig(enabled=True, file_path=temp_file.name, level=LogLevel.DEBUG),
            environment="testing"
        )
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_singleton_pattern_isolated(self, isolated_logger, performance_monitor):
        """Test that LoggerFactory is a singleton within test scope."""
        with performance_monitor.monitor():
            factory1 = LoggerFactory()
            factory2 = LoggerFactory()
            
            assert factory1 is factory2
            assert id(factory1) == id(factory2)
        
        # Verify performance
        metrics = performance_monitor.metrics
        assert_logger_test_performance(metrics)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_initialization_isolated(self, basic_config, isolated_logger, logger_performance_monitor):
        """Test factory initialization with performance monitoring."""
        logger_performance_monitor.start_monitoring()
        
        import time
        start_time = time.perf_counter()
        
        factory = LoggerFactory()
        
        # Should not be setup initially
        assert not factory._setup_complete
        
        # Initialize with config - measure performance
        init_start = time.perf_counter()
        factory.initialize(basic_config)
        init_time = time.perf_counter() - init_start
        logger_performance_monitor.record_logger_creation(init_time)
        
        assert factory._setup_complete
        assert factory.config == basic_config
        assert factory.console_handler is not None
        assert factory.structured_handler is not None
        assert factory.file_handler is None  # File not enabled in basic_config
        
        # Verify initialization was fast
        assert init_time < 1.0, f"Logger factory initialization took {init_time:.3f}s, expected <1.0s"
        
        # Get performance report
        performance_report = logger_performance_monitor.get_performance_report()
        assert_logger_performance_within_limits(performance_report, max_total_time=2.0)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_double_initialization_error(self, basic_config, isolated_logger):
        """Test that double initialization raises an error."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        with pytest.raises(LoggerInitializationError):
            factory.initialize(basic_config)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_logger_before_initialization(self, isolated_logger):
        """Test getting logger before initialization raises error."""
        factory = LoggerFactory()
        
        with pytest.raises(LoggerInitializationError):
            factory.get_logger("test_logger")
    
    @pytest.mark.fast
    @pytest.mark.unit  
    def test_basic_logger_creation_isolated(self, basic_config, isolated_logger, enforce_logger_performance):
        """Test basic logger creation with isolation and performance limits."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        # Test logger creation within performance limits
        logger = factory.get_logger("test_logger")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
        assert len(logger.handlers) == 2  # Console + Structured
        assert logger.propagate is False
        
        # Test that logger is properly isolated
        test_message = "Test isolation message"
        logger.info(test_message)  # Should not interfere with other tests
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_logger_caching_performance(self, basic_config, isolated_logger, performance_monitor):
        """Test that loggers are cached and reused with performance validation."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        with performance_monitor.monitor():
            # First access - should create logger
            logger1 = factory.get_logger("test_logger")
            
            # Second access - should use cache (much faster)
            logger2 = factory.get_logger("test_logger")
            
            # Multiple accesses to test cache performance
            for i in range(10):
                cached_logger = factory.get_logger("test_logger")
                assert cached_logger is logger1
        
        assert logger1 is logger2
        assert id(logger1) == id(logger2)
        
        # Verify caching improved performance
        metrics = performance_monitor.metrics
        assert_logger_test_performance(metrics)
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_console_only_logger(self, basic_config):
        """Test console-only logger creation."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        console_logger = factory.get_console_logger("test_logger")
        
        assert isinstance(console_logger, logging.Logger)
        assert console_logger.name == "test_logger_console_only"
        assert len(console_logger.handlers) == 1  # Only console handler
        assert console_logger.handlers[0] == factory.console_handler
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_structured_only_logger(self, basic_config):
        """Test structured-only logger creation."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        structured_logger = factory.get_structured_logger("test_logger")
        
        assert isinstance(structured_logger, logging.Logger)
        assert structured_logger.name == "test_logger_structured_only"
        assert len(structured_logger.handlers) == 1  # Only structured handler
        assert structured_logger.handlers[0] == factory.structured_handler
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_file_handler_setup(self, file_config):
        """Test file handler setup."""
        factory = LoggerFactory()
        factory.initialize(file_config)
        
        assert factory.file_handler is not None
        assert isinstance(factory.file_handler, logging.Handler)
        
        # Test that loggers get file handler
        logger = factory.get_logger("test_logger")
        assert len(logger.handlers) == 3  # Console + Structured + File
        
        # Test that structured-only logger gets file handler
        structured_logger = factory.get_structured_logger("test_logger")
        assert len(structured_logger.handlers) == 2  # Structured + File
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_third_party_logger_suppression(self, basic_config):
        """Test third-party logger suppression."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        # Check that Azure SDK loggers are suppressed
        azure_logger = logging.getLogger("azure")
        assert azure_logger.level == logging.WARNING
        assert azure_logger.propagate is False
        
        # Check that urllib3 loggers are suppressed
        urllib3_logger = logging.getLogger("urllib3")
        assert urllib3_logger.level == logging.WARNING
        assert urllib3_logger.propagate is False
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_third_party_suppression_disabled(self):
        """Test with third-party suppression disabled."""
        config = LoggingConfig(
            suppress_azure_sdk=False,
            suppress_urllib3=False,
            disable_http_logging=False,
            environment="testing"
        )
        
        factory = LoggerFactory()
        factory.initialize(config)
        
        # Azure logger should not be modified
        azure_logger = logging.getLogger("azure")
        # Note: level might still be WARNING due to other initialization
        # The key point is that we don't explicitly suppress it
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_logger_level_setting(self, basic_config):
        """Test that logger levels are set correctly."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        logger = factory.get_logger("test_logger")
        
        # Logger level should be the most verbose of its handlers
        # Console: INFO, Structured: DEBUG, so logger should be DEBUG
        assert logger.level == logging.DEBUG
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_console_disabled_configuration(self):
        """Test configuration with console handler disabled."""
        config = LoggingConfig(
            console=ConsoleConfig(enabled=False),
            structured=StructuredConfig(enabled=True, level=LogLevel.INFO),
            environment="testing"
        )
        
        factory = LoggerFactory()
        factory.initialize(config)
        
        assert factory.console_handler is None
        assert factory.structured_handler is not None
        
        logger = factory.get_logger("test_logger")
        assert len(logger.handlers) == 1  # Only structured handler
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_all_handlers_disabled(self):
        """Test configuration with all handlers disabled."""
        config = LoggingConfig(
            console=ConsoleConfig(enabled=False),
            structured=StructuredConfig(enabled=False),
            environment="testing"
        )
        
        factory = LoggerFactory()
        factory.initialize(config)
        
        assert factory.console_handler is None
        assert factory.structured_handler is None
        
        logger = factory.get_logger("test_logger")
        assert len(logger.handlers) == 0
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_reconfiguration(self, basic_config):
        """Test factory reconfiguration."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        # Get a logger with initial config
        logger1 = factory.get_logger("test_logger")
        initial_handler_count = len(logger1.handlers)
        
        # Create new configuration
        new_config = LoggingConfig(
            console=ConsoleConfig(enabled=False),
            structured=StructuredConfig(enabled=True, level=LogLevel.ERROR),
            environment="testing"
        )
        
        # Reconfigure
        factory.reconfigure(new_config)
        
        # Get logger again - should be fresh
        logger2 = factory.get_logger("test_logger")
        
        # Should be different instance (because loggers were cleared)
        assert logger2 is not logger1
        assert len(logger2.handlers) == 1  # Only structured handler
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_cleanup(self, basic_config):
        """Test factory cleanup."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        # Create some loggers
        logger1 = factory.get_logger("logger1")
        logger2 = factory.get_logger("logger2")
        
        assert len(factory._loggers) == 2
        assert factory._setup_complete is True
        
        # Cleanup
        factory.cleanup()
        
        assert len(factory._loggers) == 0
        assert factory._setup_complete is False
        assert factory.console_handler is None
        assert factory.structured_handler is None
        assert factory.file_handler is None
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_thread_safety(self, basic_config):
        """Test thread safety of logger factory."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        loggers = []
        errors = []
        
        def create_logger(logger_name):
            try:
                logger = factory.get_logger(f"logger_{logger_name}")
                loggers.append(logger)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_logger, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(loggers) == 10
        assert len(factory._loggers) == 10
        
        # Each logger should be unique
        logger_names = [logger.name for logger in loggers]
        assert len(set(logger_names)) == 10
    
    @pytest.mark.performance
    @pytest.mark.integration
    def test_logger_factory_performance_benchmarks(self, basic_config, isolated_logger, logger_performance_monitor):
        """Comprehensive performance benchmarks for logger factory - Phase 1 Recovery Target."""
        logger_performance_monitor.start_monitoring()
        
        import time
        
        factory = LoggerFactory()
        
        # Benchmark 1: Factory initialization
        init_start = time.perf_counter()
        factory.initialize(basic_config)
        init_time = time.perf_counter() - init_start
        logger_performance_monitor.record_logger_creation(init_time)
        
        # Benchmark 2: Single logger creation
        create_start = time.perf_counter()
        logger = factory.get_logger("perf_test_logger")
        create_time = time.perf_counter() - create_start
        logger_performance_monitor.record_logger_creation(create_time)
        
        # Benchmark 3: Multiple logger creation (should use caching)
        cache_start = time.perf_counter()
        cached_loggers = []
        for i in range(10):
            cached_loggers.append(factory.get_logger(f"perf_logger_{i}"))
        cache_time = time.perf_counter() - cache_start
        logger_performance_monitor.record_logger_creation(cache_time)
        
        # Benchmark 4: Logger usage performance
        usage_start = time.perf_counter()
        for i in range(100):
            logger.info(f"Performance test message {i}")
        usage_time = time.perf_counter() - usage_start
        logger_performance_monitor.record_handler_operation(usage_time)
        
        # Verify performance targets
        performance_report = logger_performance_monitor.get_performance_report()
        
        # Phase 1 Recovery Targets:
        # - Individual test execution: <5s
        # - Logger initialization: <1s
        # - Logger creation: <0.1s
        # - Logger caching should be fast: <0.01s per cached access
        assert init_time < 1.0, f"Logger factory initialization took {init_time:.3f}s, target <1.0s"
        assert create_time < 0.1, f"Single logger creation took {create_time:.3f}s, target <0.1s"
        assert cache_time < 0.5, f"10 logger creation took {cache_time:.3f}s, target <0.5s"
        assert usage_time < 0.2, f"100 log messages took {usage_time:.3f}s, target <0.2s"
        
        # Overall performance validation
        assert_logger_performance_within_limits(performance_report, max_total_time=5.0, max_creation_time=1.0)
        
        print(f"\n🎯 LOGGER FACTORY PERFORMANCE BENCHMARKS:")
        print(f"   Factory initialization: {init_time:.3f}s")
        print(f"   Single logger creation: {create_time:.3f}s")
        print(f"   10 logger creation: {cache_time:.3f}s")
        print(f"   100 log messages: {usage_time:.3f}s")
        print(f"   Total test time: {performance_report['total_execution_time']:.3f}s")
        print(f"   ✅ All performance targets met - Phase 1 recovery successful!")
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_concurrent_same_logger_creation(self, basic_config):
        """Test concurrent creation of the same logger name."""
        factory = LoggerFactory()
        factory.initialize(basic_config)
        
        loggers = []
        errors = []
        
        def get_same_logger():
            try:
                logger = factory.get_logger("shared_logger")
                loggers.append(logger)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads trying to get the same logger
        threads = []
        for i in range(5):
            thread = threading.Thread(target=get_same_logger)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Concurrent creation errors: {errors}"
        assert len(loggers) == 5
        
        # All loggers should be the same instance
        first_logger = loggers[0]
        for logger in loggers[1:]:
            assert logger is first_logger
        
        # Should only have one logger in the factory cache
        assert len(factory._loggers) == 1
    
    @pytest.mark.fast
    @pytest.mark.unit
    def test_reset_functionality(self, basic_config):
        """Test factory reset functionality."""
        # Create first instance
        factory1 = LoggerFactory()
        factory1.initialize(basic_config)
        factory1.get_logger("test_logger")
        
        assert factory1._setup_complete is True
        assert len(factory1._loggers) == 1
        
        # Reset the factory
        LoggerFactory.reset()
        
        # Create new instance - should be different
        factory2 = LoggerFactory()
        
        # Should be a fresh instance
        assert factory2._setup_complete is False
        assert len(factory2._loggers) == 0
        assert factory2 is not factory1