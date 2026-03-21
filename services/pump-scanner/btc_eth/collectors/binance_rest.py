"""Binance REST — 合约市场数据（每 5 分钟）

采集指标：
  1. 大户多空比 (topLongShortPositionRatio)
  2. 散户多空比 (globalLongShortAccountRatio)
  3. 主动买卖量 (takerlongshortRatio)
  4. 未平仓量 (openInterest + openInterestHist)
  5. 爆仓数据 (forceOrders)
  6. 资金费率 (fundingRate)
  7. 订单簿深度 (depth)
"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import BINANCE_FAPI_URL, BINANCE_REST_URL, INTERVAL_HIGH_FREQ

log = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class BinanceRestCollector(BaseCollector):
    """Binance 合约 REST API 采集器"""

    def __init__(self):
        super().__init__("binance_rest", INTERVAL_HIGH_FREQ)
        self._session = None  # type: aiohttp.ClientSession

    async def init(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        """采集 BTC + ETH 的合约市场数据"""
        result = {}
        for asset, symbol in [("BTC", "BTCUSDT"), ("ETH", "ETHUSDT")]:
            data = {}

            # 1. 大户多空比
            top_ls = await self._get(
                f"{BINANCE_FAPI_URL}/futures/data/topLongShortPositionRatio",
                {"symbol": symbol, "period": "5m", "limit": 1}
            )
            if top_ls:
                data["long_short_ratio"] = float(top_ls[0].get("longShortRatio", 1))

            # 2. 散户多空比
            retail_ls = await self._get(
                f"{BINANCE_FAPI_URL}/futures/data/globalLongShortAccountRatio",
                {"symbol": symbol, "period": "5m", "limit": 1}
            )
            if retail_ls:
                data["retail_long_short"] = float(retail_ls[0].get("longShortRatio", 1))

            # 3. 主动买卖量
            taker = await self._get(
                f"{BINANCE_FAPI_URL}/futures/data/takerlongshortRatio",
                {"symbol": symbol, "period": "5m", "limit": 1}
            )
            if taker:
                data["taker_buy_sell_ratio"] = float(taker[0].get("buyVol", 0)) / max(
                    float(taker[0].get("sellVol", 1)), 0.001
                )

            # 4. 未平仓量
            oi = await self._get(
                f"{BINANCE_FAPI_URL}/fapi/v1/openInterest",
                {"symbol": symbol}
            )
            if oi:
                data["oi_usd"] = float(oi.get("openInterest", 0))

            oi_hist = await self._get(
                f"{BINANCE_FAPI_URL}/futures/data/openInterestHist",
                {"symbol": symbol, "period": "5m", "limit": 2}
            )
            if oi_hist and len(oi_hist) >= 2:
                old_oi = float(oi_hist[0].get("sumOpenInterestValue", 1))
                new_oi = float(oi_hist[1].get("sumOpenInterestValue", 1))
                data["oi_change_4h"] = (new_oi - old_oi) / max(old_oi, 1)

            # 5. 爆仓数据
            liqs = await self._get(
                f"{BINANCE_FAPI_URL}/fapi/v1/forceOrders",
                {"symbol": symbol, "limit": 100}
            )
            if liqs:
                total_liq = sum(float(l.get("origQty", 0)) * float(l.get("price", 0)) for l in liqs)
                long_liq = sum(
                    float(l.get("origQty", 0)) * float(l.get("price", 0))
                    for l in liqs if l.get("side") == "SELL"  # SELL = long 被清算
                )
                data["liquidation_24h_usd"] = total_liq
                data["liq_long_pct"] = long_liq / max(total_liq, 1)

            # 6. 资金费率
            funding = await self._get(
                f"{BINANCE_FAPI_URL}/fapi/v1/fundingRate",
                {"symbol": symbol, "limit": 1}
            )
            if funding:
                data["funding_rate"] = float(funding[0].get("fundingRate", 0))

            # 7. 订单簿深度
            depth = await self._get(
                f"{BINANCE_FAPI_URL}/fapi/v1/depth",
                {"symbol": symbol, "limit": 20}
            )
            if depth:
                bids = depth.get("bids", [])
                asks = depth.get("asks", [])
                bid_vol = sum(float(b[1]) for b in bids)
                ask_vol = sum(float(a[1]) for a in asks)
                data["bid_depth_2pct"] = bid_vol
                data["ask_depth_2pct"] = ask_vol
                data["depth_imbalance"] = (bid_vol - ask_vol) / max(bid_vol + ask_vol, 1)

            result[asset] = data

        return result

    async def _get(self, url: str, params: dict) -> Any:
        """GET 请求，失败返回 None"""
        try:
            async with self._session.get(url, params=params, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    return await resp.json()
                log.debug("[Binance REST] %s HTTP %d", url.split("/")[-1], resp.status)
        except Exception as e:
            log.debug("[Binance REST] %s: %s", url.split("/")[-1], e)
        return None
