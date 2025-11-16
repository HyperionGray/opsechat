from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from app.state import load_config
from transfer_sdk.blob import load_blob
from transfer_sdk.spool import job_from_dict
from transfer_sdk.streaming import reconstruct_window_payload


def _decode_encoded_base(manifest_path: Path) -> tuple[str, str]:
    """Return (user, stored_relative_path) from encoded manifest filename.

    The manifest file is <inbox>/<encoded>.ff3job where encoded represents
    user/path components joined with %2f. We decode and split the first segment
    as the user; the remainder (possibly empty) is the stored path.
    """
    from api.api import _decode_name  # reuse helpers
    enc = manifest_path.stem  # remove .ff3job
    decoded = _decode_name(enc)
    parts = decoded.split("/") if decoded else []
    user = parts[0] if parts else "user"
    stored = "/".join(parts[1:]) if len(parts) > 1 else ""
    return user, stored or manifest_path.stem  # fallback to encoded when empty


async def compute_window_hashes(manifest_path: Path) -> tuple[str, int, List[str]]:
    """Load job manifest and compute sha256 per window via reconstruction.

    Returns (job_sha256, window_size, digests).
    """
    data = json.loads(manifest_path.read_text("utf-8"))
    job = job_from_dict(data)
    blob = load_blob(job.blob)
    blob.ensure_loaded()
    digs: List[str] = []
    def _win_len(i: int) -> int:
        if i < job.total_windows - 1:
            return job.window_size
        return max(0, int(job.object_size) - job.window_size * (job.total_windows - 1))
    for w in job.windows:
        try:
            idx = int(getattr(w, "idx", 0))
        except Exception:
            idx = 0
        payload = reconstruct_window_payload(w, blob, _win_len(idx))
        import hashlib as _h
        h = _h.sha256()
        h.update(payload)
        digs.append(h.hexdigest())
    return job.sha256, job.window_size, digs


async def process_once(sender_url: str, repair_host: str, repair_port: int, manifests: List[Path]) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        for m in manifests:
            try:
                sha, ws, local_digs = await compute_window_hashes(m)
                r = await client.get(f"{sender_url}/integrity/{sha}", params={"ws": ws})
                if r.status_code != 200:
                    continue  # sender not ready; try later
                remote = r.json()
                remote_digs: List[str] = list(remote.get("windows") or [])
                need: List[int] = []
                for i, d in enumerate(local_digs):
                    if i >= len(remote_digs) or d != str(remote_digs[i]):
                        need.append(i)
                if not need:
                    continue
                user, stored = _decode_encoded_base(m)
                req = {
                    "sha256": sha,
                    "ws": ws,
                    "windows": need,
                    "receiver": {
                        "host": repair_host,
                        "port": repair_port,
                        "user": user,
                        "stored": stored,
                    },
                }
                await client.post(f"{sender_url}/repair", json=req)
            except Exception:
                continue


async def run_forever(sender_url: str, interval: float = 2.0) -> None:
    cfg = load_config()
    inbox = cfg.inbox_dir
    seen: Dict[Path, float] = {}
    repair_host = os.environ.get("FF3_REPAIR_ADDR", "127.0.0.1")
    repair_port = int(os.environ.get("FF3_REPAIR_PORT", "41004"))
    while True:
        manifests = []
        try:
            for p in sorted(inbox.glob("*.ff3job")):
                try:
                    mt = p.stat().st_mtime
                except OSError:
                    continue
                if p not in seen or seen[p] < mt:
                    seen[p] = mt
                    manifests.append(p)
        except Exception:
            manifests = []
        if manifests:
            await process_once(sender_url, repair_host, repair_port, manifests)
        await asyncio.sleep(interval)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="FF3 Integrity Receiver Daemon")
    parser.add_argument("--sender-url", default=os.environ.get("FF3_SENDER_INTEGRITY_URL", "http://127.0.0.1:9352"))
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        asyncio.run(run_forever(args.sender_url, interval=args.interval))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
