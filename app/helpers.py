from app.validators import is_valid_ip
import socket


def resolve_host(host: str) -> str | None:
    if is_valid_ip(host):
        return host

    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        print(f"Unable to resolve hostname: {host}")
        return None