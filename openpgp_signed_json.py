"""
Helpers for verifying OpenPGP clearsigned JSON statements with gpg.

The room-transition flow uses small, signed JSON statements for proposals,
approvals, candidate acknowledgements, and activations. The browser creates
those statements with OpenPGP.js and the server verifies them with the local
`gpg` binary before mutating room state.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Iterable, Mapping

from openpgp_room_policy import normalize_fingerprint


PGP_SIGNED_MESSAGE_BEGIN = "-----BEGIN PGP SIGNED MESSAGE-----"
PGP_SIGNATURE_BEGIN = "-----BEGIN PGP SIGNATURE-----"
PGP_SIGNATURE_END = "-----END PGP SIGNATURE-----"
MAX_SIGNED_STATEMENT_LENGTH = 262144


def has_gpg() -> bool:
    """Return True when a usable gpg binary is available."""
    return bool(shutil.which("gpg"))


def normalize_signed_statement(value: object, field_name: str = "signed_statement") -> str:
    """Validate a clearsigned OpenPGP statement."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if len(normalized) > MAX_SIGNED_STATEMENT_LENGTH:
        raise ValueError(
            f"{field_name} must be <= {MAX_SIGNED_STATEMENT_LENGTH} characters"
        )
    if PGP_SIGNED_MESSAGE_BEGIN not in normalized:
        raise ValueError(f"{field_name} must contain an armored signed message")
    if PGP_SIGNATURE_BEGIN not in normalized or PGP_SIGNATURE_END not in normalized:
        raise ValueError(f"{field_name} must contain an OpenPGP signature block")
    return normalized


def verify_clearsigned_json(
    signed_statement: object,
    expected_signer_fingerprint: str,
    public_key_armored_blocks: Iterable[str],
) -> dict:
    """
    Verify a clearsigned JSON statement and return its payload.

    Args:
        signed_statement: Armored clearsigned OpenPGP message.
        expected_signer_fingerprint: Fingerprint that must appear in the
            `VALIDSIG` status line from gpg.
        public_key_armored_blocks: Armored public keys that allow gpg to verify
            the statement signature.
    """
    if not has_gpg():
        raise RuntimeError("gpg is not available; signed room statements are unsupported")

    statement = normalize_signed_statement(signed_statement)
    expected_fp = normalize_fingerprint(expected_signer_fingerprint)
    public_keys = [str(block).strip() for block in public_key_armored_blocks if str(block).strip()]
    if not public_keys:
        raise ValueError("no public keys were provided for statement verification")

    gpg = shutil.which("gpg")
    if not gpg:
        raise RuntimeError("gpg is not available; signed room statements are unsupported")

    with tempfile.TemporaryDirectory(prefix="opsechat-gpg-verify-") as homedir:
        os.chmod(homedir, 0o700)
        key_path = os.path.join(homedir, "keys.asc")
        statement_path = os.path.join(homedir, "statement.asc")
        plaintext_path = os.path.join(homedir, "statement.json")

        with open(key_path, "w", encoding="utf-8") as handle:
            handle.write("\n\n".join(public_keys))
            handle.write("\n")

        with open(statement_path, "w", encoding="utf-8") as handle:
            handle.write(statement)
            handle.write("\n")

        import_proc = subprocess.run(
            [gpg, "--batch", "--yes", "--homedir", homedir, "--import", key_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if import_proc.returncode != 0:
            raise ValueError("could not import public keys for statement verification")

        verify_proc = subprocess.run(
            [
                gpg,
                "--batch",
                "--yes",
                "--homedir",
                homedir,
                "--status-fd",
                "1",
                "--output",
                plaintext_path,
                "--decrypt",
                statement_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if verify_proc.returncode != 0:
            raise ValueError("signed statement verification failed")

        valid_signers = []
        for line in verify_proc.stdout.splitlines():
            if line.startswith("[GNUPG:] VALIDSIG "):
                parts = line.split()
                if len(parts) >= 3:
                    valid_signers.append(parts[2].upper())

        if len(valid_signers) != 1:
            raise ValueError("signed statement must have exactly one valid signature")
        if valid_signers[0] != expected_fp:
            raise ValueError("signed statement fingerprint mismatch")

        with open(plaintext_path, "r", encoding="utf-8") as handle:
            try:
                payload = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError("signed statement payload is not valid JSON") from exc

    if not isinstance(payload, Mapping):
        raise ValueError("signed statement payload must be a JSON object")
    return dict(payload)
