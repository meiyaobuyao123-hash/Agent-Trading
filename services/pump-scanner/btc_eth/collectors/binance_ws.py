"""Binance WebSocket — BTC/ETH 实时价格 + K线 + Ticker

1 个 WS 连接订阅 6 个 stream：
  btcusdt@kline_1h, btcusdt@kline_4h, btcusdt@ticker
  ethusdt@kline_1h, ethusdt@kline_4h, ethusdt@ticker

数据推送到 IndicatorEngine 的回调函数。
"""
import asyncio
import json
import logging
import time
from collections import deque
from typing import Dict, List, Callable, Optional, Any

import websockets

from btc_eth.config import BINANCE_WS_URL, BINANCE_STREAMS, KLINE_BUFFER_SIZE

log = logging.getLogger(__name__)


class BinanceWsCollector:
    """Binance 合并 WS 流 — 实时价格 + K线"""

    def __init__(self):
        self._running = False
        self._ws = None  # type: Optional[Any]
        self._callbacks = []  # type: List[Callable]

        # 最新 ticker 数据
        self._tickers = {}  # type: Dict[str, Dict[str, Any]]  # symbol -> ticker

        # K线缓存（ring buffer）
        self._klines = {}  # type: Dict[str, deque]  # "BTC_1h" -> deque of candles

        for asset in ("BTC", "ETH"):
            for tf in ("1h", "4h"):
                key = f"{asset}_{tf}"
                self._klines[key] = deque(maxlen=KLINE_BUFFER_SIZE)

        self._reconnect_delay = 1
        self._last_msg_time = 0.0

    def on_data(self, callback: Callable) -> None:
        """注册数据回调"""
        self._callbacks.append(callback)

    def get_ticker(self, asset: str) -> Optional[Dict[str, Any]]:
        """获取最新 ticker"""
        return self._tickers.get(f"{asset.lower()}usdt")

    def get_klines(self, asset: str, timeframe: str) -> List[Dict[str, Any]]:
        """获取 K线缓存"""
        key = f"{asset}_{timeframe}"
        return list(self._klines.get(key, []))

    async def start(self) -> None:
        """启动 WS 连接（自动重连）"""
        self._running = True
        streams = "/".join(BINANCE_STREAMS)
        url = f"{BINANCE_WS_URL}?streams={streams}"

        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1
                    log.info("[Binance WS] 已连接，%d 个 stream", len(BINANCE_STREAMS))

                    async for raw in ws:
                        if not self._running:
                            break
                        self._last_msg_time = time.time()
                        try:
                            msg = json.loads(raw)
                            data = msg.get("data", {})
                            stream = msg.get("stream", "")
                            self._process_message(stream, data)
                        except Exception as e:
                            log.debug("[Binance WS] 消息解析: %s", e)

            except Exception as e:
                log.warning("[Binance WS] 断开: %s, %ds 后重连", e, self._reconnect_delay)

            if self._running:
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    def _process_message(self, stream: str, data: Dict[str, Any]) -> None:
        """解析 Binance WS 消息"""
        if "ticker" in stream:
            self._process_ticker(data)
        elif "kline" in stream:
            self._process_kline(stream, data)

    def _process_ticker(self, data: Dict[str, Any]) -> None:
        """24h ticker"""
        symbol = data.get("s", "").lower()
        if not symbol:
            return
        self._tickers[symbol] = {
            "price": float(data.get("c", 0)),
            "price_change_24h": float(data.get("P", 0)),
            "volume_24h": float(data.get("v", 0)),
            "volume_24h_quote": float(data.get("q", 0)),
            "high_24h": float(data.get("h", 0)),
            "low_24h": float(data.get("l", 0)),
            "open_24h": float(data.get("o", 0)),
            "ts": time.time(),
        }
        asset = "BTC" if "btc" in symbol else "ETH"
        self._notify("ticker", asset, self._tickers[symbol])

    def _process_kline(self, stream: str, data: Dict[str, Any]) -> None:
        """K线数据"""
        k = data.get("k", {})
        if not k:
            return

        symbol = k.get("s", "").lower()
        asset = "BTC" if "btc" in symbol else "ETH"
        interval = k.get("i", "")

        candle = {
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "volume_quote": float(k.get("q", 0)),
            "ts": k.get("t", 0) / 1000,  # ms → s
            "is_closed": k.get("x", False),
        }

        key = f"{asset}_{interval}"
        buf = self._klines.get(key)
        if buf is None:
            return

        # 更新或追加
        if buf and buf[-1]["ts"] == candle["ts"]:
            buf[-1] = candle  # 更新当前 K线
        else:
            buf.append(candle)

        # K线收线时通知
        if candle["is_closed"]:
            self._notify("kline_closed", asset, {
                "timeframe": interval,
                "candle": candle,
                "buffer_size": len(buf),
            })

    def _notify(self, event_type: str, asset: str, data: Dict[str, Any]) -> None:
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(event_type, asset, data)
            except Exception as e:
                log.debug("[Binance WS] 回调错误: %s", e)

    def health(self) -> Dict[str, Any]:
        return {
            "name": "binance_ws",
            "healthy": self._running and (time.time() - self._last_msg_time) < 30,
            "last_msg": self._last_msg_time,
            "streams": len(BINANCE_STREAMS),
            "btc_price": self._tickers.get("btcusdt", {}).get("price"),
            "eth_price": self._tickers.get("ethusdt", {}).get("price"),
        }
