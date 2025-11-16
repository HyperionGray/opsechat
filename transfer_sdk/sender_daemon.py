from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Optional

from .protocol import send_job, send_job_websocket, send_job_stream_websocket
from .spool import iter_spool_jobs, load_job_from_spool


async def send_loop(
    spool_dir: Path,
    sent_dir: Path,
    host: Optional[str],
    port: Optional[int],
    interval: float,
    ws_url: Optional[str],
    ws_timeout: float,
    ws_stream: bool,
) -> None:
    while True:
        pending = iter_spool_jobs(spool_dir)
        if not pending:
            await asyncio.sleep(interval)
            continue
        for job_path in pending:
            try:
                job = load_job_from_spool(job_path)
                if ws_url:
                    if ws_stream:
                        await send_job_stream_websocket(job, ws_url, timeout=ws_timeout)
                    else:
                        await send_job_websocket(job, ws_url, timeout=ws_timeout)
                else:
                    if host is None or port is None:
                        raise RuntimeError("TCP transport requested without host/port")
                    await send_job(job, host, port)
                target = sent_dir / job_path.name
                job_path.replace(target)
                print(f"[sender] delivered {job.object_name} ({job.total_windows} windows)")
            except Exception as exc:
                print(f"[sender] failed {job_path.name}: {exc}")
                await asyncio.sleep(interval)
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Sender daemon: push spool jobs to a remote receiver")
    parser.add_argument("--spool", type=Path, required=True, help="Spool directory to watch")
    parser.add_argument("--host", type=str, default=None, help="Receiver host (TCP mode)")
    parser.add_argument("--port", type=int, default=None, help="Receiver port (TCP mode)")
    parser.add_argument("--interval", type=float, default=1.5, help="Poll interval when idle")
    parser.add_argument("--sent", type=Path, default=None, help="Directory for completed jobs")
    parser.add_argument("--ws-url", type=str, default=None, help="WebSocket URL (ws:// or wss://) for UI relay")
    parser.add_argument("--ws-timeout", type=float, default=30.0, help="Timeout waiting for WebSocket ACK (seconds)")
    parser.add_argument(
        "--ws-stream",
        action="store_true",
        help="Stream windows over WebSocket instead of sending full job payloads",
    )
    args = parser.parse_args()

    args.spool.mkdir(parents=True, exist_ok=True)
    sent_dir = args.sent or (args.spool / "sent")
    sent_dir.mkdir(parents=True, exist_ok=True)

    ws_url = (args.ws_url or "").strip() or None
    if ws_url is None and (args.host is None or args.port is None):
        parser.error("--host and --port are required unless --ws-url is provided")
    if args.ws_stream and ws_url is None:
        parser.error("--ws-stream requires --ws-url")

    try:
        asyncio.run(
            send_loop(
                args.spool,
                sent_dir,
                args.host,
                args.port,
                args.interval,
                ws_url,
                args.ws_timeout,
                args.ws_stream,
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
