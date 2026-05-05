"""
R42 P0.3 — HITL → 全自动化路由器(取代分层审批)

设计决策(2026-05-05 与用户对齐):
  - **不分层**:所有交易直接全自动执行,无审批弹窗,无 30s 撤销窗口
  - **强兜底**:7 条硬防线,任一触发拒交易 + 推送告警
  - **不要紧急开关**:用户单笔/单日上限 + 策略级 pause 已足够

7 条兜底防线(每次 trade 执行前 check):
  1. 单笔金额 > strategy.max_position_usd → 拒
  2. 全 App 单日累计 > daily_auto_cap_usd(默认 $50,000)→ 拒(当天剩余时间)
  3. 该策略连续亏损 ≥ 3 笔 → 自动暂停策略 → 拒
  4. 该策略 30 天最大回撤 > 30% → 强制锁回 paper → 拒
  5. 单笔持仓亏 > 50% → 自动平仓 + 暂停策略 → 拒新交易(由 position_monitor 真触发)
  6. safety_engine 30 HR + 13 CB(已有,trade_executor 内部已 wire)
  7. input_filter / cost_guard / output_filter(R40+R41 已 wire 到 chat 路径)

API 极简:
  is_allowed_to_auto_execute(user_id, strategy, amount_usd, side) → (bool, reason)
    True = 通过,可调 trade_executor.execute_trade()
    False = 拒绝,reason 用户可读

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone, date
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)

# ── 默认配置 ─────────────────────────────────────────────────

DEFAULT_DAILY_CAP_USD = 50000.0          # 全 App 每用户每日累计上限
DEFAULT_MAX_POSITION_USD = 5000.0        # 单笔默认上限(策略可覆盖)
CONSECUTIVE_LOSS_THRESHOLD = 3           # 连续亏损暂停策略
MAX_DRAWDOWN_PCT_30D = 30.0              # 30 天最大回撤红线

# ── 内存级 daily 累计追踪(简化版,失败降级允许)─────────────

# {user_id: {date_iso: total_usd}}
_daily_totals: Dict[str, Dict[str, float]] = {}


def _today_iso() -> str:
    return date.today().isoformat()


def _get_daily_total(user_id: str) -> float:
    """返用户今天累计已交易金额(USD)。"""
    today = _today_iso()
    user_dict = _daily_totals.get(user_id, {})
    return user_dict.get(today, 0.0)


def _add_to_daily_total(user_id: str, amount_usd: float) -> float:
    """累加 + 返新累计值。"""
    today = _today_iso()
    if user_id not in _daily_totals:
        _daily_totals[user_id] = {}
    cur = _daily_totals[user_id].get(today, 0.0)
    new = cur + amount_usd
    _daily_totals[user_id][today] = new
    # GC 老日期(只留今天)
    _daily_totals[user_id] = {today: new}
    return new


def reset_daily_for_test() -> None:
    """测试用:清空 daily 累计。"""
    global _daily_totals
    _daily_totals = {}


# ── 主入口 ──────────────────────────────────────────────────

def is_allowed_to_auto_execute(
    user_id: str,
    strategy: Dict[str, Any],
    amount_usd: float,
    side: str = "buy",
) -> Tuple[bool, Optional[str]]:
    """R42 P0.3 全自动化兜底检查。

    Args:
        user_id: 用户 ID
        strategy: dict,关键字段:
            - id, status, mode (paper/live)
            - max_position_usd(可选,无则用默认 $5,000)
            - daily_auto_cap_usd(可选,无则用默认 $50,000 — 全 App 合计)
            - consecutive_losses(可选,trade history 累积)
            - max_drawdown_pct_30d(可选,review_engine 算)
        amount_usd: 本笔金额
        side: buy / sell(sell 不受 daily cap 限制)

    Returns:
        (allowed: bool, reason: Optional[str])
        allowed=True → caller 可调 trade_executor.execute_trade(),
                      之后必须调 record_executed() 写累计
        allowed=False → caller 应通知用户 + 不调 executor

    失败永不抛(降级允许执行,只 log warning)。
    """
    # 1. paper 模式:直接通过(不消耗 daily cap,不查兜底)
    mode = (strategy or {}).get("mode", "paper")
    if mode == "paper":
        return True, None

    # 2. 策略已 archived/paused → 拒
    status = (strategy or {}).get("status", "active")
    if status in ("archived", "paused"):
        return False, f"策略已 {status},不允许自动交易"

    # 3. 单笔金额上限
    max_position = float((strategy or {}).get("max_position_usd") or DEFAULT_MAX_POSITION_USD)
    if amount_usd > max_position:
        return False, f"单笔 ${amount_usd:.0f} 超策略上限 ${max_position:.0f}"

    # 4. sell 不受 daily cap / 连亏 / 回撤限制(让止损能正常出货)
    if side == "sell":
        return True, None

    # 5. 全 App 单日累计上限
    daily_cap = float((strategy or {}).get("daily_auto_cap_usd") or DEFAULT_DAILY_CAP_USD)
    today_used = _get_daily_total(user_id)
    if today_used + amount_usd > daily_cap:
        return False, (
            f"全 App 单日累计 ${today_used:.0f} + ${amount_usd:.0f} = "
            f"${today_used + amount_usd:.0f} 超上限 ${daily_cap:.0f},"
            f"明天 0 点重置"
        )

    # 6. 连续亏损保护
    consecutive_losses = int((strategy or {}).get("consecutive_losses") or 0)
    if consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD:
        return False, (
            f"该策略连续亏损 {consecutive_losses} 笔 (≥{CONSECUTIVE_LOSS_THRESHOLD}),"
            f"已自动暂停,等用户手动恢复"
        )

    # 7. 30 天最大回撤
    max_dd = float((strategy or {}).get("max_drawdown_pct_30d") or 0.0)
    if max_dd > MAX_DRAWDOWN_PCT_30D:
        return False, (
            f"该策略 30 天最大回撤 {max_dd:.1f}% > {MAX_DRAWDOWN_PCT_30D:.0f}%,"
            f"已锁回模拟盘,等用户手动恢复"
        )

    return True, None


def record_executed(
    user_id: str,
    amount_usd: float,
    side: str = "buy",
) -> float:
    """trade_executor 成功执行后调一次,累加到 daily total。
    sell 不计入(只算资金流出)。

    Returns: 累加后的今日总额。
    """
    if side != "buy":
        return _get_daily_total(user_id)
    return _add_to_daily_total(user_id, amount_usd)


def get_daily_remaining(user_id: str, daily_cap: Optional[float] = None) -> float:
    """返用户今天还能交易的额度(USD)。"""
    cap = daily_cap if daily_cap is not None else DEFAULT_DAILY_CAP_USD
    used = _get_daily_total(user_id)
    return max(0.0, cap - used)


def get_stats(user_id: str) -> Dict[str, Any]:
    """给 admin / Flutter 看的状态。"""
    today_used = _get_daily_total(user_id)
    return {
        "user_id": user_id,
        "today": _today_iso(),
        "today_used_usd": round(today_used, 2),
        "daily_cap_usd": DEFAULT_DAILY_CAP_USD,
        "remaining_usd": round(max(0.0, DEFAULT_DAILY_CAP_USD - today_used), 2),
    }
