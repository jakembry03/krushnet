SERVICE_MAP: dict[tuple[str, int], str] = {
    ("tcp", 20): "FTP Data",
    ("tcp", 21): "FTP",
    ("tcp", 22): "SSH",
    ("tcp", 23): "Telnet",
    ("tcp", 25): "SMTP",
    ("tcp", 53): "DNS",
    ("udp", 53): "DNS",
    ("tcp", 80): "HTTP",
    ("tcp", 110): "POP3",
    ("tcp", 143): "IMAP",
    ("tcp", 443): "HTTPS",
    ("tcp", 445): "SMB",
    ("tcp", 3389): "RDP",
}

def get_service_name(port: int, protocol: str = "tcp") -> str | None:
    return SERVICE_MAP.get((protocol.lower(), port))

