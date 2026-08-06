import socket
from app.validators import is_valid_ip

def init_scanner(host: str):
    print("WELCOME TO KRUSHNET")
    print("-" * 50)
    print(f"Beginning scan for: {host}")
    print("-" * 50)

def scan_target(host: str, ports: range) -> list[dict] | None:
    ip = resolve_host(host)
    open_ports: list[dict] = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex((ip, port))
            if result == 0:
                open_ports.append({port: "open"})
                return open_ports
            else:
                return None
            

def resolve_host(host: str):
    try:
        if is_valid_ip(host):
            return host
        else:
            ip = socket.gethostbyname(host)
            return ip
    except socket.gaierror:
        print("Unable to resolve hostname.")


def main():
    host = input("Please enter the host: ")
    ports = range(1, 1024)
    init_scanner(host)
    open_ports = scan_target(host, ports)
    print(open_ports)

if __name__ == "__main__":
    main()



