"""
FastAPI REST API 服务
"""
from typing import Optional
from fastapi import FastAPI, Query
from .core import ProxyPool

app = FastAPI(title="ProxyPool API", version="1.0.0")
_pool: Optional[ProxyPool] = None


def get_pool() -> ProxyPool:
    global _pool
    if _pool is None:
        _pool = ProxyPool(auto_fetch=False)
    return _pool


@app.on_event("startup")
async def startup():
    global _pool
    _pool = ProxyPool(auto_fetch=True, auto_validate=False)


@app.get("/api/proxy")
async def get_proxy(
    protocol: Optional[str] = Query(None, description="http/https/socks4/socks5"),
    strategy: str = Query("random", description="random/round_robin/fastest"),
):
    """获取单个代理"""
    pool = get_pool()
    proxy = pool.get_proxy(protocol=protocol, strategy=strategy)
    if proxy:
        return proxy.to_dict()
    return {"error": "no proxy available"}


@app.get("/api/proxies")
async def get_proxies(
    count: int = Query(10, ge=1, le=1000),
    protocol: Optional[str] = Query(None),
    strategy: str = Query("random"),
):
    """批量获取代理"""
    pool = get_pool()
    proxies = pool.get_proxies(count=count, protocol=protocol, strategy=strategy)
    return {"count": len(proxies), "proxies": [p.to_dict() for p in proxies]}


@app.get("/api/all")
async def get_all(protocol: Optional[str] = Query(None)):
    """获取全部可用代理"""
    pool = get_pool()
    proxies = pool.get_all(protocol=protocol)
    return {"count": len(proxies), "proxies": [p.to_dict() for p in proxies]}


@app.post("/api/refresh")
async def refresh(validate: bool = Query(False)):
    """刷新代理池"""
    pool = get_pool()
    result = await pool.refresh_async(validate=validate)
    return result


@app.get("/api/stats")
async def stats():
    """代理池统计"""
    pool = get_pool()
    return pool.stats()


@app.get("/api/export")
async def export(
    protocol: Optional[str] = Query(None),
    fmt: str = Query("txt", description="txt/json/csv"),
):
    """导出代理列表"""
    pool = get_pool()
    return {"data": pool.export(protocol=protocol, fmt=fmt)}
