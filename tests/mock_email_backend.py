"""
In-memory email backends used by tests/mock_server.py when email_system imports fail.

These classes intentionally implement only the small interface needed by the mock
server routes and test helpers.
"""

from __future__ import annotations

import datetime
import secrets
from typing import Dict, List, Optional


class MockEmailStorage:
    """Minimal in-memory inbox storage for the mock server."""

    def __init__(self) -> None:
        self.emails: Dict[str, List[Dict]] = {}

    def create_user_inbox(self, user_id: str) -> None:
        if user_id not in self.emails:
            self.emails[user_id] = []


class MockBurnerManager:
    """Minimal burner manager with expiry and user mapping."""

    def __init__(self) -> None:
        self.burner_addresses: Dict[str, Dict] = {}
        self.user_burners: Dict[str, List[str]] = {}
        self.default_domain = "example.com"

    def generate_burner_email(self, user_id: str, hours_valid: int = 24) -> str:
        token = secrets.token_hex(6)
        email = f"burner-{token}@{self.default_domain}"
        now = datetime.datetime.now()
        self.burner_addresses[email] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + datetime.timedelta(hours=hours_valid),
        }
        self.user_burners.setdefault(user_id, []).append(email)
        return email

    def rotate_burner(self, user_id: str, old_email: Optional[str] = None) -> str:
        if old_email:
            self.expire_burner(old_email)
        return self.generate_burner_email(user_id)

    def get_user_burners(self, user_id: str) -> List[Dict]:
        self.cleanup_expired()
        burners = []
        now = datetime.datetime.now()
        for email in self.user_burners.get(user_id, []):
            info = self.burner_addresses.get(email)
            if not info:
                continue
            remaining = int((info["expires_at"] - now).total_seconds())
            burners.append(
                {
                    "email": email,
                    "created_at": info["created_at"],
                    "expires_at": info["expires_at"],
                    "time_remaining_seconds": max(remaining, 0),
                }
            )
        return burners

    def get_user_for_burner(self, email: str) -> Optional[str]:
        info = self.burner_addresses.get(email)
        if not info:
            return None
        if info["expires_at"] <= datetime.datetime.now():
            self.expire_burner(email)
            return None
        return info["user_id"]

    def expire_burner(self, email: str) -> bool:
        info = self.burner_addresses.pop(email, None)
        if not info:
            return False
        user_id = info["user_id"]
        if user_id in self.user_burners:
            self.user_burners[user_id] = [e for e in self.user_burners[user_id] if e != email]
            if not self.user_burners[user_id]:
                del self.user_burners[user_id]
        return True

    def cleanup_expired(self) -> None:
        now = datetime.datetime.now()
        expired = [
            email
            for email, info in self.burner_addresses.items()
            if info["expires_at"] <= now
        ]
        for email in expired:
            self.expire_burner(email)

    def snapshot(self) -> Dict:
        """Return serializable state for diagnostics."""
        self.cleanup_expired()
        return {
            "burner_count": len(self.burner_addresses),
            "user_count": len(self.user_burners),
            "burners_by_user": {
                user_id: len(emails) for user_id, emails in self.user_burners.items()
            },
        }
