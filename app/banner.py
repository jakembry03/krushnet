import socket
import ssl

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

def grab_http_banner(sock: socket.socket, host: str) -> str | None:
    request = (
        f"HEAD / HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    try:
        sock.sendall(request.encode())

        response = sock.recv(4096)

        return response.decode(errors="ignore")

    except (socket.timeout, OSError):
        return None

def grab_https_banner(sock: socket.socket, host: str) -> str | None:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Useful for your own lab/network scanner where devices may have self-signed certificate
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        tls_sock = context.wrap_socket(
            sock,
            server_hostname=host
        )

        request = (
            f"HEAD / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )

        tls_sock.sendall(request.encode())

        response = tls_sock.recv(4096)

        return response.decode(errors="ignore")

    except (ssl.SSLError, socket.timeout, OSError):
        return None
