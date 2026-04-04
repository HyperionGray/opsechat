"""
Unit tests for review performance helpers and per-user review stats.
"""

import datetime

from review_performance import (
    create_reviews_hash,
    get_cached_review_stats,
    get_user_review_count,
    get_user_review_stats,
    invalidate_review_cache,
)


def _sample_reviews():
    base_time = datetime.datetime(2026, 1, 1, 12, 0, 0)
    return [
        {
            "id": "r1",
            "user_id": "user-a",
            "rating": 5,
            "text": "great",
            "timestamp": base_time,
        },
        {
            "id": "r2",
            "user_id": "user-b",
            "rating": "4",
            "review_text": "good",
            "timestamp": base_time + datetime.timedelta(minutes=1),
        },
        {
            "id": "r3",
            "user_id": "user-a",
            "rating": 3,
            "text": "ok",
            "timestamp": base_time + datetime.timedelta(minutes=2),
        },
    ]


def test_get_cached_review_stats_handles_mixed_rating_types():
    invalidate_review_cache()
    stats = get_cached_review_stats(_sample_reviews())

    assert stats["total"] == 3
    assert stats["average_rating"] == 4.0
    assert stats["rating_distribution"] == {1: 0, 2: 0, 3: 1, 4: 1, 5: 1}


def test_get_user_review_count_returns_real_count():
    reviews = _sample_reviews()
    reviews_hash = create_reviews_hash(reviews)

    assert get_user_review_count("user-a", reviews_hash, reviews=reviews) == 2
    assert get_user_review_count("user-b", reviews_hash, reviews=reviews) == 1
    assert get_user_review_count("missing", reviews_hash, reviews=reviews) == 0


def test_get_user_review_stats_includes_distribution_and_latest_timestamp():
    reviews = _sample_reviews()
    stats = get_user_review_stats("user-a", reviews)

    assert stats["review_count"] == 2
    assert stats["average_rating"] == 4.0
    assert stats["rating_distribution"] == {1: 0, 2: 0, 3: 1, 4: 0, 5: 1}
    assert stats["last_review_timestamp"] == "2026-01-01T12:02:00"


def test_create_reviews_hash_changes_when_reviews_change():
    reviews = _sample_reviews()
    first_hash = create_reviews_hash(reviews)

    reviews[0]["text"] = "great-updated"
    second_hash = create_reviews_hash(reviews)

    assert first_hash != second_hash
