from app.validators import is_valid_ip
from app.helpers import resolve_host
from app.scanner import run_scan
from app.cli import parse_args
from app.discovery import scan_network, scan_active_hosts


def init_scanner(host: str):
    print("WELCOME TO KRUSHNET")
    print("-" * 50)
    print(f"Beginning scan for: {host}")
    print("-" * 50)


def main():
    args = parse_args()
    host = args.target
    ports = args.ports

    init_scanner(host)

    if args.agressive:
        active_hosts = scan_network(host)

        print(f"Active hosts for {host}")
        for active_host in active_hosts:
            print(active_host)

        print("-" * 50)
        print("Beginning port scans...")
        print("-" * 50)

        scan_results = scan_active_hosts(active_hosts, ports)

        for result in scan_results:
            print(result)

    elif args.discover:
        active_hosts = scan_network(host)

        print(f"Active Hosts for {host}")
        
        for host in active_hosts:
            print(host)

    else:
        open_ports = run_scan(host, ports)
        if open_ports:
            print("Open Ports: ")

            for port_info in open_ports:
                print(port_info)
        else:
            print("No open ports were found.")

if __name__ == "__main__":
    main()





