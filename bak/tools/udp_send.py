from __future__ import annotations

import asyncio
import os
import socket
from typing import Tuple, Any, List, Dict, Optional


def _frames_from_bref_json(bref_obj: Any, user: str, name: str, default_ws: int) -> List[Dict[str, Any]]:
    frames: List[Dict[str, Any]] = []
    ws = int(default_ws)
    # Accept shapes similar to QUIC sender
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
        raise ValueError("Unsupported BREF JSON format for UDP sender")

    frames.append({"t": "PREF", "user": user, "name": name, "ws": ws})
    for w in windows:
        idx = int(w.get("i", 0))
        chunks = [(int(a), int(b)) for (a, b) in (w.get("c") or [])]
        frames.append({"t": "WIN", "i": idx})
        frames.append({"t": "BREF", "c": chunks})
        frames.append({"t": "END"})
    frames.append({"t": "DONE"})
    return frames


async def send_udp_bytes(host: str, port: int, payload: bytes, *, name: str = "udp-object.bin", user: str = "user", bref_json: Optional[str] = None) -> str:
    import json as _json
    import base64 as _b64

    allow_raw = os.environ.get("FF3_UDP_ALLOW_RAW", "0") in ("1","true","TRUE","True")
    ws = max(1024, min(65536, len(payload) or 1024))
    psk = os.environ.get("FF3_UDP_PSK")
    if bref_json:
        with open(bref_json, "r", encoding="utf-8") as f:
            bref_obj = _json.load(f)
        frames = _frames_from_bref_json(bref_obj, user=user, name=name, default_ws=ws)
    else:
        frames = []
        pref = {"t":"PREF","user":user,"name":name,"ws":ws}
        if psk:
            pref["psk"] = psk
        frames.append(pref)
        frames.append({"t":"WIN","i":0})
        if allow_raw:
            frames.append({"t":"RAW","p":_b64.b64encode(payload).decode("ascii")})
        else:
            frames.append({"t":"BREF","c":[]})
        frames.append({"t":"END"})
        frames.append({"t":"DONE"})
    ndjson = "\n".join(_json.dumps(o, separators=(",",":"), ensure_ascii=False) for o in frames) + "\n"

    loop = asyncio.get_running_loop()
    on_response = loop.create_future()

    class _Client(asyncio.DatagramProtocol):
        def connection_made(self, transport: asyncio.BaseTransport) -> None:
            self.transport: asyncio.DatagramTransport = transport  # type: ignore[assignment]
            self.transport.sendto(ndjson.encode("utf-8"), (host, port))

        def datagram_received(self, data: bytes, addr):
            if not on_response.done():
                on_response.set_result(data.decode("utf-8", "ignore"))

    transport, protocol = await loop.create_datagram_endpoint(lambda: _Client(), remote_addr=None)
    try:
        try:
            resp = await asyncio.wait_for(on_response, timeout=1.0)
        except asyncio.TimeoutError:
            resp = ""
        return resp
    finally:
        transport.close()


def main():
    import argparse
    p = argparse.ArgumentParser(description="Send a single NDJSON payload over UDP to FF3 receiver")
    p.add_argument("path", help="Path to file to send")
    p.add_argument("--host", default=os.environ.get("FF3_UDP_ADDR", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("FF3_UDP_PORT", "41003")))
    p.add_argument("--user", default=os.environ.get("FF3_USER", "user"))
    p.add_argument("--bref-json", dest="bref_json", help="Path to JSON describing BREF windows/chunks", default=None)
    args = p.parse_args()

    data = open(args.path, "rb").read()
    name = os.path.basename(args.path)
    resp = asyncio.run(send_udp_bytes(args.host, args.port, data, name=name, user=args.user, bref_json=args.bref_json))
    if resp:
        print(resp)


if __name__ == "__main__":
    main()
