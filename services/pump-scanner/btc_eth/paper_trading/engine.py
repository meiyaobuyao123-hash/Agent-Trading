"""模拟盘交易引擎 — 自动执行信号 + 持仓管理"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import uuid

from btc_eth import storage
from btc_eth.config import PAPER_DEFAULT_CAPITAL, PAPER_MAX_POSITION_PCT

log = logging.getLogger(__name__)


class PaperTradingEngine:
    """模拟盘引擎"""

    async def init_portfolio(
        self, user_id: str, capital: float = PAPER_DEFAULT_CAPITAL,
        risk_preference: str = "moderate"
    ) -> Dict[str, Any]:
        """初始化模拟盘"""
        portfolio = {
            "user_id": user_id,
            "mode": "paper",
            "initial_capital": capital,
            "current_equity": capital,
            "peak_equity": capital,
            "risk_preference": risk_preference,
            "is_active": True,
        }
        storage.upsert_portfolio(portfolio)
        log.info("[PaperTrading] 初始化: user=%s capital=$%.0f risk=%s",
                 user_id[:8], capital, risk_preference)
        return portfolio

    async def process_signal(
        self, user_id: str, signal: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """自动执行信号"""
        portfolio = storage.get_portfolio(user_id)
        if not portfolio or not portfolio.get("is_active"):
            return None

        equity = float(portfolio.get("current_equity", 0))
        if equity <= 0:
            return None

        # 计算仓位大小
        risk_pref = portfolio.get("risk_preference", "moderate")
        position_pct = {
            "conservative": 0.10,
            "moderate": 0.20,
            "aggressive": 0.30,
        }.get(risk_pref, 0.20)

        position_pct = min(position_pct, PAPER_MAX_POSITION_PCT)
        amount_usd = equity * position_pct

        entry_price = float(signal.get("entry_price", 0))
        if entry_price <= 0:
            return None

        asset = signal.get("asset", "BTC")
        quantity = amount_usd / entry_price

        trade = {
            "user_id": user_id,
            "signal_id": signal.get("id"),
            "asset": asset,
            "action": "buy",
            "side": signal.get("signal_type", "long"),
            "entry_price": entry_price,
            "quantity": round(quantity, 8),
            "amount_usd": round(amount_usd, 2),
            "status": "open",
            "stop_loss": float(signal.get("stop_loss", 0)),
            "take_profit": float(signal.get("target_price", 0)),
        }

        storage.save_paper_trade(trade)

        # 更新组合净值（扣除买入金额）
        new_equity = equity - amount_usd
        storage.upsert_portfolio({
            "user_id": user_id,
            "current_equity": round(new_equity, 2),
        })

        log.info("[PaperTrading] 买入 %s %.6f @ $%.2f ($%.0f)",
                 asset, quantity, entry_price, amount_usd)
        return trade

    async def check_exits(
        self, user_id: str, current_prices: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """检查止盈止损"""
        from database import get_db
        try:
            res = (get_db().table("btc_eth_paper_trades")
                   .select("*").eq("user_id", user_id).eq("status", "open").execute())
            open_trades = res.data or []
        except Exception:
            return []

        closed = []
        for trade in open_trades:
            asset = trade.get("asset", "BTC")
            price = current_prices.get(asset, 0)
            if price <= 0:
                continue

            entry = float(trade.get("entry_price", 0))
            sl = float(trade.get("stop_loss", 0))
            tp = float(trade.get("take_profit", 0))
            side = trade.get("side", "long")
            quantity = float(trade.get("quantity", 0))

            should_close = False
            reason = ""

            if side == "long":
                if sl > 0 and price <= sl:
                    should_close = True
                    reason = "hit_stop"
                elif tp > 0 and price >= tp:
                    should_close = True
                    reason = "hit_target"
            else:  # short
                if sl > 0 and price >= sl:
                    should_close = True
                    reason = "hit_stop"
                elif tp > 0 and price <= tp:
                    should_close = True
                    reason = "hit_target"

            if should_close:
                pnl_usd = (price - entry) * quantity if side == "long" else (entry - price) * quantity
                pnl_pct = (price / entry - 1) * 100 if side == "long" else (1 - price / entry) * 100

                updates = {
                    "exit_price": price,
                    "pnl_usd": round(pnl_usd, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "status": reason,
                    "closed_at": datetime.now(timezone.utc).isoformat(),
                }

                try:
                    get_db().table("btc_eth_paper_trades").update(updates).eq("id", trade["id"]).execute()
                except Exception:
                    pass

                # 更新组合净值
                portfolio = storage.get_portfolio(user_id)
                if portfolio:
                    returned = float(trade.get("amount_usd", 0)) + pnl_usd
                    new_equity = float(portfolio.get("current_equity", 0)) + returned
                    peak = max(float(portfolio.get("peak_equity", 0)), new_equity)
                    storage.upsert_portfolio({
                        "user_id": user_id,
                        "current_equity": round(new_equity, 2),
                        "peak_equity": round(peak, 2),
                    })

                trade.update(updates)
                closed.append(trade)
                log.info("[PaperTrading] 平仓 %s %s: PNL $%.2f (%.1f%%)",
                         asset, reason, pnl_usd, pnl_pct)

        return closed

    async def get_metrics(self, user_id: str) -> Dict[str, Any]:
        """计算绩效指标"""
        from database import get_db
        try:
            res = (get_db().table("btc_eth_paper_trades")
                   .select("*").eq("user_id", user_id)
                   .neq("status", "open").execute())
            trades = res.data or []
        except Exception:
            trades = []

        if not trades:
            return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}

        wins = [t for t in trades if (t.get("pnl_usd") or 0) > 0]
        losses = [t for t in trades if (t.get("pnl_usd") or 0) <= 0]
        total_pnl = sum(float(t.get("pnl_usd", 0) or 0) for t in trades)
        avg_win = sum(float(t.get("pnl_usd", 0) or 0) for t in wins) / max(len(wins), 1)
        avg_loss = abs(sum(float(t.get("pnl_usd", 0) or 0) for t in losses) / max(len(losses), 1))

        portfolio = storage.get_portfolio(user_id) or {}
        equity = float(portfolio.get("current_equity", 0))
        initial = float(portfolio.get("initial_capital", 10000))
        peak = float(portfolio.get("peak_equity", initial))
        drawdown = (peak - equity) / peak * 100 if peak > 0 else 0

        return {
            "total_trades": len(trades),
            "win_rate": round(len(wins) / len(trades) * 100, 1),
            "wins": len(wins),
            "losses": len(losses),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round((equity / initial - 1) * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(avg_win / max(avg_loss, 0.01), 2),
            "max_drawdown_pct": round(drawdown, 2),
            "current_equity": equity,
            "initial_capital": initial,
        }
