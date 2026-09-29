"""
Proxy 数据模型
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
import time


@dataclass
class Proxy:
    ip: str
    port: int
    protocol: str  # http, https, socks4, socks5
    country: Optional[str] = None
    latency: Optional[float] = None  # 响应时间(秒)
    last_checked: Optional[float] = None  # unix timestamp
    alive: bool = False
    source: Optional[str] = None  # 来源

    def __post_init__(self):
        if isinstance(self.port, str):
            self.port = int(self.port)
        self.protocol = self.protocol.lower().strip()

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    @property
    def requests_dict(self) -> dict:
        """直接用于 requests 的 proxies 参数"""
        addr = f"{self.ip}:{self.port}"
        if self.protocol in ("http", "https"):
            return {"http": f"http://{addr}", "https": f"http://{addr}"}
        elif self.protocol in ("socks4", "socks5"):
            return {"http": f"{self.protocol}://{addr}", "https": f"{self.protocol}://{addr}"}
        return {}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["address"] = self.address
        d["url"] = self.url
        return d

    @classmethod
    def from_line(cls, line: str, protocol: str = "http", source: str = None) -> Optional["Proxy"]:
        """从 'ip:port' 文本行解析"""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        parts = line.split(":")
        if len(parts) < 2:
            return None
        try:
            ip = parts[0].strip()
            port = int(parts[1].strip())
            if not ip or port <= 0 or port > 65535:
                return None
            return cls(ip=ip, port=port, protocol=protocol, source=source)
        except (ValueError, IndexError):
            return None

    def __hash__(self):
        return hash((self.ip, self.port, self.protocol))

    def __eq__(self, other):
        if isinstance(other, Proxy):
            return self.ip == other.ip and self.port == other.port and self.protocol == other.protocol
        return False
