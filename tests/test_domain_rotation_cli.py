"""
Tests for domain_rotation_cli helper behavior.
"""

from datetime import datetime

import domain_rotation_cli as cli


def test_format_datetime_handles_datetime():
    value = datetime(2026, 1, 2, 3, 4, 5)
    assert cli._format_datetime(value, "%Y-%m-%d") == "2026-01-02"


def test_format_datetime_handles_iso_string():
    assert (
        cli._format_datetime("2026-01-02T03:04:05", "%Y-%m-%d %H:%M")
        == "2026-01-02 03:04"
    )


def test_format_datetime_handles_unknown_values():
    assert cli._format_datetime(None, "%Y") == "Unknown"
