"""
In-memory mock email backend for tests and local development.

This module is used when the production email system is unavailable.
"""

import datetime
import random
import string
from typing import Any, Dict, List, Optional


class MockEmailStorage:
    """Simple inbox storage for mock server usage."""

    def __init__(self):
        self.emails: Dict[str, List[Dict[str, Any]]] = {}

    def create_user_inbox(self, user_id: str) -> None:
        if user_id not in self.emails:
            self.emails[user_id] = []

    def add_email(self, user_id: str, email: Dict[str, Any]) -> Dict[str, Any]:
        self.create_user_inbox(user_id)
        stored = dict(email)
        stored.setdefault("id", f"mock-{self._token(12)}")
        stored.setdefault("timestamp", datetime.datetime.now())
        self.emails[user_id].append(stored)
        return stored

    def get_emails(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        self.create_user_inbox(user_id)
        emails = list(self.emails[user_id])
        if limit is None:
            return emails
        return emails[-limit:]

    @staticmethod
    def _token(size: int) -> str:
        return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(size))


class MockBurnerManager:
    """In-memory burner manager compatible with route tests."""

    def __init__(self, default_domain: str = "example.com"):
        self.default_domain = default_domain
        self.burner_addresses: Dict[str, Dict[str, Any]] = {}
        self.user_burners: Dict[str, List[str]] = {}

    def generate_burner_email(
        self,
        user_id: str,
        domain: Optional[str] = None,
        hours_valid: int = 24
    ) -> str:
        self.cleanup_expired()
        resolved_domain = domain or self.default_domain

        email = self._new_email(resolved_domain)
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

    def get_user_burners(self, user_id: str) -> List[Dict[str, Any]]:
        self.cleanup_expired()
        now = datetime.datetime.now()
        result: List[Dict[str, Any]] = []
        for email in self.user_burners.get(user_id, []):
            info = self.burner_addresses.get(email)
            if not info:
                continue
            remaining = int((info["expires_at"] - now).total_seconds())
            result.append(
                {
                    "email": email,
                    "created_at": info["created_at"],
                    "expires_at": info["expires_at"],
                    "time_remaining_seconds": max(remaining, 0),
                }
            )
        return result

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
        self._remove_user_mapping(info["user_id"], email)
        return True

    def cleanup_expired(self) -> None:
        now = datetime.datetime.now()
        expired = [
            email
            for email, info in self.burner_addresses.items()
            if info["expires_at"] <= now
        ]
        for email in expired:
            info = self.burner_addresses.pop(email, None)
            if not info:
                continue
            self._remove_user_mapping(info["user_id"], email)

    def _remove_user_mapping(self, user_id: str, email: str) -> None:
        user_emails = self.user_burners.get(user_id, [])
        if email in user_emails:
            user_emails.remove(email)
        if not user_emails and user_id in self.user_burners:
            del self.user_burners[user_id]

    def _new_email(self, domain: str) -> str:
        while True:
            local_part = "".join(
                random.choice(string.ascii_lowercase + string.digits) for _ in range(12)
            )
            email = f"{local_part}@{domain}"
            if email not in self.burner_addresses:
                return email
