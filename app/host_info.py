import socket
from app.dataset import HostInfo

def get_host_info(host: str) -> HostInfo:
    ip_address = socket.gethostbyname(host)
    hostname = None

    try:
        hostname, aliases, addresses = socket.gethostbyaddr(ip_address)
    except socket.herror:
        pass

    return HostInfo(
        ip_address=ip_address,
        hostname=hostname
    )

