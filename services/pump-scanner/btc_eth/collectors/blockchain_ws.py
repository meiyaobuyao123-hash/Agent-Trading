"""Blockchain.com WS — BTC 大额转账实时监控"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Callable

import websockets

from btc_eth.config import BLOCKCHAIN_WS_URL, WHALE_TX_THRESHOLD_BTC

log = logging.getLogger(__name__)

# 已知交易所热钱包地址前缀（简化版，用于判断流入/流出）
EXCHANGE_ADDRESSES = {
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h",  # Binance
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",           # Binance
    "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",            # Coinbase
}


class BlockchainWsCollector:
    """Blockchain.com WS — 实时大额 BTC 转账"""

    def __init__(self):
        self._running = False
        self._callbacks = []  # type: List[Callable]
        self._whale_txns = []  # type: List[Dict[str, Any]]
        self._last_msg_time = 0.0
        self._reconnect_delay = 1

    def on_whale_tx(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def get_recent_whales(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._whale_txns[-limit:]

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                async with websockets.connect(BLOCKCHAIN_WS_URL, ping_interval=30) as ws:
                    self._reconnect_delay = 1
                    await ws.send(json.dumps({"op": "unconfirmed_sub"}))
                    log.info("[Blockchain WS] 已连接，监控大额 BTC 转账")

                    async for raw in ws:
                        if not self._running:
                            break
                        self._last_msg_time = time.time()
                        try:
                            msg = json.loads(raw)
                            if msg.get("op") == "utx":
                                self._process_tx(msg.get("x", {}))
                        except Exception:
                            pass
            except Exception as e:
                log.warning("[Blockchain WS] 断开: %s, %ds 后重连", e, self._reconnect_delay)

            if self._running:
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def stop(self):
        self._running = False

    def _process_tx(self, tx: Dict[str, Any]) -> None:
        outputs = tx.get("out", [])
        total_btc = sum(o.get("value", 0) for o in outputs) / 1e8

        if total_btc < WHALE_TX_THRESHOLD_BTC:
            return

        # 解析转入地址
        to_addrs = [o.get("addr", "") for o in outputs if o.get("addr")]
        from_addrs = [i.get("prev_out", {}).get("addr", "") for i in tx.get("inputs", []) if i.get("prev_out", {}).get("addr")]

        # 判断是否转入交易所
        to_exchange = any(a in EXCHANGE_ADDRESSES for a in to_addrs)
        from_exchange = any(a in EXCHANGE_ADDRESSES for a in from_addrs)

        whale_tx = {
            "hash": tx.get("hash", ""),
            "btc_amount": round(total_btc, 4),
            "usd_estimate": 0,  # 需要价格
            "to_exchange": to_exchange,
            "from_exchange": from_exchange,
            "direction": "exchange_inflow" if to_exchange else ("exchange_outflow" if from_exchange else "transfer"),
            "ts": time.time(),
        }

        self._whale_txns.append(whale_tx)
        if len(self._whale_txns) > 100:
            self._whale_txns = self._whale_txns[-50:]

        log.info("[Blockchain WS] 🐋 大额转账 %.2f BTC (%s)", total_btc, whale_tx["direction"])

        for cb in self._callbacks:
            try:
                cb(whale_tx)
            except Exception:
                pass

    def health(self) -> Dict[str, Any]:
        return {
            "name": "blockchain_ws",
            "healthy": self._running and (time.time() - self._last_msg_time) < 120,
            "last_msg": self._last_msg_time,
            "whale_txns_cached": len(self._whale_txns),
        }
