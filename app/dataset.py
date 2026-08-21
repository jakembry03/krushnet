from dataclasses import dataclass, asdict, field

@dataclass
class PortScanResult:
    host: str
    port: int
    status: str = "open"
    protocol: str = "tcp"
    service: str | None = None
    banner: str | None = None

    def __str__(self) -> str:
        service = self.service or "unknown"
        banner = self.banner or "No banner returned"

        return (
            f"Port: {self.port:<5} "
            f"Status: {self.status:<8} "
            f"Service: {service:<10} "
            f"Banner: {banner}"
        )

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class HostInfo:
    ip_address: str
    hostname: str | None = None

@dataclass
class HostScanResult:
    host: HostInfo
    ports: list[PortScanResult] = field(default_factory=list)

    def __str__(self) -> str:
        hostname = self.host.hostname or "Unknown"

        output = [
            "-" * 50,
            f"IP Address: {self.host.ip_address}",
            f"Hostname: {hostname}",
            "Open Ports:"
        ]

        if self.ports:
            for port in self.ports:
                output.append(str(port))
        else:
            output.append("No open ports found.")

        return "\n".join(output)

