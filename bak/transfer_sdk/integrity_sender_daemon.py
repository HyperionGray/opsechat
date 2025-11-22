from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn


class _DigestIndex:
    """In-memory index mapping sha256 -> path and cached window digests per ws."""

    def __init__(self) -> None:
        self.by_sha: Dict[str, Path] = {}
        self.by_ws: Dict[tuple[str, int], List[str]] = {}

    def register_file(self, path: Path) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    if not chunk:
                        break
                    h.update(chunk)
            digest = h.hexdigest()
        except Exception:
            return None
        self.by_sha[digest] = path
        return digest

    def get_path(self, sha256: str) -> Optional[Path]:
        return self.by_sha.get(sha256)

    def get_digests(self, sha256: str, ws: int) -> Optional[List[str]]:
        key = (sha256, int(ws))
        if key in self.by_ws:
            return self.by_ws[key]
        p = self.get_path(sha256)
        if not p or not p.exists():
            return None
        try:
            window_size = int(ws)
            data = p.read_bytes()
            total = (len(data) + window_size - 1) // window_size if window_size > 0 else 0
            out: List[str] = []
            for i in range(total):
                start = i * window_size
                end = min(start + window_size, len(data))
                h = hashlib.sha256()
                h.update(data[start:end])
                out.append(h.hexdigest())
            self.by_ws[key] = out
            return out
        except Exception:
            return None


class RepairRequest(BaseModel):
    sha256: str
    ws: int
    windows: List[int]
    receiver: Dict[str, object]


class RegisterRequest(BaseModel):
    path: str
    alias: Optional[str] = None


def create_app(index: _DigestIndex) -> FastAPI:
    app = FastAPI(title="FF3 Integrity Sender Daemon", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"]
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/integrity/{sha256}")
    async def get_integrity(sha256: str, ws: int):
        digs = index.get_digests(sha256, int(ws))
        if digs is None:
            raise HTTPException(status_code=404, detail="unknown sha")
        return {"sha256": sha256, "ws": int(ws), "windows": digs}

    @app.post("/repair")
    async def trigger_repair(req: RepairRequest):
        src = index.get_path(req.sha256)
        if not src or not src.exists():
            raise HTTPException(status_code=404, detail="source not found")
        # Receiver connection details
        recv = req.receiver or {}
        host_val = recv.get("host")
        host = str(host_val) if isinstance(host_val, str) and host_val else str(os.environ.get("FF3_REPAIR_ADDR", "127.0.0.1"))
        port_val = recv.get("port")
        if isinstance(port_val, (int, str)):
            try:
                port = int(port_val)
            except Exception:
                port = int(os.environ.get("FF3_REPAIR_PORT", "41004"))
        else:
            port = int(os.environ.get("FF3_REPAIR_PORT", "41004"))
        user = str(recv.get("user") or os.environ.get("FF3_USER", "user"))
        stored = str(recv.get("stored") or "")
        if not stored:
            raise HTTPException(status_code=400, detail="missing stored")
        # Use the helper from tools.repair_send
        from tools.repair_send import send_repairs
        ok = await send_repairs(host, port, source=src, user=user, stored=stored, ws=int(req.ws), windows=req.windows)
        return {"ok": bool(ok)}

    @app.post("/register")
    async def register(req: RegisterRequest):
        p = Path(req.path).expanduser()
        if not p.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        digest = index.register_file(p)
        if not digest:
            raise HTTPException(status_code=500, detail="failed to index file")
        return {"sha256": digest, "path": str(p)}

    return app


async def _watch_once(index: _DigestIndex, watch_dir: Path):
    for p in sorted(watch_dir.glob("*")):
        if p.is_file():
            index.register_file(p)


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(description="FF3 Integrity Sender Daemon")
    parser.add_argument("--watch", type=Path, default=None, help="Directory to watch and pre-index")
    parser.add_argument("--host", default=os.environ.get("FF3_INTEGRITY_SENDER_ADDR", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FF3_INTEGRITY_SENDER_PORT", "9352")))
    args = parser.parse_args(argv)

    index = _DigestIndex()
    if args.watch:
        args.watch.mkdir(parents=True, exist_ok=True)
        asyncio.run(_watch_once(index, args.watch))

    app = create_app(index)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
