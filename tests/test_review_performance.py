import datetime

from review_performance import (
    create_reviews_hash,
    get_user_review_count,
    invalidate_review_cache,
)


def _build_reviews():
    now = datetime.datetime.now()
    return [
        {"user_id": "alice", "rating": 5, "timestamp": now - datetime.timedelta(minutes=3)},
        {"user_id": "bob", "rating": 4, "timestamp": now - datetime.timedelta(minutes=2)},
        {"user_id": "alice", "rating": 3, "timestamp": now - datetime.timedelta(minutes=1)},
    ]


def test_get_user_review_count_returns_real_count():
    invalidate_review_cache()
    reviews = _build_reviews()
    reviews_hash = create_reviews_hash(reviews)

    assert get_user_review_count("alice", reviews_hash) == 2
    assert get_user_review_count("bob", reviews_hash) == 1


def test_get_user_review_count_unknown_user_returns_zero():
    invalidate_review_cache()
    reviews_hash = create_reviews_hash(_build_reviews())

    assert get_user_review_count("charlie", reviews_hash) == 0


def test_invalidate_review_cache_clears_cached_counts():
    invalidate_review_cache()
    reviews_hash = create_reviews_hash(_build_reviews())
    assert get_user_review_count("alice", reviews_hash) == 2

    invalidate_review_cache()
    assert get_user_review_count("alice", reviews_hash) == 0


def test_empty_reviews_hash_has_zero_counts():
    invalidate_review_cache()
    reviews_hash = create_reviews_hash([])

    assert get_user_review_count("any-user", reviews_hash) == 0
