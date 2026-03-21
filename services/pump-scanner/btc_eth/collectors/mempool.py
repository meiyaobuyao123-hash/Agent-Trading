"""Mempool.space — BTC mempool 拥堵状态（每 30 分钟）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import MEMPOOL_URL, INTERVAL_MID_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class MempoolCollector(BaseCollector):

    def __init__(self):
        super().__init__("mempool", INTERVAL_MID_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        result = {}

        # 推荐手续费
        async with self._session.get(
            f"{MEMPOOL_URL}/v1/fees/recommended", timeout=_TIMEOUT
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                result["avg_fee_sat_vb"] = float(data.get("halfHourFee", 0))

        # Mempool 统计
        async with self._session.get(
            f"{MEMPOOL_URL}/mempool", timeout=_TIMEOUT
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                vsize = data.get("vsize", 0)
                result["mempool_size_mb"] = round(vsize / 1e6, 2)

        return result
