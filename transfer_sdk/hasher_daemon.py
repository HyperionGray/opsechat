from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import (
    DEFAULT_BLOB_SEED,
    DEFAULT_BLOB_SIZE,
    DEFAULT_MIN_MATCH,
    DEFAULT_WINDOW_SIZE,
    make_blob_config,
)
from .blob import load_blob
from .encoding import build_job
from .spool import write_job_to_spool


def process_once(input_dir: Path, spool_dir: Path, window_size: int, blob, blob_config, *, min_match: int) -> None:
    for candidate in sorted(input_dir.glob("*")):
        if not candidate.is_file():
            continue
        job = build_job(candidate, blob, window_size, blob_config=blob_config, min_match=min_match)
        write_job_to_spool(job, spool_dir)
        print(f"[hasher] queued {candidate.name} ({job.total_windows} windows)")


async def run_forever(
    input_dir: Path,
    spool_dir: Path,
    window_size: int,
    blob_size: int,
    blob_seed: int,
    blob_path: Path | None,
    interval: float = 2.0,
    *,
    min_match: int,
) -> None:
    blob_config = make_blob_config(blob_size, blob_seed, blob_path)
    blob = load_blob(blob_config)
    seen: dict[Path, float] = {}
    while True:
        for candidate in sorted(input_dir.glob("*")):
            if not candidate.is_file():
                continue
            mtime = candidate.stat().st_mtime
            if candidate in seen and seen[candidate] >= mtime:
                continue
            job = build_job(candidate, blob, window_size, blob_config=blob_config, min_match=min_match)
            write_job_to_spool(job, spool_dir)
            seen[candidate] = mtime
            print(f"[hasher] queued {candidate.name} ({job.total_windows} windows)")
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hasher daemon: convert files into PVRT/IPROG jobs")
    parser.add_argument("--input", type=Path, required=True, help="Directory with files to send")
    parser.add_argument("--spool", type=Path, required=True, help="Spool directory for jobs")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE, help="Window size in bytes")
    parser.add_argument("--blob-size", type=int, default=DEFAULT_BLOB_SIZE, help="Virtual blob size")
    parser.add_argument("--blob-seed", type=int, default=DEFAULT_BLOB_SEED, help="Virtual blob seed")
    parser.add_argument("--blob-path", type=Path, help="Path to shared blob file")
    parser.add_argument("--min-match", type=int, default=DEFAULT_MIN_MATCH, help="Minimum run length (in bytes) to reference from the blob")
    parser.add_argument("--once", action="store_true", help="Process current files then exit")
    args = parser.parse_args()

    args.input.mkdir(parents=True, exist_ok=True)
    args.spool.mkdir(parents=True, exist_ok=True)

    blob_config = make_blob_config(args.blob_size, args.blob_seed, args.blob_path)
    if args.once:
        blob = load_blob(blob_config)
        process_once(args.input, args.spool, args.window_size, blob, blob_config, min_match=max(1, args.min_match))
    else:
        asyncio.run(
            run_forever(
                args.input,
                args.spool,
                args.window_size,
                args.blob_size,
                args.blob_seed,
                args.blob_path,
                min_match=max(1, args.min_match),
            )
        )


if __name__ == "__main__":
    main()
