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
        help="Discover active hosts on a network"
    )

    parser.add_argument(
        "-A",
        "--aggressive",
        action="store_true",
        help="Perform an aggressive scan"
    )

    return parser

def parse_args():
    parser = build_parser()
    return parser.parse_args()