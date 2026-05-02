"""
paper→auto 晋升门槛测试 — R37 P0-2
跑法:python3 -m pytest tests/test_promotion_gate.py -v

验证(对齐 04-agent-spec §5.4 + 03-prd §5.4):
  1. 不足 30 天 → ineligible(reason)
  2. 不足 30 笔 closed → ineligible
  3. avg_pnl_pct < 1% → ineligible
  4. max_drawdown_pct >= 30% → ineligible
  5. 全过 → eligible
  6. go_live() 不通过门槛 → 返 None,strategy mode 不变
  7. go_live(force=True) 绕开门槛 → 切 live(写 audit log 由调用方负责)
  8. go_live() mode != paper → 幂等返 strategy
  9. _compute_paper_stats_sync 累计回撤公式正确(连续 -10/-15 → max_dd 25)
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _mock_strategy(
    strategy_id: str = "strat-1",
    mode: str = "paper",
    status: str = "active",
    days_ago: int = 31,
):
    created_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "id": strategy_id,
        "mode": mode,
        "status": status,
        "created_at": created_at,
    }


def _mock_db_with_trades(trades: list, strategy: dict | None):
    """构造 get_db().table().select()....execute() chain。"""
    db = MagicMock()
    # strategies 表
    strat_chain = MagicMock()
    strat_chain.execute.return_value.data = [strategy] if strategy else []
    # paper trades 表
    trade_chain = MagicMock()
    trade_chain.execute.return_value.data = trades

    def _table(name):
        m = MagicMock()
        if name == "agent_strategies":
            m.select.return_value.eq.return_value = strat_chain
            m.update.return_value.eq.return_value.execute.return_value.data = [
                {**(strategy or {}), "mode": "live"}
            ]
        elif name == "agent_paper_trades":
            m.select.return_value.eq.return_value = trade_chain
        return m

    db.table = _table
    return db


# ── _compute_paper_stats_sync ────────────────────────────────


def test_compute_drawdown_simple():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    # 序列:+10 / -5 / -10 → cum 10 / 5 / -5;peak=10;最大 dd = 10-(-5) = 15
    trades = [
        {"status": "closed", "pnl_pct": 10, "closed_at": "2026-01-01"},
        {"status": "closed", "pnl_pct": -5, "closed_at": "2026-01-02"},
        {"status": "closed", "pnl_pct": -10, "closed_at": "2026-01-03"},
    ]
    db = _mock_db_with_trades(trades, None)
    with patch("agent.strategy_manager.get_db", return_value=db):
        stats = sm._compute_paper_stats_sync("s1")
    assert stats["closed_count"] == 3
    assert abs(stats["avg_pnl_pct"] - (-5/3)) < 0.01
    assert stats["max_drawdown_pct"] == 15.0
    assert stats["win_rate"] == pytest.approx(33.33, abs=0.01)


def test_compute_drawdown_no_trades():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    db = _mock_db_with_trades([], None)
    with patch("agent.strategy_manager.get_db", return_value=db):
        stats = sm._compute_paper_stats_sync("s1")
    assert stats["closed_count"] == 0
    assert stats["max_drawdown_pct"] == 0.0


# ── check_promotion_eligibility ──────────────────────────────


def test_eligibility_strategy_not_found():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    db = _mock_db_with_trades([], None)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("ghost")
    assert r["eligible"] is False
    assert "strategy_not_found" in r["reasons"]


def test_eligibility_strategy_not_active():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(status="archived")
    db = _mock_db_with_trades([], s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("s1")
    assert r["eligible"] is False
    assert any("strategy_not_active" in x for x in r["reasons"])


def test_eligibility_too_few_days():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=15)  # 只 15 天
    # 即便 trades 充足
    trades = [
        {"status": "closed", "pnl_pct": 2.0, "closed_at": f"2026-01-{i:02d}"}
        for i in range(1, 31)
    ]
    db = _mock_db_with_trades(trades, s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("s1")
    assert r["eligible"] is False
    assert any("need_30d_active" in x for x in r["reasons"])


def test_eligibility_too_few_trades():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=60)  # 60 天 OK
    trades = [
        {"status": "closed", "pnl_pct": 5.0, "closed_at": f"2026-01-{i:02d}"}
        for i in range(1, 11)  # 只 10 笔
    ]
    db = _mock_db_with_trades(trades, s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("s1")
    assert r["eligible"] is False
    assert any("need_30_closed_trades" in x for x in r["reasons"])


def test_eligibility_avg_pnl_too_low():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=60)
    # 30 笔 closed 但 avg pnl = 0.5%
    trades = [
        {"status": "closed", "pnl_pct": 0.5, "closed_at": f"2026-01-{i:02d}"}
        for i in range(1, 31)
    ]
    db = _mock_db_with_trades(trades, s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("s1")
    assert r["eligible"] is False
    assert any("need_avg_pnl_>=1.0%" in x for x in r["reasons"])


def test_eligibility_drawdown_too_large():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=60)
    # avg ok 但 drawdown 超 30%:序列 +50 -40 +30 → cum 50/10/40;peak=50; dd=40
    trades = [
        {"status": "closed", "pnl_pct": 50, "closed_at": "2026-01-01"},
        {"status": "closed", "pnl_pct": -40, "closed_at": "2026-01-02"},
        {"status": "closed", "pnl_pct": 30, "closed_at": "2026-01-03"},
    ] + [
        {"status": "closed", "pnl_pct": 0.5, "closed_at": f"2026-02-{i:02d}"}
        for i in range(1, 28)
    ]  # 凑到 30 笔
    db = _mock_db_with_trades(trades, s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("s1")
    assert r["eligible"] is False
    assert any("max_drawdown" in x and ">=" in x for x in r["reasons"])


def test_eligibility_all_pass():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=45)
    # 30 笔,avg pnl 2%,小回撤
    trades = [
        {"status": "closed", "pnl_pct": 2.0, "closed_at": f"2026-01-{i:02d}"}
        for i in range(1, 31)
    ]
    db = _mock_db_with_trades(trades, s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        r = sm.check_promotion_eligibility("s1")
    assert r["eligible"] is True, f"应通过但被拦: {r['reasons']}"
    assert r["closed_count"] == 30
    assert r["avg_pnl_pct"] == 2.0


# ── go_live() ────────────────────────────────────────────────


def test_go_live_blocks_when_not_eligible():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=10)  # 不足 30 天
    db = _mock_db_with_trades([], s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        result = sm.go_live("s1")
    assert result is None, "不通过门槛应返 None"


def test_go_live_force_bypasses_gate():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=1)
    db = _mock_db_with_trades([], s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        # mock update_strategy 返成功
        with patch.object(
            sm, "update_strategy",
            return_value={"id": "s1", "mode": "live"},
        ):
            result = sm.go_live("s1", force=True, actor="admin")
    assert result is not None
    assert result["mode"] == "live"


def test_go_live_idempotent_when_already_live():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(mode="live")
    db = _mock_db_with_trades([], s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        result = sm.go_live("s1")
    assert result is not None
    assert result["mode"] == "live"  # 直接返,无门槛检查


def test_go_live_when_not_active_returns_none():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(status="archived")
    db = _mock_db_with_trades([], s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        result = sm.go_live("s1")
    assert result is None


def test_go_live_passes_when_eligible():
    from agent.strategy_manager import StrategyManager
    sm = StrategyManager()
    s = _mock_strategy(days_ago=45)
    trades = [
        {"status": "closed", "pnl_pct": 2.0, "closed_at": f"2026-01-{i:02d}"}
        for i in range(1, 31)
    ]
    db = _mock_db_with_trades(trades, s)
    with patch("agent.strategy_manager.get_db", return_value=db):
        with patch.object(
            sm, "update_strategy",
            return_value={"id": "s1", "mode": "live"},
        ):
            result = sm.go_live("s1")
    assert result is not None
    assert result["mode"] == "live"
