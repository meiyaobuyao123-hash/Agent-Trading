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

            # PRD-006: 时间衰减止损接入
            try:
                from agent.risk_manager import get_risk_manager
                rm = get_risk_manager()
                # 估算持仓时间（从 DB row 的 created_at）
                hold_hours = 0.0
                try:
                    from database import get_db
                    exec_row = get_db().table("agent_executions").select(
                        "created_at"
                    ).eq("id", eid).limit(1).execute()
                    if exec_row.data:
                        created_str = exec_row.data[0].get("created_at", "")
                        if created_str:
                            created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                            hold_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                except Exception:
                    pass

                if hold_hours > 8:
                    sl_price = pos.entry_price * (1 - pos.stop_loss_pct / 100)
                    adjusted_sl_price = rm.apply_time_decay_stop(
                        stop_loss=sl_price,
                        entry_price=pos.entry_price,
                        peak_price=peak,
                        current_pnl_pct=pnl_pct,
                        hold_hours=hold_hours,
                        token_type="meme",
                    )
                    # 用 adjusted_sl_price 检查：如果当前价低于调整后的止损价
                    adjusted_sl_pct = (pos.entry_price - adjusted_sl_price) / pos.entry_price * 100
                    if price <= adjusted_sl_price and adjusted_sl_price > 0:
                        await self._execute_exit(eid, pos, price, "time_decay_stop", pnl_pct)
                        continue
            except Exception as e:
                log.debug("[PositionMonitor] Time decay check error: %s", e)

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

            # 执行卖出 — R47 P5 透传 user_id → user_wallets 解密路径
            result = await executor.execute_trade(
                chain=pos.chain,
                token_address=pos.token_address,
                action="sell",
                amount_usd=1.0,  # 1.0 = 全仓卖出
                slippage_pct=2.0,  # 卖出用更大滑点
                wallet_address=pos.wallet_address or None,
                private_key=pos.private_key or None,
                user_id=pos.user_id or None,    # R47 P5
                safety_ctx={
                    "user_id": pos.user_id,
                    "strategy_id": pos.strategy_id,
                    "mode": "live",   # position_monitor 只扫真盘
                },
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

            # PRD-005: 写入中期记忆（交易复盘） + 紧急反思检查
            try:
                from agent.memory import get_memory_manager
                mem = get_memory_manager()

                # 写入短期记忆
                mem.add_event({
                    "type": "exit",
                    "trigger": trigger,
                    "token": pos.token_address[:10],
                    "chain": pos.chain,
                    "pnl_pct": round(pnl_pct, 2),
                    "amount_usd": pos.amount_usd,
                    "summary": f"退出 {pos.token_address[:10]}.. {trigger} pnl={pnl_pct:+.1f}%",
                })

                # 写入中期记忆（交易闭环 → episodic）
                mem.add_trade_review({
                    "content": (
                        f"{pos.token_address[:10]} {trigger}: "
                        f"entry=${pos.entry_price:.6f} exit=${exit_price:.6f} "
                        f"pnl={pnl_pct:+.1f}%"
                    ),
                    "structured_data": {
                        "token": pos.token_address,
                        "chain": pos.chain,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": round(pnl_pct, 2),
                        "pnl_usd": round(pnl_usd, 2),
                        "hold_seconds": (
                            datetime.now(timezone.utc) - datetime.now(timezone.utc)
                        ).total_seconds(),  # 实际用 created_at
                        "exit_trigger": trigger,
                        "amount_usd": pos.amount_usd,
                    },
                    "chain": pos.chain,
                    "importance": min(10, abs(pnl_pct) / 5),
                })

                # 回填规则合规记录
                try:
                    db = get_db()
                    exec_row = db.table("agent_executions").select(
                        "trigger_context"
                    ).eq("id", eid).execute()
                    if exec_row.data:
                        tc = exec_row.data[0].get("trigger_context") or {}
                        matched = tc.get("_matched_rules", [])
                        won = pnl_pct > 0
                        for mr in matched:
                            rule_action = mr.get("action", "")
                            # 如果规则说 skip_buy 且我们买了 → violate
                            complied = not rule_action.startswith("skip")
                            mem.semantic.record_compliance(
                                mr["rule_id"], complied=complied, won=won
                            )
                except Exception:
                    pass

                # 紧急反思检查
                if mem.reflection.should_emergency_reflect(pnl_pct, pos.amount_usd):
                    import asyncio
                    asyncio.create_task(
                        _trigger_emergency_reflection(mem, pos.chain)
                    )
            except Exception as e:
                log.debug("[PositionMonitor] Memory write error: %s", e)

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

    async def scan_and_check_now(self) -> int:
        """R42 P0.1:常驻 loop 每 30s 调一次 — 拉所有 open 持仓 + 从 price_feed
        拿当前价 + 跑 check_all 触发止盈止损/追踪止损。

        Returns:
            int — 本次扫描的 position 数量(用于 log)

        失败永不抛(catch all),保证 loop 不会因为单次错误中断。
        """
        try:
            await self.load_positions()
        except Exception as e:
            log.warning("[PositionMonitor] load_positions failed: %s", e)
            return 0

        if not self._positions:
            return 0

        # 从 price_feed 拿每个 position 的当前价
        try:
            from price_feed import price_feed
        except Exception as e:
            log.warning("[PositionMonitor] price_feed import failed: %s", e)
            return len(self._positions)

        prices: Dict[str, float] = {}
        for eid, pos in self._positions.items():
            addr = (pos.token_address or "").lower()
            if not addr:
                continue
            p = price_feed.get_token_price(addr)
            if p and p > 0:
                # 同时支持 "chain:address" 和纯 address 两种 key
                prices[f"{pos.chain}:{addr}"] = p
                prices[addr] = p

        if not prices:
            log.debug("[PositionMonitor] %d positions but 0 prices from feed", len(self._positions))
            return len(self._positions)

        try:
            await self.check_all(prices)
        except Exception as e:
            log.warning("[PositionMonitor] check_all failed: %s", e)

        return len(self._positions)

    async def execute_crisis_close_all(self) -> int:
        """PRD-006: CRISIS 清仓 — 按金额大到小逐个卖出

        策略：
        1. 按持仓金额从大到小排序
        2. 每笔卖出间隔 3s（避免并发踩踏）
        3. 滑点放宽到 5%（优先成交）
        4. 失败 → 重试 1 次 → 仍失败记录 pending
        5. 总超时 60s
        """
        await self.load_positions()
        if not self._positions:
            return 0

        # 按金额从大到小排序
        sorted_positions = sorted(
            self._positions.items(),
            key=lambda x: x[1].amount_usd,
            reverse=True,
        )

        closed = 0
        start_time = time.time()
        timeout = 60.0

        for eid, pos in sorted_positions:
            if time.time() - start_time > timeout:
                log.warning("[CRISIS] Close timeout after %ds, %d/%d closed",
                           int(time.time() - start_time), closed, len(sorted_positions))
                break

            if eid in self._selling:
                continue

            self._selling.add(eid)
            try:
                from agent.trade_executor import get_trade_executor
                executor = get_trade_executor()

                success = False
                for attempt in range(2):  # 最多重试 1 次
                    try:
                        # R47 P5 — 紧急清仓也透传 user_id
                        result = await executor.execute_trade(
                            chain=pos.chain,
                            token_address=pos.token_address,
                            action="sell",
                            amount_usd=1.0,  # 全仓卖出
                            slippage_pct=5.0,  # CRISIS 滑点放宽
                            wallet_address=pos.wallet_address or None,
                            private_key=pos.private_key or None,
                            user_id=pos.user_id or None,
                            safety_ctx={
                                "user_id": pos.user_id,
                                "strategy_id": pos.strategy_id,
                                "mode": "live",
                            },
                        )
                        if result.success:
                            success = True
                            break
                        log.warning("[CRISIS] Close attempt %d failed for %s: %s",
                                   attempt + 1, pos.token_address[:10], result.error)
                    except Exception as e:
                        log.warning("[CRISIS] Close attempt %d error for %s: %s",
                                   attempt + 1, pos.token_address[:10], e)

                if success:
                    closed += 1
                    # 更新 DB
                    try:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        get_db().table("agent_executions").update({
                            "exit_trigger": "crisis_close",
                            "exited_at": now_iso,
                            "status": "closed",
                        }).eq("id", eid).execute()
                    except Exception:
                        pass
                    self._positions.pop(eid, None)
                    self._peak_prices.pop(eid, None)

                # 间隔 3s
                await asyncio.sleep(3)

            except Exception as e:
                log.error("[CRISIS] Close error for %s: %s", pos.token_address[:10], e)
            finally:
                self._selling.discard(eid)

        log.warning("[CRISIS] Close all done: %d/%d closed in %.1fs",
                   closed, len(sorted_positions), time.time() - start_time)
        return closed

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


async def _trigger_emergency_reflection(mem, chain: str) -> None:
    """PRD-005: 紧急反思 — 单笔亏损 >25% 且金额 >$30"""
    try:
        from database import get_db
        from datetime import timedelta

        db = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        res = db.table("agent_executions").select("*") \
            .eq("status", "closed") \
            .gte("exited_at", cutoff) \
            .order("exited_at", desc=True) \
            .limit(10).execute()

        trades = []
        for r in (res.data or []):
            trades.append({
                "token": r.get("token_address", "")[:10],
                "chain": r.get("chain", ""),
                "action": r.get("action", ""),
                "pnl_pct": r.get("pnl_pct", 0),
                "pnl_usd": r.get("pnl_usd", 0),
                "exit_trigger": r.get("exit_trigger", ""),
                "amount_usd": r.get("amount_usd", 0),
            })

        if not trades:
            return

        active_rules = mem.semantic.get_all_active()
        result = await mem.reflection.run_reflection(
            trades=trades,
            active_rules=active_rules,
            is_emergency=True,
        )

        if result and result.get("new_rules"):
            for rule in result["new_rules"][:3]:
                mem.episodic.add({
                    "category": "risk_lesson",
                    "content": f"Emergency: {rule.get('condition', '')} -> {rule.get('action', '')}",
                    "structured_data": rule,
                    "chain": chain,
                    "importance": 8,
                })
            log.info("[Emergency Reflection] Generated %d new rules", len(result["new_rules"]))

    except Exception as e:
        log.warning("[Emergency Reflection] Failed: %s", e)
