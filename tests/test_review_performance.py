"""
Unit tests for review_performance helpers.
"""

import datetime

from review_performance import (
    create_reviews_hash,
    get_user_review_count,
)


def _sample_reviews():
    now = datetime.datetime.now()
    return [
        {"user_id": "alice", "rating": 5, "timestamp": now - datetime.timedelta(minutes=2)},
        {"user_id": "alice", "rating": 4, "timestamp": now - datetime.timedelta(minutes=1)},
        {"user_id": "bob", "rating": 3, "timestamp": now},
    ]


def test_get_user_review_count_returns_expected_counts():
    reviews = _sample_reviews()
    reviews_hash = create_reviews_hash(reviews)

    assert get_user_review_count("alice", reviews_hash) == 2
    assert get_user_review_count("bob", reviews_hash) == 1
    assert get_user_review_count("charlie", reviews_hash) == 0


def test_get_user_review_count_empty_reviews_returns_zero():
    reviews_hash = create_reviews_hash([])
    assert get_user_review_count("any-user", reviews_hash) == 0


def test_reviews_hash_changes_when_latest_timestamp_changes():
    now = datetime.datetime.now()
    reviews_a = [{"user_id": "alice", "rating": 5, "timestamp": now}]
    reviews_b = [{"user_id": "alice", "rating": 5, "timestamp": now + datetime.timedelta(seconds=1)}]

    hash_a = create_reviews_hash(reviews_a)
    hash_b = create_reviews_hash(reviews_b)

    assert hash_a != hash_b
