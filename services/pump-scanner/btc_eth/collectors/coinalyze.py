"""Coinalyze — 全网聚合 OI + 费率（每 30 分钟）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import COINALYZE_URL, INTERVAL_MID_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class CoinalyzeCollector(BaseCollector):

    def __init__(self):
        super().__init__("coinalyze", INTERVAL_MID_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        result = {}

        for asset, symbol in [("BTC", "BTCUSD_PERP.A"), ("ETH", "ETHUSD_PERP.A")]:
            # 聚合 OI
            oi_url = f"{COINALYZE_URL}/open-interest"
            try:
                async with self._session.get(
                    oi_url, params={"symbols": symbol}, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            result[f"{asset}_agg_oi"] = float(data[0].get("value", 0) if isinstance(data, list) else 0)
            except Exception as e:
                log.debug("[Coinalyze] OI %s: %s", asset, e)

            # 聚合费率
            fr_url = f"{COINALYZE_URL}/funding-rate"
            try:
                async with self._session.get(
                    fr_url, params={"symbols": symbol}, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            result[f"{asset}_agg_funding"] = float(data[0].get("value", 0) if isinstance(data, list) else 0)
            except Exception as e:
                log.debug("[Coinalyze] FR %s: %s", asset, e)

        return result
