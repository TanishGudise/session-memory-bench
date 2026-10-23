import socket
import threading

from smb.proxy import Proxy


def _connect(port, target):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
    return s, s.recv(1024).decode()


def test_refuses_hosts_not_on_the_allowlist(tmp_path):
    p = Proxy({"api.anthropic.com:443"}, tmp_path / "log").start()
    try:
        s, reply = _connect(p.port, "example.com:443")
        assert reply.startswith("HTTP/1.1 403")
        s.close()
        assert '"refused"' in (tmp_path / "log").read_text()
    finally:
        p.stop()


def test_tunnels_allowlisted_host(tmp_path):
    echo = socket.socket()
    echo.bind(("127.0.0.1", 0))
    echo.listen(1)
    port = echo.getsockname()[1]

    def serve():
        c, _ = echo.accept()
        c.sendall(c.recv(100).upper())
        c.close()

    threading.Thread(target=serve, daemon=True).start()
    p = Proxy({f"127.0.0.1:{port}"}).start()
    try:
        s, reply = _connect(p.port, f"127.0.0.1:{port}")
        assert reply.startswith("HTTP/1.1 200")
        s.sendall(b"hello")
        assert s.recv(100) == b"HELLO"
        s.close()
    finally:
        p.stop()
        echo.close()
