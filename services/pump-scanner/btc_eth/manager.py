"""BTC/ETH 模块编排器 — 启动所有 collector + 指标引擎 + 事件接入

启动顺序：
  1. 初始化 IndicatorEngine
  2. 启动 Binance WS（实时价格+K线）
  3. 启动 Binance REST + OKX REST（每5min）
  4. 启动其他 collector（30min/4h/daily）
  5. 启动指标持久化循环（每5min写DB）
  6. 启动信号追踪循环（1h/4h/12h/24h/72h 价格对比）
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional

from btc_eth.collectors.binance_ws import BinanceWsCollector
from btc_eth.collectors.binance_rest import BinanceRestCollector
from btc_eth.collectors.okx_rest import OkxRestCollector
from btc_eth.collectors.blockchain_ws import BlockchainWsCollector
from btc_eth.collectors.cryptopanic import CryptoPanicCollector
from btc_eth.collectors.coinalyze import CoinalyzeCollector
from btc_eth.collectors.mempool import MempoolCollector
from btc_eth.collectors.defilama import DeFiLlamaCollector
from btc_eth.collectors.blockchain_onchain import BlockchainOnchainCollector
from btc_eth.collectors.twelve_data import TwelveDataCollector
from btc_eth.collectors.lunarcrush import LunarCrushCollector
from btc_eth.collectors.alternative_me import AlternativeMeCollector
from btc_eth.collectors.dune_onchain import DuneOnchainCollector
from btc_eth.indicators.indicator_engine import IndicatorEngine
from btc_eth import storage
from btc_eth.config import (
    INTERVAL_HIGH_FREQ, INTERVAL_MID_FREQ, INTERVAL_LOW_FREQ,
    INTERVAL_DAILY, INDICATOR_PERSIST_INTERVAL,
)

log = logging.getLogger(__name__)


class BtcEthManager:
    """BTC/ETH 投资 Agent 模块编排器"""

    def __init__(self):
        self._running = False

        # 核心组件
        self._indicator_engine = IndicatorEngine()
        self._binance_ws = BinanceWsCollector()
        self._blockchain_ws = BlockchainWsCollector()
        self._binance_rest = BinanceRestCollector()
        self._okx_rest = OkxRestCollector()

        # 中频 collector（每 30 分钟）
        self._mid_freq = [
            CryptoPanicCollector(),
            CoinalyzeCollector(),
            MempoolCollector(),
        ]

        # 低频 collector（每 4 小时）
        self._low_freq = [
            DeFiLlamaCollector(),
            BlockchainOnchainCollector(),
            TwelveDataCollector(),
            LunarCrushCollector(),
            AlternativeMeCollector(),
        ]

        # 每日 collector
        self._daily = [
            DuneOnchainCollector(),
        ]

        # 指标引擎连接 K线数据
        self._indicator_engine.set_kline_getter(self._binance_ws.get_klines)

        # 注册 WS 数据回调
        self._binance_ws.on_data(self._on_binance_data)

        self._last_persist_time = 0.0

    async def start(self) -> None:
        """启动所有组件"""
        self._running = True
        log.info("[BTC/ETH] 模块启动中...")

        # 初始化所有 REST collector
        await self._binance_rest.init()
        await self._okx_rest.init()
        for c in self._mid_freq + self._low_freq + self._daily:
            if hasattr(c, 'init'):
                await c.init()

        # 启动各组件
        # 注意：Blockchain.com WS unconfirmed_sub 每秒数百条消息，
        # 解析阻塞事件循环导致 FastAPI 挂掉。暂时禁用，改用 REST 轮询。
        tasks = [
            asyncio.create_task(self._binance_ws.start()),
            # asyncio.create_task(self._blockchain_ws.start()),  # 暂禁：消息量过大
            asyncio.create_task(self._high_freq_loop()),
            asyncio.create_task(self._mid_freq_loop()),
            asyncio.create_task(self._low_freq_loop()),
            asyncio.create_task(self._daily_loop()),
            asyncio.create_task(self._persist_loop()),
        ]

        log.info(
            "[BTC/ETH] ✅ 模块已启动 — %d 个 collector + IndicatorEngine",
            2 + 2 + len(self._mid_freq) + len(self._low_freq) + len(self._daily)
        )

        # 等待所有任务（不会正常返回，除非 stop）
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """优雅关闭"""
        self._running = False
        await self._binance_ws.stop()
        await self._blockchain_ws.stop()
        await self._binance_rest.close()
        await self._okx_rest.close()
        for c in self._mid_freq + self._low_freq + self._daily:
            if hasattr(c, 'close'):
                await c.close()
        log.info("[BTC/ETH] 模块已停止")

    def _on_binance_data(self, event_type: str, asset: str, data: Dict[str, Any]) -> None:
        """Binance WS 数据回调"""
        if event_type == "ticker":
            # 更新价格和成交量到指标引擎
            self._indicator_engine.ingest("binance_ws", asset, {
                "price_usd": data.get("price", 0),
                "volume_24h_usd": data.get("volume_24h_quote", 0),
                "price_change_24h": data.get("price_change_24h", 0),
            })
        elif event_type == "kline_closed":
            # K线收线 → 重新计算技术指标
            timeframe = data.get("timeframe", "")
            self._indicator_engine.on_kline_closed(asset, timeframe)
            log.debug("[BTC/ETH] %s %s K线收线，RSI=%.1f",
                      asset, timeframe,
                      self._indicator_engine.get_snapshot(asset).get("rsi_14", 0))

    async def _high_freq_loop(self) -> None:
        """每 5 分钟采集 Binance REST + OKX 数据"""
        while self._running:
            try:
                data = await self._binance_rest.safe_collect()
                if data:
                    for asset in ("BTC", "ETH"):
                        asset_data = data.get(asset, {})
                        if asset_data:
                            self._indicator_engine.ingest("binance_rest", asset, asset_data)
                            log.debug("[BTC/ETH] %s REST 数据更新: %d 项", asset, len(asset_data))
            except Exception as e:
                log.warning("[BTC/ETH] 高频采集错误: %s", e)

            await asyncio.sleep(INTERVAL_HIGH_FREQ)

    async def _mid_freq_loop(self) -> None:
        """每 30 分钟采集中频数据"""
        await asyncio.sleep(30)  # 错开启动
        while self._running:
            for collector in self._mid_freq:
                try:
                    data = await collector.safe_collect()
                    if data:
                        # 中频数据大部分是全局的，同时更新 BTC 和 ETH
                        for asset in ("BTC", "ETH"):
                            self._indicator_engine.ingest(collector.name, asset, data)
                        log.debug("[BTC/ETH] %s 数据更新: %d 项", collector.name, len(data))
                except Exception as e:
                    log.warning("[BTC/ETH] %s 错误: %s", collector.name, e)
                await asyncio.sleep(2)  # 间隔避免并发
            await asyncio.sleep(INTERVAL_MID_FREQ)

    async def _low_freq_loop(self) -> None:
        """每 4 小时采集低频数据"""
        await asyncio.sleep(60)  # 错开启动
        while self._running:
            for collector in self._low_freq:
                try:
                    data = await collector.safe_collect()
                    if data:
                        for asset in ("BTC", "ETH"):
                            self._indicator_engine.ingest(collector.name, asset, data)
                        log.debug("[BTC/ETH] %s 数据更新: %d 项", collector.name, len(data))
                except Exception as e:
                    log.warning("[BTC/ETH] %s 错误: %s", collector.name, e)
                await asyncio.sleep(5)
            await asyncio.sleep(INTERVAL_LOW_FREQ)

    async def _daily_loop(self) -> None:
        """每日采集 Dune 链上数据"""
        await asyncio.sleep(120)  # 错开启动
        while self._running:
            for collector in self._daily:
                try:
                    data = await collector.safe_collect()
                    if data:
                        for asset in ("BTC", "ETH"):
                            asset_data = data.get(f"{asset}_exchange_netflow")
                            if asset_data:
                                self._indicator_engine.ingest(
                                    collector.name, asset,
                                    {"exchange_netflow_usd": float(asset_data.get("netflow", 0) if isinstance(asset_data, dict) else asset_data)}
                                )
                        log.info("[BTC/ETH] %s 每日数据更新", collector.name)
                except Exception as e:
                    log.warning("[BTC/ETH] %s 错误: %s", collector.name, e)
            await asyncio.sleep(INTERVAL_DAILY)

    async def _persist_loop(self) -> None:
        """每 5 分钟将指标写入 DB"""
        while self._running:
            await asyncio.sleep(INDICATOR_PERSIST_INTERVAL)
            try:
                for asset in ("BTC", "ETH"):
                    snapshot = self._indicator_engine.get_snapshot(asset)
                    if snapshot.get("price_usd", 0) > 0:
                        storage.save_indicators(asset, snapshot)
                        log.debug("[BTC/ETH] %s 指标已持久化，stale=%d",
                                  asset, snapshot.get("_stale_count", 0))
            except Exception as e:
                log.warning("[BTC/ETH] 持久化错误: %s", e)

    def get_health(self) -> Dict[str, Any]:
        """返回模块健康状态"""
        btc = self._indicator_engine.get_snapshot("BTC")
        eth = self._indicator_engine.get_snapshot("ETH")

        collector_health = {
            "binance_ws": self._binance_ws.health(),
            "blockchain_ws": self._blockchain_ws.health(),
            "binance_rest": self._binance_rest.health(),
            "okx_rest": self._okx_rest.health(),
        }
        for c in self._mid_freq + self._low_freq + self._daily:
            collector_health[c.name] = c.health()

        return {
            "running": self._running,
            "collectors": collector_health,
            "btc_price": btc.get("price_usd", 0),
            "eth_price": eth.get("price_usd", 0),
            "btc_rsi": btc.get("rsi_14"),
            "eth_rsi": eth.get("rsi_14"),
            "btc_stale_count": btc.get("_stale_count", 0),
            "eth_stale_count": eth.get("_stale_count", 0),
            "composite_scores": {
                "BTC": self._indicator_engine.get_composite_scores("BTC"),
                "ETH": self._indicator_engine.get_composite_scores("ETH"),
            },
        }

    def get_snapshot(self, asset: str) -> Dict[str, Any]:
        """外部获取指标快照"""
        return self._indicator_engine.get_snapshot(asset)
