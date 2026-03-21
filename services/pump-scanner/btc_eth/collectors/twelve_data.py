"""Twelve Data — DXY / 标普500 / 黄金（每 4 小时）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import TWELVE_DATA_API_KEY, TWELVE_DATA_URL, INTERVAL_LOW_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class TwelveDataCollector(BaseCollector):

    def __init__(self):
        super().__init__("twelve_data", INTERVAL_LOW_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        if not TWELVE_DATA_API_KEY:
            return {}

        result = {}
        symbols = {
            "dxy_index": "DXY",
            "sp500_change_pct": "SPX",
            "gold_change_pct": "XAU/USD",
        }

        for key, symbol in symbols.items():
            url = f"{TWELVE_DATA_URL}/quote"
            params = {"symbol": symbol, "apikey": TWELVE_DATA_API_KEY}
            try:
                async with self._session.get(url, params=params, timeout=_TIMEOUT) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if "percent_change" in data:
                        if key == "dxy_index":
                            result[key] = float(data.get("close", 100))
                        else:
                            result[key] = float(data.get("percent_change", 0))
            except Exception as e:
                log.debug("[TwelveData] %s: %s", symbol, e)

        return result
