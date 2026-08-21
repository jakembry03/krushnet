from dataclasses import dataclass, asdict

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