"""
多源代理抓取器 — 从 GitHub 公开仓库和公开 API 抓取代理列表
"""
import re
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


# ── 数据源定义 ──────────────────────────────────────────────

GITHUB_SOURCES = [
    # monosans/proxy-list — 每小时更新
    {
        "name": "monosans",
        "urls": {
            "http": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "socks4": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
            "socks5": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        },
    },
    # proxifly/free-proxy-list — 每5分钟更新
    {
        "name": "proxifly",
        "urls": {
            "http": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/http.txt",
            "socks4": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/socks4.txt",
            "socks5": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/socks5.txt",
        },
    },
    # TheSpeedX/PROXY-List — 每天更新
    {
        "name": "TheSpeedX",
        "urls": {
            "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        },
    },
    # clarketm/proxy-list — 每天更新
    {
        "name": "clarketm",
        "urls": {
            "http": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        },
    },
    # jetkai/proxy-list — 每小时更新
    {
        "name": "jetkai",
        "urls": {
            "http": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/http.txt",
            "socks4": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/socks4.txt",
            "socks5": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/socks5.txt",
        },
    },
    # roxkso/free-proxy-list — 每天更新
    {
        "name": "roxkso",
        "urls": {
            "http": "https://raw.githubusercontent.com/roxkso/free-proxy-list/main/http.txt",
            "socks5": "https://raw.githubusercontent.com/roxkso/free-proxy-list/main/socks5.txt",
        },
    },
    # MuRongPIG/Proxy-Master
    {
        "name": "MuRongPIG",
        "urls": {
            "http": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
            "socks5": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
        },
    },
    # yemixeng/proxy-list
    {
        "name": "yemixeng",
        "urls": {
            "http": "https://raw.githubusercontent.com/yemixeng/proxy-list/main/proxy-list/data.txt",
        },
    },
    # officialputuid/KangProxy
    {
        "name": "KangProxy",
        "urls": {
            "http": "https://raw.githubusercontent.com/officialputuid/KangProxy/main/http.txt",
            "socks5": "https://raw.githubusercontent.com/officialputuid/KangProxy/main/socks5.txt",
        },
    },
    # saeidgholamitabar/ProxyList
    {
        "name": "saeidgh",
        "urls": {
            "http": "https://raw.githubusercontent.com/saeidgholamitabar/ProxyList/main/http.txt",
            "socks5": "https://raw.githubusercontent.com/saeidgholamitabar/ProxyList/main/socks5.txt",
        },
    },
]

API_SOURCES = [
    {
        "name": "ProxyScrape-http",
        "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&proxy_filter=normal",
        "protocol": "http",
        "format": "txt",
    },
    {
        "name": "ProxyScrape-socks5",
        "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&proxy_filter=normal",
        "protocol": "socks5",
        "format": "txt",
    },
    {
        "name": "Geonode",
        "url": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "protocol": "auto",
        "format": "json",
    },
]


# ── 解析器 ──────────────────────────────────────────────────

def _parse_txt(content: str, protocol: str, source: str) -> List[Proxy]:
    proxies = []
    for line in content.strip().split("\n"):
        p = Proxy.from_line(line, protocol=protocol, source=source)
        if p:
            proxies.append(p)
    return proxies


def _parse_geonode_json(content: str, source: str) -> List[Proxy]:
    import json
    proxies = []
    try:
        data = json.loads(content)
        items = data.get("data", [])
        for item in items:
            ip = item.get("ip")
            port = item.get("port")
            proto = item.get("protocols", ["http"])
            if isinstance(proto, list) and proto:
                proto = proto[0]
            country = item.get("country")
            if ip and port:
                try:
                    proxies.append(Proxy(
                        ip=str(ip),
                        port=int(port),
                        protocol=str(proto).lower(),
                        country=country,
                        source=source,
                    ))
                except (ValueError, TypeError):
                    pass
    except (json.JSONDecodeError, KeyError):
        pass
    return proxies


# ── 同步抓取 ────────────────────────────────────────────────

def fetch_all_sync(timeout: int = 15) -> List[Proxy]:
    """同步抓取所有数据源，返回去重后的代理列表"""
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests is required: pip install requests")

    all_proxies = []
    seen = set()

    # GitHub sources
    for src in GITHUB_SOURCES:
        for proto, url in src["urls"].items():
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200 and r.text.strip():
                    for p in _parse_txt(r.text, proto, src["name"]):
                        key = (p.ip, p.port, p.protocol)
                        if key not in seen:
                            seen.add(key)
                            all_proxies.append(p)
            except Exception:
                pass

    # API sources
    for src in API_SOURCES:
        try:
            r = requests.get(src["url"], timeout=timeout)
            if r.status_code != 200 or not r.text.strip():
                continue
            if src["format"] == "json":
                for p in _parse_geonode_json(r.text, src["name"]):
                    key = (p.ip, p.port, p.protocol)
                    if key not in seen:
                        seen.add(key)
                        all_proxies.append(p)
            else:
                for p in _parse_txt(r.text, src["protocol"], src["name"]):
                    key = (p.ip, p.port, p.protocol)
                    if key not in seen:
                        seen.add(key)
                        all_proxies.append(p)
        except Exception:
            pass

    return all_proxies


# ── 异步抓取 ────────────────────────────────────────────────

async def fetch_all_async(timeout: int = 15) -> List[Proxy]:
    """异步抓取所有数据源"""
    if not AIOHTTP_AVAILABLE:
        raise ImportError("aiohttp is required: pip install aiohttp")

    all_proxies = []
    seen = set()

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        # GitHub sources
        tasks = []
        for src in GITHUB_SOURCES:
            for proto, url in src["urls"].items():
                tasks.append(_fetch_one(session, url, proto, src["name"], "txt"))

        # API sources
        for src in API_SOURCES:
            tasks.append(_fetch_one(session, src["url"], src["protocol"], src["name"], src["format"]))

        import asyncio
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                for p in result:
                    key = (p.ip, p.port, p.protocol)
                    if key not in seen:
                        seen.add(key)
                        all_proxies.append(p)

    return all_proxies


async def _fetch_one(session, url: str, protocol: str, source: str, fmt: str) -> List[Proxy]:
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()
            if not text.strip():
                return []
            if fmt == "json":
                return _parse_geonode_json(text, source)
            return _parse_txt(text, protocol, source)
    except Exception:
        return []
