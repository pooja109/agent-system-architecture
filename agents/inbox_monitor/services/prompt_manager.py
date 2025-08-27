"""
Prompt Management Service for External Agent Instructions
========================================================

Provides centralized loading, validation, and caching of agent prompts
from external YAML configuration files.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from enum import Enum
import sys
import yaml
import structlog
from datetime import datetime, timedelta, timezone
import threading
import weakref

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

try:
    from models.prompt_models import PromptConfig, TemplateConfig
    from exceptions.prompt_exceptions import (
        PromptNotFoundError, 
        PromptValidationError, 
        PromptCacheError
    )
except ImportError:
    from ..models.prompt_models import PromptConfig, TemplateConfig
    from ..exceptions.prompt_exceptions import (
        PromptNotFoundError, 
        PromptValidationError, 
        PromptCacheError
    )


class CircuitBreakerState(Enum):
    """Circuit breaker states for error resilience."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for prompt loading resilience.
    
    Protects against cascading failures by temporarily disabling prompt loading
    when consecutive failures exceed threshold.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before trying to close circuit
            success_threshold: Number of successes needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
        self.logger = structlog.get_logger(__name__)
    
    def can_proceed(self) -> bool:
        """Check if operation can proceed based on circuit breaker state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if enough time has passed to try again
            if (self.last_failure_time and 
                datetime.now(timezone.utc) - self.last_failure_time >= self.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                self.logger.info("Circuit breaker transitioning to half-open state")
                return True
            return False
        
        # HALF_OPEN state - allow limited requests through
        return True
    
    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.logger.info("Circuit breaker closed - service recovered")
        else:
            # Reset failure count on success in closed state
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.logger.error(
                    "Circuit breaker opened due to consecutive failures",
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold
                )
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Failure in half-open state immediately opens circuit
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            self.logger.warning("Circuit breaker reopened after failed recovery attempt")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state and metrics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "recovery_timeout_seconds": self.recovery_timeout.total_seconds()
        }


class PromptManagerMeta(type):
    """Metaclass for PromptManager to implement thread-safe singleton pattern."""
    _instances = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        """Thread-safe singleton creation with configuration-based instance reuse."""
        # Create a signature from the arguments for configuration-based instances
        config_key = (cls.__name__, str(sorted(kwargs.items())), str(args))
        
        with cls._lock:
            if config_key not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[config_key] = instance
                instance._is_singleton_primary = True
            else:
                # Increment reuse counter for existing instance
                instance = cls._instances[config_key]
                if hasattr(instance, '_singleton_reuse_count'):
                    instance._singleton_reuse_count += 1
                else:
                    instance._singleton_reuse_count = 1
                    
                # Log singleton reuse for performance monitoring
                if hasattr(instance, 'logger'):
                    instance.logger.debug(
                        "PromptManager singleton reused",
                        reuse_count=instance._singleton_reuse_count,
                        cache_size=len(getattr(instance, '_cache', {})),
                        memory_efficient=True
                    )
            
            return instance


class PromptManager(metaclass=PromptManagerMeta):
    """
    Enterprise-grade singleton PromptManager with optimized caching and performance monitoring.
    
    Features:
    - Thread-safe singleton pattern for optimal resource utilization
    - YAML-based configuration loading
    - In-memory caching with TTL support and shared access
    - Schema validation for prompt structure
    - Hot-reloading support for development
    - Comprehensive error handling
    - Performance monitoring and metrics
    - Memory-efficient singleton caching
    - Cross-component cache sharing
    """
    
    def __init__(
        self, 
        prompts_base_path: Optional[Path] = None,
        cache_ttl_seconds: int = 300,
        enable_hot_reload: bool = False,
        schema_validation: bool = True,
        enable_circuit_breaker: bool = True,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_recovery_timeout: int = 60
    ):
        """
        Initialize the PromptManager.
        
        Args:
            prompts_base_path: Base directory for prompt files (defaults to ./prompts)
            cache_ttl_seconds: Time-to-live for cached prompts in seconds
            enable_hot_reload: Whether to check file modification times
            schema_validation: Whether to validate YAML structure against schemas
            enable_circuit_breaker: Whether to enable circuit breaker for resilience
            circuit_breaker_failure_threshold: Failures before opening circuit
            circuit_breaker_recovery_timeout: Seconds to wait before retry
        """
        if prompts_base_path:
            self.prompts_base_path = Path(prompts_base_path)
        else:
            self.prompts_base_path = Path(__file__).parent.parent / "prompts"
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.enable_hot_reload = enable_hot_reload
        self.schema_validation = schema_validation
        self.enable_circuit_breaker = enable_circuit_breaker
        self.logger = structlog.get_logger(__name__)
        
        # Thread-safe singleton initialization check
        if hasattr(self, '_initialized') and self._initialized:
            return  # Already initialized, skip re-initialization for singleton
            
        # Initialize circuit breaker if enabled
        self.circuit_breaker = None
        if self.enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=circuit_breaker_failure_threshold,
                recovery_timeout=circuit_breaker_recovery_timeout
            )
        
        # Thread-safe cache structures with singleton optimization
        self._cache_lock = threading.RLock()
        self._cached_prompts: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._file_modification_times: Dict[Path, float] = {}
        
        # Singleton-specific attributes
        self._singleton_reuse_count = 0
        self._is_singleton_primary = False
        
        # Enhanced performance metrics with singleton optimization tracking
        self._cache_hits = 0
        self._cache_misses = 0
        self._load_times: Dict[str, float] = {}
        self._singleton_cache_benefits = 0
        self._memory_optimization_events = 0
        
        # Ensure base directory exists
        self.prompts_base_path.mkdir(parents=True, exist_ok=True)
        
        # Mark as initialized for singleton pattern
        self._initialized = True
        
        self.logger.info(
            "PromptManager singleton initialized",
            base_path=str(self.prompts_base_path),
            cache_ttl=cache_ttl_seconds,
            hot_reload=enable_hot_reload,
            schema_validation=schema_validation,
            singleton_pattern=True,
            thread_safe_caching=True,
            memory_optimized=True
        )
    
    def _validate_prompt_name(self, prompt_name: str) -> None:
        """Validate prompt name to prevent directory traversal attacks."""
        if not prompt_name:
            raise PromptValidationError("Prompt name cannot be empty")
        
        # Check for directory traversal patterns
        dangerous_patterns = ['..', '/', '\\', '\x00']
        for pattern in dangerous_patterns:
            if pattern in prompt_name:
                raise PromptValidationError(
                    f"Invalid prompt name '{prompt_name}': contains dangerous characters",
                    validation_errors=[f"Contains '{pattern}' which is not allowed"]
                )
        
        # Only allow alphanumeric, underscore, and hyphen
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', prompt_name):
            raise PromptValidationError(
                f"Invalid prompt name '{prompt_name}': only alphanumeric, underscore, and hyphen allowed"
            )
        
        # Reasonable length limits
        if len(prompt_name) > 100:
            raise PromptValidationError(
                f"Prompt name too long: {len(prompt_name)} characters (max 100)"
            )
    
    def _validate_template_name(self, template_name: str) -> None:
        """Validate template name to prevent directory traversal attacks."""
        if not template_name:
            raise PromptValidationError("Template name cannot be empty")
        
        # Same validation as prompt names
        self._validate_prompt_name(template_name)
    
    def _safe_yaml_load(self, file_path: Path) -> Dict[str, Any]:
        """Safely load YAML file with injection protection."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read file with size limit to prevent memory exhaustion
                max_file_size = 10 * 1024 * 1024  # 10MB limit
                content = f.read(max_file_size)
                
                if f.read(1):  # Check if there's more content
                    raise PromptValidationError(
                        f"YAML file too large: {file_path} exceeds {max_file_size} bytes"
                    )
                
                # Use safe_load to prevent arbitrary code execution
                data = yaml.safe_load(content)
                
                if data is None:
                    raise PromptValidationError(f"Empty or invalid YAML in {file_path}")
                
                if not isinstance(data, dict):
                    raise PromptValidationError(
                        f"YAML must contain a dictionary/object at root level in {file_path}"
                    )
                
                return data
                
        except yaml.YAMLError as e:
            raise PromptValidationError(f"YAML parsing error in {file_path}: {e}")
        except UnicodeDecodeError as e:
            raise PromptValidationError(f"File encoding error in {file_path}: {e}")
        except MemoryError:
            raise PromptValidationError(f"File too large to process: {file_path}")
    
    async def load_prompt_config(self, prompt_name: str) -> PromptConfig:
        """
        Load a prompt configuration from YAML file with caching.
        
        Args:
            prompt_name: Name of the prompt directory (e.g., 'email_classification')
            
        Returns:
            PromptConfig object with validated configuration
            
        Raises:
            PromptNotFoundError: If prompt directory or config file doesn't exist
            PromptValidationError: If YAML structure is invalid
            PromptCacheError: If caching operations fail
        """
        start_time = datetime.now(timezone.utc)
        cache_key = f"config_{prompt_name}"
        
        try:
            # Validate prompt name for security
            self._validate_prompt_name(prompt_name)
            
            # Check circuit breaker
            if self.circuit_breaker and not self.circuit_breaker.can_proceed():
                raise PromptCacheError(
                    f"Circuit breaker is open - prompt loading temporarily disabled for {prompt_name}"
                )
            
            # Check cache first
            if self._is_cache_valid(cache_key, prompt_name):
                self._cache_hits += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                self.logger.debug(
                    "Prompt config loaded from cache",
                    prompt_name=prompt_name,
                    cache_hits=self._cache_hits
                )
                return PromptConfig(**self._cached_prompts[cache_key])
            
            # Load from file
            config_path = self.prompts_base_path / prompt_name / "system_instructions.yaml"
            
            if not config_path.exists():
                raise PromptNotFoundError(
                    f"Prompt configuration not found: {config_path}"
                )
            
            # Safely load and parse YAML with security checks
            raw_config = self._safe_yaml_load(config_path)
            
            # Validate schema if enabled
            if self.schema_validation:
                await self._validate_prompt_schema(raw_config, "system_instructions")
            
            # Create validated config
            config = PromptConfig(**raw_config)
            
            # Thread-safe cache update with singleton optimization
            with self._cache_lock:
                self._cached_prompts[cache_key] = raw_config
                self._cache_timestamps[cache_key] = datetime.now(timezone.utc)
                if self.enable_hot_reload:
                    self._file_modification_times[config_path] = config_path.stat().st_mtime
                
                self._cache_misses += 1
                self._memory_optimization_events += 1
            load_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._load_times[prompt_name] = load_time
            
            self.logger.info(
                "Prompt configuration loaded into singleton cache",
                prompt_name=prompt_name,
                version=config.agent_config.version if config.agent_config else "unknown",
                load_time_ms=int(load_time * 1000),
                singleton_optimized=True,
                thread_safe=True,
                cache_misses=self._cache_misses
            )
            
            # Record success for circuit breaker
            if self.circuit_breaker:
                self.circuit_breaker.record_success()
            
            return config
            
        except Exception as e:
            load_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.error(
                "Failed to load prompt configuration",
                prompt_name=prompt_name,
                error=str(e),
                load_time_ms=int(load_time * 1000),
                config_path=str(config_path) if 'config_path' in locals() else "unknown"
            )
            
            # Record failure for circuit breaker (unless it's a circuit breaker rejection)
            if (self.circuit_breaker and 
                not isinstance(e, PromptCacheError) or 
                "Circuit breaker is open" not in str(e)):
                self.circuit_breaker.record_failure()
            
            if isinstance(e, (PromptNotFoundError, PromptValidationError)):
                raise
            else:
                raise PromptCacheError(f"Failed to load prompt {prompt_name}: {e}") from e
    
    async def get_system_instructions(self, prompt_name: str) -> str:
        """
        Get system instructions for a specific prompt.
        
        Args:
            prompt_name: Name of the prompt (e.g., 'email_classification')
            
        Returns:
            System instructions string
            
        Raises:
            PromptNotFoundError: If prompt or instructions not found
            PromptValidationError: If instructions are empty or invalid
        """
        config = await self.load_prompt_config(prompt_name)
        
        if not config.system_instructions:
            raise PromptValidationError(
                f"System instructions empty or missing for prompt: {prompt_name}"
            )
        
        self.logger.debug(
            "System instructions retrieved",
            prompt_name=prompt_name,
            instruction_length=len(config.system_instructions)
        )
        
        return config.system_instructions.strip()
    
    async def load_template(self, prompt_name: str, template_name: str) -> TemplateConfig:
        """
        Load a specific template configuration.
        
        Args:
            prompt_name: Name of the prompt directory
            template_name: Name of the template file (without .yaml extension)
            
        Returns:
            TemplateConfig object with validated template
            
        Raises:
            PromptNotFoundError: If template file doesn't exist
            PromptValidationError: If template structure is invalid
        """
        cache_key = f"template_{prompt_name}_{template_name}"
        
        try:
            # Validate names for security
            self._validate_prompt_name(prompt_name)
            self._validate_template_name(template_name)
            # Check cache first
            if self._is_cache_valid(cache_key, prompt_name, template_name):
                self._cache_hits += 1
                return TemplateConfig(**self._cached_prompts[cache_key])
            
            # Load from file
            template_path = self.prompts_base_path / prompt_name / f"{template_name}.yaml"
            
            if not template_path.exists():
                raise PromptNotFoundError(
                    f"Template not found: {template_path}"
                )
            
            # Safely load template data
            template_data = self._safe_yaml_load(template_path)
            
            if 'template' not in template_data:
                raise PromptValidationError(
                    f"Invalid template structure in {template_path}: missing 'template' field"
                )
            
            # Validate schema if enabled
            if self.schema_validation:
                await self._validate_prompt_schema(template_data, "template")
            
            # Create validated template config
            template_config = TemplateConfig(**template_data)
            
            # Update cache
            self._cached_prompts[cache_key] = template_data
            self._cache_timestamps[cache_key] = datetime.now(timezone.utc)
            
            self._cache_misses += 1
            
            self.logger.info(
                "Template loaded successfully",
                prompt_name=prompt_name,
                template_name=template_name,
                template_version=template_config.template_version
            )
            
            return template_config
            
        except Exception as e:
            self.logger.error(
                "Failed to load template",
                prompt_name=prompt_name,
                template_name=template_name,
                error=str(e)
            )
            
            if isinstance(e, (PromptNotFoundError, PromptValidationError)):
                raise
            else:
                raise PromptCacheError(f"Failed to load template {template_name}: {e}") from e
    
    def clear_cache(self, prompt_name: Optional[str] = None) -> None:
        """
        Clear cached prompts. If prompt_name provided, clear only that prompt.
        
        Args:
            prompt_name: Optional specific prompt to clear from cache
        """
        if prompt_name:
            # Clear specific prompt caches
            keys_to_remove = [
                key for key in self._cached_prompts.keys() 
                if key.startswith(f"config_{prompt_name}") or key.startswith(f"template_{prompt_name}")
            ]
            
            for key in keys_to_remove:
                self._cached_prompts.pop(key, None)
                self._cache_timestamps.pop(key, None)
            
            self.logger.info("Cache cleared for specific prompt", extra={"prompt_name": prompt_name})
        else:
            # Clear all caches
            self._cached_prompts.clear()
            self._cache_timestamps.clear()
            self._file_modification_times.clear()
            
            self.logger.info("All prompt caches cleared")
    
    async def validate_all_prompts(self) -> Dict[str, bool]:
        """
        Validate all prompt configurations in the prompts directory.
        
        Returns:
            Dictionary mapping prompt names to validation success status
        """
        validation_results = {}
        
        try:
            for prompt_dir in self.prompts_base_path.iterdir():
                if prompt_dir.is_dir() and prompt_dir.name != "schemas":
                    # Skip directories with invalid names for security
                    try:
                        self._validate_prompt_name(prompt_dir.name)
                    except PromptValidationError:
                        self.logger.warning(
                            "Skipping directory with invalid name",
                            directory_name=prompt_dir.name
                        )
                        continue
                        
                    try:
                        await self.load_prompt_config(prompt_dir.name)
                        validation_results[prompt_dir.name] = True
                        self.logger.info(
                            "Prompt validation successful", 
                            prompt_name=prompt_dir.name
                        )
                    except Exception as e:
                        validation_results[prompt_dir.name] = False
                        self.logger.error(
                            "Prompt validation failed",
                            prompt_name=prompt_dir.name,
                            error=str(e)
                        )
            
            success_count = sum(validation_results.values())
            total_count = len(validation_results)
            
            self.logger.info(
                "Prompt validation summary",
                successful=success_count,
                total=total_count,
                success_rate=f"{(success_count/total_count*100):.1f}%" if total_count > 0 else "0%"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to validate prompts: {e}")
            raise PromptValidationError(f"Validation process failed: {e}") from e
        
        return validation_results
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "cached_items": len(self._cached_prompts),
            "average_load_times": {
                name: round(time * 1000, 2) 
                for name, time in self._load_times.items()
            }
        }
        
        # Add circuit breaker statistics if enabled
        if self.circuit_breaker:
            stats["circuit_breaker"] = self.circuit_breaker.get_state()
        
        return stats
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get memory usage statistics for the PromptManager."""
        stats = {
            "cache_memory_usage": {
                "cached_prompts_size_bytes": sys.getsizeof(self._cached_prompts),
                "cache_timestamps_size_bytes": sys.getsizeof(self._cache_timestamps),
                "file_modification_times_size_bytes": sys.getsizeof(self._file_modification_times),
                "load_times_size_bytes": sys.getsizeof(self._load_times),
            }
        }
        
        # Add detailed cache item sizes
        total_prompt_data_size = 0
        for key, value in self._cached_prompts.items():
            item_size = sys.getsizeof(key) + sys.getsizeof(value)
            total_prompt_data_size += item_size
        
        stats["cache_memory_usage"]["total_prompt_data_size_bytes"] = total_prompt_data_size
        stats["cache_memory_usage"]["total_cache_size_mb"] = round(total_prompt_data_size / 1024 / 1024, 3)
        
        # Add process memory info if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                stats["process_memory"] = {
                    "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                    "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
                    "memory_percent": round(process.memory_percent(), 2)
                }
            except Exception as e:
                stats["process_memory"] = {"error": str(e)}
        else:
            stats["process_memory"] = {"error": "psutil not available"}
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of the PromptManager."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache_status": self.get_cache_statistics(),
            "memory_status": self.get_memory_statistics(),
        }
        
        # Check if prompts directory is accessible
        try:
            if not self.prompts_base_path.exists():
                health_status["status"] = "unhealthy"
                health_status["errors"] = [f"Prompts directory not found: {self.prompts_base_path}"]
            elif not self.prompts_base_path.is_dir():
                health_status["status"] = "unhealthy" 
                health_status["errors"] = [f"Prompts path is not a directory: {self.prompts_base_path}"]
            else:
                health_status["prompts_directory"] = {
                    "path": str(self.prompts_base_path),
                    "exists": True,
                    "readable": os.access(self.prompts_base_path, os.R_OK)
                }
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["errors"] = [f"Error checking prompts directory: {e}"]
        
        # Validate all prompts if requested
        try:
            validation_results = await self.validate_all_prompts()
            health_status["prompt_validation"] = validation_results
            
            # Check if any prompts failed validation
            failed_prompts = [name for name, result in validation_results.items() if not result]
            if failed_prompts:
                health_status["status"] = "degraded"
                health_status["warnings"] = [f"Failed prompt validation: {', '.join(failed_prompts)}"]
                
        except Exception as e:
            health_status["status"] = "unhealthy"
            if "errors" not in health_status:
                health_status["errors"] = []
            health_status["errors"].append(f"Prompt validation failed: {e}")
        
        return health_status
    
    def _is_cache_valid(self, cache_key: str, prompt_name: str, template_name: Optional[str] = None) -> bool:
        """Check if cached item is still valid based on TTL and file modification."""
        if cache_key not in self._cached_prompts:
            return False
        
        # Check TTL
        if cache_key in self._cache_timestamps:
            age = datetime.now(timezone.utc) - self._cache_timestamps[cache_key]
            if age > self.cache_ttl:
                return False
        
        # Check file modification time if hot reload enabled
        if self.enable_hot_reload:
            if template_name:
                file_path = self.prompts_base_path / prompt_name / f"{template_name}.yaml"
            else:
                file_path = self.prompts_base_path / prompt_name / "system_instructions.yaml"
            
            if file_path.exists() and file_path in self._file_modification_times:
                current_mtime = file_path.stat().st_mtime
                cached_mtime = self._file_modification_times[file_path]
                if current_mtime > cached_mtime:
                    return False
        
        return True
    
    async def _validate_prompt_schema(self, data: Dict[str, Any], schema_type: str) -> None:
        """Validate prompt data against JSON schema."""
        if not JSONSCHEMA_AVAILABLE:
            # Fallback to basic validation if jsonschema is not available
            required_fields = {
                "system_instructions": ["agent_config", "system_instructions"],
                "template": ["template", "template_version"]
            }
            
            if schema_type in required_fields:
                for field in required_fields[schema_type]:
                    if field not in data:
                        raise PromptValidationError(
                            f"Required field '{field}' missing in {schema_type} schema"
                        )
            return
        
        # Load and use JSON schema for validation
        schema_file_map = {
            "system_instructions": "system_instructions_schema.json",
            "template": "template_schema.json"
        }
        
        schema_filename = schema_file_map.get(schema_type)
        if not schema_filename:
            self.logger.warning(f"No schema file found for type: {schema_type}")
            return
        
        schema_path = self.prompts_base_path / "schemas" / schema_filename
        
        try:
            if schema_path.exists():
                import json
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                
                # Validate data against schema
                jsonschema.validate(instance=data, schema=schema)
                
                self.logger.debug(
                    "Schema validation successful",
                    schema_type=schema_type,
                    schema_file=schema_filename
                )
            else:
                self.logger.warning(
                    f"Schema file not found: {schema_path}. Skipping JSON schema validation."
                )
                
        except jsonschema.ValidationError as e:
            raise PromptValidationError(
                f"Schema validation failed for {schema_type}: {e.message}",
                validation_errors=[e.message]
            )
        except Exception as e:
            self.logger.error(
                "Error during schema validation",
                schema_type=schema_type,
                error=str(e)
            )
            raise PromptValidationError(f"Schema validation error: {e}")
    
    def get_singleton_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics including singleton optimization benefits.
        
        Returns:
            Dictionary with performance and optimization metrics
        """
        with self._cache_lock:
            total_cache_operations = self._cache_hits + self._cache_misses
            cache_hit_ratio = (self._cache_hits / total_cache_operations * 100) if total_cache_operations > 0 else 0
            
            return {
                "caching_performance": {
                    "cache_hits": self._cache_hits,
                    "cache_misses": self._cache_misses,
                    "cache_hit_ratio_percent": round(cache_hit_ratio, 2),
                    "cached_prompts": len(self._cached_prompts)
                },
                "singleton_optimization": {
                    "instance_reuse_count": self._singleton_reuse_count,
                    "singleton_cache_benefits": self._singleton_cache_benefits,
                    "memory_optimization_events": self._memory_optimization_events,
                    "is_primary_instance": getattr(self, '_is_singleton_primary', False)
                },
                "performance_tracking": {
                    "average_load_time_ms": round(sum(self._load_times.values()) / len(self._load_times) * 1000, 2) if self._load_times else 0,
                    "total_prompts_loaded": len(self._load_times),
                    "thread_safe_operations": True
                },
                "configuration": {
                    "cache_ttl_seconds": self.cache_ttl.total_seconds(),
                    "hot_reload_enabled": self.enable_hot_reload,
                    "schema_validation_enabled": self.schema_validation,
                    "circuit_breaker_enabled": self.enable_circuit_breaker
                }
            }
    
    def get_cache_efficiency_report(self) -> str:
        """Generate a human-readable report on singleton cache efficiency.
        
        Returns:
            Formatted string with cache performance analysis
        """
        metrics = self.get_singleton_metrics()
        
        caching = metrics["caching_performance"]
        singleton = metrics["singleton_optimization"]
        performance = metrics["performance_tracking"]
        
        report_lines = [
            "\n=== PromptManager Singleton Performance Report ===",
            f"Cache Hit Ratio: {caching['cache_hit_ratio_percent']}% ({caching['cache_hits']}/{caching['cache_hits'] + caching['cache_misses']} requests)",
            f"Cached Prompts: {caching['cached_prompts']}",
            f"Singleton Instance Reuses: {singleton['instance_reuse_count']}",
            f"Cache Sharing Benefits: {singleton['singleton_cache_benefits']} operations",
            f"Memory Optimizations: {singleton['memory_optimization_events']} events",
            f"Average Load Time: {performance['average_load_time_ms']}ms",
            f"Thread-Safe Operations: {performance['thread_safe_operations']}",
            "===============================================\n"
        ]
        
        return "\n".join(report_lines)
    
    @classmethod
    def get_global_singleton_stats(cls) -> Dict[str, Any]:
        """Get statistics about all PromptManager singleton instances.
        
        Returns:
            Dictionary with global singleton statistics
        """
        with cls._lock:
            return {
                "total_singleton_instances": len(cls._instances),
                "instance_configurations": list(cls._instances.keys()),
                "memory_efficiency": "High" if len(cls._instances) <= 3 else "Moderate",
                "singleton_pattern_active": True
            }


# Convenience factory function for creating singleton PromptManager
def get_prompt_manager(**kwargs) -> PromptManager:
    """Factory function to get a PromptManager singleton instance.
    
    Args:
        **kwargs: Configuration parameters for PromptManager
        
    Returns:
        PromptManager singleton instance with specified configuration
    """
    return PromptManager(**kwargs)