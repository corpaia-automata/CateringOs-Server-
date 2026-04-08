"""
Thread-safe in-memory cache with per-entry TTL.
Used as a Redis substitute for tenant config caching.
"""
import time
from threading import Lock

_store: dict = {}
_lock = Lock()


def get(key: str):
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del _store[key]
            return None
        return value


def set(key: str, value, ttl: int = 300):
    with _lock:
        _store[key] = (value, time.monotonic() + ttl)


def delete(key: str):
    with _lock:
        _store.pop(key, None)
