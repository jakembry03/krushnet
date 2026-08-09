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

    parser.add_argument(
        "-d",
        "--discover",
        action="store_true",
        help="Perform network discovery"
    )

    return parser

def parse_args():
    parser = build_parser()
    return parser.parse_args()