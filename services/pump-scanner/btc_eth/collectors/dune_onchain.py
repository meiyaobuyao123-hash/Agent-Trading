"""Dune Analytics — 链上数据（每日）

查询：交易所 BTC/ETH 净流入、SOPR、大额转账
复用已有 Dune API Key。
"""
import logging
from typing import Dict, Any, Optional

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import (
    DUNE_API_KEY, DUNE_URL, INTERVAL_DAILY,
    DUNE_BTC_EXCHANGE_FLOW_QUERY, DUNE_ETH_EXCHANGE_FLOW_QUERY,
)

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=60)


class DuneOnchainCollector(BaseCollector):

    def __init__(self):
        super().__init__("dune_onchain", INTERVAL_DAILY)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        if not DUNE_API_KEY:
            return {}

        result = {}

        # BTC 交易所净流入
        if DUNE_BTC_EXCHANGE_FLOW_QUERY:
            btc_flow = await self._get_query_result(DUNE_BTC_EXCHANGE_FLOW_QUERY)
            if btc_flow:
                result["BTC_exchange_netflow"] = btc_flow

        # ETH 交易所净流入
        if DUNE_ETH_EXCHANGE_FLOW_QUERY:
            eth_flow = await self._get_query_result(DUNE_ETH_EXCHANGE_FLOW_QUERY)
            if eth_flow:
                result["ETH_exchange_netflow"] = eth_flow

        return result

    async def _get_query_result(self, query_id: str) -> Optional[Dict[str, Any]]:
        """获取 Dune 查询最新结果"""
        try:
            headers = {"X-Dune-API-Key": DUNE_API_KEY}
            url = f"{DUNE_URL}/query/{query_id}/results"
            async with self._session.get(url, headers=headers, timeout=_TIMEOUT) as resp:
                if resp.status != 200:
                    log.debug("[Dune] query %s HTTP %d", query_id, resp.status)
                    return None
                data = await resp.json()
                rows = data.get("result", {}).get("rows", [])
                if rows:
                    return rows[0]  # 最新一行
        except Exception as e:
            log.debug("[Dune] query %s: %s", query_id, e)
        return None
