from __future__ import annotations

from cachetools import TTLCache


class Cache:
    def __init__(self, *, maxsize: int, ttl_seconds: int) -> None:
        self._cache: TTLCache[str, object] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

    def get(self, key: str) -> object | None:
        return self._cache.get(key)

    def set(self, key: str, value: object) -> None:
        self._cache[key] = value
