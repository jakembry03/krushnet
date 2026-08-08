import ipaddress
import subprocess

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

