import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Krushnet network scanning tool"
    )

    parser.add_argument(
        "target",
        help="IP address, hostname, or network to scan"
    )

    parser.add_argument(
        "-p",
        "--ports",
        nargs="+",
        type=int,
        default=list(range(1, 1025)),
        help="Ports to scan"
    )

    discovery_group = parser.add_mutually_exclusive_group()

    discovery_group.add_argument(
        "-d",
        "--discover",
        action="store_true",
        help="Perform network discovery"
    )

    discovery_group.add_argument(
        "-A",
        "--agressive",
        action="store_true",
        help="Discover active hosts and port scan each host"
    )

    return parser

def parse_args():
    parser = build_parser()
    return parser.parse_args()