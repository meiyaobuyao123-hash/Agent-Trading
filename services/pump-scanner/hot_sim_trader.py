"""
热币模拟盘 — 入榜即买，实时止盈止损

两种模式并行运行：
  repeat: 每次入榜都买 $10（同币可重复买）
  unique: 每币只买一次

止盈止损 15%，用 PriceFeed 实时价格判断。
数据存 Supabase hot_sim_trades 表。

Python 3.9 兼容。
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Set

from database import get_db

log = logging.getLogger(__name__)

BUY_AMOUNT_DEFAULT = 10.0
BUY_AMOUNT_BTC = 50.0
BUY_AMOUNT_ETH = 20.0
TP_PCT = 15.0
SL_PCT = 15.0


def _get_buy_amount(source: str, symbol: str) -> float:
    """按资产类型返回下单金额"""
    if source == "btc_eth":
        if symbol.upper() == "BTC":
            return BUY_AMOUNT_BTC
        elif symbol.upper() == "ETH":
            return BUY_AMOUNT_ETH
    return BUY_AMOUNT_DEFAULT


class HotSimTrader:
    def __init__(self):
        # unique 模式已买过的 token（chain:address）
        self._bought_unique: Set[str] = set()
        # 所有 open 仓位 {id: {entry_price, chain, address, symbol, mode}}
        self._open_positions: Dict[str, dict] = {}
        self._initialized = False

    def init_from_db(self):
        """启动时从 DB 加载已有数据"""
        if self._initialized:
            return
        try:
            db = get_db()
            # 加载 unique 已买过的
            res = db.table("hot_sim_trades").select("chain, address").eq("mode", "unique").execute()
            for r in (res.data or []):
                self._bought_unique.add(f"{r['chain']}:{r['address']}")

            # 加载 open 仓位
            res2 = db.table("hot_sim_trades").select("*").eq("status", "open").execute()
            for r in (res2.data or []):
                self._open_positions[r["id"]] = r

            log.info("[HotSim] 初始化: unique已买=%d, open仓位=%d",
                     len(self._bought_unique), len(self._open_positions))
            self._initialized = True
        except Exception as e:
            log.warning("[HotSim] 初始化失败: %s", e)

    def on_token_enter(self, address: str, chain: str, symbol: str,
                       price: float, score: float, source: str = "hot"):
        """信号触发时调用 — 自动模拟买入（支持多信号源）"""
        if price <= 0:
            return
        self.init_from_db()
        now_iso = datetime.now(timezone.utc).isoformat()
        db = get_db()
        amount = _get_buy_amount(source, symbol)

        base_row = {
            "chain": chain,
            "address": address,
            "symbol": symbol or "?",
            "entry_price": price,
            "amount_usd": amount,
            "tp_pct": TP_PCT,
            "sl_pct": SL_PCT,
            "tp_price": round(price * (1 + TP_PCT / 100), 12),
            "sl_price": round(price * (1 - SL_PCT / 100), 12),
            "score_at_entry": score,
            "source": source,
            "status": "open",
            "entered_at": now_iso,
        }

        # mode=repeat: 每次都买
        try:
            row_repeat = {**base_row, "mode": "repeat"}
            res = db.table("hot_sim_trades").insert(row_repeat).execute()
            if res.data:
                self._open_positions[res.data[0]["id"]] = res.data[0]
        except Exception as e:
            log.debug("[Sim] repeat insert: %s", e)

        # mode=unique: 只买一次（BTC/ETH 跳过 unique，只有 2 个币没意义）
        if source == "btc_eth":
            return

        key = f"{source}:{chain}:{address}"
        if key not in self._bought_unique:
            try:
                row_unique = {**base_row, "mode": "unique"}
                res = db.table("hot_sim_trades").insert(row_unique).execute()
                if res.data:
                    self._open_positions[res.data[0]["id"]] = res.data[0]
                self._bought_unique.add(key)
            except Exception as e:
                log.debug("[HotSim] unique insert: %s", e)

    def on_price_update(self, address: str, price: float):
        """价格更新时检查止盈止损"""
        if price <= 0:
            return

        to_close = []
        for pid, pos in self._open_positions.items():
            if pos.get("address", "").lower() != address.lower():
                continue

            tp = float(pos.get("tp_price", 0))
            sl = float(pos.get("sl_price", 0))
            entry = float(pos.get("entry_price", 0))

            if tp > 0 and price >= tp:
                to_close.append((pid, "tp", price, TP_PCT))
            elif sl > 0 and price <= sl:
                to_close.append((pid, "sl", price, -SL_PCT))

        for pid, reason, exit_price, pnl_pct in to_close:
            self._close_position(pid, reason, exit_price, pnl_pct)

    def _close_position(self, pid: str, reason: str, exit_price: float, pnl_pct: float):
        """平仓"""
        pos_amount = float(self._open_positions.get(pid, {}).get("amount_usd", BUY_AMOUNT_DEFAULT))
        pnl_usd = round(pos_amount * pnl_pct / 100, 2)
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            get_db().table("hot_sim_trades").update({
                "status": reason,
                "exit_price": exit_price,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": pnl_usd,
                "exited_at": now_iso,
            }).eq("id", pid).execute()
        except Exception as e:
            log.debug("[HotSim] close: %s", e)

        pos = self._open_positions.pop(pid, None)
        if pos:
            sym = pos.get("symbol", "?")
            mode = pos.get("mode", "?")
            log.info("[HotSim] %s %s %s: %s exit=$%.8f pnl=%+.1f%% ($%+.2f)",
                     mode, reason.upper(), sym, pos.get("chain", ""), exit_price, pnl_pct, pnl_usd)


# 全局单例
_sim_trader = None

def get_sim_trader() -> HotSimTrader:
    global _sim_trader
    if _sim_trader is None:
        _sim_trader = HotSimTrader()
    return _sim_trader
