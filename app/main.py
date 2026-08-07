import socket
from app.validators import is_valid_ip
from app.helpers import resolve_host
from app.scanner import scan_target

def init_scanner(host: str):
    print("WELCOME TO KRUSHNET")
    print("-" * 50)
    print(f"Beginning scan for: {host}")
    print("-" * 50)


def main() -> None:
    host = input("Please enter the host: ").strip()

    if not host:
        print("A hostname or IP address is required.")
        return

    # Use a small range while testing the scanner
    ports = range(1, 101)

    init_scanner(host)
    open_ports = scan_target(host, ports)

    print("-" * 50)

    if open_ports:
        print("Open ports:")
        for port_info in open_ports:
            print(f"Port {port_info['port']}: {port_info['status']}: {port_info['banner']}")
    else:
        print("No open ports were found.")


if __name__ == "__main__":
    main()





