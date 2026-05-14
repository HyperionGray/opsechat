"""
HTTP Mail System for opsechat

Provides email-like functionality over HTTP with no SMTP/IMAP dependencies.
Messages are posted to named inboxes and read back as ciphertext for
browser-side decryption.

Design:
- Mailbox has a public address (internal token) plus an optional
  shareable alias
- Mailbox has a private read_key for destructive actions
- Anyone can POST a message to a mailbox address
- Inbox reads return ciphertext; the browser decrypts with the user key
- Messages auto-expire after 24 hours (in-memory only)
- Memory is overwritten on deletion (security)
"""

import datetime
import secrets
import threading
from typing import Dict, List, Optional


# Maximum message length
MAX_MAIL_MESSAGE_LENGTH = 2000

# Message expiry (24 hours)
MAIL_EXPIRY_HOURS = 24

MAILBOX_ALIAS_ADJECTIVES = (
    "amber", "ashen", "brisk", "cipher", "covert", "ember",
    "ghost", "ivory", "lunar", "misty", "silent", "velvet",
)

MAILBOX_ALIAS_NOUNS = (
    "badger", "falcon", "harbor", "lantern", "otter", "raven",
    "signal", "sparrow", "thistle", "vector", "willow", "wren",
)


ENCRYPTED_SUBJECT_PLACEHOLDER = "(encrypted message)"
ENCRYPTED_BODY_PLACEHOLDER = (
    "Ciphertext only. Decrypt in your browser with the correct inbox key."
)


class HttpMessage:
    """A single in-memory HTTP mail message."""

    def __init__(
        self,
        msg_id: str,
        subject: str,
        body: str,
        sender_handle: str,
        timestamp: datetime.datetime,
        encrypted_payload: Optional[str] = None,
    ):
        self.msg_id = msg_id
        self.subject = subject
        self.body = body
        self.sender_handle = sender_handle
        self.timestamp = timestamp
        self.encrypted_payload = encrypted_payload

    def to_dict(self) -> Dict:
        payload = {
            "id": self.msg_id,
            "subject": self.subject,
            "body": self.body,
            "sender": self.sender_handle,
            "timestamp": self.timestamp.isoformat(),
            "encrypted": bool(self.encrypted_payload),
        }
        if self.encrypted_payload is not None:
            payload["ciphertext"] = self.encrypted_payload
            payload["cipher_mode"] = "shared-secret-v1"
        return payload

    def overwrite(self) -> None:
        """Overwrite message content in memory before deletion."""
        length = len(self.body)
        self.body = "X" * length
        self.subject = "X" * len(self.subject)
        self.sender_handle = "X" * len(self.sender_handle)
        if self.encrypted_payload is not None:
            self.encrypted_payload = "X" * len(self.encrypted_payload)


class HttpMailbox:
    """A single HTTP mailbox identified by address with a private read_key."""

    def __init__(
        self,
        address: str,
        read_key: str,
        owner_id: Optional[str] = None,
        alias: Optional[str] = None,
    ):
        self.address = address
        self.read_key = read_key
        self.owner_id = owner_id
        self.alias = alias
        self.messages: List[HttpMessage] = []
        self.created_at = datetime.datetime.now()
        self.lock = threading.Lock()
        self.destroyed = False

    def add_message(self, subject: str, body: str, sender_handle: str) -> str:
        """Add a message; returns the new message ID."""
        if self.destroyed:
            raise RuntimeError("Mailbox has been destroyed")
        msg_id = _generate_id(12)  # 12 bytes → 16 URL-safe chars
        msg = HttpMessage(
            msg_id=msg_id,
            subject=subject,
            body=body,
            sender_handle=sender_handle,
            timestamp=datetime.datetime.now(),
        )
        with self.lock:
            self.messages.append(msg)
        return msg_id

    def add_encrypted_message(self, encrypted_payload: str) -> str:
        """Add a browser-encrypted message bundle."""
        if self.destroyed:
            raise RuntimeError("Mailbox has been destroyed")
        msg_id = _generate_id(12)
        msg = HttpMessage(
            msg_id=msg_id,
            subject=ENCRYPTED_SUBJECT_PLACEHOLDER,
            body=ENCRYPTED_BODY_PLACEHOLDER,
            sender_handle="encrypted",
            timestamp=datetime.datetime.now(),
            encrypted_payload=encrypted_payload,
        )
        with self.lock:
            self.messages.append(msg)
        return msg_id

    def get_messages(self) -> List[Dict]:
        """Return mailbox contents. The browser handles decryption locally."""
        self._expire_old_messages()
        with self.lock:
            return [m.to_dict() for m in self.messages]

    def delete_message(self, read_key: str, msg_id: str) -> bool:
        """Delete a message by ID after verifying read_key."""
        if not secrets.compare_digest(read_key, self.read_key):
            return False
        with self.lock:
            for i, msg in enumerate(self.messages):
                if msg.msg_id == msg_id:
                    msg.overwrite()
                    del self.messages[i]
                    return True
        return False

    def _expire_old_messages(self) -> None:
        """Remove messages older than MAIL_EXPIRY_HOURS."""
        cutoff = (
            datetime.datetime.now()
            - datetime.timedelta(hours=MAIL_EXPIRY_HOURS)
        )
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
        self._aliases: Dict[str, str] = {}  # alias -> address
        self._lock = threading.Lock()

    def create_mailbox(
        self,
        address: Optional[str] = None,
        owner_id: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> HttpMailbox:
        """Create a new mailbox."""
        read_key = _generate_id(24)  # 24 bytes → 32 URL-safe chars

        with self._lock:
            if address is None:
                while True:
                    candidate = _generate_id(9)  # 9 bytes → 12 URL-safe chars
                    if candidate not in self._mailboxes:
                        address = candidate
                        break
            elif address in self._mailboxes:
                raise ValueError("Mailbox address already exists")

            if alias and alias in self._aliases:
                raise ValueError("Mailbox alias already exists")

            mailbox = HttpMailbox(
                address=address,
                read_key=read_key,
                owner_id=owner_id,
                alias=alias,
            )
            self._mailboxes[address] = mailbox
            if alias:
                self._aliases[alias] = address

        return mailbox

    def get_mailbox(self, address: str) -> Optional[HttpMailbox]:
        with self._lock:
            return self._mailboxes.get(address)

    def get_mailbox_by_alias(self, alias: str) -> Optional[HttpMailbox]:
        with self._lock:
            address = self._aliases.get(alias)
            if not address:
                return None
            return self._mailboxes.get(address)

    def get_mailboxes_for_owner(
        self,
        owner_id: str,
    ) -> Dict[str, HttpMailbox]:
        """Return burner aliases mapped to mailboxes for a given owner."""
        with self._lock:
            owned_mailboxes = {}
            for mailbox in self._mailboxes.values():
                if mailbox.owner_id == owner_id and mailbox.alias:
                    owned_mailboxes[mailbox.alias] = mailbox
            return owned_mailboxes

    def delete_mailbox(self, address: str, read_key: str) -> bool:
        """Delete entire mailbox after verifying read_key.

        Concurrency notes:
        - We remove the mailbox from the global store under `self._lock`.
        - We then overwrite and clear messages under the per-mailbox lock
          to avoid races with concurrent send/add operations.

        """
        # First, look up and authenticate the mailbox under the global lock.
        with self._lock:
            mailbox = self._mailboxes.get(address)
            if mailbox is None:
                return False
            if not secrets.compare_digest(read_key, mailbox.read_key):
                return False
            if mailbox.alias:
                self._aliases.pop(mailbox.alias, None)
            # Remove the mailbox from the global mapping while still holding
            # the storage lock so no new lookups can obtain it.
            del self._mailboxes[address]
            for alias, alias_address in list(self._aliases.items()):
                if alias_address == address:
                    del self._aliases[alias]

        # Now that the mailbox is no longer globally reachable, safely
        # overwrite and clear its messages under the per-mailbox lock.
        # This avoids data races on `mailbox.messages` with concurrent sends.
        lock = getattr(mailbox, "lock", None)
        if lock is not None:
            with lock:
                for msg in mailbox.messages:
                    msg.overwrite()
                # Clear the list so message objects can be GC'ed.
                mailbox.messages.clear()
                # Mark as destroyed so writers can refuse future sends.
                setattr(mailbox, "destroyed", True)
        else:
            # Fallback: no explicit mailbox lock available; still perform
            # overwrite/clear to maintain best-effort data scrubbing.
            for msg in mailbox.messages:
                msg.overwrite()
            mailbox.messages.clear()
            setattr(mailbox, "destroyed", True)

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


def generate_mailbox_alias() -> str:
    """Generate a human-shareable mailbox username."""
    adjective = secrets.choice(MAILBOX_ALIAS_ADJECTIVES)
    noun = secrets.choice(MAILBOX_ALIAS_NOUNS)
    suffix = f"{secrets.randbelow(10000):04d}"
    return f"{adjective}-{noun}-{suffix}"


# Global singleton
http_mail_storage = HttpMailStorage()
