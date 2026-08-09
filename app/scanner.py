import socket
import ssl
import ipaddress
from app.helpers import resolve_host
from app.validators import is_valid_network
from app.banner import grab_banner, grab_http_banner, grab_https_banner


def run_scan(host: str, ports: range) -> list[dict]:
    ip = resolve_host(host)
    open_ports: list[dict] = []

    if ip is None:
        return []

    print(f"Resolved address: {ip}")

    open_ports = scan_target(ip, ports, open_ports)
    return open_ports


def scan_target(ip: str, ports: range, open_ports: list[dict]) -> list[dict]:
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)

            result = sock.connect_ex((ip, port))

            if result == 0:
                if port == 80:
                    banner = grab_http_banner(sock, ip)
                    open_ports.append({
                        "port": port,
                        "status": "open",
                        "banner": banner
                    })

                elif port == 443:
                    banner = grab_https_banner(sock, ip)
                    open_ports.append({
                        "port": port,
                        "status": "open",
                        "banner": banner
                    })

                else:   
                    banner = grab_banner(sock)

                    open_ports.append({
                        "port": port,
                        "status": "open",
                        "banner": banner
                    })
    return open_ports



    




