"""
持仓监控器 — 自动止盈止损 + 追踪止损

监控所有 open 状态的策略执行（strategy_executions），
当价格触达 SL/TP/Trailing Stop 时自动触发卖出。

触发源：
  1. EventBus 价格事件（毫秒级）
  2. monitor_job 30s 轮询（fallback）

Python 3.9 兼容。
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from database import get_db

log = logging.getLogger(__name__)


class PositionInfo:
    """持仓信息"""
    __slots__ = (
        "execution_id", "strategy_id", "user_id", "chain",
        "token_address", "entry_price", "amount_usd", "amount_token",
        "stop_loss_pct", "take_profit_pct", "trailing_stop_pct",
        "wallet_address", "private_key",
    )

    def __init__(self, row: dict):
        self.execution_id = row.get("id", "")
        self.strategy_id = row.get("strategy_id", "")
        self.user_id = row.get("user_id", "")
        self.chain = row.get("chain", "")
        self.token_address = row.get("token_address", "")
        self.entry_price = float(row.get("executed_price") or 0)
        self.amount_usd = float(row.get("amount_usd") or 0)
        self.amount_token = float(row.get("amount_token") or 0)
        self.stop_loss_pct = float(row.get("stop_loss_pct") or 30)
        self.take_profit_pct = float(row.get("take_profit_pct") or 100)
        self.trailing_stop_pct = float(row.get("trailing_stop_pct") or 0)
        self.wallet_address = row.get("wallet_address", "")
        self.private_key = row.get("private_key", "")


class PositionMonitor:
    """监控所有 open 持仓，检查 SL/TP/Trailing"""

    def __init__(self):
        self._positions: Dict[str, PositionInfo] = {}  # {execution_id: PositionInfo}
        self._peak_prices: Dict[str, float] = {}  # {execution_id: peak_price}
        self._last_load = 0.0
        self._load_interval = 30.0  # 每 30s 从 DB 重新加载
        self._selling: set = set()  # 正在卖出的 execution_id（防重入）

    async def load_positions(self):
        """从 DB 加载所有 open 持仓"""
        now = time.time()
        if now - self._last_load < self._load_interval and self._positions:
            return

        try:
            db = get_db()
            res = db.table("agent_executions").select("*") \
                .eq("status", "confirmed").eq("action", "buy") \
                .is_("exit_price", "null") \
                .execute()

            new_positions = {}
            for row in (res.data or []):
                eid = row.get("id", "")
                if not eid:
                    continue
                # 从关联的 strategy 获取风控参数
                sid = row.get("strategy_id", "")
                if sid:
                    try:
                        s_res = db.table("strategies").select(
                            "stop_loss_pct, take_profit_pct, trailing_stop_pct"
                        ).eq("id", sid).limit(1).execute()
                        if s_res.data:
                            row.update(s_res.data[0])
                    except Exception:
                        pass
                new_positions[eid] = PositionInfo(row)

            self._positions = new_positions
            self._last_load = now
            if new_positions:
                log.debug(f"[PositionMonitor] 加载 {len(new_positions)} 个 open 持仓")

        except Exception as e:
            log.warning(f"[PositionMonitor] 加载持仓失败: {e}")

    async def check_all(self, current_prices: Dict[str, float]):
        """
        检查所有持仓的止盈止损

        current_prices 格式: {"solana:tokenAddress": price_usd, ...}
        """
        await self.load_positions()

        for eid, pos in list(self._positions.items()):
            if eid in self._selling:
                continue

            key = f"{pos.chain}:{pos.token_address}"
            price = current_prices.get(key) or current_prices.get(pos.token_address)
            if not price or price <= 0 or pos.entry_price <= 0:
                continue

            # 更新峰值（追踪止损用）
            peak = self._peak_prices.get(eid, pos.entry_price)
            if price > peak:
                self._peak_prices[eid] = price
                peak = price

            pnl_pct = (price - pos.entry_price) / pos.entry_price * 100

            # 止盈检查
            if pos.take_profit_pct > 0 and pnl_pct >= pos.take_profit_pct:
                await self._execute_exit(eid, pos, price, "take_profit", pnl_pct)

            # 止损检查
            elif pos.stop_loss_pct > 0 and pnl_pct <= -pos.stop_loss_pct:
                await self._execute_exit(eid, pos, price, "stop_loss", pnl_pct)

            # 追踪止损检查
            elif pos.trailing_stop_pct > 0 and peak > pos.entry_price:
                drawdown_from_peak = (peak - price) / peak * 100
                if drawdown_from_peak >= pos.trailing_stop_pct:
                    await self._execute_exit(eid, pos, price, "trailing_stop", pnl_pct)

    async def _execute_exit(
        self, eid: str, pos: PositionInfo,
        exit_price: float, trigger: str, pnl_pct: float,
    ):
        """执行退出"""
        self._selling.add(eid)
        try:
            from agent.trade_executor import get_trade_executor
            executor = get_trade_executor()

            log.info(
                f"[PositionMonitor] 触发 {trigger}: {pos.token_address[:10]}.. "
                f"entry=${pos.entry_price:.6f} exit=${exit_price:.6f} pnl={pnl_pct:+.1f}%"
            )

            # 执行卖出
            result = await executor.execute_trade(
                chain=pos.chain,
                token_address=pos.token_address,
                action="sell",
                amount_usd=1.0,  # 1.0 = 全仓卖出
                slippage_pct=2.0,  # 卖出用更大滑点
                wallet_address=pos.wallet_address or None,
                private_key=pos.private_key or None,
            )

            # 更新 DB
            pnl_usd = pos.amount_usd * pnl_pct / 100
            now_iso = datetime.now(timezone.utc).isoformat()

            db = get_db()
            db.table("agent_executions").update({
                "exit_price": exit_price,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 2),
                "exit_trigger": trigger,
                "exit_tx_hash": result.tx_hash if result.success else None,
                "exited_at": now_iso,
                "status": "closed",
            }).eq("id", eid).execute()

            # 从内存移除
            self._positions.pop(eid, None)
            self._peak_prices.pop(eid, None)

            if result.success:
                log.info(
                    f"[PositionMonitor] 卖出成功: {trigger} "
                    f"tx={result.tx_hash} pnl={pnl_pct:+.1f}%"
                )
            else:
                log.warning(
                    f"[PositionMonitor] 卖出失败: {result.error}，"
                    f"已标记 closed（链上可能未成交）"
                )

        except Exception as e:
            log.error(f"[PositionMonitor] 退出执行异常: {e}")
        finally:
            self._selling.discard(eid)

    def get_stats(self) -> dict:
        """返回监控状态"""
        return {
            "open_positions": len(self._positions),
            "peak_prices_tracked": len(self._peak_prices),
            "selling_in_progress": len(self._selling),
        }


# ── 全局单例 ────────────────────────────────────────────────
_monitor: Optional[PositionMonitor] = None


def get_position_monitor() -> PositionMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PositionMonitor()
    return _monitor
