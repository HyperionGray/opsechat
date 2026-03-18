#!/usr/bin/env python3
"""In-memory fallback backends for mock server degraded mode."""

import datetime
import random
import string
from typing import Any, Dict, List, Optional


class InMemoryMockEmailStorage:
    """Lightweight in-memory inbox storage used when email_system is unavailable."""

    def __init__(self):
        self.inboxes: Dict[str, List[Dict[str, Any]]] = {}

    def create_user_inbox(self, user_id: str):
        self.inboxes.setdefault(user_id, [])

    def add_email(self, user_id: str, email: Dict[str, Any]):
        self.create_user_inbox(user_id)
        email_copy = dict(email)
        email_copy.setdefault("timestamp", datetime.datetime.now())
        self.inboxes[user_id].append(email_copy)

    def get_emails(self, user_id: str) -> List[Dict[str, Any]]:
        return list(self.inboxes.get(user_id, []))


class InMemoryMockBurnerManager:
    """Simple burner manager with expiration support for mock/test fallback paths."""

    def __init__(self, domain: str = "example.com", hours_valid: int = 24):
        self.domain = domain
        self.hours_valid = hours_valid
        self.burners: Dict[str, Dict[str, Any]] = {}
        self.user_burners: Dict[str, List[str]] = {}

    def cleanup_expired(self):
        now = datetime.datetime.now()
        expired = [
            email for email, meta in self.burners.items()
            if meta["expires_at"] <= now
        ]
        for email in expired:
            user_id = self.burners[email]["user_id"]
            del self.burners[email]
            if user_id in self.user_burners:
                self.user_burners[user_id] = [
                    burner for burner in self.user_burners[user_id] if burner != email
                ]

    def generate_burner_email(self, user_id: str):
        self.cleanup_expired()
        local_part = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
        email = f"{local_part}@{self.domain}"
        now = datetime.datetime.now()
        self.burners[email] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + datetime.timedelta(hours=self.hours_valid)
        }
        self.user_burners.setdefault(user_id, []).append(email)
        return email

    def rotate_burner(self, user_id: str, old_email: Optional[str] = None):
        if old_email:
            self.expire_burner(old_email)
        return self.generate_burner_email(user_id)

    def get_user_burners(self, user_id: str):
        self.cleanup_expired()
        result = []
        for email in self.user_burners.get(user_id, []):
            meta = self.burners.get(email)
            if meta:
                result.append(
                    {
                        "email": email,
                        "created_at": meta["created_at"],
                        "expires_at": meta["expires_at"]
                    }
                )
        return result

    def get_user_for_burner(self, email: str):
        self.cleanup_expired()
        meta = self.burners.get(email)
        if not meta:
            return None
        return meta["user_id"]

    def expire_burner(self, email: str):
        if email not in self.burners:
            return False
        user_id = self.burners[email]["user_id"]
        del self.burners[email]
        if user_id in self.user_burners:
            self.user_burners[user_id] = [
                burner for burner in self.user_burners[user_id] if burner != email
            ]
        return True
