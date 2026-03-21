"""LunarCrush — 社交热度 + Galaxy Score（每 4 小时）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import LUNARCRUSH_URL, LUNARCRUSH_API_KEY, INTERVAL_LOW_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class LunarCrushCollector(BaseCollector):

    def __init__(self):
        super().__init__("lunarcrush", INTERVAL_LOW_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        result = {}
        for symbol in ("BTC", "ETH"):
            url = f"{LUNARCRUSH_URL}/coins/{symbol.lower()}/v1"
            headers = {}
            if LUNARCRUSH_API_KEY:
                headers["Authorization"] = f"Bearer {LUNARCRUSH_API_KEY}"
            try:
                async with self._session.get(url, headers=headers, timeout=_TIMEOUT) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    coin_data = data.get("data", data)
                    if isinstance(coin_data, dict):
                        result[f"{symbol}_social_volume"] = int(coin_data.get("social_volume", 0) or 0)
                        result[f"{symbol}_galaxy_score"] = float(coin_data.get("galaxy_score", 0) or 0)
            except Exception as e:
                log.debug("[LunarCrush] %s: %s", symbol, e)

        # 合并为平均社交量
        btc_sv = result.get("BTC_social_volume", 0)
        eth_sv = result.get("ETH_social_volume", 0)
        result["social_volume"] = btc_sv + eth_sv

        return result
