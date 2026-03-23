"""
HTTP Mail System for opsechat

Provides email-like functionality over HTTP with no SMTP/IMAP dependencies.
Messages are posted to mailboxes and read back using a secret read_key.
Default deny: without the read_key, nobody can read the inbox.

Design:
- Mailbox has a public address (short token, safe to share with senders)
- Mailbox has a private read_key (long token, only owner knows it)
- Anyone can POST a message to a mailbox address
- Only the holder of read_key can GET the inbox
- Messages auto-expire after 24 hours (in-memory only)
- Memory is overwritten on deletion (security)
"""

import datetime
import secrets
import string
import threading
from typing import Dict, List, Optional


# Maximum message length
MAX_MAIL_MESSAGE_LENGTH = 2000

# Message expiry (24 hours)
MAIL_EXPIRY_HOURS = 24


class HttpMessage:
    """A single in-memory HTTP mail message."""

    def __init__(self, msg_id: str, subject: str, body: str,
                 sender_handle: str, timestamp: datetime.datetime):
        self.msg_id = msg_id
        self.subject = subject
        self.body = body
        self.sender_handle = sender_handle
        self.timestamp = timestamp

    def to_dict(self) -> Dict:
        return {
            "id": self.msg_id,
            "subject": self.subject,
            "body": self.body,
            "sender": self.sender_handle,
            "timestamp": self.timestamp.isoformat(),
        }

    def overwrite(self) -> None:
        """Overwrite message content in memory before deletion."""
        length = len(self.body)
        self.body = "X" * length
        self.subject = "X" * len(self.subject)
        self.sender_handle = "X" * len(self.sender_handle)


class HttpMailbox:
    """A single HTTP mailbox identified by address with a private read_key."""

    def __init__(self, address: str, read_key: str):
        self.address = address
        self.read_key = read_key
        self.messages: List[HttpMessage] = []
        self.created_at = datetime.datetime.now()
        self.lock = threading.Lock()
        self.destroyed = False

    def add_message(self, subject: str, body: str, sender_handle: str) -> Optional[str]:
        """Add a message; returns the new message ID, or None if mailbox is destroyed."""
        msg_id = _generate_id(12)  # 12 bytes → 16 URL-safe chars
        msg = HttpMessage(
            msg_id=msg_id,
            subject=subject,
            body=body,
            sender_handle=sender_handle,
            timestamp=datetime.datetime.now(),
        )
        with self.lock:
            if self.destroyed:
                return None
            self.messages.append(msg)
        return msg_id

    def get_messages(self, read_key: str) -> Optional[List[Dict]]:
        """Return messages if read_key matches, else None (default deny)."""
        if not secrets.compare_digest(read_key, self.read_key):
            return None
        self._expire_old_messages()
        with self.lock:
            return [m.to_dict() for m in self.messages]

    def delete_message(self, read_key: str, msg_id: str) -> bool:
        """Delete a message by ID after verifying read_key. Returns True on success."""
        if not secrets.compare_digest(read_key, self.read_key):
            return False
        with self.lock:
            if self.destroyed:
                return False
            for i, msg in enumerate(self.messages):
                if msg.msg_id == msg_id:
                    msg.overwrite()
                    del self.messages[i]
                    return True
        return False

    def _expire_old_messages(self) -> None:
        """Remove messages older than MAIL_EXPIRY_HOURS."""
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=MAIL_EXPIRY_HOURS)
        with self.lock:
            surviving = []
            for msg in self.messages:
                if msg.timestamp < cutoff:
                    msg.overwrite()
                else:
                    surviving.append(msg)
            self.messages = surviving

    def message_count(self) -> int:
        self._expire_old_messages()
        with self.lock:
            return len(self.messages)


class HttpMailStorage:
    """Global in-memory store for all HTTP mailboxes."""

    def __init__(self):
        self._mailboxes: Dict[str, HttpMailbox] = {}  # address -> mailbox
        self._lock = threading.Lock()

    def create_mailbox(self) -> HttpMailbox:
        """Create a new mailbox; returns the mailbox object (contains address + read_key)."""
        address = _generate_id(9)    # 9 bytes → 12 URL-safe chars
        read_key = _generate_id(24)  # 24 bytes → 32 URL-safe chars
        mailbox = HttpMailbox(address=address, read_key=read_key)
        with self._lock:
            self._mailboxes[address] = mailbox
        return mailbox

    def get_mailbox(self, address: str) -> Optional[HttpMailbox]:
        with self._lock:
            return self._mailboxes.get(address)

    def delete_mailbox(self, address: str, read_key: str) -> bool:
        """Delete entire mailbox after verifying read_key.

        Concurrency notes:
        - We remove the mailbox from the global store under `self._lock`.
        - We then overwrite and clear messages under the per-mailbox lock
          to avoid races with concurrent send/add operations.

        Checklist (follow-ups outside this class):
        - [x] Ensure HttpMailbox exposes a `lock` used by all writers.
        - [x] Ensure add_message (or equivalent) checks a `destroyed` flag.
        """
        # First, look up and authenticate the mailbox under the global lock.
        with self._lock:
            mailbox = self._mailboxes.get(address)
            if mailbox is None:
                return False
            if not secrets.compare_digest(read_key, mailbox.read_key):
                return False
            # Remove the mailbox from the global mapping while still holding
            # the storage lock so no new lookups can obtain it.
            del self._mailboxes[address]

        # Now that the mailbox is no longer globally reachable, safely
        # overwrite and clear its messages under the per-mailbox lock.
        # This avoids data races on `mailbox.messages` with concurrent sends.
        lock = getattr(mailbox, "lock", None)
        if lock is not None:
            with lock:
                setattr(mailbox, "destroyed", True)
                for msg in mailbox.messages:
                    msg.overwrite()
                # Clear the list so message objects can be GC'ed.
                mailbox.messages.clear()
        else:
            # Fallback: no explicit mailbox lock available; still perform
            # overwrite/clear to maintain best-effort data scrubbing.
            setattr(mailbox, "destroyed", True)
            for msg in mailbox.messages:
                msg.overwrite()
            mailbox.messages.clear()

        return True
    def cleanup_empty_old_mailboxes(self) -> None:
        """Remove mailboxes with no messages that are older than 48 hours."""
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=48)
        with self._lock:
            stale = [
                addr for addr, mb in self._mailboxes.items()
                if mb.created_at < cutoff and len(mb.messages) == 0
            ]
            for addr in stale:
                del self._mailboxes[addr]

    def mailbox_count(self) -> int:
        with self._lock:
            return len(self._mailboxes)


def _generate_id(nbytes: int) -> str:
    """Generate a URL-safe random token from the given number of random bytes.

    ``secrets.token_urlsafe(n)`` encodes *n* random bytes into a base64url
    string (no padding), so passing *nbytes* directly gives full entropy —
    never truncate the result.

    Byte-to-character reference (base64url, no padding):
      9  bytes → 12 chars
      24 bytes → 32 chars
    """
    return secrets.token_urlsafe(nbytes)


# Global singleton
http_mail_storage = HttpMailStorage()
