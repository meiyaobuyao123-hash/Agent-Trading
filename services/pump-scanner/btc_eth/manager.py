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
from btc_eth.analysis.signal_generator import SignalGenerator
from btc_eth.analysis.cycle_analyzer import CycleAnalyzer
from btc_eth import storage
from btc_eth.config import (
    INTERVAL_HIGH_FREQ, INTERVAL_MID_FREQ, INTERVAL_LOW_FREQ,
    INTERVAL_DAILY, INDICATOR_PERSIST_INTERVAL,
)

# 信号生成间隔（5 分钟检查一次预筛条件）
INTERVAL_SIGNAL = 300

log = logging.getLogger(__name__)


class BtcEthManager:
    """BTC/ETH 投资 Agent 模块编排器"""

    def __init__(self):
        self._running = False

        # 核心组件
        self._indicator_engine = IndicatorEngine()
        self._signal_generator = SignalGenerator()
        self._cycle_analyzer = CycleAnalyzer()
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
            asyncio.create_task(self._paper_exit_loop()),
            asyncio.create_task(self._signal_loop()),  # BTC/ETH 信号生成
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

    async def _paper_exit_loop(self) -> None:
        """每 60s 检查模拟盘止盈止损（PRD-004 M-05）"""
        while self._running:
            await asyncio.sleep(60)
            try:
                from btc_eth.paper_trading.engine import get_paper_engine
                engine = get_paper_engine()
                prices = {
                    "BTC": self._indicator_engine.get_snapshot("BTC").get("price_usd", 0),
                    "ETH": self._indicator_engine.get_snapshot("ETH").get("price_usd", 0),
                }
                closed = await engine.check_all_exits(prices)
                if closed > 0:
                    log.info("[BTC/ETH] Paper trading: %d positions closed by SL/TP", closed)
            except Exception as e:
                log.debug("[BTC/ETH] Paper exit check: %s", e)

    async def _signal_loop(self) -> None:
        """每 5 分钟检查 BTC/ETH 是否生成交易信号 → 触发模拟盘买入

        流程：
          1. 等待指标齐全（RSI_14 需要 14 根 1m K 线，约 14 分钟）
          2. Stage 1: 规则预筛（RSI/费率/OI 极值）
          3. Stage 2: Claude 确认或规则引擎降级（10s timeout）
          4. 信号生成 → SignalGenerator._trigger_sim → sim_trader 买入
        """
        # 启动后先等 2 分钟拿到基础数据
        await asyncio.sleep(120)

        # 等待指标齐全（最多等 10 分钟）
        # 三项齐全才能判定就绪：
        #   1) WS 价格已喂入（price_usd > 0）
        #   2) 技术指标已计算（rsi_14 非 None）
        #   3) REST 采集至少成功一轮（_last_success 非 None）
        # 加第 3 条避免 "WS 有价但 REST 指标缺" 时的误信号
        max_warmup = 600
        elapsed = 0
        while self._running and elapsed < max_warmup:
            rest_ready = self._binance_rest._last_success is not None
            ready = []
            for asset in ("BTC", "ETH"):
                s = self._indicator_engine.get_snapshot(asset)
                if s and s.get("price_usd", 0) > 0 and s.get("rsi_14") is not None:
                    ready.append(asset)
            if len(ready) == 2 and rest_ready:
                log.info("[BTC/ETH] 指标预热完成（含 REST），信号循环启动（每 %ds）", INTERVAL_SIGNAL)
                break
            await asyncio.sleep(30)
            elapsed += 30
        else:
            log.warning("[BTC/ETH] 指标预热超时（%ds），仍启动信号循环", max_warmup)

        while self._running:
            # 主 try 捕获循环级别的异常，不影响下一轮
            try:
                for asset in ("BTC", "ETH"):
                    # 单资产 try：一个资产失败不影响另一个
                    try:
                        snapshot = self._indicator_engine.get_snapshot(asset)
                        if not snapshot or snapshot.get("price_usd", 0) <= 0:
                            continue

                        # Stage 1: 规则预筛
                        direction = self._signal_generator.pre_filter(asset, snapshot)
                        if not direction:
                            continue

                        log.info("[BTC/ETH] %s Stage1 预筛通过: %s", asset, direction)

                        # 获取周期阶段
                        cycle = self._cycle_analyzer.analyze_rule_based(snapshot)
                        cycle_phase = cycle.get("phase", "unknown")

                        # Stage 2: 生成信号，加 15s timeout 防止 Claude 阻塞
                        try:
                            signal = await asyncio.wait_for(
                                self._signal_generator.generate_signal(
                                    asset, direction, snapshot, cycle_phase
                                ),
                                timeout=15.0,
                            )
                        except asyncio.TimeoutError:
                            log.warning("[BTC/ETH] %s Claude 超时，降级规则引擎", asset)
                            # 降级直接走规则引擎（不调 Claude）
                            signal = self._signal_generator._rule_based_signal(
                                asset, direction, snapshot
                            )
                            if signal:
                                # 规则降级的信号也要触发 sim
                                self._signal_generator._trigger_sim(asset, signal)

                        if signal:
                            log.info(
                                "[BTC/ETH] %s 信号生成: type=%s confidence=%s entry=%s",
                                asset, signal.get("signal_type"),
                                signal.get("confidence"), signal.get("entry_price"),
                            )
                    except Exception as e:
                        log.warning("[BTC/ETH] %s 信号生成失败: %s", asset, e)
                        continue  # 下一个资产
            except Exception as e:
                log.error("[BTC/ETH] 信号循环未预期错误: %s", e)

            await asyncio.sleep(INTERVAL_SIGNAL)

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
