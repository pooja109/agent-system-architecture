"""
Import performance optimization for faster test execution.

This module provides import caching and optimization to reduce test startup time
and prevent slow imports from affecting test performance.
"""
import sys
import importlib
import time
import threading
from typing import Dict, Any, Optional, Set, List, Tuple
from contextlib import contextmanager
import weakref


class ImportCache:
    """Cache frequently imported modules for performance."""
    
    def __init__(self):
        self._module_cache: Dict[str, Any] = {}
        self._import_times: Dict[str, float] = {}
        self._failed_imports: Set[str] = set()
        self._lock = threading.Lock()
        self._preload_completed = False
    
    def cached_import(self, module_name: str, force_reload: bool = False):
        """Import module with caching."""
        with self._lock:
            if force_reload or module_name not in self._module_cache:
                start_time = time.perf_counter()
                
                try:
                    if module_name in sys.modules and force_reload:
                        importlib.reload(sys.modules[module_name])
                        module = sys.modules[module_name]
                    else:
                        module = importlib.import_module(module_name)
                    
                    self._module_cache[module_name] = module
                    import_time = time.perf_counter() - start_time
                    self._import_times[module_name] = import_time
                    
                    # Remove from failed imports if it was there
                    self._failed_imports.discard(module_name)
                    
                except ImportError as e:
                    # Cache import failures to avoid repeated attempts
                    self._module_cache[module_name] = e
                    self._failed_imports.add(module_name)
                    import_time = time.perf_counter() - start_time
                    self._import_times[module_name] = import_time
                    raise
            
            cached_result = self._module_cache[module_name]
            if isinstance(cached_result, Exception):
                raise cached_result
            
            return cached_result
    
    def preload_common_modules(self):
        """Pre-load commonly used modules for better performance."""
        if self._preload_completed:
            return
        
        common_modules = [
            # Standard library modules
            'unittest.mock',
            'pytest',
            'json',
            'datetime',
            'asyncio',
            'logging',
            'typing',
            'pathlib',
            'dataclasses',
            'contextlib',
            'threading',
            'time',
            'os',
            'sys',
            'tempfile',
            'subprocess',
            
            # Testing modules
            'unittest',
            'collections',
            'functools',
            'itertools',
            
            # Common third-party modules (if available)
            'psutil',
            'yaml'
        ]
        
        preload_start = time.perf_counter()
        loaded_count = 0
        
        for module_name in common_modules:
            try:
                self.cached_import(module_name)
                loaded_count += 1
            except ImportError:
                # Skip modules that aren't available
                pass
        
        preload_time = time.perf_counter() - preload_start
        self._import_times['__preload_session__'] = preload_time
        self._preload_completed = True
        
        return {
            'preload_time': preload_time,
            'modules_loaded': loaded_count,
            'modules_attempted': len(common_modules)
        }
    
    def preload_project_modules(self):
        """Pre-load project-specific modules."""
        project_modules = [
            # Core service modules
            'services.email_processor',
            'services.graph_api_client', 
            'services.azure_ai_foundry_client',
            'services.salesforce_client',
            'services.monitor',
            'services.round_robin_service',
            'services.contact_lookup_service',
            'services.response_handler',
            
            # Model modules
            'models.email',
            'models.settings',
            
            # Utility modules
            'utils.retry'
        ]
        
        loaded_count = 0
        failed_imports = []
        
        for module_name in project_modules:
            try:
                self.cached_import(module_name)
                loaded_count += 1
            except ImportError as e:
                failed_imports.append((module_name, str(e)))
        
        return {
            'modules_loaded': loaded_count,
            'modules_attempted': len(project_modules),
            'failed_imports': failed_imports
        }
    
    def get_import_stats(self) -> Dict[str, float]:
        """Get import timing statistics."""
        with self._lock:
            return self._import_times.copy()
    
    def get_slow_imports(self, threshold_ms: float = 100.0) -> List[Tuple[str, float]]:
        """Get list of imports that exceed time threshold."""
        with self._lock:
            slow_imports = []
            for module_name, import_time in self._import_times.items():
                if import_time * 1000 > threshold_ms:  # Convert to ms
                    slow_imports.append((module_name, import_time))
            
            return sorted(slow_imports, key=lambda x: x[1], reverse=True)
    
    def clear_cache(self):
        """Clear import cache."""
        with self._lock:
            self._module_cache.clear()
            self._import_times.clear()
            self._failed_imports.clear()
            self._preload_completed = False
    
    def get_cache_size(self) -> int:
        """Get number of cached modules."""
        return len(self._module_cache)


class LazyImporter:
    """Lazy import wrapper for expensive modules."""
    
    def __init__(self, module_name: str, import_cache: ImportCache = None):
        self.module_name = module_name
        self.import_cache = import_cache or _global_import_cache
        self._module = None
        self._import_attempted = False
    
    def __getattr__(self, name):
        """Lazy load module on first attribute access."""
        if not self._import_attempted:
            self._import_attempted = True
            try:
                self._module = self.import_cache.cached_import(self.module_name)
            except ImportError:
                self._module = None
                raise
        
        if self._module is None:
            raise ImportError(f"Module {self.module_name} could not be imported")
        
        return getattr(self._module, name)
    
    def __call__(self, *args, **kwargs):
        """Support calling the module if it's callable."""
        if not self._import_attempted:
            self._import_attempted = True
            self._module = self.import_cache.cached_import(self.module_name)
        
        return self._module(*args, **kwargs)


# Global import cache
_global_import_cache = ImportCache()


class ImportPerformanceMonitor:
    """Monitor import performance during test execution."""
    
    def __init__(self):
        self.import_times: List[Tuple[str, float]] = []
        self.monitoring = False
        self.original_import = None
    
    def start_monitoring(self):
        """Start monitoring import performance."""
        if self.monitoring:
            return
        
        self.original_import = __builtins__.__import__
        self.import_times.clear()
        
        def monitored_import(name, globals=None, locals=None, fromlist=(), level=0):
            start_time = time.perf_counter()
            try:
                result = self.original_import(name, globals, locals, fromlist, level)
                import_time = time.perf_counter() - start_time
                self.import_times.append((name, import_time))
                return result
            except ImportError:
                import_time = time.perf_counter() - start_time
                self.import_times.append((f"{name} (FAILED)", import_time))
                raise
        
        __builtins__.__import__ = monitored_import
        self.monitoring = True
    
    def stop_monitoring(self):
        """Stop monitoring import performance."""
        if not self.monitoring or not self.original_import:
            return
        
        __builtins__.__import__ = self.original_import
        self.monitoring = False
    
    def get_import_report(self) -> Dict[str, Any]:
        """Get import performance report."""
        if not self.import_times:
            return {}
        
        total_time = sum(time for _, time in self.import_times)
        slow_imports = [(name, time) for name, time in self.import_times if time > 0.1]  # >100ms
        
        return {
            'total_imports': len(self.import_times),
            'total_import_time': total_time,
            'average_import_time': total_time / len(self.import_times),
            'slow_imports': sorted(slow_imports, key=lambda x: x[1], reverse=True),
            'fastest_import': min(self.import_times, key=lambda x: x[1]),
            'slowest_import': max(self.import_times, key=lambda x: x[1])
        }
    
    @contextmanager
    def monitor(self):
        """Context manager for import monitoring."""
        self.start_monitoring()
        try:
            yield self
        finally:
            self.stop_monitoring()


@contextmanager
def fast_imports():
    """Context manager for optimized imports."""
    preload_stats = _global_import_cache.preload_common_modules()
    yield _global_import_cache, preload_stats


@contextmanager
def lazy_import_context():
    """Context manager that provides lazy importing capabilities."""
    
    class LazyImportProvider:
        def __init__(self, cache):
            self.cache = cache
        
        def lazy(self, module_name: str):
            return LazyImporter(module_name, self.cache)
        
        def preload_project(self):
            return self.cache.preload_project_modules()
    
    provider = LazyImportProvider(_global_import_cache)
    yield provider


# Pre-configured lazy imports for common expensive modules
def get_azure_client_lazy():
    """Get lazy importer for Azure client."""
    return LazyImporter('services.azure_ai_foundry_client')


def get_graph_client_lazy():
    """Get lazy importer for Graph API client."""
    return LazyImporter('services.graph_api_client')


def get_salesforce_client_lazy():
    """Get lazy importer for Salesforce client."""
    return LazyImporter('services.salesforce_client')


# Import performance validation
def assert_import_performance(import_stats: Dict[str, float], 
                            max_individual_time_ms: float = 100.0,
                            max_total_time_s: float = 10.0):
    """Assert import performance meets requirements."""
    total_time = sum(import_stats.values())
    slow_imports = [(name, time) for name, time in import_stats.items() 
                   if time * 1000 > max_individual_time_ms]
    
    assert total_time < max_total_time_s, \
        f"Total import time {total_time:.2f}s exceeds limit {max_total_time_s}s"
    
    if slow_imports:
        slow_list = ', '.join(f"{name}: {time*1000:.1f}ms" for name, time in slow_imports[:3])
        assert False, f"Slow imports detected: {slow_list}"


def validate_tiered_import_limits(import_stats: Dict[str, float]):
    """Validate imports meet tiered performance limits."""
    for module_name, import_time in import_stats.items():
        time_ms = import_time * 1000
        
        # Tiered limits: Azure SDK modules get 2000ms, our modules get 100ms
        if any(keyword in module_name.lower() for keyword in ['azure', 'openai', 'graph']):
            max_time_ms = 2000  # 2000ms for Azure/external modules
        else:
            max_time_ms = 100   # 100ms for our own modules
        
        assert time_ms < max_time_ms, \
            f"Module {module_name} import time {time_ms:.1f}ms exceeds limit {max_time_ms}ms"


# Session-level preloading
def initialize_import_cache():
    """Initialize import cache at session start."""
    return _global_import_cache.preload_common_modules()


# Pre-load common modules at module import time for session-wide benefit
try:
    _preload_stats = _global_import_cache.preload_common_modules()
except Exception:
    # Don't fail module import if preloading fails
    _preload_stats = {}


# Export for use in tests
__all__ = [
    'ImportCache', 'LazyImporter', 'ImportPerformanceMonitor',
    'fast_imports', 'lazy_import_context', 
    'get_azure_client_lazy', 'get_graph_client_lazy', 'get_salesforce_client_lazy',
    'assert_import_performance', 'validate_tiered_import_limits',
    '_global_import_cache'
]