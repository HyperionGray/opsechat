from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path


def send_file(host: str, port: int, file_path: Path, dest: str, user: str = "user", secret: str | None = None):
    size = file_path.stat().st_size
    header = {"user": user, "virtual_path": dest, "size": size}
    if secret:
        header["secret"] = secret
    data = (json.dumps(header) + "\n").encode("utf-8")

    with socket.create_connection((host, port)) as sock:
        sock.sendall(data)
        with file_path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                sock.sendall(chunk)
        # Read simple response
        resp = sock.recv(64)
        sys.stdout.write(resp.decode("utf-8", errors="ignore"))


def main(argv: list[str]):
    if len(argv) < 2:
        print("Usage: tcp_send.py <file> [dest-path] [host] [port]", file=sys.stderr)
        sys.exit(2)
    file_path = Path(argv[1]).expanduser()
    if not file_path.exists():
        print(f"file does not exist: {file_path}", file=sys.stderr)
        sys.exit(2)
    dest = argv[2] if len(argv) > 2 else file_path.name
    host = argv[3] if len(argv) > 3 else os.environ.get("FF3_TCP_ADDR", "127.0.0.1")
    port = int(argv[4]) if len(argv) > 4 else int(os.environ.get("FF3_TCP_PORT", "41001"))
    user = os.environ.get("FF3_TCP_USER", "user")
    secret = os.environ.get("FF3_TCP_SECRET")
    send_file(host, port, file_path, dest, user=user, secret=secret)


if __name__ == "__main__":
    main(sys.argv)
