"""
Agent 策略模拟盘引擎 (PRD-008 M14)

- 策略创建默认 paper 模式运行 3 天
- 信号触发时用实时价格模拟交易（不调 OKX DEX）
- 扣除 1.5% 模拟滑点（v1.1 Q3）
- 每 30s 检查 SL/TP（v1.1 Q1）
- 3 天后推送切换提醒（v1.1 Q2）
- 7 天无操作自动暂停（v1.1 Q2）

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone

from database import get_db

log = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────
SIMULATED_SLIPPAGE = 0.015       # 1.5% 模拟滑点
PAPER_DEFAULT_DAYS = 3           # 默认 paper 模式天数
PAPER_MAX_IDLE_DAYS = 7          # 7 天无操作自动暂停


class PaperEngine:
    """模拟交易引擎"""

    # ── 开仓 ──────────────────────────────────────────────────

    async def open_position(
        self,
        strategy_id: str,
        user_id: str,
        token_address: str,
        token_symbol: str,
        chain: str,
        price: float,
        amount_usd: float,
        sl_pct: float,
        tp_pct: float,
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        模拟开仓 — 扣除模拟滑点

        买入时价格上浮 1.5%（模拟市价买入滑点）。
        写入 agent_paper_trades(status=open)。

        Returns:
            创建的 paper trade 记录，失败返回 None
        """
        # 买入模拟滑点：实际成交价 = 市场价 * (1 + 1.5%)
        simulated_price = price * (1 + SIMULATED_SLIPPAGE)

        row = {
            "strategy_id": strategy_id,
            "user_id": user_id,
            "chain": chain,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "action": "buy",
            "entry_price": simulated_price,
            "amount_usd": amount_usd,
            "sl_pct": sl_pct,
            "tp_pct": tp_pct,
            "trigger_context": trigger_context or {},
            "status": "open",
        }

        try:
            result = get_db().table("agent_paper_trades").insert(row).execute()
            if result.data:
                trade = result.data[0]
                log.info(
                    "Paper OPEN: %s %s $%.2f @%.8f (market=%.8f, slippage=+%.1f%%) strategy=%s",
                    chain, token_symbol, amount_usd, simulated_price,
                    price, SIMULATED_SLIPPAGE * 100, strategy_id,
                )
                return trade
        except Exception as e:
            log.error("Paper open_position error: %s", e)

        return None

    # ── 平仓 ──────────────────────────────────────────────────

    async def close_position(
        self,
        trade_id: str,
        exit_price: float,
        reason: str = "manual",
    ) -> Optional[Dict[str, Any]]:
        """
        模拟平仓 — 卖出模拟滑点

        卖出时价格下浮 1.5%。
        计算 PnL 并更新 agent_paper_trades。

        Args:
            trade_id: paper trade UUID
            exit_price: 当前市场价
            reason: 平仓原因 (sl/tp/manual)
        """
        # 卖出模拟滑点：实际成交价 = 市场价 * (1 - 1.5%)
        simulated_exit = exit_price * (1 - SIMULATED_SLIPPAGE)

        try:
            # 先读取原始交易
            res = (
                get_db()
                .table("agent_paper_trades")
                .select("*")
                .eq("id", trade_id)
                .eq("status", "open")
                .execute()
            )
            if not res.data:
                log.warning("Paper close: trade %s not found or already closed", trade_id)
                return None

            trade = res.data[0]
            entry_price = float(trade["entry_price"])

            # 计算 PnL
            if entry_price > 0:
                pnl_pct = ((simulated_exit - entry_price) / entry_price) * 100
            else:
                pnl_pct = 0.0

            amount_usd = float(trade.get("amount_usd", 0))
            pnl_usd = amount_usd * (pnl_pct / 100)

            now = datetime.now(timezone.utc).isoformat()
            update = {
                "exit_price": simulated_exit,
                "pnl_usd": round(pnl_usd, 4),
                "pnl_pct": round(pnl_pct, 4),
                "status": "closed",
                "closed_at": now,
                "trigger_context": {
                    **(trade.get("trigger_context") or {}),
                    "close_reason": reason,
                    "market_exit_price": exit_price,
                },
            }

            result = (
                get_db()
                .table("agent_paper_trades")
                .update(update)
                .eq("id", trade_id)
                .execute()
            )

            if result.data:
                log.info(
                    "Paper CLOSE: %s %s PnL=%.2f%% ($%.2f) reason=%s",
                    trade.get("chain"), trade.get("token_symbol"),
                    pnl_pct, pnl_usd, reason,
                )
                return result.data[0]

        except Exception as e:
            log.error("Paper close_position error: %s", e)

        return None

    # ── SL/TP 检查（每 30s 调用）─────────────────────────────

    async def check_exits(self) -> int:
        """
        检查所有 open 的模拟持仓的止损/止盈

        读取实时价格，比对 entry_price + sl_pct / tp_pct，
        触发则自动平仓。

        Returns:
            本轮平仓数量
        """
        from price_feed import price_feed

        closed_count = 0

        try:
            res = (
                get_db()
                .table("agent_paper_trades")
                .select("*")
                .eq("status", "open")
                .execute()
            )
            trades = res.data or []
        except Exception as e:
            log.error("Paper check_exits query error: %s", e)
            return 0

        for trade in trades:
            try:
                token_address = trade.get("token_address", "")
                entry_price = float(trade.get("entry_price", 0))
                sl_pct = float(trade.get("sl_pct") or 25)
                tp_pct = float(trade.get("tp_pct") or 100)

                if entry_price <= 0:
                    continue

                # R47 P4 防御:sl_pct/tp_pct < 1 几乎肯定是 ratio 单位误存(如 0.3 = 30%),
                # 这种值会导致 token 一动 0.3% 就 SL → 跳过 + 报警等数据修复
                if sl_pct < 1 or tp_pct < 1:
                    log.error(
                        "[paper_engine] trade %s sl_pct=%s tp_pct=%s ratio_unit_skip "
                        "(sl_pct/tp_pct must be percent integer; 30 means 30 percent)",
                        trade.get("id"), sl_pct, tp_pct,
                    )
                    continue

                # 获取当前价格
                current_price = price_feed.get_token_price(token_address)
                if current_price is None:
                    continue

                change_pct = ((current_price - entry_price) / entry_price) * 100

                reason = None
                if change_pct <= -sl_pct:
                    reason = "sl"
                elif change_pct >= tp_pct:
                    reason = "tp"

                if reason:
                    await self.close_position(
                        trade_id=trade["id"],
                        exit_price=current_price,
                        reason=reason,
                    )
                    closed_count += 1

            except Exception as e:
                log.error(
                    "Paper check_exits error for trade %s: %s",
                    trade.get("id"), e,
                )

        if closed_count > 0:
            log.info("Paper check_exits: closed %d positions", closed_count)

        return closed_count

    # ── 提醒 + 自动暂停 ──────────────────────────────────────

    async def check_reminders(self) -> None:
        """
        检查 paper 模式策略：
        1. 运行满 3 天 → 推送切换提醒
        2. 运行满 7 天且无操作 → 自动暂停
        """
        now = datetime.now(timezone.utc)
        cutoff_3d = (now - timedelta(days=PAPER_DEFAULT_DAYS)).isoformat()
        cutoff_7d = (now - timedelta(days=PAPER_MAX_IDLE_DAYS)).isoformat()

        try:
            # 找出 paper 模式 + active 状态 + 创建超过 3 天的策略
            res = (
                get_db()
                .table("agent_strategies")
                .select("id, user_id, name, created_at, mode")
                .eq("status", "active")
                .eq("mode", "paper")
                .lte("created_at", cutoff_3d)
                .execute()
            )
            strategies = res.data or []
        except Exception as e:
            log.error("Paper check_reminders query error: %s", e)
            return

        for s in strategies:
            strategy_id = s["id"]
            user_id = s.get("user_id", "")
            created_at = s.get("created_at", "")

            # 7 天暂停检查
            if created_at and created_at <= cutoff_7d:
                # 检查最近 7 天有无 paper trade
                try:
                    trade_res = (
                        get_db()
                        .table("agent_paper_trades")
                        .select("id", count="exact")
                        .eq("strategy_id", strategy_id)
                        .gte("created_at", cutoff_7d)
                        .execute()
                    )
                    recent_count = trade_res.count or 0
                except Exception:
                    recent_count = 0

                if recent_count == 0:
                    # 自动暂停
                    try:
                        get_db().table("agent_strategies").update({
                            "status": "paused",
                        }).eq("id", strategy_id).execute()

                        # 写入告警
                        get_db().table("agent_alerts").insert({
                            "user_id": user_id,
                            "strategy_id": strategy_id,
                            "title": "策略已自动暂停",
                            "message": f"策略 '{s.get('name')}' 模拟盘运行 7 天无操作，已自动暂停。",
                            "severity": "warning",
                            "is_read": False,
                            "is_pushed": False,
                            "trigger_context": {"type": "paper_auto_pause", "days": 7},
                        }).execute()

                        log.info(
                            "Paper auto-pause: strategy %s (7d idle)", strategy_id
                        )
                    except Exception as e:
                        log.error("Paper auto-pause error: %s", e)
                    continue

            # 3 天提醒（只发一次，检查是否已发过）
            try:
                existing_alert = (
                    get_db()
                    .table("agent_alerts")
                    .select("id", count="exact")
                    .eq("strategy_id", strategy_id)
                    .eq("trigger_context->>type", "paper_3day_reminder")
                    .execute()
                )
                if (existing_alert.count or 0) > 0:
                    continue  # 已发过提醒
            except Exception:
                pass

            # 发送 3 天提醒
            try:
                get_db().table("agent_alerts").insert({
                    "user_id": user_id,
                    "strategy_id": strategy_id,
                    "title": "模拟盘 3 天到期",
                    "message": f"策略 '{s.get('name')}' 模拟盘已运行 3 天，查看表现后可切换到实盘。",
                    "severity": "info",
                    "is_read": False,
                    "is_pushed": False,
                    "trigger_context": {"type": "paper_3day_reminder"},
                }).execute()

                log.info(
                    "Paper 3-day reminder sent: strategy %s", strategy_id
                )
            except Exception as e:
                log.error("Paper 3-day reminder error: %s", e)

    # ── 统计 ──────────────────────────────────────────────────

    async def get_stats(
        self, strategy_id: str
    ) -> Dict[str, Any]:
        """
        获取策略的模拟盘统计

        Returns:
            {win_rate, total_pnl_usd, total_pnl_pct, trade_count,
             avg_pnl_pct, max_win_pct, max_loss_pct, open_count}
        """
        try:
            res = (
                get_db()
                .table("agent_paper_trades")
                .select("*")
                .eq("strategy_id", strategy_id)
                .execute()
            )
            trades = res.data or []
        except Exception as e:
            log.error("Paper get_stats error: %s", e)
            trades = []

        closed = [t for t in trades if t.get("status") == "closed"]
        open_trades = [t for t in trades if t.get("status") == "open"]

        if not closed:
            return {
                "strategy_id": strategy_id,
                "trade_count": len(trades),
                "closed_count": 0,
                "open_count": len(open_trades),
                "win_rate": 0.0,
                "total_pnl_usd": 0.0,
                "total_pnl_pct": 0.0,
                "avg_pnl_pct": 0.0,
                "max_win_pct": 0.0,
                "max_loss_pct": 0.0,
            }

        wins = sum(1 for t in closed if float(t.get("pnl_usd") or 0) > 0)
        win_rate = (wins / len(closed)) * 100 if closed else 0.0

        total_pnl_usd = sum(float(t.get("pnl_usd") or 0) for t in closed)
        pnl_pcts = [float(t.get("pnl_pct") or 0) for t in closed]
        total_pnl_pct = sum(pnl_pcts)
        avg_pnl_pct = total_pnl_pct / len(closed) if closed else 0.0
        max_win_pct = max(pnl_pcts) if pnl_pcts else 0.0
        max_loss_pct = min(pnl_pcts) if pnl_pcts else 0.0

        return {
            "strategy_id": strategy_id,
            "trade_count": len(trades),
            "closed_count": len(closed),
            "open_count": len(open_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl_usd": round(total_pnl_usd, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "avg_pnl_pct": round(avg_pnl_pct, 2),
            "max_win_pct": round(max_win_pct, 2),
            "max_loss_pct": round(max_loss_pct, 2),
        }

    # ── 对比：模拟盘 vs 实盘 ─────────────────────────────────

    async def get_comparison(
        self, strategy_id: str
    ) -> Dict[str, Any]:
        """
        模拟盘 vs 实盘对比 (v1.1 Q6)

        Returns:
            {paper: {...stats}, live: {...stats}}
        """
        paper_stats = await self.get_stats(strategy_id)

        # 获取实盘统计（agent_executions 表）
        live_stats = {
            "trade_count": 0,
            "win_rate": 0.0,
            "total_pnl_usd": 0.0,
        }
        try:
            res = (
                get_db()
                .table("agent_executions")
                .select("*")
                .eq("strategy_id", strategy_id)
                .eq("status", "confirmed")
                .execute()
            )
            rows = res.data or []
            if rows:
                live_stats["trade_count"] = len(rows)
                # 简单 PnL 计算（按 token 分组）
                by_token = {}  # type: Dict[str, Dict[str, float]]
                for r in rows:
                    tk = r.get("token_address", "")
                    if tk not in by_token:
                        by_token[tk] = {"buy": 0.0, "sell": 0.0}
                    amt = float(r.get("amount_usd") or 0)
                    if r.get("action") == "buy":
                        by_token[tk]["buy"] += amt
                    elif r.get("action") == "sell":
                        by_token[tk]["sell"] += amt

                total_pnl = sum(v["sell"] - v["buy"] for v in by_token.values())
                wins = sum(1 for v in by_token.values() if v["sell"] > v["buy"])
                live_stats["total_pnl_usd"] = round(total_pnl, 2)
                if by_token:
                    live_stats["win_rate"] = round(
                        (wins / len(by_token)) * 100, 2
                    )
        except Exception as e:
            log.error("Paper get_comparison live stats error: %s", e)

        return {
            "strategy_id": strategy_id,
            "paper": paper_stats,
            "live": live_stats,
        }


# ── 全局单例 ──────────────────────────────────────────────────

_paper_engine: Optional[PaperEngine] = None


def get_paper_engine() -> PaperEngine:
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperEngine()
    return _paper_engine


# ── 定时任务入口 ──────────────────────────────────────────────

async def run_paper_check_exits():
    """定时任务：检查模拟盘 SL/TP"""
    engine = get_paper_engine()
    await engine.check_exits()


async def run_paper_check_reminders():
    """定时任务：检查 3 天提醒 + 7 天暂停"""
    engine = get_paper_engine()
    await engine.check_reminders()
