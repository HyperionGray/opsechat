from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import TransferSettings
from .streaming import StreamJob, consume_window_queue, stream_file_to_queue


async def _run(path: Path, sample_every: int) -> None:
    cfg = TransferSettings.from_env()
    job = StreamJob(path=path, window_size=cfg.window_size, blob_size=cfg.blob_size, blob_seed=cfg.blob_seed)
    queue: asyncio.Queue = asyncio.Queue(maxsize=cfg.window_size // 1024)

    blob = job.load_blob()
    blob.ensure_loaded()

    producer = asyncio.create_task(stream_file_to_queue(job, queue))
    stats = await consume_window_queue(queue, blob, sample_every=sample_every)
    await producer

    size_mb = path.stat().st_size / (1024 * 1024) if path.exists() else 0
    print(f"Streamed {stats['windows']} windows from {path} ({size_mb:.2f} MiB)")
    print(f"Sampled {stats['sampled']} windows, failures={stats['failures']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream a file through the transfer-sdk window pipeline")
    parser.add_argument("path", type=Path, help="File to stream")
    parser.add_argument("--sample-every", type=int, default=10, help="Integrity sample interval (default: 10)")
    args = parser.parse_args()

    if not args.path.exists():
        parser.error(f"file not found: {args.path}")

    asyncio.run(_run(args.path, args.sample_every))


if __name__ == "__main__":
    main()
