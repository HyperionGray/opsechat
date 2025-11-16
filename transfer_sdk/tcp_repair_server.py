from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from app.state import load_config

# Optional PSK for repair
PSK_EXPECTED = os.environ.get("FF3_REPAIR_PSK")


async def _patch_windows(path: Path, ws: int, reader: asyncio.StreamReader) -> None:
    # Simple binary framing: [idx(4)][len(4)][payload]
    def _read_u32(b: bytes) -> int:
        return int.from_bytes(b, "big", signed=False)

    # Ensure file exists; open r+b, creating if missing
    path.parent.mkdir(parents=True, exist_ok=True)
    f = None
    try:
        f = path.open("r+b") if path.exists() else path.open("w+b")
        while True:
            hdr = await reader.readexactly(8)
            if not hdr:
                break
            idx = _read_u32(hdr[:4])
            ln = _read_u32(hdr[4:8])
            if ln <= 0:
                # zero-length sentinel: stop
                break
            payload = await reader.readexactly(ln)
            # Patch at offset idx * ws
            off = int(idx) * int(ws)
            f.seek(off)
            f.write(payload)
    except asyncio.IncompleteReadError:
        # Connection closed; treat as normal end
        pass
    finally:
        if f is not None:
            f.flush()
            f.close()


async def handle_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    try:
        # First line: JSON header
        head_line = await reader.readline()
        if not head_line:
            writer.close(); await writer.wait_closed(); return
        try:
            head = json.loads(head_line.decode("utf-8").strip())
        except Exception:
            writer.write(b"ERR invalid header\n"); await writer.drain(); writer.close(); await writer.wait_closed(); return
        # PSK
        if PSK_EXPECTED is not None:
            if str(head.get("psk") or "") != PSK_EXPECTED:
                writer.write(b"ERR unauthorized\n"); await writer.drain(); writer.close(); await writer.wait_closed(); return
        user = (head.get("user") or "user").strip().split("/")[0]
        stored = (head.get("stored") or head.get("name") or "").strip()
        ws = int(head.get("ws") or 0)
        if not stored or ws <= 0:
            writer.write(b"ERR bad request\n"); await writer.drain(); writer.close(); await writer.wait_closed(); return
        # Resolve target path in inbox
        cfg = load_config()
        from api.api import _encode_path as enc
        encoded = enc(f"{user}/{stored}")
        target = cfg.inbox_dir / encoded
        await _patch_windows(target, ws, reader)
        writer.write(b"OK\n"); await writer.drain()
    except Exception:
        try:
            writer.write(b"ERR internal\n"); await writer.drain()
        except Exception:
            pass
    try:
        writer.close(); await writer.wait_closed()
    except Exception:
        pass


async def run(host: str, port: int):
    server = await asyncio.start_server(handle_conn, host=host, port=port)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[repaird] listening on {addrs}")
    async with server:
        await server.serve_forever()


def main():
    host = os.environ.get("FF3_REPAIR_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_REPAIR_PORT", "41004"))
    try:
        asyncio.run(run(host, port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
