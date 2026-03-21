"""指标引擎 — 汇聚所有数据源 → 50 项归一化指标 + 5 项复合评分

职责：
  1. 接收各 collector 推送的原始数据
  2. 维护内存中的最新指标快照（BTC + ETH）
  3. K线收线时计算技术指标
  4. 每 5 分钟写入 btc_eth_indicators 表
  5. 计算复合评分（momentum/sentiment/onchain/macro/risk）
"""
import logging
import time
from typing import Dict, Any, Optional

from btc_eth.indicators.technical import (
    calc_rsi, calc_macd, calc_bollinger, calc_atr, calc_ma, calc_support_resistance
)
from btc_eth.config import STALE_THRESHOLD

log = logging.getLogger(__name__)


class IndicatorEngine:
    """50 项指标聚合引擎"""

    def __init__(self):
        # 每个资产的最新指标
        self._latest = {
            "BTC": self._empty_snapshot(),
            "ETH": self._empty_snapshot(),
        }  # type: Dict[str, Dict[str, Any]]

        # 每个指标的最后更新时间
        self._update_times = {
            "BTC": {},
            "ETH": {},
        }  # type: Dict[str, Dict[str, float]]

        # K线缓存引用（由 BinanceWsCollector 提供）
        self._kline_getter = None

    def set_kline_getter(self, getter) -> None:
        """设置获取 K线的函数：fn(asset, timeframe) -> List[candle]"""
        self._kline_getter = getter

    def ingest(self, source: str, asset: str, data: Dict[str, Any]) -> None:
        """接收采集器数据，更新对应指标"""
        now = time.time()
        snapshot = self._latest.get(asset)
        times = self._update_times.get(asset)
        if snapshot is None or times is None:
            return

        for key, value in data.items():
            if key in snapshot and value is not None:
                snapshot[key] = value
                times[key] = now

        # 记录来源
        snapshot["_last_source"] = source
        snapshot["_last_update"] = now

    def on_kline_closed(self, asset: str, timeframe: str) -> None:
        """K线收线 → 重新计算技术指标"""
        if not self._kline_getter:
            return

        candles = self._kline_getter(asset, timeframe)
        if not candles or len(candles) < 30:
            return

        snapshot = self._latest.get(asset, {})

        # 价格
        last_candle = candles[-1]
        snapshot["price_usd"] = last_candle["close"]

        # RSI
        rsi = calc_rsi(candles, 14)
        if rsi is not None:
            snapshot["rsi_14"] = rsi

        # MACD
        macd = calc_macd(candles)
        if macd:
            snapshot["macd_signal"] = macd["histogram"]  # 正=多头, 负=空头

        # 布林带
        bb = calc_bollinger(candles)
        if bb:
            snapshot["bb_position"] = bb["position"]

        # ATR
        atr = calc_atr(candles)
        if atr is not None:
            snapshot["atr_14"] = atr

        # MA
        ma7 = calc_ma(candles, 7)
        ma25 = calc_ma(candles, 25)
        ma99 = calc_ma(candles, 99)
        snapshot["_ma7"] = ma7
        snapshot["_ma25"] = ma25
        snapshot["_ma99"] = ma99

        # 支撑阻力
        sr = calc_support_resistance(candles)
        snapshot["_support_levels"] = sr["support"]
        snapshot["_resistance_levels"] = sr["resistance"]

        # 涨跌幅
        if len(candles) >= 2:
            snapshot["price_change_1h"] = (
                (candles[-1]["close"] - candles[-2]["close"]) / max(candles[-2]["close"], 0.01) * 100
            )
        if len(candles) >= 5:
            snapshot["price_change_4h"] = (
                (candles[-1]["close"] - candles[-5]["close"]) / max(candles[-5]["close"], 0.01) * 100
            )
        if len(candles) >= 25:
            snapshot["price_change_24h"] = (
                (candles[-1]["close"] - candles[-25]["close"]) / max(candles[-25]["close"], 0.01) * 100
            )

        # 更新复合评分
        self._calc_composite_scores(asset)

        now = time.time()
        for k in ("rsi_14", "macd_signal", "bb_position", "atr_14",
                   "price_usd", "price_change_1h", "price_change_4h", "price_change_24h"):
            self._update_times[asset][k] = now

    def get_snapshot(self, asset: str) -> Dict[str, Any]:
        """返回当前完整快照（50 项指标 + 复合评分 + stale 标记）"""
        snapshot = dict(self._latest.get(asset, {}))
        times = self._update_times.get(asset, {})
        now = time.time()

        # 标记过期指标
        stale_keys = []
        for key, ts in times.items():
            age = now - ts
            # 根据指标频率确定过期阈值
            threshold = STALE_THRESHOLD.get("high_freq", 600)
            if key in ("fear_greed_index", "dxy_index", "etf_flow_usd", "hash_rate"):
                threshold = STALE_THRESHOLD.get("low_freq", 28800)
            elif key in ("news_sentiment", "social_volume"):
                threshold = STALE_THRESHOLD.get("mid_freq", 3600)

            if age > threshold:
                stale_keys.append(key)

        snapshot["_stale_keys"] = stale_keys
        snapshot["_stale_count"] = len(stale_keys)
        snapshot["asset"] = asset
        snapshot["ts"] = now
        return snapshot

    def get_composite_scores(self, asset: str) -> Dict[str, int]:
        """返回 5 项复合评分"""
        s = self._latest.get(asset, {})
        return {
            "momentum": s.get("score_momentum", 50),
            "sentiment": s.get("score_sentiment", 50),
            "onchain": s.get("score_onchain", 50),
            "macro": s.get("score_macro", 50),
            "risk": s.get("score_risk", 50),
        }

    def _calc_composite_scores(self, asset: str) -> None:
        """计算 5 项复合评分（0-100）"""
        s = self._latest.get(asset, {})

        # 1. 动量 (RSI + MACD + 价格变化 + OI变化)
        rsi = s.get("rsi_14", 50)
        macd_h = s.get("macd_signal", 0)
        p1h = s.get("price_change_1h", 0)
        oi_chg = s.get("oi_change_4h", 0)
        momentum = 50
        if rsi is not None:
            momentum = int(max(0, min(100,
                (rsi * 0.3) +
                (50 + min(max(macd_h * 1000, -50), 50)) * 0.3 +
                (50 + min(max(p1h * 5, -50), 50)) * 0.2 +
                (50 + min(max(oi_chg * 200, -50), 50)) * 0.2
            )))
        s["score_momentum"] = momentum

        # 2. 情绪 (恐慌指数 + 资金费率 + 多空比 + 新闻情绪)
        fgi = s.get("fear_greed_index", 50)
        fr = s.get("funding_rate", 0)
        ls = s.get("long_short_ratio", 1)
        news = s.get("news_sentiment", 0)
        sentiment = int(max(0, min(100,
            fgi * 0.35 +
            (50 - min(max(fr * 2000, -50), 50)) * 0.25 +
            (50 + min(max((ls - 1) * 30, -30), 30)) * 0.2 +
            (50 + news * 50) * 0.2
        )))
        s["score_sentiment"] = sentiment

        # 3. 链上 (交易所流入 + 活跃地址 + SOPR)
        netflow = s.get("exchange_netflow_usd", 0)
        active = s.get("active_addresses", 0)
        sopr = s.get("sopr", 1)
        onchain = int(max(0, min(100,
            (50 - min(max(netflow / 1e7, -50), 50)) * 0.4 +  # 流出=看涨
            min(active / 10000, 100) * 0.3 +
            (50 + (sopr - 1) * 100) * 0.3
        )))
        s["score_onchain"] = onchain

        # 4. 宏观 (DXY反向 + ETF流入 + 稳定币)
        dxy = s.get("dxy_index", 100)
        etf = s.get("etf_flow_usd", 0)
        stable = s.get("stablecoin_mcap", 0)
        macro = int(max(0, min(100,
            (50 - min(max((dxy - 100) * 2, -30), 30)) * 0.35 +  # DXY高=利空
            (50 + min(max(etf / 1e8, -50), 50)) * 0.35 +
            min(stable / 2e11, 100) * 0.3
        )))
        s["score_macro"] = macro

        # 5. 风险 (爆仓 + 费率极端 + 深度失衡)
        liq = s.get("liquidation_24h_usd", 0)
        depth_imb = s.get("depth_imbalance", 0)
        risk = int(max(0, min(100,
            (100 - min(liq / 1e8, 100)) * 0.4 +  # 爆仓少=低风险
            (50 - abs(fr or 0) * 2000) * 0.3 +  # 费率极端=高风险
            (50 + depth_imb * 50) * 0.3
        )))
        s["score_risk"] = risk

    @staticmethod
    def _empty_snapshot() -> Dict[str, Any]:
        """空快照模板"""
        return {
            "price_usd": 0, "price_change_1h": 0, "price_change_4h": 0,
            "price_change_24h": 0, "volume_24h_usd": 0,
            "funding_rate": 0, "oi_usd": 0, "oi_change_4h": 0,
            "long_short_ratio": 1, "retail_long_short": 1,
            "taker_buy_sell_ratio": 1, "liquidation_24h_usd": 0, "liq_long_pct": 0.5,
            "exchange_netflow_usd": 0, "active_addresses": 0, "hash_rate": 0,
            "sopr": 1, "whale_txn_count": 0,
            "dxy_index": 100, "sp500_change_pct": 0, "gold_change_pct": 0,
            "fear_greed_index": 50, "social_volume": 0, "news_sentiment": 0,
            "etf_flow_usd": 0, "stablecoin_mcap": 0, "total_tvl_usd": 0,
            "rsi_14": 50, "macd_signal": 0, "bb_position": 0.5, "atr_14": 0,
            "mempool_size_mb": 0, "avg_fee_sat_vb": 0,
            "bid_depth_2pct": 0, "ask_depth_2pct": 0, "depth_imbalance": 0,
            "score_momentum": 50, "score_sentiment": 50, "score_onchain": 50,
            "score_macro": 50, "score_risk": 50,
        }
