from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Iterable, List


async def send_repairs(host: str, port: int, *, source: Path, user: str, stored: str, ws: int, windows: Iterable[int]) -> bool:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    reader, writer = await asyncio.open_connection(host, port)
    try:
        header = {"user": user, "stored": stored, "ws": int(ws)}
        psk = os.environ.get("FF3_REPAIR_PSK")
        if psk:
            header["psk"] = psk
        writer.write((json.dumps(header) + "\n").encode("utf-8"))
        await writer.drain()
        data = source.read_bytes()
        for idx in windows:
            i = int(idx)
            start = i * ws
            end = min(start + ws, len(data))
            chunk = data[start:end]
            # frame: idx(4) len(4) payload
            writer.write(i.to_bytes(4, "big"))
            writer.write(len(chunk).to_bytes(4, "big"))
            writer.write(chunk)
            await writer.drain()
        # send zero-length sentinel
        writer.write((0).to_bytes(4, "big"))
        writer.write((0).to_bytes(4, "big"))
        await writer.drain()
        # read response
        resp = await asyncio.wait_for(reader.readline(), timeout=5.0)
        return resp.decode("utf-8", "ignore").strip().upper().startswith("OK")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description="Send per-window repair frames to FF3 repair daemon")
    p.add_argument("source", type=Path, help="Path to original file")
    p.add_argument("stored", type=str, help="Effective stored filename on receiver (from NACK)")
    p.add_argument("ws", type=int, help="Window size")
    p.add_argument("windows", type=int, nargs="+", help="Window indices to send")
    p.add_argument("--host", default=os.environ.get("FF3_REPAIR_ADDR", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("FF3_REPAIR_PORT", "41004")))
    p.add_argument("--user", default=os.environ.get("FF3_USER", "user"))
    args = p.parse_args()

    ok = asyncio.run(send_repairs(args.host, args.port, source=args.source, user=args.user, stored=args.stored, ws=args.ws, windows=args.windows))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
