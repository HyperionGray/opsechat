import datetime

from review_performance import (
    create_reviews_hash,
    get_user_review_count,
    invalidate_review_cache,
)


def test_get_user_review_count_returns_expected_counts():
    invalidate_review_cache()
    base_time = datetime.datetime(2026, 1, 1, 0, 0, 0)
    reviews = [
        {"user_id": "alice", "rating": 5, "timestamp": base_time},
        {"user_id": "alice", "rating": 4, "timestamp": base_time + datetime.timedelta(seconds=1)},
        {"user_id": "bob", "rating": 3, "timestamp": base_time + datetime.timedelta(seconds=2)},
    ]

    reviews_hash = create_reviews_hash(reviews)

    assert get_user_review_count("alice", reviews_hash) == 2
    assert get_user_review_count("bob", reviews_hash) == 1
    assert get_user_review_count("charlie", reviews_hash) == 0


def test_get_user_review_count_changes_when_review_data_changes():
    invalidate_review_cache()
    base_time = datetime.datetime(2026, 1, 1, 0, 0, 0)
    reviews_v1 = [
        {"user_id": "alice", "rating": 5, "timestamp": base_time},
    ]
    reviews_v2 = reviews_v1 + [
        {"user_id": "alice", "rating": 4, "timestamp": base_time + datetime.timedelta(seconds=1)},
    ]

    hash_v1 = create_reviews_hash(reviews_v1)
    hash_v2 = create_reviews_hash(reviews_v2)

    assert hash_v1 != hash_v2
    assert get_user_review_count("alice", hash_v1) == 1
    assert get_user_review_count("alice", hash_v2) == 2


def test_get_user_review_count_handles_empty_and_none_user():
    invalidate_review_cache()
    reviews_hash = create_reviews_hash([])

    assert get_user_review_count("alice", reviews_hash) == 0
    assert get_user_review_count(None, reviews_hash) == 0
