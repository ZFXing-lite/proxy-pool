"""
SQLite 缓存存储 — 代理池本地持久化
"""
import sqlite3
import json
import time
import os
from typing import List, Optional
from .models import Proxy

DEFAULT_DB_PATH = os.path.join(os.path.expanduser("~"), ".proxy_pool", "proxies.db")


class Cache:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proxies (
                    ip TEXT,
                    port INTEGER,
                    protocol TEXT,
                    country TEXT,
                    latency REAL,
                    last_checked REAL,
                    alive INTEGER,
                    source TEXT,
                    PRIMARY KEY (ip, port, protocol)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, proxies: List[Proxy]):
        """批量保存代理（upsert）"""
        with self._conn() as conn:
            for p in proxies:
                conn.execute("""
                    INSERT OR REPLACE INTO proxies
                    (ip, port, protocol, country, latency, last_checked, alive, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.ip, p.port, p.protocol, p.country,
                    p.latency, p.last_checked, int(p.alive), p.source
                ))
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("last_update", str(time.time()))
            )

    def load(self, protocol: str = None, only_alive: bool = True,
             limit: int = 0, sort_by_latency: bool = True) -> List[Proxy]:
        """从缓存加载代理"""
        query = "SELECT * FROM proxies WHERE 1=1"
        params = []
        if only_alive:
            query += " AND alive = 1"
        if protocol:
            query += " AND protocol = ?"
            params.append(protocol)
        if sort_by_latency:
            query += " ORDER BY latency ASC"
        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [Proxy(
            ip=row["ip"],
            port=row["port"],
            protocol=row["protocol"],
            country=row["country"],
            latency=row["latency"],
            last_checked=row["last_checked"],
            alive=bool(row["alive"]),
            source=row["source"],
        ) for row in rows]

    def count(self, protocol: str = None, only_alive: bool = True) -> int:
        query = "SELECT COUNT(*) as c FROM proxies WHERE 1=1"
        params = []
        if only_alive:
            query += " AND alive = 1"
        if protocol:
            query += " AND protocol = ?"
            params.append(protocol)
        with self._conn() as conn:
            return conn.execute(query, params).fetchone()["c"]

    def clear(self):
        with self._conn() as conn:
            conn.execute("DELETE FROM proxies")

    def last_update(self) -> Optional[float]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'last_update'"
            ).fetchone()
            return float(row["value"]) if row else None

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM proxies").fetchone()["c"]
            alive = conn.execute("SELECT COUNT(*) as c FROM proxies WHERE alive = 1").fetchone()["c"]
            by_proto = {}
            for row in conn.execute(
                "SELECT protocol, COUNT(*) as c FROM proxies WHERE alive = 1 GROUP BY protocol"
            ).fetchall():
                by_proto[row["protocol"]] = row["c"]
            by_source = {}
            for row in conn.execute(
                "SELECT source, COUNT(*) as c FROM proxies WHERE alive = 1 GROUP BY source"
            ).fetchall():
                by_source[row["source"]] = row["c"]
        return {
            "total": total,
            "alive": alive,
            "by_protocol": by_proto,
            "by_source": by_source,
            "last_update": self.last_update(),
        }
