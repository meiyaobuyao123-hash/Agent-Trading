"""Alternative.me — 恐慌贪婪指数（每 4 小时）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import ALTERNATIVE_ME_URL, INTERVAL_LOW_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class AlternativeMeCollector(BaseCollector):

    def __init__(self):
        super().__init__("alternative_me", INTERVAL_LOW_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        async with self._session.get(ALTERNATIVE_ME_URL, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}")
            data = await resp.json()

        items = data.get("data", [])
        if not items:
            return {}

        latest = items[0]
        return {
            "fear_greed_index": int(latest.get("value", 50)),
            "fear_greed_label": latest.get("value_classification", "Neutral"),
        }
