import socket
import ssl
import ipaddress
from app.helpers import resolve_host
from app.validators import is_valid_network
from app.banner import grab_banner, grab_http_banner, grab_https_banner
from app.dataset import PortScanResult
from app.service_map import get_service_name


def run_scan(host: str, ports: list[int]) -> list[PortScanResult]:
    ip = resolve_host(host)

    if ip is None:
        return []

    print(f"Resolved address: {ip}")

    return scan_target(ip, ports)


def scan_target(ip: str, ports: list[int]) -> list[PortScanResult]:
    open_ports: list[PortScanResult] = []

    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)

            result = sock.connect_ex((ip, port))

            if result == 0:
                banner = None
                service = get_service_name(port)

                if port == 80:
                    service = "http"
                    banner = grab_http_banner(sock, ip)

                elif port == 443:
                    service = "https"
                    banner = grab_https_banner(sock, ip)

                else:
                    banner = grab_banner(sock)

                open_ports.append(
                    PortScanResult(
                        host=ip,
                        port=port,
                        status="open",
                        service=service,
                        banner=banner
                    )
                )
    return open_ports



    




