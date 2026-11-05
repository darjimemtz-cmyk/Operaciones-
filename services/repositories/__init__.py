"""
Repository Layer Foundation - FNG San Luis Potosí
Optimized SQLite connection pool with WAL mode and in-memory TTL cache.
"""

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, TypeVar

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "control_maestro_v6.db")

# Thread-local storage for connections
_thread_local = threading.local()

# Simple TTL cache: key -> (value, expires_at)
_cache: Dict[str, Tuple[Any, float]] = {}
_cache_lock = threading.Lock()

# Default TTL in seconds
DEFAULT_TTL = 30  # 30 seconds for static catalogs
LONG_TTL = 60     # 60 seconds for slower-changing data


@dataclass
class CacheConfig:
    """Cache configuration per query type."""
    ttl: int = DEFAULT_TTL
    key_prefix: str = ""


def get_db_connection() -> sqlite3.Connection:
    """
    Get a thread-local SQLite connection with WAL mode enabled.
    Reuses connection within the same thread for performance.
    """
    if not hasattr(_thread_local, "conn") or _thread_local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high-concurrency reads
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-32768")  # 32MB cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        _thread_local.conn = conn
    return _thread_local.conn


def close_db_connection() -> None:
    """Close the thread-local connection if exists."""
    if hasattr(_thread_local, "conn") and _thread_local.conn is not None:
        _thread_local.conn.close()
        _thread_local.conn = None


@contextmanager
def db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for database cursor with automatic cleanup."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def cache_get(key: str) -> Optional[Any]:
    """Get value from cache if not expired."""
    with _cache_lock:
        if key in _cache:
            value, expires_at = _cache[key]
            if time.time() < expires_at:
                return value
            else:
                del _cache[key]
    return None


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Set value in cache with TTL."""
    with _cache_lock:
        _cache[key] = (value, time.time() + ttl)


def cache_invalidate(pattern: str = "") -> None:
    """Invalidate cache entries matching pattern (or all if empty)."""
    with _cache_lock:
        if not pattern:
            _cache.clear()
        else:
            keys_to_del = [k for k in _cache if pattern in k]
            for k in keys_to_del:
                del _cache[k]


def cached_query(key: str, query_fn: Callable[[], Any], ttl: int = DEFAULT_TTL) -> Any:
    """
    Execute query with caching. Returns cached value if valid, otherwise executes query and caches result.
    """
    cached = cache_get(key)
    if cached is not None:
        return cached
    result = query_fn()
    cache_set(key, result, ttl)
    return result


T = TypeVar("T")


def rows_to_dicts(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
    """Convert cursor rows to list of dicts."""
    return [dict(row) for row in cursor.fetchall()]


def row_to_dict(cursor: sqlite3.Cursor) -> Optional[Dict[str, Any]]:
    """Convert single row to dict."""
    row = cursor.fetchone()
    return dict(row) if row else None


# Export commonly used symbols
__all__ = [
    "DB_PATH",
    "get_db_connection",
    "close_db_connection",
    "db_cursor",
    "cache_get",
    "cache_set",
    "cache_invalidate",
    "cached_query",
    "rows_to_dicts",
    "row_to_dict",
    "DEFAULT_TTL",
    "LONG_TTL",
    "CacheConfig",
]