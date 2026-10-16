"""SQLite 缓存 — CacheManager 类"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional


class CacheManager:
    """SQLite 缓存管理器。

    缓存键格式：{dept}:{version}:{depth}:{model}:{temp}
    数据以 JSON 字符串持久化。
    """

    def __init__(self, db_path: str = "./cache.db"):
        self._db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """初始化数据库表结构"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    ttl   INTEGER DEFAULT 0,
                    set_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
                """
            )
            conn.commit()

    @staticmethod
    def _make_key(dept: str, version: str, depth: str, model: str, temp: str) -> str:
        """按约定格式生成缓存键"""
        return f"{dept}:{version}:{depth}:{model}:{temp}"

    def get(self, dept: str, version: str, depth: str, model: str, temp: str) -> Optional[str]:
        """读取缓存，若已过期则返回 None"""
        key = self._make_key(dept, version, depth, model, temp)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT value, ttl, set_at FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        value, ttl, set_at = row
        if ttl > 0 and set_at + ttl < int(__import__("time").time()):
            self.delete(key)
            return None
        return value

    def put(self, dept: str, version: str, depth: str, model: str, temp: str, value: str, ttl: int = 3600) -> None:
        """写入缓存，设置 TTL（秒）"""
        key = self._make_key(dept, version, depth, model, temp)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, ttl, set_at) VALUES (?, ?, ?, strftime('%s', 'now'))",
                (key, value, ttl),
            )
            conn.commit()

    def delete(self, key: str) -> None:
        """删除指定缓存"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    def clear(self) -> None:
        """清除所有缓存"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def keys(self) -> list[str]:
        """列出所有缓存键"""
        with sqlite3.connect(self._db_path) as conn:
            return [row[0] for row in conn.execute("SELECT key FROM cache")]

    def count(self) -> int:
        """缓存条目数量"""
        with sqlite3.connect(self._db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
