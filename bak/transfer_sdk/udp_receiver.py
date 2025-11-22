from __future__ import annotations

import asyncio
import os
from typing import Dict, Optional, Tuple

from app.state import load_config
from transfer_sdk.config import TransferSettings
from transfer_sdk.upload_manager import TransferIngestor


ALLOW_RAW = os.environ.get("FF3_UDP_ALLOW_RAW", "0") in ("1", "true", "TRUE", "True")
PSK_EXPECTED = os.environ.get("FF3_UDP_PSK")


def _process_ndjson(data: bytes, ingestor: TransferIngestor) -> Tuple[bool, str]:
    try:
        text = data.decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        import json as _json

        user: str = "user"
        name: str = "udp-object.bin"
        window_size: int = 0
        cur: Optional[int] = None
        agg: Dict[int, bytearray] = {}
        blob = ingestor._get_blob()

        for ln in lines:
            try:
                msg = _json.loads(ln)
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue
            t = msg.get("t")
            if t == "PREF":
                user = str(msg.get("user") or user)
                name = str(msg.get("name") or name)
                window_size = int(msg.get("ws") or window_size or 0)
                if PSK_EXPECTED is not None:
                    provided = str(msg.get("psk") or "")
                    if provided != PSK_EXPECTED:
                        return False, "unauthorized (bad psk)"
            elif t == "WIN":
                cur = int(msg.get("i") or 0)
                agg.setdefault(cur, bytearray())
            elif t == "BREF":
                if cur is None:
                    return False, "BREF without WIN"
                chunks = msg.get("c") or []
                out = agg.setdefault(cur, bytearray())
                for off, ln2 in chunks:
                    out.extend(blob.read(int(off), int(ln2)))
            elif t == "RAW":
                if not ALLOW_RAW:
                    return False, "RAW disallowed by server policy"
                if cur is None:
                    return False, "RAW without WIN"
                import base64 as _b64
                b64 = str(msg.get("p") or "")
                if b64:
                    out = agg.setdefault(cur, bytearray())
                    out.extend(_b64.b64decode(b64.encode("ascii")))
            elif t == "END":
                cur = None
            elif t == "DONE":
                break

        obj = bytearray()
        for w in sorted(agg.keys()):
            obj.extend(agg[w])

        cfg = load_config()
        virtual = f"{user}/{name}".strip("/")
        from api.api import _encode_path as enc, _unique_encoded_target as uniq
        encoded = enc(virtual)
        target = uniq(cfg.inbox_dir, encoded)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as f:
            f.write(obj)

        # build job in background thread
        asyncio.get_running_loop().run_in_executor(None, ingestor.build_job_for_path, target)
        return True, "OK"
    except Exception as e:
        return False, f"ERR:{str(e)[:160]}"


class UdpIngestProtocol(asyncio.DatagramProtocol):
    def __init__(self, ingestor: TransferIngestor):
        super().__init__()
        self.ingestor = ingestor
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr):
        ok, msg = _process_ndjson(data, self.ingestor)
        if self.transport is not None:
            try:
                self.transport.sendto((msg or ("OK" if ok else "ERR")).encode("utf-8"), addr)
            except Exception:
                pass


async def create_server(host: str, port: int):
    cfg = load_config()
    blob_path = cfg.blob_path if cfg.blob_path else None
    blob_size = blob_path.stat().st_size if blob_path and blob_path.exists() else 4 * 1024 * 1024
    settings = TransferSettings(
        inbox_dir=cfg.inbox_dir,
        spool_dir=cfg.spool_dir,
        outbox_dir=cfg.outbox_dir,
        window_size=cfg.window_size,
        blob_size=blob_size,
        blob_path=blob_path,
    )
    ingestor = TransferIngestor(settings)
    ingestor.ensure_ready()

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UdpIngestProtocol(ingestor), local_addr=(host, port)
    )
    return transport, protocol


def main():
    host = os.environ.get("FF3_UDP_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_UDP_PORT", "41003"))
    async def _run():
        transport, _ = await create_server(host, port)
        sock = transport.get_extra_info("sockname")
        print(f"[udp-receiver] listening on {sock}")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            transport.close()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
