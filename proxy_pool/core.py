"""
ProxyPool 核心引擎 — 抓取、验证、缓存、轮询
"""
import time
import random
import threading
from typing import List, Optional, Dict, Any
from .models import Proxy
from .fetchers import fetch_all_sync, fetch_all_async
from .validator import validate_sync, validate_async
from .cache import Cache


class ProxyPool:
    """
    代理池核心类。

    用法:
        pool = ProxyPool()
        proxy = pool.get_proxy(protocol="http")
        proxies = pool.get_proxies(count=10, protocol="socks5")
    """

    def __init__(
        self,
        auto_fetch: bool = True,
        auto_validate: bool = False,
        cache_ttl: int = 3600,  # 1小时
        validate_timeout: int = 5,
        max_concurrent: int = 100,
        db_path: str = None,
    ):
        self.cache = Cache(db_path)
        self.cache_ttl = cache_ttl
        self.validate_timeout = validate_timeout
        self.max_concurrent = max_concurrent
        self._round_robin_idx = 0
        self._lock = threading.Lock()

        if auto_fetch:
            self.refresh(validate=auto_validate)

    def refresh(self, validate: bool = False) -> Dict[str, Any]:
        """刷新代理池：抓取 + (可选)验证 + 缓存"""
        start = time.time()

        # 抓取
        proxies = fetch_all_sync(timeout=15)
        fetch_count = len(proxies)

        # 验证
        alive_count = 0
        if validate and proxies:
            alive = validate_sync(
                proxies,
                timeout=self.validate_timeout,
                max_workers=self.max_concurrent,
            )
            alive_count = len(alive)
            # 保存全部，标记存活状态
            alive_set = {(p.ip, p.port, p.protocol) for p in alive}
            for p in proxies:
                p.alive = (p.ip, p.port, p.protocol) in alive_set
            self.cache.save(proxies)
        else:
            # 不验证，标记全部为 alive=True（惰性验证模式）
            for p in proxies:
                p.alive = True
            self.cache.save(proxies)
            alive_count = fetch_count

        elapsed = round(time.time() - start, 2)
        return {
            "fetched": fetch_count,
            "alive": alive_count,
            "elapsed_seconds": elapsed,
        }

    async def refresh_async(self, validate: bool = False) -> Dict[str, Any]:
        """异步刷新代理池"""
        start = time.time()

        proxies = await fetch_all_async(timeout=15)
        fetch_count = len(proxies)

        alive_count = 0
        if validate and proxies:
            alive = await validate_async(
                proxies,
                timeout=self.validate_timeout,
                max_concurrent=self.max_concurrent,
            )
            alive_count = len(alive)
            alive_set = {(p.ip, p.port, p.protocol) for p in alive}
            for p in proxies:
                p.alive = (p.ip, p.port, p.protocol) in alive_set
            self.cache.save(proxies)
        else:
            for p in proxies:
                p.alive = True
            self.cache.save(proxies)
            alive_count = fetch_count

        elapsed = round(time.time() - start, 2)
        return {
            "fetched": fetch_count,
            "alive": alive_count,
            "elapsed_seconds": elapsed,
        }

    def _is_cache_fresh(self) -> bool:
        last = self.cache.last_update()
        if last is None:
            return False
        return (time.time() - last) < self.cache_ttl

    def get_proxy(
        self,
        protocol: str = None,
        strategy: str = "random",
    ) -> Optional[Proxy]:
        """获取单个代理"""
        proxies = self.get_proxies(count=1, protocol=protocol, strategy=strategy)
        return proxies[0] if proxies else None

    def get_proxies(
        self,
        count: int = 1,
        protocol: str = None,
        strategy: str = "random",
    ) -> List[Proxy]:
        """
        获取多个代理。

        strategy:
            - "random": 随机选取
            - "round_robin": 轮询
            - "fastest": 按延迟排序取最快的
        """
        # 如果缓存过期，自动刷新（不验证）
        if not self._is_cache_fresh():
            try:
                self.refresh(validate=False)
            except Exception:
                pass

        proxies = self.cache.load(protocol=protocol, only_alive=True, sort_by_latency=True)

        if not proxies:
            return []

        if strategy == "fastest":
            return proxies[:count]
        elif strategy == "round_robin":
            with self._lock:
                start = self._round_robin_idx
                selected = []
                for i in range(count):
                    idx = (start + i) % len(proxies)
                    selected.append(proxies[idx])
                self._round_robin_idx = (start + count) % len(proxies)
            return selected
        else:  # random
            return random.sample(proxies, min(count, len(proxies)))

    def get_all(self, protocol: str = None) -> List[Proxy]:
        """获取全部可用代理"""
        return self.cache.load(protocol=protocol, only_alive=True, sort_by_latency=True)

    def stats(self) -> dict:
        """获取代理池统计信息"""
        return self.cache.stats()

    def export(self, protocol: str = None, fmt: str = "txt") -> str:
        """
        导出代理列表。

        fmt: "txt" (ip:port), "json", "csv"
        """
        proxies = self.get_all(protocol=protocol)
        if fmt == "json":
            import json
            return json.dumps([p.to_dict() for p in proxies], indent=2)
        elif fmt == "csv":
            lines = ["ip,port,protocol,country,latency,source"]
            for p in proxies:
                lines.append(f"{p.ip},{p.port},{p.protocol},{p.country or ''},{p.latency or ''},{p.source or ''}")
            return "\n".join(lines)
        else:  # txt
            return "\n".join(p.address for p in proxies)
