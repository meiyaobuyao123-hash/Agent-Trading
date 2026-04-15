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

特性：
- 进程内 TTL 缓存，全局共享（所有用户同参数命中同一份数据）
- 缓存击穿保护（同一 key 并发时只穿透 1 次）
- 失败时保留上一份成功数据（stale-while-error）
- LRU 上限 200 条，防止内存泄漏
- key 按 module + function + 参数生成，避免冲突
"""
import asyncio
import logging
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# 单个缓存实例最大条目数（超过后 LRU 淘汰）
_MAX_CACHE_SIZE = 200
# 失败时保留旧数据的最长时间（即使过期也降级返回）
_STALE_WHILE_ERROR_SEC = 600


class TTLCache:
    """进程内 TTL 缓存 — 线程/协程安全 + 缓存击穿保护 + LRU 淘汰"""

    def __init__(self, ttl_seconds: int):
        # OrderedDict 实现简易 LRU：最近访问的移到末尾
        self._cache: "OrderedDict[str, tuple]" = OrderedDict()
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        # 单飞：key → Event，用于合并并发的穿透请求
        self._pending: dict = {}
        self._hits = 0
        self._misses = 0
        self._stale_served = 0

    async def get(self, key: str, allow_stale: bool = False) -> Optional[Any]:
        """获取缓存。allow_stale=True 时，即使过期也返回（在降级窗口内）"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            data, ts = entry
            age = time.time() - ts

            if age <= self._ttl:
                # 新鲜 — 命中
                self._cache.move_to_end(key)
                self._hits += 1
                return data

            # 已过期：保留给 allow_stale 用，除非超过降级窗口才清理
            if age >= _STALE_WHILE_ERROR_SEC:
                del self._cache[key]
                self._misses += 1
                return None

            if allow_stale:
                self._stale_served += 1
                return data

            # 未到清理时间，但也不新鲜，返回 None（让调用方重新计算）
            self._misses += 1
            return None

    async def set(self, key: str, data: Any) -> None:
        async with self._lock:
            self._cache[key] = (data, time.time())
            self._cache.move_to_end(key)
            # LRU 淘汰：超过上限时删最老的
            while len(self._cache) > _MAX_CACHE_SIZE:
                self._cache.popitem(last=False)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "stale_served": self._stale_served,
            "hit_rate": round(self._hits / total * 100, 2) if total > 0 else 0,
        }


def cached(ttl: int):
    """
    装饰器：自动缓存 async 函数的返回值

    Args:
        ttl: 缓存有效期（秒）

    特性：
    - 所有用户共享同一份缓存（按参数区分）
    - 缓存击穿保护：并发穿透时只调用 1 次原函数
    - 失败降级：原函数抛异常时，返回最近 10 分钟内的旧数据（如有）
    """
    cache = TTLCache(ttl)

    def decorator(fn: Callable):
        # key 前缀带上模块名，避免同名函数在不同文件冲突
        fn_id = f"{fn.__module__}.{fn.__name__}"

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            # 构造缓存 key
            key_parts = [fn_id]
            for a in args:
                key_parts.append(str(a))
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}={kwargs[k]}")
            key = ":".join(key_parts)

            # 1. 先查缓存
            hit = await cache.get(key)
            if hit is not None:
                return hit

            # 2. 缓存击穿保护：如果有其他请求正在计算同一 key，等待它
            async with cache._lock:
                pending = cache._pending.get(key)
                if pending is not None:
                    # 已有请求在跑，等它完成
                    event = pending
                else:
                    # 我是第一个，创建 Event 并标记
                    event = asyncio.Event()
                    cache._pending[key] = event
                    is_leader = True
                    pending = None

            if pending is not None:
                # 等待领导者完成
                await event.wait()
                # 领导者已写入缓存，直接读
                hit = await cache.get(key)
                if hit is not None:
                    return hit
                # 领导者失败了，我也失败降级
                return await _fallback_or_raise(cache, key, fn_id)

            # 3. 我是领导者，真正调用原函数
            try:
                result = await fn(*args, **kwargs)
                if result is not None:
                    # 不缓存 error 响应
                    if isinstance(result, dict) and "error" in result and len(result) <= 2:
                        pass
                    else:
                        await cache.set(key, result)
                return result
            except Exception as e:
                log.warning("[%s] failed: %s, trying stale cache", fn_id, e)
                # 失败 → 尝试返回旧数据
                stale = await cache.get(key, allow_stale=True)
                if stale is not None:
                    log.info("[%s] served stale data", fn_id)
                    return stale
                raise
            finally:
                # 唤醒所有等待者，清理 pending
                async with cache._lock:
                    cache._pending.pop(key, None)
                event.set()

        # 暴露缓存实例，方便调试
        wrapper._cache = cache  # type: ignore
        return wrapper

    return decorator


async def _fallback_or_raise(cache: TTLCache, key: str, fn_id: str) -> Any:
    """等待的请求：领导者失败时的降级"""
    stale = await cache.get(key, allow_stale=True)
    if stale is not None:
        log.info("[%s] waiter served stale", fn_id)
        return stale
    raise RuntimeError(f"[{fn_id}] upstream failed and no stale cache available")
