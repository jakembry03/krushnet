import socket
from app.helpers import resolve_host


def scan_target(host: str, ports: range) -> list[dict]:
    ip = resolve_host(host)

    if ip is None:
        return []

    print(f"Resolved address: {ip}")

    open_ports: list[dict] = []

    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)

            result = sock.connect_ex((ip, port))

            if result == 0:
                banner = grab_banner(sock)

                open_ports.append({
                    "port": port,
                    "status": "open",
                    "banner": banner
                })

    return open_ports


def grab_banner(sock: socket.socket) -> str | None:
    chunks: list[bytes] = []
    closed = False

    try:
        while len(b"".join(chunks)) < 4096:
            chunk = sock.recv(1024)
            if not chunk:
                closed = True
                break
            chunks.append(chunk)
    except (TimeoutError, OSError):
        pass

    raw = b"".join(chunks)

    if not raw:
        return "<closed by peer, no data>" if closed else None

    # errors="replace" keeps a marker for bad bytes instead of deleting them
    text = raw.decode("utf-8", errors="replace")
    # make control characters visible rather than invisible
    text = "".join(c if c.isprintable() or c in "/t" else f"//x{ord(c):02x}" for c in text)

    return text.strip() or f"<{len(raw)} non-text bytes: {raw[:32].hex(' ')}>"




