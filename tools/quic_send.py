from __future__ import annotations

import asyncio
import os
from typing import Optional, List, Dict, Any


def _frames_from_bref_json(bref_obj: Any, user: str, name: str, default_ws: int) -> List[Dict[str, Any]]:
    import math
    frames: List[Dict[str, Any]] = []
    ws = int(default_ws)
    # Accept shapes: {windows:[{i,c}], ws?, user?, name?} | [{i,c}] | {c:[...]} (single window 0)
    if isinstance(bref_obj, dict) and "windows" in bref_obj:
        ws = int(bref_obj.get("ws", ws) or ws)
        user = str(bref_obj.get("user", user) or user)
        name = str(bref_obj.get("name", name) or name)
        windows = list(bref_obj.get("windows") or [])
    elif isinstance(bref_obj, list):
        windows = [{"i": 0, "c": bref_obj}]
    elif isinstance(bref_obj, dict) and "c" in bref_obj:
        windows = [{"i": int(bref_obj.get("i", 0)), "c": list(bref_obj.get("c") or [])}]
    else:
        raise ValueError("Unsupported BREF JSON format")

    frames.append({"t": "PREF", "user": user, "name": name, "ws": ws})
    for w in windows:
        idx = int(w.get("i", 0))
        chunks = [(int(a), int(b)) for (a, b) in (w.get("c") or [])]
        frames.append({"t": "WIN", "i": idx})
        frames.append({"t": "BREF", "c": chunks})
        frames.append({"t": "END"})
    frames.append({"t": "DONE"})
    return frames


async def send_quic_bytes(host: str, port: int, payload: bytes, *, name: str = "quic-object.bin", user: str = "user", bref_json: Optional[str] = None) -> bytes:
    """Send NDJSON BREF-only QUIC payload matching the simplified receiver.

    Format (newline-delimited JSON objects):
      {"t":"PREF","user":"...","name":"...","ws":<int>}\n
      {"t":"WIN","i":0}\n
      {"t":"BREF","c":[[offset,length],...]}   # offsets absolute into shared blob
      {"t":"END"}\n
      {"t":"DONE"}\n
    We do not send RAW unless FF3_QUIC_ALLOW_RAW is enabled server-side.
    """
    # For demo, treat entire payload literal as RAW fallback by embedding bytes directly if requested.
    # But since we prioritize BREF and we don't have offset mapping for arbitrary user bytes, we simulate by writing RAW.
    allow_raw = os.environ.get("FF3_QUIC_ALLOW_RAW", "0") in ("1","true","TRUE","True")
    import base64 as _b64
    import json as _json

    ws = max(1024, min(65536, len(payload) or 1024))
    psk = os.environ.get("FF3_QUIC_PSK")
    if bref_json:
        with open(bref_json, "r", encoding="utf-8") as f:
            bref_obj = _json.load(f)
        lines = _frames_from_bref_json(bref_obj, user=user, name=name, default_ws=ws)
        if psk and isinstance(lines, list) and lines and isinstance(lines[0], dict) and lines[0].get("t") == "PREF":
            lines[0]["psk"] = psk
        # Keep sender lean; no MFST/digest list here
    else:
        lines = []
        pref = {"t":"PREF","user":user,"name":name,"ws":ws}
        if psk:
            pref["psk"] = psk
        lines.append(pref)
        # No MFST; integrity handled by background daemons
        lines.append({"t":"WIN","i":0})
        if allow_raw:
            b64 = _b64.b64encode(payload).decode("ascii")
            lines.append({"t":"RAW","p":b64})
        else:
            lines.append({"t":"BREF","c":[]})
        lines.append({"t":"END"})
        lines.append({"t":"DONE"})

    import json as _json
    ndjson = "\n".join(_json.dumps(o, separators=(",",":"), ensure_ascii=False) for o in lines) + "\n"

    # Lazy import to avoid hard dependency errors when tool isn't used
    from aioquic.asyncio import connect
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.connection import QuicConnection

    config = QuicConfiguration(is_client=True, alpn_protocols=["pfs-arith"], verify_mode=False)
    async with connect(host, port, configuration=config) as client:
        quic: QuicConnection = client._quic  # type: ignore
        sid = quic.get_next_available_stream_id()
        client._quic.send_stream_data(sid, ndjson.encode("utf-8"), end_stream=True)  # type: ignore
        if hasattr(client, "_network_changed"):
            await client._network_changed()  # type: ignore[attr-defined]
        else:
            await asyncio.sleep(0)  # allow loop to flush
        # Small wait for server response (best-effort)
        await asyncio.sleep(0.1)
        return b""


def main():
    import argparse
    p = argparse.ArgumentParser(description="Send a single payload over QUIC to FF3 receiver")
    p.add_argument("path", help="Path to file to send")
    p.add_argument("--host", default=os.environ.get("FF3_QUIC_ADDR", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("FF3_QUIC_PORT", "41002")))
    p.add_argument("--user", default=os.environ.get("FF3_USER", "user"))
    p.add_argument("--bref-json", dest="bref_json", help="Path to JSON describing BREF windows/chunks", default=None)
    args = p.parse_args()

    data = open(args.path, "rb").read()
    name = os.path.basename(args.path)
    asyncio.run(send_quic_bytes(args.host, args.port, data, name=name, user=args.user, bref_json=args.bref_json))


if __name__ == "__main__":
    main()
