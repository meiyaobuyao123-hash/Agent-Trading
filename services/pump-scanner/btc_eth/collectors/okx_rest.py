"""OKX REST — 合约数据（每 5 分钟，跨交易所验证）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import INTERVAL_HIGH_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_BASE = "https://www.okx.com"


class OkxRestCollector(BaseCollector):

    def __init__(self):
        super().__init__("okx_rest", INTERVAL_HIGH_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        result = {}
        for asset, inst_id in [("BTC", "BTC-USDT-SWAP"), ("ETH", "ETH-USDT-SWAP")]:
            data = {}
            # 资金费率
            fr = await self._get(f"{_BASE}/api/v5/public/funding-rate", {"instId": inst_id})
            if fr and fr.get("data"):
                data["okx_funding_rate"] = float(fr["data"][0].get("fundingRate", 0))

            # 多空比
            ls = await self._get(
                f"{_BASE}/api/v5/rubik/stat/contracts/long-short-account-ratio",
                {"ccy": asset, "period": "5m"}
            )
            if ls and ls.get("data"):
                data["okx_long_short"] = float(ls["data"][0][1]) if ls["data"][0] else 1.0

            # 持仓量
            oi = await self._get(
                f"{_BASE}/api/v5/rubik/stat/contracts/open-interest-volume",
                {"ccy": asset, "period": "5m"}
            )
            if oi and oi.get("data"):
                data["okx_oi"] = float(oi["data"][0][1]) if ls["data"][0] else 0

            result[asset] = data
        return result

    async def _get(self, url, params):
        try:
            async with self._session.get(url, params=params, timeout=_TIMEOUT,
                                         headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            log.debug("[OKX REST] %s: %s", url.split("/")[-1], e)
        return None
