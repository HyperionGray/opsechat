from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, List

from .config import BlobConfig, DEFAULT_BLOB_SEED, DEFAULT_BLOB_SIZE
from .encoding import TransferJob, TransferWindow, job_to_dict


def _to_int(value: object, default: int) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip() or str(default))
        except ValueError:
            return default
    return default


def job_from_dict(data: Dict[str, object]) -> TransferJob:
    blob_raw = data.get("blob")
    size_value = DEFAULT_BLOB_SIZE
    seed_value = DEFAULT_BLOB_SEED
    path_value = None
    if isinstance(blob_raw, dict):
        size_value = _to_int(blob_raw.get("size"), DEFAULT_BLOB_SIZE)
        seed_value = _to_int(blob_raw.get("seed"), DEFAULT_BLOB_SEED)
        path_value = blob_raw.get("path")
    blob_path = Path(path_value) if isinstance(path_value, str) and path_value else None
    cfg = BlobConfig(size=size_value, seed=seed_value, path=blob_path)

    windows_data = data.get("windows")
    window_entries = windows_data if isinstance(windows_data, list) else []
    windows: List[TransferWindow] = []
    for entry in window_entries:
        if not isinstance(entry, dict):
            continue
        idx = _to_int(entry.get("idx"), 0)
        raw_val = entry.get("raw")
        raw_str = str(raw_val) if raw_val is not None else None
        proto_val = entry.get("proto")
        proto_str = str(proto_val) if proto_val is not None else None
        bref_items = []
        refs = entry.get("bref")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict):
                    off_val = _to_int(ref.get("offset"), 0)
                    len_val = _to_int(ref.get("length"), 0)
                    flags_val = _to_int(ref.get("flags"), 0)
                    at_val = _to_int(ref.get("at"), 0)
                    bref_items.append({
                        "offset": off_val,
                        "length": len_val,
                        "flags": flags_val,
                        "at": at_val,
                    })
        windows.append(TransferWindow(idx=idx, bref=bref_items, raw=raw_str, proto=proto_str))
    return TransferJob(
        object_name=str(data.get("object_name", "object.bin")),
        object_size=_to_int(data.get("object_size"), 0),
        window_size=_to_int(data.get("window_size"), 65536),
        total_windows=_to_int(data.get("total_windows"), len(windows) or 1),
        blob=cfg,
        sha256=str(data.get("sha256", "")),
        windows=windows,
    )


def write_job_to_spool(job: TransferJob, spool_dir: Path | str) -> Path:
    """Write a job payload to the spool using a collision-resistant filename.

    Preferred base name is first 16 hex of job sha256; falls back to object name.
    If a file exists, appends -1, -2, ... until an unused name is found.
    """
    directory = Path(spool_dir)
    directory.mkdir(parents=True, exist_ok=True)
    payload = job_to_dict(job)
    base = job.sha256[:16] or job.object_name or "job"
    # Optionally include a short tenant/user tag derived from the encoded object_name (user%2f...)
    raw_name = getattr(job, "object_name", "") or ""
    decoded = raw_name.replace("%2f", "/")
    tenant = decoded.split("/", 1)[0] if decoded else ""
    if tenant:
        # sanitize tenant: keep alnum, dash, underscore, dot, limit length
        import re
        safe_tenant = re.sub(r"[^A-Za-z0-9._-]", "-", tenant)[:24]
        base = f"{base}-{safe_tenant}"
    candidate = directory / f"job_{base}.json"
    counter = 1
    while candidate.exists():
        candidate = directory / f"job_{base}-{counter}.json"
        counter += 1
    with tempfile.NamedTemporaryFile("w", dir=str(directory), delete=False) as tmp:
        json.dump(payload, tmp, separators=(",", ":"))
        temp_path = Path(tmp.name)
    temp_path.replace(candidate)
    return candidate


def load_job_from_spool(path: Path | str) -> TransferJob:
    source = Path(path)
    with source.open("r") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("invalid job payload")
    return job_from_dict(data)


def iter_spool_jobs(spool_dir: Path | str) -> List[Path]:
    directory = Path(spool_dir)
    if not directory.exists():
        return []
    return [path for path in sorted(directory.glob("job_*.json")) if path.is_file()]
