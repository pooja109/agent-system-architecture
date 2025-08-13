"""
Performance Optimizer - Caching and Performance Optimization
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json


class CacheManager:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self.cache = {}
        self.default_ttl = default_ttl
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function name and arguments."""
        # Create a hashable representation of arguments
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        
        # Create hash of the serialized data
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self.cache:
            value, expiry = self.cache[key]
            if datetime.now() < expiry:
                return value
            else:
                # Remove expired entry
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self.default_ttl
        expiry = datetime.now() + timedelta(seconds=ttl)
        self.cache[key] = (value, expiry)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        now = datetime.now()
        expired_keys = [k for k, (_, expiry) in self.cache.items() if now >= expiry]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


class PerformanceOptimizer:
    """Handles caching and performance optimization."""
    
    def __init__(self):
        self.cache = CacheManager()
        self.performance_metrics = {}
        self.operation_counts = {}
    
    def cached(self, ttl: int = 300):
        """Decorator for caching function results."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.cache._generate_key(func.__name__, args, kwargs)
                
                # Try to get from cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self._record_cache_hit(func.__name__)
                    return cached_result
                
                # Execute function and cache result
                start_time = time.time()
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Cache the result
                self.cache.set(cache_key, result, ttl)
                
                # Record metrics
                self._record_cache_miss(func.__name__)
                self._record_performance(func.__name__, duration)
                
                return result
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.cache._generate_key(func.__name__, args, kwargs)
                
                # Try to get from cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self._record_cache_hit(func.__name__)
                    return cached_result
                
                # Execute function and cache result
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Cache the result
                self.cache.set(cache_key, result, ttl)
                
                # Record metrics
                self._record_cache_miss(func.__name__)
                self._record_performance(func.__name__, duration)
                
                return result
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def timed(self, func):
        """Decorator for timing function execution."""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                self._record_performance(func.__name__, duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                self._record_performance(func.__name__, duration)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    def _record_cache_hit(self, func_name: str):
        """Record cache hit."""
        if func_name not in self.operation_counts:
            self.operation_counts[func_name] = {'hits': 0, 'misses': 0}
        self.operation_counts[func_name]['hits'] += 1
    
    def _record_cache_miss(self, func_name: str):
        """Record cache miss."""
        if func_name not in self.operation_counts:
            self.operation_counts[func_name] = {'hits': 0, 'misses': 0}
        self.operation_counts[func_name]['misses'] += 1
    
    def _record_performance(self, func_name: str, duration: float):
        """Record performance metrics."""
        if func_name not in self.performance_metrics:
            self.performance_metrics[func_name] = {
                'total_time': 0,
                'call_count': 0,
                'min_time': float('inf'),
                'max_time': 0
            }
        
        metrics = self.performance_metrics[func_name]
        metrics['total_time'] += duration
        metrics['call_count'] += 1
        metrics['min_time'] = min(metrics['min_time'], duration)
        metrics['max_time'] = max(metrics['max_time'], duration)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        report = {
            'cache_stats': self._generate_cache_stats(),
            'performance_stats': self._generate_performance_stats(),
            'recommendations': self._generate_recommendations()
        }
        return report
    
    def _generate_cache_stats(self) -> Dict[str, Any]:
        """Generate cache statistics."""
        total_hits = sum(counts['hits'] for counts in self.operation_counts.values())
        total_requests = sum(counts['hits'] + counts['misses'] for counts in self.operation_counts.values())
        
        cache_stats = {
            'total_entries': len(self.cache.cache),
            'total_requests': total_requests,
            'total_hits': total_hits,
            'hit_rate': (total_hits / max(total_requests, 1)) * 100,
            'by_function': {}
        }
        
        for func_name, counts in self.operation_counts.items():
            total = counts['hits'] + counts['misses']
            if total > 0:
                cache_stats['by_function'][func_name] = {
                    'hits': counts['hits'],
                    'misses': counts['misses'],
                    'hit_rate': (counts['hits'] / total) * 100
                }
        
        return cache_stats
    
    def _generate_performance_stats(self) -> Dict[str, Any]:
        """Generate performance statistics."""
        performance_stats = {}
        
        for func_name, metrics in self.performance_metrics.items():
            if metrics['call_count'] > 0:
                avg_time = metrics['total_time'] / metrics['call_count']
                performance_stats[func_name] = {
                    'call_count': metrics['call_count'],
                    'total_time': round(metrics['total_time'], 4),
                    'avg_time': round(avg_time, 4),
                    'min_time': round(metrics['min_time'], 4),
                    'max_time': round(metrics['max_time'], 4)
                }
        
        return performance_stats
    
    def _generate_recommendations(self) -> list[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        # Check cache hit rates
        for func_name, counts in self.operation_counts.items():
            total = counts['hits'] + counts['misses']
            if total > 0:
                hit_rate = (counts['hits'] / total) * 100
                if hit_rate < 50 and total > 10:
                    recommendations.append(
                        f"Consider increasing cache TTL for {func_name} (hit rate: {hit_rate:.1f}%)"
                    )
        
        # Check performance
        for func_name, metrics in self.performance_metrics.items():
            if metrics['call_count'] > 0:
                avg_time = metrics['total_time'] / metrics['call_count']
                if avg_time > 1.0:
                    recommendations.append(
                        f"{func_name} is slow (avg: {avg_time:.2f}s) - consider optimization"
                    )
        
        if not recommendations:
            recommendations.append("Performance looks good! No specific recommendations.")
        
        return recommendations
    
    def clear_metrics(self):
        """Clear all performance metrics and cache."""
        self.cache.clear()
        self.performance_metrics.clear()
        self.operation_counts.clear()
    
    def cleanup_cache(self) -> int:
        """Clean up expired cache entries."""
        return self.cache.cleanup_expired()


# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()

# Convenience decorators
cached = performance_optimizer.cached
timed = performance_optimizer.timed


def optimize_mock_services(mock_services):
    """Apply caching to mock services for better performance."""
    # Cache classification results
    if hasattr(mock_services, 'classify_email'):
        original_classify = mock_services.classify_email
        mock_services.classify_email = cached(ttl=600)(original_classify)
    
    # Cache contact lookup results
    if hasattr(mock_services, 'lookup_contact'):
        original_lookup = mock_services.lookup_contact
        mock_services.lookup_contact = cached(ttl=300)(original_lookup)
    
    # Cache case creation (in case of identical requests)
    if hasattr(mock_services, 'create_case'):
        original_create_case = mock_services.create_case
        mock_services.create_case = cached(ttl=60)(original_create_case)
    
    return mock_services


def get_performance_summary() -> Dict[str, Any]:
    """Get current performance summary."""
    return performance_optimizer.get_performance_report()