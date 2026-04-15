"""
API 响应内存缓存 — 减少 Supabase 查询压力

使用场景：统计/聚合类接口，数据变化不频繁，可容忍 TTL 范围内的延迟。
不使用场景：实时信号、价格、告警等对及时性敏感的接口。

用法：
    from api._cache import cached

    @router.get("/pnl-distribution")
    @cached(ttl=300)  # 5分钟缓存
    async def get_pnl_distribution():
        ...
"""
import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class TTLCache:
    """简单的进程内 TTL 缓存（线程/协程安全）"""

    def __init__(self, ttl_seconds: int):
        self._cache: dict = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            data, ts = entry
            if time.time() - ts > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return data

    async def set(self, key: str, data: Any) -> None:
        async with self._lock:
            self._cache[key] = (data, time.time())
            # 简单防爆：超过 100 条时清理已过期的
            if len(self._cache) > 100:
                now = time.time()
                expired = [k for k, (_, t) in self._cache.items() if now - t > self._ttl]
                for k in expired:
                    del self._cache[k]

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 2) if total > 0 else 0,
        }


def cached(ttl: int):
    """
    装饰器：自动缓存 async 函数的返回值

    Args:
        ttl: 缓存有效期（秒）

    Example:
        @cached(ttl=300)
        async def my_api(param1: str, param2: int = 10):
            ...
    """
    cache = TTLCache(ttl)

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            # 构造缓存 key：函数名 + 参数
            key_parts = [fn.__name__]
            for a in args:
                key_parts.append(str(a))
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}={kwargs[k]}")
            key = ":".join(key_parts)

            hit = await cache.get(key)
            if hit is not None:
                return hit

            result = await fn(*args, **kwargs)
            if result is not None:
                await cache.set(key, result)
            return result

        # 暴露缓存实例，方便调试
        wrapper._cache = cache  # type: ignore
        return wrapper

    return decorator
