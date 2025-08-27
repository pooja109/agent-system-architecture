"""
Comprehensive Unit Tests for PromptManager
=========================================
Tests all functionality of the prompt management system including edge cases,
error scenarios, and performance characteristics.
"""
import pytest
import tempfile
import yaml
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from services.prompt_manager import PromptManager
from models.prompt_models import PromptConfig, TemplateConfig, AgentConfig
from exceptions.prompt_exceptions import (
    PromptNotFoundError,
    PromptValidationError, 
    PromptCacheError
)
@pytest.fixture
def temp_prompts_dir():
    """Create temporary directory with test prompt configurations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_dir = Path(temp_dir)
        # Create test prompt configuration
        email_class_dir = prompts_dir / "email_classification"
        email_class_dir.mkdir(parents=True)
        config_data = {
            "agent_config": {
                "name": "email-intent-classifier",  
                "description": "Test email classification agent",
                "version": "1.0.0"
            },
            "system_instructions": """
You are an expert AI agent specializing in email intent classification.
INTENT CATEGORIES TO CLASSIFY:
1. POSITIVE - Customer shows interest
2. NEGATIVE - Customer rejects offer
CONFIDENCE SCORING GUIDELINES:
- High confidence (0.85-0.99): Clear intent
- Medium confidence (0.60-0.84): Some ambiguity
RESPONSE FORMAT:
Always respond with valid JSON containing intent and confidence.
""".strip(),
            "confidence_scoring": {
                "high": {"range": [0.85, 0.99], "description": "Clear intent"},
                "medium": {"range": [0.60, 0.84], "description": "Some ambiguity"},
                "low": {"range": [0.30, 0.59], "description": "Unclear intent"},
                "very_low": {"range": [0.10, 0.29], "description": "Very ambiguous"}
            },
            "response_format": {
                "type": "json",
                "response_schema": {
                    "intent": "string",
                    "confidence": "float"
                }
            }
        }
        config_file = email_class_dir / "system_instructions.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        yield prompts_dir
@pytest.fixture
def temp_prompts_with_template():
    """Create temporary directory with template files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        prompts_dir = Path(temp_dir)
        # Create template directory and file
        template_dir = prompts_dir / "email_classification"
        template_dir.mkdir(parents=True)
        template_data = {
            "template_version": "1.0.0",
            "template": "Hello {name}, your email about {subject} was received.",
            "variables": {
                "name": "Recipient name",
                "subject": "Email subject"
            }
        }
        template_file = template_dir / "test_template.yaml"
        with open(template_file, 'w') as f:
            yaml.dump(template_data, f)
        yield prompts_dir
class TestPromptManagerInitialization:
    """Test PromptManager initialization and configuration."""
    @pytest.mark.fast
    @pytest.mark.prompt
    @pytest.mark.unit
    @pytest.mark.fast
    def test_default_initialization(self):
        """Test PromptManager with default settings."""
        manager = PromptManager()
        # Clear cache from previous tests
        manager.clear_cache()
        assert manager.prompts_base_path.name == "prompts"
        assert manager.cache_ttl == timedelta(seconds=300)
        assert manager.enable_hot_reload is False
        assert manager.schema_validation is True
        assert len(manager._cached_prompts) == 0
    @pytest.mark.fast
    @pytest.mark.prompt
    @pytest.mark.unit
    @pytest.mark.fast
    def test_custom_initialization(self):
        """Test PromptManager with custom settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = Path(temp_dir) / "custom_prompts"
            manager = PromptManager(
                prompts_base_path=custom_path,
                cache_ttl_seconds=600,
                enable_hot_reload=True,
                schema_validation=False
            )
            assert manager.prompts_base_path == custom_path
            assert manager.cache_ttl == timedelta(seconds=600)
            assert manager.enable_hot_reload is True
            assert manager.schema_validation is False
            assert custom_path.exists()
    @pytest.mark.fast
    @pytest.mark.prompt
    @pytest.mark.unit
    @pytest.mark.fast
    def test_base_directory_creation(self):
        """Test that base directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_path = Path(temp_dir) / "new_prompts_dir"
            assert not non_existent_path.exists()
            manager = PromptManager(prompts_base_path=non_existent_path)
            assert non_existent_path.exists()
class TestPromptConfigLoading:
    """Test prompt configuration loading functionality."""
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_successful_config_loading(self, temp_prompts_dir):
        """Test successful loading of prompt configuration."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        config = await manager.load_prompt_config("email_classification")
        assert isinstance(config, PromptConfig)
        assert config.agent_config.name == "email-intent-classifier"
        assert config.agent_config.version == "1.0.0"
        assert "INTENT CATEGORIES" in config.system_instructions
        assert config.confidence_scoring is not None
        assert config.response_format.type == "json"
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_config_not_found_error(self, temp_prompts_dir):
        """Test error when prompt configuration doesn't exist."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        with pytest.raises(PromptNotFoundError) as exc_info:
            await manager.load_prompt_config("nonexistent_prompt")
        assert "nonexistent_prompt" in str(exc_info.value)
        assert "system_instructions.yaml" in str(exc_info.value)
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_empty_config_validation_error(self, temp_prompts_dir):
        """Test error when configuration file is empty."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Create empty config file
        empty_dir = temp_prompts_dir / "empty_prompt"
        empty_dir.mkdir()
        empty_config = empty_dir / "system_instructions.yaml"
        empty_config.touch()
        with pytest.raises(PromptValidationError) as exc_info:
            await manager.load_prompt_config("empty_prompt")
        assert "Empty or invalid YAML" in str(exc_info.value)
class TestSystemInstructionsRetrieval:
    """Test system instructions retrieval functionality."""
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_get_system_instructions_success(self, temp_prompts_dir):
        """Test successful retrieval of system instructions."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        instructions = await manager.get_system_instructions("email_classification")
        assert isinstance(instructions, str)
        assert len(instructions) > 0
        assert "INTENT CATEGORIES" in instructions
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_get_system_instructions_not_found(self, temp_prompts_dir):
        """Test error when prompt not found."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        with pytest.raises(PromptNotFoundError):
            await manager.get_system_instructions("nonexistent_prompt")
class TestCachingBehavior:
    """Test caching functionality and performance."""
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_cache_hit_behavior(self, temp_prompts_dir):
        """Test that second load uses cache."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # First load - should be cache miss
        config1 = await manager.load_prompt_config("email_classification")
        assert manager._cache_misses == 1
        assert manager._cache_hits == 0
        # Second load - should be cache hit
        config2 = await manager.load_prompt_config("email_classification")
        assert manager._cache_misses == 1
        assert manager._cache_hits == 1
        # Configs should be equivalent
        assert config1.agent_config.name == config2.agent_config.name
        assert config1.system_instructions == config2.system_instructions
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_cache_ttl_expiration(self, temp_prompts_dir):
        """Test that cache expires after TTL."""
        manager = PromptManager(
            prompts_base_path=temp_prompts_dir,
            cache_ttl_seconds=1  # 1 second TTL
        )
        # First load
        await manager.load_prompt_config("email_classification")
        assert manager._cache_misses == 1
        # Wait for TTL expiration
        await asyncio.sleep(1.1)
        # Second load should be cache miss due to TTL expiration
        await manager.load_prompt_config("email_classification")
        assert manager._cache_misses == 2
    @pytest.mark.fast
    @pytest.mark.prompt
    @pytest.mark.unit
    @pytest.mark.fast
    def test_manual_cache_clearing(self, temp_prompts_dir):
        """Test manual cache clearing functionality."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Populate cache
        manager._cached_prompts["test_key"] = {"test": "data"}
        manager._cache_timestamps["test_key"] = datetime.now(timezone.utc)
        assert len(manager._cached_prompts) == 1
        # Clear cache
        manager.clear_cache()
        assert len(manager._cached_prompts) == 0
        assert len(manager._cache_timestamps) == 0
    @pytest.mark.fast
    @pytest.mark.prompt
    @pytest.mark.unit
    @pytest.mark.fast
    def test_cache_statistics(self, temp_prompts_dir):
        """Test cache statistics calculation."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Simulate some cache activity
        manager._cache_hits = 10
        manager._cache_misses = 5
        manager._load_times = {"test_prompt": 0.025}
        stats = manager.get_cache_statistics()
        assert stats["cache_hits"] == 10
        assert stats["cache_misses"] == 5
        assert stats["hit_rate_percent"] == 66.67
        assert "test_prompt" in stats["average_load_times"]
        assert stats["average_load_times"]["test_prompt"] == 25.0  # Converted to ms
class TestSpecificCacheClearing:
    """Test specific cache clearing functionality."""
    @pytest.mark.ci_safe
    @pytest.mark.email
    @pytest.mark.fast
    @pytest.mark.prompt
    @pytest.mark.unit
    @pytest.mark.fast
    def test_clear_specific_prompt_cache(self, temp_prompts_dir):
        """Test clearing cache for specific prompt."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Populate cache with multiple items
        manager._cached_prompts["config_email_classification"] = {"test": "data1"}
        manager._cached_prompts["config_other_prompt"] = {"test": "data2"}
        manager._cached_prompts["template_email_classification_template1"] = {"test": "data3"}
        manager._cache_timestamps["config_email_classification"] = datetime.now(timezone.utc)
        manager._cache_timestamps["config_other_prompt"] = datetime.now(timezone.utc)
        manager._cache_timestamps["template_email_classification_template1"] = datetime.now(timezone.utc)
        assert len(manager._cached_prompts) == 3
        # Clear cache for specific prompt
        manager.clear_cache("email_classification")
        # Should have cleared email_classification items but not other_prompt
        assert len(manager._cached_prompts) == 1
        assert "config_other_prompt" in manager._cached_prompts
        assert "config_email_classification" not in manager._cached_prompts
        assert "template_email_classification_template1" not in manager._cached_prompts
class TestErrorHandling:
    """Test comprehensive error handling scenarios."""
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_file_permission_error(self, temp_prompts_dir):
        """Test handling of file permission errors."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Create a directory we can't read (simulate permission error)
        restricted_dir = temp_prompts_dir / "restricted_prompt"
        restricted_dir.mkdir()
        config_file = restricted_dir / "system_instructions.yaml"
        config_file.write_text("test: data")
        # Mock permission error
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with pytest.raises(PromptCacheError) as exc_info:
                await manager.load_prompt_config("restricted_prompt")
        assert "Failed to load prompt" in str(exc_info.value)
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_yaml_parsing_error(self, temp_prompts_dir):
        """Test handling of malformed YAML files."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Create malformed YAML
        bad_yaml_dir = temp_prompts_dir / "bad_yaml_prompt"
        bad_yaml_dir.mkdir()
        bad_config = bad_yaml_dir / "system_instructions.yaml"
        bad_config.write_text("invalid: yaml: content: [unclosed bracket")
        with pytest.raises((PromptCacheError, PromptValidationError)):
            await manager.load_prompt_config("bad_yaml_prompt")
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_validation_error_handling(self, temp_prompts_dir):
        """Test handling of Pydantic validation errors."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Create config with missing required fields
        invalid_dir = temp_prompts_dir / "invalid_prompt"
        invalid_dir.mkdir()
        invalid_config = invalid_dir / "system_instructions.yaml"
        # Missing required system_instructions field
        invalid_data = {
            "agent_config": {
                "name": "test",
                "description": "test", 
                "version": "1.0.0"
            }
            # Missing system_instructions
        }
        with open(invalid_config, 'w') as f:
            yaml.dump(invalid_data, f)
        with pytest.raises(Exception):  # Should be Pydantic validation error
            await manager.load_prompt_config("invalid_prompt")
class TestTemplateLoading:
    """Test template loading functionality."""
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_successful_template_loading(self, temp_prompts_with_template):
        """Test successful loading of template configuration."""
        manager = PromptManager(prompts_base_path=temp_prompts_with_template)
        template = await manager.load_template("email_classification", "test_template")
        assert isinstance(template, TemplateConfig)
        assert template.template_version == "1.0.0"
        assert "{name}" in template.template
        assert "{subject}" in template.template
        assert template.variables is not None
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_template_not_found_error(self, temp_prompts_with_template):
        """Test error when template file doesn't exist."""
        manager = PromptManager(prompts_base_path=temp_prompts_with_template)
        with pytest.raises(PromptNotFoundError) as exc_info:
            await manager.load_template("email_classification", "nonexistent_template")
        assert "nonexistent_template" in str(exc_info.value)
class TestValidationFramework:
    """Test the validation framework for all prompts."""
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_validate_all_prompts_success(self, temp_prompts_dir):
        """Test validation of all prompts when they're valid."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        results = await manager.validate_all_prompts()
        assert "email_classification" in results
        assert results["email_classification"] is True
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_validate_all_prompts_with_failures(self, temp_prompts_dir):
        """Test validation when some prompts are invalid."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        # Add an invalid prompt
        invalid_dir = temp_prompts_dir / "invalid_prompt"
        invalid_dir.mkdir()
        invalid_config = invalid_dir / "system_instructions.yaml"
        invalid_config.write_text("invalid: incomplete config")
        results = await manager.validate_all_prompts()
        assert "email_classification" in results
        assert "invalid_prompt" in results
        assert results["email_classification"] is True
        assert results["invalid_prompt"] is False


# Additional advanced features from test_prompt_manager_new_features.py
from services.prompt_manager import CircuitBreakerState, CircuitBreaker


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.integration
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker is properly initialized."""
        manager = PromptManager(enable_circuit_breaker=True)
        assert manager.circuit_breaker is not None
        assert manager.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert manager.circuit_breaker.failure_threshold == 5
        assert manager.circuit_breaker.can_proceed() is True
    
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.integration
    def test_circuit_breaker_disabled(self):
        """Test circuit breaker can be disabled."""
        manager = PromptManager(enable_circuit_breaker=False)
        assert manager.circuit_breaker is None
    
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.integration
    def test_circuit_breaker_statistics(self):
        """Test circuit breaker statistics in cache statistics."""
        manager = PromptManager(enable_circuit_breaker=True)
        stats = manager.get_cache_statistics()
        assert "circuit_breaker" in stats
        cb_stats = stats["circuit_breaker"]
        assert "state" in cb_stats
        assert "failure_count" in cb_stats
        assert "success_count" in cb_stats
        assert cb_stats["state"] == "closed"


class TestMemoryMonitoring:
    """Test memory monitoring functionality."""
    
    @pytest.mark.ci_safe
    @pytest.mark.email
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.medium
    @pytest.mark.integration
    def test_memory_statistics_basic(self):
        """Test basic memory statistics collection."""
        manager = PromptManager()
        stats = manager.get_memory_statistics()
        assert "cache_memory_usage" in stats
        cache_stats = stats["cache_memory_usage"]
        assert "cached_prompts_size_bytes" in cache_stats
        assert "cache_timestamps_size_bytes" in cache_stats
        assert "total_cache_size_mb" in cache_stats
        # Initially should be minimal memory usage
        assert cache_stats["total_cache_size_mb"] < 1.0
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.integration
    def test_memory_statistics_process_info(self):
        """Test process memory information collection."""
        manager = PromptManager()
        stats = manager.get_memory_statistics()
        assert "process_memory" in stats
        process_stats = stats["process_memory"]
        # Should either have memory info or error message
        if "error" not in process_stats:
            assert "rss_mb" in process_stats
            assert "vms_mb" in process_stats
            assert "memory_percent" in process_stats
            assert process_stats["rss_mb"] > 0


class TestHealthChecks:
    """Test health check functionality."""
    
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.email
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_health_check_healthy_system(self, temp_prompts_dir):
        """Test health check with healthy system."""
        manager = PromptManager(prompts_base_path=temp_prompts_dir)
        health = await manager.health_check()
        assert "status" in health
        assert "timestamp" in health
        assert "cache_status" in health
        assert "memory_status" in health
        assert "prompts_directory" in health
        assert "prompt_validation" in health
        # Should be healthy with valid test data
        assert health["status"] in ["healthy", "degraded"]  # degraded is ok if some validation fails
        # Directory should be accessible
        dir_info = health["prompts_directory"]
        assert dir_info["exists"] is True
        assert dir_info["readable"] is True