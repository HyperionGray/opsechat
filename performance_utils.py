"""
Performance optimization utilities for opsechat
Implements caching and performance monitoring as recommended by Amazon Q Code Review
"""

from functools import lru_cache, wraps
import time
import logging
from typing import Dict, Any, Callable, Optional

# Configure performance logger
perf_logger = logging.getLogger('opsechat.performance')
perf_logger.setLevel(logging.INFO)

# Global cache invalidation tracking
_cache_invalidation_times = {}

class PerformanceCache:
    """
    Intelligent caching system for opsechat with automatic invalidation
    """
    
    def __init__(self):
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache performance statistics"""
        return self._cache_stats.copy()
    
    def invalidate_cache(self, cache_key: str):
        """Invalidate specific cache entry"""
        _cache_invalidation_times[cache_key] = time.time()
        self._cache_stats['invalidations'] += 1
        perf_logger.debug(f"Cache invalidated for key: {cache_key}")

# Global performance cache instance
performance_cache = PerformanceCache()

def cached_with_invalidation(cache_key: str, maxsize: int = 128, ttl: Optional[int] = None):
    """
    Decorator for caching function results with manual invalidation support
    
    Args:
        cache_key: Unique key for this cache
        maxsize: Maximum cache size (default 128)
        ttl: Time to live in seconds (optional)
    """
    def decorator(func: Callable) -> Callable:
        # Create LRU cache for the function
        cached_func = lru_cache(maxsize=maxsize)(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if cache should be invalidated
            if cache_key in _cache_invalidation_times:
                # Clear cache and remove invalidation marker
                cached_func.cache_clear()
                del _cache_invalidation_times[cache_key]
                performance_cache._cache_stats['invalidations'] += 1
            
            # Check TTL if specified
            if ttl and hasattr(wrapper, '_last_cache_time'):
                if time.time() - wrapper._last_cache_time > ttl:
                    cached_func.cache_clear()
                    wrapper._last_cache_time = time.time()
            
            # Get cache info before call
            cache_info_before = cached_func.cache_info()
            
            # Call the cached function
            result = cached_func(*args, **kwargs)
            
            # Update cache statistics
            cache_info_after = cached_func.cache_info()
            if cache_info_after.hits > cache_info_before.hits:
                performance_cache._cache_stats['hits'] += 1
            else:
                performance_cache._cache_stats['misses'] += 1
            
            # Set cache time for TTL tracking
            if ttl and not hasattr(wrapper, '_last_cache_time'):
                wrapper._last_cache_time = time.time()
            
            return result
        
        # Add cache management methods
        wrapper.cache_clear = cached_func.cache_clear
        wrapper.cache_info = cached_func.cache_info
        wrapper.invalidate = lambda: performance_cache.invalidate_cache(cache_key)
        
        return wrapper
    return decorator

def performance_monitor(operation_name: str):
    """
    Decorator to monitor function performance
    
    Args:
        operation_name: Name of the operation for logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log performance metrics
                perf_logger.info(f"{operation_name} completed in {execution_time:.3f}s")
                
                # Log slow operations (>1 second)
                if execution_time > 1.0:
                    perf_logger.warning(f"Slow operation detected: {operation_name} took {execution_time:.3f}s")
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                perf_logger.error(f"{operation_name} failed after {execution_time:.3f}s: {str(e)}")
                raise
        
        return wrapper
    return decorator

def memoize_with_expiry(expiry_seconds: int = 300):
    """
    Memoization decorator with automatic expiry
    
    Args:
        expiry_seconds: Cache expiry time in seconds (default 5 minutes)
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from arguments
            key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # Check if we have a cached result that hasn't expired
            if key in cache:
                result, timestamp = cache[key]
                if current_time - timestamp < expiry_seconds:
                    performance_cache._cache_stats['hits'] += 1
                    return result
                else:
                    # Remove expired entry
                    del cache[key]
            
            # Compute new result
            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            performance_cache._cache_stats['misses'] += 1
            
            return result
        
        # Add cache management
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_size = lambda: len(cache)
        
        return wrapper
    return decorator

class PerformanceMetrics:
    """
    Collect and report performance metrics
    """
    
    def __init__(self):
        self._metrics = {
            'request_count': 0,
            'total_response_time': 0.0,
            'slow_requests': 0,
            'error_count': 0
        }
    
    def record_request(self, response_time: float, error: bool = False):
        """Record a request's performance metrics"""
        self._metrics['request_count'] += 1
        self._metrics['total_response_time'] += response_time
        
        if response_time > 1.0:  # Slow request threshold
            self._metrics['slow_requests'] += 1
        
        if error:
            self._metrics['error_count'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        metrics = self._metrics.copy()
        
        if metrics['request_count'] > 0:
            metrics['average_response_time'] = metrics['total_response_time'] / metrics['request_count']
            metrics['slow_request_percentage'] = (metrics['slow_requests'] / metrics['request_count']) * 100
            metrics['error_rate'] = (metrics['error_count'] / metrics['request_count']) * 100
        else:
            metrics['average_response_time'] = 0.0
            metrics['slow_request_percentage'] = 0.0
            metrics['error_rate'] = 0.0
        
        # Add cache statistics
        metrics['cache_stats'] = performance_cache.get_stats()
        
        return metrics
    
    def reset_metrics(self):
        """Reset all performance metrics"""
        self._metrics = {
            'request_count': 0,
            'total_response_time': 0.0,
            'slow_requests': 0,
            'error_count': 0
        }

# Global performance metrics instance
performance_metrics = PerformanceMetrics()

def get_performance_report() -> Dict[str, Any]:
    """
    Generate comprehensive performance report
    """
    return {
        'timestamp': time.time(),
        'metrics': performance_metrics.get_metrics(),
        'cache_performance': performance_cache.get_stats(),
        'system_info': {
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'platform': sys.platform
        }
    }

# Import sys for system info
import sys