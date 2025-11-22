from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_WINDOW_SIZE = 64 * 1024
DEFAULT_BLOB_SIZE = 4 * 1024 * 1024  # 4 MiB keeps samples light
DEFAULT_BLOB_SEED = 1337

# Encoder tuning knobs (overridable via env for experimentation)
DEFAULT_MIN_MATCH = int(os.getenv("PFS_MIN_MATCH", "8"))          # minimum run length to reference blob
DEFAULT_MAX_CANDIDATES = int(os.getenv("PFS_MAX_CANDIDATES", "16"))  # cap for candidate offsets per probe


@dataclass(frozen=True)
class BlobConfig:
    size: int = DEFAULT_BLOB_SIZE
    seed: int = DEFAULT_BLOB_SEED
    path: Path | None = None


def make_blob_config(size: int | None = None, seed: int | None = None, path: Path | None = None) -> BlobConfig:
    resolved_path = Path(path) if path else None
    if resolved_path and resolved_path.exists():
        computed_size = resolved_path.stat().st_size
    else:
        computed_size = size or DEFAULT_BLOB_SIZE
    return BlobConfig(
        size=computed_size,
        seed=seed or DEFAULT_BLOB_SEED,
        path=resolved_path,
    )


def _coerce_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class TransferSettings:
    """Runtime paths and tunables for the web/demo stack."""

    inbox_dir: Path
    spool_dir: Path
    outbox_dir: Path
    window_size: int = DEFAULT_WINDOW_SIZE
    blob_size: int = DEFAULT_BLOB_SIZE
    blob_seed: int = DEFAULT_BLOB_SEED
    blob_path: Path | None = None
    max_upload_bytes: int = 512 * 1024 * 1024  # 512 MiB default upload limit
    upload_chunk_bytes: int = 1 * 1024 * 1024  # Read 1 MiB at a time from uploads

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "TransferSettings":
        namespace = env or os.environ
        root = Path(namespace.get("TRANSFER_SDK_ROOT", "/tmp/sdk-demo"))
        inbox = Path(namespace.get("TRANSFER_SDK_INBOX", str(root / "inbox")))
        spool = Path(namespace.get("TRANSFER_SDK_SPOOL", str(root / "spool")))
        outbox = Path(namespace.get("TRANSFER_SDK_OUTBOX", str(root / "outbox")))

        window = _coerce_int(namespace.get("TRANSFER_SDK_WINDOW_SIZE"), DEFAULT_WINDOW_SIZE)
        blob_size = _coerce_int(namespace.get("TRANSFER_SDK_BLOB_SIZE"), DEFAULT_BLOB_SIZE)
        blob_seed = _coerce_int(namespace.get("TRANSFER_SDK_BLOB_SEED"), DEFAULT_BLOB_SEED)
        max_upload = _coerce_int(namespace.get("TRANSFER_SDK_MAX_UPLOAD"), 512 * 1024 * 1024)
        chunk_size = _coerce_int(namespace.get("TRANSFER_SDK_UPLOAD_CHUNK"), 1 * 1024 * 1024)
        blob_path_value = namespace.get("TRANSFER_SDK_BLOB_PATH")
        default_blob_path = Path(__file__).resolve().parent.parent / "artifacts" / "pfs-blob.bin"
        blob_path = Path(blob_path_value) if blob_path_value else (default_blob_path if default_blob_path.exists() else None)
        if blob_path and blob_path.exists():
            blob_size = blob_path.stat().st_size

        return cls(
            inbox_dir=inbox,
            spool_dir=spool,
            outbox_dir=outbox,
            window_size=window,
            blob_size=blob_size,
            blob_seed=blob_seed,
            blob_path=blob_path,
            max_upload_bytes=max_upload,
            upload_chunk_bytes=max(64 * 1024, chunk_size),  # enforce sensible minimum
        )

    def ensure_directories(self) -> None:
        for path in (self.inbox_dir, self.spool_dir, self.outbox_dir):
            path.mkdir(parents=True, exist_ok=True)
