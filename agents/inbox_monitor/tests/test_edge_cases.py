"""
Edge Case Tests for PromptManager Coverage Improvement
=====================================================
These tests target specific uncovered lines and edge cases to increase
test coverage from 80% to 90%+.
Focus areas:
- Import error handling
- Edge cases in circuit breaker states
- Error conditions in health checks
- Fallback paths in schema validation
- Memory monitoring edge cases
"""
import pytest
import tempfile
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timezone
from services.prompt_manager import PromptManager, CircuitBreaker, CircuitBreakerState
from exceptions.prompt_exceptions import (
    PromptNotFoundError,
    PromptValidationError, 
    PromptCacheError
)
class TestImportFallbackPaths:
    """Test import error handling and fallback paths."""



    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_psutil_not_available_fallback(self):
        """Test behavior when psutil is not available."""
        with patch.dict('sys.modules', {'psutil': None}):
            # Force re-import to trigger ImportError path
            import importlib
            if 'services.prompt_manager' in sys.modules:
                del sys.modules['services.prompt_manager']
            # This should use the fallback path
            from services.prompt_manager import PromptManager
            manager = PromptManager()
            memory_stats = manager.get_memory_statistics()
            # Should have error message for process memory when psutil unavailable
            assert "process_memory" in memory_stats
            assert "error" in memory_stats["process_memory"]
            assert "psutil not available" in memory_stats["process_memory"]["error"]




    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_jsonschema_not_available_fallback(self):
        """Test schema validation fallback when jsonschema not available."""
        # Test the case where jsonschema is not available
        manager = PromptManager()
        # Patch JSONSCHEMA_AVAILABLE to False for this test
        with patch('services.prompt_manager.JSONSCHEMA_AVAILABLE', False):
            # Test basic validation without jsonschema
            test_data = {
                "agent_config": {
                    "name": "test",
                    "description": "test desc",
                    "version": "1.0.0"
                },
                "system_instructions": "Test instructions"
            }
            # Should not raise exception and use fallback validation
            import asyncio
            result = asyncio.run(manager._validate_prompt_schema(test_data, "system_instructions"))
            # Fallback validation should pass for valid structure
            assert result is None  # No exception raised




    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_jsonschema_validation_with_missing_fields(self):
        """Test jsonschema fallback validation with missing required fields."""
        manager = PromptManager()
        # Patch JSONSCHEMA_AVAILABLE to False for this test
        with patch('services.prompt_manager.JSONSCHEMA_AVAILABLE', False):
            # Missing system_instructions field
            invalid_data = {
                "agent_config": {
                    "name": "test",
                    "description": "test",
                    "version": "1.0.0"
                }
                # Missing system_instructions
            }
            with pytest.raises(PromptValidationError) as exc_info:
                import asyncio
                asyncio.run(manager._validate_prompt_schema(invalid_data, "system_instructions"))
            assert "Required field 'system_instructions' missing" in str(exc_info.value)
class TestCircuitBreakerEdgeCases:
    """Test circuit breaker edge cases and state transitions."""



    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_circuit_breaker_half_open_return_true(self):
        """Test that circuit breaker returns True in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        # Manually set to HALF_OPEN state
        breaker.state = CircuitBreakerState.HALF_OPEN
        # Should return True to allow requests through
        assert breaker.can_proceed() is True



    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_circuit_breaker_success_in_closed_state(self):
        """Test record_success in CLOSED state resets failure count."""
        breaker = CircuitBreaker()
        # Record some failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        # Record success in CLOSED state should reset failure count
        breaker.record_success()
        assert breaker.failure_count == 0



    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.edge_case
    @pytest.mark.fast
    def test_memory_error_during_psutil_access(self):
        """Test handling of memory errors when accessing process memory."""
        manager = PromptManager()
        with patch('psutil.Process') as mock_process:
            mock_instance = MagicMock()
            mock_instance.memory_info.side_effect = MemoryError("Out of memory")
            mock_process.return_value = mock_instance
            memory_stats = manager.get_memory_statistics()
            # Should handle MemoryError gracefully
            assert "process_memory" in memory_stats
            assert "error" in memory_stats["process_memory"]
            assert "Out of memory" in memory_stats["process_memory"]["error"]
class TestHealthCheckEdgeCases:
    """Test health check edge cases and error conditions."""
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_health_check_directory_not_directory(self):
        """Test health check when prompts path exists but is not a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use different approach - test with manager that has existing path but patch is_dir
            manager = PromptManager(prompts_base_path=Path(temp_dir))
            # Mock the path to appear as non-directory during health check
            with patch.object(Path, 'exists', return_value=True), \
                 patch.object(Path, 'is_dir', return_value=False):
                health = await manager.health_check()
            assert health["status"] in ["unhealthy", "degraded"]
            # May be in errors or warnings depending on implementation
            all_messages = health.get("errors", []) + health.get("warnings", [])
            assert any("not a directory" in msg for msg in all_messages)
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_health_check_directory_access_error(self):
        """Test health check when directory access raises exception."""
        manager = PromptManager()
        with patch.object(Path, 'exists', side_effect=OSError("Permission denied")):
            health = await manager.health_check()
            assert health["status"] in ["unhealthy", "degraded"]
            # May be in errors or warnings depending on implementation
            all_messages = health.get("errors", []) + health.get("warnings", [])
            assert any("Error checking prompts directory" in msg or "Permission denied" in msg for msg in all_messages)
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_health_check_validation_exception(self):
        """Test health check when validate_all_prompts raises exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PromptManager(prompts_base_path=Path(temp_dir))
            with patch.object(manager, 'validate_all_prompts', side_effect=Exception("Validation error")):
                health = await manager.health_check()
                assert health["status"] == "unhealthy"
                assert "errors" in health
                assert any("Prompt validation failed" in error for error in health["errors"])
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_health_check_with_failed_prompts(self):
        """Test health check with some failed prompt validations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            # Create valid prompt
            valid_dir = prompts_dir / "valid_prompt"
            valid_dir.mkdir(parents=True)
            valid_config = valid_dir / "system_instructions.yaml"
            valid_config.write_text("""
agent_config:
  name: "test"
  description: "test description"
  version: "1.0.0"
system_instructions: |
  Test instructions
  INTENT CATEGORIES TO CLASSIFY:
  1. POSITIVE - Test
  CONFIDENCE SCORING GUIDELINES:
  - High confidence (0.85-0.99): Clear
  RESPONSE FORMAT:
  JSON format required
""")
            # Create invalid prompt
            invalid_dir = prompts_dir / "invalid_prompt"
            invalid_dir.mkdir()
            invalid_config = invalid_dir / "system_instructions.yaml"
            invalid_config.write_text("invalid: yaml content")
            manager = PromptManager(prompts_base_path=prompts_dir)
            health = await manager.health_check()
            assert health["status"] == "degraded"
            assert "warnings" in health
            assert any("Failed prompt validation" in warning for warning in health["warnings"])
            assert "invalid_prompt" in str(health["warnings"])
class TestSchemaValidationEdgeCases:
    """Test schema validation edge cases and fallback paths."""
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_validate_schema_no_schema_file(self):
        """Test schema validation when schema file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PromptManager(prompts_base_path=Path(temp_dir))
            # Test data
            test_data = {"test": "data"}
            # Should not raise exception when schema file missing
            await manager._validate_prompt_schema(test_data, "nonexistent_schema")
            # Should log warning but continue
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_validate_schema_json_load_error(self):
        """Test schema validation with malformed JSON schema file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            schemas_dir = prompts_dir / "schemas"
            schemas_dir.mkdir(parents=True)
            # Create malformed JSON schema
            schema_file = schemas_dir / "system_instructions_schema.json"
            schema_file.write_text("{invalid json content}")
            manager = PromptManager(prompts_base_path=prompts_dir)
            with pytest.raises(PromptValidationError) as exc_info:
                await manager._validate_prompt_schema({"test": "data"}, "system_instructions")
            assert "Schema validation error" in str(exc_info.value)
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_validate_schema_jsonschema_validation_error(self):
        """Test jsonschema ValidationError handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            schemas_dir = prompts_dir / "schemas"
            schemas_dir.mkdir(parents=True)
            # Create valid JSON schema that will fail validation
            schema_file = schemas_dir / "system_instructions_schema.json"
            schema_file.write_text("""
{
    "type": "object",
    "required": ["required_field"],
    "properties": {
        "required_field": {"type": "string"}
    }
}
""")
            manager = PromptManager(prompts_base_path=prompts_dir)
            # Data missing required field
            invalid_data = {"other_field": "value"}
            with pytest.raises(PromptValidationError) as exc_info:
                await manager._validate_prompt_schema(invalid_data, "system_instructions")
            assert "Schema validation failed" in str(exc_info.value)
class TestTemplateLoadingEdgeCases:
    """Test template loading edge cases."""
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_load_template_missing_template_field(self):
        """Test loading template without 'template' field."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            # Create template directory
            template_dir = prompts_dir / "test_prompt"
            template_dir.mkdir(parents=True)
            # Create template file without 'template' field
            template_file = template_dir / "test_template.yaml"
            template_file.write_text("""
template_version: "1.0.0"
variables:
  name: "Test variable"
""")
            manager = PromptManager(prompts_base_path=prompts_dir)
            with pytest.raises(PromptValidationError) as exc_info:
                await manager.load_template("test_prompt", "test_template")
            assert "missing 'template' field" in str(exc_info.value)
class TestCacheEdgeCases:
    """Test cache-related edge cases."""
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_specific_cache_clearing_no_matching_keys(self):
        """Test clearing cache for prompt with no cached items."""
        manager = PromptManager()
        # Clear cache for non-existent prompt should not raise error
        manager.clear_cache("nonexistent_prompt")
        # Should log info but not cause issues
        assert len(manager._cached_prompts) == 0



    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_file_modification_tracking_file_deleted(self):
        """Test file modification tracking when file is deleted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PromptManager(
                prompts_base_path=Path(temp_dir),
                enable_hot_reload=True
            )
            # Add file to modification tracking
            test_file = Path(temp_dir) / "test.yaml"
            test_file.touch()
            manager._file_modification_times[test_file] = test_file.stat().st_mtime
            # Delete the file
            test_file.unlink()
            # Should handle missing file gracefully in cache validation
            cache_key = "test_key"
            result = manager._is_cache_valid(cache_key, "test_prompt")
            assert result is False  # Should be false since key not in cache
class TestMemoryEdgeCases:
    """Test memory monitoring edge cases."""
    @pytest.mark.prompt
    @pytest.mark.medium
    @pytest.mark.unit

    @pytest.mark.fast
    def test_memory_statistics_with_large_cache(self):
        """Test memory statistics calculation with substantial cache data."""
        manager = PromptManager()
        # Simulate large cache data (smaller but more realistic size)
        large_data = {"large_content": "x" * 1000}  # 1KB of data per item
        for i in range(10):
            cache_key = f"large_prompt_{i}"
            manager._cached_prompts[cache_key] = large_data
            manager._cache_timestamps[cache_key] = datetime.now(timezone.utc)
        memory_stats = manager.get_memory_statistics()
        # Should report cache usage (adjusted expectations)
        assert memory_stats["cache_memory_usage"]["total_cache_size_mb"] > 0
        assert memory_stats["cache_memory_usage"]["total_prompt_data_size_bytes"] > 1000  # > 1KB
class TestValidationAllPromptsEdgeCases:
    """Test validate_all_prompts edge cases."""
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_validate_all_prompts_permission_error(self):
        """Test validate_all_prompts with directory permission error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PromptManager(prompts_base_path=Path(temp_dir))
            with patch.object(Path, 'iterdir', side_effect=PermissionError("Access denied")):
                with pytest.raises(PromptValidationError) as exc_info:
                    await manager.validate_all_prompts()
                assert "Validation process failed" in str(exc_info.value)
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_validate_all_prompts_with_invalid_directory_names(self):
        """Test validation skipping directories with invalid names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir)
            # Create directory with valid name
            valid_dir = prompts_dir / "valid_prompt"
            valid_dir.mkdir()
            valid_config = valid_dir / "system_instructions.yaml"
            valid_config.write_text("""
agent_config:
  name: "test"
  description: "test description"  
  version: "1.0.0"
system_instructions: |
  Test instructions
  INTENT CATEGORIES TO CLASSIFY:
  1. POSITIVE - Test
  CONFIDENCE SCORING GUIDELINES:
  - High confidence (0.85-0.99): Clear
  RESPONSE FORMAT:
  JSON format required
""")
            # Create directory with dangerous name (should be skipped)
            try:
                dangerous_dir = prompts_dir / "../dangerous"
                dangerous_dir.mkdir()
                dangerous_config = dangerous_dir / "system_instructions.yaml"
                dangerous_config.write_text("test: data")
            except OSError:
                # If we can't create the dangerous directory, create a different invalid one
                dangerous_dir = prompts_dir / "dir with spaces"
                dangerous_dir.mkdir()
            manager = PromptManager(prompts_base_path=prompts_dir)
            results = await manager.validate_all_prompts()
            # Should only validate the valid prompt
            assert "valid_prompt" in results
            # Should not include dangerous directory names
            for prompt_name in results.keys():
                # All validated prompts should have valid names
                assert "/" not in prompt_name
                assert ".." not in prompt_name
class TestCircuitBreakerIntegrationEdgeCases:
    """Test circuit breaker integration edge cases."""
    @pytest.mark.slow
    @pytest.mark.edge_case
    @pytest.mark.prompt
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    async def test_circuit_breaker_rejection_not_recorded_as_failure(self):
        """Test that circuit breaker rejections don't count as failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PromptManager(
                prompts_base_path=Path(temp_dir),
                enable_circuit_breaker=True,
                circuit_breaker_failure_threshold=2
            )
            # Force circuit breaker to open state
            manager.circuit_breaker.state = CircuitBreakerState.OPEN
            initial_failure_count = manager.circuit_breaker.failure_count
            # This should raise PromptCacheError due to circuit breaker
            with pytest.raises(PromptCacheError) as exc_info:
                await manager.load_prompt_config("test_prompt")
            assert "Circuit breaker is open" in str(exc_info.value)
            # Failure count should not increase (circuit breaker rejection doesn't count)
            assert manager.circuit_breaker.failure_count == initial_failure_count
# Additional utility tests for complete coverage
class TestUtilityFunctions:
    """Test utility functions and edge cases."""
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.prompt
    @pytest.mark.fast
    @pytest.mark.edge_case
    def test_safe_yaml_load_memory_error(self):
        """Test _safe_yaml_load with memory error."""
        manager = PromptManager()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("test: data")
            temp_path = Path(f.name)
        try:
            with patch('builtins.open', side_effect=MemoryError("Out of memory")):
                with pytest.raises(PromptValidationError) as exc_info:
                    manager._safe_yaml_load(temp_path)
                assert "File too large to process" in str(exc_info.value)
        finally:
            temp_path.unlink()



    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.edge_case
    @pytest.mark.fast
    def test_safe_yaml_load_unicode_decode_error(self):
        """Test _safe_yaml_load with unicode decode error."""
        manager = PromptManager()
        # Create file with invalid UTF-8
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.yaml', delete=False) as f:
            f.write(b'\xff\xfe\x00\x00invalid utf-8 content')
            temp_path = Path(f.name)
        try:
            with pytest.raises(PromptValidationError) as exc_info:
                manager._safe_yaml_load(temp_path)
            assert "File encoding error" in str(exc_info.value)
        finally:
            temp_path.unlink()
# Run additional edge case tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])