import socket
from app.helpers import resolve_host


def scan_target(host: str, ports: range) -> list[dict] | None:
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
    try:
        banner = sock.recv(1024)
        return banner.decode(errors="ignore").strip()
    except socket.timeout:
        return None
    except OSError:
        return None



