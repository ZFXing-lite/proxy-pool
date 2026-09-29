"""
异步代理验证器 — 并发检测代理可用性和响应时间
"""
import asyncio
import time
from typing import List, Optional

from .models import Proxy

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# 验证用的测试 URL
TEST_URLS = {
    "http": "http://httpbin.org/ip",
    "https": "https://httpbin.org/ip",
    "socks4": "http://httpbin.org/ip",
    "socks5": "http://httpbin.org/ip",
}

# 备用测试 URL（httpbin 可能不稳定）
FALLBACK_URL = "http://ip-api.com/json"


async def _check_one_async(proxy: Proxy, timeout: int = 5) -> Proxy:
    """异步检测单个代理"""
    if not AIOHTTP_AVAILABLE:
        raise ImportError("aiohttp is required")

    proxy_url = proxy.url
    start = time.time()
    try:
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as session:
            async with session.get(
                TEST_URLS.get(proxy.protocol, FALLBACK_URL),
                proxy=proxy_url,
            ) as resp:
                if resp.status == 200:
                    proxy.alive = True
                    proxy.latency = round(time.time() - start, 3)
                    proxy.last_checked = time.time()
                else:
                    proxy.alive = False
    except Exception:
        proxy.alive = False
    finally:
        proxy.last_checked = time.time()
    return proxy


async def validate_async(proxies: List[Proxy], timeout: int = 5, max_concurrent: int = 100) -> List[Proxy]:
    """异步批量验证代理"""
    if not AIOHTTP_AVAILABLE:
        raise ImportError("aiohttp is required: pip install aiohttp")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _limited_check(p: Proxy) -> Proxy:
        async with semaphore:
            return await _check_one_async(p, timeout)

    tasks = [_limited_check(p) for p in proxies]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    alive = []
    for r in results:
        if isinstance(r, Proxy) and r.alive:
            alive.append(r)
    return alive


def _check_one_sync(proxy: Proxy, timeout: int = 5) -> Proxy:
    """同步检测单个代理"""
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests is required")

    start = time.time()
    try:
        r = requests.get(
            TEST_URLS.get(proxy.protocol, FALLBACK_URL),
            proxies=proxy.requests_dict,
            timeout=timeout,
        )
        if r.status_code == 200:
            proxy.alive = True
            proxy.latency = round(time.time() - start, 3)
        else:
            proxy.alive = False
    except Exception:
        proxy.alive = False
    finally:
        proxy.last_checked = time.time()
    return proxy


def validate_sync(proxies: List[Proxy], timeout: int = 5, max_workers: int = 50) -> List[Proxy]:
    """同步批量验证代理（线程池）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    alive = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_one_sync, p, timeout): p for p in proxies}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result.alive:
                    alive.append(result)
            except Exception:
                pass
    return alive
