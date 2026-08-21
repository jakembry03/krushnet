import ipaddress
import subprocess
from app.dataset import PortScanResult
from app.scanner import run_scan

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

def scan_active_hosts(active_hosts: list[str], ports: list[int]) -> list[PortScanResult]:
    discovery_results: list[PortScanResult] = []

    for host in active_hosts:
        host_results = run_scan(host, ports)
        discovery_results.extend(host_results)

    return discovery_results


