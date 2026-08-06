import socket
from validators import is_valid_ip

def init_scanner(host: str):
    print("WELCOME TO KRUSHNET")
    print("-" * 50)
    print(f"Beginning scan for: {host}")
    print("-" * 50)

def scan_target(host: str, ports: range):
    host_resolved = resolve_host(host)
    open_ports: list[dict] = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex((host, port))
            if result == 0:
                open_ports.append({port: "open"})
    print(open_ports)

def resolve_host(host: str):
    if is_valid_ip(host):
        return host
    else:
        host_resolved = socket.gethostbyname(host)
        return host_resolved


host = input("Please enter the host: ")
ports = range(1, 1024)

init_scanner(host)

scan_target(host, ports)



