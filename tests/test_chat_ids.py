"""
Tests for cryptographically secure ID generation and random username/color
generation in simple_chat_routes.

Related GitHub issues: #116 (automated key exchange / non-discoverable room IDs),
#118 (final tests — randomized usernames, DMs).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_chat_routes import (
    generate_random_username,
    generate_secure_dm_id,
    generate_secure_room_id,
    get_random_color_rgb,
)


class TestSecureIdGeneration:
    def test_room_ids_are_unique(self):
        ids = {generate_secure_room_id() for _ in range(50)}
        assert len(ids) == 50

    def test_room_id_minimum_length(self):
        # secrets.token_urlsafe(32) produces at least 43 chars
        for _ in range(10):
            rid = generate_secure_room_id()
            assert len(rid) >= 40, f"Room ID too short: {rid!r}"

    def test_dm_ids_are_unique(self):
        ids = {generate_secure_dm_id() for _ in range(50)}
        assert len(ids) == 50

    def test_dm_id_minimum_length(self):
        for _ in range(10):
            did = generate_secure_dm_id()
            assert len(did) >= 16, f"DM ID too short: {did!r}"

    def test_room_id_url_safe(self):
        """Room ID must be safe to embed in a URL path segment."""
        rid = generate_secure_room_id()
        invalid = set(" /\\?#%")
        assert not (set(rid) & invalid), f"Room ID contains unsafe chars: {rid!r}"


class TestUsernameColorGeneration:
    def test_username_pattern(self):
        """Username must match Adjective+Noun+4digit format."""
        pattern = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+\d{4}$")
        for _ in range(20):
            name = generate_random_username()
            assert pattern.match(name), f"Username does not match pattern: {name!r}"

    def test_usernames_are_varied(self):
        names = {generate_random_username() for _ in range(30)}
        # Very unlikely to get all the same with 12*12*9999 combinations
        assert len(names) > 1

    def test_color_is_list_of_three_ints(self):
        color = get_random_color_rgb()
        assert isinstance(color, list)
        assert len(color) == 3
        for channel in color:
            assert isinstance(channel, int)
            assert 0 <= channel <= 255

    def test_colors_are_varied(self):
        colors = {tuple(get_random_color_rgb()) for _ in range(50)}
        # Palette has 10 entries; with 50 draws we must hit more than 1
        assert len(colors) > 1
