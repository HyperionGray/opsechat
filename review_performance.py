"""
Performance-optimized review system functions
Implements caching as recommended by Amazon Q Code Review
"""

import datetime
from functools import lru_cache
import time
from typing import Iterable, Tuple

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
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total_rating = 0
        valid_ratings = 0
        for review in reviews:
            try:
                rating = int(review.get("rating", 0))
            except (TypeError, ValueError):
                continue
            if rating < 1 or rating > 5:
                continue
            rating_distribution[rating] += 1
            total_rating += rating
            valid_ratings += 1

        total = valid_ratings
        average_rating = round(total_rating / total, 1) if total > 0 else 0

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

@lru_cache(maxsize=256)
def _get_user_review_count_cached(
    user_id: str, reviews_hash: int, review_user_ids: Tuple[str, ...]
) -> int:
    """
    Count user-authored reviews using an LRU cache.
    """
    # reviews_hash is part of the cache key by design, even though this
    # function can derive counts from review_user_ids alone.
    _ = reviews_hash
    return sum(1 for candidate in review_user_ids if candidate == user_id)


def get_user_review_count(user_id: str, reviews: Iterable[dict]) -> int:
    """
    Get review count for a specific user with cache invalidation.
    """
    reviews = list(reviews)
    reviews_hash = create_reviews_hash(reviews)
    review_user_ids = tuple(str(review.get("user_id", "")) for review in reviews)
    return _get_user_review_count_cached(user_id, reviews_hash, review_user_ids)

def create_reviews_hash(reviews):
    """
    Create a hash of reviews for cache invalidation
    """
    if not reviews:
        return hash(())

    # Include stable fields so cache invalidates whenever review content changes.
    fingerprint = []
    for review in reviews:
        timestamp = review.get("timestamp")
        if hasattr(timestamp, "isoformat"):
            timestamp_value = timestamp.isoformat()
        else:
            timestamp_value = str(timestamp)
        fingerprint.append(
            (
                str(review.get("id", "")),
                str(review.get("user_id", "")),
                str(review.get("rating", "")),
                str(review.get("text", "")),
                timestamp_value,
            )
        )
    return hash(tuple(fingerprint))

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