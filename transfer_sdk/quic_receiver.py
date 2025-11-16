from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
import ipaddress
from typing import Dict, Optional

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, QuicEvent
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.state import load_config
from transfer_sdk.upload_manager import TransferIngestor
from transfer_sdk.config import TransferSettings

# Lightweight QUIC NDJSON protocol constants
ALLOW_RAW = os.environ.get("FF3_QUIC_ALLOW_RAW", "0") in ("1", "true", "TRUE", "True")
PSK_EXPECTED = os.environ.get("FF3_QUIC_PSK")  # optional pre-shared key


def _generate_self_signed_cert(host: str) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host or "localhost")])
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
    )
    alt_names = []
    try:
        alt_names.append(x509.DNSName(host))
    except Exception:
        pass
    alt_names.append(x509.DNSName("localhost"))
    try:
        alt_names.append(x509.IPAddress(ipaddress.ip_address(host)))
    except Exception:
        pass
    builder = builder.add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
    cert = builder.sign(private_key=key, algorithm=hashes.SHA256())
    return cert, key


class PfsQuicProtocol(QuicConnectionProtocol):
    def __init__(self, *args, ingestor: TransferIngestor, **kwargs):
        super().__init__(*args, **kwargs)
        self._streams: Dict[int, bytearray] = {}
        self.ingestor = ingestor

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            buf = self._streams.setdefault(event.stream_id, bytearray())
            buf += event.data
            if event.end_stream:
                asyncio.create_task(self._handle_stream(event.stream_id, bytes(buf)))

    async def _handle_stream(self, stream_id: int, data: bytes):
        try:
            # NDJSON protocol: PREF, WIN, BREF, RAW, END, DONE
            text = data.decode("utf-8", errors="ignore")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            import json as _json

            user: str = "user"
            name: str = "quic-object.bin"
            window_size: int = 0
            cur: Optional[int] = None
            agg: Dict[int, bytearray] = {}
            blob = self.ingestor._get_blob()

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
                    # PSK enforcement if configured
                    if PSK_EXPECTED is not None:
                        provided = str(msg.get("psk") or "")
                        if provided != PSK_EXPECTED:
                            raise RuntimeError("unauthorized (bad psk)")
                elif t == "WIN":
                    cur = int(msg.get("i") or 0)
                    agg.setdefault(cur, bytearray())
                elif t == "BREF":
                    if cur is None:
                        raise RuntimeError("BREF without WIN")
                    chunks = msg.get("c") or []
                    out = agg.setdefault(cur, bytearray())
                    for off, ln2 in chunks:
                        out.extend(blob.read(int(off), int(ln2)))
                elif t == "RAW":
                    if not ALLOW_RAW:
                        raise RuntimeError("RAW disallowed by server policy")
                    if cur is None:
                        raise RuntimeError("RAW without WIN")
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
            # Effective stored leaf name for downstream repair tooling
            effective_leaf = target.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as f:
                f.write(obj)

            # Queue ingestion build in background
            await asyncio.to_thread(self.ingestor.build_job_for_path, target)
            # Keep QUIC path lean: just acknowledge success; integrity handled by background daemons
            self._send_bytes(stream_id, b"OK")
        except Exception as e:
            msg = f"ERR:{str(e)[:160]}".encode("utf-8", errors="ignore")
            self._send_err(stream_id, msg)

    def _send_bytes(self, stream_id: int, data: bytes):
        try:
            self._quic.send_stream_data(stream_id, data or b"OK", end_stream=True)
        finally:
            asyncio.create_task(self._network_changed())

    def _send_err(self, stream_id: int, msg: bytes):
        try:
            self._quic.send_stream_data(stream_id, msg or b"ERR", end_stream=True)
        finally:
            asyncio.create_task(self._network_changed())


async def create_server(host: str, port: int, cert: str | None, key: str | None):
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

    qc = QuicConfiguration(is_client=False, alpn_protocols=["pfs-arith"])
    if cert and key and os.path.exists(cert) and os.path.exists(key):
        qc.load_cert_chain(certfile=cert, keyfile=key)
    else:
        auto_cert, auto_key = _generate_self_signed_cert(host)
        qc.certificate = auto_cert
        qc.private_key = auto_key
        qc.certificate_chain = []

    def mkproto(*a, **kw):
        return PfsQuicProtocol(*a, ingestor=ingestor, **kw)

    server = await serve(host, port, configuration=qc, create_protocol=mkproto)
    return server


async def _run(host: str, port: int, cert: str | None, key: str | None):
    server = await create_server(host, port, cert, key)
    addrs = ", ".join(str(sock.getsockname()) for sock in (server._transport.sockets or []))  # type: ignore[attr-defined]
    print(f"[quic-receiver] listening on {addrs}")
    try:
        await server.wait_closed()
    except asyncio.CancelledError:  # pragma: no cover
        pass


def main():
    host = os.environ.get("FF3_QUIC_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_QUIC_PORT", "41002"))
    cert = os.environ.get("FF3_QUIC_CERT")
    key = os.environ.get("FF3_QUIC_KEY")
    asyncio.run(_run(host, port, cert, key))


if __name__ == "__main__":  # pragma: no cover
    main()
