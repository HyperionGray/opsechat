"""
Performance-optimized review system functions
Implements caching as recommended by Amazon Q Code Review
"""

import datetime
from functools import lru_cache
import time
from typing import Dict, List

# Cache for review statistics
_review_stats_cache = None
_review_stats_cache_time = 0
_cache_ttl = 60  # Cache for 60 seconds
_review_user_count_by_hash: Dict[int, Dict[str, int]] = {}
_review_hash_order: List[int] = []
_review_hash_cache_limit = 32

def invalidate_review_cache():
    """Invalidate the review statistics cache"""
    global _review_stats_cache, _review_stats_cache_time
    global _review_user_count_by_hash, _review_hash_order
    _review_stats_cache = None
    _review_stats_cache_time = 0
    _review_user_count_by_hash = {}
    _review_hash_order = []
    # Safe to clear here because the function is called after module import.
    try:
        get_user_review_count.cache_clear()
    except NameError:
        pass

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
    if user_id is None:
        return 0
    review_counts = _review_user_count_by_hash.get(reviews_hash, {})
    return review_counts.get(str(user_id), 0)


def _build_user_review_counts(reviews):
    """Build user->review_count mapping for the supplied review list."""
    counts = {}
    for review in reviews:
        user_id = review.get("user_id")
        if user_id is None:
            continue
        user_key = str(user_id)
        counts[user_key] = counts.get(user_key, 0) + 1
    return counts


def _remember_review_counts(reviews_hash, review_counts):
    """Store user review count mappings with bounded in-memory retention."""
    if reviews_hash in _review_hash_order:
        _review_hash_order.remove(reviews_hash)
    _review_hash_order.append(reviews_hash)
    _review_user_count_by_hash[reviews_hash] = review_counts

    while len(_review_hash_order) > _review_hash_cache_limit:
        stale_hash = _review_hash_order.pop(0)
        _review_user_count_by_hash.pop(stale_hash, None)

def create_reviews_hash(reviews):
    """
    Create a hash of reviews for cache invalidation
    """
    if not reviews:
        reviews_hash = hash(())
        _remember_review_counts(reviews_hash, {})
        return reviews_hash

    review_counts = _build_user_review_counts(reviews)

    # Generate a deterministic signature that changes when per-user counts change.
    latest_timestamp = max(review["timestamp"] for review in reviews)
    signature = (
        len(reviews),
        latest_timestamp.isoformat(),
        tuple(sorted(review_counts.items())),
    )
    reviews_hash = hash(signature)
    _remember_review_counts(reviews_hash, review_counts)
    return reviews_hash

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