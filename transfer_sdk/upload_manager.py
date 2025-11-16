from __future__ import annotations

import json
from dataclasses import dataclass
import os
import json
from pathlib import Path
from typing import AsyncIterator

from .blob import load_blob, VirtualBlob
from .config import TransferSettings, make_blob_config
from .encoding import TransferJob, build_job, job_to_dict
from .pathutils import ensure_unique_path, sanitize_filename
from .spool import write_job_to_spool


class UploadError(Exception):
    """Base class for upload-related failures."""


class UploadTooLarge(UploadError):
    """Raised when an upload exceeds the configured size limit."""


@dataclass
class UploadResult:
    filename: str
    bytes_written: int
    stored_path: Path
    job_path: Path | None
    job: TransferJob
    bref_path: Path | None = None

    def summary(self) -> dict:
        return {
            "filename": self.filename,
            "bytes_written": self.bytes_written,
            "stored_path": str(self.stored_path),
            "job": {
                "object_name": self.job.object_name,
                "object_size": self.job.object_size,
                "total_windows": self.job.total_windows,
                "window_size": self.job.window_size,
                "sha256": self.job.sha256,
                "spool_path": str(self.job_path) if self.job_path else None,
            },
            "original_size": self.job.object_size,
            "compressed_size": self.job.object_size,
            "compression_ratio": 1.0,
            "compression_percent": "0%",
            "queued": self.job_path is not None,
            "bref_path": str(self.bref_path) if self.bref_path else None,
        }


class TransferIngestor:
    """High-level helper for storing uploads and queuing transfer jobs."""

    def __init__(self, settings: TransferSettings) -> None:
        self.settings = settings
        self._virtual_blob: VirtualBlob | None = None
        self._blob_config = None

    def ensure_ready(self) -> None:
        self.settings.ensure_directories()

    def _get_blob_config(self):
        if self._blob_config is None:
            self._blob_config = make_blob_config(
                self.settings.blob_size,
                self.settings.blob_seed,
                self.settings.blob_path,
            )
        return self._blob_config

    def _get_blob(self) -> VirtualBlob:
        if self._virtual_blob is None:
            self._virtual_blob = load_blob(self._get_blob_config())
        return self._virtual_blob

    def _build_job(self, path: Path) -> TransferJob:
        blob = self._get_blob()
        return build_job(
            path,
            blob,
            window_size=self.settings.window_size,
            blob_config=self._get_blob_config(),
        )

    def _queue_job(self, job: TransferJob) -> Path:
        return write_job_to_spool(job, self.settings.spool_dir)

    def _write_bref_snapshot(self, job: TransferJob, target: Path) -> Path:
        """Persist a manifest of the job's windowed representation.

        Historically this wrote a .bref file; we now prefer a compact .ff3job
        manifest (still returned as bref_path for backward compatibility).
        """
        manifest = job_to_dict(job)
        manifest["virtual"] = True
        # Prefer .ff3job extension; keep legacy .bref if env forces it.
        use_legacy = os.environ.get("FF3_LEGACY_BREF", "0") in {"1", "true", "TRUE"}
        ext = ".bref" if use_legacy else ".ff3job"
        destination = target.with_name(f"{target.name}{ext}")
        destination.write_text(json.dumps(manifest, separators=(",", ":")))
        return destination

    async def ingest_stream(self, filename: str, chunks: AsyncIterator[bytes]) -> UploadResult:
        safe_name = sanitize_filename(filename)
        target = ensure_unique_path(self.settings.inbox_dir, safe_name)
        total = 0

        self.ensure_ready()

        try:
            with target.open("wb") as handle:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self.settings.max_upload_bytes:
                        raise UploadTooLarge(
                            f"upload exceeds {self.settings.max_upload_bytes} bytes limit"
                        )
                    handle.write(chunk)
        except UploadTooLarge:
            target.unlink(missing_ok=True)
            raise
        except Exception as exc:  # pragma: no cover - safety net
            target.unlink(missing_ok=True)
            raise UploadError("failed to persist upload") from exc

        job = self._build_job(target)
        bref_path = self._write_bref_snapshot(job, target)
        vfs_mode = os.environ.get("FF3_VFS_MODE", "windowed").lower()
        store_original = vfs_mode not in {"windowed", "manifest", "virtual"}
        if not store_original:
            # Remove original payload to preserve space; leave only manifest representation.
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass  # non-fatal
        return UploadResult(
            filename=target.name,
            bytes_written=total,
            stored_path=target if store_original else bref_path,
            job_path=None,
            job=job,
            bref_path=bref_path,
        )

    def build_job_for_path(self, path: Path) -> UploadResult:
        self.ensure_ready()
        job = self._build_job(path)
        job_path = self._queue_job(job)
        bref_path = self._write_bref_snapshot(job, path)
        vfs_mode = os.environ.get("FF3_VFS_MODE", "windowed").lower()
        store_original = vfs_mode not in {"windowed", "manifest", "virtual"}
        if not store_original:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        return UploadResult(
            filename=path.name,
            bytes_written=path.stat().st_size if store_original else job.object_size,
            stored_path=path if store_original else bref_path,
            job_path=job_path,
            job=job,
            bref_path=bref_path,
        )
