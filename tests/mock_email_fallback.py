"""
In-memory fallback email services for mock server tests.

Used when importing `email_system` fails in isolated test environments.
The implementation provides deterministic behavior for burner management
without requiring external services or persistent storage.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import secrets
import string
from typing import Dict, List, Optional, Tuple


class MockEmailStorage:
    """Minimal in-memory inbox store."""

    def __init__(self) -> None:
        self.inboxes: Dict[str, List[dict]] = {}

    def create_user_inbox(self, user_id: str) -> List[dict]:
        """Create (or return) a user's inbox list."""
        normalized_user_id = str(user_id)
        return self.inboxes.setdefault(normalized_user_id, [])


class MockBurnerManager:
    """In-memory burner manager used by mock server fallback mode."""

    def __init__(self, default_domain: str = "example.com", default_hours_valid: int = 24) -> None:
        self.default_domain = default_domain
        self.default_hours_valid = default_hours_valid
        self._burners: Dict[str, dict] = {}

    def _sanitize_domain(self, domain: Optional[str]) -> str:
        chosen = (domain or self.default_domain).strip()
        if chosen.startswith("@"):
            chosen = chosen[1:]
        return chosen or self.default_domain

    def _random_local_part(self, length: int = 12) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _is_expired(self, metadata: dict, now: Optional[datetime] = None) -> bool:
        expires_at = metadata.get("expires_at")
        if not isinstance(expires_at, datetime):
            return True
        now = now or datetime.utcnow()
        return expires_at <= now

    def cleanup_expired(self) -> int:
        """Remove expired burners and return number removed."""
        now = datetime.utcnow()
        expired_emails = [
            email
            for email, metadata in self._burners.items()
            if self._is_expired(metadata, now=now)
        ]
        for email in expired_emails:
            self._burners.pop(email, None)
        return len(expired_emails)

    def generate_burner_email(
        self, user_id: str, domain: Optional[str] = None, hours_valid: Optional[int] = None
    ) -> str:
        """Generate a new burner for a user."""
        normalized_user_id = str(user_id)
        chosen_domain = self._sanitize_domain(domain)
        ttl_hours = hours_valid if isinstance(hours_valid, int) and hours_valid > 0 else self.default_hours_valid

        burner_email = f"{self._random_local_part()}@{chosen_domain}"
        while burner_email in self._burners:
            burner_email = f"{self._random_local_part()}@{chosen_domain}"

        now = datetime.utcnow()
        self._burners[burner_email] = {
            "user_id": normalized_user_id,
            "created_at": now,
            "expires_at": now + timedelta(hours=ttl_hours),
        }
        return burner_email

    def rotate_burner(self, user_id: str, old_email: str) -> str:
        """Rotate from an old burner to a newly generated burner."""
        normalized_user_id = str(user_id)
        old_metadata = self._burners.get(old_email)
        if old_metadata and old_metadata.get("user_id") == normalized_user_id:
            self._burners.pop(old_email, None)
        return self.generate_burner_email(normalized_user_id)

    def get_user_burners(self, user_id: str) -> List[str]:
        """Get all active burners for a user."""
        normalized_user_id = str(user_id)
        self.cleanup_expired()
        return [
            email
            for email, metadata in self._burners.items()
            if metadata.get("user_id") == normalized_user_id
        ]

    def get_user_for_burner(self, email: str) -> Optional[str]:
        """Return owner of active burner email, otherwise None."""
        metadata = self._burners.get(email)
        if not metadata:
            return None
        if self._is_expired(metadata):
            self._burners.pop(email, None)
            return None
        return metadata.get("user_id")

    def expire_burner(self, email: str) -> bool:
        """Expire burner immediately."""
        return self._burners.pop(email, None) is not None


def create_fallback_email_services() -> Tuple[MockEmailStorage, MockBurnerManager]:
    """Factory used by mock server fallback paths."""
    return MockEmailStorage(), MockBurnerManager()
