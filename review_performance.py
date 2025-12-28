"""
Performance-optimized review system functions
Implements caching as recommended by Amazon Q Code Review
"""

import datetime
from functools import lru_cache
import time

# Cache for review statistics
_review_stats_cache = None
_review_stats_cache_time = 0
_cache_ttl = 60  # Cache for 60 seconds

def invalidate_review_cache():
    """Invalidate the review statistics cache"""
    global _review_stats_cache, _review_stats_cache_time
    _review_stats_cache = None
    _review_stats_cache_time = 0

def get_cached_review_stats(reviews):
    """
    Get review statistics with caching
    Cache is invalidated after 60 seconds or when reviews are modified
    """
    global _review_stats_cache, _review_stats_cache_time
    
    current_time = time.time()
    
    # Check if cache is valid
    if (_review_stats_cache is not None and 
        current_time - _review_stats_cache_time < _cache_ttl):
        return _review_stats_cache
    
    # Calculate fresh statistics
    if not reviews:
        stats = {
            "total": 0,
            "average_rating": 0,
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        }
    else:
        total = len(reviews)
        total_rating = sum(review["rating"] for review in reviews)
        average_rating = round(total_rating / total, 1)
        
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            rating_distribution[review["rating"]] += 1
        
        stats = {
            "total": total,
            "average_rating": average_rating,
            "rating_distribution": rating_distribution
        }
    
    # Update cache
    _review_stats_cache = stats
    _review_stats_cache_time = current_time
    
    return stats

def optimized_cleanup_old_reviews(reviews, secs_to_live=86400):
    """
    Optimized cleanup function that tracks if cleanup is needed
    """
    if not reviews:
        return []
    
    current_time = datetime.datetime.now()
    
    # Use list comprehension for better performance
    cleaned_reviews = [
        review for review in reviews
        if (current_time - review["timestamp"]).total_seconds() < secs_to_live
    ]
    
    # If reviews were removed, invalidate cache
    if len(cleaned_reviews) != len(reviews):
        invalidate_review_cache()
    
    return cleaned_reviews

@lru_cache(maxsize=32)
def get_user_review_count(user_id, reviews_hash):
    """
    Get review count for a specific user (cached)
    reviews_hash is used to invalidate cache when reviews change
    """
    # This would need to be implemented with actual review data
    # For now, return 0 as placeholder
    return 0

def create_reviews_hash(reviews):
    """
    Create a hash of reviews for cache invalidation
    """
    if not reviews:
        return hash(())
    
    # Create hash based on review count and latest timestamp
    latest_timestamp = max(review["timestamp"] for review in reviews)
    return hash((len(reviews), latest_timestamp.isoformat()))

# Performance monitoring for review operations
class ReviewPerformanceMonitor:
    def __init__(self):
        self.stats = {
            'cleanup_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_cleanup_time': 0.0
        }
    
    def record_cleanup(self, execution_time):
        self.stats['cleanup_calls'] += 1
        self.stats['total_cleanup_time'] += execution_time
    
    def record_cache_hit(self):
        self.stats['cache_hits'] += 1
    
    def record_cache_miss(self):
        self.stats['cache_misses'] += 1
    
    def get_stats(self):
        stats = self.stats.copy()
        if stats['cleanup_calls'] > 0:
            stats['average_cleanup_time'] = stats['total_cleanup_time'] / stats['cleanup_calls']
        else:
            stats['average_cleanup_time'] = 0.0
        
        total_cache_requests = stats['cache_hits'] + stats['cache_misses']
        if total_cache_requests > 0:
            stats['cache_hit_rate'] = (stats['cache_hits'] / total_cache_requests) * 100
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats

# Global performance monitor
review_performance_monitor = ReviewPerformanceMonitor()