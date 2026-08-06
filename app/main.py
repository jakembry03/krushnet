import socket
from app.validators import is_valid_ip
from app.helpers import resolve_host

def init_scanner(host: str):
    print("WELCOME TO KRUSHNET")
    print("-" * 50)
    print(f"Beginning scan for: {host}")
    print("-" * 50)


def scan_target(host: str, ports: range) -> list[dict] | None:
    ip = resolve_host(host)

    if ip is None:
        return []

    print(f"Resolved address: {ip}")

    open_ports: list[dict] = []

    for port in ports:
        # This provides visible progress without printing all 1,023 ports.
        if port % 100 == 0:
            print(f"Scanning port {port}...")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as scanner_socket:
            scanner_socket.settimeout(0.5)
            result = scanner_socket.connect_ex((ip, port))

            if result == 0:
                print(f"Port {port} is open")
                open_ports.append(
                    {
                        "port": port,
                        "status": "open",
                    }
                )


    return open_ports


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
            print(f"Port {port_info['port']}: {port_info['status']}")
    else:
        print("No open ports were found.")


if __name__ == "__main__":
    main()





