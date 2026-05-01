"""
S07 review_engine 单元测试 — W3 D5+
覆盖:
  - cold_start 三态(no_trades / few_trades / normal)
  - metrics 计算(win_rate / EV / Sharpe / max_drawdown / Kelly)
  - 规则化 insights(win_pattern / loss_pattern / risk_warning / observation)
  - 规则化 rule_proposals(收紧 / 加仓 阈值)
  - period 窗口正确

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_review_engine.py -v
"""
from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.review_engine import (  # noqa: E402
    _avg_pnl_pct,
    _cold_start_state,
    _compute_metrics,
    _make_summary,
    _rule_based_insights,
    _rule_based_proposals,
    _wilson_lower,
    generate_review,
)


# ── helpers ─────────────────────────────────────────────────

def _trade(addr, chain, pnl_ratio, is_closed=True, d3=0.0):
    return {
        "token_address": addr,
        "chain": chain,
        "buy_count": 1,
        "sell_count": 1 if is_closed else 0,
        "buy_usd": 100.0,
        "sell_usd": 100.0 * pnl_ratio if is_closed and pnl_ratio else 0.0,
        "avg_buy_price": 1.0,
        "avg_sell_price": pnl_ratio if is_closed else None,
        "pnl_ratio": pnl_ratio if is_closed else None,
        "realized_pnl_usd": 100.0 * (pnl_ratio - 1) if is_closed and pnl_ratio else 0.0,
        "d3_pct": d3,
        "first_executed_at": "2026-04-30T10:00:00Z",
        "is_closed": is_closed,
        "strategy_id": "s-1",
    }


# ── cold_start_state ────────────────────────────────────────

def test_cold_start_no_trades():
    assert _cold_start_state(0) == "no_trades"

def test_cold_start_few_trades():
    assert _cold_start_state(3) == "few_trades"

def test_cold_start_normal():
    assert _cold_start_state(10) == "normal"


# ── _compute_metrics ────────────────────────────────────────

def test_metrics_empty_trades():
    m = _compute_metrics([])
    assert m["trade_count"] == 0
    assert m["win_rate"] == 0.0


def test_metrics_all_wins():
    trades = [_trade(f"a{i}", "SOL", 1.5) for i in range(5)]
    m = _compute_metrics(trades)
    assert m["trade_count"] == 5
    assert m["win_rate"] == 1.0
    assert m["ev_pct"] == 50.0
    assert m["max_drawdown_pct"] == 0.0


def test_metrics_mixed_wins_losses():
    trades = (
        [_trade(f"w{i}", "SOL", 1.5) for i in range(3)]
        + [_trade(f"l{i}", "SOL", 0.7) for i in range(2)]
    )
    m = _compute_metrics(trades)
    assert m["trade_count"] == 5
    assert m["win_rate"] == 0.6
    # EV = (1.5*3 + 0.7*2)/5 - 1 = (5.9/5) - 1 = 0.18 → 18%
    assert m["ev_pct"] == 18.0
    assert m["profit_factor"] > 0
    assert m["kelly_fraction"] is not None


def test_metrics_max_drawdown():
    """连续亏损 → max_drawdown 显著为负。"""
    trades = [
        _trade("a1", "SOL", 1.5),
        _trade("a2", "SOL", 0.7),  # 累计 1.5 * 0.7 = 1.05
        _trade("a3", "SOL", 0.6),  # 累计 1.05 * 0.6 = 0.63 → drawdown 0.63/1.5 - 1 = -58%
    ]
    m = _compute_metrics(trades)
    assert m["max_drawdown_pct"] < -30


def test_metrics_open_positions_use_d3():
    """全开仓时用 D3 估算 win_rate / ev。"""
    trades = [
        _trade("a1", "SOL", None, is_closed=False, d3=25.0),  # win
        _trade("a2", "SOL", None, is_closed=False, d3=15.0),  # not win
        _trade("a3", "SOL", None, is_closed=False, d3=30.0),  # win
    ]
    m = _compute_metrics(trades)
    assert m["trade_count"] == 3
    assert abs(m["win_rate"] - 2 / 3) < 0.001  # 2/3
    assert m["ev_pct"] == round((25 + 15 + 30) / 3, 2)


# ── _make_summary ───────────────────────────────────────────

def test_summary_no_trades():
    s = _make_summary("daily", {"trade_count": 0}, "no_trades")
    assert "暂无交易" in s["headline"]


def test_summary_few_trades():
    s = _make_summary("weekly", {"trade_count": 3, "win_rate": 0.66, "ev_pct": 5.0}, "few_trades")
    assert "样本不足" in s["headline"]


def test_summary_normal_good_performance():
    s = _make_summary("monthly", {
        "trade_count": 30, "win_rate": 0.65, "ev_pct": 3.5,
        "sharpe": 1.5, "max_drawdown_pct": -5, "profit_factor": 1.8,
    }, "normal")
    assert "本月" in s["headline"]
    assert "65%" in s["headline"]
    assert "良好" in s["body"]


def test_summary_normal_bad_performance():
    s = _make_summary("daily", {
        "trade_count": 10, "win_rate": 0.3, "ev_pct": -5,
        "sharpe": 0.5, "max_drawdown_pct": -8, "profit_factor": 0.7,
    }, "normal")
    assert "亏损" in s["body"]


# ── _rule_based_insights ────────────────────────────────────

def test_insights_win_pattern():
    trades = [_trade(f"w{i}", "SOL", 1.4) for i in range(4)]
    metrics = {"trade_count": 4, "win_rate": 1.0, "max_drawdown_pct": 0,
               "ev_pct": 40.0, "sharpe": 1.0, "profit_factor": 5.0}
    insights = _rule_based_insights(trades, metrics)
    types = [i["type"] for i in insights]
    assert "win_pattern" in types


def test_insights_loss_pattern():
    trades = [_trade(f"l{i}", "EVM", 0.6) for i in range(4)]
    metrics = {"trade_count": 4, "win_rate": 0.0, "max_drawdown_pct": -40,
               "ev_pct": -40.0, "sharpe": -1.0, "profit_factor": 0.1}
    insights = _rule_based_insights(trades, metrics)
    types = [i["type"] for i in insights]
    assert "loss_pattern" in types
    assert "risk_warning" in types  # max_dd -40 触发


def test_insights_observation_when_no_pattern():
    """中性表现 + 没明显 win/loss pattern → observation。"""
    trades = [_trade("m1", "SOL", 1.05), _trade("m2", "EVM", 0.95),
              _trade("m3", "BSC", 1.02), _trade("m4", "Base", 0.99),
              _trade("m5", "SOL", 1.01)]
    metrics = {"trade_count": 5, "win_rate": 0.6, "max_drawdown_pct": -2,
               "ev_pct": 0.4, "sharpe": 0.3, "profit_factor": 1.1}
    insights = _rule_based_insights(trades, metrics)
    # 5 笔无 3 笔同链 → 不会触发 win_pattern;loss < 3 也不触发
    types = [i["type"] for i in insights]
    assert "observation" in types or "loss_pattern" in types


# ── _rule_based_proposals ───────────────────────────────────

def test_proposals_few_trades_no_proposals():
    trades = [_trade(f"a{i}", "SOL", 1.0) for i in range(3)]
    proposals = _rule_based_proposals(trades, {"trade_count": 3, "win_rate": 0.5,
                                                "profit_factor": 1.0})
    assert proposals == []


def test_proposals_tighten_on_loss_streak():
    trades = [_trade(f"l{i}", "SOL", 0.6) for i in range(7)] + [
        _trade(f"w{i}", "SOL", 1.3) for i in range(3)
    ]
    metrics = {"trade_count": 10, "win_rate": 0.3, "profit_factor": 0.5}
    proposals = _rule_based_proposals(trades, metrics)
    assert len(proposals) >= 1
    assert any("tighten" in p["proposal_id"] for p in proposals)


def test_proposals_scale_on_high_profit_factor():
    trades = [_trade(f"w{i}", "SOL", 1.4) for i in range(20)]
    metrics = {"trade_count": 20, "win_rate": 0.7, "profit_factor": 2.5}
    proposals = _rule_based_proposals(trades, metrics)
    assert any("scale" in p["proposal_id"] for p in proposals)


# ── _wilson_lower ───────────────────────────────────────────

def test_wilson_lower_zero_n():
    assert _wilson_lower(0.5, 0) is None


def test_wilson_lower_high_n_high_p():
    """100 笔胜率 80% → Wilson 下界 ~71%。"""
    lo = _wilson_lower(0.8, 100)
    assert lo is not None
    assert 0.7 < lo < 0.85


def test_wilson_lower_low_n_high_p():
    """3 笔全赢 → Wilson 下界很低(样本太少)。"""
    lo = _wilson_lower(1.0, 3)
    assert lo is not None
    assert lo < 0.5  # 3 笔不足以确认 100% 胜率


# ── _avg_pnl_pct ────────────────────────────────────────────

def test_avg_pnl_pct():
    trades = [_trade("a", "SOL", 1.5), _trade("b", "SOL", 0.5)]
    # (50% + -50%) / 2 = 0%
    assert _avg_pnl_pct(trades) == 0.0


# ── generate_review (integration with mocked DB) ────────────

@pytest.mark.asyncio
async def test_generate_review_no_trades():
    """DB 失败 → 返 no_trades 状态。"""
    from agent import review_engine
    with patch.object(review_engine, "_load_trades", return_value=[]):
        r = await review_engine.generate_review(period="daily")
    assert r["cold_start_state"] == "no_trades"
    assert r["metrics"]["trade_count"] == 0
    assert r["insights"] == []


@pytest.mark.asyncio
async def test_generate_review_period_window():
    from agent import review_engine
    with patch.object(review_engine, "_load_trades", return_value=[]):
        r = await review_engine.generate_review(period="weekly")
    pf = datetime.fromisoformat(r["period_from"].replace("Z", "+00:00"))
    pt = datetime.fromisoformat(r["period_to"].replace("Z", "+00:00"))
    assert (pt - pf).days == 7


@pytest.mark.asyncio
async def test_generate_review_with_trades():
    from agent import review_engine
    fake_trades = [
        _trade(f"w{i}", "SOL", 1.3) for i in range(8)
    ] + [
        _trade(f"l{i}", "SOL", 0.7) for i in range(2)
    ]
    with patch.object(review_engine, "_load_trades", return_value=fake_trades):
        r = await review_engine.generate_review(period="weekly")
    assert r["cold_start_state"] == "normal"
    assert r["metrics"]["trade_count"] == 10
    assert r["metrics"]["win_rate"] == 0.8
    assert r["source"] == "rule_engine"
