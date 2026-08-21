import ipaddress
import subprocess
from app.dataset import PortScanResult, HostScanResult
from app.scanner import run_scan
from app.host_info import get_host_info

def is_host_alive(ip: str) -> bool:
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return result.returncode == 0

def scan_network(cidr: str) -> list[str]:
    network = ipaddress.ip_network(cidr, strict=False)

    active_hosts = []

    for host in network.hosts():
        ip = str(host)

        if is_host_alive(ip):
            active_hosts.append(ip)

    return active_hosts

def scan_active_hosts(active_hosts: list[str], ports: list[int]) -> list[HostScanResult]:
    discovery_results: list[HostScanResult] = []

    for host in active_hosts:
        host_info = get_host_info(host)
        port_results = run_scan(host, ports)

        host_result = HostScanResult(
            host=host_info,
            ports=port_results
        )

        discovery_results.append(host_result)

    return discovery_results


