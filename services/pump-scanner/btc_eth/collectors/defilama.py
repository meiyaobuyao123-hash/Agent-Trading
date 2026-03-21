"""DeFiLlama — ETF 资金流 + 稳定币市值 + TVL（每 4 小时）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import DEFILAMA_URL, INTERVAL_LOW_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=15)


class DeFiLlamaCollector(BaseCollector):

    def __init__(self):
        super().__init__("defilama", INTERVAL_LOW_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        result = {}

        # 1. 稳定币总市值
        stables = await self._get(f"{DEFILAMA_URL}/v2/stablecoins")
        if stables:
            total_mcap = 0
            for s in stables.get("peggedAssets", []):
                chains = s.get("chainCirculating", {})
                for chain_data in chains.values():
                    total_mcap += float(chain_data.get("current", {}).get("peggedUSD", 0) or 0)
            result["stablecoin_mcap"] = total_mcap

        # 2. ETH 生态 TVL
        tvl = await self._get(f"{DEFILAMA_URL}/v2/chains")
        if tvl:
            eth_tvl = 0
            for chain in tvl:
                if chain.get("name") == "Ethereum":
                    eth_tvl = float(chain.get("tvl", 0))
                    break
            result["total_tvl_usd"] = eth_tvl

        # 3. BTC/ETH ETF flows（DeFiLlama 可能没有直接端点，用 protocol 数据）
        # 备选：直接查已知 ETF 协议
        protocols = await self._get(f"{DEFILAMA_URL}/protocols")
        if protocols:
            for p in protocols:
                name_lower = (p.get("name", "") or "").lower()
                if "ibit" in name_lower or "blackrock" in name_lower:
                    result["etf_flow_usd"] = float(p.get("change_1d", 0) or 0)
                    break

        return result

    async def _get(self, url: str):
        try:
            async with self._session.get(url, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            log.debug("[DeFiLlama] %s: %s", url.split("/")[-1], e)
        return None
