"""数据采集器抽象基类 — 断路器 + 健康检查 + 指数退避"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from btc_eth.config import COLLECTOR_MAX_FAILURES, COLLECTOR_BACKOFF_BASE, COLLECTOR_BACKOFF_MAX

log = logging.getLogger(__name__)


class BaseCollector(ABC):
    """所有数据采集器的基类"""

    def __init__(self, name: str, interval_seconds: int):
        self.name = name
        self.interval = interval_seconds
        self._healthy = True
        self._last_success = None       # type: Optional[float]
        self._last_attempt = None       # type: Optional[float]
        self._consecutive_failures = 0
        self._total_successes = 0
        self._total_failures = 0

    @abstractmethod
    async def collect(self) -> Dict[str, Any]:
        """子类实现：获取数据，返回归一化 dict。失败时 raise。"""
        ...

    async def safe_collect(self) -> Optional[Dict[str, Any]]:
        """安全封装：断路器 + 错误计数 + 退避"""
        self._last_attempt = time.time()

        # 断路器：连续失败超限 → 指数退避
        if self._consecutive_failures >= COLLECTOR_MAX_FAILURES:
            backoff = min(
                COLLECTOR_BACKOFF_BASE ** self._consecutive_failures,
                COLLECTOR_BACKOFF_MAX
            )
            if self._last_success and (time.time() - self._last_attempt) < backoff:
                return None  # 还在退避中

        try:
            data = await self.collect()
            self._healthy = True
            self._last_success = time.time()
            self._consecutive_failures = 0
            self._total_successes += 1
            return data
        except Exception as e:
            self._consecutive_failures += 1
            self._total_failures += 1
            self._healthy = self._consecutive_failures < COLLECTOR_MAX_FAILURES
            log.warning(
                "[%s] 采集失败 (%d/%d): %s",
                self.name, self._consecutive_failures, COLLECTOR_MAX_FAILURES, e
            )
            return None

    def health(self) -> Dict[str, Any]:
        """返回健康状态"""
        return {
            "name": self.name,
            "healthy": self._healthy,
            "last_success": self._last_success,
            "consecutive_failures": self._consecutive_failures,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "interval_seconds": self.interval,
        }
