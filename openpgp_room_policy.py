"""
Closed-roster OpenPGP room policy helpers.

This module does not implement OpenPGP encryption itself. It defines the room
membership and receive-side validation rules for a small, pre-planned group
where every member must verify every other member out of band.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Dict, FrozenSet, Iterable, List, Sequence, Set, Tuple


_ALLOWED_FINGERPRINT_LENGTHS = {40, 64}
_HEX = set("0123456789ABCDEF")
_ROSTER_HASH_DOMAIN = "opsechat-roster-v1"


def normalize_fingerprint(value: str) -> str:
    """Normalize a fingerprint to uppercase hex without separators."""
    if not isinstance(value, str):
        raise TypeError("fingerprint must be a string")

    normalized = "".join(ch for ch in value.upper() if ch in _HEX)
    if len(normalized) not in _ALLOWED_FINGERPRINT_LENGTHS:
        raise ValueError(
            "fingerprint must be 40 or 64 hex characters after normalization"
        )
    return normalized


def _normalize_member_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("member_id must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("member_id must be non-empty")
    return normalized


@dataclass(frozen=True, order=True)
class RoomMember:
    """Application-level member identity bound to signing/encryption keys."""

    member_id: str
    signing_fingerprint: str
    encryption_fingerprint: str
    display_name: str = ""

    def __post_init__(self):
        object.__setattr__(self, "member_id", _normalize_member_id(self.member_id))
        object.__setattr__(
            self,
            "signing_fingerprint",
            normalize_fingerprint(self.signing_fingerprint),
        )
        object.__setattr__(
            self,
            "encryption_fingerprint",
            normalize_fingerprint(self.encryption_fingerprint),
        )
        if not self.display_name:
            object.__setattr__(self, "display_name", self.member_id)

    def canonical_line(self) -> str:
        """Return a deterministic line used in roster hashing."""
        return (
            f"{self.member_id}|"
            f"{self.signing_fingerprint}|"
            f"{self.encryption_fingerprint}"
        )


@dataclass(frozen=True)
class TrustedIdentity:
    """Locally observed identity state for a single application identifier."""

    member_id: str
    signing_fingerprint: str
    encryption_fingerprint: str
    verified: bool = False

    @classmethod
    def from_member(cls, member: RoomMember, verified: bool = False) -> "TrustedIdentity":
        return cls(
            member_id=member.member_id,
            signing_fingerprint=member.signing_fingerprint,
            encryption_fingerprint=member.encryption_fingerprint,
            verified=verified,
        )


@dataclass
class TrustStore:
    """
    Local trust state.

    Verification is intentionally local and pairwise. One device marking a
    member verified says nothing about any other device's trust decision.
    """

    identities: Dict[str, TrustedIdentity] = field(default_factory=dict)

    def observe(self, member: RoomMember) -> str:
        """
        Record first sight of a member identifier or detect a key change.

        Returns:
        - "new" when the identifier is first observed
        - "known" when the identifier matches the previously observed keys
        - "changed" when the identifier is known but the keys differ
        """
        existing = self.identities.get(member.member_id)
        if existing is None:
            self.identities[member.member_id] = TrustedIdentity.from_member(member)
            return "new"

        if (
            existing.signing_fingerprint != member.signing_fingerprint
            or existing.encryption_fingerprint != member.encryption_fingerprint
        ):
            return "changed"

        return "known"

    def mark_verified(self, member_id: str) -> None:
        member_id = _normalize_member_id(member_id)
        existing = self.identities.get(member_id)
        if existing is None:
            raise KeyError(f"member_id not found: {member_id}")

        self.identities[member_id] = TrustedIdentity(
            member_id=existing.member_id,
            signing_fingerprint=existing.signing_fingerprint,
            encryption_fingerprint=existing.encryption_fingerprint,
            verified=True,
        )

    def is_verified(self, member_or_id) -> bool:
        if isinstance(member_or_id, RoomMember):
            member_id = member_or_id.member_id
        else:
            member_id = _normalize_member_id(str(member_or_id))

        existing = self.identities.get(member_id)
        return bool(existing and existing.verified)

    def expected_identity(self, member_id: str) -> TrustedIdentity | None:
        return self.identities.get(_normalize_member_id(member_id))


def canonicalize_roster(members: Iterable[RoomMember]) -> Tuple[RoomMember, ...]:
    """Return a deterministic roster tuple and reject ambiguous duplicates."""
    canonical = tuple(
        sorted(
            set(members),
            key=lambda item: (
                item.signing_fingerprint,
                item.encryption_fingerprint,
                item.member_id,
            ),
        )
    )
    if not canonical:
        raise ValueError("roster must contain at least one member")

    member_ids = [member.member_id for member in canonical]
    if len(member_ids) != len(set(member_ids)):
        raise ValueError("member_id values must be unique within a roster")

    signing_fps = [member.signing_fingerprint for member in canonical]
    if len(signing_fps) != len(set(signing_fps)):
        raise ValueError("signing fingerprints must be unique within a roster")

    encryption_fps = [member.encryption_fingerprint for member in canonical]
    if len(encryption_fps) != len(set(encryption_fps)):
        raise ValueError("encryption fingerprints must be unique within a roster")

    return canonical


def hash_roster(members: Iterable[RoomMember]) -> str:
    """Hash a roster using a deterministic application-specific encoding."""
    canonical = canonicalize_roster(members)
    payload = _ROSTER_HASH_DOMAIN + "\n" + "\n".join(
        member.canonical_line() for member in canonical
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


@dataclass(frozen=True)
class RoomEpoch:
    """Closed roster state for one epoch of a room."""

    room_id: str
    epoch: int
    members: Tuple[RoomMember, ...]
    roster_hash: str = field(init=False)

    def __post_init__(self):
        room_id = _normalize_member_id(self.room_id)
        if self.epoch < 1:
            raise ValueError("epoch must be >= 1")

        canonical = canonicalize_roster(self.members)
        object.__setattr__(self, "room_id", room_id)
        object.__setattr__(self, "members", canonical)
        object.__setattr__(self, "roster_hash", hash_roster(canonical))

    def signing_fingerprints(self) -> FrozenSet[str]:
        return frozenset(member.signing_fingerprint for member in self.members)

    def encryption_fingerprints(self) -> FrozenSet[str]:
        return frozenset(member.encryption_fingerprint for member in self.members)

    def member_ids(self) -> FrozenSet[str]:
        return frozenset(member.member_id for member in self.members)

    def added_members(self, next_members: Sequence[RoomMember]) -> Tuple[RoomMember, ...]:
        current_ids = self.member_ids()
        canonical = canonicalize_roster(next_members)
        return tuple(member for member in canonical if member.member_id not in current_ids)

    def continuing_members(self, next_members: Sequence[RoomMember]) -> Tuple[RoomMember, ...]:
        """
        Return members that continue unchanged into the next epoch.

        These are the current-roster members who remain with the same member id
        and the same signing/encryption fingerprints. They are the members who
        can approve the next epoch transition without also being candidates for
        re-introduction.
        """
        canonical = canonicalize_roster(next_members)
        proposed_by_id = {member.member_id: member for member in canonical}
        return tuple(
            member
            for member in self.members
            if (
                proposed_by_id.get(member.member_id) is not None
                and proposed_by_id[member.member_id].signing_fingerprint
                == member.signing_fingerprint
                and proposed_by_id[member.member_id].encryption_fingerprint
                == member.encryption_fingerprint
            )
        )

    def introduced_members(self, next_members: Sequence[RoomMember]) -> Tuple[RoomMember, ...]:
        """
        Return proposed members that are new to the epoch or present new keys.

        This includes:
        - members not present in the current roster
        - existing member ids whose signing or encryption fingerprint changed
        """
        canonical = canonicalize_roster(next_members)
        current_by_id = {member.member_id: member for member in self.members}
        return tuple(
            member
            for member in canonical
            if (
                current_by_id.get(member.member_id) is None
                or current_by_id[member.member_id].signing_fingerprint
                != member.signing_fingerprint
                or current_by_id[member.member_id].encryption_fingerprint
                != member.encryption_fingerprint
            )
        )


@dataclass
class PendingRosterChange:
    """Proposed roster replacement that requires unanimous approval."""

    current_epoch: RoomEpoch
    proposed_members: Tuple[RoomMember, ...]
    approvals: Set[str] = field(default_factory=set)
    candidate_acks: Set[str] = field(default_factory=set)

    def __post_init__(self):
        self.proposed_members = canonicalize_roster(self.proposed_members)
        if self.current_epoch.room_id != self.proposed_epoch().room_id:
            raise ValueError("proposed epoch must use the same room_id")

    def proposed_epoch(self) -> RoomEpoch:
        return RoomEpoch(
            room_id=self.current_epoch.room_id,
            epoch=self.current_epoch.epoch + 1,
            members=self.proposed_members,
        )

    def added_members(self) -> Tuple[RoomMember, ...]:
        return self.current_epoch.added_members(self.proposed_members)

    def introduced_members(self) -> Tuple[RoomMember, ...]:
        return self.current_epoch.introduced_members(self.proposed_members)

    def removed_member_ids(self) -> FrozenSet[str]:
        proposed_ids = {member.member_id for member in self.proposed_members}
        return frozenset(
            member.member_id
            for member in self.current_epoch.members
            if member.member_id not in proposed_ids
        )

    def required_approvers(self) -> FrozenSet[str]:
        return frozenset(
            member.signing_fingerprint
            for member in self.current_epoch.continuing_members(self.proposed_members)
        )

    def required_candidate_acks(self) -> FrozenSet[str]:
        return frozenset(member.signing_fingerprint for member in self.introduced_members())

    def approve(self, approver_signing_fingerprint: str, trust_store: TrustStore) -> None:
        approver = normalize_fingerprint(approver_signing_fingerprint)
        if approver not in self.required_approvers():
            raise ValueError("approver is not a current roster member")

        for member in self.introduced_members():
            if not trust_store.is_verified(member.member_id):
                raise ValueError(
                    f"cannot approve roster change; added member is not locally verified: {member.member_id}"
                )

        self.approvals.add(approver)

    def acknowledge_candidate(self, candidate_signing_fingerprint: str) -> None:
        candidate = normalize_fingerprint(candidate_signing_fingerprint)
        if candidate not in self.required_candidate_acks():
            raise ValueError("candidate is not part of the added-member set")
        self.candidate_acks.add(candidate)

    def ready_to_activate(self) -> bool:
        return (
            self.approvals == set(self.required_approvers())
            and self.candidate_acks == set(self.required_candidate_acks())
        )

    def activate(self) -> RoomEpoch:
        if not self.ready_to_activate():
            raise ValueError("roster change is not fully approved")
        return self.proposed_epoch()


@dataclass(frozen=True)
class MessageEnvelopeMetadata:
    """Signed/validated metadata required to accept a room message."""

    room_id: str
    epoch: int
    sender_signing_fingerprint: str
    roster_hash: str
    recipient_encryption_fingerprints: FrozenSet[str]
    intended_recipient_fingerprints: FrozenSet[str] = frozenset()
    anonymous_recipients: bool = False
    decryption_ok: bool = False
    integrity_ok: bool = False
    signature_ok: bool = False

    def __post_init__(self):
        object.__setattr__(self, "room_id", _normalize_member_id(self.room_id))
        object.__setattr__(
            self,
            "sender_signing_fingerprint",
            normalize_fingerprint(self.sender_signing_fingerprint),
        )
        object.__setattr__(
            self,
            "recipient_encryption_fingerprints",
            frozenset(
                normalize_fingerprint(fingerprint)
                for fingerprint in self.recipient_encryption_fingerprints
            ),
        )
        object.__setattr__(
            self,
            "intended_recipient_fingerprints",
            frozenset(
                normalize_fingerprint(fingerprint)
                for fingerprint in self.intended_recipient_fingerprints
            ),
        )


@dataclass(frozen=True)
class MessageValidationResult:
    accepted: bool
    errors: Tuple[str, ...] = ()


def validate_message_for_epoch(
    epoch: RoomEpoch,
    envelope: MessageEnvelopeMetadata,
    local_encryption_fingerprint: str,
) -> MessageValidationResult:
    """
    Validate receive-side policy for a closed-roster room message.

    This function intentionally fails closed. A message is rejected unless the
    cryptographic checks succeeded and the envelope metadata matches the room
    epoch exactly.
    """
    local_fp = normalize_fingerprint(local_encryption_fingerprint)
    expected_recipients = epoch.encryption_fingerprints()
    errors: List[str] = []

    if envelope.room_id != epoch.room_id:
        errors.append("room_id mismatch")
    if envelope.epoch != epoch.epoch:
        errors.append("epoch mismatch")
    if envelope.roster_hash != epoch.roster_hash:
        errors.append("roster hash mismatch")
    if envelope.sender_signing_fingerprint not in epoch.signing_fingerprints():
        errors.append("sender is not part of the roster")
    if local_fp not in expected_recipients:
        errors.append("local recipient is not part of the roster")
    if local_fp not in envelope.recipient_encryption_fingerprints:
        errors.append("message was not encrypted to the local recipient")
    if envelope.anonymous_recipients:
        errors.append("anonymous recipients are forbidden")
    if envelope.recipient_encryption_fingerprints != expected_recipients:
        errors.append("recipient set does not match the room roster")
    if (
        envelope.intended_recipient_fingerprints
        and envelope.intended_recipient_fingerprints != expected_recipients
    ):
        errors.append("intended recipient fingerprints do not match the room roster")
    if not envelope.decryption_ok:
        errors.append("message decryption failed")
    if not envelope.integrity_ok:
        errors.append("message integrity check failed")
    if not envelope.signature_ok:
        errors.append("message signature verification failed")

    return MessageValidationResult(accepted=not errors, errors=tuple(errors))
