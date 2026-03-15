"""
Fallback email components for test-only mock server usage.

These classes intentionally avoid Flask or project runtime imports so they can
be tested in minimal environments.
"""

import datetime
import secrets


class MockEmailStorage:
    """In-memory fallback inbox storage for isolated tests."""

    def __init__(self):
        self._inboxes = {}

    def create_user_inbox(self, user_id):
        self._inboxes.setdefault(user_id, [])

    def get_user_inbox(self, user_id):
        self.create_user_inbox(user_id)
        return self._inboxes[user_id]

    def add_email(self, user_id, email):
        self.get_user_inbox(user_id).append(email)


class MockBurnerManager:
    """Simple in-memory burner manager when email_system is unavailable."""

    def __init__(self):
        self._burners = {}
        self._owner_by_email = {}

    def cleanup_expired(self):
        now = datetime.datetime.now()
        expired = [email for email, meta in self._burners.items() if meta["expires_at"] <= now]
        for email in expired:
            self.expire_burner(email)
        return len(expired)

    def _new_email(self, user_id):
        token = secrets.token_hex(4)
        return f"test-{user_id}-{token}@example.com"

    def generate_burner_email(self, user_id):
        self.cleanup_expired()
        email = self._new_email(user_id)
        self._burners[email] = {
            "user_id": user_id,
            "expires_at": datetime.datetime.now() + datetime.timedelta(minutes=10),
        }
        self._owner_by_email[email] = user_id
        return email

    def rotate_burner(self, user_id, old_email):
        self.expire_burner(old_email)
        return self.generate_burner_email(user_id)

    def get_user_burners(self, user_id):
        self.cleanup_expired()
        return [email for email, owner in self._owner_by_email.items() if owner == user_id]

    def get_user_for_burner(self, email):
        self.cleanup_expired()
        return self._owner_by_email.get(email)

    def expire_burner(self, email):
        self._burners.pop(email, None)
        self._owner_by_email.pop(email, None)
