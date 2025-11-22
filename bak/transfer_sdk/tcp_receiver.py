from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Tuple

from app.state import load_config
from transfer_sdk.upload_manager import TransferIngestor
from transfer_sdk.config import TransferSettings


VIRTUAL_SEP = "%2f"


def _encode_path(path: str) -> str:
    cleaned = path.strip().strip("/")
    return cleaned.replace("/", VIRTUAL_SEP) if cleaned else ""


def _append_suffix(name: str) -> str:
    p = Path(name)
    stem, suffix = p.stem, p.suffix
    if not stem:
        return name
    import re
    m = re.match(r"^(.*)-(\d+)$", stem)
    if m:
        base, num = m.group(1), int(m.group(2)) + 1
        return f"{base}-{num}{suffix}"
    return f"{stem}-1{suffix}"


def _unique_target(root: Path, encoded: str) -> Path:
    candidate = root / encoded
    while candidate.exists():
        parts = encoded.split(VIRTUAL_SEP)
        if parts:
            parts[-1] = _append_suffix(parts[-1])
        encoded = VIRTUAL_SEP.join(parts)
        candidate = root / encoded
    return candidate


class TCPIngestServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 41001) -> None:
        self.host = host
        self.port = port
        self.cfg = load_config()
        # Initialize ingestor similar to API
        blob_path = self.cfg.blob_path if self.cfg.blob_path else None
        blob_size = (
            blob_path.stat().st_size if blob_path and blob_path.exists() else 4 * 1024 * 1024
        )
        settings = TransferSettings(
            inbox_dir=self.cfg.inbox_dir,
            spool_dir=self.cfg.spool_dir,
            outbox_dir=self.cfg.outbox_dir,
            window_size=self.cfg.window_size,
            blob_size=blob_size,
            blob_path=blob_path,
        )
        self.ingestor = TransferIngestor(settings)
        self.ingestor.ensure_ready()

    async def handle_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        try:
            header_line = await reader.readline()
            if not header_line:
                writer.close()
                await writer.wait_closed()
                return
            try:
                header = json.loads(header_line.decode("utf-8").strip())
            except Exception:
                writer.write(b"ERR invalid header\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # Optional shared secret for basic protection
            secret = os.environ.get("FF3_TCP_SECRET")
            if secret:
                if header.get("secret") != secret:
                    writer.write(b"ERR unauthorized\n")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

            user = (header.get("user") or "user").strip().split("/")[0]
            vpath = (header.get("virtual_path") or header.get("name") or "").strip().strip("/")
            total = int(header.get("size") or 0)
            if not vpath or total <= 0:
                writer.write(b"ERR bad request\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            full_virtual = "/".join([user, vpath])
            encoded = _encode_path(full_virtual)
            target = _unique_target(self.cfg.inbox_dir, encoded)
            target.parent.mkdir(parents=True, exist_ok=True)

            remaining = total
            with target.open("wb") as f:
                while remaining > 0:
                    chunk = await reader.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)

            if remaining != 0:
                try:
                    target.unlink()
                except Exception:
                    pass
                writer.write(b"ERR incomplete\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # Queue job build without blocking the event loop
            await asyncio.to_thread(self.ingestor.build_job_for_path, target)
            writer.write(b"OK\n")
            await writer.drain()
        except Exception:
            try:
                writer.write(b"ERR internal\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def run(self):
        server = await asyncio.start_server(self.handle_conn, self.host, self.port)
        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
        print(f"[tcp-receiver] listening on {addrs}")
        async with server:
            await server.serve_forever()


def main():
    host = os.environ.get("FF3_TCP_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_TCP_PORT", "41001"))
    srv = TCPIngestServer(host=host, port=port)
    asyncio.run(srv.run())


if __name__ == "__main__":
    main()
