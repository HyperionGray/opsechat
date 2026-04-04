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

def _coerce_rating(value):
    """Convert rating values to validated integers in range [1, 5]."""
    try:
        rating = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= rating <= 5:
        return rating
    return None


def _normalize_review_text(review):
    """
    Support both historical review payloads:
    - {'text': '...'}
    - {'review_text': '...'}
    """
    text = review.get("text")
    if text is None:
        text = review.get("review_text", "")
    return str(text)


def _timestamp_to_sortable(value):
    """Normalize timestamps to a comparable value for hashing/sorting."""
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


@lru_cache(maxsize=256)
def _cached_user_review_count(user_id, reviews_hash, review_user_ids):
    """
    Cached helper for user review counts.
    reviews_hash is included to provide explicit cache invalidation semantics.
    """
    return sum(1 for review_user_id in review_user_ids if review_user_id == user_id)


def invalidate_review_cache():
    """Invalidate the review statistics cache"""
    global _review_stats_cache, _review_stats_cache_time
    _review_stats_cache = None
    _review_stats_cache_time = 0
    _cached_user_review_count.cache_clear()

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
        valid_ratings = []
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for review in reviews:
            rating = _coerce_rating(review.get("rating"))
            if rating is None:
                continue
            valid_ratings.append(rating)
            rating_distribution[rating] += 1

        average_rating = round(sum(valid_ratings) / len(valid_ratings), 1) if valid_ratings else 0

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

def get_user_review_count(user_id, reviews_hash, reviews=None):
    """
    Get review count for a specific user (cached)
    reviews_hash is used to invalidate cache when reviews change.
    """
    if not user_id or not reviews:
        return 0

    review_user_ids = tuple(review.get("user_id") for review in reviews)
    return _cached_user_review_count(user_id, reviews_hash, review_user_ids)


def get_user_review_stats(user_id, reviews):
    """Return per-session anonymous review insights for the current user."""
    empty_stats = {
        "review_count": 0,
        "average_rating": 0,
        "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        "last_review_timestamp": None,
    }
    if not user_id or not reviews:
        return empty_stats

    reviews_hash = create_reviews_hash(reviews)
    review_count = get_user_review_count(user_id, reviews_hash, reviews=reviews)
    if review_count == 0:
        return empty_stats

    user_reviews = [review for review in reviews if review.get("user_id") == user_id]
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    valid_ratings = []
    latest_timestamp = None

    for review in user_reviews:
        rating = _coerce_rating(review.get("rating"))
        if rating is not None:
            valid_ratings.append(rating)
            rating_distribution[rating] += 1

        timestamp = review.get("timestamp")
        if isinstance(timestamp, datetime.datetime):
            if latest_timestamp is None or timestamp > latest_timestamp:
                latest_timestamp = timestamp
        elif isinstance(timestamp, str):
            if latest_timestamp is None:
                latest_timestamp = timestamp
            elif isinstance(latest_timestamp, str) and timestamp > latest_timestamp:
                latest_timestamp = timestamp

    average_rating = round(sum(valid_ratings) / len(valid_ratings), 1) if valid_ratings else 0
    if isinstance(latest_timestamp, datetime.datetime):
        latest_timestamp = latest_timestamp.isoformat()

    return {
        "review_count": review_count,
        "average_rating": average_rating,
        "rating_distribution": rating_distribution,
        "last_review_timestamp": latest_timestamp,
    }

def create_reviews_hash(reviews):
    """
    Create a hash of reviews for cache invalidation
    """
    if not reviews:
        return hash(())
    
    review_signature = []
    for review in reviews:
        review_signature.append(
            (
                review.get("id"),
                review.get("user_id"),
                _coerce_rating(review.get("rating")),
                _normalize_review_text(review),
                _timestamp_to_sortable(review.get("timestamp")),
            )
        )

    return hash(tuple(review_signature))

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