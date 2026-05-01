"""
Redis 单例 + fail-safe 包装

为什么:
  跨进程 IPC（pump-scanner 主进程 → pump-scanner-api 进程)
  原文件 IPC (/tmp/pump_signal_pool.json) 60s dump → API 最差 60s 延迟
  Redis 改 5s dump → 毫秒级读 + 跨实例可扩展

设计原则:
  1. Singleton — 整个进程一个 client
  2. Fail-safe — 连不上 Redis 不能阻塞主流程,降级到文件 IPC
  3. 同步 + 异步 API 都给(主 loop 用 sync,API handler 用 async)
  4. 无侵入 — 只读环境变量 REDIS_URL,默认 redis://localhost:6379/0
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "1.0"))

_client_lock = threading.Lock()
_client: Optional[object] = None
_async_client: Optional[object] = None
_redis_available: Optional[bool] = None  # None=未试 / True=可用 / False=不可用


def _try_import_redis():
    try:
        import redis  # type: ignore
        return redis
    except ImportError:
        log.warning("redis 包未安装,Redis IPC 降级到文件 IPC (pip install redis>=5.0)")
        return None


def get_client():
    """同步 client。返回 None 表示不可用,调用方降级文件 IPC。"""
    global _client, _redis_available
    if _redis_available is False:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        redis = _try_import_redis()
        if redis is None:
            _redis_available = False
            return None
        try:
            c = redis.Redis.from_url(
                REDIS_URL,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
            c.ping()
            _client = c
            _redis_available = True
            log.info("Redis client 已连接 %s", REDIS_URL)
            return _client
        except Exception as e:
            log.warning("Redis 连接失败 (%s),降级到文件 IPC: %s", REDIS_URL, e)
            _redis_available = False
            return None


async def get_async_client():
    """异步 client。返回 None 表示不可用。"""
    global _async_client, _redis_available
    if _redis_available is False:
        return None
    if _async_client is not None:
        return _async_client
    redis = _try_import_redis()
    if redis is None:
        _redis_available = False
        return None
    try:
        from redis import asyncio as aioredis  # type: ignore
        c = aioredis.from_url(
            REDIS_URL,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
        await c.ping()
        _async_client = c
        _redis_available = True
        log.info("Redis async client 已连接 %s", REDIS_URL)
        return _async_client
    except Exception as e:
        log.warning("Redis async 连接失败 (%s),降级到文件 IPC: %s", REDIS_URL, e)
        _redis_available = False
        return None


def safe_set(key: str, value: str, ex: Optional[int] = None) -> bool:
    """fail-safe set。返回 False 表示失败(调用方应降级文件)。"""
    c = get_client()
    if c is None:
        return False
    try:
        c.set(key, value, ex=ex)
        return True
    except Exception as e:
        log.warning("Redis set %s 失败: %s", key, e)
        return False


async def safe_get_async(key: str) -> Optional[str]:
    """fail-safe async get。返回 None 表示 key 不存在或 Redis 不可用。"""
    c = await get_async_client()
    if c is None:
        return None
    try:
        return await c.get(key)
    except Exception as e:
        log.warning("Redis get %s 失败: %s", key, e)
        return None


def reset_for_test():
    """测试用:重置 client 状态。"""
    global _client, _async_client, _redis_available
    _client = None
    _async_client = None
    _redis_available = None


# 共享 key 命名空间
KEY_PUMP_SIGNAL_POOL = "pump:signal_pool"
