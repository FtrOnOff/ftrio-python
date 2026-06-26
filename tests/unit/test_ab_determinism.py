"""Pinned cross-language A/B determinism vectors.

These buckets are verified against the .NET implementation. Pinning them means a
regression in the hashing or byte-order handling is caught immediately, since the
whole point of A/B bucketing is that the same user lands identically across runs
and across runtimes.
"""

from __future__ import annotations

import pytest

from ftrio.strategies import compute_bucket

# (user, key, salt, expected_bucket)
_PINNED_VECTORS = [
    ("alice", "TestingABTest", "", 84),
    ("bob", "TestingABTest", "", 68),
    ("charlie", "TestingABTest", "", 89),
    ("dave", "TestingABTest", "", 64),
    ("alice", "TestingABTestSalted", "round2", 2),
    ("bob", "TestingABTestSalted", "round2", 99),
]


@pytest.mark.parametrize("user_id, toggle_key, salt, expected_bucket", _PINNED_VECTORS)
def test_compute_bucket_matches_pinned_cross_language_vectors(
    user_id, toggle_key, salt, expected_bucket
):
    assert compute_bucket(user_id, toggle_key, salt) == expected_bucket


def test_compute_bucket_is_stable_for_repeated_calls():
    first = compute_bucket("alice", "SomeToggle", "")
    for _ in range(50):
        assert compute_bucket("alice", "SomeToggle", "") == first


def test_compute_bucket_salt_changes_bucket_for_at_least_one_user():
    # The salted form must not be a no-op: across a population, some users must
    # bucket differently with a salt than without.
    user_ids = [f"user-{index}" for index in range(100)]
    without_salt = [compute_bucket(user_id, "Toggle", "") for user_id in user_ids]
    with_salt = [compute_bucket(user_id, "Toggle", "round2") for user_id in user_ids]
    assert without_salt != with_salt
