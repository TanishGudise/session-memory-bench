"""Loopback CONNECT proxy with a host allowlist. Paid runs send all model traffic through it while the run
itself sits under sandbox-exec with non-loopback network denied, so nothing but the allowlisted host is reachable.

  python -m smb.proxy --port 0 --allow api.anthropic.com:443 --log runs/<run>/proxy.log
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from pathlib import Path


class Proxy:
    def __init__(self, allow: set[str], log: Path | None = None, port: int = 0):
        self.allow = allow
        self.log = log
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.sock.listen(64)
        self.port = self.sock.getsockname()[1]
        self.lock = threading.Lock()
        self.stopped = False

    def _log(self, **rec) -> None:
        if self.log:
            with self.lock, open(self.log, "a") as fh:
                fh.write(json.dumps({"t": round(time.time(), 3), **rec}) + "\n")

    def serve_forever(self) -> None:
        while not self.stopped:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def start(self) -> "Proxy":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        self.stopped = True
        self.sock.close()

    def _handle(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(30)
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 8192:
                chunk = conn.recv(1024)
                if not chunk:
                    return
                head += chunk
            line = head.split(b"\r\n", 1)[0].decode("latin-1")
            parts = line.split()
            if len(parts) != 3 or parts[0] != "CONNECT" or parts[1] not in self.allow:
                self._log(event="refused", request=line[:200])
                conn.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            host, port = parts[1].rsplit(":", 1)
            upstream = socket.create_connection((host, int(port)), timeout=30)
            self._log(event="connect", target=parts[1])
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            conn.settimeout(None)
            upstream.settimeout(None)

            def pump(a, b):
                try:
                    while True:
                        data = a.recv(65536)
                        if not data:
                            break
                        b.sendall(data)
                except OSError:
                    pass
                finally:
                    for s in (a, b):
                        try:
                            s.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

            t = threading.Thread(target=pump, args=(upstream, conn), daemon=True)
            t.start()
            pump(conn, upstream)
            t.join(timeout=5)
            upstream.close()
        except OSError as exc:
            self._log(event="error", error=str(exc)[:200])
        finally:
            conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--log")
    args = ap.parse_args()
    p = Proxy(set(args.allow), Path(args.log) if args.log else None, args.port)
    print(json.dumps({"port": p.port}), flush=True)
    p.serve_forever()


if __name__ == "__main__":
    main()
