"""Blockchain.com Charts API — BTC 链上指标（每 4 小时）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import BLOCKCHAIN_CHARTS_URL, INTERVAL_LOW_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=15)


class BlockchainOnchainCollector(BaseCollector):

    def __init__(self):
        super().__init__("blockchain_onchain", INTERVAL_LOW_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        result = {}

        charts = {
            "hash_rate": "hash-rate",
            "active_addresses": "n-unique-addresses",
            "miners_revenue": "miners-revenue",
            "tx_volume_usd": "estimated-transaction-volume-usd",
            "mempool_size_mb": "mempool-size",
            "avg_fee_sat_vb": "fees-usd-per-transaction",
        }

        for key, chart_name in charts.items():
            url = f"{BLOCKCHAIN_CHARTS_URL}/{chart_name}?timespan=2days&format=json"
            val = await self._get_latest_value(url)
            if val is not None:
                result[key] = val

        return result

    async def _get_latest_value(self, url: str):
        try:
            async with self._session.get(url, timeout=_TIMEOUT) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                values = data.get("values", [])
                if values:
                    return float(values[-1].get("y", 0))
        except Exception as e:
            log.debug("[Blockchain.com] %s: %s", url.split("/")[-2], e)
        return None
